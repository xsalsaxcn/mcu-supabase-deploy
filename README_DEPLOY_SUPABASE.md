# MCU System - Streamlit Cloud + Supabase Free

## File utama
- `app.py` = full script aplikasi Streamlit yang sudah support SQLite lokal dan Supabase PostgreSQL.
- `requirements.txt` = dependency untuk Streamlit Cloud.
- `SUPABASE_SCHEMA.sql` = schema manual jika ingin dibuat dari Supabase SQL Editor.
- `.streamlit/config.toml` = konfigurasi Streamlit.

## Cara pakai di Streamlit Community Cloud

1. Buat project Supabase.
2. Ambil connection string PostgreSQL dari Supabase:
   Project Settings > Database > Connection string.
3. Buat GitHub repo, upload semua file dari ZIP ini.
4. Di Streamlit Community Cloud, deploy repo tersebut.
5. Buka App settings > Secrets.
6. Isi secrets:

```toml
SUPABASE_DB_URL = "postgresql://postgres.xxxxxx:PASSWORD@aws-0-xxxxx.pooler.supabase.com:6543/postgres"
```

Atau:

```toml
[database]
url = "postgresql://postgres.xxxxxx:PASSWORD@aws-0-xxxxx.pooler.supabase.com:6543/postgres"
```

7. Deploy / reboot app.

## Login awal

Jika tabel masih kosong, sistem otomatis membuat:

```text
username: admin
password: admin123
```

Segera ganti password setelah berhasil login.

## Catatan penting

- QR/PDF/Excel di Streamlit Cloud bersifat sementara. Untuk data permanen, data utama tersimpan di Supabase PostgreSQL.
- Kalau mau QR/PDF permanen, perlu storage eksternal seperti Supabase Storage.
- File `capaska_forms.py` dan `capaska_importer.py` jika ada di project lokal kamu, upload juga ke repo agar form khusus CAPASKA dan import hasil pemeriksaan lengkap berjalan.
