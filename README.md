# PassId (2026-III-PassId)

Plataforma universitaria para la gestion de accesos, pasaporte de eventos extracurriculares y control de asistencia a clases mediante codigos QR, desarrollada para la Universidad Tecnologica del Valle de Mexico (UTVAM).

Este proyecto corresponde a la migracion y reingenieria del sistema legacy Pasaporte2 (PHP/MySQL) hacia una arquitectura moderna, escalable y mantenible basada en Python y Django.

---

## 1. Stack Tecnologico y Dependencias

### Tecnologias Base
- Lenguaje: Python 3.11+
- Framework Web: Django 5.x / 6.x
- Sistema Gestor de Base de Datos: MySQL 8.x / MariaDB (con fallback a SQLite3 para entornos de prueba local)

### Librerias Principales
- **Django**: Framework web principal para la gestion de vistas, enrutamiento, seguridad y ORM.
- **python-dotenv**: Carga y gestion segura de variables de entorno desde archivos `.env`, evitando la exposicion de credenciales y claves secretas en el control de versiones.
- **mysqlclient**: Driver nativo de alto rendimiento en C para la comunicacion entre Django y el servidor MySQL.
- **bcrypt**: Algoritmo de hashing criptografico para validar y migrar las contraseñas generadas previamente por `password_hash()` en PHP sin forzar el reinicio de contraseñas de los usuarios existentes.
- **sqlparse**: Motor de formateo y analisis sintactico de sentencias SQL utilizado internamente por el subsistema de migraciones de Django.
- **asgiref**: Interfaz estandar ASGI para interoperabilidad asincrona en Python.

---

## 2. Variables de Entorno (.env)

El proyecto utiliza `python-dotenv` para aislar la configuracion sensible del entorno. Para configurar el proyecto en un entorno local o de produccion, cree un archivo `.env` en la raiz del proyecto basado en la siguiente plantilla:

```ini
# Configuracion General de Django
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Configuracion de Conexion a Base de Datos (MySQL)
DB_ENGINE=django.db.backends.mysql
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

# Configuracion Regional
LANGUAGE_CODE=es-mx
TIME_ZONE=America/Mexico_City
```

---

## 3. Arquitectura Modular del Sistema

El proyecto esta organizado bajo una arquitectura de aplicaciones desacopladas, asegurando alta cohesion y mantenibilidad:

```text
2026-III-PassId/
|-- core/                  # Configuracion central del proyecto (settings, urls, wsgi, asgi)
|-- usuarios/              # Autenticacion, usuarios institucionales, perfiles y permisos
|-- academico/             # Carreras, aulas, materias, horarios, inscripciones y asistencia QR
|-- eventos/               # Eventos institucionales, pre-registro, control de acceso y reportes
|-- docs/                  # Documentacion de diseño tecnico y matriz de migracion
|-- manage.py              # Script utilitario de administracion de Django
|-- requirements.txt       # Declaracion formal de dependencias de Python
|-- .env.example           # Plantilla de variables de entorno
`-- README.md              # Documentacion general del repositorio
```

---

## 4. Especificacion de Modelos de Datos (ORM)

El sistema integra 18 modelos que cubren la totalidad de los datos y reglas de negocio del sistema anterior:

### Aplicacion: usuarios
- **Usuario** (`db_table: usuario`): Custom User Model que hereda de `AbstractBaseUser`. Preserva los atributos institucionales (`matricula`, `grupo`, `categoria`, `whatsapp`, `nombre`, `apaterno`, `amaterno`, `activo`, `superusuario`).
- **Perfil** (`db_table: perfil`): Catálogo de roles institucionales (admin, profesor, alumno, dev, qa).
- **Permiso** (`db_table: permiso`): Permisos atomicos del sistema (`tipo.codename`).
- **PerfilTienePermiso** (`db_table: perfil_tiene_permiso`): Tabla intermedia para la relacion N:M de permisos asignados a cada rol.
- **UsuarioTienePerfil** (`db_table: usuario_tiene_perfil`): Tabla intermedia para la asignacion de roles a usuarios.
- **UsuarioTienePermiso** (`db_table: usuario_tiene_permiso`): Permisos directos otorgados a usuarios individuales.
- **PasswordReset** (`db_table: password_reset`): Tokens de recuperacion de contraseñas con expiracion temporal.

### Aplicacion: academico
- **Carrera** (`db_table: carrera`): Programas academicos universitarios (`clave`, `nombre`, `activa`).
- **Aula** (`db_table: aula`): Espacios fisicos (`codigo`, `edificio`, `capacidad`, `tipo`).
- **Materia** (`db_table: materia`): Asignaturas vinculadas a carrera, con horas semanales y meta minima de asistencias.
- **Horario** (`db_table: horario`): Asignacion de docente, materia, aula, grupo y horarios. Incluye `UniqueConstraint` para prevenir colisiones de espacio y tiempo.
- **ProfesorDisponibilidad** (`db_table: profesor_disponibilidad`): Bloques horarios de disponibilidad docente por ciclo escolar.
- **Inscripcion** (`db_table: inscripcion`): Alumnos inscritos en materia, grupo y periodo.
- **AsistenciaClase** (`db_table: asistencia_clase`): Pase de lista por sesion con soporte para lectura de codigos QR y registro manual, contemplando estados (`presente`, `retardo`, `falta`, `justificado`).

### Aplicacion: eventos
- **Evento** (`db_table: evento`): Catálogo general de eventos institucionales y del pasaporte.
- **Registro** (`db_table: registro`): Pre-registro de asistentes y equipos participantes.
- **Asistencia** (`db_table: asistencia`): Registro de acceso real con auditoria del personal staff escaneador.
- **ResponsableEvento** (`db_table: responsable_evento`): Personal a cargo de la coordinacion del evento.
- **ReporteEventos** (`db_table: reporte_eventos`): Modelo no gestionado (`managed = False`) para consultar la vista SQL de metricas por evento.
- **ReporteUsuarios** (`db_table: reporte_usuarios`): Modelo no gestionado (`managed = False`) para metricas de participacion por alumno.

---

## 5. Guia de Instalacion y Ejecucion Local

### 1. Clonar el repositorio
```bash
git clone https://github.com/NiTo454/2026-III-PassId.git
cd 2026-III-PassId
```

### 2. Creacion y activacion del entorno virtual
En Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

En Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalacion de dependencias
```bash
pip install -r requirements.txt
```

### 4. Configuracion de variables de entorno
Copie el archivo de ejemplo y configure los accesos a su base de datos local:
```bash
cp .env.example .env
```

### 5. Ejecutar migraciones del ORM
```bash
python manage.py migrate
```

### 6. Creacion de usuario administrador
```bash
python manage.py createsuperuser
```

### 7. Iniciar el servidor de desarrollo
```bash
python manage.py runserver
```
El panel de administracion estara disponible en: `http://127.0.0.1:8000/admin/`

---

## 6. Organizacion de Ramas en el Repositorio

El flujo de trabajo sigue una estrategia modular de integracion continua mediante Pull Requests:

- **main**: Rama principal de produccion y despliegue.
- **feature/orm-usuarios**: Desarrollo y pruebas del modulo de usuarios, roles y autenticacion.
- **feature/orm-academico**: Desarrollo y pruebas del modulo academico, horarios y asistencias a clase.
- **feature/orm-eventos**: Desarrollo y pruebas del modulo de eventos, registros y pasaporte.
- **migracion**: Rama consolidada con todos los modelos y migraciones integrados.
- **docs/diseno-migracion**: Documento formal de diseño tecnico y matriz de equivalencias de campos.
- **readme**: Actualizacion y mantenimiento de la documentacion principal del proyecto.

---

## 7. Documentacion Tecnica Complementaria

Para revisar el analisis de normalizacion, el mapeo campo por campo y el orden de ejecucion ETL para la carga de datos sin conflictos de integridad referencial, consulte el documento:
- `docs/diseno_migracion_orm_django.md`

---
Universidad Tecnologica del Valle de Mexico (UTVAM) - 2026.
