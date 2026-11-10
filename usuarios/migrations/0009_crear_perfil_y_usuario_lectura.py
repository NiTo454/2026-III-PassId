from django.contrib.auth.hashers import is_password_usable, make_password
from django.db import migrations


READ_PERMISSIONS = (
    ("core", "view_home", "Ver página principal"),
    ("usuario", "view_permiso", "Ver permisos"),
    ("usuario", "view_perfil", "Ver perfiles"),
    ("usuario", "view_usuario", "Ver usuarios"),
    ("carrera", "view_carrera", "Ver carreras"),
    ("aula", "view_aula", "Ver aulas"),
    ("materia", "view_materia", "Ver materias"),
    ("horario", "view_horario", "Ver horarios"),
    ("horario", "view_carga_academica", "Ver carga académica"),
    ("inscripcion", "view_inscripcion", "Ver inscripciones"),
    ("asistencia_clase", "ver_mi_asistencia", "Consultar la asistencia propia"),
    ("asistencia_clase", "view_progreso_asistencia", "Ver progreso de asistencia"),
    ("asistencia_clase", "ver_historial", "Consultar historial de asistencia"),
    ("evento", "view_evento", "Ver eventos"),
    ("evento", "view_eventos_disponibles", "Consultar eventos disponibles"),
    ("registro", "view_registro", "Ver registros a eventos"),
    ("asistencia", "view_asistencia", "Ver asistencias de eventos"),
    ("asistencia_qr", "ver_mi_qr", "Consultar el QR propio de asistencia"),
    ("asistencia_qr", "ver_asistencias", "Consultar asistencias de clase"),
)


def create_read_only_profile_and_user(apps, schema_editor):
    database = schema_editor.connection.alias
    Permiso = apps.get_model("usuarios", "Permiso")
    Perfil = apps.get_model("usuarios", "Perfil")
    PerfilTienePermiso = apps.get_model("usuarios", "PerfilTienePermiso")
    Usuario = apps.get_model("usuarios", "Usuario")
    UsuarioTienePerfil = apps.get_model("usuarios", "UsuarioTienePerfil")
    UsuarioTienePermiso = apps.get_model("usuarios", "UsuarioTienePermiso")

    profile, _ = Perfil.objects.using(database).get_or_create(nombre="lectura")
    permission_ids = []
    for tipo, codename, nombre in READ_PERMISSIONS:
        permission, _ = Permiso.objects.using(database).update_or_create(
            codename=codename,
            defaults={"tipo": tipo, "nombre": nombre},
        )
        permission_ids.append(permission.pk)

    PerfilTienePermiso.objects.using(database).filter(
        perfil_id=profile.pk,
    ).exclude(permiso_id__in=permission_ids).delete()
    PerfilTienePermiso.objects.using(database).bulk_create(
        [
            PerfilTienePermiso(
                perfil_id=profile.pk,
                permiso_id=permission_id,
            )
            for permission_id in permission_ids
        ],
        ignore_conflicts=True,
    )

    email = "lectura@passid.invalid"
    user = Usuario.objects.using(database).filter(username="lectura").first()
    if user is None:
        user = Usuario.objects.using(database).create(
            username="lectura",
            email=email,
            password=make_password(None),
            nombre="Usuario",
            apaterno="Lectura",
            amaterno="",
            whatsapp="No aplica",
            grupo="",
            activo=True,
            is_superuser=False,
        )
    elif (
        user.email != email
        or user.is_superuser
        or is_password_usable(user.password)
    ):
        raise RuntimeError(
            "Ya existe una cuenta 'lectura' con datos propios. "
            "Renómbrala o resuelve el conflicto antes de aplicar esta migración."
        )

    UsuarioTienePerfil.objects.using(database).filter(
        usuario_id=user.pk,
    ).exclude(perfil_id=profile.pk).delete()
    UsuarioTienePerfil.objects.using(database).get_or_create(
        usuario_id=user.pk,
        perfil_id=profile.pk,
    )
    UsuarioTienePermiso.objects.using(database).filter(usuario_id=user.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0007_passwordreset_creado_en"),
        ("usuarios", "0008_reconstruir_permisos_perfiles"),
    ]

    operations = [
        migrations.RunPython(
            create_read_only_profile_and_user,
            migrations.RunPython.noop,
        ),
    ]
