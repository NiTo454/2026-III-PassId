from datetime import date

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from usuarios.models import Usuario
from .models import AsistenciaClase, Aula, Carrera, Horario, IncidenciaAsistencia, Inscripcion, Materia


class AsistenciaConUbicacionTests(TestCase):
    def setUp(self):
        self.hoy = date(2026, 10, 26)
        self.alumno = Usuario.objects.create(
            username="alumno",
            password=make_password("clave"),
            email="alumno@example.com",
            whatsapp="5550000000",
            grupo="A",
            activo=True,
        )
        self.administrador = Usuario.objects.create(
            username="admin",
            password=make_password("clave"),
            email="admin@example.com",
            whatsapp="5550000001",
            grupo="",
            activo=True,
            is_superuser=True,
        )
        carrera = Carrera.objects.create(clave="TEST", nombre="Carrera de prueba")
        materia = Materia.objects.create(clave="TEST-1", nombre="Materia de prueba", carrera=carrera)
        aula = Aula.objects.create(codigo="A-1")
        self.horario = Horario.objects.create(
            materia=materia,
            profesor=self.administrador,
            aula=aula,
            grupo="A",
            dia_semana="lunes",
            hora_inicio="08:00",
            hora_fin="09:00",
            periodo="2026-3",
            activo=True,
        )
        Inscripcion.objects.create(
            usuario=self.alumno,
            materia=materia,
            grupo="A",
            periodo="2026-3",
            activa=True,
        )

    @patch("academico.views.timezone.localdate")
    def test_alumno_registra_asistencia_con_coordenadas(self, localdate):
        localdate.return_value = self.hoy
        self.client.force_login(self.alumno)
        pagina = self.client.get(reverse("academico:mi_asistencia"))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Materia de prueba")

        response = self.client.post(
            reverse("academico:enviar_asistencia"),
            {
                "horario_id": self.horario.pk,
                "latitud": "19.43261234",
                "longitud": "-99.13320987",
            },
        )

        self.assertEqual(response.status_code, 200)
        asistencia = AsistenciaClase.objects.get(horario=self.horario, usuario=self.alumno, fecha=self.hoy)
        self.assertEqual(asistencia.metodo, "ubicacion")
        self.assertEqual(str(asistencia.latitud), "19.432612")
        self.assertEqual(str(asistencia.longitud), "-99.133210")

    @patch("academico.views.timezone.localdate")
    def test_tres_fallos_generan_solicitud_y_admin_puede_asistir(self, localdate):
        localdate.return_value = self.hoy
        self.client.force_login(self.alumno)
        for numero in range(1, 4):
            response = self.client.post(
                reverse("academico:reportar_fallo_ubicacion"),
                {"horario_id": self.horario.pk, "motivo": f"Error de ubicación {numero}"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["intentos"], numero)

        incidencia = IncidenciaAsistencia.objects.get(horario=self.horario, usuario=self.alumno)
        self.assertEqual(incidencia.intentos, 3)
        self.assertIn("Error de ubicación 3", incidencia.motivo)

        self.client.force_login(self.administrador)
        pagina = self.client.get(reverse("academico:incidencias_asistencia"))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Error de ubicación 3")
        response = self.client.post(
            reverse("academico:incidencias_asistencia"),
            {"incidencia_id": incidencia.pk},
        )

        self.assertRedirects(response, reverse("academico:incidencias_asistencia"))
        asistencia = AsistenciaClase.objects.get(horario=self.horario, usuario=self.alumno, fecha=self.hoy)
        self.assertEqual(asistencia.metodo, "manual")
        self.assertEqual(asistencia.registrado_por, self.administrador)
        incidencia.refresh_from_db()
        self.assertTrue(incidencia.atendida)

    @patch("academico.views.timezone.localdate")
    def test_alumno_no_puede_reportar_clase_no_inscrita(self, localdate):
        localdate.return_value = self.hoy
        otro = Usuario.objects.create(
            username="otro",
            password=make_password("clave"),
            email="otro@example.com",
            whatsapp="5550000002",
            grupo="A",
            activo=True,
        )
        self.client.force_login(otro)

        response = self.client.post(
            reverse("academico:enviar_asistencia"),
            {"horario_id": self.horario.pk, "latitud": "19", "longitud": "-99"},
        )

        self.assertEqual(response.status_code, 404)
