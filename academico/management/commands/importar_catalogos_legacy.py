import os
from datetime import datetime

import pymysql
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academico.models import Aula, Carrera, Materia
from eventos.models import Evento


TABLAS_OMITIDAS = (
    "usuario",
    "usuario_tiene_perfil",
    "asistencia",
    "asistencia_clase",
    "registro",
    "inscripcion",
    "password_reset",
    "perfil_tiene_permiso",
)


class Command(BaseCommand):
    help = (
        "Importa catalogos de oferta academica (carrera, aula, materia) y "
        "datos generales de eventos desde la base de datos MySQL legacy Pasaporte2. "
        "Omite deliberadamente usuarios, perfiles, asistencias e inscripciones."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la importacion mostrando una previsualizacion detallada sin guardar cambios en la base de datos.",
        )
        parser.add_argument(
            "--legacy-host",
            dest="legacy_host",
            default=os.environ.get("LEGACY_DB_HOST", "127.0.0.1"),
            help="Host de MySQL de Pasaporte2 (default: 127.0.0.1 o $LEGACY_DB_HOST).",
        )
        parser.add_argument(
            "--legacy-port",
            dest="legacy_port",
            type=int,
            default=int(os.environ.get("LEGACY_DB_PORT", "3307")),
            help="Puerto de MySQL de Pasaporte2 (default: 3307 o $LEGACY_DB_PORT).",
        )
        parser.add_argument(
            "--legacy-db",
            dest="legacy_db",
            default=os.environ.get("LEGACY_DB_NAME", "polysit"),
            help="Nombre de base de datos de Pasaporte2 (default: polysit o $LEGACY_DB_NAME).",
        )
        parser.add_argument(
            "--legacy-user",
            dest="legacy_user",
            default=os.environ.get("LEGACY_DB_USER", "root"),
            help="Usuario de MySQL de Pasaporte2 (default: root o $LEGACY_DB_USER).",
        )
        parser.add_argument(
            "--legacy-password",
            dest="legacy_password",
            default=os.environ.get("LEGACY_DB_PASSWORD", "root"),
            help="Contrasena de MySQL de Pasaporte2 (default: root o $LEGACY_DB_PASSWORD).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        legacy_host = options["legacy_host"]
        legacy_port = options["legacy_port"]
        legacy_db = options["legacy_db"]
        legacy_user = options["legacy_user"]
        legacy_password = options["legacy_password"]

        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.MIGRATE_HEADING("  COMANDO DE IMPORTACION DE CATALOGOS LEGACY (Pasaporte2)")
        )
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    " [MODO DRY-RUN ACTIVO] Previsualizacion activada. NO se guardara ningun cambio en la base de datos.\n"
                )
            )

        self.stdout.write(
            f" Conectando a Pasaporte2: {legacy_user}@{legacy_host}:{legacy_port}/{legacy_db}"
        )
        self.stdout.write(
            self.style.NOTICE(
                " Tablas deliberadamente omitidas: " + ", ".join(TABLAS_OMITIDAS)
            )
        )
        self.stdout.write("-" * 70)


        legacy_conn = self.conectar_legacy(
            host=legacy_host,
            port=legacy_port,
            db=legacy_db,
            user=legacy_user,
            password=legacy_password,
        )

        try:

            datos_legacy = self.extraer_datos(legacy_conn)
        finally:
            legacy_conn.close()

        
        self.procesar_importacion(datos_legacy, dry_run=dry_run)

    def conectar_legacy(self, host, port, db, user, password):
        """Conecta a la base de datos MySQL de Pasaporte2 y fuerza modo de solo lectura."""
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                read_timeout=30,
            )
            
            with conn.cursor() as cur:
                try:
                    cur.execute("SET SESSION TRANSACTION READ ONLY;")
                except Exception:
                    cur.execute("SET TRANSACTION READ ONLY;")
            self.stdout.write(self.style.SUCCESS(" [OK] Conexion de solo lectura establecida con exito."))
            return conn
        except Exception as error:
            raise CommandError(
                f"Error al conectar con la base de datos Pasaporte2 en {host}:{port}/{db}: {error}"
            ) from error

    def extraer_datos(self, conn):
    
        datos = {}
        with conn.cursor() as cur:
           
            self.stdout.write(" Extrayendo 'carrera' de Pasaporte2...")
            cur.execute("SELECT * FROM carrera ORDER BY id ASC;")
            datos["carrera"] = cur.fetchall()

        
            self.stdout.write(" Extrayendo 'aula' de Pasaporte2...")
            cur.execute("SELECT * FROM aula ORDER BY id ASC;")
            datos["aula"] = cur.fetchall()

            
            self.stdout.write(" Extrayendo 'materia' de Pasaporte2...")
            cur.execute("SELECT * FROM materia ORDER BY id ASC;")
            datos["materia"] = cur.fetchall()

            
            self.stdout.write(" Extrayendo 'evento' de Pasaporte2...")
            cur.execute("SELECT * FROM evento ORDER BY id ASC;")
            datos["evento"] = cur.fetchall()

        self.stdout.write(
            f" Registros leidos: {len(datos['carrera'])} carreras, "
            f"{len(datos['aula'])} aulas, "
            f"{len(datos['materia'])} materias, "
            f"{len(datos['evento'])} eventos."
        )
        self.stdout.write("-" * 70)
        return datos

    def procesar_importacion(self, datos, dry_run=False):
       
       
        with transaction.atomic():
            stats = {
                "carrera": {"creados": 0, "actualizados": 0, "omitidos": 0},
                "aula": {"creados": 0, "actualizados": 0, "omitidos": 0},
                "materia": {"creados": 0, "actualizados": 0, "omitidos": 0},
                "evento": {"creados": 0, "actualizados": 0, "omitidos": 0},
            }

            carrera_id_map = {}

           
            self.stdout.write(self.style.MIGRATE_LABEL("\n[1/4] Importando Catálogo: carrera ➔ Carrera"))
            for fila in datos.get("carrera", []):
                legacy_id = fila["id"]
                clave = str(fila.get("clave", "")).strip()
                nombre = str(fila.get("nombre", "")).strip()
                activa = bool(fila.get("activa", True))

                if not clave:
                    self.stdout.write(self.style.WARNING(f"   [OMITIR] Carrera ID {legacy_id} sin clave."))
                    stats["carrera"]["omitidos"] += 1
                    continue

                obj = Carrera.objects.filter(clave=clave).first()
                if obj:
                    cambios = []
                    if obj.nombre != nombre:
                        obj.nombre = nombre
                        cambios.append("nombre")
                    if obj.activa != activa:
                        obj.activa = activa
                        cambios.append("activa")
                    if cambios:
                        obj.save(update_fields=cambios)
                        stats["carrera"]["actualizados"] += 1
                        self.stdout.write(f"   [ACTUALIZAR] Carrera '{clave}' ({', '.join(cambios)})")
                    else:
                        stats["carrera"]["omitidos"] += 1
                        self.stdout.write(f"   [SIN CAMBIOS] Carrera '{clave}'")
                    carrera_id_map[legacy_id] = obj
                else:
                   
                    if not Carrera.objects.filter(id=legacy_id).exists():
                        obj = Carrera.objects.create(id=legacy_id, clave=clave, nombre=nombre, activa=activa)
                    else:
                        obj = Carrera.objects.create(clave=clave, nombre=nombre, activa=activa)
                    carrera_id_map[legacy_id] = obj
                    stats["carrera"]["creados"] += 1
                    self.stdout.write(self.style.SUCCESS(f"   [CREAR] Carrera '{clave}' - '{nombre}' (ID nuevo: {obj.id})"))

            self.stdout.write(self.style.MIGRATE_LABEL("\n[2/4] Importando Catálogo: aula ➔ Aula"))
            tipos_validos = {choice[0] for choice in Aula.TIPO_CHOICES}
            for fila in datos.get("aula", []):
                legacy_id = fila["id"]
                codigo = str(fila.get("codigo", "")).strip()
                edificio = fila.get("edificio")
                if edificio is not None:
                    edificio = str(edificio).strip()
                capacidad = fila.get("capacidad")
                tipo = str(fila.get("tipo", "aula")).strip().lower()
                if tipo not in tipos_validos:
                    tipo = "otro"
                activa = bool(fila.get("activa", True))

                if not codigo:
                    self.stdout.write(self.style.WARNING(f"   [OMITIR] Aula ID {legacy_id} sin codigo."))
                    stats["aula"]["omitidos"] += 1
                    continue

                obj = Aula.objects.filter(codigo=codigo).first()
                if obj:
                    cambios = []
                    if obj.edificio != edificio:
                        obj.edificio = edificio
                        cambios.append("edificio")
                    if obj.capacidad != capacidad:
                        obj.capacidad = capacidad
                        cambios.append("capacidad")
                    if obj.tipo != tipo:
                        obj.tipo = tipo
                        cambios.append("tipo")
                    if obj.activa != activa:
                        obj.activa = activa
                        cambios.append("activa")
                    if cambios:
                        obj.save(update_fields=cambios)
                        stats["aula"]["actualizados"] += 1
                        self.stdout.write(f"   [ACTUALIZAR] Aula '{codigo}' ({', '.join(cambios)})")
                    else:
                        stats["aula"]["omitidos"] += 1
                        self.stdout.write(f"   [SIN CAMBIOS] Aula '{codigo}'")
                else:
                    if not Aula.objects.filter(id=legacy_id).exists():
                        obj = Aula.objects.create(
                            id=legacy_id,
                            codigo=codigo,
                            edificio=edificio,
                            capacidad=capacidad,
                            tipo=tipo,
                            activa=activa,
                        )
                    else:
                        obj = Aula.objects.create(
                            codigo=codigo,
                            edificio=edificio,
                            capacidad=capacidad,
                            tipo=tipo,
                            activa=activa,
                        )
                    stats["aula"]["creados"] += 1
                    self.stdout.write(self.style.SUCCESS(f"   [CREAR] Aula '{codigo}' - Tipo: {tipo} (ID: {obj.id})"))

            self.stdout.write(self.style.MIGRATE_LABEL("\n[3/4] Importando Catálogo: materia ➔ Materia (con carrera_id)"))
            for fila in datos.get("materia", []):
                legacy_id = fila["id"]
                clave = str(fila.get("clave", "")).strip()
                nombre = str(fila.get("nombre", "")).strip()
              
                asistencias = fila.get("asistencias")
                if asistencias is None:
                    asistencias = fila.get("creditos", 0)
                asistencias = int(asistencias or 0)
                horas_semana = int(fila.get("horas_semana") or 0)
                
                periodo = fila.get("periodo")
                if periodo is None and fila.get("cuatrimestre") is not None:
                    periodo = str(fila.get("cuatrimestre"))
                if periodo is not None:
                    periodo = str(periodo).strip()
                activa = bool(fila.get("activa", True))

                
                legacy_carrera_id = fila.get("carrera_id")
                carrera_obj = None
                if legacy_carrera_id:
                    carrera_obj = carrera_id_map.get(legacy_carrera_id)
                    if not carrera_obj:
                        carrera_obj = Carrera.objects.filter(id=legacy_carrera_id).first()

                if not clave:
                    self.stdout.write(self.style.WARNING(f"   [OMITIR] Materia ID {legacy_id} sin clave."))
                    stats["materia"]["omitidos"] += 1
                    continue

                obj = Materia.objects.filter(clave=clave).first()
                if obj:
                    cambios = []
                    if obj.nombre != nombre:
                        obj.nombre = nombre
                        cambios.append("nombre")
                    if obj.asistencias != asistencias:
                        obj.asistencias = asistencias
                        cambios.append("asistencias")
                    if obj.horas_semana != horas_semana:
                        obj.horas_semana = horas_semana
                        cambios.append("horas_semana")
                    if obj.periodo != periodo:
                        obj.periodo = periodo
                        cambios.append("periodo")
                    if obj.carrera != carrera_obj:
                        obj.carrera = carrera_obj
                        cambios.append("carrera")
                    if obj.activa != activa:
                        obj.activa = activa
                        cambios.append("activa")
                    if cambios:
                        obj.save(update_fields=cambios)
                        stats["materia"]["actualizados"] += 1
                        self.stdout.write(f"   [ACTUALIZAR] Materia '{clave}' ({', '.join(cambios)})")
                    else:
                        stats["materia"]["omitidos"] += 1
                        self.stdout.write(f"   [SIN CAMBIOS] Materia '{clave}'")
                else:
                    materia_kwargs = {
                        "clave": clave,
                        "nombre": nombre,
                        "asistencias": asistencias,
                        "horas_semana": horas_semana,
                        "periodo": periodo,
                        "carrera": carrera_obj,
                        "activa": activa,
                    }
                    if not Materia.objects.filter(id=legacy_id).exists():
                        materia_kwargs["id"] = legacy_id
                    obj = Materia.objects.create(**materia_kwargs)
                    stats["materia"]["creados"] += 1
                    carrera_info = f"Carrera: {carrera_obj.clave}" if carrera_obj else "Sin carrera"
                    self.stdout.write(
                        self.style.SUCCESS(f"   [CREAR] Materia '{clave}' - '{nombre}' ({carrera_info}) (ID: {obj.id})")
                    )

        
            self.stdout.write(self.style.MIGRATE_LABEL("\n[4/4] Importando Catálogo: evento ➔ Evento (datos generales)"))
            for fila in datos.get("evento", []):
                legacy_id = fila["id"]
                nombre = str(fila.get("nombre", "")).strip()
                fecha_hora = fila.get("fecha_hora")
                if isinstance(fecha_hora, str):
                    try:
                        fecha_hora = datetime.fromisoformat(fecha_hora)
                    except ValueError:
                        pass
                if fecha_hora and isinstance(fecha_hora, datetime) and timezone.is_naive(fecha_hora):
                    fecha_hora = timezone.make_aware(fecha_hora, timezone.get_current_timezone())

                lugar = fila.get("lugar")
                if lugar is not None:
                    lugar = str(lugar).strip()
                requiere_registro = (
                    bool(fila.get("requiere_registro"))
                    if fila.get("requiere_registro") is not None
                    else True
                )
                permitir_autorregistro = (
                    bool(fila.get("permitir_autorregistro"))
                    if fila.get("permitir_autorregistro") is not None
                    else True
                )
                responsable_interno = fila.get("responsable_interno")
                if responsable_interno is not None:
                    responsable_interno = str(responsable_interno).strip()
                responsable_externo = fila.get("responsable_externo")
                if responsable_externo is not None:
                    responsable_externo = str(responsable_externo).strip()

                if not nombre or not fecha_hora:
                    self.stdout.write(self.style.WARNING(f"   [OMITIR] Evento ID {legacy_id} incompleto (nombre o fecha_hora faltante)."))
                    stats["evento"]["omitidos"] += 1
                    continue

                obj = Evento.objects.filter(id=legacy_id).first()
                if not obj:
                    obj = Evento.objects.filter(nombre=nombre, fecha_hora=fecha_hora).first()

                if obj:
                    cambios = []
                    if obj.nombre != nombre:
                        obj.nombre = nombre
                        cambios.append("nombre")
                    if obj.fecha_hora != fecha_hora:
                        obj.fecha_hora = fecha_hora
                        cambios.append("fecha_hora")
                    if obj.lugar != lugar:
                        obj.lugar = lugar
                        cambios.append("lugar")
                    if obj.requiere_registro != requiere_registro:
                        obj.requiere_registro = requiere_registro
                        cambios.append("requiere_registro")
                    if obj.permitir_autorregistro != permitir_autorregistro:
                        obj.permitir_autorregistro = permitir_autorregistro
                        cambios.append("permitir_autorregistro")
                    if obj.responsable_interno != responsable_interno:
                        obj.responsable_interno = responsable_interno
                        cambios.append("responsable_interno")
                    if obj.responsable_externo != responsable_externo:
                        obj.responsable_externo = responsable_externo
                        cambios.append("responsable_externo")
                    if cambios:
                        obj.save(update_fields=cambios)
                        stats["evento"]["actualizados"] += 1
                        self.stdout.write(f"   [ACTUALIZAR] Evento '{nombre}' ({', '.join(cambios)})")
                    else:
                        stats["evento"]["omitidos"] += 1
                        self.stdout.write(f"   [SIN CAMBIOS] Evento '{nombre}'")
                else:
                    evento_kwargs = {
                        "nombre": nombre,
                        "fecha_hora": fecha_hora,
                        "lugar": lugar,
                        "requiere_registro": requiere_registro,
                        "permitir_autorregistro": permitir_autorregistro,
                        "responsable_interno": responsable_interno,
                        "responsable_externo": responsable_externo,
                    }
                    if not Evento.objects.filter(id=legacy_id).exists():
                        evento_kwargs["id"] = legacy_id
                    obj = Evento.objects.create(**evento_kwargs)
                    stats["evento"]["creados"] += 1
                    self.stdout.write(self.style.SUCCESS(f"   [CREAR] Evento '{nombre}' ({fecha_hora}) (ID: {obj.id})"))

           
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.MIGRATE_HEADING(" RESUMEN DE PROCESAMIENTO"))
            self.stdout.write("=" * 70)
            for catalogo, res in stats.items():
                self.stdout.write(
                    f" - {catalogo.capitalize():<10}: "
                    f"Creados: {res['creados']:<4} | "
                    f"Actualizados: {res['actualizados']:<4} | "
                    f"Sin cambios/Omitidos: {res['omitidos']:<4}"
                )
            self.stdout.write(
                self.style.NOTICE(
                    "\n [VERIFICACION] Tablas deliberadamente omitidas y protegidas: "
                    + ", ".join(TABLAS_OMITIDAS)
                )
            )

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING(
                        "\n [DRY-RUN EXITOSO] Previsualizacion concluida. Rollback aplicado; ningun dato fue modificado."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "\n [IMPORTACION EXITOSA] Los catalogos y eventos han sido transferidos correctamente."
                    )
                )
