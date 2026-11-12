from django import forms

from academico.models import Horario


class EscaneoAsistenciaForm(forms.Form):
    horario = forms.ModelChoiceField(
        queryset=Horario.objects.none(),
        label="Clase / horario",
        empty_label="Selecciona una clase",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    token = forms.CharField(
        max_length=500,
        required=False,
        strip=True,
        widget=forms.HiddenInput(),
    )
    inscribir = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
    )
    matricula = forms.CharField(
        max_length=50,
        required=False,
        strip=True,
        label="Matrícula (captura manual)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "placeholder": "Captura la matrícula si no puedes usar cámara",
            }
        ),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        horarios = Horario.objects.filter(activo=True).select_related("materia", "aula")
        if not user.is_superuser and not user.has_perm("horario.admin"):
            horarios = horarios.filter(profesor=user)
        self.fields["horario"].queryset = horarios.order_by(
            "periodo", "dia_semana", "hora_inicio"
        )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("token") and not cleaned_data.get("matricula"):
            raise forms.ValidationError("Escanea un QR o captura una matrícula.")
        if cleaned_data.get("token") and cleaned_data.get("matricula"):
            raise forms.ValidationError("Envía el QR o la matrícula manual, no ambos.")
        return cleaned_data
