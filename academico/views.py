from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.db.models import Count, F, Q
from django.contrib import messages
from core.mixins import PassIdPermissionMixin
from .models import Carrera, Aula, Materia, Horario, Inscripcion
from .forms import CarreraForm, AulaForm, MateriaForm, HorarioForm, InscripcionForm
from django.contrib.auth import get_user_model


# ==============================================================================
# VISTAS DE CARRERA
# ==============================================================================
class CarreraListView(PassIdPermissionMixin, ListView):
    model = Carrera
    template_name = "academico/carrera_list.html"
    context_object_name = "carreras"
    paginate_by = 10
    required_permission = "carrera.view_carrera"
    create_permission = "carrera.add_carrera"

    def get_queryset(self):
        queryset = Carrera.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(clave__icontains=query) | Q(nombre__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Catálogo de Carreras"
        context["page_subtitle"] = "Gestión de planes de estudio y programas académicos"
        context["create_url"] = reverse_lazy("academico:carrera_create")
        context["create_label"] = "Nueva Carrera"
        context["search_placeholder"] = "Buscar por clave o nombre de carrera..."
        return context


class CarreraCreateView(PassIdPermissionMixin, CreateView):
    model = Carrera
    form_class = CarreraForm
    template_name = "academico/carrera_form.html"
    success_url = reverse_lazy("academico:carrera_list")
    required_permission = "carrera.add_carrera"

    def form_valid(self, form):
        messages.success(self.request, f"Carrera '{form.instance.nombre}' creada con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Nueva Carrera"
        context["subtitle"] = "Ingresa la clave y nombre oficial del programa académico"
        context["button_text"] = "Guardar Carrera"
        context["cancel_url"] = reverse_lazy("academico:carrera_list")
        return context


class CarreraUpdateView(PassIdPermissionMixin, UpdateView):
    model = Carrera
    form_class = CarreraForm
    template_name = "academico/carrera_form.html"
    success_url = reverse_lazy("academico:carrera_list")
    required_permission = "carrera.change_carrera"

    def form_valid(self, form):
        messages.success(self.request, f"Carrera '{form.instance.nombre}' actualizada con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Carrera: {self.object.clave}"
        context["subtitle"] = "Modifica los datos del programa académico seleccionado"
        context["button_text"] = "Actualizar Carrera"
        context["cancel_url"] = reverse_lazy("academico:carrera_list")
        return context


class CarreraDeleteView(PassIdPermissionMixin, DeleteView):
    model = Carrera
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("academico:carrera_list")
    required_permission = "carrera.delete_carrera"

    def delete(self, request, *args, **kwargs):
        carrera = self.get_object()
        messages.success(request, f"Carrera '{carrera.nombre}' eliminada del sistema.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Eliminar Carrera: {self.object.clave}"
        context["cancel_url"] = reverse_lazy("academico:carrera_list")
        return context

class CarreraDetailView(PassIdPermissionMixin, DetailView):
    model = Carrera
    template_name = "academico/carrera_detail.html"
    context_object_name = "carrera"
    required_permission = "carrera.view_carrera"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Detalles de la Carrera: {self.object.clave}"
        context["list_url"] = reverse_lazy("academico:carrera_list")
        context["update_url"] = reverse_lazy("academico:carrera_update", kwargs={'pk': self.object.pk})
        context["materias"] = self.object.materias.all()
        return context


# ==============================================================================
# VISTAS DE AULA
# ==============================================================================
class AulaListView(PassIdPermissionMixin, ListView):
    model = Aula
    template_name = "academico/aula_list.html"
    context_object_name = "aulas"
    paginate_by = 10
    required_permission = "aula.view_aula"
    create_permission = "aula.add_aula"

    def get_queryset(self):
        queryset = Aula.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(codigo__icontains=query) |
                Q(edificio__icontains=query) |
                Q(tipo__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Catálogo de Aulas y Espacios"
        context["page_subtitle"] = "Administración de aulas, laboratorios y auditorios"
        context["create_url"] = reverse_lazy("academico:aula_create")
        context["create_label"] = "Nueva Aula"
        context["search_placeholder"] = "Buscar por código, edificio o tipo..."
        return context


class AulaCreateView(PassIdPermissionMixin, CreateView):
    model = Aula
    form_class = AulaForm
    template_name = "academico/aula_form.html"
    success_url = reverse_lazy("academico:aula_list")
    required_permission = "aula.add_aula"

    def form_valid(self, form):
        messages.success(self.request, f"Aula '{form.instance.codigo}' registrada correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Nueva Aula"
        context["subtitle"] = "Especifica el código, ubicación y tipo de espacio"
        context["button_text"] = "Guardar Aula"
        context["cancel_url"] = reverse_lazy("academico:aula_list")
        return context


class AulaUpdateView(PassIdPermissionMixin, UpdateView):
    model = Aula
    form_class = AulaForm
    template_name = "academico/aula_form.html"
    success_url = reverse_lazy("academico:aula_list")
    required_permission = "aula.change_aula"

    def form_valid(self, form):
        messages.success(self.request, f"Aula '{form.instance.codigo}' actualizada con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Aula: {self.object.codigo}"
        context["subtitle"] = "Modifica los atributos del espacio seleccionado"
        context["button_text"] = "Actualizar Aula"
        context["cancel_url"] = reverse_lazy("academico:aula_list")
        return context


class AulaDeleteView(PassIdPermissionMixin, DeleteView):
    model = Aula
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("academico:aula_list")
    required_permission = "aula.delete_aula"

    def delete(self, request, *args, **kwargs):
        aula = self.get_object()
        messages.success(request, f"Aula '{aula.codigo}' eliminada exitosamente.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Eliminar Aula: {self.object.codigo}"
        context["cancel_url"] = reverse_lazy("academico:aula_list")
        return context

class AulaDetailView(PassIdPermissionMixin, DetailView):
    model = Aula
    template_name = "academico/aula_detail.html"
    context_object_name = "aula"
    required_permission = "aula.view_aula"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Detalles del Aula: {self.object.codigo}"
        context["list_url"] = reverse_lazy("academico:aula_list")
        context["update_url"] = reverse_lazy("academico:aula_update", kwargs={'pk': self.object.pk})
        context["horarios"] = self.object.horarios.all()
        return context 


# ==============================================================================
# VISTAS DE MATERIA
# ==============================================================================
class MateriaListView(PassIdPermissionMixin, ListView):
    model = Materia
    template_name = "academico/materia_list.html"
    context_object_name = "materias"
    paginate_by = 10
    required_permission = "materia.view_materia"
    create_permission = "materia.add_materia"

    def get_queryset(self):
        queryset = Materia.objects.select_related("carrera").all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(clave__icontains=query) |
                Q(nombre__icontains=query) |
                Q(periodo__icontains=query) |
                Q(carrera__nombre__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Catálogo de Materias"
        context["page_subtitle"] = "Listado general de asignaturas y planes de estudio"
        context["create_url"] = reverse_lazy("academico:materia_create")
        context["create_label"] = "Nueva Materia"
        context["search_placeholder"] = "Buscar por clave, nombre, periodo o carrera..."
        return context


class MateriaCreateView(PassIdPermissionMixin, CreateView):
    model = Materia
    form_class = MateriaForm
    template_name = "academico/materia_form.html"
    success_url = reverse_lazy("academico:materia_list")
    required_permission = "materia.add_materia"

    def form_valid(self, form):
        messages.success(self.request, f"Materia '{form.instance.nombre}' creada con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Nueva Materia"
        context["subtitle"] = "Configura la asignatura, horas y carrera asociada"
        context["button_text"] = "Guardar Materia"
        context["cancel_url"] = reverse_lazy("academico:materia_list")
        return context


class MateriaUpdateView(PassIdPermissionMixin, UpdateView):
    model = Materia
    form_class = MateriaForm
    template_name = "academico/materia_form.html"
    success_url = reverse_lazy("academico:materia_list")
    required_permission = "materia.change_materia"

    def form_valid(self, form):
        messages.success(self.request, f"Materia '{form.instance.nombre}' actualizada con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Materia: {self.object.clave}"
        context["subtitle"] = "Actualiza los datos y horas de la asignatura"
        context["button_text"] = "Actualizar Materia"
        context["cancel_url"] = reverse_lazy("academico:materia_list")
        return context


class MateriaDeleteView(PassIdPermissionMixin, DeleteView):
    model = Materia
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("academico:materia_list")
    required_permission = "materia.delete_materia"

    def delete(self, request, *args, **kwargs):
        materia = self.get_object()
        messages.success(request, f"Materia '{materia.nombre}' eliminada con éxito.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Eliminar Materia: {self.object.clave}"
        context["cancel_url"] = reverse_lazy("academico:materia_list")
        return context

class MateriaDetailView(PassIdPermissionMixin, DetailView):
    model = Materia
    template_name = "academico/materia_detail.html"
    context_object_name = "materia"
    required_permission = "materia.view_materia"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Detalles de la Materia: {self.object.clave}"
        context["list_url"] = reverse_lazy("academico:materia_list")
        context["update_url"] = reverse_lazy("academico:materia_update", kwargs={'pk': self.object.pk})
        return context


# ==============================================================================
# VISTAS DE HORARIO
# ==============================================================================
class HorarioListView(PassIdPermissionMixin, ListView):
    model = Horario
    template_name = "academico/horario_list.html"
    context_object_name = "horarios"
    paginate_by = 10
    required_permission = "horario.view_horario"
    create_permission = "horario.add_horario"

    def get_queryset(self):
        queryset = Horario.objects.select_related("materia", "profesor", "aula").all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(materia__nombre__icontains=query) |
                Q(profesor__nombre__icontains=query) |
                Q(profesor__username__icontains=query) |
                Q(aula__codigo__icontains=query) |
                Q(periodo__icontains=query) |
                Q(dia_semana__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Gestión de Horarios de Clases"
        context["page_subtitle"] = "Programación académica por grupo, aula y docente"
        context["create_url"] = reverse_lazy("academico:horario_create")
        context["create_label"] = "Nuevo Horario"
        context["search_placeholder"] = "Buscar por materia, profesor, aula, grupo o periodo..."
        return context


class HorarioCreateView(PassIdPermissionMixin, CreateView):
    model = Horario
    form_class = HorarioForm
    template_name = "academico/horario_form.html"
    success_url = reverse_lazy("academico:horario_list")
    required_permission = "horario.add_horario"

    def form_valid(self, form):
        messages.success(self.request, "Horario de clase asignado con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Asignar Nuevo Horario"
        context["subtitle"] = "Asigna materia, docente, aula y bloque horario"
        context["button_text"] = "Guardar Horario"
        context["cancel_url"] = reverse_lazy("academico:horario_list")
        return context


class HorarioUpdateView(PassIdPermissionMixin, UpdateView):
    model = Horario
    form_class = HorarioForm
    template_name = "academico/horario_form.html"
    success_url = reverse_lazy("academico:horario_list")
    required_permission = "horario.change_horario"

    def form_valid(self, form):
        messages.success(self.request, "Horario de clase actualizado con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar Horario de Clase"
        context["subtitle"] = "Modifica la asignación docente, aula u horario"
        context["button_text"] = "Actualizar Horario"
        context["cancel_url"] = reverse_lazy("academico:horario_list")
        return context


class HorarioDeleteView(PassIdPermissionMixin, DeleteView):
    model = Horario
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("academico:horario_list")
    required_permission = "horario.delete_horario"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Horario de clase eliminado.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Eliminar Horario de Clase"
        context["cancel_url"] = reverse_lazy("academico:horario_list")
        return context

class HorarioDetailView(PassIdPermissionMixin, DetailView):
    model = Horario
    template_name = "academico/horario_detail.html"
    context_object_name = "horario"
    required_permission = "horario.view_horario"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Detalles del Horario"
        context["list_url"] = reverse_lazy("academico:horario_list")
        context["update_url"] = reverse_lazy("academico:horario_update", kwargs={'pk': self.object.pk})
        return context    


# ==============================================================================
# VISTAS DE INSCRIPCIÓN
# ==============================================================================
class InscripcionListView(PassIdPermissionMixin, ListView):
    model = Inscripcion
    template_name = "academico/inscripcion_list.html"
    context_object_name = "inscripciones"
    paginate_by = 10
    required_permission = "inscripcion.view_inscripcion"
    create_permission = "inscripcion.add_inscripcion"

    def get_queryset(self):
        queryset = Inscripcion.objects.select_related("usuario", "materia").order_by("-fecha_inscripcion")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(usuario__nombre__icontains=query) |
                Q(usuario__username__icontains=query) |
                Q(usuario__matricula__icontains=query) |
                Q(materia__nombre__icontains=query) |
                Q(grupo__icontains=query) |
                Q(periodo__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Inscripciones de Alumnos"
        context["page_subtitle"] = "Gestión de alumnos inscritos en materias y grupos"
        context["create_url"] = reverse_lazy("academico:inscripcion_create")
        context["create_label"] = "Nueva Inscripción"
        context["search_placeholder"] = "Buscar por alumno, matrícula, materia, grupo o periodo..."
        return context


class InscripcionCreateView(PassIdPermissionMixin, CreateView):
    model = Inscripcion
    form_class = InscripcionForm
    template_name = "academico/inscripcion_form.html"
    success_url = reverse_lazy("academico:inscripcion_list")
    required_permission = "inscripcion.add_inscripcion"

    def form_valid(self, form):
        messages.success(self.request, f"Alumno inscrito en '{form.instance.materia.nombre}' con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Nueva Inscripción"
        context["subtitle"] = "Inscribe a un alumno en una materia para el periodo actual"
        context["button_text"] = "Guardar Inscripción"
        context["cancel_url"] = reverse_lazy("academico:inscripcion_list")
        return context


class InscripcionUpdateView(PassIdPermissionMixin, UpdateView):
    model = Inscripcion
    form_class = InscripcionForm
    template_name = "academico/inscripcion_form.html"
    success_url = reverse_lazy("academico:inscripcion_list")
    required_permission = "inscripcion.change_inscripcion"

    def form_valid(self, form):
        messages.success(self.request, "Inscripción actualizada correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Modificar Inscripción"
        context["subtitle"] = "Actualiza el grupo, estado o periodo de la inscripción"
        context["button_text"] = "Actualizar Inscripción"
        context["cancel_url"] = reverse_lazy("academico:inscripcion_list")
        return context


class InscripcionDeleteView(PassIdPermissionMixin, DeleteView):
    model = Inscripcion
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("academico:inscripcion_list")
    required_permission = "inscripcion.delete_inscripcion"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Inscripción de alumno cancelada exitosamente.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Eliminar Inscripción"
        context["cancel_url"] = reverse_lazy("academico:inscripcion_list")
        return context

class InscripcionDetailView(PassIdPermissionMixin, DetailView):
    model = Inscripcion
    template_name = "academico/inscripcion_detail.html"
    context_object_name = "inscripcion"
    required_permission = "inscripcion.view_inscripcion"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Detalles de la Inscripción"
        context["list_url"] = reverse_lazy("academico:inscripcion_list")
        context["update_url"] = reverse_lazy("academico:inscripcion_update", kwargs={'pk': self.object.pk})
        return context

class ProgresoAsistenciaView(PassIdPermissionMixin, TemplateView):
    template_name = "academico/mi_progreso.html"
    required_permission = "asistencia_clase.view_progreso_asistencia"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estudiante_id = self.request.user.id
        periodos_disponibles = list(Inscripcion.objects.filter(
            usuario_id=estudiante_id,
            activa=True
        ).values_list("periodo", flat=True).distinct().order_by("-periodo"))
        periodo_por_defecto = periodos_disponibles[0] if periodos_disponibles else ""
        periodo_solicitado = self.request.GET.get("periodo")
        periodo = (
            periodo_solicitado
            if periodo_solicitado in periodos_disponibles
            else periodo_por_defecto
        )
        context['estudiante_nombre'] = getattr(self.request.user, 'nombre', self.request.user.username)
        context['periodo_actual'] = periodo
        context['periodos_disponibles'] = periodos_disponibles
        filtro_asistencias = Q(
            materia__horarios__asistencias__usuario_id=estudiante_id,
            materia__horarios__grupo=F("grupo"),
            materia__horarios__periodo=periodo,
        )
        inscripciones = (
            Inscripcion.objects.filter(
                usuario_id=estudiante_id,
                periodo=periodo,
                activa=True,
            )
            .select_related("materia")
            .annotate(
                total_clases=Count(
                    "materia__horarios__asistencias",
                    filter=filtro_asistencias,
                ),
                asistencias_validas=Count(
                    "materia__horarios__asistencias",
                    filter=filtro_asistencias
                    & Q(materia__horarios__asistencias__estado__in=[
                        "presente",
                        "retardo",
                        "justificado",
                    ]),
                ),
            )
        )
        progreso_materias = []

        for inscripcion in inscripciones:
            materia = inscripcion.materia
            total_clases = inscripcion.total_clases
            asistencias_validas = inscripcion.asistencias_validas
            porcentaje = (
                int((asistencias_validas / total_clases) * 100)
                if total_clases
                else 0
            )

            progreso_materias.append({
                'materia': materia.nombre,
                'codigo': materia.clave,
                'grupo': inscripcion.grupo,
                'asistencias': asistencias_validas,
                'total_clases': total_clases,
                'porcentaje': porcentaje
            })

        context['progreso_materias'] = progreso_materias
        return context

class CargaAcademicaView(PassIdPermissionMixin, TemplateView):
    template_name = "academico/carga_academica.html"
    required_permission = "horario.view_carga_academica"

    DIAS_SEMANA = [
        ("lunes", "Lunes"),
        ("martes", "Martes"),
        ("miercoles", "Miércoles"),
        ("jueves", "Jueves"),
        ("viernes", "Viernes"),
        ("sabado", "Sábado"),
    ]

    def dispatch(self, request, *args, **kwargs):
        self.es_admin_horarios = (
            request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.has_perm("horario.admin")
            )
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        periodo = self.request.GET.get("periodo", "2026-1").strip()
        periodo = periodo or "2026-1"

        profesor_id = usuario.pk

        if self.es_admin_horarios:
            profesor_id_solicitado = self.request.GET.get(
                "profesor_id", ""
            ).strip()

            if profesor_id_solicitado.isdigit():
                profesor_id = int(profesor_id_solicitado)

        Usuario = get_user_model()

        profesor = Usuario.objects.filter(pk=profesor_id).first()

        if profesor is None:
            profesor = usuario
            profesor_id = usuario.pk

        horarios = list(
            Horario.objects.filter(
                profesor_id=profesor_id,
                periodo=periodo,
                activo=True,
            )
            .select_related("materia", "aula", "profesor")
            .order_by("dia_semana", "hora_inicio")
        )

        horarios_por_dia = {
            dia: [] for dia, _ in self.DIAS_SEMANA
        }

        minutos_totales = 0

        for horario in horarios:
            horarios_por_dia.setdefault(
                horario.dia_semana, []
            ).append(horario)

            inicio = (
                horario.hora_inicio.hour * 60
                + horario.hora_inicio.minute
            )

            fin = (
                horario.hora_fin.hour * 60
                + horario.hora_fin.minute
            )

            minutos_totales += max(fin - inicio, 0)

        nombre_profesor = " ".join(
            parte
            for parte in [
                getattr(profesor, "nombre", ""),
                getattr(profesor, "apaterno", ""),
                getattr(profesor, "amaterno", ""),
            ]
            if parte
        ).strip() or profesor.username

        dias_con_horarios = [
            {
                "clave": dia,
                "nombre": nombre,
                "horarios": horarios_por_dia[dia],
            }
            for dia, nombre in self.DIAS_SEMANA
        ]

        context.update({
            "periodo": periodo,
            "profesor_seleccionado": profesor,
            "profesor_nombre": nombre_profesor,
            "dias_con_horarios": dias_con_horarios,
            "hay_horarios": bool(horarios),
            "horas_totales": minutos_totales // 60,
            "minutos_totales": minutos_totales % 60,
            "es_admin_horarios": self.es_admin_horarios,
        })

        if self.es_admin_horarios:
            context["profesores"] = (
                Usuario.objects.filter(activo=True)
                .order_by("nombre", "apaterno", "username")
            )

        return context