from io import BytesIO, StringIO
import csv

from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from eventos.models import Evento
from .forms import UsuarioUpdateForm
from .models import Perfil, Permiso, Usuario


class CambiarPasswordViewTests(TestCase):
    def setUp(self):
        self.usuario = Usuario(
            username="cambiar_password_usuario",
            email="cambiar-password@example.invalid",
            whatsapp="5550000000",
            grupo="A1",
        )
        self.usuario.set_password("password-original")
        self.usuario.save()
        permission, _ = Permiso.objects.get_or_create(
            tipo="usuario",
            codename="change_password",
        )
        self.usuario.permisos_directos.add(permission)
        self.client.force_login(self.usuario)

    def test_password_change_form_uses_styled_fields_and_visibility_toggles(self):
        response = self.client.get(reverse("usuarios:cambiar_password"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seguridad de la cuenta")
        self.assertContains(response, 'class="form-control"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertEqual(response.content.count(b"data-password-toggle"), 3)
        self.assertContains(response, "password-change-guidance")


class MiPerfilViewTests(TestCase):
    def setUp(self):
        usuario = Usuario.objects.create_superuser(
            username="perfil_ui_usuario",
            email="perfil-ui@example.invalid",
            password="test-password",
            nombre="Ana",
            apaterno="López",
            whatsapp="5550000000",
            grupo="1A",
        )
        self.client.force_login(usuario)

    def test_profile_form_renders_styled_fields_and_responsive_layout(self):
        response = self.client.get(reverse("usuarios:mi_perfil"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="profile-settings-page"')
        self.assertContains(response, 'class="profile-form-grid"')
        self.assertContains(response, 'class="form-control"')
        self.assertContains(response, 'autocomplete="given-name"')
        self.assertContains(response, 'autocomplete="email"')
        self.assertContains(response, 'type="tel"')
        self.assertContains(response, "Guardar cambios")


class PerfilManagementUiTests(TestCase):
    def setUp(self):
        admin = Usuario.objects.create_superuser(
            username="perfil_management_admin",
            email="perfil-management@example.invalid",
            password="test-password",
            whatsapp="",
            grupo="",
        )
        self.client.force_login(admin)

    def test_profile_catalog_summarizes_permissions_until_expanded(self):
        perfil = Perfil.objects.create(nombre="Coordinación")
        permisos = [
            Permiso.objects.create(
                tipo="academico",
                codename=f"permiso_{index}",
                nombre=f"Permiso {index}",
            )
            for index in range(5)
        ]
        perfil.permisos.add(*permisos)

        response = self.client.get(reverse("usuarios:perfil_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="glass-card role-card"')
        self.assertContains(response, "5 permisos")
        self.assertContains(response, "Ver los 2 permisos restantes")
        self.assertContains(response, 'class="role-permissions-details"')

    def test_profile_form_renders_searchable_permission_groups_and_retains_choices(self):
        perfil = Perfil.objects.create(nombre="Docente")
        permisos = [
            Permiso.objects.create(
                tipo=module,
                codename=f"ver_{module}",
                nombre=f"Consultar {module}",
            )
            for module in ("academico", "eventos")
        ]
        perfil.permisos.add(permisos[0])

        response = self.client.get(
            reverse("usuarios:perfil_update", kwargs={"pk": perfil.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="role-permission-search"')
        self.assertContains(response, 'id="role-permission-module"')
        self.assertContains(response, 'id="role-permission-selected-only"')
        self.assertContains(response, 'id="role-permission-groups"')
        self.assertContains(response, 'data-select-visible')
        self.assertContains(response, 'data-clear-visible')
        self.assertContains(response, "/static/js/perfil-permisos.js")
        self.assertContains(response, "academico.ver_academico")
        self.assertContains(response, "eventos.ver_eventos")
        self.assertGreaterEqual(response.content.count(b'type="checkbox"'), 2)


class UsuarioUpdatePasswordTests(TestCase):
    def setUp(self):
        self.usuario = Usuario(
            username="usuario_edicion",
            email="usuario-edicion@example.invalid",
            whatsapp="5550000000",
            grupo="A1",
        )
        self.usuario.set_password("password-original")
        self.usuario.save()

    def form_data(self, password):
        return {
            "username": self.usuario.username,
            "email": self.usuario.email,
            "password": password,
            "nombre": "",
            "apaterno": "",
            "amaterno": "",
            "categoria": "",
            "whatsapp": self.usuario.whatsapp,
            "grupo": self.usuario.grupo,
            "matricula": "",
            "activo": "on",
        }

    def test_blank_password_preserves_existing_password_when_updating_user(self):
        data = self.form_data("")
        data["nombre"] = "Nombre actualizado"
        form = UsuarioUpdateForm(data=data, instance=self.usuario)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, "Nombre actualizado")
        self.assertTrue(self.usuario.check_password("password-original"))
        self.assertNotEqual(self.usuario.password, "")

    def test_nonblank_password_replaces_existing_password(self):
        form = UsuarioUpdateForm(
            data=self.form_data("password-nuevo"),
            instance=self.usuario,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("password-nuevo"))
        self.assertFalse(self.usuario.check_password("password-original"))

    def test_update_form_assigns_direct_permissions_without_a_profile(self):
        permission = Permiso.objects.create(
            tipo="usuario_prueba",
            codename="permiso_directo_prueba",
            nombre="Permiso directo de prueba",
        )
        data = self.form_data("")
        data["permisos_directos"] = [str(permission.pk)]
        form = UsuarioUpdateForm(data=data, instance=self.usuario)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.usuario.refresh_from_db()
        self.assertTrue(
            self.usuario.permisos_directos.filter(pk=permission.pk).exists()
        )
        self.assertFalse(self.usuario.perfiles.exists())

    def test_update_form_removes_unchecked_direct_permissions(self):
        permission_to_remove = Permiso.objects.create(
            tipo="usuario_prueba",
            codename="permiso_directo_quitar",
            nombre="Permiso directo para quitar",
        )
        permission_to_keep = Permiso.objects.create(
            tipo="usuario_prueba",
            codename="permiso_directo_conservar",
            nombre="Permiso directo para conservar",
        )
        self.usuario.permisos_directos.add(
            permission_to_remove,
            permission_to_keep,
        )
        data = self.form_data("")
        data["permisos_directos"] = [str(permission_to_keep.pk)]
        form = UsuarioUpdateForm(data=data, instance=self.usuario)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.usuario.refresh_from_db()
        self.assertFalse(
            self.usuario.permisos_directos.filter(
                pk=permission_to_remove.pk
            ).exists()
        )
        self.assertTrue(
            self.usuario.permisos_directos.filter(
                pk=permission_to_keep.pk
            ).exists()
        )

    def test_successful_update_returns_to_edit_page_with_message_at_top(self):
        change_permission, _ = Permiso.objects.get_or_create(
            codename="change_usuario",
            defaults={"tipo": "usuario", "nombre": "Cambiar usuario"},
        )
        self.usuario.permisos_directos.add(change_permission)
        self.client.force_login(self.usuario)
        data = self.form_data("")
        data["nombre"] = "Nombre actualizado"
        data["permisos_directos"] = [str(change_permission.pk)]
        edit_url = reverse(
            "usuarios:usuario_update",
            kwargs={"pk": self.usuario.pk},
        )

        response = self.client.post(edit_url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(f"{edit_url}#messages", 302)],
        )
        self.assertContains(response, 'id="messages"')
        self.assertContains(response, "actualizado correctamente.")

    def test_edit_user_page_shows_filterable_direct_permissions_table(self):
        permission = Permiso.objects.create(
            tipo="asistencia_prueba",
            codename="permiso_directo_asignado",
            nombre="Permiso directo ya asignado",
        )
        available_permission = Permiso.objects.create(
            tipo="asistencia_prueba",
            codename="permiso_directo_disponible",
            nombre="Permiso directo disponible",
        )
        change_permission, _ = Permiso.objects.get_or_create(
            codename="change_usuario",
            defaults={"tipo": "usuario", "nombre": "Cambiar usuario"},
        )
        self.usuario.permisos_directos.add(permission, change_permission)
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse("usuarios:usuario_update", kwargs={"pk": self.usuario.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="filter-direct-permission-type"')
        self.assertContains(response, 'id="filter-direct-permission-query"')
        self.assertContains(response, 'id="apply-direct-permission-filters"')
        self.assertContains(response, available_permission.codename)
        self.assertContains(response, permission.codename)
        self.assertRegex(
            response.content.decode(),
            rf'name="permisos_directos"\s+value="{permission.pk}"\s+'
            r'class="direct-permission-checkbox"\s+checked',
        )
        self.assertContains(response, 'id="direct-permission-pagination"')

    def test_edit_user_page_shows_all_direct_permissions_and_paginates_by_six(self):
        change_permission, _ = Permiso.objects.get_or_create(
            codename="change_usuario",
            defaults={"tipo": "usuario", "nombre": "Cambiar usuario"},
        )
        self.usuario.permisos_directos.add(change_permission)
        for index in range(11):
            Permiso.objects.create(
                tipo="paginacion_prueba",
                codename=f"permiso_pagina_{index:02}",
                nombre=f"Permiso página {index}",
            )
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse("usuarios:usuario_update", kwargs={"pk": self.usuario.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["permisos"].filter(
                codename__startswith="permiso_pagina_"
            ).count(),
            11,
        )
        self.assertIn(
            change_permission,
            response.context["permisos"],
        )
        self.assertContains(response, 'id="direct-permission-next"')
        self.assertContains(response, "/static/js/usuario-permisos.js")


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

    def test_permission_list_filters_by_type_and_code_or_name(self):
        matching_permission = Permiso.objects.create(
            tipo="registro_filtro_test",
            codename="importar_asistentes_filtro_test",
            nombre="Importar asistentes de prueba",
        )
        Permiso.objects.create(
            tipo="usuario_filtro_test",
            codename="importar_usuarios_filtro_test",
            nombre="Importar usuarios de prueba",
        )

        response = self.client.get(
            reverse("usuarios:permiso_list"),
            {"tipo": "registro_filtro_test", "q": "asistentes"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching_permission.codename)
        self.assertNotContains(response, "importar_usuarios_filtro_test")
        self.assertEqual(response.context["selected_type"], "registro_filtro_test")
        self.assertEqual(
            response.context["pagination_query"],
            "tipo=registro_filtro_test&q=asistentes",
        )

    def test_permission_list_orders_results_by_id_ascending(self):
        first = Permiso.objects.create(
            tipo="orden_filtro_test",
            codename="z_primero",
            nombre="Primero por ID",
        )
        second = Permiso.objects.create(
            tipo="orden_filtro_test",
            codename="a_segundo",
            nombre="Segundo por ID",
        )

        response = self.client.get(
            reverse("usuarios:permiso_list"),
            {"tipo": "orden_filtro_test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [permission.pk for permission in response.context["permisos"]],
            [first.pk, second.pk],
        )

    def test_user_list_filters_by_group_category_status_and_search(self):
        matching = Usuario.objects.create_user(
            username="usuario_filtro_activo",
            email="usuario-filtro-activo@example.invalid",
            password="test-password",
            nombre="Ana Coincidente",
            matricula="USERFILTER-001",
            grupo="FILTRO-A",
            categoria="Estudiante",
            whatsapp="5550000001",
            activo=True,
        )
        excluded = Usuario.objects.create_user(
            username="usuario_filtro_inactivo",
            email="usuario-filtro-inactivo@example.invalid",
            password="test-password",
            nombre="Ana Coincidente",
            matricula="USERFILTER-002",
            grupo="FILTRO-B",
            categoria="Docente",
            whatsapp="5550000002",
            activo=False,
        )

        response = self.client.get(
            reverse("usuarios:usuario_list"),
            {
                "grupo": matching.grupo,
                "categoria": matching.categoria,
                "activo": "1",
                "q": matching.matricula,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.username)
        self.assertNotContains(response, excluded.username)
        self.assertEqual(
            response.context["pagination_query"],
            "grupo=FILTRO-A&categoria=Estudiante&activo=1&q=USERFILTER-001",
        )

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
