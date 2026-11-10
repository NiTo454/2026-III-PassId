from django.core import signing
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import json

from eventos.models import Evento, Registro, Asistencia
from usuarios.models import Permiso, Usuario


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
        response = self.client.get(reverse("eventos:lector"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lector QR de Eventos")

    def test_lector_view_preselects_event(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("eventos:lector") + f"?evento={self.evento_con_registro.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["evento_preseleccionado"], self.evento_con_registro
        )

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
