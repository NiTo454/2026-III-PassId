from django.db import migrations, models
import django.utils.timezone


def invalidate_legacy_tokens(apps, schema_editor):
    PasswordReset = apps.get_model("usuarios", "PasswordReset")
    PasswordReset.objects.using(schema_editor.connection.alias).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0006_asignar_permiso_autorregistro_alumno"),
    ]

    operations = [
        migrations.RunPython(
            invalidate_legacy_tokens,
            migrations.RunPython.noop,
        ),
        migrations.AddField(
            model_name="passwordreset",
            name="creado_en",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                verbose_name="Fecha de creación",
            ),
        ),
    ]
