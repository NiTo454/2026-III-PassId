from django.db import models
from django.conf import settings

class Carrera(models.Model):
    """Catálogo de programas académicos / carreras universitarias."""
    id = models.BigAutoField(primary_key=True)
    clave = models.CharField(max_length=20, unique=True, verbose_name="Clave")
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la carrera")
    activa = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        db_table = "carrera"
        verbose_name = "Carrera"
        verbose_name_plural = "Carreras"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.clave} - {self.nombre}"


class Aula(models.Model):
    """Espacios físicos disponibles para clases, talleres y eventos."""
    TIPO_CHOICES = [
        ("aula", "Aula"),
        ("laboratorio", "Laboratorio"),
        ("auditorio", "Auditorio"),
        ("taller", "Taller"),
        ("otro", "Otro"),
    ]

    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=30, unique=True, verbose_name="Código del aula")
    edificio = models.CharField(max_length=100, null=True, blank=True, verbose_name="Edificio")
    capacidad = models.PositiveIntegerField(null=True, blank=True, verbose_name="Capacidad")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="aula", verbose_name="Tipo")
    activa = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        db_table = "aula"
        verbose_name = "Aula"
        verbose_name_plural = "Aulas"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} ({self.edificio or 'Sin edificio'})"


class Materia(models.Model):
    """Asignaturas académicas vinculadas a una carrera y periodo."""
    id = models.BigAutoField(primary_key=True)
    clave = models.CharField(max_length=30, unique=True, verbose_name="Clave de materia")
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la asignatura")
    asistencias = models.PositiveIntegerField(default=0, verbose_name="Asistencias mínimas")
    horas_semana = models.PositiveIntegerField(default=0, verbose_name="Horas semanales")
    periodo = models.CharField(max_length=30, null=True, blank=True, verbose_name="Periodo / Cuatrimestre")
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materias",
        db_column="carrera_id"
    )
    activa = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        db_table = "materia"
        verbose_name = "Materia"
        verbose_name_plural = "Materias"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.clave} - {self.nombre}"


class DiaSemanaChoices(models.TextChoices):
    LUNES = "lunes", "Lunes"
    MARTES = "martes", "Martes"
    MIERCOLES = "miercoles", "Miércoles"
    JUEVES = "jueves", "Jueves"
    VIERNES = "viernes", "Viernes"
    SABADO = "sabado", "Sábado"


class Horario(models.Model):
    """Bloque de clase programado: materia, profesor, aula, grupo y día/hora."""
    id = models.BigAutoField(primary_key=True)
    materia = models.ForeignKey(Materia, on_delete=models.RESTRICT, related_name="horarios", db_column="materia_id")
    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="horarios_impartidos", db_column="profesor_id")
    aula = models.ForeignKey(Aula, on_delete=models.SET_NULL, null=True, blank=True, related_name="horarios", db_column="aula_id")
    grupo = models.CharField(max_length=10, default="A", verbose_name="Grupo")
    dia_semana = models.CharField(max_length=15, choices=DiaSemanaChoices.choices, verbose_name="Día de la semana")
    hora_inicio = models.TimeField(verbose_name="Hora de inicio")
    hora_fin = models.TimeField(verbose_name="Hora de finalización")
    periodo = models.CharField(max_length=30, verbose_name="Periodo académico")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")

    class Meta:
        db_table = "horario"
        verbose_name = "Horario de Clase"
        verbose_name_plural = "Horarios de Clases"
        constraints = [
            models.UniqueConstraint(
                fields=["aula", "dia_semana", "hora_inicio", "periodo"],
                name="uq_horario_slot"
            )
        ]
        ordering = ["periodo", "dia_semana", "hora_inicio"]

    def __str__(self):
        return f"{self.materia.nombre} | {self.dia_semana} {self.hora_inicio}-{self.hora_fin} ({self.grupo})"


class ProfesorDisponibilidad(models.Model):
    """Disponibilidad de horarios del personal docente para cada periodo."""
    TIPO_CHOICES = [
        ("disponible", "Disponible"),
        ("no_disponible", "No disponible"),
    ]

    id = models.BigAutoField(primary_key=True)
    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="disponibilidades", db_column="profesor_id")
    dia_semana = models.CharField(max_length=15, choices=DiaSemanaChoices.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    periodo = models.CharField(max_length=30)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="disponible")
    notas = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "profesor_disponibilidad"
        constraints = [
            models.UniqueConstraint(
                fields=["profesor", "dia_semana", "hora_inicio", "periodo"],
                name="uk_profesor_disp_bloque"
            )
        ]
        verbose_name = "Disponibilidad de Profesor"
        verbose_name_plural = "Disponibilidades de Profesores"

    def __str__(self):
        return f"{self.profesor} - {self.dia_semana} ({self.tipo})"


class Inscripcion(models.Model):
    """Inscripción de un alumno en una materia, grupo y periodo específico."""
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inscripciones", db_column="usuario_id")
    materia = models.ForeignKey(Materia, on_delete=models.RESTRICT, related_name="inscripciones", db_column="materia_id")
    grupo = models.CharField(max_length=10, default="A")
    periodo = models.CharField(max_length=30)
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "inscripcion"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "materia", "grupo", "periodo"],
                name="uq_inscripcion"
            )
        ]
        verbose_name = "Inscripción de Alumno"
        verbose_name_plural = "Inscripciones de Alumnos"

    def __str__(self):
        return f"{self.usuario} -> {self.materia.nombre} ({self.periodo})"


class AsistenciaClase(models.Model):
    """Registro de pase de lista por clase y fecha (lectura QR o manual)."""
    ESTADO_CHOICES = [
        ("presente", "Presente"),
        ("retardo", "Retardo"),
        ("falta", "Falta"),
        ("justificado", "Justificado"),
    ]
    METODO_CHOICES = [
        ("qr", "Código QR"),
        ("manual", "Manual"),
    ]

    id = models.BigAutoField(primary_key=True)
    horario = models.ForeignKey(Horario, on_delete=models.CASCADE, related_name="asistencias", db_column="horario_id")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="asistencias_clase", db_column="usuario_id")
    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default="presente")
    metodo = models.CharField(max_length=10, choices=METODO_CHOICES, default="qr")

    class Meta:
        db_table = "asistencia_clase"
        constraints = [
            models.UniqueConstraint(
                fields=["horario", "usuario", "fecha"],
                name="uq_asistclase_sesion"
            )
        ]
        verbose_name = "Asistencia a Clase"
        verbose_name_plural = "Asistencias a Clases"

    def __str__(self):
        return f"{self.usuario} - {self.horario.materia.clave} ({self.fecha} - {self.estado})"
