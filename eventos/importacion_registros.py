import csv
import io
import unicodedata
from collections import defaultdict
from zipfile import BadZipFile

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from usuarios.models import Usuario
from .models import Evento, Registro


MAX_IMPORT_ROWS = 5000


def normalize_event_name(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


def _read_csv(uploaded_file):
    content = uploaded_file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _read_xlsx(uploaded_file):
    workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    try:
        return [list(row) for row in workbook.active.iter_rows(values_only=True)]
    finally:
        workbook.close()


def read_registration_rows(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    try:
        rows = _read_csv(uploaded_file) if extension == "csv" else _read_xlsx(uploaded_file)
    except (csv.Error, UnicodeDecodeError, OSError, ValueError) as error:
        raise ValidationError(
            "No se pudo leer el archivo. Verifica que sea un CSV o Excel válido."
        ) from error
    except (BadZipFile, InvalidFileException, KeyError) as error:
        raise ValidationError(
            "No se pudo leer el archivo Excel. Verifica que el libro no esté dañado."
        ) from error

    if not rows:
        raise ValidationError("El archivo está vacío.")

    headers = [
        str(value).strip().lower() if value is not None else ""
        for value in rows[0]
    ]
    if len(headers) != len(set(headers)):
        raise ValidationError("El archivo contiene nombres de columnas repetidos.")
    missing_columns = [
        column for column in ("evento", "matricula") if column not in headers
    ]
    if missing_columns:
        raise ValidationError(
            "Faltan las columnas requeridas: " + ", ".join(missing_columns) + "."
        )

    evento_index = headers.index("evento")
    matricula_index = headers.index("matricula")
    equipo_index = headers.index("equipo") if "equipo" in headers else None
    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        if row_number > MAX_IMPORT_ROWS + 1:
            raise ValidationError(
                f"El archivo supera el máximo de {MAX_IMPORT_ROWS} filas de datos."
            )

        evento = row[evento_index] if evento_index < len(row) else None
        matricula = row[matricula_index] if matricula_index < len(row) else None
        equipo = row[equipo_index] if equipo_index is not None and equipo_index < len(row) else None
        if isinstance(matricula, float) and matricula.is_integer():
            matricula = int(matricula)
        records.append({
            "evento": str(evento).strip() if evento is not None else "",
            "matricula": str(matricula).strip() if matricula is not None else "",
            "equipo": str(equipo).strip() if equipo is not None else "",
            "row_number": row_number,
        })
    return records


def import_registros(uploaded_file):
    rows = read_registration_rows(uploaded_file)
    created_count = 0
    skipped_count = 0
    errors = []
    seen = defaultdict(int)
    eventos_por_nombre = defaultdict(list)
    for evento in Evento.objects.all():
        eventos_por_nombre[normalize_event_name(evento.nombre)].append(evento)

    for record in rows:
        row_number = record["row_number"]
        event_name = record["evento"]
        matricula = record["matricula"]
        if not event_name:
            errors.append({"row": row_number, "detail": "evento es obligatorio."})
            continue
        matching_events = eventos_por_nombre.get(normalize_event_name(event_name), [])
        if not matching_events:
            errors.append({
                "row": row_number,
                "detail": "evento no encontrado por nombre.",
            })
            continue
        if len(matching_events) > 1:
            errors.append({
                "row": row_number,
                "detail": "nombre de evento ambiguo; coincide con más de un evento.",
            })
            continue
        evento = matching_events[0]
        if not matricula:
            errors.append({"row": row_number, "detail": "matricula es obligatoria."})
            continue

        registration_key = (evento.pk, matricula.casefold())
        if registration_key in seen:
            errors.append({
                "row": row_number,
                "detail": f"evento y matricula repetidos en fila {seen[registration_key]}.",
            })
            continue
        seen[registration_key] = row_number

        usuarios = list(
            Usuario.objects.filter(matricula__iexact=matricula).only("pk")[:2]
        )
        if not usuarios:
            errors.append({
                "row": row_number,
                "detail": "matricula no encontrada.",
            })
            continue
        if len(usuarios) > 1:
            errors.append({
                "row": row_number,
                "detail": "matricula asociada a más de un usuario.",
            })
            continue

        usuario = usuarios[0]
        equipo = record["equipo"] or None
        try:
            with transaction.atomic():
                _, created = Registro.objects.get_or_create(
                    evento=evento,
                    usuario=usuario,
                    defaults={"equipo": equipo},
                )
        except IntegrityError:
            errors.append({
                "row": row_number,
                "detail": "no se pudo guardar el registro.",
            })
            continue

        if created:
            created_count += 1
        else:
            skipped_count += 1

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "error_count": len(errors),
        "errors": errors,
    }
