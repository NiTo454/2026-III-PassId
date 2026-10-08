from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class Permiso(models.Model):
    """
    Catálogo de permisos atómicos del sistema clasificados por tipo/módulo.
    """
    id = models.BigAutoField(primary_key=True)
    tipo = models.CharField(max_length=100, verbose_name="Tipo / Módulo")
    codename = models.CharField(max_length=100, unique=True, verbose_name="Código")
    nombre = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nombre descriptivo")

    class Meta:
        db_table = "permiso"
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"
        ordering = ["tipo", "codename"]

    def __str__(self):
        return f"{self.tipo}.{self.codename} - {self.nombre or ''}"


class Perfil(models.Model):
    """
    Roles o perfiles agrupadores de permisos (ej. admin, profesor, alumno, dev).
    """
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, verbose_name="Nombre del perfil")
    permisos = models.ManyToManyField(
        Permiso,
        through="PerfilTienePermiso",
        related_name="perfiles",
        blank=True,
        verbose_name="Permisos asignados"
    )

    class Meta:
        db_table = "perfil"
        verbose_name = "Perfil / Rol"
        verbose_name_plural = "Perfiles / Roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def perms(self):
        """Retorna el QuerySet de permisos asignados al perfil eliminando duplicados en la consulta ORM."""
        return self.permisos.all().distinct()

    def tiene_permiso(self, perm_str: str) -> bool:
        """Verifica si el perfil cuenta con un permiso específico (ej. 'evento.add_evento' o 'evento.*')."""
        if "." in perm_str:
            tipo, codename = perm_str.split(".", 1)
            if codename == "*":
                return self.perms.filter(tipo=tipo).exists()
            return self.perms.filter(tipo=tipo, codename=codename).exists()
        return self.perms.filter(codename=perm_str).exists()


class PerfilTienePermiso(models.Model):
    """Tabla intermedia entre Perfil y Permiso."""
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, db_column="perfil_id")
    permiso = models.ForeignKey(Permiso, on_delete=models.RESTRICT, db_column="permiso_id")

    class Meta:
        db_table = "perfil_tiene_permiso"
        unique_together = (("perfil", "permiso"),)
        verbose_name = "Permiso de Perfil"
        verbose_name_plural = "Permisos de Perfiles"


class UsuarioManager(BaseUserManager):
    """Manager personalizado para la creación de usuarios y superusuarios."""
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio.")
        if not username:
            raise ValueError("El nombre de usuario es obligatorio.")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("activo", True)
        return self.create_user(username, email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de Usuario compatible con el sistema de autenticación de Django, PermissionsMixin
    y la base de datos de Pasaporte2.
    """
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True, verbose_name="Nombre de usuario")
    password = models.CharField(max_length=255, verbose_name="Contraseña")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    is_superuser = models.BooleanField(default=False, verbose_name="¿Superusuario?", db_column="superusuario")

    nombre = models.CharField(max_length=50, null=True, blank=True, verbose_name="Nombre(s)")
    apaterno = models.CharField(max_length=50, null=True, blank=True, verbose_name="Apellido Paterno")
    amaterno = models.CharField(max_length=50, null=True, blank=True, verbose_name="Apellido Materno")
    email = models.EmailField(max_length=50, unique=True, verbose_name="Correo institucional")
    categoria = models.CharField(max_length=50, null=True, blank=True, verbose_name="Categoría")
    whatsapp = models.CharField(max_length=50, verbose_name="WhatsApp / Teléfono")
    grupo = models.CharField(max_length=50, verbose_name="Grupo")
    matricula = models.CharField(max_length=50, null=True, blank=True, verbose_name="Matrícula")

    perfiles = models.ManyToManyField(
        Perfil,
        through="UsuarioTienePerfil",
        related_name="usuarios",
        blank=True
    )
    permisos_directos = models.ManyToManyField(
        Permiso,
        through="UsuarioTienePermiso",
        related_name="usuarios",
        blank=True
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "usuario"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["nombre", "apaterno", "amaterno"]

    def __str__(self):
        nombre_completo = f"{self.nombre or ''} {self.apaterno or ''} {self.amaterno or ''}".strip()
        return nombre_completo if nombre_completo else self.username

    @property
    def superusuario(self):
        return self.is_superuser

    @superusuario.setter
    def superusuario(self, value):
        self.is_superuser = value

    @property
    def is_staff(self):
        return self.is_superuser

    @property
    def is_active(self):
        return self.activo

    @property
    def perms(self):
        """
        Retorna el QuerySet consolidado y sin duplicados de todos los Permisos
        del usuario (tanto directos como heredados de sus perfiles/roles).
        """
        if self.is_superuser:
            return Permiso.objects.all().distinct()

        permisos_directos = Permiso.objects.filter(usuarios=self)
        permisos_perfil = Permiso.objects.filter(perfiles__usuarios=self)
        return (permisos_directos | permisos_perfil).distinct()

    def get_all_permissions(self, obj=None):
        """
        Retorna un conjunto (set) de nombres completos de permisos ('tipo.codename')
        del usuario sin duplicados para compatibilidad con la librería de permisos de Django.
        """
        if self.is_superuser:
            return set(f"{p.tipo}.{p.codename}" for p in Permiso.objects.all())
        return set(f"{p.tipo}.{p.codename}" for p in self.perms)

    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        if "." in perm:
            tipo, codename = perm.split(".", 1)
            if codename == "*":
                return self.perms.filter(tipo=tipo).exists()
            return self.perms.filter(tipo=tipo, codename=codename).exists()
        return self.perms.filter(codename=perm).exists()

    def has_module_perms(self, app_label):
        if self.is_superuser:
            return True
        return self.perms.filter(tipo=app_label).exists()


class UsuarioTienePerfil(models.Model):
    """Tabla intermedia entre Usuario y Perfil."""
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column="usuario_id")
    perfil = models.ForeignKey(Perfil, on_delete=models.RESTRICT, db_column="perfil_id")

    class Meta:
        db_table = "usuario_tiene_perfil"
        unique_together = (("usuario", "perfil"),)
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"


class UsuarioTienePermiso(models.Model):
    """Tabla intermedia para permisos directos asignados a un Usuario."""
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column="usuario_id")
    permiso = models.ForeignKey(Permiso, on_delete=models.RESTRICT, db_column="permiso_id")

    class Meta:
        db_table = "usuario_tiene_permiso"
        unique_together = (("usuario", "permiso"),)
        verbose_name = "Permiso directo de Usuario"
        verbose_name_plural = "Permisos directos de Usuarios"


class PasswordReset(models.Model):
    """Almacena tokens de recuperación de contraseñas con expiración temporal."""
    token = models.CharField(max_length=64, primary_key=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column="usuario_id")
    expira_en = models.DateTimeField(verbose_name="Fecha de expiración")

    class Meta:
        db_table = "password_reset"
        verbose_name = "Token de Recuperación"
        verbose_name_plural = "Tokens de Recuperación"

    def __str__(self):
        return f"Token de {self.usuario.username} (Expira: {self.expira_en})"
