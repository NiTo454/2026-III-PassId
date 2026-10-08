from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.contrib import messages
from .models import Permiso, Perfil, Usuario
from .forms import PermisoForm, PerfilForm, UsuarioCreateForm, UsuarioUpdateForm

class PermisoListView(ListView):
    model = Permiso
    template_name = "usuarios/permiso_list.html"
    context_object_name = "permisos"
    paginate_by = 10

    def get_queryset(self):
        queryset = Permiso.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(tipo__icontains=query) |
                Q(codename__icontains=query) |
                Q(nombre__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["total_count"] = self.get_queryset().count()
        return context


class PermisoCreateView(CreateView):
    model = Permiso
    form_class = PermisoForm
    template_name = "usuarios/permiso_form.html"
    success_url = reverse_lazy("usuarios:permiso_list")

    def form_valid(self, form):
        messages.success(self.request, f"Permiso '{form.instance.codename}' creado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Crear Nuevo Permiso"
        context["button_text"] = "Guardar Permiso"
        return context


class PermisoUpdateView(UpdateView):
    model = Permiso
    form_class = PermisoForm
    template_name = "usuarios/permiso_form.html"
    success_url = reverse_lazy("usuarios:permiso_list")

    def form_valid(self, form):
        messages.success(self.request, f"Permiso '{form.instance.codename}' actualizado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Permiso: {self.object.codename}"
        context["button_text"] = "Actualizar Permiso"
        return context


class PermisoDeleteView(DeleteView):
    model = Permiso
    template_name = "usuarios/permiso_confirm_delete.html"
    success_url = reverse_lazy("usuarios:permiso_list")
    context_object_name = "permiso"

    def delete(self, request, *args, **kwargs):
        permiso = self.get_object()
        messages.success(request, f"Permiso '{permiso.codename}' eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class PerfilListView(ListView):
    model = Perfil
    template_name = "usuarios/perfil_list.html"
    context_object_name = "perfiles"
    paginate_by = 10

    def get_queryset(self):
        queryset = Perfil.objects.prefetch_related("permisos").all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(nombre__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["total_count"] = self.get_queryset().count()
        return context


class PerfilCreateView(CreateView):
    model = Perfil
    form_class = PerfilForm
    template_name = "usuarios/perfil_form.html"
    success_url = reverse_lazy("usuarios:perfil_list")

    def form_valid(self, form):
        messages.success(self.request, f"Perfil '{form.instance.nombre}' creado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Crear Nuevo Perfil / Rol"
        context["button_text"] = "Guardar Perfil"
        return context


class PerfilUpdateView(UpdateView):
    model = Perfil
    form_class = PerfilForm
    template_name = "usuarios/perfil_form.html"
    success_url = reverse_lazy("usuarios:perfil_list")

    def form_valid(self, form):
        messages.success(self.request, f"Perfil '{form.instance.nombre}' actualizado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Perfil: {self.object.nombre}"
        context["button_text"] = "Actualizar Perfil"
        return context


class PerfilDeleteView(DeleteView):
    model = Perfil
    template_name = "usuarios/perfil_confirm_delete.html"
    success_url = reverse_lazy("usuarios:perfil_list")
    context_object_name = "perfil"

    def delete(self, request, *args, **kwargs):
        perfil = self.get_object()
        messages.success(request, f"Perfil '{perfil.nombre}' eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class UsuarioListView(ListView):
    model = Usuario
    template_name = "usuarios/usuario_list.html"
    context_object_name = "usuarios_list"
    paginate_by = 10

    def get_queryset(self):
        queryset = Usuario.objects.prefetch_related("perfiles").all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |
                Q(nombre__icontains=query) |
                Q(apaterno__icontains=query) |
                Q(email__icontains=query) |
                Q(matricula__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["total_count"] = self.get_queryset().count()
        return context


class UsuarioCreateView(CreateView):
    model = Usuario
    form_class = UsuarioCreateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:usuario_list")

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' registrado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Nuevo Usuario"
        context["button_text"] = "Guardar Usuario"
        return context


class UsuarioUpdateView(UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:usuario_list")

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' actualizado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Usuario: {self.object.username}"
        context["button_text"] = "Actualizar Usuario"
        return context


class UsuarioDeleteView(DeleteView):
    model = Usuario
    template_name = "usuarios/usuario_confirm_delete.html"
    success_url = reverse_lazy("usuarios:usuario_list")
    context_object_name = "usuario"

    def delete(self, request, *args, **kwargs):
        usuario = self.get_object()
        messages.success(request, f"Usuario '{usuario.username}' eliminado correctamente.")
        return super().delete(request, *args, **kwargs)
