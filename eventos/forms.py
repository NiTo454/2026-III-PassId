from django import forms
from .models import Evento, Registro, Asistencia

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            "nombre", "fecha_hora", "lugar",
            "requiere_registro", "permitir_autorregistro",
            "responsable_interno", "responsable_externo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del evento"}),
            "fecha_hora": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "lugar": forms.TextInput(attrs={"class": "form-control", "placeholder": "Auditorio, Aula Magna, etc."}),
            "requiere_registro": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "permitir_autorregistro": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "responsable_interno": forms.TextInput(attrs={"class": "form-control", "placeholder": "Responsable interno"}),
            "responsable_externo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Responsable externo o ponente"}),
        }


class RegistroEventoForm(forms.ModelForm):
    class Meta:
        model = Registro
        fields = ["evento", "usuario", "equipo"]
        widgets = {
            "evento": forms.Select(attrs={"class": "form-select"}),
            "usuario": forms.Select(attrs={"class": "form-select"}),
            "equipo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de equipo (opcional)"}),
        }


class AsistenciaEventoForm(forms.ModelForm):
    class Meta:
        model = Asistencia
        fields = ["evento", "usuario"]
        widgets = {
            "evento": forms.Select(attrs={"class": "form-select"}),
            "usuario": forms.Select(attrs={"class": "form-select"}),
        }


class EscaneoAsistenciaEventoForm(forms.Form):
    evento = forms.ModelChoiceField(
        queryset=Evento.objects.none(),
        label="Evento a gestionar",
        empty_label="Selecciona un evento",
        widget=forms.Select(attrs={"class": "form-control scanner-select", "id": "id_evento"}),
    )
    token = forms.CharField(
        max_length=500,
        required=False,
        strip=True,
        widget=forms.HiddenInput(attrs={"id": "id_token"}),
    )
    matricula = forms.CharField(
        max_length=50,
        required=False,
        strip=True,
        label="Matrícula o Usuario (captura manual)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "id_matricula",
                "autocomplete": "off",
                "placeholder": "Captura la matrícula si no puedes usar la cámara",
            }
        ),
    )
    registrar_si_no_existe = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput(attrs={"id": "id_registrar_si_no_existe"}),
    )

    def __init__(self, *args, user=None, initial_evento_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["evento"].queryset = Evento.objects.all().order_by("-fecha_hora")
        if initial_evento_id:
            try:
                self.fields["evento"].initial = Evento.objects.get(pk=initial_evento_id)
            except Evento.DoesNotExist:
                pass

    def clean(self):
        cleaned_data = super().clean()
        token = cleaned_data.get("token")
        matricula = cleaned_data.get("matricula")
        if not token and not matricula:
            raise forms.ValidationError("Escanea un código QR o ingresa una matrícula manualmente.")
        if token and matricula:
            raise forms.ValidationError("Envía el código QR o la matrícula manual, no ambos.")
        return cleaned_data
