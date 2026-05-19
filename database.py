import os
import re
import sqlite3
from pathlib import Path

import streamlit as st

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except Exception:
    psycopg2 = None
    RealDictCursor = None
    POSTGRES_AVAILABLE = False


DB_PATH = Path(os.getenv("SQLITE_DB_PATH", "mcu.db"))

POSTGRES_ID_TABLES = {
    "companies",
    "posts",
    "packages",
    "users",
    "parameters",
    "package_parameters",
    "participants",
    "examination_results",
    "audit_logs",
    "participant_sources",
    "participant_reviews",
}


def get_supabase_db_url():
    """
    Ambil Supabase PostgreSQL connection string dari Streamlit Secrets
    atau environment variable.
    """
    try:
        if "SUPABASE_DB_URL" in st.secrets:
            return str(st.secrets["SUPABASE_DB_URL"]).strip()
    except Exception:
        pass

    try:
        if "database" in st.secrets and "url" in st.secrets["database"]:
            return str(st.secrets["database"]["url"]).strip()
    except Exception:
        pass

    return os.getenv("SUPABASE_DB_URL", "").strip()


def using_postgres():
    return bool(get_supabase_db_url())


class PgCursorAdapter:
    """
    Adapter supaya query lama gaya SQLite tetap bisa jalan di PostgreSQL/Supabase:
    - ? diganti %s
    - INSERT OR IGNORE diganti ON CONFLICT DO NOTHING
    - lastrowid diisi dari RETURNING id untuk tabel yang punya id serial
    """
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
        self._last_returned_row = None

    def _convert_sql(self, sql):
        q = sql.strip()

        q = q.replace("?", "%s")

        if re.match(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", q):
            q = re.sub(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", "INSERT INTO ", q)
            if "ON CONFLICT" not in q.upper():
                q = q.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        q = re.sub(
            r"(?is)INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "SERIAL PRIMARY KEY",
            q,
        )

        return q

    def _maybe_add_returning_id(self, sql):
        q = sql.strip()
        upper = q.upper()

        if not upper.startswith("INSERT INTO"):
            return q

        if " RETURNING " in upper:
            return q

        if " ON CONFLICT " in upper:
            return q

        m = re.match(r"(?is)INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", q)
        if not m:
            return q

        table = m.group(1)

        if table not in POSTGRES_ID_TABLES:
            return q

        return q.rstrip().rstrip(";") + " RETURNING id"

    def execute(self, sql, params=None):
        params = params or ()
        q = self._convert_sql(sql)
        q = self._maybe_add_returning_id(q)

        self._last_returned_row = None
        self.lastrowid = None

        self.cursor.execute(q, params)

        if q.strip().upper().startswith("INSERT INTO") and " RETURNING ID" in q.upper():
            try:
                row = self.cursor.fetchone()
                self._last_returned_row = row
                if row and "id" in row:
                    self.lastrowid = row["id"]
            except Exception:
                self._last_returned_row = None
                self.lastrowid = None

        return self

    def executemany(self, sql, seq_of_params):
        q = self._convert_sql(sql)
        self.cursor.executemany(q, seq_of_params)
        return self

    def fetchone(self):
        if self._last_returned_row is not None:
            row = self._last_returned_row
            self._last_returned_row = None
            return row
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        return self.cursor.close()


class PgConnectionAdapter:
    def __init__(self, dsn):
        self.conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)

    def cursor(self):
        return PgCursorAdapter(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def get_connection():
    """
    Dipakai oleh capaska_importer.py dan modul lama lain.

    Kalau SUPABASE_DB_URL ada di Streamlit Secrets:
        pakai Supabase PostgreSQL.
    Kalau tidak:
        fallback ke SQLite lokal mcu.db.
    """
    if using_postgres():
        if not POSTGRES_AVAILABLE:
            raise RuntimeError(
                "psycopg2-binary belum terinstall. "
                "Tambahkan psycopg2-binary ke requirements.txt."
            )

        return PgConnectionAdapter(get_supabase_db_url())

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
