-- Supabase PostgreSQL schema for MCU System
-- Jalankan di Supabase SQL Editor jika ingin membuat tabel manual.
-- app.py juga bisa membuat tabel dasar otomatis saat pertama kali run.

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    pic_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    program_type TEXT DEFAULT 'corporate'
);

CREATE TABLE IF NOT EXISTS packages (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    company_id INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    program_type TEXT DEFAULT 'corporate'
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    post_id INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    program_type TEXT DEFAULT 'corporate'
);

CREATE TABLE IF NOT EXISTS parameters (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    post_id INTEGER,
    unit TEXT,
    input_type TEXT,
    normal_value TEXT,
    reference_text TEXT,
    reference_image_path TEXT,
    config_json TEXT,
    is_required INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    program_type TEXT DEFAULT 'corporate'
);

CREATE TABLE IF NOT EXISTS package_parameters (
    id SERIAL PRIMARY KEY,
    package_id INTEGER NOT NULL,
    parameter_id INTEGER NOT NULL,
    sort_order INTEGER DEFAULT 0,
    UNIQUE(package_id, parameter_id)
);

CREATE TABLE IF NOT EXISTS participants (
    id SERIAL PRIMARY KEY,
    mcu_id TEXT,
    external_id TEXT,
    name TEXT NOT NULL,
    nik TEXT,
    gender TEXT,
    birth_date TEXT,
    company_id INTEGER,
    package_id INTEGER,
    mcu_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_id INTEGER,
    province TEXT,
    service_date TEXT,
    exam_type TEXT,
    doctor_assigned TEXT,
    nurse_assigned TEXT,
    barcode_value TEXT,
    barcode_image_path TEXT,
    barcode_created_at TEXT,
    program_type TEXT DEFAULT 'corporate'
);

CREATE TABLE IF NOT EXISTS examination_results (
    id SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL,
    parameter_id INTEGER NOT NULL,
    value TEXT,
    input_by INTEGER,
    input_post_id INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(participant_id, parameter_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    action TEXT,
    participant_id INTEGER,
    parameter_id INTEGER,
    old_value TEXT,
    new_value TEXT
);

CREATE TABLE IF NOT EXISTS participant_sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    institution_name TEXT,
    program_type TEXT DEFAULT 'capaska',
    description TEXT,
    uploaded_filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS participant_reviews (
    id SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL UNIQUE,
    review_status TEXT DEFAULT 'Belum Direview',
    final_decision TEXT,
    doctor_note TEXT,
    reviewed_by INTEGER,
    reviewed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO posts (name, description, program_type, is_active)
SELECT 'Admin', 'Post admin sistem', 'all', 1
WHERE NOT EXISTS (SELECT 1 FROM posts WHERE name = 'Admin');

INSERT INTO users (name, username, password, role, post_id, program_type, is_active)
SELECT 'Administrator', 'admin', 'admin123', 'admin', posts.id, 'all', 1
FROM posts
WHERE posts.name = 'Admin'
  AND NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');
