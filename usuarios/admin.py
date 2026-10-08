from django.contrib import admin
from .models import Permiso, Perfil, Usuario, PerfilTienePermiso, UsuarioTienePerfil, UsuarioTienePermiso, PasswordReset

class PerfilTienePermisoInline(admin.TabularInline):
    model = PerfilTienePermiso
    extra = 1

class UsuarioTienePerfilInline(admin.TabularInline):
    model = UsuarioTienePerfil
    extra = 1

class UsuarioTienePermisoInline(admin.TabularInline):
    model = UsuarioTienePermiso
    extra = 1

@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "codename", "nombre")
    search_fields = ("tipo", "codename", "nombre")
    list_filter = ("tipo",)

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)
    inlines = [PerfilTienePermisoInline]

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "nombre", "apaterno", "matricula", "grupo", "activo", "is_superuser")
    search_fields = ("username", "email", "nombre", "apaterno", "matricula")
    list_filter = ("activo", "is_superuser", "grupo", "categoria")
    inlines = [UsuarioTienePerfilInline, UsuarioTienePermisoInline]

@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ("usuario", "token", "expira_en")
    search_fields = ("usuario__username", "token")

