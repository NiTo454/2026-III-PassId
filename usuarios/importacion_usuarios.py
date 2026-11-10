import csv
import io
from zipfile import BadZipFile
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import Perfil, Usuario, UsuarioTienePerfil


REQUIRED_COLUMNS = (
    "username",
    "email",
    "nombre",
    "apaterno",
    "amaterno",
    "matricula",
    "grupo",
    "whatsapp",
    "rol",
)
MAX_IMPORT_ROWS = 5000


def _read_csv(uploaded_file):
    content = uploaded_file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _read_xlsx(uploaded_file):
    workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        rows = list(worksheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    return [list(row) for row in rows]


def read_user_rows(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    try:
        rows = (
            _read_csv(uploaded_file)
            if extension == "csv"
            else _read_xlsx(uploaded_file)
        )
    except (csv.Error, UnicodeDecodeError, OSError, ValueError) as error:
        raise ValidationError("No se pudo leer el archivo. Verifica que sea un CSV o Excel válido.") from error
    except (BadZipFile, InvalidFileException, KeyError) as error:
        raise ValidationError("No se pudo leer el archivo Excel. Verifica que el libro no esté dañado.") from error

    if not rows:
        raise ValidationError("El archivo está vacío.")

    headers = [
        str(value).strip().lower() if value is not None else ""
        for value in rows[0]
    ]
    if len(headers) != len(set(headers)):
        raise ValidationError("El archivo contiene nombres de columnas repetidos.")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        raise ValidationError(
            "Faltan columnas requeridas: " + ", ".join(missing_columns) + "."
        )

    indexes = {column: headers.index(column) for column in REQUIRED_COLUMNS}
    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        if row_number > MAX_IMPORT_ROWS + 1:
            raise ValidationError(
                f"El archivo supera el máximo de {MAX_IMPORT_ROWS} filas de datos."
            )

        record = {}
        for column, index in indexes.items():
            value = row[index] if index < len(row) else None
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            record[column] = str(value).strip() if value is not None else ""
        record["row_number"] = row_number
        records.append(record)

    return records


def import_users(uploaded_file):
    rows = read_user_rows(uploaded_file)
    profiles = {
        profile.nombre.lower(): profile
        for profile in Perfil.objects.filter(nombre__in=["alumno", "profesor"])
    }
    missing_profiles = [
        role for role in ("alumno", "profesor") if role not in profiles
    ]
    if missing_profiles:
        raise ValidationError(
            "No están configurados los perfiles requeridos: "
            + ", ".join(missing_profiles)
            + "."
        )

    created_count = 0
    errors = []
    seen = defaultdict(dict)

    for record in rows:
        row_number = record.pop("row_number")
        missing_values = [
            column for column in REQUIRED_COLUMNS if not record[column]
        ]
        if missing_values:
            errors.append({
                "row": row_number,
                "detail": "Campos vacíos: " + ", ".join(missing_values),
            })
            continue

        role = record["rol"].lower()
        if role not in profiles:
            errors.append({
                "row": row_number,
                "detail": "rol debe ser alumno o profesor",
            })
            continue

        conflicts = []
        for column in ("username", "email", "matricula"):
            normalized = record[column].casefold()
            first_row = seen[column].get(normalized)
            if first_row is not None:
                conflicts.append(f"{column} repetido en fila {first_row}")
            else:
                seen[column][normalized] = row_number

        for column in ("username", "email", "matricula"):
            normalized = record[column].casefold()
            if seen[column].get(normalized) == row_number:
                exists = Usuario.objects.filter(
                    **{f"{column}__iexact": record[column]}
                ).exists()
                if exists:
                    conflicts.append(f"{column} ya registrado")

        if conflicts:
            errors.append({
                "row": row_number,
                "detail": "; ".join(dict.fromkeys(conflicts)),
            })
            continue

        try:
            with transaction.atomic():
                user = Usuario(
                    username=record["username"],
                    email=record["email"],
                    nombre=record["nombre"],
                    apaterno=record["apaterno"],
                    amaterno=record["amaterno"],
                    matricula=record["matricula"],
                    grupo=record["grupo"],
                    whatsapp=record["whatsapp"],
                    categoria=role,
                    activo=True,
                    is_superuser=False,
                )
                user.set_password(record["matricula"])
                user.full_clean()
                user.save()
                UsuarioTienePerfil.objects.create(
                    usuario=user,
                    perfil=profiles[role],
                )
        except (IntegrityError, ValidationError) as error:
            detail = (
                "; ".join(
                    f"{field}: {', '.join(messages)}"
                    for field, messages in error.message_dict.items()
                )
                if isinstance(error, ValidationError) and hasattr(error, "message_dict")
                else str(error)
            )
            errors.append({"row": row_number, "detail": detail})
            continue

        created_count += 1

    return {
        "created_count": created_count,
        "error_count": len(errors),
        "errors": errors,
    }
