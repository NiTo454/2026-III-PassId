from django import forms
from .models import Permiso, Perfil, Usuario

class PermisoForm(forms.ModelForm):
    class Meta:
        model = Permiso
        fields = ["tipo", "codename", "nombre"]
        labels = {
            "tipo": "Tipo / Módulo",
            "codename": "Código de Permiso",
            "nombre": "Nombre Descriptivo",
        }
        widgets = {
            "tipo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej. usuarios, academico, eventos",
                "required": True,
            }),
            "codename": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej. add_usuario, view_evento",
                "required": True,
            }),
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej. Permite crear nuevos usuarios en el sistema",
            }),
        }


class PerfilForm(forms.ModelForm):
    permisos = forms.ModelMultipleChoiceField(
        queryset=Permiso.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=False,
        label="Permisos asignados"
    )

    class Meta:
        model = Perfil
        fields = ["nombre", "permisos"]
        labels = {
            "nombre": "Nombre del Perfil / Rol",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej. Administrador, Profesor, Alumno",
                "required": True,
            }),
        }


class UsuarioCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "••••••••"}),
        required=True
    )
    perfiles = forms.ModelMultipleChoiceField(
        queryset=Perfil.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=False,
        label="Perfiles / Roles"
    )

    class Meta:
        model = Usuario
        fields = [
            "username", "email", "password", "nombre", "apaterno", "amaterno",
            "categoria", "whatsapp", "grupo", "matricula", "activo", "is_superuser", "perfiles"
        ]
        labels = {
            "username": "Nombre de usuario",
            "email": "Correo institucional",
            "nombre": "Nombre(s)",
            "apaterno": "Apellido Paterno",
            "amaterno": "Apellido Materno",
            "categoria": "Categoría",
            "whatsapp": "WhatsApp / Teléfono",
            "grupo": "Grupo",
            "matricula": "Matrícula",
            "activo": "¿Usuario Activo?",
            "is_superuser": "¿Es Superusuario?",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "ej. jdoe"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "ej. jdoe@utvam.edu.mx"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apaterno": forms.TextInput(attrs={"class": "form-control"}),
            "amaterno": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_superuser": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class UsuarioUpdateForm(forms.ModelForm):
    password = forms.CharField(
        label="Nueva Contraseña (opcional)",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Dejar en blanco para conservar"}),
        required=False
    )
    perfiles = forms.ModelMultipleChoiceField(
        queryset=Perfil.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=False,
        label="Perfiles / Roles"
    )

    class Meta:
        model = Usuario
        fields = [
            "username", "email", "password", "nombre", "apaterno", "amaterno",
            "categoria", "whatsapp", "grupo", "matricula", "activo", "is_superuser", "perfiles"
        ]
        labels = {
            "username": "Nombre de usuario",
            "email": "Correo institucional",
            "nombre": "Nombre(s)",
            "apaterno": "Apellido Paterno",
            "amaterno": "Apellido Materno",
            "categoria": "Categoría",
            "whatsapp": "WhatsApp / Teléfono",
            "grupo": "Grupo",
            "matricula": "Matrícula",
            "activo": "¿Usuario Activo?",
            "is_superuser": "¿Es Superusuario?",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apaterno": forms.TextInput(attrs={"class": "form-control"}),
            "amaterno": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_superuser": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user
