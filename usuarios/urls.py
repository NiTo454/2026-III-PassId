from django.urls import path
from .views import (
    PermisoListView,
    PermisoCreateView,
    PermisoUpdateView,
    PermisoDeleteView,
    PerfilListView,
    PerfilCreateView,
    PerfilUpdateView,
    PerfilDeleteView,
    UsuarioListView,
    UsuarioCreateView,
    UsuarioUpdateView,
    UsuarioDeleteView,
)

app_name = "usuarios"

urlpatterns = [
    path("permisos/", PermisoListView.as_view(), name="permiso_list"),
    path("permisos/crear/", PermisoCreateView.as_view(), name="permiso_create"),
    path("permisos/<int:pk>/editar/", PermisoUpdateView.as_view(), name="permiso_update"),
    path("permisos/<int:pk>/eliminar/", PermisoDeleteView.as_view(), name="permiso_delete"),

    path("perfiles/", PerfilListView.as_view(), name="perfil_list"),
    path("perfiles/crear/", PerfilCreateView.as_view(), name="perfil_create"),
    path("perfiles/<int:pk>/editar/", PerfilUpdateView.as_view(), name="perfil_update"),
    path("perfiles/<int:pk>/eliminar/", PerfilDeleteView.as_view(), name="perfil_delete"),

    path("usuarios/", UsuarioListView.as_view(), name="usuario_list"),
    path("usuarios/crear/", UsuarioCreateView.as_view(), name="usuario_create"),
    path("usuarios/<int:pk>/editar/", UsuarioUpdateView.as_view(), name="usuario_update"),
    path("usuarios/<int:pk>/eliminar/", UsuarioDeleteView.as_view(), name="usuario_delete"),
]
