from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Perfil, Permiso, Usuario
from .models import ProfesorDisponibilidad


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
