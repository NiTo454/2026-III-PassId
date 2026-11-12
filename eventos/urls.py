from django.urls import path
from .views import (
    EventoListView, EventoCreateView, EventoUpdateView, EventoDeleteView,
    RegistroListView, RegistroCreateView, RegistroPlantillaView, RegistroImportView,
    RegistroUpdateView, RegistroDeleteView,
    AsistenciaListView, AsistenciaCreateView, AsistenciaDeleteView,
    EventosDisponiblesView, AutoregistroInscribirView, AutoregistroCancelarView,
    EscanearAsistenciaEventoView, InfoEventoApiView, RegistrarAsistenciaEventoQrView,
    EventoQrRegistroImagenView,
)

app_name = "eventos"

urlpatterns = [
    path("", EventoListView.as_view(), name="evento_list"),
    path("crear/", EventoCreateView.as_view(), name="evento_create"),
    path("<int:pk>/editar/", EventoUpdateView.as_view(), name="evento_update"),
    path("<int:pk>/eliminar/", EventoDeleteView.as_view(), name="evento_delete"),

    path("registros/", RegistroListView.as_view(), name="registro_list"),
    path("registros/plantilla/", RegistroPlantillaView.as_view(), name="registro_template"),
    path("registros/importar/", RegistroImportView.as_view(), name="registro_import"),
    path("registros/crear/", RegistroCreateView.as_view(), name="registro_create"),
    path("registros/<int:pk>/editar/", RegistroUpdateView.as_view(), name="registro_update"),
    path("registros/<int:pk>/eliminar/", RegistroDeleteView.as_view(), name="registro_delete"),

    path("asistencias/", AsistenciaListView.as_view(), name="asistencia_list"),
    path("asistencias/crear/", AsistenciaCreateView.as_view(), name="asistencia_create"),
    path("asistencias/<int:pk>/eliminar/", AsistenciaDeleteView.as_view(), name="asistencia_delete"),

 
    path("lector/", EscanearAsistenciaEventoView.as_view(), name="lector"),
    path("lector/info-evento/<int:pk>/", InfoEventoApiView.as_view(), name="info_evento"),
    path("lector/qr-registro/<int:pk>/", EventoQrRegistroImagenView.as_view(), name="qr_registro_evento"),
    path("registrar-qr/", RegistrarAsistenciaEventoQrView.as_view(), name="registrar_qr"),

    path("disponibles/", EventosDisponiblesView.as_view(), name="eventos_disponibles"),
    path("disponibles/<int:pk>/inscribir/", AutoregistroInscribirView.as_view(), name="autoregistro_inscribir"),
    path("disponibles/<int:pk>/cancelar/", AutoregistroCancelarView.as_view(), name="autoregistro_cancelar"),
]
