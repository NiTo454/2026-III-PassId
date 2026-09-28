from django.db import models
from django.conf import settings

class Evento(models.Model):
    """Catálogo general de eventos institucionales y del pasaporte."""
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200, verbose_name="Nombre del evento")
    fecha_hora = models.DateTimeField(verbose_name="Fecha y hora")
    lugar = models.CharField(max_length=200, null=True, blank=True, verbose_name="Lugar o auditorio")
    requiere_registro = models.BooleanField(default=True, null=True, verbose_name="¿Requiere pre-registro?")
    permitir_autorregistro = models.BooleanField(default=True, null=True, verbose_name="¿Permite autoregistro?")
    responsable_interno = models.CharField(max_length=200, null=True, blank=True, verbose_name="Responsable interno")
    responsable_externo = models.CharField(max_length=200, null=True, blank=True, verbose_name="Responsable externo")

    responsables = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ResponsableEvento",
        related_name="eventos_a_cargo",
        blank=True
    )
    asistentes_registrados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Registro",
        related_name="eventos_registrados",
        blank=True
    )

    class Meta:
        db_table = "evento"
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"{self.nombre} ({self.fecha_hora.strftime('%d/%m/%Y %H:%M')})"


class Registro(models.Model):
    """Pre-registro de usuarios/alumnos a un evento."""
    evento = models.ForeignKey(Evento, on_delete=models.RESTRICT, related_name="registros", db_column="evento_id")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="registros_eventos", db_column="usuario_id")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    equipo = models.CharField(max_length=50, null=True, blank=True, verbose_name="Equipo (opcional)")

    class Meta:
        db_table = "registro"
        unique_together = (("evento", "usuario"),)
        verbose_name = "Pre-registro a Evento"
        verbose_name_plural = "Pre-registros a Eventos"

    def __str__(self):
        return f"{self.usuario} -> {self.evento.nombre}"


class Asistencia(models.Model):
    """Registro de asistencia real / pase de lista en puerta para eventos."""
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="asistencias", db_column="evento_id")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="asistencias_eventos", db_column="usuario_id")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="asistencias_escaneadas",
        db_column="registrado_por"
    )
    fecha_entrada = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y hora de acceso")

    class Meta:
        db_table = "asistencia"
        unique_together = (("evento", "usuario"),)
        verbose_name = "Asistencia a Evento"
        verbose_name_plural = "Asistencias a Eventos"

    def __str__(self):
        return f"Asistencia: {self.usuario} en {self.evento.nombre}"


class ResponsableEvento(models.Model):
    """Asignación de personal o docentes como responsables del evento."""
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, db_column="evento_id")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column="usuario_id")

    class Meta:
        db_table = "responsable_evento"
        unique_together = (("evento", "usuario"),)
        verbose_name = "Responsable de Evento"
        verbose_name_plural = "Responsables de Eventos"

    def __str__(self):
        return f"{self.usuario} coordina {self.evento.nombre}"


class ReporteEventos(models.Model):
    """Modelo de solo lectura para la vista SQL reporte_eventos."""
    id = models.BigIntegerField(primary_key=True)
    nombre = models.CharField(max_length=200)
    lugar = models.CharField(max_length=200)
    fecha_hora = models.CharField(max_length=50)
    responsable = models.CharField(max_length=200)
    asistentes_registrados = models.IntegerField()
    usuarios_asistidos = models.IntegerField()

    class Meta:
        managed = False
        db_table = "reporte_eventos"
        verbose_name = "Reporte de Eventos"
        verbose_name_plural = "Reportes de Eventos"


class ReporteUsuarios(models.Model):
    """Modelo de solo lectura para la vista SQL reporte_usuarios."""
    id = models.BigIntegerField(primary_key=True)
    matricula = models.CharField(max_length=50)
    nombre = models.CharField(max_length=50)
    apaterno = models.CharField(max_length=50)
    amaterno = models.CharField(max_length=50)
    grupo = models.CharField(max_length=50)
    eventos_registrados = models.IntegerField()
    eventos_asistidos = models.IntegerField()

    class Meta:
        managed = False
        db_table = "reporte_usuarios"
        verbose_name = "Reporte de Usuarios"
        verbose_name_plural = "Reportes de Usuarios"
