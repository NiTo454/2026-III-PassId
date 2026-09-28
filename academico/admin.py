from django.contrib import admin
from .models import Carrera, Aula, Materia, Horario, ProfesorDisponibilidad, Inscripcion, AsistenciaClase

@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ("clave", "nombre", "activa")
    search_fields = ("clave", "nombre")
    list_filter = ("activa",)

@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "edificio", "capacidad", "tipo", "activa")
    search_fields = ("codigo", "edificio")
    list_filter = ("tipo", "activa")

@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ("clave", "nombre", "carrera", "periodo", "asistencias", "horas_semana", "activa")
    search_fields = ("clave", "nombre")
    list_filter = ("carrera", "periodo", "activa")

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ("materia", "profesor", "aula", "grupo", "dia_semana", "hora_inicio", "hora_fin", "periodo", "activo")
    search_fields = ("materia__nombre", "profesor__username", "profesor__nombre", "grupo")
    list_filter = ("dia_semana", "periodo", "activo")

@admin.register(ProfesorDisponibilidad)
class ProfesorDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ("profesor", "dia_semana", "hora_inicio", "hora_fin", "periodo", "tipo")
    list_filter = ("dia_semana", "periodo", "tipo")

@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "materia", "grupo", "periodo", "activa", "fecha_inscripcion")
    search_fields = ("usuario__username", "usuario__matricula", "materia__nombre")
    list_filter = ("periodo", "activa", "grupo")

@admin.register(AsistenciaClase)
class AsistenciaClaseAdmin(admin.ModelAdmin):
    list_display = ("usuario", "horario", "fecha", "hora", "estado", "metodo")
    search_fields = ("usuario__username", "usuario__matricula", "horario__materia__nombre")
    list_filter = ("estado", "metodo", "fecha")
