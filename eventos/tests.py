import csv
from io import BytesIO, StringIO

from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import json

from eventos.models import Evento, Registro, Asistencia
from usuarios.models import Perfil, Permiso, Usuario


class EventosScannerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Crear usuarios para pruebas de eventos
        cls.asistente = Usuario.objects.create_user(
            username="asistente_evento",
            email="asistente_evento@example.com",
            password="test-password",
            nombre="Juan",
            apaterno="Pérez",
            matricula="EVT-2026-001",
            grupo="TIC-71",
            activo=True,
        )

        cls.asistente_no_reg = Usuario.objects.create_user(
            username="asistente_no_reg",
            email="asistente_no_reg@example.com",
            password="test-password",
            nombre="María",
            apaterno="Gómez",
            matricula="EVT-2026-002",
            grupo="TIC-72",
            activo=True,
        )

        cls.staff_user = Usuario.objects.create_user(
            username="staff_cadenero",
            email="staff_cadenero@example.com",
            password="test-password",
            nombre="Carlos",
            apaterno="Staff",
            activo=True,
        )

        cls.user_sin_permiso = Usuario.objects.create_user(
            username="sin_permiso",
            email="sin_permiso@example.com",
            password="test-password",
            activo=True,
        )

        # Permiso de staff para registrar accesos a eventos
        perm_asistencia, _ = Permiso.objects.get_or_create(
            codename="add_asistencia",
            defaults={"tipo": "asistencia", "nombre": "Registrar nueva asistencia"},
        )
        cls.staff_user.permisos_directos.add(perm_asistencia)

        # Crear dos eventos: uno con pre-registro obligatorio y otro de acceso libre
        cls.evento_con_registro = Evento.objects.create(
            nombre="Hackathon PassID 2026",
            fecha_hora=timezone.now() + timezone.timedelta(days=1),
            lugar="Auditorio 1",
            requiere_registro=True,
            permitir_autorregistro=True,
            responsable_interno="Ing. Coordinador",
        )

        cls.evento_libre = Evento.objects.create(
            nombre="Feria de Ciencias",
            fecha_hora=timezone.now() + timezone.timedelta(days=2),
            lugar="Patio Central",
            requiere_registro=False,
            permitir_autorregistro=False,
        )

        # Pre-registrar al asistente en el evento con registro
        Registro.objects.create(
            evento=cls.evento_con_registro,
            usuario=cls.asistente,
            equipo="Los Linces",
        )

    # 1. Permisos y Vistas GET
    def test_lector_view_requires_permission(self):
        # Usuario no autenticado -> redirige a login
        response = self.client.get(reverse("eventos:lector"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

        # Usuario autenticado sin permiso de staff -> redirige a home
        self.client.force_login(self.user_sin_permiso)
        response = self.client.get(reverse("eventos:lector"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

        # Staff con permiso -> 200 OK
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("eventos:lector"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertIn(reverse("asistencia_qr:lector"), response.redirect_chain[0][0])
        self.assertContains(response, "Lector QR")
        self.assertEqual(response.context["scanner_mode"], "evento")

    def test_unified_lector_is_available_to_event_staff_without_class_permission(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("asistencia_qr:lector"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_scan_classes"])
        self.assertTrue(response.context["can_scan_events"])
        self.assertEqual(response.context["scanner_mode"], "evento")

    def test_lector_view_preselects_event(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("eventos:lector") + f"?evento={self.evento_con_registro.pk}",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_event"], self.evento_con_registro
        )
        self.assertEqual(response.context["scanner_mode"], "evento")

    def test_info_evento_api(self):
        self.client.force_login(self.staff_user)
        url = reverse("eventos:info_evento", kwargs={"pk": self.evento_con_registro.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["nombre"], "Hackathon PassID 2026")
        self.assertEqual(data["total_registrados"], 1)
        self.assertEqual(data["total_asistencias"], 0)
        self.assertTrue(data["requiere_registro"])

    # 2. Escaneo QR: Texto plano de credencial/matrícula
    def test_registrar_qr_texto_plano_matricula(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": self.asistente.matricula,
                "matricula": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["access_granted"])
        self.assertEqual(data["metodo"], "qr")
        self.assertEqual(data["asistente"]["matricula"], self.asistente.matricula)
        self.assertEqual(data["asistente"]["equipo"], "Los Linces")
        self.assertEqual(data["total_asistencias"], 1)

    # 3. Escaneo QR: JSON serializado en QR
    def test_registrar_qr_formato_json(self):
        self.client.force_login(self.staff_user)
        qr_json = json.dumps({"matricula": self.asistente.matricula, "evento_id": self.evento_con_registro.pk})
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": qr_json,
                "matricula": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    # 4. Escaneo QR: Token firmado digitalmente
    def test_registrar_qr_token_firmado(self):
        self.client.force_login(self.staff_user)
        token = signing.dumps({"matricula": self.asistente.matricula}, salt="eventos.acceso")
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": token,
                "matricula": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    # 5. Reglas de Negocio: Pre-registro obligatorio en eventos
    def test_acceso_denegado_sin_preregistro(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": self.asistente_no_reg.matricula,
                "matricula": "",
            },
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertFalse(data["access_granted"])
        self.assertEqual(data["reason"], "no_registro")
        self.assertIn("no cuenta con pre-registro", data["message"])
        self.assertFalse(
            Asistencia.objects.filter(
                evento=self.evento_con_registro, usuario=self.asistente_no_reg
            ).exists()
        )

    # 6. Prevención de acceso duplicado en eventos
    def test_prevencion_acceso_duplicado(self):
        self.client.force_login(self.staff_user)

        # Primer acceso al evento
        response1 = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": self.asistente.matricula,
                "matricula": "",
            },
        )
        self.assertEqual(response1.status_code, 200)

        # Segundo acceso al mismo evento (debe rechazar)
        response2 = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": self.asistente.matricula,
                "matricula": "",
            },
        )
        self.assertEqual(response2.status_code, 409)
        data = response2.json()
        self.assertFalse(data["ok"])
        self.assertTrue(data["duplicate"])
        self.assertIn("¡Acceso duplicado!", data["message"])
        self.assertEqual(
            Asistencia.objects.filter(
                evento=self.evento_con_registro, usuario=self.asistente
            ).count(),
            1,
        )

    # 7. Evento Libre (sin requerir pre-registro)
    def test_acceso_evento_libre_sin_preregistro(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_libre.pk,
                "token": self.asistente_no_reg.matricula,
                "matricula": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(
            Asistencia.objects.filter(
                evento=self.evento_libre, usuario=self.asistente_no_reg
            ).exists()
        )

    # 8. Captura manual por matrícula o username
    def test_registro_manual_por_matricula(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": "",
                "matricula": self.asistente.matricula,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["metodo"], "manual")
        self.assertTrue(
            Asistencia.objects.filter(
                evento=self.evento_con_registro, usuario=self.asistente
            ).exists()
        )

    def test_registro_manual_por_username(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_libre.pk,
                "token": "",
                "matricula": self.asistente_no_reg.username,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(
            Asistencia.objects.filter(
                evento=self.evento_libre, usuario=self.asistente_no_reg
            ).exists()
        )

    # 9. Registro en puerta desde el QR cuando no estaba pre-registrado
    def test_registro_en_puerta_desde_qr_autoriza_acceso(self):
        self.client.force_login(self.staff_user)
        self.assertFalse(
            Registro.objects.filter(
                evento=self.evento_con_registro, usuario=self.asistente_no_reg
            ).exists()
        )

        response = self.client.post(
            reverse("eventos:registrar_qr"),
            {
                "evento": self.evento_con_registro.pk,
                "token": self.asistente_no_reg.matricula,
                "matricula": "",
                "registrar_si_no_existe": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["access_granted"])
        self.assertTrue(data["registrado_en_puerta"])
        self.assertIn("Registrado en puerta", data["message"])

        # Verificar que se creó el registro y la asistencia en la BD
        self.assertTrue(
            Registro.objects.filter(
                evento=self.evento_con_registro, usuario=self.asistente_no_reg
            ).exists()
        )
        self.assertTrue(
            Asistencia.objects.filter(
                evento=self.evento_con_registro, usuario=self.asistente_no_reg
            ).exists()
        )

    # 10. Vista de imagen QR para auto-registro al evento
    def test_qr_registro_evento_imagen_view(self):
        self.client.force_login(self.staff_user)
        url = reverse("eventos:qr_registro_evento", kwargs={"pk": self.evento_con_registro.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(len(response.content) > 0)

    def _grant_registro_permission(self):
        permission, _ = Permiso.objects.get_or_create(
            codename="add_registro",
            defaults={"tipo": "registro", "nombre": "Registrar asistentes a eventos"},
        )
        bulk_permission, _ = Permiso.objects.get_or_create(
            codename="add_registro_masivo",
            defaults={
                "tipo": "registro",
                "nombre": "Importar registros de eventos de forma masiva",
            },
        )
        self.staff_user.permisos_directos.add(permission, bulk_permission)
        self.client.force_login(self.staff_user)

    def test_bulk_registration_permission_is_migrated_to_admin_profile(self):
        permission = Permiso.objects.get(
            tipo="registro",
            codename="add_registro_masivo",
        )
        admin = Perfil.objects.get(nombre__iexact="admin")

        self.assertTrue(admin.permisos.filter(pk=permission.pk).exists())

    def test_bulk_import_requires_its_specific_permission(self):
        create_permission, _ = Permiso.objects.get_or_create(
            codename="add_registro",
            defaults={"tipo": "registro", "nombre": "Agregar registro a evento"},
        )
        self.staff_user.permisos_directos.add(create_permission)
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("eventos:registro_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("eventos:registro_import"))
        self.assertEqual(
            self.client.get(reverse("eventos:registro_import")).url,
            reverse("home"),
        )
        self.assertEqual(
            self.client.get(reverse("eventos:registro_template")).url,
            reverse("home"),
        )

    def _grant_registro_view_permission(self):
        permission, _ = Permiso.objects.get_or_create(
            codename="view_registro",
            defaults={"tipo": "registro", "nombre": "Consultar registros de eventos"},
        )
        self.staff_user.permisos_directos.add(permission)
        self.client.force_login(self.staff_user)

    def _create_candidate(self, *, username, name, matricula, grupo, categoria):
        return Usuario.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="test-password",
            nombre=name,
            matricula=matricula,
            grupo=grupo,
            categoria=categoria,
            activo=True,
        )

    def make_registration_csv(self, rows, name="registros.csv"):
        content = StringIO()
        writer = csv.writer(content)
        writer.writerow(["evento", "matricula", "equipo"])
        writer.writerows(rows)
        return SimpleUploadedFile(name, content.getvalue().encode("utf-8"))

    def test_registration_create_shows_template_and_import_buttons(self):
        self._grant_registro_permission()
        response = self.client.get(
            reverse("eventos:registro_create"),
            {"evento": self.evento_con_registro.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("eventos:registro_template"))
        self.assertContains(response, reverse("eventos:registro_import"))

    def test_registration_selection_is_restored_after_changing_search(self):
        self._grant_registro_permission()
        selected = self._create_candidate(
            username="asistente_seleccionado",
            name="Ana Seleccionada",
            matricula="SELECCION-001",
            grupo="TIC-71",
            categoria="Estudiante",
        )
        current_result = self._create_candidate(
            username="asistente_busqueda_actual",
            name="Bruno Actual",
            matricula="SELECCION-002",
            grupo="TIC-72",
            categoria="Estudiante",
        )
        response = self.client.get(
            reverse("eventos:registro_create"),
            {
                "evento": self.evento_con_registro.pk,
                "grupo": current_result.grupo,
                "q": current_result.nombre,
                "seleccionados": [str(selected.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["usuarios_seleccionados_fuera_filtro"]),
            [selected],
        )
        self.assertContains(response, f'value="{selected.pk}" checked')
        self.assertContains(response, current_result.nombre)

    def test_registration_post_saves_selected_users_across_different_filters(self):
        self._grant_registro_permission()
        selected = [
            self._create_candidate(
                username="asistente_filtro_a",
                name="Ana Grupo A",
                matricula="MULTIFILTER-001",
                grupo="TIC-71",
                categoria="Estudiante",
            ),
            self._create_candidate(
                username="asistente_filtro_b",
                name="Bruno Grupo B",
                matricula="MULTIFILTER-002",
                grupo="TIC-72",
                categoria="Estudiante",
            ),
        ]
        response = self.client.post(
            reverse("eventos:registro_create"),
            {
                "evento": self.evento_con_registro.pk,
                "grupo": selected[1].grupo,
                "q": selected[1].nombre,
                "usuarios": [str(usuario.pk) for usuario in selected],
                "equipo": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Registro.objects.filter(
                evento=self.evento_con_registro,
                usuario__in=selected,
            ).count(),
            2,
        )

    def test_registration_list_filters_by_event_group_category_and_name(self):
        self._grant_registro_view_permission()
        matching = self._create_candidate(
            username="registro_coincidente",
            name="Ana Coincidente",
            matricula="LISTFILTER-001",
            grupo="TIC-71",
            categoria="Estudiante",
        )
        excluded = self._create_candidate(
            username="registro_excluido",
            name="Bruno Excluido",
            matricula="LISTFILTER-002",
            grupo="TIC-72",
            categoria="Docente",
        )
        Registro.objects.create(evento=self.evento_con_registro, usuario=matching)
        Registro.objects.create(evento=self.evento_con_registro, usuario=excluded)

        response = self.client.get(
            reverse("eventos:registro_list"),
            {
                "evento": self.evento_con_registro.pk,
                "grupo": "TIC-71",
                "categoria": "Estudiante",
                "q": "LISTFILTER-001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.nombre)
        self.assertNotContains(response, excluded.nombre)
        self.assertContains(response, 'name="evento"')
        self.assertContains(response, 'name="grupo"')
        self.assertContains(response, 'name="categoria"')

    def test_registration_list_pagination_preserves_active_filters(self):
        self._grant_registro_view_permission()
        for index in range(11):
            usuario = self._create_candidate(
                username=f"registro_paginado_{index}",
                name=f"Usuario página {index}",
                matricula=f"PAGE-{index:03d}",
                grupo="TIC-PAGE",
                categoria="Estudiante",
            )
            Registro.objects.create(
                evento=self.evento_con_registro,
                usuario=usuario,
            )

        response = self.client.get(
            reverse("eventos:registro_list"),
            {
                "evento": self.evento_con_registro.pk,
                "grupo": "TIC-PAGE",
                "categoria": "Estudiante",
                "q": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(
            response.context["pagination_query"],
            f"evento={self.evento_con_registro.pk}&grupo=TIC-PAGE&categoria=Estudiante",
        )

    def test_registration_template_download_has_expected_columns(self):
        from openpyxl import load_workbook

        self._grant_registro_permission()
        response = self.client.get(reverse("eventos:registro_template"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("plantilla_registros_eventos.xlsx", response["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.content), read_only=True, data_only=True)
        self.assertEqual(
            list(workbook["Registros"].values)[0],
            ("evento", "matricula", "equipo"),
        )
        self.assertIn("Eventos disponibles", workbook.sheetnames)
        self.assertIn("Instrucciones", workbook.sheetnames)
        event_rows = list(workbook["Eventos disponibles"].values)
        self.assertIn(
            self.evento_con_registro.nombre,
            [row[0] for row in event_rows[1:]],
        )
        workbook.close()

    def test_import_registers_users_from_xlsx(self):
        from openpyxl import Workbook

        self._grant_registro_permission()
        evento = Evento.objects.create(
            nombre="Exposición Técnica",
            fecha_hora=timezone.now() + timezone.timedelta(days=3),
            lugar="Auditorio 2",
        )
        candidate = self._create_candidate(
            username="asistente_importado_excel",
            name="Asistente Excel",
            matricula="IMPORT-EXCEL",
            grupo="TIC-71",
            categoria="Estudiante",
        )
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["evento", "matricula", "equipo"])
        worksheet.append([
            "  EXPOSICION   TECNICA ",
            candidate.matricula,
            "Equipo Excel",
        ])
        content = BytesIO()
        workbook.save(content)
        response = self.client.post(
            reverse("eventos:registro_import"),
            {
                "archivo": SimpleUploadedFile(
                    "registros.xlsx",
                    content.getvalue(),
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["report"]["created_count"], 1)
        self.assertEqual(
            Registro.objects.get(
                evento=evento,
                usuario=candidate,
            ).equipo,
            "Equipo Excel",
        )

    def test_import_registers_multiple_users_and_skips_existing_records(self):
        self._grant_registro_permission()
        asistentes = [
            self._create_candidate(
                username=f"asistente_importado_{index}",
                name=f"Asistente importado {index}",
                matricula=f"IMPORT-{index}",
                grupo="TIC-71",
                categoria="Estudiante",
            )
            for index in range(1, 3)
        ]
        response = self.client.post(
            reverse("eventos:registro_import"),
            {
                "archivo": self.make_registration_csv([
                    [self.evento_con_registro.nombre, asistentes[0].matricula, "Equipo A"],
                    [self.evento_libre.nombre, asistentes[1].matricula, ""],
                    [self.evento_con_registro.nombre, self.asistente.matricula, "Los Linces"],
                ]),
            },
        )

        self.assertEqual(response.status_code, 200)
        report = response.context["report"]
        self.assertEqual(report["created_count"], 2)
        self.assertEqual(report["skipped_count"], 1)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(
            Registro.objects.get(
                evento=self.evento_con_registro,
                usuario=asistentes[0],
            ).equipo,
            "Equipo A",
        )
        self.assertTrue(
            Registro.objects.filter(
                evento=self.evento_libre,
                usuario=asistentes[1],
            ).exists()
        )

    def test_import_reports_unknown_repeated_and_ambiguous_values(self):
        self._grant_registro_permission()
        Evento.objects.create(
            nombre="HÁCKATHON PASSID 2026",
            fecha_hora=timezone.now() + timezone.timedelta(days=4),
            lugar="Auditorio 3",
        )
        candidate = self._create_candidate(
            username="asistente_importado_valido",
            name="Asistente válido",
            matricula="IMPORT-VALIDO",
            grupo="TIC-71",
            categoria="Estudiante",
        )
        response = self.client.post(
            reverse("eventos:registro_import"),
            {
                "archivo": self.make_registration_csv([
                    [self.evento_libre.nombre, candidate.matricula, ""],
                    [self.evento_libre.nombre, "NO-EXISTE", ""],
                    [self.evento_libre.nombre, candidate.matricula, ""],
                    ["EVENTO NO REGISTRADO", candidate.matricula, ""],
                    ["hackathon   passid 2026", candidate.matricula, ""],
                ]),
            },
        )

        self.assertEqual(response.status_code, 200)
        report = response.context["report"]
        self.assertEqual(report["created_count"], 1)
        self.assertEqual(report["error_count"], 4)
        self.assertContains(response, "matricula no encontrada")
        self.assertContains(response, "evento y matricula repetidos en fila 2")
        self.assertContains(response, "evento no encontrado por nombre")
        self.assertContains(response, "nombre de evento ambiguo")