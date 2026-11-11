
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from academico.models import Horario, Inscripcion
from core.mixins import PassIdPermissionMixin
from eventos.models import Asistencia, Evento


class HomeView(PassIdPermissionMixin, TemplateView):
    template_name = "core/home.html"
    required_permission = "core.view_home"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ahora = timezone.localtime()
        dia_semana = (
            "lunes",
            "martes",
            "miercoles",
            "jueves",
            "viernes",
            "sabado",
            "domingo",
        )[ahora.weekday()]
        inscripciones = Inscripcion.objects.filter(
            usuario_id=self.request.user.pk,
            activa=True,
        )
        totales = inscripciones.aggregate(
            materias=Count("pk"),
            horas_sem=Sum("materia__horas_semana"),
        )

        horarios_hoy = Horario.objects.filter(
            activo=True,
            materia__activa=True,
            dia_semana=dia_semana,
            materia__inscripciones__usuario_id=self.request.user.pk,
            materia__inscripciones__activa=True,
            materia__inscripciones__grupo=F("grupo"),
            materia__inscripciones__periodo=F("periodo"),
        ).distinct()
        hora_actual = ahora.time()
        siguiente_clase = (
            horarios_hoy.filter(
                Q(hora_inicio__gte=hora_actual)
                | Q(hora_inicio__lt=hora_actual, hora_fin__gt=hora_actual)
            )
            .select_related("materia", "aula")
            .order_by("hora_inicio")
            .first()
        )

        context["estadisticas"] = {
            "materias": totales["materias"],
            "horas_sem": totales["horas_sem"] or 0,
            "eventos": Evento.objects.count(),
            "asistencias_evt": Asistencia.objects.filter(
                usuario_id=self.request.user.pk,
            ).count(),
        }
        context["siguiente_clase"] = siguiente_clase
        context["clase_en_curso"] = bool(
            siguiente_clase
            and siguiente_clase.hora_inicio <= hora_actual < siguiente_clase.hora_fin
        )
        context["hay_clases_hoy"] = horarios_hoy.exists()
        context["evento_proximo"] = (
            Evento.objects.filter(fecha_hora__gte=ahora)
            .order_by("fecha_hora")
            .first()
        )
        return context
