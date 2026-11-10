import hashlib
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from usuarios.models import PasswordReset, Usuario


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
