from django.contrib import admin
from .models import Permiso, Perfil, Usuario, PasswordReset

@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "codename", "nombre")
    search_fields = ("tipo", "codename", "nombre")
    list_filter = ("tipo",)

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)
    filter_horizontal = ("permisos",)

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "nombre", "apaterno", "matricula", "grupo", "activo", "superusuario")
    search_fields = ("username", "email", "nombre", "apaterno", "matricula")
    list_filter = ("activo", "superusuario", "grupo", "categoria")
    filter_horizontal = ("perfiles", "permisos_directos")

@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ("usuario", "token", "expira_en")
    search_fields = ("usuario__username", "token")
