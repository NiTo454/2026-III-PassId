from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asistenciaclase",
            name="metodo",
            field=models.CharField(
                choices=[
                    ("qr", "Código QR"),
                    ("manual", "Manual"),
                    ("ubicacion", "Ubicación"),
                ],
                default="qr",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="asistenciaclase",
            name="latitud",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="asistenciaclase",
            name="longitud",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="asistenciaclase",
            name="registrado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="asistencias_clase_registradas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="IncidenciaAsistencia",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("fecha", models.DateField()),
                ("intentos", models.PositiveSmallIntegerField(default=0)),
                ("motivo", models.TextField()),
                ("atendida", models.BooleanField(default=False)),
                ("creada", models.DateTimeField(auto_now_add=True)),
                ("atendida_el", models.DateTimeField(blank=True, null=True)),
                (
                    "atendida_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="incidencias_asistencia_atendidas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "horario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incidencias_asistencia",
                        to="academico.horario",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incidencias_asistencia",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Incidencia de asistencia",
                "verbose_name_plural": "Incidencias de asistencia",
                "db_table": "incidencia_asistencia",
                "ordering": ["creada"],
            },
        ),
        migrations.AddConstraint(
            model_name="incidenciaasistencia",
            constraint=models.UniqueConstraint(
                fields=("horario", "usuario", "fecha"),
                name="uq_incidencia_asistencia_dia",
            ),
        ),
    ]
