import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import PasswordChangeView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView, CreateView, UpdateView, DeleteView

from core.mixins import PassIdPermissionMixin
from autenticacion.context import AUTH_TEMPLATE, build_auth_context
from .forms import (
    MiPerfilForm,
    PasswordResetRequestForm,
    PasswordResetSetPasswordForm,
    PerfilForm,
    PermisoForm,
    UsuarioCreateForm,
    UsuarioImportForm,
    UsuarioUpdateForm,
)
from .importacion_usuarios import import_users
from .models import PasswordReset, Permiso, Perfil, Usuario


class PasswordResetRequestView(FormView):
    form_class = PasswordResetRequestForm
    template_name = AUTH_TEMPLATE
    success_url = reverse_lazy("usuarios:password_reset_done")
    rate_limit = 5
    rate_limit_seconds = 900

    def is_rate_limited(self):
        remote_address = self.request.META.get("REMOTE_ADDR", "")
        address_hash = hashlib.sha256(remote_address.encode("utf-8")).hexdigest()
        cache_key = f"password-reset-request:{address_hash}"
        cache.add(cache_key, 0, timeout=self.rate_limit_seconds)
        try:
            attempts = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=self.rate_limit_seconds)
            attempts = 1
        return attempts > self.rate_limit

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_auth_context(self.request, "reset", context["form"]))
        context.update({
            "title": "Recuperar contraseña",
            "subtitle": (
                "Ingresa tu correo institucional o matrícula. Si encontramos "
                "una cuenta, enviaremos instrucciones para restablecer la contraseña."
            ),
            "button_text": "Enviar instrucciones",
            "cancel_url": reverse_lazy("autenticacion:login"),
        })
        return context

    def form_valid(self, form):
        if self.is_rate_limited():
            return super().form_valid(form)

        identifier = form.cleaned_data["identifier"]
        matches = list(
            Usuario.objects.filter(
                Q(email__iexact=identifier) | Q(matricula__iexact=identifier)
            ).order_by("pk")[:2]
        )

        if len(matches) == 1:
            user = matches[0]
            token = secrets.token_hex(32)
            now = timezone.now()
            reset_path = reverse(
                "usuarios:password_reset_confirm",
                kwargs={"token": token},
            )
            reset_url = urljoin(
                f"{settings.PASSWORD_RESET_BASE_URL.rstrip('/')}/",
                reset_path.lstrip("/"),
            )
            message = (
                "Recibimos una solicitud para restablecer la contraseña de tu cuenta PassID.\n\n"
                f"Para elegir una nueva contraseña, abre este enlace:\n{reset_url}\n\n"
                "El enlace vence en 24 horas y solo puede utilizarse una vez. "
                "Si no solicitaste este cambio, puedes ignorar este mensaje."
            )

            with transaction.atomic():
                locked_user = Usuario.objects.select_for_update().get(pk=user.pk)
                PasswordReset.objects.filter(usuario=locked_user).delete()
                PasswordReset.objects.create(
                    usuario=locked_user,
                    token=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    expira_en=now + timedelta(hours=24),
                )
                send_mail(
                    "Restablecimiento de contraseña de PassID",
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [locked_user.email],
                    fail_silently=False,
                )

        return super().form_valid(form)


class PasswordResetDoneView(View):
    def get(self, request, *args, **kwargs):
        return render(request, "usuarios/password_reset_done.html")


class PasswordResetConfirmView(View):
    template_name = "usuarios/password_reset_confirm.html"

    def render_sensitive(self, request, template_name, context=None, status=200):
        response = render(request, template_name, context, status=status)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def get_reset(self, token, lock=False):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        resets = PasswordReset.objects.select_related("usuario")
        if lock:
            resets = resets.select_for_update()
        return resets.filter(
            token=token_hash,
            expira_en__gt=timezone.now(),
        ).first()

    def get_context_data(self, form, token):
        return {
            "form": form,
            "title": "Crear nueva contraseña",
            "subtitle": "Elige una contraseña segura para tu cuenta.",
            "button_text": "Guardar contraseña",
            "cancel_url": reverse_lazy("autenticacion:login"),
            "token": token,
        }

    def get(self, request, token, *args, **kwargs):
        reset = self.get_reset(token)
        if reset is None:
            return self.render_sensitive(
                request,
                "usuarios/password_reset_invalid.html",
                status=400,
            )
        form = PasswordResetSetPasswordForm(user=reset.usuario)
        return self.render_sensitive(
            request,
            self.template_name,
            self.get_context_data(form, token),
        )

    def post(self, request, token, *args, **kwargs):
        with transaction.atomic():
            reset = self.get_reset(token, lock=True)
            if reset is None:
                return self.render_sensitive(
                    request,
                    "usuarios/password_reset_invalid.html",
                    status=400,
                )
            form = PasswordResetSetPasswordForm(
                user=reset.usuario,
                data=request.POST,
            )
            if form.is_valid():
                form.save()
                PasswordReset.objects.filter(usuario=reset.usuario).delete()
                return self.render_sensitive(
                    request,
                    "usuarios/password_reset_complete.html",
                )

        return self.render_sensitive(
            request,
            self.template_name,
            self.get_context_data(form, token),
            status=400,
        )


class PermisoListView(PassIdPermissionMixin, ListView):
    model = Permiso
    template_name = "usuarios/permiso_list.html"
    context_object_name = "permisos"
    paginate_by = 10
    required_permission = "usuario.view_permiso"

    def get_queryset(self):
        self.permission_type = self.request.GET.get("tipo", "").strip()
        self.query = self.request.GET.get("q", "").strip()
        queryset = Permiso.objects.order_by("id")
        if self.permission_type:
            queryset = queryset.filter(tipo=self.permission_type)
        if self.query:
            queryset = queryset.filter(
                Q(codename__icontains=self.query) |
                Q(nombre__icontains=self.query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        permission_type = getattr(
            self,
            "permission_type",
            self.request.GET.get("tipo", "").strip(),
        )
        query = getattr(self, "query", self.request.GET.get("q", "").strip())
        context["query"] = query
        context["selected_type"] = permission_type
        context["permission_types"] = (
            Permiso.objects.order_by()
            .values_list("tipo", flat=True)
            .distinct()
        )
        context["pagination_query"] = urlencode(
            {key: value for key, value in {"tipo": permission_type, "q": query}.items() if value}
        )
        context["total_count"] = self.get_queryset().count()
        return context


class PermisoCreateView(PassIdPermissionMixin, CreateView):
    model = Permiso
    form_class = PermisoForm
    template_name = "usuarios/permiso_form.html"
    success_url = reverse_lazy("usuarios:permiso_list")
    required_permission = "usuario.add_permiso"

    def form_valid(self, form):
        messages.success(self.request, f"Permiso '{form.instance.codename}' creado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Crear Nuevo Permiso"
        context["button_text"] = "Guardar Permiso"
        return context


class PermisoUpdateView(PassIdPermissionMixin, UpdateView):
    model = Permiso
    form_class = PermisoForm
    template_name = "usuarios/permiso_form.html"
    success_url = reverse_lazy("usuarios:permiso_list")
    required_permission = "usuario.change_permiso"

    def form_valid(self, form):
        messages.success(self.request, f"Permiso '{form.instance.codename}' actualizado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Permiso: {self.object.codename}"
        context["button_text"] = "Actualizar Permiso"
        return context


class PermisoDeleteView(PassIdPermissionMixin, DeleteView):
    model = Permiso
    template_name = "usuarios/permiso_confirm_delete.html"
    success_url = reverse_lazy("usuarios:permiso_list")
    context_object_name = "permiso"
    required_permission = "usuario.delete_permiso"

    def delete(self, request, *args, **kwargs):
        permiso = self.get_object()
        messages.success(request, f"Permiso '{permiso.codename}' eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class PerfilListView(PassIdPermissionMixin, ListView):
    model = Perfil
    template_name = "usuarios/perfil_list.html"
    context_object_name = "perfiles"
    paginate_by = 10
    required_permission = "usuario.view_perfil"

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


class PerfilCreateView(PassIdPermissionMixin, CreateView):
    model = Perfil
    form_class = PerfilForm
    template_name = "usuarios/perfil_form.html"
    success_url = reverse_lazy("usuarios:perfil_list")
    required_permission = "usuario.add_perfil"

    def form_valid(self, form):
        messages.success(self.request, f"Perfil '{form.instance.nombre}' creado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Crear Nuevo Perfil / Rol"
        context["button_text"] = "Guardar Perfil"
        return context


class PerfilUpdateView(PassIdPermissionMixin, UpdateView):
    model = Perfil
    form_class = PerfilForm
    template_name = "usuarios/perfil_form.html"
    success_url = reverse_lazy("usuarios:perfil_list")
    required_permission = "usuario.change_perfil"

    def form_valid(self, form):
        messages.success(self.request, f"Perfil '{form.instance.nombre}' actualizado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Perfil: {self.object.nombre}"
        context["button_text"] = "Actualizar Perfil"
        return context


class PerfilDeleteView(PassIdPermissionMixin, DeleteView):
    model = Perfil
    template_name = "usuarios/perfil_confirm_delete.html"
    success_url = reverse_lazy("usuarios:perfil_list")
    context_object_name = "perfil"
    required_permission = "usuario.delete_perfil"

    def delete(self, request, *args, **kwargs):
        perfil = self.get_object()
        messages.success(request, f"Perfil '{perfil.nombre}' eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class UsuarioListView(PassIdPermissionMixin, ListView):
    model = Usuario
    template_name = "usuarios/usuario_list.html"
    context_object_name = "usuarios_list"
    paginate_by = 10
    required_permission = "usuario.view_usuario"

    def get_filters(self):
        return {
            "grupo": self.request.GET.get("grupo", "").strip(),
            "categoria": self.request.GET.get("categoria", "").strip(),
            "activo": self.request.GET.get("activo", "").strip(),
            "q": self.request.GET.get("q", "").strip(),
        }

    def get_queryset(self):
        self.filters = self.get_filters()
        queryset = Usuario.objects.prefetch_related("perfiles").all()
        if self.filters["grupo"]:
            queryset = queryset.filter(grupo=self.filters["grupo"])
        if self.filters["categoria"]:
            queryset = queryset.filter(categoria=self.filters["categoria"])
        if self.filters["activo"] in {"1", "0"}:
            queryset = queryset.filter(activo=self.filters["activo"] == "1")

        query = self.filters["q"]
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |
                Q(nombre__icontains=query) |
                Q(apaterno__icontains=query) |
                Q(amaterno__icontains=query) |
                Q(email__icontains=query) |
                Q(matricula__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = getattr(self, "filters", self.get_filters())
        context["query"] = filters["q"]
        context["filters"] = filters
        context["grupos"] = (
            Usuario.objects.exclude(grupo="")
            .values_list("grupo", flat=True)
            .distinct()
            .order_by("grupo")
        )
        context["categorias"] = (
            Usuario.objects.exclude(categoria__isnull=True)
            .exclude(categoria="")
            .values_list("categoria", flat=True)
            .distinct()
            .order_by("categoria")
        )
        context["pagination_query"] = urlencode(
            {
                key: value
                for key, value in filters.items()
                if value
            }
        )
        context["total_count"] = self.get_queryset().count()
        return context


class UsuarioCreateView(PassIdPermissionMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:usuario_list")
    required_permission = "usuario.add_usuario"

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' registrado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar Nuevo Usuario"
        context["button_text"] = "Guardar Usuario"
        return context


class UsuarioImportView(PassIdPermissionMixin, FormView):
    form_class = UsuarioImportForm
    template_name = "usuarios/usuario_importar.html"
    required_permission = "usuario.add_usuario_masivo"

    def form_valid(self, form):
        try:
            report = import_users(form.cleaned_data["archivo"])
        except ValidationError as error:
            form.add_error("archivo", error)
            return self.form_invalid(form)
        return self.render_to_response(
            self.get_context_data(form=form, report=report)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("title", "Carga masiva de usuarios")
        return context


class UsuarioUpdateView(PassIdPermissionMixin, UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = "usuarios/usuario_form.html"
    required_permission = "usuario.change_usuario"

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' actualizado correctamente.")
        return super().form_valid(form)

    def get_success_url(self):
        return f"{reverse('usuarios:usuario_update', kwargs={'pk': self.object.pk})}#messages"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Usuario: {self.object.username}"
        context["button_text"] = "Actualizar Usuario"
        permission_values = context["form"]["permisos_directos"].value() or []
        context["permisos_directos_seleccionados"] = [
            str(permission_id) for permission_id in permission_values
        ]
        context["permisos"] = Permiso.objects.order_by(
            "tipo",
            "codename",
        )
        context["tipos_permisos"] = (
            Permiso.objects.order_by()
            .values_list("tipo", flat=True)
            .distinct()
        )
        return context


class UsuarioDeleteView(PassIdPermissionMixin, DeleteView):
    model = Usuario
    template_name = "usuarios/usuario_confirm_delete.html"
    success_url = reverse_lazy("usuarios:usuario_list")
    context_object_name = "usuario"
    required_permission = "usuario.delete_usuario"

    def delete(self, request, *args, **kwargs):
        usuario = self.get_object()
        messages.success(request, f"Usuario '{usuario.username}' eliminado correctamente.")
        return super().delete(request, *args, **kwargs)

class MiPerfilView(PassIdPermissionMixin, UpdateView):
    model = Usuario
    form_class = MiPerfilForm
    template_name = 'usuarios/mi_perfil.html' 
    success_url = reverse_lazy('autenticacion:login')
    required_permission = "usuario.change_mi_perfil"

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Configuración de mi Perfil'
        context['cancel_url'] = reverse_lazy('home')
        context['submit_text'] = 'Guardar Cambios'
        return context

    def form_valid(self, form):
        messages.success(self.request, "Perfil actualizado exitosamente. Por favor, inicia sesión nuevamente.")
        response = super().form_valid(form)
        logout(self.request)
        return response

class CambiarPasswordView(PassIdPermissionMixin, PasswordChangeView):
    template_name = 'usuarios/cambiar_password.html'
    success_url = reverse_lazy('autenticacion:login')
    required_permission = "usuario.change_password"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        autocomplete_values = {
            "old_password": "current-password",
            "new_password1": "new-password",
            "new_password2": "new-password",
        }
        for field_name, autocomplete in autocomplete_values.items():
            widget = form.fields[field_name].widget
            widget.attrs["class"] = "form-control"
            widget.attrs["autocomplete"] = autocomplete
        return form

    def form_valid(self, form):
        messages.success(self.request, "Tu contraseña ha sido actualizada. Por favor, inicia sesión con tu nueva contraseña.")
        response = super().form_valid(form)
        logout(self.request)
        return response