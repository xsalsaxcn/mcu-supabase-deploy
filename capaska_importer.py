from datetime import datetime, date
import pandas as pd

from database import get_connection


CAPASKA_COMPANY_NAME = "BPIP / CAPASKA"
CAPASKA_PACKAGE_NAME = "CAPASKA 2025/2026"
CAPASKA_PROGRAM_TYPE = "capaska"
REGISTRATION_POST_NAME = "Registrasi CAPASKA"


METADATA_COLUMNS = {
    "Submission Date",
    "Flow Status",
    "Tanggal layanan",
    "Jenis Pemeriksaan",
    "Dokter Bertugas",
    "Perawat Bertugas",
    "Jenis Kelamin",
    "Asal Provinsi Putra",
    "Asal Provinsi Putri",
    "Pilih Nama Peserta Putra",
    "Pilih Nama Peserta Putri",
}


REGISTRATION_PARAMETERS = [
    "Asal Provinsi",
    "Dokter Bertugas",
    "Perawat Bertugas",
    "Tanggal Layanan",
]


def column_exists(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cur.fetchall()]
    return column_name in columns


def ensure_column(cur, table_name, column_name, definition):
    if not column_exists(cur, table_name, column_name):
        cur.execute(f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_name} {definition}
        """)


def ensure_schema_columns(cur):
    ensure_column(cur, "participants", "external_id", "TEXT")
    ensure_column(cur, "participants", "program_type", "TEXT DEFAULT 'corporate'")
    ensure_column(cur, "packages", "program_type", "TEXT DEFAULT 'corporate'")
    ensure_column(cur, "posts", "program_type", "TEXT DEFAULT 'corporate'")
    ensure_column(cur, "parameters", "program_type", "TEXT DEFAULT 'corporate'")
    ensure_column(cur, "users", "program_type", "TEXT DEFAULT 'corporate'")


def is_empty(value):
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip()

    if text == "":
        return True

    if text.lower() in ["nan", "none", "nat"]:
        return True

    return False


def value_to_str(value):
    if is_empty(value):
        return ""

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    return str(value).strip()


def clean_name(value):
    text = value_to_str(value)

    if not text:
        return ""

    parts = [
        part.strip()
        for part in text.replace("\r", "\n").split("\n")
        if part.strip()
    ]

    if parts:
        return parts[-1]

    return text


def normalize_date(value):
    if is_empty(value):
        return ""

    try:
        parsed = pd.to_datetime(value)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return value_to_str(value)


def find_external_id(row):
    possible_columns = [
        "Nomor ID",
        "No ID",
        "ID Peserta",
        "Nomor Peserta",
        "No Peserta",
        "Nomor Registrasi",
        "No Registrasi",
        "NIK",
    ]

    for col in possible_columns:
        if col in row.index:
            value = value_to_str(row.get(col))
            if value:
                return value

    return ""


def get_selected_identity(row):
    gender = value_to_str(row.get("Jenis Kelamin"))

    if "putri" in gender.lower():
        name_raw = row.get("Pilih Nama Peserta Putri")
        province_raw = row.get("Asal Provinsi Putri")
    else:
        name_raw = row.get("Pilih Nama Peserta Putra")
        province_raw = row.get("Asal Provinsi Putra")

    name = clean_name(name_raw)
    province = value_to_str(province_raw)

    if not name:
        fallback_putra = clean_name(row.get("Pilih Nama Peserta Putra"))
        fallback_putri = clean_name(row.get("Pilih Nama Peserta Putri"))
        name = fallback_putra or fallback_putri

    if not province:
        province = (
            value_to_str(row.get("Asal Provinsi Putra"))
            or value_to_str(row.get("Asal Provinsi Putri"))
        )

    external_id = find_external_id(row)

    return {
        "name": name,
        "gender": gender,
        "province": province,
        "external_id": external_id,
    }


def ensure_company(cur, name):
    cur.execute("""
    INSERT OR IGNORE INTO companies (name, address, pic_name)
    VALUES (?, ?, ?)
    """, (name, "-", "-"))

    cur.execute("SELECT id FROM companies WHERE name = ?", (name,))
    return cur.fetchone()["id"]


def ensure_package(cur, name, company_id):
    cur.execute("""
    INSERT OR IGNORE INTO packages (name, description, company_id, is_active, program_type)
    VALUES (?, ?, ?, 1, ?)
    """, (name, "Imported CAPASKA BPIP package", company_id, CAPASKA_PROGRAM_TYPE))

    cur.execute("""
    UPDATE packages
    SET program_type = ?
    WHERE name = ?
    """, (CAPASKA_PROGRAM_TYPE, name))

    cur.execute("SELECT id FROM packages WHERE name = ?", (name,))
    return cur.fetchone()["id"]


def ensure_post(cur, name, description=None):
    cur.execute("""
    INSERT OR IGNORE INTO posts (name, description, program_type)
    VALUES (?, ?, ?)
    """, (name, description or name, CAPASKA_PROGRAM_TYPE))

    cur.execute("""
    UPDATE posts
    SET program_type = ?
    WHERE name = ?
    """, (CAPASKA_PROGRAM_TYPE, name))

    cur.execute("SELECT id FROM posts WHERE name = ?", (name,))
    return cur.fetchone()["id"]


def detect_input_type(series, header):
    header_lower = str(header).lower()

    non_empty_values = [
        value
        for value in series.tolist()
        if not is_empty(value)
    ]

    if not non_empty_values:
        return "text"

    numeric_count = 0

    for value in non_empty_values:
        try:
            float(value)
            numeric_count += 1
        except Exception:
            pass

    numeric_ratio = numeric_count / len(non_empty_values)

    if numeric_ratio >= 0.8:
        return "number"

    max_length = max(len(value_to_str(value)) for value in non_empty_values)

    if max_length > 120:
        return "textarea"

    if "catatan" in header_lower or "keterangan" in header_lower:
        return "textarea"

    return "text"


def ensure_parameter(
    cur,
    name,
    category,
    post_id,
    package_id,
    input_type="text",
    sort_order=0
):
    cur.execute("""
    SELECT id
    FROM parameters
    WHERE name = ?
      AND post_id = ?
    """, (name, post_id))

    row = cur.fetchone()
    created = False

    if row:
        parameter_id = row["id"]

        cur.execute("""
        UPDATE parameters
        SET program_type = ?
        WHERE id = ?
        """, (CAPASKA_PROGRAM_TYPE, parameter_id))

    else:
        cur.execute("""
        INSERT INTO parameters
        (
            name,
            category,
            post_id,
            unit,
            input_type,
            normal_value,
            reference_text,
            reference_image_path,
            config_json,
            is_required,
            is_active,
            sort_order,
            program_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            category,
            post_id,
            "",
            input_type,
            None,
            None,
            None,
            None,
            0,
            1,
            sort_order,
            CAPASKA_PROGRAM_TYPE
        ))

        parameter_id = cur.lastrowid
        created = True

    cur.execute("""
    INSERT OR IGNORE INTO package_parameters
    (package_id, parameter_id, sort_order)
    VALUES (?, ?, ?)
    """, (package_id, parameter_id, sort_order))

    return parameter_id, created


def generate_capaska_mcu_id(cur):
    prefix = "CAPASKA-2025"

    cur.execute("""
    SELECT COUNT(*) AS total
    FROM participants
    WHERE mcu_id LIKE ?
    """, (f"{prefix}-%",))

    total = cur.fetchone()["total"]
    next_number = total + 1

    while True:
        mcu_id = f"{prefix}-{next_number:04d}"

        cur.execute("""
        SELECT id
        FROM participants
        WHERE mcu_id = ?
        """, (mcu_id,))

        if cur.fetchone() is None:
            return mcu_id

        next_number += 1


def get_or_create_participant(
    cur,
    name,
    gender,
    external_id,
    company_id,
    package_id,
    mcu_date
):
    if external_id:
        cur.execute("""
        SELECT id, mcu_id
        FROM participants
        WHERE external_id = ?
          AND package_id = ?
        LIMIT 1
        """, (external_id, package_id))
    else:
        cur.execute("""
        SELECT id, mcu_id
        FROM participants
        WHERE name = ?
          AND gender = ?
          AND company_id = ?
          AND package_id = ?
        LIMIT 1
        """, (name, gender, company_id, package_id))

    row = cur.fetchone()

    if row:
        participant_id = row["id"]
        mcu_id = row["mcu_id"]

        cur.execute("""
        UPDATE participants
        SET
            program_type = ?,
            external_id = COALESCE(NULLIF(external_id, ''), ?)
        WHERE id = ?
        """, (CAPASKA_PROGRAM_TYPE, external_id, participant_id))

        return participant_id, mcu_id, False

    mcu_id = generate_capaska_mcu_id(cur)

    cur.execute("""
    INSERT INTO participants
    (
        mcu_id,
        external_id,
        name,
        nik,
        gender,
        birth_date,
        company_id,
        package_id,
        mcu_date,
        program_type
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mcu_id,
        external_id,
        name,
        "",
        gender,
        "",
        company_id,
        package_id,
        mcu_date,
        CAPASKA_PROGRAM_TYPE
    ))

    return cur.lastrowid, mcu_id, True


def upsert_result(
    cur,
    participant_id,
    parameter_id,
    value,
    user_id,
    post_id,
    stats
):
    value = value_to_str(value)

    if value == "":
        stats["results_skipped_empty"] += 1
        return

    cur.execute("""
    SELECT value
    FROM examination_results
    WHERE participant_id = ?
      AND parameter_id = ?
    """, (participant_id, parameter_id))

    existing = cur.fetchone()

    if existing:
        old_value = value_to_str(existing["value"])

        if old_value != value:
            cur.execute("""
            UPDATE examination_results
            SET
                value = ?,
                updated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE participant_id = ?
              AND parameter_id = ?
            """, (
                value,
                user_id,
                participant_id,
                parameter_id
            ))

            cur.execute("""
            INSERT INTO audit_logs
            (
                user_id,
                action,
                participant_id,
                parameter_id,
                old_value,
                new_value
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                "IMPORT_CAPASKA_UPDATE",
                participant_id,
                parameter_id,
                old_value,
                value
            ))

            stats["results_updated"] += 1
        else:
            stats["results_unchanged"] += 1

    else:
        cur.execute("""
        INSERT INTO examination_results
        (
            participant_id,
            parameter_id,
            value,
            input_by,
            input_post_id
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            participant_id,
            parameter_id,
            value,
            user_id,
            post_id
        ))

        cur.execute("""
        INSERT INTO audit_logs
        (
            user_id,
            action,
            participant_id,
            parameter_id,
            old_value,
            new_value
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            "IMPORT_CAPASKA_CREATE",
            participant_id,
            parameter_id,
            None,
            value
        ))

        stats["results_created"] += 1


def import_capaska_excel(uploaded_file, user_id):
    df = pd.read_excel(uploaded_file, sheet_name=0, engine="openpyxl")
    df.columns = [str(col).strip() for col in df.columns]

    required_columns = [
        "Jenis Pemeriksaan",
        "Jenis Kelamin",
        "Pilih Nama Peserta Putra",
        "Pilih Nama Peserta Putri",
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Format Excel tidak sesuai. Kolom hilang: "
            + ", ".join(missing_columns)
        )

    if "Submission Date" in df.columns:
        df["_submission_sort"] = pd.to_datetime(
            df["Submission Date"],
            errors="coerce"
        )
        df = df.sort_values("_submission_sort")

    conn = get_connection()
    cur = conn.cursor()

    ensure_schema_columns(cur)

    stats = {
        "rows_read": len(df),
        "rows_imported": 0,
        "rows_skipped": 0,
        "participants_created": 0,
        "participants_existing": 0,
        "posts_created_or_found": 0,
        "parameters_created": 0,
        "parameters_existing": 0,
        "results_created": 0,
        "results_updated": 0,
        "results_unchanged": 0,
        "results_skipped_empty": 0,
    }

    company_id = ensure_company(cur, CAPASKA_COMPANY_NAME)
    package_id = ensure_package(cur, CAPASKA_PACKAGE_NAME, company_id)

    registration_post_id = ensure_post(
        cur,
        REGISTRATION_POST_NAME,
        "Import identitas peserta CAPASKA"
    )

    registration_parameter_ids = {}

    for index, param_name in enumerate(REGISTRATION_PARAMETERS, start=1):
        parameter_id, created = ensure_parameter(
            cur=cur,
            name=param_name,
            category="Identitas",
            post_id=registration_post_id,
            package_id=package_id,
            input_type="text",
            sort_order=index
        )

        registration_parameter_ids[param_name] = parameter_id

        if created:
            stats["parameters_created"] += 1
        else:
            stats["parameters_existing"] += 1

    post_names = [
        value_to_str(value)
        for value in df["Jenis Pemeriksaan"].dropna().unique()
        if value_to_str(value)
    ]

    post_ids = {}

    for post_name in post_names:
        post_ids[post_name] = ensure_post(cur, post_name, post_name)
        stats["posts_created_or_found"] += 1

    parameter_map = {}

    for post_name in post_names:
        post_id = post_ids[post_name]

        sub_df = df[
            df["Jenis Pemeriksaan"].apply(value_to_str) == post_name
        ]

        sort_order = 1

        for column in df.columns:
            if column in METADATA_COLUMNS:
                continue

            if column.startswith("_"):
                continue

            series = sub_df[column]
            has_value = series.apply(lambda value: not is_empty(value)).any()

            if not has_value:
                continue

            input_type = detect_input_type(series, column)

            parameter_id, created = ensure_parameter(
                cur=cur,
                name=column,
                category=post_name,
                post_id=post_id,
                package_id=package_id,
                input_type=input_type,
                sort_order=sort_order
            )

            parameter_map[(post_name, column)] = {
                "parameter_id": parameter_id,
                "post_id": post_id,
            }

            if created:
                stats["parameters_created"] += 1
            else:
                stats["parameters_existing"] += 1

            sort_order += 1

    for _, row in df.iterrows():
        post_name = value_to_str(row.get("Jenis Pemeriksaan"))

        if not post_name:
            stats["rows_skipped"] += 1
            continue

        identity = get_selected_identity(row)
        participant_name = identity["name"]
        gender = identity["gender"]
        province = identity["province"]
        external_id = identity["external_id"]

        if not participant_name:
            stats["rows_skipped"] += 1
            continue

        tanggal_layanan = normalize_date(row.get("Tanggal layanan"))

        participant_id, mcu_id, created = get_or_create_participant(
            cur=cur,
            name=participant_name,
            gender=gender,
            external_id=external_id,
            company_id=company_id,
            package_id=package_id,
            mcu_date=tanggal_layanan
        )

        if created:
            stats["participants_created"] += 1
        else:
            stats["participants_existing"] += 1

        upsert_result(
            cur=cur,
            participant_id=participant_id,
            parameter_id=registration_parameter_ids["Asal Provinsi"],
            value=province,
            user_id=user_id,
            post_id=registration_post_id,
            stats=stats
        )

        upsert_result(
            cur=cur,
            participant_id=participant_id,
            parameter_id=registration_parameter_ids["Dokter Bertugas"],
            value=row.get("Dokter Bertugas"),
            user_id=user_id,
            post_id=registration_post_id,
            stats=stats
        )

        upsert_result(
            cur=cur,
            participant_id=participant_id,
            parameter_id=registration_parameter_ids["Perawat Bertugas"],
            value=row.get("Perawat Bertugas"),
            user_id=user_id,
            post_id=registration_post_id,
            stats=stats
        )

        upsert_result(
            cur=cur,
            participant_id=participant_id,
            parameter_id=registration_parameter_ids["Tanggal Layanan"],
            value=tanggal_layanan,
            user_id=user_id,
            post_id=registration_post_id,
            stats=stats
        )

        for column in df.columns:
            key = (post_name, column)

            if key not in parameter_map:
                continue

            parameter_id = parameter_map[key]["parameter_id"]
            post_id = parameter_map[key]["post_id"]
            value = row.get(column)

            upsert_result(
                cur=cur,
                participant_id=participant_id,
                parameter_id=parameter_id,
                value=value,
                user_id=user_id,
                post_id=post_id,
                stats=stats
            )

        stats["rows_imported"] += 1

    conn.commit()
    conn.close()

    return stats
