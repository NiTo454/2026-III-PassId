from django.contrib import admin
from .models import Evento, Registro, Asistencia, ResponsableEvento

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fecha_hora", "lugar", "requiere_registro", "permitir_autorregistro")
    search_fields = ("nombre", "lugar")
    list_filter = ("requiere_registro", "permitir_autorregistro")
    filter_horizontal = ("responsables", "asistentes_registrados")

@admin.register(Registro)
class RegistroAdmin(admin.ModelAdmin):
    list_display = ("evento", "usuario", "fecha_registro", "equipo")
    search_fields = ("evento__nombre", "usuario__username", "usuario__matricula")
    list_filter = ("evento",)

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("evento", "usuario", "registrado_por", "fecha_entrada")
    search_fields = ("evento__nombre", "usuario__username", "registrado_por__username")
    list_filter = ("evento",)

@admin.register(ResponsableEvento)
class ResponsableEventoAdmin(admin.ModelAdmin):
    list_display = ("evento", "usuario")
