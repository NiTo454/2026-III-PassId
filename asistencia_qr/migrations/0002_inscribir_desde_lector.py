from django.db import migrations


PERMISSION_CODENAME = "inscribir_estudiante_en_clase"
PERMISSION_NAME = "Inscribir alumnos desde el lector QR"


def grant_scanner_enrollment_permission(apps, schema_editor):
    database = schema_editor.connection.alias
    Permiso = apps.get_model("usuarios", "Permiso")
    Perfil = apps.get_model("usuarios", "Perfil")
    PerfilTienePermiso = apps.get_model("usuarios", "PerfilTienePermiso")

    permission, _ = Permiso.objects.using(database).update_or_create(
        codename=PERMISSION_CODENAME,
        defaults={
            "tipo": "asistencia_qr",
            "nombre": PERMISSION_NAME,
        },
    )

    for profile_name in ("profesor", "dev", "admin"):
        profile = Perfil.objects.using(database).filter(
            nombre__iexact=profile_name,
        ).first()
        if profile is None:
            if profile_name == "profesor":
                raise RuntimeError(
                    "No se encontró el perfil 'profesor' para asignar el permiso "
                    "de inscripción desde el lector QR."
                )
            continue
        PerfilTienePermiso.objects.using(database).get_or_create(
            perfil_id=profile.pk,
            permiso_id=permission.pk,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("asistencia_qr", "0001_seed_permissions"),
        ("usuarios", "0009_crear_perfil_lectura"),
    ]

    operations = [
        migrations.RunPython(
            grant_scanner_enrollment_permission,
            migrations.RunPython.noop,
        ),
    ]
