from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.views.generic.edit import FormView
from django.db.models import Q, Exists, OuterRef
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.core import signing
from urllib.parse import urlencode
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
import json
from urllib.parse import urlencode
from django.urls import reverse
from django.views.generic import RedirectView
from core.mixins import PassIdPermissionMixin
from usuarios.models import Usuario
from .models import Evento, Registro, Asistencia
from .forms import (
    EventoForm,
    RegistroEventoForm,
    RegistroMultipleEventoForm,
    RegistroImportForm,
    AsistenciaEventoForm,
    EscaneoAsistenciaEventoForm,
)
from .importacion_registros import import_registros



class EventoListView(PassIdPermissionMixin, ListView):
    model = Evento
    template_name = "eventos/evento_list.html"
    context_object_name = "eventos"
    paginate_by = 10
    required_permission = "evento.view_evento"
    create_permission = "evento.add_evento"

    def get_queryset(self):
        queryset = Evento.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) |
                Q(lugar__icontains=query) |
                Q(responsable_interno__icontains=query) |
                Q(responsable_externo__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Catálogo de Eventos"
        context["page_subtitle"] = "Gestión de conferencias, talleres y actividades de PassID"
        context["create_url"] = reverse_lazy("eventos:evento_create")
        context["create_label"] = "Nuevo Evento"
        context["search_placeholder"] = "Buscar por nombre, lugar o responsable..."
        return context


class EventoCreateView(PassIdPermissionMixin, CreateView):
    model = Evento
    form_class = EventoForm
    template_name = "eventos/evento_form.html"
    success_url = reverse_lazy("eventos:evento_list")
    required_permission = "evento.add_evento"

    def form_valid(self, form):
        messages.success(self.request, f"Evento '{form.instance.nombre}' programado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Programar Nuevo Evento"
        context["subtitle"] = "Define fechas, lugar y requerimientos de asistencia"
        context["button_text"] = "Guardar Evento"
        context["cancel_url"] = reverse_lazy("eventos:evento_list")
        return context


class EventoUpdateView(PassIdPermissionMixin, UpdateView):
    model = Evento
    form_class = EventoForm
    template_name = "eventos/evento_form.html"
    success_url = reverse_lazy("eventos:evento_list")
    required_permission = "evento.change_evento"

    def form_valid(self, form):
        messages.success(self.request, f"Evento '{form.instance.nombre}' actualizado con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Evento: {self.object.nombre}"
        context["subtitle"] = "Modifica los detalles del evento seleccionado"
        context["button_text"] = "Actualizar Evento"
        context["cancel_url"] = reverse_lazy("eventos:evento_list")
        return context


class EventoDeleteView(PassIdPermissionMixin, DeleteView):
    model = Evento
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("eventos:evento_list")
    required_permission = "evento.delete_evento"

    def delete(self, request, *args, **kwargs):
        evento = self.get_object()
        messages.success(request, f"Evento '{evento.nombre}' cancelado y eliminado.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Eliminar Evento: {self.object.nombre}"
        context["cancel_url"] = reverse_lazy("eventos:evento_list")
        return context



class RegistroListView(PassIdPermissionMixin, ListView):
    model = Registro
    template_name = "eventos/registro_list.html"
    context_object_name = "registros"
    paginate_by = 10
    required_permission = "registro.view_registro"
    create_permission = "registro.add_registro"

    def get_filters(self):
        return {
            "evento": self.request.GET.get("evento", "").strip(),
            "grupo": self.request.GET.get("grupo", "").strip(),
            "categoria": self.request.GET.get("categoria", "").strip(),
            "q": self.request.GET.get("q", "").strip(),
        }

    def get_queryset(self):
        self.filters = self.get_filters()
        queryset = Registro.objects.select_related("evento", "usuario").order_by("-fecha_registro")
        if self.filters["evento"].isdecimal():
            queryset = queryset.filter(evento_id=self.filters["evento"])
        if self.filters["grupo"]:
            queryset = queryset.filter(usuario__grupo=self.filters["grupo"])
        if self.filters["categoria"]:
            queryset = queryset.filter(usuario__categoria=self.filters["categoria"])

        query = self.filters["q"]
        if query:
            queryset = queryset.filter(
                Q(evento__nombre__icontains=query) |
                Q(usuario__nombre__icontains=query) |
                Q(usuario__apaterno__icontains=query) |
                Q(usuario__amaterno__icontains=query) |
                Q(usuario__matricula__icontains=query) |
                Q(usuario__username__icontains=query) |
                Q(equipo__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = getattr(self, "filters", self.get_filters())
        context["query"] = filters["q"]
        context["filters"] = filters
        context["eventos"] = Evento.objects.all().order_by("nombre")
        context["grupos"] = (
            Usuario.objects.filter(registros_eventos__isnull=False)
            .exclude(grupo="")
            .values_list("grupo", flat=True)
            .distinct()
            .order_by("grupo")
        )
        context["categorias"] = (
            Usuario.objects.filter(registros_eventos__isnull=False)
            .exclude(categoria__isnull=True)
            .exclude(categoria="")
            .values_list("categoria", flat=True)
            .distinct()
            .order_by("categoria")
        )
        context["pagination_query"] = urlencode(
            {key: value for key, value in filters.items() if value}
        )
        context["page_title"] = "Pre-registros a Eventos"
        context["page_subtitle"] = "Listado de asistentes y equipos pre-inscritos a eventos"
        context["create_url"] = reverse_lazy("eventos:registro_create")
        context["create_label"] = "Nuevo Pre-registro"
        return context


class RegistroCreateView(PassIdPermissionMixin, View):
    template_name = "eventos/registro_create.html"
    required_permission = "registro.add_registro"

    def get_filters(self, data):
        return {
            "evento": data.get("evento", "").strip(),
            "grupo": data.get("grupo", "").strip(),
            "categoria": data.get("categoria", "").strip(),
            "q": data.get("q", "").strip(),
        }

    def get_event(self, filters):
        if not filters["evento"].isdecimal():
            return None
        return Evento.objects.filter(pk=filters["evento"]).first()

    def get_eligible_users(self, evento):
        if evento is None:
            return Usuario.objects.none()

        registered_user_ids = Registro.objects.filter(evento=evento).values("usuario_id")
        return Usuario.objects.exclude(pk__in=registered_user_ids)

    def get_candidates(self, evento, filters):
        candidates = self.get_eligible_users(evento)
        if evento is None:
            return candidates
        if filters["grupo"]:
            candidates = candidates.filter(grupo=filters["grupo"])
        if filters["categoria"]:
            candidates = candidates.filter(categoria=filters["categoria"])
        if filters["q"]:
            query = filters["q"]
            candidates = candidates.filter(
                Q(matricula__icontains=query)
                | Q(username__icontains=query)
                | Q(nombre__icontains=query)
                | Q(apaterno__icontains=query)
                | Q(amaterno__icontains=query)
            )
        return candidates.order_by("grupo", "nombre", "apaterno", "amaterno")

    def get_context_data(self, *, data, form=None):
        filters = self.get_filters(data)
        evento = self.get_event(filters)
        eligible_users = self.get_eligible_users(evento)
        candidates = self.get_candidates(evento, filters)
        if form and form.is_bound:
            submitted_user_ids = form["usuarios"].value() or []
        else:
            submitted_user_ids = data.getlist("seleccionados")
        submitted_user_ids = [
            user_id for user_id in submitted_user_ids if str(user_id).isdecimal()
        ]
        selected_users = eligible_users.filter(pk__in=submitted_user_ids)
        visible_user_ids = candidates.values_list("pk", flat=True)
        previously_selected_users = selected_users.exclude(pk__in=visible_user_ids)
        form = form or RegistroMultipleEventoForm(
            initial={"evento": evento.pk} if evento else None,
            usuarios=eligible_users,
        )
        selected_user_ids = [str(user.pk) for user in selected_users]
        return {
            "title": "Registrar Asistente a Evento",
            "subtitle": "Filtra y selecciona uno o varios asistentes para pre-registrarlos.",
            "eventos": Evento.objects.all(),
            "grupos": (
                Usuario.objects.exclude(grupo="")
                .values_list("grupo", flat=True)
                .distinct()
                .order_by("grupo")
            ),
            "categorias": (
                Usuario.objects.exclude(categoria__isnull=True)
                .exclude(categoria="")
                .values_list("categoria", flat=True)
                .distinct()
                .order_by("categoria")
            ),
            "filters": filters,
            "evento_seleccionado": evento,
            "usuarios": candidates,
            "usuarios_seleccionados_fuera_filtro": previously_selected_users,
            "form": form,
            "selected_user_ids": selected_user_ids,
            "cancel_url": reverse_lazy("eventos:registro_list"),
        }

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            self.get_context_data(data=request.GET),
        )

    def post(self, request, *args, **kwargs):
        filters = self.get_filters(request.POST)
        evento = self.get_event(filters)
        eligible_users = self.get_eligible_users(evento)
        form = RegistroMultipleEventoForm(
            request.POST,
            usuarios=eligible_users,
        )
        if form.is_valid():
            evento = form.cleaned_data["evento"]
            equipo = form.cleaned_data["equipo"].strip() or None
            registrados = 0
            with transaction.atomic():
                for usuario in form.cleaned_data["usuarios"]:
                    _, created = Registro.objects.get_or_create(
                        evento=evento,
                        usuario=usuario,
                        defaults={"equipo": equipo},
                    )
                    registrados += int(created)

            messages.success(
                request,
                f"Se registraron {registrados} asistente(s) en «{evento.nombre}».",
            )
            query = urlencode(
                {
                    "evento": evento.pk,
                    "grupo": filters["grupo"],
                    "categoria": filters["categoria"],
                    "q": filters["q"],
                }
            )
            return redirect(f"{reverse_lazy('eventos:registro_create')}?{query}")

        return render(
            request,
            self.template_name,
            self.get_context_data(data=request.POST, form=form),
        )


class RegistroPlantillaView(PassIdPermissionMixin, View):
    required_permission = "registro.add_registro_masivo"

    def get(self, request, *args, **kwargs):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Registros"
        worksheet.append(["evento", "matricula", "equipo"])
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = "A1:C1"
        worksheet.column_dimensions["A"].width = 14
        worksheet.column_dimensions["B"].width = 24
        worksheet.column_dimensions["C"].width = 32
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="27272A")

        event_catalog = workbook.create_sheet("Eventos disponibles")
        event_catalog.append(["nombre", "fecha_hora", "lugar"])
        for evento in Evento.objects.order_by("pk"):
            event_catalog.append([
                evento.nombre,
                timezone.localtime(evento.fecha_hora).strftime("%d/%m/%Y %H:%M")
                if timezone.is_aware(evento.fecha_hora)
                else evento.fecha_hora.strftime("%d/%m/%Y %H:%M"),
                evento.lugar or "",
            ])
        event_catalog.freeze_panes = "A2"
        event_catalog.auto_filter.ref = f"A1:C{event_catalog.max_row}"
        event_catalog.column_dimensions["A"].width = 40
        event_catalog.column_dimensions["B"].width = 22
        event_catalog.column_dimensions["C"].width = 32
        for cell in event_catalog[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="27272A")

        instructions = workbook.create_sheet("Instrucciones")
        instructions.append(["Columna", "Instrucción"])
        instructions.append(["evento", "Obligatoria. Escribe el nombre del evento como aparece en Eventos disponibles. No distingue mayúsculas, acentos ni espacios repetidos."])
        instructions.append(["matricula", "Obligatoria. Debe existir en PassID; mantenla como texto para conservar ceros iniciales."])
        instructions.append(["equipo", "Opcional. Se asignará al pre-registro de esa persona."])
        for cell in instructions[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="27272A")
        instructions.column_dimensions["A"].width = 20
        instructions.column_dimensions["B"].width = 100

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            'attachment; filename="plantilla_registros_eventos.xlsx"'
        )
        workbook.save(response)
        return response


class RegistroImportView(PassIdPermissionMixin, FormView):
    form_class = RegistroImportForm
    template_name = "eventos/registro_import.html"
    required_permission = "registro.add_registro_masivo"

    def form_valid(self, form):
        try:
            report = import_registros(form.cleaned_data["archivo"])
        except ValidationError as error:
            form.add_error("archivo", error)
            return self.form_invalid(form)
        return self.render_to_response(
            self.get_context_data(form=form, report=report)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("title", "Carga masiva de registros de eventos")
        context["cancel_url"] = reverse_lazy("eventos:registro_create")
        return context


class RegistroUpdateView(PassIdPermissionMixin, UpdateView):
    model = Registro
    form_class = RegistroEventoForm
    template_name = "eventos/registro_form.html"
    success_url = reverse_lazy("eventos:registro_list")
    required_permission = "registro.change_registro"

    def form_valid(self, form):
        messages.success(self.request, "Pre-registro actualizado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar Pre-registro"
        context["subtitle"] = "Modifica los datos del registro"
        context["button_text"] = "Actualizar Registro"
        context["cancel_url"] = reverse_lazy("eventos:registro_list")
        return context


class RegistroDeleteView(PassIdPermissionMixin, DeleteView):
    model = Registro
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("eventos:registro_list")
    required_permission = "registro.delete_registro"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Pre-registro removido exitosamente.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Eliminar Pre-registro"
        context["cancel_url"] = reverse_lazy("eventos:registro_list")
        return context



class AsistenciaListView(PassIdPermissionMixin, ListView):
    model = Asistencia
    template_name = "eventos/asistencia_list.html"
    context_object_name = "asistencias"
    paginate_by = 10
    required_permission = "asistencia.view_asistencia"
    create_permission = "asistencia.add_asistencia"

    def get_queryset(self):
        queryset = Asistencia.objects.select_related("evento", "usuario", "registrado_por").order_by("-fecha_entrada")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(evento__nombre__icontains=query) |
                Q(usuario__nombre__icontains=query) |
                Q(usuario__matricula__icontains=query) |
                Q(usuario__username__icontains=query) |
                Q(registrado_por__username__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Asistencias Registradas a Eventos"
        context["page_subtitle"] = "Registro de acceso y pase de lista verificado"
        context["create_url"] = reverse_lazy("eventos:asistencia_create")
        context["create_label"] = "Registrar Asistencia Manual"
        context["search_placeholder"] = "Buscar por evento, asistente o registrador..."
        return context


class AsistenciaCreateView(PassIdPermissionMixin, CreateView):
    model = Asistencia
    form_class = AsistenciaEventoForm
    template_name = "eventos/asistencia_form.html"
    success_url = reverse_lazy("eventos:asistencia_list")
    required_permission = "asistencia.add_asistencia"

    def form_valid(self, form):
        form.instance.registrado_por = self.request.user
        messages.success(self.request, f"Asistencia de {form.instance.usuario} registrada con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registro Manual de Asistencia"
        context["subtitle"] = "Pase de lista o registro presencial para un asistente"
        context["button_text"] = "Validar y Guardar Asistencia"
        context["cancel_url"] = reverse_lazy("eventos:asistencia_list")
        return context


class AsistenciaDeleteView(PassIdPermissionMixin, DeleteView):
    model = Asistencia
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("eventos:asistencia_list")
    required_permission = "asistencia.delete_asistencia"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Registro de asistencia eliminado.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Eliminar Registro de Asistencia"
        context["cancel_url"] = reverse_lazy("eventos:asistencia_list")
        return context



class EventosDisponiblesView(PassIdPermissionMixin, ListView):
    model = Evento
    template_name = "eventos/eventos_disponibles.html"
    context_object_name = "eventos"
    paginate_by = 10
    required_permission = "evento.view_eventos_disponibles"

    def get_queryset(self):
        ahora = timezone.now()
        queryset = Evento.objects.filter(
            fecha_hora__gt=ahora,
            permitir_autorregistro=True,
        ).order_by("fecha_hora")

        queryset = queryset.annotate(
            ya_inscrito=Exists(
                Registro.objects.filter(
                    evento=OuterRef("pk"),
                    usuario=self.request.user,
                )
            )
        )

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) |
                Q(lugar__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Eventos Disponibles"
        context["page_subtitle"] = "Inscríbete a conferencias y actividades extracurriculares"
        context["search_placeholder"] = "Buscar por nombre o lugar..."
        return context


class AutoregistroInscribirView(PassIdPermissionMixin, View):
    required_permission = "otro.autorregistrarse"

    def post(self, request, pk):
        ahora = timezone.now()
        evento = get_object_or_404(
            Evento,
            pk=pk,
            permitir_autorregistro=True,
            fecha_hora__gt=ahora,
        )

        _, created = Registro.objects.get_or_create(
            evento=evento,
            usuario=request.user,
        )

        if created:
            messages.success(request, f"¡Te has inscrito exitosamente a '{evento.nombre}'!")
        else:
            messages.error(request, f"Ya estás inscrito en '{evento.nombre}'.")

        return redirect("eventos:eventos_disponibles")


class AutoregistroCancelarView(PassIdPermissionMixin, View):
    required_permission = "otro.autorregistrarse"

    def post(self, request, pk):
        ahora = timezone.now()
        registro = get_object_or_404(
            Registro,
            evento__pk=pk,
            usuario=request.user,
            evento__fecha_hora__gt=ahora,
        )

        nombre_evento = registro.evento.nombre
        registro.delete()
        messages.success(request, f"Tu inscripción a '{nombre_evento}' ha sido cancelada.")

        return redirect("eventos:eventos_disponibles")


class EscanearAsistenciaEventoView(PassIdPermissionMixin, RedirectView):
    required_permission = "asistencia.add_asistencia"

    def get_redirect_url(self, *args, **kwargs):
        params = {"mode": "evento"}
        evento_id = self.request.GET.get("evento")
        if evento_id and evento_id.isdigit():
            params["evento"] = evento_id
        return f"{reverse('asistencia_qr:lector')}?{urlencode(params)}"


class InfoEventoApiView(PassIdPermissionMixin, View):
    required_permission = "asistencia.add_asistencia"

    def get(self, request, pk, *args, **kwargs):
        evento = get_object_or_404(Evento, pk=pk)
        return JsonResponse({
            "ok": True,
            "id": evento.id,
            "nombre": evento.nombre,
            "fecha_hora": timezone.localtime(evento.fecha_hora).strftime("%d/%m/%Y %H:%M"),
            "lugar": evento.lugar or "Sin lugar asignado",
            "requiere_registro": bool(evento.requiere_registro),
            "permitir_autorregistro": bool(evento.permitir_autorregistro),
            "total_registrados": evento.registros.count(),
            "total_asistencias": evento.asistencias.count(),
        })


class RegistrarAsistenciaEventoQrView(PassIdPermissionMixin, View):
    required_permission = "asistencia.add_asistencia"

    def post(self, request, *args, **kwargs):
        form = EscaneoAsistenciaEventoForm(request.POST, user=request.user)
        if not form.is_valid():
            return JsonResponse(
                {
                    "ok": False,
                    "access_granted": False,
                    "message": "Selecciona un evento y escanea un código QR o captura la matrícula.",
                },
                status=400,
            )

        evento = form.cleaned_data["evento"]
        token = form.cleaned_data.get("token")
        matricula_raw = form.cleaned_data.get("matricula")

        if token:
            raw_text = token.strip()
            matricula = raw_text

            
            if raw_text.startswith("{") and raw_text.endswith("}"):
                try:
                    payload = json.loads(raw_text)
                    matricula = (
                        payload.get("matricula")
                        or payload.get("username")
                        or payload.get("usuario")
                        or raw_text
                    )
                except Exception:
                    pass

            
            elif ":" in raw_text:
                try:
                    
                    payload = None
                    for salt in ("asistencia_qr.matricula", "eventos.acceso", None):
                        try:
                            payload = (
                                signing.loads(raw_text, salt=salt)
                                if salt
                                else signing.loads(raw_text)
                            )
                            break
                        except (signing.BadSignature, Exception):
                            continue
                    if isinstance(payload, dict):
                        matricula = (
                            payload.get("matricula")
                            or payload.get("username")
                            or payload.get("usuario")
                            or raw_text
                        )
                    elif isinstance(payload, str) and payload:
                        matricula = payload
                except signing.SignatureExpired:
                    return JsonResponse(
                        {
                            "ok": False,
                            "access_granted": False,
                            "message": "El código QR ha expirado. Solicita al asistente actualizar su código.",
                        },
                        status=400,
                    )
                except Exception:
                    
                    matricula = raw_text

            metodo = "qr"
        else:
            matricula = matricula_raw.strip()
            metodo = "manual"

        
        asistente = Usuario.objects.filter(matricula=matricula, activo=True).first()
        if not asistente:
            asistente = Usuario.objects.filter(username=matricula, activo=True).first()

        if not asistente:
            return JsonResponse(
                {
                    "ok": False,
                    "access_granted": False,
                    "message": f"No se encontró ningún usuario activo con la matrícula o usuario '{matricula}'.",
                },
                status=404,
            )


        registro = None
        registrado_en_puerta = False
        registrar_si_no_existe = form.cleaned_data.get("registrar_si_no_existe", False)

        if evento.requiere_registro:
            registro = Registro.objects.filter(evento=evento, usuario=asistente).first()
            if not registro:
                if registrar_si_no_existe:
                    registro = Registro.objects.create(
                        evento=evento,
                        usuario=asistente,
                        equipo="Registro en puerta",
                    )
                    registrado_en_puerta = True
                else:
                    return JsonResponse(
                        {
                            "ok": False,
                            "access_granted": False,
                            "can_register": True,
                            "reason": "no_registro",
                            "message": f"Acceso Denegado: {asistente} no cuenta con pre-registro para '{evento.nombre}'.",
                            "asistente": {
                                "id": asistente.id,
                                "nombre": str(asistente),
                                "matricula": asistente.matricula or asistente.username,
                                "grupo": asistente.grupo,
                            },
                        },
                        status=403,
                    )
        else:
            registro = Registro.objects.filter(evento=evento, usuario=asistente).first()

        
        asistencia_existente = Asistencia.objects.filter(evento=evento, usuario=asistente).first()
        if asistencia_existente:
            hora_previa = timezone.localtime(asistencia_existente.fecha_entrada).strftime("%H:%M:%S")
            registrador = (
                asistencia_existente.registrado_por.username
                if asistencia_existente.registrado_por
                else "Staff"
            )
            return JsonResponse(
                {
                    "ok": False,
                    "duplicate": True,
                    "access_granted": False,
                    "message": f"¡Acceso duplicado! {asistente} ya ingresó previamente a las {hora_previa} (registrado por {registrador}).",
                    "asistente": {
                        "id": asistente.id,
                        "nombre": str(asistente),
                        "matricula": asistente.matricula or asistente.username,
                        "grupo": asistente.grupo,
                    },
                    "hora_previa": hora_previa,
                },
                status=409,
            )

        
        asistencia = Asistencia.objects.create(
            evento=evento,
            usuario=asistente,
            registrado_por=request.user,
        )

        hora_acceso = timezone.localtime(asistencia.fecha_entrada).strftime("%H:%M:%S")

        return JsonResponse(
            {
                "ok": True,
                "access_granted": True,
                "registrado_en_puerta": registrado_en_puerta,
                "metodo": metodo,
                "message": (
                    f"¡Registrado en puerta y Acceso Autorizado! Bienvenido/a {asistente}."
                    if registrado_en_puerta
                    else f"¡Acceso Autorizado! Bienvenido/a {asistente}."
                ),
                "asistente": {
                    "id": asistente.id,
                    "nombre": str(asistente),
                    "matricula": asistente.matricula or asistente.username,
                    "grupo": asistente.grupo,
                    "categoria": asistente.categoria or "Asistente",
                    "equipo": registro.equipo if (registro and registro.equipo) else None,
                },
                "evento": {
                    "id": evento.id,
                    "nombre": evento.nombre,
                },
                "hora_acceso": hora_acceso,
                "total_asistencias": Asistencia.objects.filter(evento=evento).count(),
                "total_registrados": (
                    Registro.objects.filter(evento=evento).count()
                    if evento.requiere_registro
                    else None
                ),
            }
        )


class EventoQrRegistroImagenView(PassIdPermissionMixin, View):
    required_permission = "asistencia.add_asistencia"

    def get(self, request, pk, *args, **kwargs):
        evento = get_object_or_404(Evento, pk=pk)
        registro_url = request.build_absolute_uri(
            reverse_lazy("eventos:autoregistro_inscribir", kwargs={"pk": evento.pk})
        )
        from core.utils import generar_qr
        import base64
        from django.http import HttpResponse

        img_bytes = base64.b64decode(generar_qr(registro_url))
        response = HttpResponse(img_bytes, content_type="image/png")
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
