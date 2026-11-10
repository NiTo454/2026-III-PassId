from django.db import migrations


PERMISSIONS = {
    "add_permiso": ("usuario", "Agregar permiso"),
    "change_permiso": ("usuario", "Cambiar permiso"),
    "delete_permiso": ("usuario", "Eliminar permiso"),
    "view_permiso": ("usuario", "Ver permiso"),
    "list_permiso": ("usuario", "Listar permisos"),
    "add_perfil": ("usuario", "Agregar perfil"),
    "change_perfil": ("usuario", "Cambiar perfil"),
    "delete_perfil": ("usuario", "Eliminar perfil"),
    "view_perfil": ("usuario", "Ver perfil"),
    "list_perfil": ("usuario", "Listar perfiles"),
    "add_usuario": ("usuario", "Agregar usuario"),
    "change_usuario": ("usuario", "Cambiar usuario"),
    "delete_usuario": ("usuario", "Eliminar usuario"),
    "view_usuario": ("usuario", "Ver usuario"),
    "list_usuario": ("usuario", "Listar usuarios"),
    "add_usuario_masivo": ("usuario", "Agregar usuarios de forma masiva"),
    "change_mi_perfil": ("usuario", "Cambiar mi perfil"),
    "change_password": ("usuario", "Cambiar mi contraseña"),
    "view_home": ("core", "Ver página principal"),
    "view_evento": ("evento", "Ver eventos"),
    "admin": ("horario", "Administrar horarios de todos los profesores"),
    "ver_mi_qr": ("asistencia_qr", "Consultar el QR propio de asistencia"),
    "escanear_asistencia": ("asistencia_qr", "Registrar asistencia mediante QR"),
    "ver_asistencias": ("asistencia_qr", "Consultar asistencias de clase"),
    "add_registro": ("registro", "Agregar registro a evento"),
    "change_registro": ("registro", "Cambiar registro a evento"),
    "delete_registro": ("registro", "Eliminar registro a evento"),
    "view_registro": ("registro", "Ver registros a eventos"),
}

BASE_PERMISSIONS = (
    "core.view_home",
    "usuario.change_mi_perfil",
    "usuario.change_password",
    "evento.view_evento",
)

PROFILE_PERMISSIONS = {
    "basico": BASE_PERMISSIONS,
    "alumno": BASE_PERMISSIONS + (
        "otro.autorregistrarse",
        "asistencia_qr.ver_mi_qr",
        "asistencia_clase.ver_mi_asistencia",
        "asistencia_clase.view_progreso_asistencia",
    ),
    "profesor": BASE_PERMISSIONS + (
        "horario.view_carga_academica",
        "horario.manage_disponibilidad",
        "asistencia_clase.pasar_lista",
        "asistencia_clase.ver_historial",
        "asistencia_qr.escanear_asistencia",
        "asistencia_qr.ver_asistencias",
    ),
    "qa": BASE_PERMISSIONS + (
        "registro.view_registro",
        "asistencia.view_asistencia",
        "carrera.view_carrera",
        "aula.view_aula",
        "materia.view_materia",
        "horario.view_horario",
        "horario.view_carga_academica",
        "inscripcion.view_inscripcion",
        "asistencia_clase.ver_mi_asistencia",
        "asistencia_clase.view_progreso_asistencia",
        "asistencia_qr.ver_mi_qr",
    ),
}

DEV_PERMISSION_TYPES = {
    "core",
    "evento",
    "registro",
    "asistencia",
    "reporte",
    "carrera",
    "aula",
    "materia",
    "horario",
    "inscripcion",
    "asistencia_clase",
    "asistencia_qr",
}


def rebuild_profile_permissions(apps, schema_editor):
    Permiso = apps.get_model("usuarios", "Permiso")
    Perfil = apps.get_model("usuarios", "Perfil")
    PerfilTienePermiso = apps.get_model("usuarios", "PerfilTienePermiso")
    database = schema_editor.connection.alias

    permissions = {}
    for codename, (tipo, nombre) in PERMISSIONS.items():
        permission, _ = Permiso.objects.using(database).update_or_create(
            codename=codename,
            defaults={"tipo": tipo, "nombre": nombre},
        )
        permissions[f"{tipo}.{codename}"] = permission

    dev_permissions = Permiso.objects.using(database).filter(
        tipo__in=DEV_PERMISSION_TYPES,
    ).exclude(tipo="horario", codename="admin")
    profile_permissions = {
        **PROFILE_PERMISSIONS,
        "dev": BASE_PERMISSIONS + tuple(
            f"{permission.tipo}.{permission.codename}"
            for permission in dev_permissions
        ),
    }

    for profile_name, permission_names in profile_permissions.items():
        profile = Perfil.objects.using(database).filter(
            nombre__iexact=profile_name,
        ).first()
        if profile is None:
            raise RuntimeError(
                f"No se encontró el perfil '{profile_name}' para asignarle permisos."
            )

        PerfilTienePermiso.objects.using(database).filter(
            perfil_id=profile.pk,
        ).delete()

        for permission_name in permission_names:
            tipo, codename = permission_name.split(".", 1)
            permission = permissions.get(permission_name)
            if permission is None:
                permission = Permiso.objects.using(database).filter(
                    tipo=tipo,
                    codename=codename,
                ).first()
            if permission is None:
                raise RuntimeError(
                    f"No se encontró el permiso '{permission_name}' "
                    f"para asignarlo al perfil '{profile_name}'."
                )
            PerfilTienePermiso.objects.using(database).get_or_create(
                perfil_id=profile.pk,
                permiso_id=permission.pk,
            )

    admin = Perfil.objects.using(database).filter(nombre__iexact="admin").first()
    if admin is None:
        raise RuntimeError(
            "No se encontró el perfil 'admin' para asignarle todos los permisos."
        )
    PerfilTienePermiso.objects.using(database).filter(perfil_id=admin.pk).delete()
    PerfilTienePermiso.objects.using(database).bulk_create(
        [
            PerfilTienePermiso(perfil_id=admin.pk, permiso_id=permission.pk)
            for permission in Permiso.objects.using(database).all()
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("asistencia_qr", "0001_seed_permissions"),
        ("usuarios", "0006_asignar_permiso_autorregistro_alumno"),
    ]

    operations = [
        migrations.RunPython(
            rebuild_profile_permissions,
            migrations.RunPython.noop,
        ),
    ]
