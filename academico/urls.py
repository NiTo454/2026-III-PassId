from django.urls import path
from .views import (
    CarreraListView, CarreraCreateView, CarreraUpdateView, CarreraDeleteView,
    AulaListView, AulaCreateView, AulaUpdateView, AulaDeleteView,
    MateriaListView, MateriaCreateView, MateriaUpdateView, MateriaDeleteView,
    HorarioListView, HorarioCreateView, HorarioUpdateView, HorarioDeleteView,
    InscripcionListView, InscripcionCreateView, InscripcionUpdateView, 
    InscripcionDeleteView, InscripcionDetailView, CarreraDetailView, 
    AulaDetailView, MateriaDetailView, HorarioDetailView, ProgresoAsistenciaView,
    CargaAcademicaView, DisponibilidadDocenteView,
)

app_name = "academico"

urlpatterns = [
    # Carreras
    path("carreras/", CarreraListView.as_view(), name="carrera_list"),
    path("carreras/crear/", CarreraCreateView.as_view(), name="carrera_create"),
    path("carreras/<int:pk>/editar/", CarreraUpdateView.as_view(), name="carrera_update"),
    path("carreras/<int:pk>/eliminar/", CarreraDeleteView.as_view(), name="carrera_delete"),
    path("carreras/<int:pk>/detalles/", CarreraDetailView.as_view(), name="carrera_detail"),

    # Aulas
    path("aulas/", AulaListView.as_view(), name="aula_list"),
    path("aulas/crear/", AulaCreateView.as_view(), name="aula_create"),
    path("aulas/<int:pk>/editar/", AulaUpdateView.as_view(), name="aula_update"),
    path("aulas/<int:pk>/eliminar/", AulaDeleteView.as_view(), name="aula_delete"),
    path("aulas/<int:pk>/detalles/", AulaDetailView.as_view(), name="aula_detail"),

    # Materias
    path("materias/", MateriaListView.as_view(), name="materia_list"),
    path("materias/crear/", MateriaCreateView.as_view(), name="materia_create"),
    path("materias/<int:pk>/editar/", MateriaUpdateView.as_view(), name="materia_update"),
    path("materias/<int:pk>/eliminar/", MateriaDeleteView.as_view(), name="materia_delete"),
    path("materias/<int:pk>/detalles/", MateriaDetailView.as_view(), name="materia_detail"),

    # Horarios
    path("horarios/", HorarioListView.as_view(), name="horario_list"),
    path("horarios/crear/", HorarioCreateView.as_view(), name="horario_create"),
    path("horarios/<int:pk>/editar/", HorarioUpdateView.as_view(), name="horario_update"),
    path("horarios/<int:pk>/eliminar/", HorarioDeleteView.as_view(), name="horario_delete"),
    path("horarios/<int:pk>/detalles/", HorarioDetailView.as_view(), name="horario_detail"),

    # Inscripciones
    path("inscripciones/", InscripcionListView.as_view(), name="inscripcion_list"),
    path("inscripciones/crear/", InscripcionCreateView.as_view(), name="inscripcion_create"),
    path("inscripciones/<int:pk>/editar/", InscripcionUpdateView.as_view(), name="inscripcion_update"),
    path("inscripciones/<int:pk>/eliminar/", InscripcionDeleteView.as_view(), name="inscripcion_delete"),
    path("inscripciones/<int:pk>/detalles/", InscripcionDetailView.as_view(), name="inscripcion_detail"),
    path("mi-progreso/", ProgresoAsistenciaView.as_view(), name="mi_progreso"),

     path("carga-academica/",CargaAcademicaView.as_view(), name="carga_academica",
    ),
     path(
         "disponibilidad-docente/",
         DisponibilidadDocenteView.as_view(),
         name="disponibilidad_docente",
     ),
]
