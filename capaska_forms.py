import sqlite3
from pathlib import Path

import streamlit as st


DB_PATH = Path("mcu.db")
PROGRAM_CAPASKA = "capaska"


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_key(text):
    if text is None:
        return ""

    value = str(text).lower().strip()

    replacements = {
        " ": "",
        "\n": "",
        "\r": "",
        "\t": "",
        ".": "",
        ",": "",
        "-": "",
        "_": "",
        "/": "",
        "\\": "",
        ">": "",
        "<": "",
        ":": "",
        ";": "",
        "(": "",
        ")": "",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def get_existing_results_by_parameter_name(participant_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        parameters.name AS parameter_name,
        examination_results.value
    FROM examination_results
    JOIN parameters ON examination_results.parameter_id = parameters.id
    WHERE examination_results.participant_id = ?
    """, (participant_id,))

    rows = cur.fetchall()
    conn.close()

    results = {}

    for row in rows:
        results[normalize_key(row["parameter_name"])] = row["value"]

    return results


def find_or_create_parameter(
    name,
    category,
    post_id,
    package_id,
    input_type="text",
    sort_order=0,
    unit="",
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, name
    FROM parameters
    WHERE post_id = ?
      AND program_type = ?
    """, (post_id, PROGRAM_CAPASKA))

    rows = cur.fetchall()

    target_key = normalize_key(name)

    for row in rows:
        if normalize_key(row["name"]) == target_key:
            parameter_id = row["id"]

            cur.execute("""
            INSERT OR IGNORE INTO package_parameters
            (package_id, parameter_id, sort_order)
            VALUES (?, ?, ?)
            """, (package_id, parameter_id, sort_order))

            conn.commit()
            conn.close()
            return parameter_id

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
        unit,
        input_type,
        None,
        None,
        None,
        None,
        0,
        1,
        sort_order,
        PROGRAM_CAPASKA
    ))

    parameter_id = cur.lastrowid

    cur.execute("""
    INSERT OR IGNORE INTO package_parameters
    (package_id, parameter_id, sort_order)
    VALUES (?, ?, ?)
    """, (package_id, parameter_id, sort_order))

    conn.commit()
    conn.close()

    return parameter_id


def save_result(participant_id, parameter_id, value, user_id, post_id):
    conn = get_connection()
    cur = conn.cursor()

    value = "" if value is None else str(value).strip()

    cur.execute("""
    SELECT value
    FROM examination_results
    WHERE participant_id = ?
      AND parameter_id = ?
    """, (participant_id, parameter_id))

    existing = cur.fetchone()

    if existing:
        old_value = existing["value"]

        if str(old_value) != str(value):
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
                "UPDATE_RESULT",
                participant_id,
                parameter_id,
                old_value,
                value
            ))

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
            "CREATE_RESULT",
            participant_id,
            parameter_id,
            None,
            value
        ))

    conn.commit()
    conn.close()


def save_field(
    participant,
    user,
    post_id,
    category,
    name,
    value,
    input_type="text",
    sort_order=0,
    unit="",
):
    parameter_id = find_or_create_parameter(
        name=name,
        category=category,
        post_id=post_id,
        package_id=participant["package_id"],
        input_type=input_type,
        sort_order=sort_order,
        unit=unit,
    )

    save_result(
        participant_id=participant["id"],
        parameter_id=parameter_id,
        value=value,
        user_id=user["id"],
        post_id=post_id,
    )


# =========================================================
# SCORING RULES
# Sesuaikan angka ini dengan juknis resmi CAPASKA/BPIP.
# =========================================================

SCORE_RULES = {
    "mata": {
        "Lensakontak/ kaca mata": {
            "Tidak menggunakan": 2,
            "Menggunakan": 1,
        },
        "Tes buta warna": {
            "Tidak buta warna": 2,
            "Buta warna parsial": 1,
            "Buta warna total": 0,
        },
        "Strabismus / Juling": {
            "(-) / (-)": 2,
            "(+) / (-)": 1,
            "(-) / (+)": 1,
            "(+) / (+)": 0,
        },
        "Pemeriksaan Visus OD  / OS": {
            "Normal 6/6": 2,
            "<6/6 - 6/12": 1,
            "<6/12": 0,
        },
    },

    "gigi": {
        "Karang Gigi": {
            "Negative": 2,
            "Positive": 0,
        },
        "Caries Dentis": {
            "0 caries": 2,
            "1 caries": 1,
            "2 caries": 1,
            "3 caries": 0,
            ">3 caries": 0,
        },
        "Tumpatan Gigi": {
            "0 tumpatan": 2,
            "<3 tumpatan": 1,
            ">3 tumpatan": 0,
        },
        "Impaksi gigi": {
            "0 gigi": 2,
            "1 gigi": 1,
            "2 gigi": 0,
            ">2 gigi": 0,
        },
        "Kehilangan Gigi (Baik depan maupun belakang)": {
            "0 gigi": 2,
            "1 gigi": 1,
            "2 gigi": 0,
            ">2 gigi": 0,
        },
        "Infeksi Gusi": {
            "Negative": 2,
            "Positive": 0,
        },
        "Dental panoramic": {
            "Normal": 2,
            "ditemukan kelainan": 0,
        },
    },

    "tht": {
        "Membran timpani": {
            "Intak": 2,
            "Tidak Intak": 0,
        },
        "Serumen": {
            "Tidak ada": 2,
            "Ada serumen": 0,
        },
        "Tonsil": {
            "T0 - T1": 2,
            "T0 - T2a": 1,
            "T0 - T2b": 1,
            "T2 - T3": 0,
        },
        "Rhinitis Alergi (divide)": {
            "Negative": 2,
            "Positive": 0,
        },
        "Epistaksis 1 tahun terakhir": {
            "Tidak Ada": 2,
            "Ada": 0,
        },
        "Tes Garputala (Weber) 512 Hz": {
            "Normal": 2,
            "Tidak Normal": 0,
        },
    },

    "penyakit_dalam": {
        "Sesuai juknis": 2,
        "Tidak sesuai juknis": 0,
        "Normal": 2,
        "Tidak Normal": 0,
        "Tidak ada tato": 2,
        "Ada tato": 0,
        "Tidak ada": 2,
        "Ada": 0,
        "Tidak ada (pria) Wanita >1)": 0,
        "Ada (pria) Wanita >1)": 0,
    },

    "jantung": {
        "Tidak Ada": 2,
        "Ada": 0,
    },

    "ortopedi": {
        "Tidak Ada": 2,
        "Ada": 0,
        "Ringan": 1,
    },

    "radiologi": {
        "Tidak Ada": 2,
        "Ringan": 1,
        "Sedang": 0,
        "Berat": 0,
    },
}


# =========================================================
# UI HELPERS
# =========================================================

def get_existing_value(existing, name, default=""):
    return existing.get(normalize_key(name), default)


def score_from_rule(group, field_name, selected_value):
    rules = SCORE_RULES.get(group, {})

    field_rules = rules.get(field_name)

    if isinstance(field_rules, dict):
        return field_rules.get(selected_value, 0)

    return rules.get(selected_value, 0)


def radio_field(label, options, existing, key, horizontal=False):
    old_value = get_existing_value(existing, label, "")

    index = 0

    if old_value in options:
        index = options.index(old_value)

    return st.radio(
        label,
        options,
        index=index,
        key=key,
        horizontal=horizontal,
    )


def text_field(label, existing, key, placeholder=""):
    old_value = get_existing_value(existing, label, "")

    return st.text_input(
        label,
        value=old_value,
        key=key,
        placeholder=placeholder,
    )


def number_text_field(label, existing, key):
    old_value = get_existing_value(existing, label, "")

    return st.text_input(
        label,
        value=old_value,
        key=key,
        placeholder="e.g., 23",
    )


def matrix_radio(section_label, rows, options, existing, key_prefix):
    st.markdown(f"**{section_label}**")

    result = {}

    header_cols = st.columns([2] + [1 for _ in options])
    header_cols[0].markdown("")

    for idx, option in enumerate(options):
        header_cols[idx + 1].markdown(f"**{option}**")

    for row in rows:
        cols = st.columns([2] + [1 for _ in options])
        cols[0].write(row)

        current_value = get_existing_value(existing, row, options[0])

        for idx, option in enumerate(options):
            with cols[idx + 1]:
                selected = st.radio(
                    row,
                    options,
                    index=options.index(current_value) if current_value in options else 0,
                    key=f"{key_prefix}_{normalize_key(row)}",
                    label_visibility="collapsed",
                    horizontal=True,
                )
                result[row] = selected
                break

    return result


def save_score_pair(
    participant,
    user,
    post_id,
    category,
    field_name,
    field_value,
    value_field_name,
    score,
    sort_order,
):
    save_field(
        participant=participant,
        user=user,
        post_id=post_id,
        category=category,
        name=field_name,
        value=field_value,
        input_type="select",
        sort_order=sort_order,
    )

    save_field(
        participant=participant,
        user=user,
        post_id=post_id,
        category=category,
        name=value_field_name,
        value=score,
        input_type="number",
        sort_order=sort_order + 1,
    )


def save_total_score(
    participant,
    user,
    post_id,
    category,
    total_name,
    total_score,
    sort_order,
):
    save_field(
        participant=participant,
        user=user,
        post_id=post_id,
        category=category,
        name=total_name,
        value=total_score,
        input_type="number",
        sort_order=sort_order,
    )


# =========================================================
# CAPASKA FORM: MATA
# =========================================================

def render_mata_form(participant, user, post_id):
    category = "Pemeriksaan Mata"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan Mata")

    with st.form("capaska_mata_form"):
        lens = radio_field(
            "Lensakontak/ kaca mata",
            ["Menggunakan", "Tidak menggunakan"],
            existing,
            "mata_lens",
        )

        buta_warna = radio_field(
            "Tes buta warna",
            ["Tidak buta warna", "Buta warna parsial", "Buta warna total"],
            existing,
            "mata_buta_warna",
        )

        strabismus = radio_field(
            "Strabismus / Juling",
            ["(+) / (-)", "(-) / (+)", "(+) / (+)", "(-) / (-)"],
            existing,
            "mata_strabismus",
        )

        visus = radio_field(
            "Pemeriksaan Visus OD  / OS",
            ["Normal 6/6", "<6/6 - 6/12", "<6/12"],
            existing,
            "mata_visus",
        )

        submit = st.form_submit_button("Submit")

    if submit:
        lens_score = score_from_rule("mata", "Lensakontak/ kaca mata", lens)
        buta_score = score_from_rule("mata", "Tes buta warna", buta_warna)
        strabismus_score = score_from_rule("mata", "Strabismus / Juling", strabismus)
        visus_score = score_from_rule("mata", "Pemeriksaan Visus OD  / OS", visus)

        total = lens_score + buta_score + strabismus_score + visus_score

        save_score_pair(participant, user, post_id, category, "Lensakontak/ kaca mata", lens, "Value Lensakontak/ kaca mata", lens_score, 1)
        save_score_pair(participant, user, post_id, category, "Tes buta warna", buta_warna, "Value buta warna", buta_score, 3)
        save_score_pair(participant, user, post_id, category, "Strabismus / Juling", strabismus, "Value Strabismus / Juling", strabismus_score, 5)
        save_score_pair(participant, user, post_id, category, "Pemeriksaan Visus OD  / OS", visus, "Value Pemeriksaan Visus OD  / OS", visus_score, 7)
        save_total_score(participant, user, post_id, category, "Total Score Kesehatan mata", total, 9)

        st.success(f"Data Pemeriksaan Mata tersimpan. Total Score: {total}")


# =========================================================
# CAPASKA FORM: GIGI
# =========================================================

def render_gigi_form(participant, user, post_id):
    category = "Pemeriksaan Kesehatan Gigi dan Mulut"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan Kesehatan Gigi dan Mulut")

    with st.form("capaska_gigi_form"):
        karang = radio_field("Karang Gigi", ["Positive", "Negative"], existing, "gigi_karang")
        caries = radio_field("Caries Dentis", ["0 caries", "1 caries", "2 caries", "3 caries", ">3 caries"], existing, "gigi_caries")
        tumpatan = radio_field("Tumpatan Gigi", ["0 tumpatan", "<3 tumpatan", ">3 tumpatan"], existing, "gigi_tumpatan")
        impaksi = radio_field("Impaksi gigi", ["0 gigi", "1 gigi", "2 gigi", ">2 gigi"], existing, "gigi_impaksi")
        kehilangan = radio_field("Kehilangan Gigi (Baik depan maupun belakang)", ["0 gigi", "1 gigi", "2 gigi", ">2 gigi"], existing, "gigi_kehilangan")
        infeksi = radio_field("Infeksi Gusi", ["Positive", "Negative"], existing, "gigi_infeksi")
        dental = radio_field("Dental panoramic", ["Normal", "ditemukan kelainan"], existing, "gigi_dental")
        kelainan = text_field("bentuk kelainan Dental Panoramik", existing, "gigi_kelainan")

        submit = st.form_submit_button("Submit")

    if submit:
        items = [
            ("Karang Gigi", karang, "Value Karang Gigi", 1),
            ("Caries Dentis", caries, "Value Caries Dentis", 3),
            ("Tumpatan Gigi", tumpatan, "Value Tumpatan Gigi", 5),
            ("Impaksi gigi", impaksi, "Value Impaksi gigi", 7),
            ("Kehilangan Gigi (Baik depan maupun belakang)", kehilangan, "Value Kehilangan Gigi (Baik depan maupun belakang)", 9),
            ("Infeksi Gusi", infeksi, "Value Infeksi Gusi", 11),
            ("Dental panoramic", dental, "Value Dental panoramic", 13),
        ]

        total = 0

        for field_name, selected, value_name, order in items:
            score = score_from_rule("gigi", field_name, selected)
            total += score
            save_score_pair(participant, user, post_id, category, field_name, selected, value_name, score, order)

        save_field(participant, user, post_id, category, "bentuk kelainan Dental Panoramik", kelainan, "text", 15)
        save_total_score(participant, user, post_id, category, "Score total Pemeriksaan Kesehatan Gigi dan Mulut", total, 16)

        st.success(f"Data Pemeriksaan Gigi tersimpan. Total Score: {total}")


# =========================================================
# CAPASKA FORM: THT
# =========================================================

def render_tht_form(participant, user, post_id):
    category = "Pemeriksaan Kesehatan THT"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan THT")

    with st.form("capaska_tht_form"):
        membran = radio_field("Membran timpani", ["Intak", "Tidak Intak"], existing, "tht_membran")
        serumen = radio_field("Serumen", ["Tidak ada", "Ada serumen"], existing, "tht_serumen")
        tonsil = radio_field("Tonsil", ["T0 - T1", "T0 - T2a", "T0 - T2b", "T2 - T3"], existing, "tht_tonsil")
        rhinitis = radio_field("Rhinitis Alergi (divide)", ["Positive", "Negative"], existing, "tht_rhinitis")
        epistaksis = radio_field("Epistaksis 1 tahun terakhir", ["Ada", "Tidak Ada"], existing, "tht_epistaksis")
        garputala = radio_field("Tes Garputala (Weber) 512 Hz", ["Normal", "Tidak Normal"], existing, "tht_garputala")

        submit = st.form_submit_button("Submit")

    if submit:
        items = [
            ("Membran timpani", membran, "Value Membran timpani", 1),
            ("Serumen", serumen, "Value Serumen", 3),
            ("Tonsil", tonsil, "Value Tonsil", 5),
            ("Rhinitis Alergi (divide)", rhinitis, "Value Rhinitis Alergi (divide)", 7),
            ("Epistaksis 1 tahun terakhir", epistaksis, "Value Epistaksis 1 tahun terakhir", 9),
            ("Tes Garputala (Weber) 512 Hz", garputala, "Value Garputala (Weber) 512 Hz", 11),
        ]

        total = 0

        for field_name, selected, value_name, order in items:
            score = score_from_rule("tht", field_name, selected)
            total += score
            save_score_pair(participant, user, post_id, category, field_name, selected, value_name, score, order)

        save_total_score(participant, user, post_id, category, "Score total Pemeriksaan Kesehatan THT", total, 13)

        st.success(f"Data Pemeriksaan THT tersimpan. Total Score: {total}")


# =========================================================
# CAPASKA FORM: PENYAKIT DALAM
# =========================================================

def render_penyakit_dalam_form(participant, user, post_id):
    category = "Pemeriksaan Penyakit Dalam"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan Penyakit Dalam")

    with st.form("capaska_penyakit_dalam_form"):
        bb_status = radio_field("Berat Badan (Kg)", ["Sesuai juknis", "Tidak sesuai juknis"], existing, "pd_bb_status")
        bb_value = text_field("BB (Kg)", existing, "pd_bb_value")

        tb_status = radio_field("TB. (Cm)", ["Sesuai juknis", "Tidak sesuai juknis"], existing, "pd_tb_status")
        tb_value = text_field("Tb (Cm)", existing, "pd_tb_value")

        vital = radio_field("Tanda Vital", ["Normal", "Tidak Normal"], existing, "pd_vital")
        vital_text = text_field("Suhu/Nadi/Napas/tekanan darah", existing, "pd_vital_text")

        tato = radio_field("Tato kulit", ["Tidak ada tato", "Ada tato"], existing, "pd_tato")
        tindik = radio_field("Tindik (selain anting) Wanita : hanya 1 / telinga", ["Tidak ada", "Ada (pria) Wanita >1)"], existing, "pd_tindik")

        jantung = radio_field("Pemeriksaan Fisik Jantung", ["Normal", "Tidak Normal"], existing, "pd_jantung")
        paru = radio_field("Pemeriksaan Fisik Paru", ["Normal", "Tidak Normal"], existing, "pd_paru")

        abdomen_rows = ["Hernia", "NT Epigastrum", "Benjolan", "Liver", "Bising Usus", "Bekas Operasi (>6Bulan)"]
        abdomen = matrix_radio("Pemeriksaan Abdomen", abdomen_rows, ["Normal", "Tidak Normal"], existing, "pd_abdomen")

        anus_rows = ["Hemoroid eksterna", "Hemoroid interna", "Fisura ani", "Struktur/Prolaps recti"]
        anus = matrix_radio("Pemeriksaan Anus & Rektum (Colok Dubur)", anus_rows, ["Normal", "Tidak Normal"], existing, "pd_anus")

        urogenital_rows = [
            "Hidronefrosis",
            "Kelainan kongenital",
            "Hipospadia",
            "Hidrokel",
            "Undescensus testis",
            "Batu sal kemih",
            "Cystitis akut / kronis",
            "Post operasi varikokel",
            "Phimosis",
        ]
        urogenital = matrix_radio("Pemeriksaan Urogenitalia", urogenital_rows, ["Normal", "Tidak Normal"], existing, "pd_urogenital")

        submit = st.form_submit_button("Submit")

    if submit:
        total = 0

        simple_items = [
            ("Berat Badan (Kg)", bb_status, "Value Berat Badan (Kg)", 1),
            ("TB. (Cm)", tb_status, "Value TB. (Cm)", 4),
            ("Tanda Vital", vital, "Value Tanda Vital", 7),
            ("Tato kulit", tato, "Value Tato kulit", 10),
            ("Tindik (selain anting) Wanita : hanya 1 / telinga", tindik, "Value (selain anting) Wanita : hanya 1 / telinga", 12),
            ("Pemeriksaan Fisik Jantung", jantung, "Value Pemeriksaan Fisik Jantung", 14),
            ("Pemeriksaan Fisik Paru", paru, "Value Pemeriksaan Fisik Paru", 16),
        ]

        for field_name, selected, value_name, order in simple_items:
            score = score_from_rule("penyakit_dalam", field_name, selected)
            total += score
            save_score_pair(participant, user, post_id, category, field_name, selected, value_name, score, order)

        save_field(participant, user, post_id, category, "BB (Kg)", bb_value, "text", 3)
        save_field(participant, user, post_id, category, "Tb (Cm)", tb_value, "text", 6)
        save_field(participant, user, post_id, category, "Suhu/Nadi/Napas/tekanan darah", vital_text, "text", 9)

        abdomen_score = 0
        for idx, row_name in enumerate(abdomen_rows, start=20):
            selected = abdomen[row_name]
            score = score_from_rule("penyakit_dalam", row_name, selected)
            abdomen_score += score
            save_field(participant, user, post_id, category, row_name, selected, "select", idx)

        save_total_score(participant, user, post_id, category, "Score Abdomen", abdomen_score, 40)

        anus_score = 0
        for idx, row_name in enumerate(anus_rows, start=50):
            selected = anus[row_name]
            score = score_from_rule("penyakit_dalam", row_name, selected)
            anus_score += score
            save_field(participant, user, post_id, category, row_name, selected, "select", idx)

        save_total_score(participant, user, post_id, category, "Score Pemeriksaan Anus & Rektum (Colok Dubur)", anus_score, 60)

        urogenital_score = 0
        for idx, row_name in enumerate(urogenital_rows, start=70):
            selected = urogenital[row_name]
            score = score_from_rule("penyakit_dalam", row_name, selected)
            urogenital_score += score
            save_field(participant, user, post_id, category, row_name, selected, "select", idx)

        save_total_score(participant, user, post_id, category, "Score Urogenitalia", urogenital_score, 90)

        total = total + abdomen_score + anus_score + urogenital_score

        save_total_score(participant, user, post_id, category, "Score total Pemeriksaan Penyakit Dalam", total, 100)

        st.success(f"Data Pemeriksaan Penyakit Dalam tersimpan. Total Score: {total}")


# =========================================================
# CAPASKA FORM: JANTUNG
# =========================================================

def render_jantung_form(participant, user, post_id):
    category = "Pemeriksaan Kesehatan Jantung dan Pembuluh Darah"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan Kesehatan Jantung dan Pembuluh Darah")

    fields = [
        "Kelainan Anatomi Jantung",
        "Kelainan Irama Jantung",
        "Iskemik Miocardial",
        "Kelainan kongenital jantung",
        "Varises Tungkai (insufisiensi vena)",
        "Kelainan Arteri pada ekstremitas",
    ]

    with st.form("capaska_jantung_form"):
        values = {}

        for idx, field in enumerate(fields):
            values[field] = radio_field(field, ["Tidak Ada", "Ada"], existing, f"jantung_{idx}")

        submit = st.form_submit_button("Submit")

    if submit:
        total = 0

        for idx, field in enumerate(fields, start=1):
            selected = values[field]
            score = score_from_rule("jantung", field, selected)
            total += score
            save_score_pair(participant, user, post_id, category, field, selected, f"Value {field}", score, idx * 2)

        save_total_score(participant, user, post_id, category, "Score total Pemeriksaan Kesehatan Jantung dan Pembuluh Darah", total, 20)

        st.success(f"Data Pemeriksaan Jantung tersimpan. Total Score: {total}")


# =========================================================
# CAPASKA FORM: ORTOPEDI
# =========================================================

def render_ortopedi_form(participant, user, post_id):
    category = "Pemeriksaan Ortopedi"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan Ortopedi")

    atas_rows = [
        "sindaktili",
        "polidaktili",
        "spina bifida",
        "mallet finger",
        "Hiperekstensi lengan",
    ]

    bawah_rows = [
        "Hammer toe",
        "Hallux valgus",
        "Webbed toe",
        "O/X bean",
        "Pes planus / kaki datar",
        "Polidactily",
        "Hiperekstensi kaki",
        "General Laxity",
    ]

    vertebra_rows = [
        "Skoliosis",
        "Kifosis",
        "Lordosis",
    ]

    with st.form("capaska_ortopedi_form"):
        atas = matrix_radio("Pemeriksaan Anggota Gerak Atas", atas_rows, ["Tidak Ada", "Ada"], existing, "ortopedi_atas")
        bawah = matrix_radio("Pemeriksaan Anggota Gerak Bawah", bawah_rows, ["Tidak Ada", "Ada"], existing, "ortopedi_bawah")
        vertebra = matrix_radio("Pemeriksaan Vertebra / Tulang Belakang", vertebra_rows, ["Tidak Ada", "Ada", "Ringan"], existing, "ortopedi_vertebra")

        submit = st.form_submit_button("Submit")

    if submit:
        score_atas = 0

        for idx, row_name in enumerate(atas_rows, start=1):
            selected = atas[row_name]
            score = score_from_rule("ortopedi", row_name, selected)
            score_atas += score
            save_field(participant, user, post_id, category, row_name, selected, "select", idx)

        save_total_score(participant, user, post_id, category, "Score Anggota Gerak Atas", score_atas, 30)

        score_bawah = 0

        for idx, row_name in enumerate(bawah_rows, start=40):
            selected = bawah[row_name]
            score = score_from_rule("ortopedi", row_name, selected)
            score_bawah += score
            save_field(participant, user, post_id, category, row_name, selected, "select", idx)

        save_total_score(participant, user, post_id, category, "Score Anggota Gerak Bawah", score_bawah, 70)

        score_vertebra = 0

        for idx, row_name in enumerate(vertebra_rows, start=80):
            selected = vertebra[row_name]
            score = score_from_rule("ortopedi", row_name, selected)
            score_vertebra += score
            save_field(participant, user, post_id, category, row_name, selected, "select", idx)

        save_total_score(participant, user, post_id, category, "Score Vertebra / Tulang Belakang", score_vertebra, 90)

        total = score_atas + score_bawah + score_vertebra

        save_total_score(participant, user, post_id, category, "Score total Pemeriksaan Ortopedi", total, 100)

        st.success(f"Data Pemeriksaan Ortopedi tersimpan. Total Score: {total}")


# =========================================================
# CAPASKA FORM: RADIOLOGI
# =========================================================

def render_radiologi_form(participant, user, post_id):
    category = "Pemeriksaan Radiologi"
    existing = get_existing_results_by_parameter_name(participant["id"])

    st.subheader("Pemeriksaan Radiologi")

    rows = [
        "Skoliosis",
        "Kifosis",
        "Lordosis",
    ]

    with st.form("capaska_radiologi_form"):
        rontgen = matrix_radio(
            "Rontgen Whole Spine AP Lateral",
            rows,
            ["Tidak Ada", "Ringan", "Sedang", "Berat"],
            existing,
            "radiologi_whole_spine",
        )

        submit = st.form_submit_button("Submit")

    if submit:
        score_rontgen = 0

        for idx, row_name in enumerate(rows, start=1):
            selected = rontgen[row_name]
            score = score_from_rule("radiologi", row_name, selected)
            score_rontgen += score

            save_field(
                participant=participant,
                user=user,
                post_id=post_id,
                category=category,
                name=f"Rontgen Whole Spine AP Lateral >> {row_name}",
                value=selected,
                input_type="select",
                sort_order=idx,
            )

        save_total_score(participant, user, post_id, category, "Score Rontgen Whole Spine AP Lateral", score_rontgen, 10)
        save_total_score(participant, user, post_id, category, "Score total Pemeriksaan Penunjang Radiologi", score_rontgen, 11)

        st.success(f"Data Pemeriksaan Radiologi tersimpan. Total Score: {score_rontgen}")


# =========================================================
# MAIN ROUTER
# =========================================================

def render_capaska_form(participant, user, post_id, post_name):
    post_name_lower = str(post_name).lower()

    if "mata" in post_name_lower:
        render_mata_form(participant, user, post_id)
        return True

    if "gigi" in post_name_lower or "dental" in post_name_lower:
        render_gigi_form(participant, user, post_id)
        return True

    if "tht" in post_name_lower:
        render_tht_form(participant, user, post_id)
        return True

    if "penyakit dalam" in post_name_lower:
        render_penyakit_dalam_form(participant, user, post_id)
        return True

    if "jantung" in post_name_lower or "pembuluh darah" in post_name_lower:
        render_jantung_form(participant, user, post_id)
        return True

    if "ortopedi" in post_name_lower:
        render_ortopedi_form(participant, user, post_id)
        return True

    if "radiologi" in post_name_lower:
        render_radiologi_form(participant, user, post_id)
        return True

    return False
