from io import BytesIO
import pymysql
from unittest.mock import MagicMock, patch
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Perfil, Permiso, Usuario
from .models import Aula, Carrera, Horario, Inscripcion, Materia, ProfesorDisponibilidad


class InscripcionImportTests(TestCase):
    def setUp(self):
        self.alumno = Usuario.objects.create_user(
            username="alumno_carga_masiva",
            email="alumno-carga-masiva@example.invalid",
            password="test-password",
            matricula="MAT-ALUMNO-01",
            whatsapp="",
            grupo="A",
        )
        carrera = Carrera.objects.create(clave="CARGA", nombre="Carrera de carga")
        self.materia_a = Materia.objects.create(
            clave="CARGA-01",
            nombre="Materia de carga 1",
            carrera=carrera,
        )
        self.materia_b = Materia.objects.create(
            clave="CARGA-02",
            nombre="Materia de carga 2",
            carrera=carrera,
        )

    def test_csv_import_creates_many_enrollments_skips_existing_and_reports_errors(self):
        Inscripcion.objects.create(
            usuario=self.alumno,
            materia=self.materia_b,
            grupo="A",
            periodo="2026-3",
            activa=False,
        )
        archivo = SimpleUploadedFile(
            "inscripciones.csv",
            (
                "matricula,clave_materia,grupo,periodo,activa\n"
                "MAT-ALUMNO-01,CARGA-01,A,2026-3,si\n"
                "MAT-ALUMNO-01,CARGA-02,A,2026-3,si\n"
                "MAT-ALUMNO-01,NO-EXISTE,A,2026-3,si\n"
            ).encode("utf-8"),
        )

        from .importacion_inscripciones import import_inscripciones
        report = import_inscripciones(archivo)

        self.assertEqual(report["created_count"], 1)
        self.assertEqual(report["skipped_count"], 1)
        self.assertEqual(report["error_count"], 1)
        self.assertEqual(Inscripcion.objects.count(), 2)
        self.assertFalse(
            Inscripcion.objects.get(materia=self.materia_b).activa
        )

    def test_xlsx_import_accepts_boolean_and_creates_enrollment(self):
        from openpyxl import Workbook
        from .importacion_inscripciones import import_inscripciones

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["matricula", "clave_materia", "grupo", "periodo", "activa"])
        worksheet.append(["MAT-ALUMNO-01", "CARGA-01", "A", "2026-3", True])
        content = BytesIO()
        workbook.save(content)
        archivo = SimpleUploadedFile(
            "inscripciones.xlsx",
            content.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        report = import_inscripciones(archivo)

        self.assertEqual(report["created_count"], 1)
        self.assertTrue(
            Inscripcion.objects.get(materia=self.materia_a).activa
        )

    def test_inscripcion_list_exposes_bulk_import_and_csv_template_actions(self):
        admin = Usuario.objects.create_superuser(
            username="admin_carga_masiva",
            email="admin-carga-masiva@example.invalid",
            password="test-password",
            whatsapp="",
            grupo="",
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("academico:inscripcion_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("academico:inscripcion_import"))
        self.assertContains(response, reverse("academico:inscripcion_template"))


class AcademicCatalogFilterTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username="catalog_admin",
            email="catalog-admin@example.com",
            password="test-password",
            nombre="Carlos",
            apaterno="Garcia",
            amaterno="Lopez",
            whatsapp="",
            grupo="",
        )
        self.client.force_login(self.admin)

    def test_career_catalog_filters_by_text_and_status(self):
        active = Carrera.objects.create(
            clave="SIS",
            nombre="Ingeniería en Sistemas",
            activa=True,
        )
        inactive = Carrera.objects.create(
            clave="SIS-OLD",
            nombre="Sistemas anteriores",
            activa=False,
        )

        response = self.client.get(
            reverse("academico:carrera_list"),
            {"q": "SIS", "activa": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["carreras"]), [active])
        self.assertEqual(response.context["pagination_query"], "q=SIS&activa=1")
        self.assertContains(response, 'id="filter-carrera-activa"')
        self.assertNotContains(response, inactive.clave)

        response = self.client.get(
            reverse("academico:carrera_list"),
            {"q": "sisold", "activa": "0"},
        )

        self.assertEqual(list(response.context["carreras"]), [inactive])

    def test_classroom_catalog_filters_by_type_and_status(self):
        active_lab = Aula.objects.create(
            codigo="LAB-01",
            tipo="laboratorio",
            activa=True,
        )
        Aula.objects.create(
            codigo="LAB-02",
            tipo="laboratorio",
            activa=False,
        )
        Aula.objects.create(
            codigo="AULA-01",
            tipo="aula",
            activa=True,
        )

        response = self.client.get(
            reverse("academico:aula_list"),
            {"tipo": "laboratorio", "activa": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["aulas"]), [active_lab])
        self.assertContains(response, 'id="filter-aula-tipo"')
        self.assertEqual(
            response.context["pagination_query"],
            "tipo=laboratorio&activa=1",
        )

        response = self.client.get(
            reverse("academico:aula_list"),
            {"q": "lab01", "activa": "1"},
        )

        self.assertEqual(list(response.context["aulas"]), [active_lab])

    def test_subject_catalog_filters_by_career_period_and_status(self):
        carrera = Carrera.objects.create(
            clave="COM",
            nombre="Ciencias Aplicadas",
        )
        matching = Materia.objects.create(
            clave="PROG-1",
            nombre="Programación I",
            periodo="2026-3",
            carrera=carrera,
            activa=True,
        )
        Materia.objects.create(
            clave="PROG-2",
            nombre="Programación II",
            periodo="2026-3",
            carrera=carrera,
            activa=False,
        )
        Materia.objects.create(
            clave="RED-1",
            nombre="Redes",
            periodo="2026-3",
            activa=True,
        )

        response = self.client.get(
            reverse("academico:materia_list"),
            {
                "q": "cienciasaplicadas",
                "periodo": "2026-3",
                "activa": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["materias"]), [matching])
        self.assertNotContains(response, 'id="filter-materia-carrera"')
        self.assertEqual(
            response.context["pagination_query"],
            "q=cienciasaplicadas&periodo=2026-3&activa=1",
        )

        response = self.client.get(
            reverse("academico:materia_list"),
            {"q": "com", "activa": "1"},
        )

        self.assertEqual(list(response.context["materias"]), [matching])

        response = self.client.get(
            reverse("academico:materia_list"),
            {"q": "prog1", "activa": "1"},
        )

        self.assertEqual(list(response.context["materias"]), [matching])

    def test_schedule_catalog_filters_by_group_day_period_and_status(self):
        materia = Materia.objects.create(
            clave="MAT-1",
            nombre="Matemáticas",
        )
        aula = Aula.objects.create(codigo="LAB-X")
        matching = Horario.objects.create(
            materia=materia,
            profesor=self.admin,
            aula=aula,
            grupo="Grupo-A",
            dia_semana="lunes",
            hora_inicio="09:00",
            hora_fin="10:00",
            periodo="2026-3",
            activo=True,
        )
        other_group = Horario.objects.create(
            materia=materia,
            profesor=self.admin,
            aula=aula,
            grupo="Grupo-B",
            dia_semana="lunes",
            hora_inicio="10:00",
            hora_fin="11:00",
            periodo="2026-3",
            activo=True,
        )
        Horario.objects.create(
            materia=materia,
            profesor=self.admin,
            aula=aula,
            grupo="Grupo-A",
            dia_semana="lunes",
            hora_inicio="11:00",
            hora_fin="12:00",
            periodo="2026-3",
            activo=False,
        )

        response = self.client.get(
            reverse("academico:horario_list"),
            {
                "q": "  gRuPo-A  ",
                "dia": "lunes",
                "periodo": "2026-3",
                "activo": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["horarios"]), [matching])
        self.assertContains(response, 'id="filter-horario-dia"')
        self.assertNotContains(response, 'id="filter-horario-materia"')
        self.assertNotContains(response, 'id="filter-horario-profesor"')
        self.assertNotContains(response, 'id="filter-horario-aula"')
        self.assertNotContains(response, 'id="filter-horario-grupo"')
        self.assertEqual(
            response.context["pagination_query"],
            "q=gRuPo-A&dia=lunes&periodo=2026-3&activo=1",
        )

        response = self.client.get(
            reverse("academico:horario_list"),
            {"q": "  cArLoS   gArCiA "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["horarios"].count(), 3)

        for apellido in ("garcia", "LOPEZ"):
            with self.subTest(apellido=apellido):
                response = self.client.get(
                    reverse("academico:horario_list"),
                    {"q": apellido},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["horarios"].count(), 3)

        response = self.client.get(
            reverse("academico:horario_list"),
            {"q": "labx", "activo": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["horarios"]),
            [matching, other_group],
        )

        response = self.client.get(
            reverse("academico:horario_list"),
            {"q": "grupo a", "activo": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["horarios"]), [matching])

        response = self.client.get(
            reverse("academico:horario_list"),
            {"q": "mat-1", "activo": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["horarios"].count(), 2)

    def test_enrollment_catalog_combines_search_and_normalizes_terms(self):
        materia = Materia.objects.create(
            clave="MAT-2",
            nombre="Física",
        )
        alumno = Usuario.objects.create_user(
            username="alumno_catalogo",
            email="alumno-catalogo@example.com",
            password="test-password",
            nombre="Ana",
            apaterno="Estudiante",
            matricula="2026-AB",
            whatsapp="",
            grupo="",
        )
        otro_alumno = Usuario.objects.create_user(
            username="alumno_inactivo_catalogo",
            email="alumno-inactivo-catalogo@example.com",
            password="test-password",
            nombre="Ana",
            apaterno="Inactiva",
            whatsapp="",
            grupo="",
        )
        matching = Inscripcion.objects.create(
            usuario=alumno,
            materia=materia,
            grupo="Grupo-A",
            periodo="2026-3",
            activa=True,
        )
        Inscripcion.objects.create(
            usuario=otro_alumno,
            materia=materia,
            grupo="Grupo-A",
            periodo="2026-3",
            activa=False,
        )
        other_group = Inscripcion.objects.create(
            usuario=alumno,
            materia=materia,
            grupo="Grupo-B",
            periodo="2026-3",
            activa=True,
        )

        response = self.client.get(
            reverse("academico:inscripcion_list"),
            {
                "q": "  aNa   estuDIAnte ",
                "periodo": "2026-3",
                "activa": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["inscripciones"].values_list("pk", flat=True)),
            {matching.pk, other_group.pk},
        )
        self.assertNotContains(response, 'id="filter-inscripcion-materia"')
        self.assertNotContains(response, 'id="filter-inscripcion-grupo"')
        self.assertEqual(
            response.context["pagination_query"],
            "q=aNa+++estuDIAnte&periodo=2026-3&activa=1",
        )

        for search in ("grupo a", "mat2", "2026ab", "ESTUDIANTE"):
            with self.subTest(search=search):
                response = self.client.get(
                    reverse("academico:inscripcion_list"),
                    {"q": search, "activa": "1"},
                )
                self.assertEqual(response.status_code, 200)
                expected_count = 1 if search == "grupo a" else 2
                self.assertEqual(
                    response.context["inscripciones"].count(),
                    expected_count,
                )


class DisponibilidadDocenteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        permiso, _ = Permiso.objects.get_or_create(
            codename="manage_disponibilidad",
            defaults={
                "tipo": "horario",
                "nombre": "Gestionar disponibilidad de horarios",
            },
        )
        perfil_profesor, _ = Perfil.objects.get_or_create(nombre="profesor")

        cls.profesor = cls.crear_usuario("profesor")
        cls.otro_profesor = cls.crear_usuario("otro_profesor")
        cls.admin = cls.crear_usuario("admin", is_superuser=True)
        cls.usuario_sin_permiso = cls.crear_usuario("sin_permiso")

        for profesor in (cls.profesor, cls.otro_profesor):
            profesor.perfiles.add(perfil_profesor)
            profesor.permisos_directos.add(permiso)

    @staticmethod
    def crear_usuario(username, is_superuser=False):
        return Usuario.objects.create(
            username=username,
            password=make_password("Prueba-segura-123"),
            email=f"{username}@example.com",
            nombre=username.replace("_", " ").title(),
            whatsapp="",
            grupo="",
            activo=True,
            is_superuser=is_superuser,
        )

    def setUp(self):
        self.url = reverse("academico:disponibilidad_docente")

    def datos_bloque(self, **overrides):
        datos = {
            "dia_semana": "lunes",
            "hora_inicio": "09:00",
            "hora_fin": "11:00",
            "periodo": "2026-3",
            "tipo": "disponible",
            "notas": "",
        }
        datos.update(overrides)
        return datos

    def test_teacher_sees_weekly_matrix_and_only_own_blocks(self):
        ProfesorDisponibilidad.objects.create(
            profesor=self.profesor,
            dia_semana="lunes",
            hora_inicio="09:00",
            hora_fin="11:00",
            periodo="2026-3",
            tipo="disponible",
        )
        ProfesorDisponibilidad.objects.create(
            profesor=self.otro_profesor,
            dia_semana="martes",
            hora_inicio="12:00",
            hora_fin="13:00",
            periodo="2026-3",
            tipo="no_disponible",
        )
        self.client.force_login(self.profesor)

        response = self.client.get(self.url, {"periodo": "2026-3"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["dias"]), 6)
        self.assertEqual(
            [
                bloque.profesor_id
                for bloque in response.context["dias"][0]["bloques"]
            ],
            [self.profesor.pk],
        )
        self.assertContains(response, "09:00")
        self.assertNotContains(response, "12:00")
        self.assertContains(response, "Mi disponibilidad")
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, "Agregar una nota (opcional)")
        self.assertContains(
            response,
            f'?periodo=2026-3&amp;dia=lunes#availability-add-title',
        )
        self.assertIn("2026-3", response.context["periodos"])

    def test_teacher_can_add_available_and_unavailable_blocks(self):
        self.client.force_login(self.profesor)

        for tipo in ("disponible", "no_disponible"):
            with self.subTest(tipo=tipo):
                response = self.client.post(
                    self.url,
                    self.datos_bloque(
                        dia_semana="martes" if tipo == "no_disponible" else "lunes",
                        tipo=tipo,
                    ),
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("availability-add-title", response.url)
                self.assertIn(
                    "dia=martes" if tipo == "no_disponible" else "dia=lunes",
                    response.url,
                )

        self.assertEqual(
            ProfesorDisponibilidad.objects.filter(profesor=self.profesor).count(),
            2,
        )
        self.assertFalse(
            ProfesorDisponibilidad.objects.filter(profesor=self.otro_profesor).exists()
        )

    def test_overlapping_blocks_are_rejected(self):
        ProfesorDisponibilidad.objects.create(
            profesor=self.profesor,
            dia_semana="lunes",
            hora_inicio="09:00",
            hora_fin="11:00",
            periodo="2026-3",
            tipo="disponible",
        )
        self.client.force_login(self.profesor)

        response = self.client.post(
            self.url,
            self.datos_bloque(hora_inicio="10:00", hora_fin="12:00"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "se cruza con el bloque del Lunes")
        self.assertContains(response, "09:00 a 11:00")
        self.assertEqual(
            ProfesorDisponibilidad.objects.filter(profesor=self.profesor).count(),
            1,
        )

    def test_teacher_cannot_add_block_for_another_professor(self):
        self.client.force_login(self.profesor)

        response = self.client.post(
            self.url,
            self.datos_bloque(profesor_id=self.otro_profesor.pk),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProfesorDisponibilidad.objects.filter(profesor=self.profesor).exists()
        )
        self.assertFalse(
            ProfesorDisponibilidad.objects.filter(profesor=self.otro_profesor).exists()
        )

    def test_admin_can_select_and_modify_another_teacher(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            self.url,
            {"profesor_id": self.otro_profesor.pk, "periodo": "2026-3"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["profesor_seleccionado"],
            self.otro_profesor,
        )

        response = self.client.post(
            self.url,
            {
                **self.datos_bloque(),
                "profesor_id": self.otro_profesor.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProfesorDisponibilidad.objects.filter(
                profesor=self.otro_profesor,
                periodo="2026-3",
            ).exists()
        )


    def test_admin_day_shortcut_keeps_selected_admin_account(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            self.url,
            {
                "profesor_id": self.admin.pk,
                "periodo": "2026-3",
                "dia": "lunes",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["profesor_seleccionado"],
            self.admin,
        )

    def test_admin_can_create_a_new_period_from_filter(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            self.url,
            {
                "profesor_id": self.otro_profesor.pk,
                "periodo": "__nuevo__",
                "nuevo_periodo": "2027-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["periodo"], "2027-1")

        response = self.client.post(
            self.url,
            {
                **self.datos_bloque(periodo="2027-1"),
                "profesor_id": self.otro_profesor.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProfesorDisponibilidad.objects.filter(
                profesor=self.otro_profesor,
                periodo="2027-1",
            ).exists()
        )

    def test_teacher_can_delete_only_own_block(self):
        bloque = ProfesorDisponibilidad.objects.create(
            profesor=self.profesor,
            dia_semana="lunes",
            hora_inicio="09:00",
            hora_fin="11:00",
            periodo="2026-3",
            tipo="disponible",
        )
        self.client.force_login(self.profesor)

        response = self.client.post(
            self.url,
            {
                "accion": "eliminar",
                "disponibilidad_id": bloque.pk,
                "periodo": "2026-3",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ProfesorDisponibilidad.objects.filter(pk=bloque.pk).exists()
        )

    def test_teacher_cannot_delete_another_professors_block(self):
        bloque = ProfesorDisponibilidad.objects.create(
            profesor=self.otro_profesor,
            dia_semana="lunes",
            hora_inicio="09:00",
            hora_fin="11:00",
            periodo="2026-3",
            tipo="disponible",
        )
        self.client.force_login(self.profesor)

        response = self.client.post(
            self.url,
            {
                "accion": "eliminar",
                "disponibilidad_id": bloque.pk,
                "periodo": "2026-3",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            ProfesorDisponibilidad.objects.filter(pk=bloque.pk).exists()
        )

    def test_user_without_permission_cannot_manage_availability(self):
        self.client.force_login(self.usuario_sin_permiso)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    def test_day_shortcut_prefills_day_and_period_in_add_form(self):
        self.client.force_login(self.profesor)

        response = self.client.get(
            self.url,
            {"periodo": "2026-3", "dia": "miercoles"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["dia_semana"].value(), "miercoles")
        self.assertEqual(response.context["form"]["periodo"].value(), "2026-3")
        self.assertContains(response, "Agregar bloque")

    def test_new_period_controls_start_collapsed_when_periods_exist(self):
        ProfesorDisponibilidad.objects.create(
            profesor=self.profesor,
            dia_semana="lunes",
            hora_inicio="09:00",
            hora_fin="11:00",
            periodo="2026-3",
            tipo="disponible",
        )
        self.client.force_login(self.profesor)

        response = self.client.get(self.url, {"periodo": "2026-3"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["periodo_nuevo_activo"])
        self.assertNotContains(response, '<details class="availability-new-period" id="availability-new-period" open>')

    def test_day_shortcut_without_period_opens_new_period_flow(self):
        self.client.force_login(self.profesor)

        response = self.client.get(
            self.url,
            {"periodo": "__nuevo__", "dia": "lunes"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["periodo_nuevo_activo"])
        self.assertContains(response, "¿No aparece? Crear un período")
        self.assertContains(response, "periodo=__nuevo__&amp;dia=lunes")


class ImportarCatalogosLegacyCommandTests(TestCase):
    def setUp(self):
        self.mock_legacy_data = {
            "carrera": [
                {
                    "id": 10,
                    "clave": "ISC-LEG",
                    "nombre": "Ingenieria en Sistemas Computacionales",
                    "activa": 1,
                },
                {
                    "id": 20,
                    "clave": "ADM-LEG",
                    "nombre": "Licenciatura en Administracion",
                    "activa": 1,
                },
            ],
            "aula": [
                {
                    "id": 101,
                    "codigo": "LAB-LEG-1",
                    "edificio": "Edificio Central",
                    "capacidad": 25,
                    "tipo": "laboratorio",
                    "activa": 1,
                },
                {
                    "id": 102,
                    "codigo": "AUD-LEG-1",
                    "edificio": "Auditorio B",
                    "capacidad": 150,
                    "tipo": "auditorio",
                    "activa": 1,
                },
            ],
            "materia": [
                {
                    "id": 501,
                    "clave": "MAT-LEG-101",
                    "nombre": "Algoritmos y Estructuras",
                    "asistencias": 32,
                    "horas_semana": 5,
                    "periodo": "2026-2",
                    "carrera_id": 10,
                    "activa": 1,
                },
                {
                    "id": 502,
                    "clave": "MAT-LEG-102",
                    "nombre": "Contabilidad Basica",
                    "asistencias": 20,
                    "horas_semana": 3,
                    "periodo": "2026-2",
                    "carrera_id": 20,
                    "activa": 1,
                },
            ],
            "evento": [
                {
                    "id": 901,
                    "nombre": "Congreso de Ingenieria 2026",
                    "fecha_hora": "2026-10-15 10:00:00",
                    "lugar": "Auditorio Principal",
                    "requiere_registro": 1,
                    "permitir_autorregistro": 1,
                    "responsable_interno": "Dr. Mario Gomez",
                    "responsable_externo": "Lic. Ana Diaz",
                }
            ],
        }

    def _setup_mock_connection(self, mock_pymysql_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        def mock_execute(sql, *args, **kwargs):
            sql_upper = sql.strip().upper()
            if "FROM CARRERA" in sql_upper:
                mock_cursor.fetchall.return_value = list(self.mock_legacy_data["carrera"])
            elif "FROM AULA" in sql_upper:
                mock_cursor.fetchall.return_value = list(self.mock_legacy_data["aula"])
            elif "FROM MATERIA" in sql_upper:
                mock_cursor.fetchall.return_value = list(self.mock_legacy_data["materia"])
            elif "FROM EVENTO" in sql_upper:
                mock_cursor.fetchall.return_value = list(self.mock_legacy_data["evento"])
            else:
                mock_cursor.fetchall.return_value = []

        mock_cursor.execute.side_effect = mock_execute
        mock_pymysql_connect.return_value = mock_conn
        return mock_conn, mock_cursor

    @patch("academico.management.commands.importar_catalogos_legacy.pymysql.connect")
    def test_dry_run_previews_without_saving_changes(self, mock_connect):
        from eventos.models import Evento
        from django.core.management import call_command
        from io import StringIO

        self._setup_mock_connection(mock_connect)
        out = StringIO()

        carreras_antes = Carrera.objects.count()
        aulas_antes = Aula.objects.count()
        materias_antes = Materia.objects.count()
        eventos_antes = Evento.objects.count()

        call_command("importar_catalogos_legacy", dry_run=True, stdout=out)
        salida = out.getvalue()

        self.assertIn("[MODO DRY-RUN ACTIVO]", salida)
        self.assertIn("DRY-RUN EXITOSO", salida)
        self.assertIn("Tablas deliberadamente omitidas", salida)
        self.assertIn("Carrera 'ISC-LEG'", salida)
        self.assertIn("Aula 'LAB-LEG-1'", salida)
        self.assertIn("Materia 'MAT-LEG-101'", salida)
        self.assertIn("Evento 'Congreso de Ingenieria 2026'", salida)

        # Verificar que no se guardo nada en la base de datos
        self.assertEqual(Carrera.objects.count(), carreras_antes)
        self.assertEqual(Aula.objects.count(), aulas_antes)
        self.assertEqual(Materia.objects.count(), materias_antes)
        self.assertEqual(Evento.objects.count(), eventos_antes)

    @patch("academico.management.commands.importar_catalogos_legacy.pymysql.connect")
    def test_importar_catalogos_exitoso_y_vinculacion_carrera(self, mock_connect):
        from eventos.models import Evento
        from django.core.management import call_command
        from io import StringIO

        self._setup_mock_connection(mock_connect)
        out = StringIO()

        call_command("importar_catalogos_legacy", stdout=out)
        salida = out.getvalue()

        self.assertIn("[IMPORTACION EXITOSA]", salida)

        # 1. Verificar carrera
        carrera_isc = Carrera.objects.get(clave="ISC-LEG")
        self.assertEqual(carrera_isc.nombre, "Ingenieria en Sistemas Computacionales")
        self.assertTrue(carrera_isc.activa)

        carrera_adm = Carrera.objects.get(clave="ADM-LEG")
        self.assertEqual(carrera_adm.nombre, "Licenciatura en Administracion")

        # 2. Verificar aula
        aula_lab = Aula.objects.get(codigo="LAB-LEG-1")
        self.assertEqual(aula_lab.tipo, "laboratorio")
        self.assertEqual(aula_lab.capacidad, 25)

        # 3. Verificar materia con FK a carrera
        materia_alg = Materia.objects.get(clave="MAT-LEG-101")
        self.assertEqual(materia_alg.nombre, "Algoritmos y Estructuras")
        self.assertEqual(materia_alg.carrera, carrera_isc)
        self.assertEqual(materia_alg.asistencias, 32)
        self.assertEqual(materia_alg.horas_semana, 5)

        materia_cont = Materia.objects.get(clave="MAT-LEG-102")
        self.assertEqual(materia_cont.carrera, carrera_adm)

        # 4. Verificar evento general
        evento = Evento.objects.get(nombre="Congreso de Ingenieria 2026")
        self.assertEqual(evento.lugar, "Auditorio Principal")
        self.assertEqual(evento.responsable_interno, "Dr. Mario Gomez")
        self.assertEqual(evento.responsable_externo, "Lic. Ana Diaz")
        self.assertTrue(evento.requiere_registro)
        self.assertTrue(evento.permitir_autorregistro)

    @patch("academico.management.commands.importar_catalogos_legacy.pymysql.connect")
    def test_actualizar_registros_existentes(self, mock_connect):
        from django.core.management import call_command
        from io import StringIO

        # Crear registros preexistentes
        carrera = Carrera.objects.create(
            clave="ISC-LEG",
            nombre="Nombre Antiguo",
            activa=False,
        )
        aula = Aula.objects.create(
            codigo="LAB-LEG-1",
            edificio="Antiguo",
            capacidad=10,
            tipo="aula",
            activa=False,
        )

        self._setup_mock_connection(mock_connect)
        out = StringIO()

        call_command("importar_catalogos_legacy", stdout=out)
        salida = out.getvalue()

        self.assertIn("[ACTUALIZAR] Carrera 'ISC-LEG'", salida)
        self.assertIn("[ACTUALIZAR] Aula 'LAB-LEG-1'", salida)

        carrera.refresh_from_db()
        self.assertEqual(carrera.nombre, "Ingenieria en Sistemas Computacionales")
        self.assertTrue(carrera.activa)

        aula.refresh_from_db()
        self.assertEqual(aula.edificio, "Edificio Central")
        self.assertEqual(aula.capacidad, 25)
        self.assertEqual(aula.tipo, "laboratorio")

    @patch("academico.management.commands.importar_catalogos_legacy.pymysql.connect")
    def test_conexion_solo_lectura(self, mock_connect):
        from django.core.management import call_command
        from io import StringIO

        _, mock_cursor = self._setup_mock_connection(mock_connect)
        out = StringIO()

        call_command("importar_catalogos_legacy", stdout=out)

        executed_queries = [call.args[0] for call in mock_cursor.execute.call_args_list]
        self.assertTrue(
            any("READ ONLY" in q for q in executed_queries),
            "Debe ejecutar SET SESSION TRANSACTION READ ONLY en la base legacy.",
        )
        for q in executed_queries:
            q_upper = q.strip().upper()
            self.assertFalse(q_upper.startswith("INSERT"), f"No debe escribir en legacy: {q}")
            self.assertFalse(q_upper.startswith("UPDATE"), f"No debe escribir en legacy: {q}")
            self.assertFalse(q_upper.startswith("DELETE"), f"No debe escribir en legacy: {q}")
            self.assertFalse(q_upper.startswith("DROP"), f"No debe escribir en legacy: {q}")

    @patch("academico.management.commands.importar_catalogos_legacy.pymysql.connect")
    def test_error_conexion_lanza_command_error(self, mock_connect):
        from django.core.management import call_command, CommandError
        from io import StringIO

        mock_connect.side_effect = pymysql.MySQLError(2003, "Can't connect to MySQL server")
        out = StringIO()

        with self.assertRaises(CommandError) as ctx:
            call_command("importar_catalogos_legacy", stdout=out)

        self.assertIn("Error al conectar con la base de datos Pasaporte2", str(ctx.exception))


class AcademicBulkCreateTests(TestCase):
    def setUp(self):
        admin = Usuario.objects.create_superuser(
            username="academic_bulk_admin",
            email="academic-bulk-admin@example.invalid",
            password="test-password",
            whatsapp="",
            grupo="",
        )
        self.client.force_login(admin)

    @staticmethod
    def management_data(total_forms):
        return {
            "records-TOTAL_FORMS": str(total_forms),
            "records-INITIAL_FORMS": "0",
            "records-MIN_NUM_FORMS": "0",
            "records-MAX_NUM_FORMS": "100",
        }

    def test_create_view_renders_batch_form_and_add_row_template(self):
        response = self.client.get(reverse("academico:materia_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "id_records-TOTAL_FORMS")
        self.assertContains(response, "data-add-row")
        self.assertContains(response, "academic-bulk-empty-row")

    def test_create_view_saves_multiple_careers_in_one_post(self):
        response = self.client.post(
            reverse("academico:carrera_create"),
            {
                **self.management_data(2),
                "records-0-clave": "BATCH-01",
                "records-0-nombre": "Carrera por lote 1",
                "records-0-activa": "on",
                "records-1-clave": "BATCH-02",
                "records-1-nombre": "Carrera por lote 2",
                "records-1-activa": "on",
            },
        )

        self.assertRedirects(response, reverse("academico:carrera_list"))
        self.assertEqual(
            list(Carrera.objects.order_by("clave").values_list("clave", flat=True)),
            ["BATCH-01", "BATCH-02"],
        )

    def test_duplicate_rows_keep_batch_unsaved_and_show_validation_errors(self):
        response = self.client.post(
            reverse("academico:carrera_create"),
            {
                **self.management_data(2),
                "records-0-clave": "BATCH-DUP",
                "records-0-nombre": "Primera carrera",
                "records-0-activa": "on",
                "records-1-clave": "BATCH-DUP",
                "records-1-nombre": "Carrera duplicada",
                "records-1-activa": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Carrera.objects.count(), 0)
        self.assertTrue(response.context["formset"].non_form_errors())

    def test_create_multiple_enrollments_for_a_student_in_one_post(self):
        alumno = Usuario.objects.create_user(
            username="academic_bulk_student",
            email="academic-bulk-student@example.invalid",
            password="test-password",
            matricula="BULK-STUDENT",
            whatsapp="",
            grupo="A",
        )
        materia_a = Materia.objects.create(clave="BULK-MAT-01", nombre="Materia 1")
        materia_b = Materia.objects.create(clave="BULK-MAT-02", nombre="Materia 2")

        page = self.client.get(reverse("academico:inscripcion_create"))
        self.assertContains(page, f"{alumno.matricula} · {alumno}")

        response = self.client.post(
            reverse("academico:inscripcion_create"),
            {
                **self.management_data(2),
                "records-0-usuario": str(alumno.pk),
                "records-0-materia": str(materia_a.pk),
                "records-0-grupo": "A",
                "records-0-periodo": "2026-3",
                "records-0-activa": "on",
                "records-1-usuario": str(alumno.pk),
                "records-1-materia": str(materia_b.pk),
                "records-1-grupo": "A",
                "records-1-periodo": "2026-3",
                "records-1-activa": "on",
            },
        )

        self.assertRedirects(response, reverse("academico:inscripcion_list"))
        self.assertEqual(
            set(
                Inscripcion.objects.filter(usuario=alumno).values_list(
                    "materia_id", flat=True
                )
            ),
            {materia_a.pk, materia_b.pk},
        )

    def test_bulk_create_preserves_add_permission(self):
        self.client.force_login(
            Usuario.objects.create_user(
                username="academic_bulk_no_permission",
                email="academic-bulk-no-permission@example.invalid",
                password="test-password",
                whatsapp="",
                grupo="",
            )
        )

        response = self.client.get(reverse("academico:carrera_create"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        self.assertEqual(Carrera.objects.count(), 0)

