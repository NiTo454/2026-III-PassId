from io import BytesIO, StringIO
import csv

from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from eventos.models import Evento
from .models import Perfil, Permiso, Usuario


class PerfilLecturaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perfil = Perfil.objects.get(nombre="lectura")
        cls.usuario = Usuario(
            username="test_lectura",
            email="test-lectura@example.invalid",
            whatsapp="",
            grupo="",
        )
        cls.usuario.set_password("test-password")
        cls.usuario.save()
        cls.usuario.perfiles.add(cls.perfil)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_profile_has_only_read_permissions(self):
        permissions = set(self.usuario.get_all_permissions())
        self.assertIn("core.view_home", permissions)
        self.assertIn("evento.view_eventos_disponibles", permissions)
        self.assertIn("registro.view_registro", permissions)
        self.assertIn("asistencia_clase.ver_historial", permissions)
        self.assertNotIn("evento.add_evento", permissions)
        self.assertNotIn("otro.autorregistrarse", permissions)
        self.assertNotIn("usuario.change_usuario", permissions)

    def test_migration_does_not_create_a_user_account(self):
        self.assertFalse(Usuario.objects.filter(username="lectura").exists())

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


class UsuarioImportTests(TestCase):
    headers = (
        "username",
        "email",
        "nombre",
        "apaterno",
        "amaterno",
        "matricula",
        "grupo",
        "whatsapp",
        "rol",
    )

    @classmethod
    def setUpTestData(cls):
        cls.import_permission, _ = Permiso.objects.get_or_create(
            codename="add_usuario_masivo",
            defaults={
                "tipo": "usuario",
                "nombre": "Agregar usuarios de forma masiva",
            },
        )
        cls.importer = Usuario(
            username="usuario_importador",
            email="importador@example.invalid",
            whatsapp="",
            grupo="",
        )
        cls.importer.set_password("test-password")
        cls.importer.save()
        cls.importer.permisos_directos.add(cls.import_permission)

    def setUp(self):
        self.client.force_login(self.importer)

    def make_csv(self, rows, name="usuarios.csv"):
        content = StringIO()
        writer = csv.writer(content)
        writer.writerow(self.headers)
        writer.writerows(rows)
        return SimpleUploadedFile(name, content.getvalue().encode("utf-8"))

    def make_row(self, suffix, role="alumno", **overrides):
        row = {
            "username": f"alumno{suffix}",
            "email": f"alumno{suffix}@example.invalid",
            "nombre": f"Nombre {suffix}",
            "apaterno": "Prueba",
            "amaterno": "PassID",
            "matricula": f"MAT{suffix}",
            "grupo": "A1",
            "whatsapp": "5550000000",
            "rol": role,
        }
        row.update(overrides)
        return [row[column] for column in self.headers]

    def test_imports_csv_sets_password_and_assigns_profile(self):
        professor_row = self.make_row("002", role="profesor")
        response = self.client.post(
            reverse("usuarios:usuario_import"),
            {"archivo": self.make_csv([self.make_row("001"), professor_row])},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 usuarios creados exitosamente, 0 con errores")
        student = Usuario.objects.get(username="alumno001")
        professor = Usuario.objects.get(username="alumno002")
        self.assertTrue(student.check_password("MAT001"))
        self.assertTrue(professor.check_password("MAT002"))
        self.assertTrue(student.perfiles.filter(nombre__iexact="alumno").exists())
        self.assertTrue(professor.perfiles.filter(nombre__iexact="profesor").exists())
        self.assertFalse(student.is_superuser)
        self.assertFalse(professor.is_superuser)

    def test_import_reports_duplicate_rows_and_continues(self):
        rows = [
            self.make_row("001"),
            self.make_row("001"),
            self.make_row("003", role="administrador"),
        ]
        response = self.client.post(
            reverse("usuarios:usuario_import"),
            {"archivo": self.make_csv(rows)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 usuarios creados exitosamente, 2 con errores")
        self.assertContains(response, "Fila 3: username repetido en fila 2")
        self.assertContains(response, "Fila 4: rol debe ser alumno o profesor")
        self.assertEqual(Usuario.objects.filter(username="alumno001").count(), 1)

    def test_imports_xlsx_files(self):
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(self.headers)
        worksheet.append(self.make_row("004"))
        content = BytesIO()
        workbook.save(content)
        response = self.client.post(
            reverse("usuarios:usuario_import"),
            {
                "archivo": SimpleUploadedFile(
                    "usuarios.xlsx",
                    content.getvalue(),
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 usuarios creados exitosamente, 0 con errores")
        self.assertTrue(Usuario.objects.filter(username="alumno004").exists())

    def test_import_requires_its_specific_permission(self):
        self.importer.permisos_directos.clear()

        response = self.client.get(reverse("usuarios:usuario_import"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    def test_import_rejects_files_missing_required_columns(self):
        response = self.client.post(
            reverse("usuarios:usuario_import"),
            {
                "archivo": SimpleUploadedFile(
                    "incompleto.csv",
                    b"username,email\nusuario,usuario@example.invalid\n",
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Faltan columnas requeridas")
        self.assertFalse(Usuario.objects.filter(username="usuario").exists())
