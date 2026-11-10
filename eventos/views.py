from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.db.models import Q, Exists, OuterRef
from django.contrib import messages
from django.utils import timezone
from core.mixins import PassIdPermissionMixin
from .models import Evento, Registro, Asistencia
from .forms import EventoForm, RegistroEventoForm, AsistenciaEventoForm



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

    def get_queryset(self):
        queryset = Registro.objects.select_related("evento", "usuario").order_by("-fecha_registro")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(evento__nombre__icontains=query) |
                Q(usuario__nombre__icontains=query) |
                Q(usuario__matricula__icontains=query) |
                Q(usuario__username__icontains=query) |
                Q(equipo__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["page_title"] = "Pre-registros a Eventos"
        context["page_subtitle"] = "Listado de asistentes y equipos pre-inscritos a eventos"
        context["create_url"] = reverse_lazy("eventos:registro_create")
        context["create_label"] = "Nuevo Pre-registro"
        context["search_placeholder"] = "Buscar por evento, alumno, matrícula o equipo..."
        return context


class RegistroCreateView(PassIdPermissionMixin, CreateView):
    model = Registro
    form_class = RegistroEventoForm
    template_name = "eventos/registro_form.html"
    success_url = reverse_lazy("eventos:registro_list")
    required_permission = "registro.add_registro"

    def form_valid(self, form):
        messages.success(self.request, f"Pre-registro de {form.instance.usuario} al evento realizado con éxito.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Asistente a Evento"
        context["subtitle"] = "Selecciona el evento y el usuario o equipo participante"
        context["button_text"] = "Completar Registro"
        context["cancel_url"] = reverse_lazy("eventos:registro_list")
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
    required_permission = "otro.autorregistrarse"

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
