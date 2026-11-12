from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academico.models import Aula, Carrera, Horario, Inscripcion, Materia
from eventos.models import Asistencia, Evento
from usuarios.models import Usuario


class HomeMetricsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ahora = timezone.make_aware(datetime(2026, 11, 9, 10, 30))
        cls.usuario = Usuario.objects.create(
            username="dashboard",
            password=make_password("dashboard-test"),
            email="dashboard@example.com",
            nombre="Dashboard",
            whatsapp="",
            grupo="A",
            activo=True,
            is_superuser=True,
        )
        carrera = Carrera.objects.create(clave="DASH", nombre="Carrera dashboard")
        cls.materia = Materia.objects.create(
            clave="DASH-101",
            nombre="Materia inscrita",
            horas_semana=4,
            carrera=carrera,
        )
        cls.inscripcion = Inscripcion.objects.create(
            usuario=cls.usuario,
            materia=cls.materia,
            grupo="A",
            periodo="2026-3",
            activa=True,
        )
        materia_inactiva = Materia.objects.create(
            clave="DASH-102",
            nombre="Materia no activa",
            horas_semana=3,
            carrera=carrera,
        )
        Inscripcion.objects.create(
            usuario=cls.usuario,
            materia=materia_inactiva,
            grupo="A",
            periodo="2026-3",
            activa=False,
        )
        cls.aula = Aula.objects.create(codigo="DASH-1")

        cls.evento_pasado = Evento.objects.create(
            nombre="Evento pasado",
            fecha_hora=timezone.make_aware(datetime(2026, 11, 8, 10, 0)),
        )
        cls.evento_futuro = Evento.objects.create(
            nombre="Evento futuro",
            fecha_hora=timezone.make_aware(datetime(2026, 11, 10, 10, 0)),
            lugar="Auditorio",
        )
        Asistencia.objects.create(
            evento=cls.evento_pasado,
            usuario=cls.usuario,
            registrado_por=cls.usuario,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def get_home(self):
        with patch("core.views.timezone.localtime", return_value=self.ahora):
            return self.client.get(reverse("home"))

    def create_schedule(self, *, start, end, group="A", day="lunes", period="2026-3"):
        return Horario.objects.create(
            materia=self.materia,
            profesor=self.usuario,
            aula=self.aula,
            grupo=group,
            dia_semana=day,
            hora_inicio=start,
            hora_fin=end,
            periodo=period,
            activo=True,
        )

    def test_home_shows_database_metrics_and_nearest_future_event(self):
        response = self.get_home()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["estadisticas"],
            {
                "materias": 1,
                "horas_sem": 4,
                "eventos": 2,
                "asistencias_evt": 1,
            },
        )
        self.assertEqual(response.context["evento_proximo"], self.evento_futuro)
        self.assertIsNone(response.context["siguiente_clase"])
        self.assertContains(response, "Materias inscritas")
        self.assertContains(response, "Evento futuro")
        self.assertNotContains(response, "20/12/2026")
        self.assertContains(response, 'class="dashboard"')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'aria-controls="navLinks"')
        self.assertContains(response, 'class="site-footer"')

    def test_next_class_matches_today_enrollment_group_and_period(self):
        clase_pasada = self.create_schedule(start="09:00", end="10:00")
        self.create_schedule(start="11:00", end="12:00", group="B")
        self.create_schedule(start="11:30", end="12:30", period="2026-2")
        siguiente = self.create_schedule(start="12:00", end="13:00")
        self.create_schedule(start="11:00", end="12:00", day="martes")

        response = self.get_home()

        self.assertEqual(response.context["siguiente_clase"], siguiente)
        self.assertFalse(response.context["clase_en_curso"])
        self.assertTrue(response.context["hay_clases_hoy"])
        self.assertNotEqual(response.context["siguiente_clase"], clase_pasada)

    def test_home_identifies_a_class_that_is_currently_in_progress(self):
        clase_actual = self.create_schedule(start="10:00", end="11:00")
        self.create_schedule(start="12:00", end="13:00")

        response = self.get_home()

        self.assertEqual(response.context["siguiente_clase"], clase_actual)
        self.assertTrue(response.context["clase_en_curso"])
        self.assertContains(response, "En curso")
