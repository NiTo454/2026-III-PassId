import base64

from django.core import signing
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator

from academico.models import AsistenciaClase, Inscripcion
from core.mixins import PassIdPermissionMixin
from core.utils import generar_qr
from usuarios.models import Usuario
from eventos.forms import EscaneoAsistenciaEventoForm
from eventos.models import Evento

from .forms import EscaneoAsistenciaForm


QR_SIGNING_SALT = "asistencia_qr.matricula"
QR_TOKEN_MAX_AGE_SECONDS = 300


class MiQrView(PassIdPermissionMixin, TemplateView):
    template_name = "asistencia_qr/mi_qr.html"
    required_permission = "asistencia_qr.ver_mi_qr"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["matricula"] = user.matricula
        context["nombre_completo"] = " ".join(
            part for part in (user.nombre, user.apaterno, user.amaterno) if part
        ) or user.username
        return context


@method_decorator(never_cache, name="dispatch")
class QrImagenView(PassIdPermissionMixin, View):
    required_permission = "asistencia_qr.ver_mi_qr"

    def get(self, request, *args, **kwargs):
        matricula = request.user.matricula
        if not matricula:
            return HttpResponse(
                "Tu cuenta no tiene una matrícula registrada.",
                status=400,
                content_type="text/plain; charset=utf-8",
            )

        token = signing.dumps(
            {"matricula": matricula},
            salt=QR_SIGNING_SALT,
            compress=True,
        )
        response = HttpResponse(
            base64.b64decode(generar_qr(token)),
            content_type="image/png",
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


class EscanearAsistenciaView(LoginRequiredMixin, TemplateView):
    template_name = "asistencia_qr/lector.html"
    login_url = "autenticacion:login"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        self.can_scan_classes = (
            user.is_superuser or user.has_perm("asistencia_qr.escanear_asistencia")
        )
        self.can_scan_events = (
            user.is_superuser or user.has_perm("asistencia.add_asistencia")
        )
        if not self.can_scan_classes and not self.can_scan_events:
            messages.error(request, "No tienes permiso para registrar asistencias.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_id = self.request.GET.get("evento")
        selected_event = None
        if self.can_scan_events and event_id and event_id.isdigit():
            selected_event = Evento.objects.filter(pk=event_id).first()

        initial_mode = self.request.GET.get("mode")
        if initial_mode not in {"clase", "evento"}:
            initial_mode = "evento" if selected_event and not self.can_scan_classes else "clase"
        if initial_mode == "clase" and not self.can_scan_classes:
            initial_mode = "evento"
        elif initial_mode == "evento" and not self.can_scan_events:
            initial_mode = "clase"

        context["class_form"] = (
            EscaneoAsistenciaForm(user=self.request.user)
            if self.can_scan_classes else None
        )
        context["event_form"] = (
            EscaneoAsistenciaEventoForm(
                user=self.request.user,
                initial_evento_id=selected_event.pk if selected_event else None,
            )
            if self.can_scan_events else None
        )
        context["can_scan_classes"] = self.can_scan_classes
        context["can_scan_events"] = self.can_scan_events
        context["scanner_mode"] = initial_mode
        context["selected_event"] = selected_event
        context["class_submit_url"] = reverse("asistencia_qr:registrar")
        context["event_submit_url"] = reverse("eventos:registrar_qr")
        return context


class RegistrarAsistenciaQrView(PassIdPermissionMixin, View):
    required_permission = "asistencia_qr.escanear_asistencia"

    def post(self, request, *args, **kwargs):
        form = EscaneoAsistenciaForm(request.POST, user=request.user)
        if not form.is_valid():
            return JsonResponse(
                {"ok": False, "message": "Selecciona una clase y escanea un QR válido."},
                status=400,
            )

        token = form.cleaned_data["token"]
        if token:
            try:
                payload = signing.loads(
                    token,
                    salt=QR_SIGNING_SALT,
                    max_age=QR_TOKEN_MAX_AGE_SECONDS,
                )
            except signing.SignatureExpired:
                return JsonResponse(
                    {"ok": False, "message": "El QR venció. Pide al estudiante que actualice su código."},
                    status=400,
                )
            except signing.BadSignature:
                return JsonResponse(
                    {"ok": False, "message": "El QR no es válido o fue alterado."},
                    status=400,
                )

            matricula = payload.get("matricula") if isinstance(payload, dict) else None
            if not isinstance(matricula, str) or not matricula:
                return JsonResponse(
                    {"ok": False, "message": "El QR no contiene una matrícula válida."},
                    status=400,
                )
            metodo = "qr"
        else:
            matricula = form.cleaned_data["matricula"]
            metodo = "manual"

        usuarios = list(Usuario.objects.filter(matricula=matricula).order_by("pk")[:2])
        if len(usuarios) != 1:
            if not usuarios:
                return JsonResponse(
                    {"ok": False, "status": "usuario_no_encontrado",
                     "message": "No existe una cuenta con esa matrícula."},
                    status=404,
                )
            return JsonResponse(
                {"ok": False, "status": "matricula_duplicada",
                 "message": "Hay varias cuentas con esa matrícula. Contacta al administrador."},
                status=409,
            )
        estudiante = usuarios[0]
        if not estudiante.activo:
            return JsonResponse(
                {"ok": False, "status": "cuenta_inactiva",
                 "message": "La cuenta del alumno está inactiva. Un administrador debe activarla."},
                status=403,
            )

        horario = form.cleaned_data["horario"]
        enrollment_permission = "asistencia_qr.inscribir_estudiante_en_clase"
        can_enroll = (
            request.user.is_superuser
            or request.user.has_perm("asistencia_qr.escanear_asistencia")
            or request.user.has_perm(enrollment_permission)
        )
        enrollment_filter = {
            "usuario": estudiante,
            "materia": horario.materia,
            "grupo": horario.grupo,
            "periodo": horario.periodo,
        }

        with transaction.atomic():
            inscripcion = Inscripcion.objects.select_for_update().filter(
                **enrollment_filter
            ).first()
            if form.cleaned_data["inscribir"]:
                if not can_enroll:
                    return JsonResponse(
                        {"ok": False, "status": "sin_permiso",
                         "message": "No tienes permiso para inscribir alumnos desde el lector."},
                        status=403,
                    )
                if inscripcion is None:
                    inscripcion = Inscripcion.objects.create(
                        **enrollment_filter,
                        activa=True,
                    )
                    enrollment_message = "Inscripción creada"
                elif not inscripcion.activa:
                    inscripcion.activa = True
                    inscripcion.save(update_fields=["activa"])
                    enrollment_message = "Inscripción reactivada"
                else:
                    enrollment_message = "Inscripción ya activa"
            elif inscripcion is None or not inscripcion.activa:
                state = "sin_inscripcion" if inscripcion is None else "inscripcion_inactiva"
                message = (
                    "El alumno no está inscrito en esta materia, grupo y periodo."
                    if inscripcion is None
                    else "El alumno tiene una inscripción inactiva en esta materia, grupo y periodo."
                )
                return JsonResponse(
                    {
                        "ok": False,
                        "status": state,
                        "message": message,
                        "can_enroll": can_enroll,
                        "enrollment_required": True,
                    },
                    status=403,
                )
            else:
                enrollment_message = "Inscripción activa"

            ahora = timezone.localtime()
            asistencia, creada = AsistenciaClase.objects.get_or_create(
                horario=horario,
                usuario=estudiante,
                fecha=ahora.date(),
                defaults={
                    "hora": ahora.time().replace(microsecond=0),
                    "estado": "presente",
                    "metodo": metodo,
                },
            )
        if not creada:
            return JsonResponse(
                {
                    "ok": False,
                    "status": "asistencia_duplicada",
                    "duplicate": True,
                    "message": f"{estudiante} ya tiene asistencia registrada para esta clase hoy.",
                },
                status=409,
            )

        return JsonResponse(
            {
                "ok": True,
                "status": "inscrito",
                "message": (
                    f"{enrollment_message}. Asistencia registrada para "
                    f"{estudiante} ({matricula})."
                ),
                "matricula": matricula,
                "hora": asistencia.hora.strftime("%H:%M:%S"),
            }
        )


class AsistenciaClaseListView(PassIdPermissionMixin, ListView):
    model = AsistenciaClase
    template_name = "asistencia_qr/asistencia_list.html"
    context_object_name = "asistencias"
    paginate_by = 25
    required_permission = "asistencia_qr.ver_asistencias"

    def get_queryset(self):
        asistencias = AsistenciaClase.objects.select_related(
            "usuario", "horario", "horario__materia"
        )
        if not self.request.user.is_superuser:
            asistencias = asistencias.filter(horario__profesor=self.request.user)
        return asistencias.order_by("-fecha", "-hora")
