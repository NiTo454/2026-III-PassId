import hashlib
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from autenticacion.forms import RegistroUsuarioForm
from usuarios.models import PasswordReset, Perfil, Usuario


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_RESET_BASE_URL="https://passid.example",
)
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = Usuario.objects.create(
            username="alumno",
            password="",
            email="alumno@example.com",
            matricula="MAT-001",
            whatsapp="5550000000",
            grupo="A",
            activo=True,
        )
        self.request_url = reverse("usuarios:password_reset_request")

    def test_request_by_email_sends_single_use_link_with_hashed_token(self):
        response = self.client.post(
            self.request_url,
            {"identifier": self.user.email},
        )

        self.assertRedirects(response, reverse("usuarios:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        token = mail.outbox[0].body.split("/usuarios/restablecer/")[1].split("/")[0]
        self.assertIn("https://passid.example/usuarios/restablecer/", mail.outbox[0].body)
        reset = PasswordReset.objects.get(usuario=self.user)
        self.assertEqual(len(token), 64)
        self.assertEqual(reset.token, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(reset.token, token)
        self.assertAlmostEqual(
            reset.expira_en,
            timezone.now() + timedelta(hours=24),
            delta=timedelta(seconds=5),
        )

    def test_request_by_matricula_sends_email(self):
        self.client.post(self.request_url, {"identifier": self.user.matricula})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_unknown_identifier_has_same_response_and_sends_no_email(self):
        response = self.client.post(
            self.request_url,
            {"identifier": "no-existe@example.com"},
        )

        self.assertRedirects(response, reverse("usuarios:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(PasswordReset.objects.exists())

    def test_duplicate_matricula_does_not_send_email(self):
        Usuario.objects.create(
            username="otro",
            password="",
            email="otro@example.com",
            matricula=self.user.matricula,
            whatsapp="5550000001",
            grupo="A",
            activo=True,
        )

        self.client.post(self.request_url, {"identifier": self.user.matricula})

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(PasswordReset.objects.exists())

    def test_expired_token_is_rejected(self):
        token = "a" * 64
        reset = PasswordReset.objects.create(
            usuario=self.user,
            token=hashlib.sha256(token.encode()).hexdigest(),
            expira_en=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get(
            reverse("usuarios:password_reset_confirm", kwargs={"token": token})
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Enlace no válido o vencido", status_code=400)
        self.assertTrue(PasswordReset.objects.filter(pk=reset.pk).exists())

    def test_valid_token_updates_password_and_cannot_be_reused(self):
        token = "b" * 64
        reset = PasswordReset.objects.create(
            usuario=self.user,
            token=hashlib.sha256(token.encode()).hexdigest(),
            expira_en=timezone.now() + timedelta(hours=24),
        )
        confirm_url = reverse(
            "usuarios:password_reset_confirm",
            kwargs={"token": token},
        )
        page = self.client.get(confirm_url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page["Cache-Control"], "no-store")
        self.assertEqual(page["Referrer-Policy"], "no-referrer")

        response = self.client.post(
            confirm_url,
            {
                "new_password1": "UnaNuevaClaveSegura#2026",
                "new_password2": "UnaNuevaClaveSegura#2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(check_password("UnaNuevaClaveSegura#2026", self.user.password))
        self.assertFalse(PasswordReset.objects.filter(pk=reset.pk).exists())
        self.assertEqual(self.client.get(confirm_url).status_code, 400)

    def test_invalid_password_does_not_consume_token(self):
        token = "c" * 64
        reset = PasswordReset.objects.create(
            usuario=self.user,
            token=hashlib.sha256(token.encode()).hexdigest(),
            expira_en=timezone.now() + timedelta(hours=24),
        )

        response = self.client.post(
            reverse("usuarios:password_reset_confirm", kwargs={"token": token}),
            {"new_password1": "123", "new_password2": "123"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(PasswordReset.objects.filter(pk=reset.pk).exists())

    def test_new_request_invalidates_previous_token(self):
        self.client.post(self.request_url, {"identifier": self.user.email})
        previous_token = mail.outbox[0].body.split("/usuarios/restablecer/")[1].split("/")[0]
        self.client.post(self.request_url, {"identifier": self.user.email})

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(PasswordReset.objects.filter(usuario=self.user).count(), 1)
        self.assertEqual(
            self.client.get(
                reverse(
                    "usuarios:password_reset_confirm",
                    kwargs={"token": previous_token},
                )
            ).status_code,
            400,
        )

    def test_request_rate_limit_stops_repeated_emails(self):
        for _ in range(6):
            self.client.post(self.request_url, {"identifier": self.user.email})

        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(PasswordReset.objects.filter(usuario=self.user).count(), 1)


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create(
            username="alumno",
            password="",
            email="alumno@example.com",
            whatsapp="5550000000",
            grupo="A",
            activo=True,
        )
        self.user.set_password("ClaveSegura#2026")
        self.user.save()

    def test_login_page_has_local_script_and_password_help(self):
        response = self.client.get(reverse("autenticacion:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "static/js/auth.js")
        self.assertContains(response, 'data-auth-mode="login"')
        self.assertContains(response, "Puedes usar cualquiera de los dos.")
        self.assertContains(response, 'data-auth-link="register"')
        self.assertContains(response, 'data-auth-reset-link')
        self.assertNotContains(response, '>Recuperar</a>')
        self.assertContains(response, 'aria-label="Mostrar contraseña"')
        self.assertNotContains(response, "auth-brand-mark")

    def test_registration_page_renders_responsive_account_form(self):
        response = self.client.get(reverse("autenticacion:registro"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crea tu cuenta")
        self.assertContains(response, "auth-form-grid")
        self.assertContains(response, 'name="nombre_completo"')
        self.assertNotContains(response, 'name="apaterno"')
        self.assertNotContains(response, 'name="amaterno"')
        self.assertContains(response, 'data-auth-mode="register"')
        self.assertContains(response, "static/js/auth.js")
        self.assertContains(response, 'aria-label="Mostrar contraseña"')
        self.assertNotContains(response, "auth-brand-mark")

    def test_registration_combines_name_fields_without_changing_user_model_fields(self):
        form = RegistroUsuarioForm(data={
            "nombre_completo": "  María   Fernanda De-la-Cruz Pérez  ",
            "matricula": "MAT-2026",
            "email": "maria@example.com",
            "whatsapp": "5550000002",
            "grupo": "A",
            "username": "maria",
            "password1": "UnaClaveSegura#2026",
            "password2": "UnaClaveSegura#2026",
        })

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.nombre, "María Fernanda")
        self.assertEqual(user.apaterno, "De-la-Cruz")
        self.assertEqual(user.amaterno, "Pérez")

    def test_registration_rejects_ambiguous_full_name_format(self):
        form = RegistroUsuarioForm(data={
            "nombre_completo": "María Fernanda",
            "matricula": "MAT-2027",
            "email": "maria2@example.com",
            "whatsapp": "5550000003",
            "grupo": "A",
            "username": "maria2",
            "password1": "UnaClaveSegura#2026",
            "password2": "UnaClaveSegura#2026",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("nombre_completo", form.errors)

    def test_registration_rejects_comma_separated_names(self):
        form = RegistroUsuarioForm(data={
            "nombre_completo": "María Fernanda, López, Pérez",
            "matricula": "MAT-2029",
            "email": "maria4@example.com",
            "whatsapp": "5550000005",
            "grupo": "A",
            "username": "maria4",
            "password1": "UnaClaveSegura#2026",
            "password2": "UnaClaveSegura#2026",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("nombre_completo", form.errors)

    def test_registration_saves_combined_name_into_existing_user_fields(self):
        basic_profile = Perfil.objects.create(nombre="Básico")
        student_profile = Perfil.objects.create(nombre="Alumno")
        response = self.client.post(
            reverse("autenticacion:registro"),
            {
                "nombre_completo": "María Fernanda De-la-Cruz Pérez",
                "matricula": "MAT-2028",
                "email": "maria3@example.com",
                "whatsapp": "5550000004",
                "grupo": "A",
                "username": "maria3",
                "password1": "UnaClaveSegura#2026",
                "password2": "UnaClaveSegura#2026",
            },
        )

        self.assertRedirects(
            response,
            reverse("autenticacion:login"),
            fetch_redirect_response=False,
        )
        user = Usuario.objects.get(username="maria3")
        self.assertEqual(
            (user.nombre, user.apaterno, user.amaterno),
            ("María Fernanda", "De-la-Cruz", "Pérez"),
        )
        self.assertSetEqual(
            set(user.perfiles.values_list("pk", flat=True)),
            {basic_profile.pk, student_profile.pk},
        )

    def test_password_reset_request_uses_authentication_design(self):
        response = self.client.get(reverse("usuarios:password_reset_request"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recupera tu contraseña")
        self.assertContains(response, "Correo institucional o matrícula")
        self.assertContains(response, "Enviar instrucciones")
        self.assertContains(response, 'data-auth-mode="reset"')
        self.assertNotContains(response, "auth-brand-mark")

    def test_login_accepts_institutional_email(self):
        response = self.client.post(
            reverse("autenticacion:login"),
            {"username": self.user.email, "password": "ClaveSegura#2026"},
        )

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post_and_shows_confirmation_message(self):
        self.client.force_login(self.user)
        logout_url = reverse("autenticacion:logout")

        response = self.client.get(logout_url)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        response = self.client.post(logout_url, follow=True)

        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "Has cerrado sesión correctamente.")
