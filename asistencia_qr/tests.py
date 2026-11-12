import base64
from datetime import time
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from academico.models import Aula, AsistenciaClase, Carrera, Horario, Inscripcion, Materia
from .forms import EscaneoAsistenciaForm
from usuarios.models import Perfil, Permiso, Usuario

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
        horario_admin_permission, _ = Permiso.objects.get_or_create(
            codename="admin",
            defaults={
                "tipo": "horario",
                "nombre": "Administrar horarios de todos los profesores",
            },
        )
        enrollment_permission, _ = Permiso.objects.get_or_create(
            codename="inscribir_estudiante_en_clase",
            defaults={
                "tipo": "asistencia_qr",
                "nombre": "Inscribir alumnos desde el lector QR",
            },
        )
        cls.student.permisos_directos.add(home_permission, qr_permission)
        cls.teacher.permisos_directos.add(scan_permission)
        cls.teacher.permisos_directos.add(enrollment_permission)

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
        self.assertContains(response, 'class="pass-ticket pass-ticket-dashboard"')
        self.assertContains(
            response,
            f'src="{reverse("asistencia_qr:qr_imagen")}"',
        )
        self.assertContains(response, "Código QR firmado de asistencia PASS-ID")
        self.assertContains(response, reverse("asistencia_qr:mi_qr"))
        self.assertContains(response, "/static/js/qr-refresh.js")
        self.assertNotContains(response, "data:image/png;base64")

    def test_my_qr_renders_a_ticket_with_student_identity_and_refresh(self):
        self.student.nombre = "Ada"
        self.student.apaterno = "Lovelace"
        self.student.save(update_fields=["nombre", "apaterno"])
        self.client.force_login(self.student)

        response = self.client.get(reverse("asistencia_qr:mi_qr"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="pass-ticket pass-ticket-full"')
        self.assertContains(response, "Ada Lovelace")
        self.assertContains(response, self.student.matricula)
        self.assertContains(response, 'data-qr-refresh-url=')
        self.assertContains(response, "/static/js/qr-refresh.js")
        self.assertNotContains(response, "style=")

    def test_my_qr_explains_when_student_has_no_matricula(self):
        self.student.matricula = ""
        self.student.save(update_fields=["matricula"])
        self.client.force_login(self.student)

        response = self.client.get(reverse("asistencia_qr:mi_qr"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No tienes una matrícula registrada")
        self.assertNotContains(response, 'id="student-qr"')
        self.assertNotContains(response, "/static/js/qr-refresh.js")

    def test_scanner_renders_confirmation_action_for_enrollment(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("asistencia_qr:lector"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scanner-enroll-confirm"')

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

    def test_reader_accepts_manual_matricula_and_records_attendance(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("asistencia_qr:registrar"),
            {
                "horario": self.horario.pk,
                "token": "",
                "matricula": self.student.matricula,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(AsistenciaClase.objects.get().metodo, "manual")

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

    def post_signed_qr(self, **data):
        token = signing.dumps(
            {"matricula": self.student.matricula},
            salt=QR_SIGNING_SALT,
            compress=True,
        )
        payload = {"horario": self.horario.pk, "token": token, "matricula": ""}
        payload.update(data)
        self.client.force_login(self.teacher)
        return self.client.post(reverse("asistencia_qr:registrar"), payload)

    def test_reader_reports_missing_enrollment_and_allows_in_place_enrollment(self):
        Inscripcion.objects.all().delete()

        response = self.post_signed_qr()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "sin_inscripcion")
        self.assertTrue(response.json()["can_enroll"])
        self.assertFalse(AsistenciaClase.objects.exists())

        response = self.post_signed_qr(inscribir="on")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "inscrito")
        enrollment = Inscripcion.objects.get(usuario=self.student)
        self.assertTrue(enrollment.activa)
        self.assertEqual(enrollment.materia, self.horario.materia)
        self.assertEqual(enrollment.grupo, self.horario.grupo)
        self.assertEqual(enrollment.periodo, self.horario.periodo)
        self.assertTrue(AsistenciaClase.objects.filter(usuario=self.student).exists())

    def test_reader_distinguishes_and_reactivates_inactive_enrollment(self):
        enrollment = Inscripcion.objects.get(usuario=self.student)
        enrollment.activa = False
        enrollment.save(update_fields=["activa"])

        response = self.post_signed_qr()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "inscripcion_inactiva")
        self.assertTrue(response.json()["can_enroll"])

        response = self.post_signed_qr(inscribir="on")

        self.assertEqual(response.status_code, 200)
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.activa)
        self.assertTrue(AsistenciaClase.objects.filter(usuario=self.student).exists())

    def test_reader_reports_inactive_student_account_without_enrolling(self):
        self.student.activo = False
        self.student.save(update_fields=["activo"])

        response = self.post_signed_qr(inscribir="on")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "cuenta_inactiva")
        self.assertFalse(AsistenciaClase.objects.exists())

    def test_scanner_can_enroll_without_separate_enrollment_permission(self):
        Inscripcion.objects.all().delete()
        self.teacher.permisos_directos.clear()
        self.teacher.permisos_directos.add(
            Permiso.objects.get(codename="escanear_asistencia")
        )

        response = self.post_signed_qr(inscribir="on")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "inscrito")
        self.assertTrue(
            Inscripcion.objects.filter(
                usuario=self.student,
                materia=self.horario.materia,
                grupo=self.horario.grupo,
                periodo=self.horario.periodo,
                activa=True,
            ).exists()
        )
        self.assertTrue(AsistenciaClase.objects.filter(usuario=self.student).exists())

    def test_migration_grants_enrollment_permission_to_professor_profile(self):
        professor_profile = Perfil.objects.get(nombre__iexact="profesor")

        self.assertTrue(
            professor_profile.tiene_permiso(
                "asistencia_qr.inscribir_estudiante_en_clase"
            )
        )

    def test_schedule_admin_can_select_active_schedules_from_all_teachers(self):
        other_teacher = Usuario(
            username="qr_other_teacher",
            email="qr-other-teacher@example.invalid",
            whatsapp="",
            grupo="",
        )
        other_teacher.set_password("test-password")
        other_teacher.save()
        other_schedule = Horario.objects.create(
            materia=self.horario.materia,
            profesor=other_teacher,
            aula=self.horario.aula,
            grupo="B",
            dia_semana="martes",
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            periodo="2026-2",
        )
        self.teacher.permisos_directos.add(
            Permiso.objects.get(tipo="horario", codename="admin")
        )

        form = EscaneoAsistenciaForm(user=self.teacher)

        self.assertIn(self.horario, form.fields["horario"].queryset)
        self.assertIn(other_schedule, form.fields["horario"].queryset)
