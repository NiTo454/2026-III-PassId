from django.db import migrations


def asignar_permiso_autorregistro_alumno(apps, schema_editor):
    Permiso = apps.get_model("usuarios", "Permiso")
    Perfil = apps.get_model("usuarios", "Perfil")
    PerfilTienePermiso = apps.get_model("usuarios", "PerfilTienePermiso")
    database = schema_editor.connection.alias

    permiso = Permiso.objects.using(database).filter(
        codename="autorregistrarse", tipo="otro"
    ).first()

    if permiso is None:
        raise RuntimeError(
            "No se encontró el permiso 'otro.autorregistrarse'. "
            "Asegúrate de que la migración 0003 se haya aplicado."
        )

    perfil_alumno = Perfil.objects.using(database).filter(
        nombre__iexact="alumno"
    ).first()

    if perfil_alumno is None:
        raise RuntimeError(
            "No se encontró el perfil 'alumno' para asignarle "
            "otro.autorregistrarse."
        )

    PerfilTienePermiso.objects.using(database).get_or_create(
        perfil_id=perfil_alumno.pk,
        permiso_id=permiso.pk,
    )


def revertir(apps, schema_editor):
    Permiso = apps.get_model("usuarios", "Permiso")
    Perfil = apps.get_model("usuarios", "Perfil")
    PerfilTienePermiso = apps.get_model("usuarios", "PerfilTienePermiso")
    database = schema_editor.connection.alias

    permiso = Permiso.objects.using(database).filter(
        codename="autorregistrarse", tipo="otro"
    ).first()
    perfil_alumno = Perfil.objects.using(database).filter(
        nombre__iexact="alumno"
    ).first()

    if permiso and perfil_alumno:
        PerfilTienePermiso.objects.using(database).filter(
            perfil_id=perfil_alumno.pk,
            permiso_id=permiso.pk,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0005_asignar_permiso_progreso_alumno"),
    ]

    operations = [
        migrations.RunPython(
            asignar_permiso_autorregistro_alumno,
            revertir,
        ),
    ]
