import base64
from datetime import time
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from academico.models import Aula, AsistenciaClase, Carrera, Horario, Inscripcion, Materia
from usuarios.models import Permiso, Usuario

from .views import QR_SIGNING_SALT, QR_TOKEN_MAX_AGE_SECONDS


class QrAttendanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Usuario(
            username="qr_student",
            email="qr-student@example.invalid",
            whatsapp="",
            grupo="A",
            matricula="QR-STUDENT-001",
        )
        cls.student.set_password("test-password")
        cls.student.save()
        cls.teacher = Usuario(
            username="qr_teacher",
            email="qr-teacher@example.invalid",
            whatsapp="",
            grupo="",
        )
        cls.teacher.set_password("test-password")
        cls.teacher.save()

        home_permission, _ = Permiso.objects.get_or_create(
            codename="view_home",
            defaults={"tipo": "core"},
        )
        qr_permission, _ = Permiso.objects.get_or_create(
            codename="ver_mi_qr",
            defaults={"tipo": "asistencia_qr"},
        )
        scan_permission, _ = Permiso.objects.get_or_create(
            codename="escanear_asistencia",
            defaults={"tipo": "asistencia_qr"},
        )
        cls.student.permisos_directos.add(home_permission, qr_permission)
        cls.teacher.permisos_directos.add(scan_permission)

        carrera = Carrera.objects.create(clave="QR-TEST", nombre="Carrera QR")
        aula = Aula.objects.create(codigo="QR-TEST", tipo="aula")
        materia = Materia.objects.create(
            clave="QR-TEST",
            nombre="Materia QR",
            carrera=carrera,
        )
        cls.horario = Horario.objects.create(
            materia=materia,
            profesor=cls.teacher,
            aula=aula,
            grupo="A",
            dia_semana="lunes",
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
            periodo="2026-2",
        )
        Inscripcion.objects.create(
            usuario=cls.student,
            materia=materia,
            grupo="A",
            periodo="2026-2",
            activa=True,
        )

    def test_home_uses_the_signed_attendance_qr_endpoint(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'src="{reverse("asistencia_qr:qr_imagen")}"',
        )
        self.assertContains(response, "Código QR firmado de asistencia PASS-ID")
        self.assertContains(response, "/static/js/qr-refresh.js")
        self.assertNotContains(response, "data:image/png;base64")

    def test_qr_image_contains_a_token_signed_for_the_student_matricula(self):
        encoded_image = base64.b64encode(b"test-image").decode("ascii")
        self.client.force_login(self.student)

        with patch("asistencia_qr.views.generar_qr", return_value=encoded_image) as generate_qr:
            response = self.client.get(reverse("asistencia_qr:qr_imagen"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"test-image")
        token = generate_qr.call_args.args[0]
        self.assertEqual(
            signing.loads(
                token,
                salt=QR_SIGNING_SALT,
                max_age=QR_TOKEN_MAX_AGE_SECONDS,
            ),
            {"matricula": self.student.matricula},
        )

    def test_reader_accepts_the_signed_qr_and_records_attendance(self):
        token = signing.dumps(
            {"matricula": self.student.matricula},
            salt=QR_SIGNING_SALT,
            compress=True,
        )
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("asistencia_qr:registrar"),
            {"horario": self.horario.pk, "token": token, "matricula": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(
            AsistenciaClase.objects.get().metodo,
            "qr",
        )

    def test_reader_rejects_the_unsigned_homepage_matricula_qr(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("asistencia_qr:registrar"),
            {
                "horario": self.horario.pk,
                "token": self.student.matricula,
                "matricula": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "El QR no es válido o fue alterado.",
        )
        self.assertFalse(AsistenciaClase.objects.exists())
