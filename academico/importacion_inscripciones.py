import csv
import io
from collections import defaultdict
from zipfile import BadZipFile

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from usuarios.models import Usuario
from .models import Inscripcion, Materia


MAX_IMPORT_ROWS = 5000
MAX_REPORTED_ERRORS = 100
REQUIRED_COLUMNS = ("matricula", "clave_materia", "grupo", "periodo")


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


def _cell_text(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip() if value is not None else ""


def read_inscripcion_rows(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if extension not in {"csv", "xlsx"}:
        raise ValidationError("El archivo debe tener extensión .csv o .xlsx.")

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
        _cell_text(value).lower()
        for value in rows[0]
    ]
    if len(headers) != len(set(headers)):
        raise ValidationError("El archivo contiene nombres de columnas repetidos.")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        raise ValidationError(
            "Faltan columnas requeridas: " + ", ".join(missing_columns) + "."
        )

    indexes = {column: headers.index(column) for column in headers}
    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(_cell_text(value) for value in row):
            continue
        if row_number > MAX_IMPORT_ROWS + 1:
            raise ValidationError(
                f"El archivo supera el máximo de {MAX_IMPORT_ROWS} filas de datos."
            )

        record = {
            column: _cell_text(row[index]) if index < len(row) else ""
            for column, index in indexes.items()
        }
        record["row_number"] = row_number
        records.append(record)
    return records


def _lookup_ids_by_value(model, field_name, values):
    matches = defaultdict(list)
    unique_values = list(dict.fromkeys(value for value in values if value))
    for start in range(0, len(unique_values), 150):
        batch = unique_values[start:start + 150]
        query = Q()
        for value in batch:
            query |= Q(**{f"{field_name}__iexact": value})
        for object_id, value in model.objects.filter(query).values_list(
            "pk", field_name
        ):
            matches[str(value).strip().casefold()].append(object_id)
    return matches


def _parse_active(value):
    normalized = value.strip().casefold()
    if not normalized:
        return True
    if normalized in {"1", "true", "si", "sí", "s", "activa", "activo"}:
        return True
    if normalized in {"0", "false", "no", "n", "inactiva", "inactivo"}:
        return False
    raise ValueError("activa debe ser sí/no, 1/0 o quedar vacía.")


def import_inscripciones(uploaded_file):
    rows = read_inscripcion_rows(uploaded_file)
    usuarios = _lookup_ids_by_value(
        Usuario,
        "matricula",
        [record.get("matricula", "") for record in rows],
    )
    materias = _lookup_ids_by_value(
        Materia,
        "clave",
        [record.get("clave_materia", "") for record in rows],
    )

    created_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    seen = {}
    limits = {
        "matricula": Usuario._meta.get_field("matricula").max_length,
        "clave_materia": Materia._meta.get_field("clave").max_length,
        "grupo": Inscripcion._meta.get_field("grupo").max_length,
        "periodo": Inscripcion._meta.get_field("periodo").max_length,
    }

    def add_error(row_number, detail):
        nonlocal error_count
        error_count += 1
        if len(errors) < MAX_REPORTED_ERRORS:
            errors.append({"row": row_number, "detail": detail})

    for record in rows:
        row_number = record["row_number"]
        missing_values = [
            column for column in REQUIRED_COLUMNS if not record.get(column)
        ]
        if missing_values:
            add_error(
                row_number,
                "Campos obligatorios vacíos: " + ", ".join(missing_values) + ".",
            )
            continue

        too_long = [
            column for column, limit in limits.items()
            if len(record[column]) > limit
        ]
        if too_long:
            add_error(
                row_number,
                "El valor excede la longitud permitida para: "
                + ", ".join(too_long)
                + ".",
            )
            continue

        row_key = tuple(
            record[column].strip().casefold()
            for column in ("matricula", "clave_materia", "grupo", "periodo")
        )
        if row_key in seen:
            add_error(
                row_number,
                f"Inscripción repetida en el archivo (fila {seen[row_key]}).",
            )
            continue
        seen[row_key] = row_number

        try:
            activa = _parse_active(record.get("activa", ""))
        except ValueError as error:
            add_error(row_number, str(error))
            continue

        matching_users = usuarios.get(record["matricula"].casefold(), [])
        if not matching_users:
            add_error(row_number, "No se encontró la matrícula.")
            continue
        if len(matching_users) > 1:
            add_error(row_number, "La matrícula coincide con más de un usuario.")
            continue

        matching_subjects = materias.get(record["clave_materia"].casefold(), [])
        if not matching_subjects:
            add_error(row_number, "No se encontró la clave de materia.")
            continue
        if len(matching_subjects) > 1:
            add_error(row_number, "La clave de materia es ambigua.")
            continue

        try:
            with transaction.atomic():
                _, created = Inscripcion.objects.get_or_create(
                    usuario_id=matching_users[0],
                    materia_id=matching_subjects[0],
                    grupo=record["grupo"],
                    periodo=record["periodo"],
                    defaults={"activa": activa},
                )
        except IntegrityError:
            add_error(row_number, "No se pudo guardar la inscripción.")
            continue

        if created:
            created_count += 1
        else:
            skipped_count += 1

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "errors": errors,
        "omitted_error_count": max(0, error_count - len(errors)),
    }
