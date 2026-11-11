from django import forms
from .models import (
    Aula,
    Carrera,
    DiaSemanaChoices,
    Horario,
    Inscripcion,
    Materia,
    ProfesorDisponibilidad,
)

class CarreraForm(forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ["clave", "nombre", "activa"]
        widgets = {
            "clave": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. ITI, MECA"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre completo de la carrera"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        fields = ["codigo", "edificio", "capacidad", "tipo", "activa"]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. A-101, LAB-REDES"}),
            "edificio": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. Edificio Docencia 1"}),
            "capacidad": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Capacidad máxima"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ["clave", "nombre", "asistencias", "horas_semana", "periodo", "carrera", "activa"]
        widgets = {
            "clave": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. PROG-WEB"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de la materia"}),
            "asistencias": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "horas_semana": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "periodo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 2026-3"}),
            "carrera": forms.Select(attrs={"class": "form-select"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class HorarioForm(forms.ModelForm):
    class Meta:
        model = Horario
        fields = ["materia", "profesor", "aula", "grupo", "dia_semana", "hora_inicio", "hora_fin", "periodo", "activo"]
        widgets = {
            "materia": forms.Select(attrs={"class": "form-select"}),
            "profesor": forms.Select(attrs={"class": "form-select"}),
            "aula": forms.Select(attrs={"class": "form-select"}),
            "grupo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. A"}),
            "dia_semana": forms.Select(attrs={"class": "form-select"}),
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "periodo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 2026-3"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class InscripcionForm(forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = ["usuario", "materia", "grupo", "periodo", "activa"]
        widgets = {
            "usuario": forms.Select(attrs={"class": "form-select"}),
            "materia": forms.Select(attrs={"class": "form-select"}),
            "grupo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. A"}),
            "periodo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 2026-3"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ProfesorDisponibilidadForm(forms.ModelForm):
    dia_semana = forms.ChoiceField(
        choices=DiaSemanaChoices.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Día de la semana",
    )

    class Meta:
        model = ProfesorDisponibilidad
        fields = ["dia_semana", "hora_inicio", "hora_fin", "periodo", "tipo", "notas"]
        labels = {
            "hora_inicio": "Hora de inicio",
            "hora_fin": "Hora de fin",
            "periodo": "Período académico",
            "tipo": "Disponibilidad",
            "notas": "Notas",
        }
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "periodo": forms.HiddenInput(),
            "tipo": forms.RadioSelect(attrs={"class": "availability-type-option"}),
            "notas": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Opcional: observaciones",
                    "maxlength": 200,
                }
            ),
        }

    def __init__(self, *args, profesor, **kwargs):
        self.profesor = profesor
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get("hora_inicio")
        fin = cleaned_data.get("hora_fin")
        dia = cleaned_data.get("dia_semana")
        periodo = cleaned_data.get("periodo")

        if inicio and fin and inicio >= fin:
            self.add_error("hora_fin", "La hora final debe ser posterior a la inicial.")
            return cleaned_data

        if inicio and fin and dia and periodo:
            traslapes = ProfesorDisponibilidad.objects.filter(
                profesor=self.profesor,
                dia_semana=dia,
                periodo=periodo,
                hora_inicio__lt=fin,
                hora_fin__gt=inicio,
            )
            if self.instance.pk:
                traslapes = traslapes.exclude(pk=self.instance.pk)
            traslape = traslapes.order_by("hora_inicio").first()
            if traslape:
                dia_nombre = dict(DiaSemanaChoices.choices)[dia]
                self.add_error(
                    None,
                    (
                        f"Este horario se cruza con el bloque del {dia_nombre} "
                        f"de {traslape.hora_inicio:%H:%M} a {traslape.hora_fin:%H:%M}."
                    ),
                )

        return cleaned_data
