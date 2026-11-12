from django.db import migrations


PERMISSION_CODENAME = "add_registro_masivo"
PERMISSION_NAME = "Importar registros de eventos de forma masiva"


def create_bulk_registration_permission(apps, schema_editor):
    database = schema_editor.connection.alias
    Permiso = apps.get_model("usuarios", "Permiso")
    Perfil = apps.get_model("usuarios", "Perfil")
    PerfilTienePermiso = apps.get_model("usuarios", "PerfilTienePermiso")

    permission, _ = Permiso.objects.using(database).update_or_create(
        codename=PERMISSION_CODENAME,
        defaults={
            "tipo": "registro",
            "nombre": PERMISSION_NAME,
        },
    )
    admin = Perfil.objects.using(database).filter(nombre__iexact="admin").first()
    if admin is None:
        raise RuntimeError(
            "No se encontró el perfil 'admin' para asignar el permiso "
            "de importación masiva de registros."
        )
    PerfilTienePermiso.objects.using(database).get_or_create(
        perfil_id=admin.pk,
        permiso_id=permission.pk,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0009_crear_perfil_lectura"),
    ]

    operations = [
        migrations.RunPython(
            create_bulk_registration_permission,
            migrations.RunPython.noop,
        ),
    ]
