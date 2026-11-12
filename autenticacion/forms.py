from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from usuarios.models import Usuario

class LoginForm(forms.Form):
    username = forms.CharField(
        label="Usuario o Correo Electrónico",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ingresa tu usuario o correo",
            "autocomplete": "username",
            "aria-describedby": "username-help",
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Ingresa tu contraseña",
            "autocomplete": "current-password",
        })
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if identifier and password:
            lookup_username = identifier.strip()
            if "@" in lookup_username:
                try:
                    user_obj = Usuario.objects.get(email__iexact=lookup_username)
                    lookup_username = user_obj.username
                except (Usuario.DoesNotExist, Usuario.MultipleObjectsReturned):
                    pass

            self.user_cache = authenticate(self.request, username=lookup_username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Credenciales inválidas. Verifica tu usuario y contraseña.")
            if not self.user_cache.activo:
                raise forms.ValidationError("Esta cuenta de usuario se encuentra inactiva.")

        return cleaned_data

    def get_user(self):
        return self.user_cache


class RegistroUsuarioForm(forms.ModelForm):
    nombre_completo = forms.CharField(
        label="Nombre completo",
        max_length=154,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ej. María Fernanda De-la-Cruz Pérez",
            "autocomplete": "name",
            "aria-describedby": "full-name-help",
        }),
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "autocomplete": "new-password",
        }),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "autocomplete": "new-password",
        }),
    )

    class Meta:
        model = Usuario
        fields = [
            "matricula",
            "email",
            "whatsapp",
            "grupo",
            "username",
        ]
        labels = {
            "matricula": "Matrícula",
            "email": "Correo electrónico",
            "whatsapp": "WhatsApp / teléfono",
            "grupo": "Grupo",
            "username": "Nombre de usuario",
        }
        widgets = {
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "autocomplete": "email",
            }),
            "whatsapp": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),
            "username": forms.TextInput(attrs={
                "class": "form-control",
                "autocomplete": "username",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_parts = None
        self.fields["username"].widget.attrs["id"] = "register-username"
        self.order_fields([
            "nombre_completo",
            "matricula",
            "email",
            "whatsapp",
            "grupo",
            "username",
            "password1",
            "password2",
        ])

    def clean_nombre_completo(self):
        full_name = self.cleaned_data["nombre_completo"]
        full_name = " ".join(full_name.split())
        name_words = full_name.split()
        if "," in full_name or len(name_words) < 3:
            raise ValidationError(
                "Escribe tus nombres y dos apellidos separados por espacios, sin comas. "
                "Ejemplo: María Fernanda De-la-Cruz Pérez."
            )
        name_parts = [
            " ".join(name_words[:-2]),
            name_words[-2],
            name_words[-1],
        ]
        if any(len(part) > 50 for part in name_parts):
            raise ValidationError("Cada parte del nombre debe tener 50 caracteres o menos.")

        self._name_parts = name_parts
        return full_name

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if Usuario.objects.filter(username__iexact=username).exists():
            raise ValidationError("Este nombre de usuario ya está registrado.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif password1 and self._name_parts:
            name_parts = self._name_parts
            user = Usuario(
                username=cleaned_data.get("username", ""),
                email=cleaned_data.get("email", ""),
                nombre=name_parts[0],
                apaterno=name_parts[1],
                amaterno=name_parts[2],
            )
            try:
                validate_password(password1, user)
            except ValidationError as error:
                self.add_error("password1", error)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.nombre, user.apaterno, user.amaterno = self._name_parts
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
