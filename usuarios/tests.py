from datetime import timedelta

from django.contrib.auth.hashers import is_password_usable
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from eventos.models import Evento
from .models import Perfil, Usuario


class PerfilLecturaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perfil = Perfil.objects.get(nombre="lectura")
        cls.usuario = Usuario.objects.get(username="lectura")

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_seeded_account_has_only_read_permissions_and_no_password(self):
        self.assertIn(self.perfil, self.usuario.perfiles.all())
        self.assertFalse(is_password_usable(self.usuario.password))

        permissions = set(self.usuario.get_all_permissions())
        self.assertIn("core.view_home", permissions)
        self.assertIn("evento.view_eventos_disponibles", permissions)
        self.assertIn("registro.view_registro", permissions)
        self.assertIn("asistencia_clase.ver_historial", permissions)
        self.assertNotIn("evento.add_evento", permissions)
        self.assertNotIn("otro.autorregistrarse", permissions)
        self.assertNotIn("usuario.change_usuario", permissions)

    def test_read_only_account_can_open_read_screens(self):
        route_names = (
            "home",
            "usuarios:permiso_list",
            "usuarios:perfil_list",
            "usuarios:usuario_list",
            "academico:carrera_list",
            "academico:aula_list",
            "academico:materia_list",
            "academico:horario_list",
            "academico:inscripcion_list",
            "academico:mi_progreso",
            "academico:carga_academica",
            "eventos:evento_list",
            "eventos:registro_list",
            "eventos:asistencia_list",
            "eventos:eventos_disponibles",
            "asistencia_qr:mi_qr",
            "asistencia_qr:asistencia_list",
        )

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_read_only_account_cannot_use_write_routes(self):
        routes = (
            ("usuarios:permiso_create", {}),
            ("usuarios:perfil_create", {}),
            ("usuarios:usuario_create", {}),
            ("academico:carrera_create", {}),
            ("academico:aula_create", {}),
            ("academico:materia_create", {}),
            ("academico:horario_create", {}),
            ("academico:inscripcion_create", {}),
            ("eventos:evento_create", {}),
            ("eventos:registro_create", {}),
            ("eventos:asistencia_create", {}),
            ("eventos:autoregistro_inscribir", {"pk": 1}),
            ("eventos:autoregistro_cancelar", {"pk": 1}),
            ("asistencia_qr:lector", {}),
        )

        for route_name, kwargs in routes:
            with self.subTest(route_name=route_name):
                response = self.client.post(reverse(route_name, kwargs=kwargs))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("home"))

    def test_available_events_screen_does_not_show_registration_controls(self):
        Evento.objects.create(
            nombre="Evento de prueba",
            fecha_hora=timezone.now() + timedelta(days=1),
            permitir_autorregistro=True,
        )
        response = self.client.get(reverse("eventos:eventos_disponibles"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evento de prueba")
        self.assertNotContains(response, "Inscribirme")
        self.assertNotContains(response, "Cancelar")
        self.assertContains(response, "Solo lectura")
