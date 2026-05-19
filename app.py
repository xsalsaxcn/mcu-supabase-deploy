import json
import secrets
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import qrcode
    QR_AVAILABLE = True
except Exception:
    qrcode = None
    QR_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    A4 = (595.275590551, 841.88976378)
    mm = 72 / 25.4
    ImageReader = None
    canvas = None
    REPORTLAB_AVAILABLE = False

from database import get_connection, using_postgres
from capaska_importer import import_capaska_excel
from capaska_forms import render_capaska_form

DB_PATH = Path("mcu.db")
EXPORT_DIR = Path("exports")
REFERENCE_UPLOAD_DIR = Path("uploads/reference_images")
BARCODE_DIR = Path("uploads/barcodes")
LABEL_PDF_DIR = Path("exports/labels")

PROGRAM_CORPORATE = "corporate"
PROGRAM_CAPASKA = "capaska"
PROGRAM_ALL = "all"

st.set_page_config(page_title="MCU System", layout="wide", initial_sidebar_state="collapsed")

def inject_modern_ui():
    st.markdown("""
    <style>
    /* ===== Global ===== */

    section.main > div {
        max-width: 100% !important;
    }

    div[data-testid="stAppViewContainer"] > .main {
        max-width: 100% !important;
    }

    div[data-testid="stHorizontalBlock"] {
        width: 100% !important;
    }


    :root {
        --primary: #3b82f6;
        --primary-dark: #2563eb;
        --primary-soft: #eff6ff;
        --bg: #f6f8fc;
        --card: #ffffff;
        --text: #172033;
        --muted: #748094;
        --border: #e8edf5;
        --success-bg: #e8fff3;
        --success-text: #128241;
        --warning-bg: #fff7ed;
        --warning-text: #c2410c;
        --danger-bg: #fff1f2;
        --danger-text: #be123c;
    }

    html, body, [class*="css"] {
        font-family: "Segoe UI Variable", "Segoe UI", Aptos, Inter, Arial, sans-serif !important;
        font-size: 16px;
        letter-spacing: -0.01em;
        -webkit-font-smoothing: antialiased;
        text-rendering: optimizeLegibility;
    }

    .stApp {
        background: radial-gradient(circle at top left, #eef6ff 0, #f7f9fc 34%, #f9fbff 100%);
    }

    .block-container {
        padding-top: 2.4rem;
        padding-bottom: 3rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100% !important;
        width: 100% !important;
    }

    h1, h2, h3 {
        color: var(--text);
        letter-spacing: -0.035em;
    }

    h1 {
        font-weight: 850 !important;
        font-size: 2.5rem !important;
        margin-bottom: 0.7rem !important;
        line-height: 1.12 !important;
        letter-spacing: -0.04em !important;
    }

    h2, h3 {
        font-weight: 750 !important;
    }

    p, label, span {
        color: #162033;
        font-size: 1rem;
        line-height: 1.55;
    }

    label {
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: #23324a !important;
    }

    .stMarkdown, .stText, .stCaption {
        font-size: 1rem !important;
    }

    div {
        color: #162033;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.82);
        backdrop-filter: blur(16px);
        border-right: 1px solid var(--border);
    }

    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 0.92rem;
    }

    section[data-testid="stSidebar"] label {
        font-weight: 500;
    }

    /* ===== Forms / Inputs ===== */
    div[data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid var(--border);
        border-radius: 26px;
        padding: 28px 30px;
        box-shadow: 0 16px 42px rgba(15, 23, 42, 0.045);
        width: 100%;
    }

    div[data-testid="stForm"] label {
        font-weight: 600;
        color: #344054;
    }


    input, textarea, [data-baseweb="select"] span {
        font-size: 1rem !important;
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div {
        min-height: 52px !important;
    }


    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > div {
        background: #f3f6fb !important;
        border: 1px solid transparent !important;
        border-radius: 16px !important;
        box-shadow: none !important;
    }

    div[data-baseweb="input"] input,
    div[data-baseweb="select"] input,
    textarea {
        color: #172033 !important;
        font-weight: 500;
    }

    div[data-testid="stDateInput"] div[data-baseweb="input"] > div {
        border-radius: 16px !important;
    }

    /* ===== Buttons ===== */
    .stButton > button,
    .stDownloadButton > button,
    button[kind="primary"],
    button[kind="secondary"] {
        border-radius: 16px !important;
        border: 1px solid #dbe7ff !important;
        background: #ffffff !important;
        color: #1d4ed8 !important;
        font-weight: 700 !important;
        padding: 0.65rem 1.05rem !important;
        box-shadow: 0 8px 22px rgba(37, 99, 235, 0.08);
        transition: all 0.18s ease;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        transform: translateY(-1px);
        border-color: var(--primary) !important;
        box-shadow: 0 12px 28px rgba(37, 99, 235, 0.16);
    }

    /* ===== Native containers ===== */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 24px !important;
        border-color: var(--border) !important;
        background: rgba(255, 255, 255, 0.9) !important;
        box-shadow: 0 16px 42px rgba(15, 23, 42, 0.045);
    }

    /* ===== Tabs ===== */
    button[data-baseweb="tab"] {
        border-radius: 14px 14px 0 0 !important;
        font-weight: 700 !important;
        padding: 0.75rem 1.1rem !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--primary-dark) !important;
    }

    /* ===== Tables ===== */
    div[data-testid="stDataFrame"] {
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid var(--border);
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.035);
    }

    /* ===== Alerts ===== */
    div[data-testid="stAlert"] {
        border-radius: 18px;
        border: 1px solid rgba(226, 232, 240, 0.9);
    }

    /* ===== Custom cards ===== */
    .modern-hero {
        background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 55%, #93c5fd 100%);
        color: white;
        padding: 34px 38px;
        border-radius: 30px;
        box-shadow: 0 22px 55px rgba(59, 130, 246, 0.26);
        margin-bottom: 26px;
        width: 100%;
    }

    .modern-hero h1, .modern-hero h2, .modern-hero h3, .modern-hero p, .modern-hero span {
        color: white !important;
    }

    .modern-hero .caption {
        opacity: 0.88;
        font-weight: 500;
        margin-top: 6px;
    }

    .modern-card {
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid var(--border);
        border-radius: 26px;
        padding: 26px 30px;
        margin: 16px 0 22px 0;
        box-shadow: 0 16px 42px rgba(15, 23, 42, 0.045);
        width: 100%;
    }

    .modern-card-title {
        font-weight: 850;
        font-size: 1.35rem;
        margin-bottom: 8px;
        color: #172033;
    }

    .modern-muted {
        color: var(--muted) !important;
        font-size: 1rem;
        line-height: 1.6;
    }

    .pill-blue {
        display: inline-block;
        background: var(--primary-soft);
        color: #1d4ed8;
        padding: 7px 12px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.78rem;
        margin-right: 6px;
    }

    .stage-status-done {
        background: var(--success-bg);
        color: var(--success-text);
        padding: 8px 14px;
        border-radius: 14px;
        text-align: center;
        font-weight: 800;
        font-size: 0.82rem;
    }

    .stage-status-pending {
        background: var(--warning-bg);
        color: var(--warning-text);
        padding: 8px 14px;
        border-radius: 14px;
        text-align: center;
        font-weight: 800;
        font-size: 0.82rem;
    }

    .stage-row {
        padding: 8px 0;
        border-bottom: 1px solid #f1f5f9;
    }

    .stage-row:last-child {
        border-bottom: none;
    }

    .metric-card {
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 18px 20px;
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.045);
    }

    .metric-label {
        color: var(--muted) !important;
        font-weight: 700;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .metric-value {
        color: #172033 !important;
        font-weight: 850;
        font-size: 2rem;
        line-height: 1.1;
        margin-top: 5px;
    }


    /* ===== Hamburger top menu ===== */
    .hamburger-topbar {
        background: rgba(255, 255, 255, 0.86);
        border: 1px solid #e8edf5;
        border-radius: 22px;
        padding: 12px 16px;
        margin-bottom: 18px;
        box-shadow: 0 12px 34px rgba(15, 23, 42, 0.045);
        backdrop-filter: blur(12px);
    }

    .hamburger-current {
        font-weight: 850;
        font-size: 1rem;
        color: #172033;
    }

    .hamburger-subtitle {
        margin-top: 2px;
        color: #748094 !important;
        font-size: 0.84rem;
        font-weight: 600;
    }

    div[data-testid="stPopover"] > button {
        border-radius: 18px !important;
        border: 1px solid #dbe7ff !important;
        background: #ffffff !important;
        color: #1d4ed8 !important;
        font-weight: 850 !important;
        min-height: 48px !important;
        box-shadow: 0 8px 22px rgba(37, 99, 235, 0.08);
    }



    /* ===== Bigger visible hamburger menu ===== */
    .hamburger-topbar {
        background: rgba(255, 255, 255, 0.94) !important;
        border: 1px solid #dbe7ff !important;
        border-radius: 24px !important;
        padding: 16px 22px !important;
        margin-bottom: 22px !important;
        box-shadow: 0 14px 38px rgba(37, 99, 235, 0.08) !important;
        backdrop-filter: blur(12px);
        min-height: 72px;
    }

    .hamburger-current {
        font-weight: 900 !important;
        font-size: 1.18rem !important;
        color: #172033 !important;
    }

    .hamburger-subtitle {
        margin-top: 4px !important;
        color: #667085 !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
    }

    div[data-testid="stPopover"] > button,
    div[data-testid="stPopover"] button,
    button[aria-haspopup="dialog"] {
        border-radius: 18px !important;
        border: 1px solid #1d4ed8 !important;
        background: linear-gradient(135deg, #2563eb, #60a5fa) !important;
        color: #ffffff !important;
        font-size: 1.05rem !important;
        font-weight: 900 !important;
        min-height: 58px !important;
        min-width: 150px !important;
        padding: 0.85rem 1.15rem !important;
        box-shadow: 0 14px 34px rgba(37, 99, 235, 0.24) !important;
    }

    div[data-testid="stPopover"] > button:hover,
    button[aria-haspopup="dialog"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 18px 44px rgba(37, 99, 235, 0.32) !important;
    }



    /* ===== Force visible top hamburger ===== */
    .top-menu-shell {
        width: 100%;
        margin: 0 0 24px 0;
        padding: 0;
        overflow: visible !important;
        position: relative;
        z-index: 999;
    }

    div[data-testid="stPopover"] {
        overflow: visible !important;
        position: relative !important;
        z-index: 10000 !important;
    }

    div[data-testid="stPopover"] > button,
    div[data-testid="stPopover"] button,
    button[aria-haspopup="dialog"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        min-width: 230px !important;
        height: 64px !important;
        min-height: 64px !important;
        padding: 0 26px !important;
        border-radius: 22px !important;
        border: 1px solid #1d4ed8 !important;
        background: linear-gradient(135deg, #1d4ed8, #3b82f6, #60a5fa) !important;
        color: #ffffff !important;
        font-size: 1.15rem !important;
        font-weight: 900 !important;
        line-height: 1 !important;
        box-shadow: 0 18px 44px rgba(37, 99, 235, 0.34) !important;
        opacity: 1 !important;
        visibility: visible !important;
        overflow: visible !important;
    }

    div[data-testid="stPopover"] > button p,
    div[data-testid="stPopover"] button p,
    button[aria-haspopup="dialog"] p {
        color: #ffffff !important;
        font-size: 1.15rem !important;
        font-weight: 900 !important;
        margin: 0 !important;
    }

    .hamburger-topbar {
        width: 100% !important;
        min-height: 64px !important;
        padding: 15px 22px !important;
        margin: 0 0 0 0 !important;
    }



    /* ===== Medical app typography refinements ===== */
    .modern-hero {
        min-height: 190px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        gap: 14px !important;
        background: linear-gradient(135deg, #2563eb 0%, #4f9df7 55%, #8bc4ff 100%) !important;
    }

    .hero-badge {
        display: inline-flex;
        width: fit-content;
        align-items: center;
        background: rgba(255, 255, 255, 0.92);
        color: #1d4ed8 !important;
        padding: 8px 14px;
        border-radius: 999px;
        font-weight: 800;
        font-size: 0.86rem;
        line-height: 1;
        margin-bottom: 4px;
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.14);
    }

    .hero-title {
        color: #ffffff !important;
        font-size: clamp(2rem, 3.5vw, 3rem) !important;
        font-weight: 900 !important;
        letter-spacing: -0.045em !important;
        line-height: 1.08 !important;
        margin: 0 !important;
        text-shadow: 0 2px 12px rgba(15, 23, 42, 0.16);
        white-space: normal !important;
        word-spacing: 0.08em !important;
    }

    .hero-subtitle {
        color: rgba(255, 255, 255, 0.94) !important;
        font-size: 1.08rem !important;
        font-weight: 650 !important;
        line-height: 1.55 !important;
        margin: 0 !important;
        max-width: 900px;
    }

    .modern-hero h1,
    .modern-hero h2,
    .modern-hero h3,
    .modern-hero p,
    .modern-hero span,
    .modern-hero div {
        color: inherit;
    }

    .modern-card-title {
        color: #101828 !important;
        letter-spacing: -0.025em !important;
    }

    .modern-muted {
        color: #64748b !important;
        font-weight: 550 !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        font-size: 1rem !important;
        letter-spacing: -0.01em !important;
    }



    /* ===== Login readability ===== */
    div[data-testid="stForm"] label {
        color: #1f2a44 !important;
        font-size: 1.02rem !important;
    }

    div[data-baseweb="input"] input {
        font-size: 1.08rem !important;
        color: #101828 !important;
    }



    /* ===== Top-right brand logo ===== */
    .top-right-logo {
        position: fixed;
        top: 74px;
        right: 42px;
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 300px;
        height: 130px;
        padding: 16px 22px;
        background: rgba(255, 255, 255, 0.98);
        border: 1px solid rgba(219, 231, 255, 1);
        border-radius: 30px;
        box-shadow: 0 24px 58px rgba(15, 23, 42, 0.20);
        backdrop-filter: blur(16px);
    }

    .top-right-logo img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        border-radius: 16px;
        display: block;
    }

    /* Kasih ruang kanan di hero supaya logo besar tidak menutup teks */
    .modern-hero {
        padding-right: 390px !important;
        min-height: 230px !important;
    }

    @media (max-width: 900px) {
        .top-right-logo {
            position: static;
            width: 240px;
            height: 105px;
            margin-left: auto;
            margin-bottom: 14px;
        }

        .modern-hero {
            padding-right: 24px !important;
            min-height: 210px !important;
        }
    }


    @media (max-width: 900px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100% !important;
        }

        h1 {
            font-size: 1.85rem !important;
        }

        .modern-hero {
            padding: 22px;
            border-radius: 24px;
        }
    }

    /* ===== Awam-friendly mobile layout ===== */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
            padding-bottom: 2rem !important;
            max-width: 100% !important;
        }

        h1 {
            font-size: 1.85rem !important;
            line-height: 1.15 !important;
        }

        h2 {
            font-size: 1.45rem !important;
        }

        h3 {
            font-size: 1.2rem !important;
        }

        p, label, span, div {
            font-size: 0.98rem !important;
            line-height: 1.5 !important;
        }

        .modern-hero {
            min-height: auto !important;
            padding: 22px 18px !important;
            padding-right: 18px !important;
            border-radius: 22px !important;
            margin-bottom: 18px !important;
        }

        .hero-title {
            font-size: 1.85rem !important;
            line-height: 1.15 !important;
        }

        .hero-subtitle {
            font-size: 0.98rem !important;
            line-height: 1.5 !important;
        }

        .hero-badge {
            font-size: 0.76rem !important;
            padding: 7px 11px !important;
        }

        .modern-card {
            padding: 18px 16px !important;
            border-radius: 20px !important;
            margin: 12px 0 16px 0 !important;
        }

        .modern-card-title {
            font-size: 1.18rem !important;
        }

        .modern-muted {
            font-size: 0.95rem !important;
        }

        .top-right-logo {
            position: static !important;
            width: 210px !important;
            height: 92px !important;
            margin: 0 0 12px auto !important;
            border-radius: 24px !important;
        }

        .top-menu-shell {
            margin-bottom: 16px !important;
        }

        div[data-testid="stPopover"] > button,
        div[data-testid="stPopover"] button,
        button[aria-haspopup="dialog"] {
            width: 100% !important;
            min-width: 100% !important;
            height: 54px !important;
            min-height: 54px !important;
            font-size: 1rem !important;
            border-radius: 18px !important;
        }

        .hamburger-topbar {
            min-height: auto !important;
            padding: 13px 15px !important;
            border-radius: 18px !important;
        }

        .hamburger-current {
            font-size: 1.05rem !important;
        }

        .hamburger-subtitle {
            font-size: 0.82rem !important;
        }

        div[data-testid="stForm"] {
            padding: 18px 16px !important;
            border-radius: 20px !important;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div {
            min-height: 54px !important;
            border-radius: 15px !important;
        }

        input, textarea, [data-baseweb="select"] span {
            font-size: 1rem !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            width: 100% !important;
            min-height: 48px !important;
            font-size: 1rem !important;
            border-radius: 15px !important;
            margin-top: 4px !important;
        }

        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.65rem !important;
        }

        div[data-testid="stDataFrame"] {
            max-width: 100% !important;
            overflow-x: auto !important;
            border-radius: 16px !important;
        }

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.86);
            border: 1px solid #e8edf5;
            border-radius: 16px;
            padding: 12px 14px;
            margin-bottom: 8px;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.55rem !important;
        }

        .stage-status-done,
        .stage-status-pending {
            display: block;
            width: 100%;
            padding: 8px 10px !important;
            font-size: 0.78rem !important;
        }

        button[data-baseweb="tab"] {
            font-size: 0.88rem !important;
            padding: 0.65rem 0.75rem !important;
        }

        div[role="tablist"] {
            overflow-x: auto !important;
            white-space: nowrap !important;
        }
    }

    /* Extra small phones */
    @media (max-width: 420px) {
        .block-container {
            padding-left: 0.65rem !important;
            padding-right: 0.65rem !important;
        }

        .hero-title {
            font-size: 1.6rem !important;
        }

        .top-right-logo {
            width: 180px !important;
            height: 80px !important;
        }
    }


    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="top-right-logo">
        <img src="https://r2.image-upload.app/ptImg/BrzkxkdW.jpg" alt="Logo" />
    </div>
    """, unsafe_allow_html=True)


def render_hero(title, subtitle="", badge=None):
    badge_html = f'<div class="hero-badge">{badge}</div>' if badge else ""
    st.markdown(
        f"""
        <section class="modern-hero">
            {badge_html}
            <div class="hero-title">{title}</div>
            <div class="hero-subtitle">{subtitle}</div>
        </section>
        """,
        unsafe_allow_html=True
    )



def render_simple_steps(title, steps):
    items_html = ""

    for idx, step in enumerate(steps, start=1):
        items_html += f"""
        <div style="display:flex; gap:12px; align-items:flex-start; margin:10px 0;">
            <div style="
                min-width:28px;
                height:28px;
                border-radius:999px;
                background:#eff6ff;
                color:#1d4ed8;
                display:flex;
                align-items:center;
                justify-content:center;
                font-weight:850;
                font-size:0.9rem;
            ">{idx}</div>
            <div style="font-weight:650; color:#23324a;">{step}</div>
        </div>
        """

    st.markdown(
        f"""
        <div class="modern-card">
            <div class="modern-card-title">{title}</div>
            <div class="modern-muted">Ikuti langkah sederhana berikut.</div>
            <div style="margin-top:12px;">{items_html}</div>
        </div>
        """,
        unsafe_allow_html=True
    )



def render_card_title(title, subtitle=""):
    subtitle_html = f'<div class="modern-muted">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="modern-card-title">{title}</div>
        {subtitle_html}
        """,
        unsafe_allow_html=True
    )


inject_modern_ui()



def check_database_exists():
    """
    Kalau SUPABASE_DB_URL tersedia, app memakai Supabase PostgreSQL dan tidak perlu file mcu.db.
    Kalau SUPABASE_DB_URL belum diisi, app fallback ke SQLite lokal.
    """
    if using_postgres():
        return

    if not DB_PATH.exists():
        st.error(
            "Database mcu.db belum ditemukan dan SUPABASE_DB_URL belum terbaca. "
            "Isi SUPABASE_DB_URL di Streamlit Secrets, lalu reboot app."
        )
        st.stop()


def column_exists(cur, table_name, column_name):
    if using_postgres():
        cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ?
          AND column_name = ?
        """, (table_name, column_name))
        return cur.fetchone() is not None

    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in cur.fetchall()
    ]
    return column_name in columns


def add_column_if_not_exists(cur, table_name, column_name, definition):
    if not column_exists(cur, table_name, column_name):
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def ensure_postgres_base_schema():
    """
    Supabase/PostgreSQL base schema.
    Ini dibutuhkan karena Streamlit Cloud tidak memiliki mcu.db.
    """
    if not using_postgres():
        return

    conn = get_connection()
    cur = conn.cursor()

    schema_sql = [
        """
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            pic_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            program_type TEXT DEFAULT 'corporate'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packages (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            company_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            program_type TEXT DEFAULT 'corporate'
        )
        """,
        """
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
        )
        """,
        """
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS package_parameters (
            id SERIAL PRIMARY KEY,
            package_id INTEGER NOT NULL,
            parameter_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            UNIQUE(package_id, parameter_id)
        )
        """,
        """
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
        )
        """,
        """
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            action TEXT,
            participant_id INTEGER,
            parameter_id INTEGER,
            old_value TEXT,
            new_value TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS participant_sources (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            institution_name TEXT,
            program_type TEXT DEFAULT 'capaska',
            description TEXT,
            uploaded_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS participant_reviews (
            id SERIAL PRIMARY KEY,
            participant_id INTEGER NOT NULL UNIQUE,
            review_status TEXT DEFAULT 'Belum Direview',
            final_decision TEXT,
            doctor_note TEXT,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]

    for sql in schema_sql:
        cur.execute(sql)

    # Seed admin minimal.
    cur.execute("SELECT id FROM posts WHERE name = ? LIMIT 1", ("Admin",))
    admin_post = cur.fetchone()

    if admin_post:
        admin_post_id = admin_post["id"]
    else:
        cur.execute("""
        INSERT INTO posts (name, description, program_type, is_active)
        VALUES (?, ?, ?, 1)
        """, ("Admin", "Post admin sistem", "all"))
        admin_post_id = cur.lastrowid

    cur.execute("SELECT id FROM users WHERE username = ? LIMIT 1", ("admin",))
    admin_user = cur.fetchone()

    if not admin_user:
        cur.execute("""
        INSERT INTO users (name, username, password, role, post_id, program_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """, ("Administrator", "admin", "admin123", "admin", admin_post_id, "all"))

    conn.commit()
    conn.close()


def ensure_runtime_schema():
    ensure_postgres_base_schema()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS participant_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        institution_name TEXT,
        program_type TEXT DEFAULT 'capaska',
        description TEXT,
        uploaded_filename TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS participant_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER NOT NULL UNIQUE,
        review_status TEXT DEFAULT 'Belum Direview',
        final_decision TEXT,
        doctor_note TEXT,
        reviewed_by INTEGER,
        reviewed_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    add_column_if_not_exists(cur, "participants", "external_id", "TEXT")
    add_column_if_not_exists(cur, "participants", "province", "TEXT")
    add_column_if_not_exists(cur, "participants", "source_id", "INTEGER")
    add_column_if_not_exists(cur, "participants", "service_date", "TEXT")
    add_column_if_not_exists(cur, "participants", "exam_type", "TEXT")
    add_column_if_not_exists(cur, "participants", "doctor_assigned", "TEXT")
    add_column_if_not_exists(cur, "participants", "nurse_assigned", "TEXT")
    add_column_if_not_exists(cur, "participants", "barcode_value", "TEXT")
    add_column_if_not_exists(cur, "participants", "barcode_image_path", "TEXT")
    add_column_if_not_exists(cur, "participants", "barcode_created_at", "TEXT")
    add_column_if_not_exists(cur, "users", "program_type", "TEXT DEFAULT 'corporate'")
    add_column_if_not_exists(cur, "posts", "program_type", "TEXT DEFAULT 'corporate'")
    add_column_if_not_exists(cur, "packages", "program_type", "TEXT DEFAULT 'corporate'")
    add_column_if_not_exists(cur, "parameters", "program_type", "TEXT DEFAULT 'corporate'")
    add_column_if_not_exists(cur, "participants", "program_type", "TEXT DEFAULT 'corporate'")

    cur.execute("UPDATE users SET program_type = 'corporate' WHERE program_type IS NULL OR program_type = ''")
    cur.execute("UPDATE posts SET program_type = 'corporate' WHERE program_type IS NULL OR program_type = ''")
    cur.execute("UPDATE packages SET program_type = 'corporate' WHERE program_type IS NULL OR program_type = ''")
    cur.execute("UPDATE parameters SET program_type = 'corporate' WHERE program_type IS NULL OR program_type = ''")
    cur.execute("UPDATE participants SET program_type = 'corporate' WHERE program_type IS NULL OR program_type = ''")
    cur.execute("UPDATE users SET program_type = 'all' WHERE role = 'admin' OR username = 'admin'")
    cur.execute("UPDATE posts SET program_type = 'all' WHERE name = 'Admin'")

    capaska_keywords = [
        "CAPASKA", "BPIP", "Kesehatan Mata", "Kesehatan Gigi", "Gigi & Mulut", "Dental",
        "Kesehatan THT", "THT", "Penyakit Dalam", "Kesehatan Jantung", "Pembuluh Darah",
        "Ortopedi", "Radiologi", "Registrasi CAPASKA"
    ]
    for keyword in capaska_keywords:
        cur.execute("""
        UPDATE packages SET program_type = 'capaska'
        WHERE name LIKE ? OR description LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%"))
        cur.execute("""
        UPDATE posts SET program_type = 'capaska'
        WHERE name LIKE ? OR description LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%"))

    for post_name in ["Registrasi", "Antropometri", "Vital Sign", "Lab", "Gigi", "Dokter"]:
        cur.execute("UPDATE posts SET program_type = 'corporate' WHERE name = ?", (post_name,))

    cur.execute("""
    UPDATE parameters
    SET program_type = (SELECT posts.program_type FROM posts WHERE posts.id = parameters.post_id)
    WHERE post_id IS NOT NULL
    """)
    cur.execute("""
    UPDATE participants
    SET program_type = (SELECT packages.program_type FROM packages WHERE packages.id = participants.package_id)
    WHERE package_id IS NOT NULL
    """)
    cur.execute("""
    UPDATE users
    SET program_type = (SELECT posts.program_type FROM posts WHERE posts.id = users.post_id)
    WHERE role != 'admin' AND username != 'admin' AND post_id IS NOT NULL
    """)
    cur.execute("UPDATE users SET program_type = 'all' WHERE role = 'admin' OR username = 'admin'")


    # =========================
    # DEFAULT CAPASKA WORKFLOW
    # =========================
    # Pastikan semua post pemeriksaan CAPASKA, operator, parameter minimal,
    # dan mapping package_parameters tersedia.
    # Ini penting untuk:
    # - akun operator lengkap muncul di Master Data > User / Operator
    # - setiap operator hanya melihat parameter sesuai post-nya
    # - progress stage tetap muncul seperti versi lokal sebelumnya

    capaska_stage_defs = [
        {
            "post_name": "Registrasi CAPASKA",
            "description": "Registrasi dan verifikasi identitas peserta CAPASKA",
            "username": "capaska_registrasi",
            "password": "registrasi123",
            "operator_name": "Operator CAPASKA Registrasi",
            "parameter_name": "Status Registrasi CAPASKA",
            "sort_order": 10,
        },
        {
            "post_name": "Kesehatan Mata",
            "description": "Input pemeriksaan kesehatan mata CAPASKA",
            "username": "capaska_mata",
            "password": "mata123",
            "operator_name": "Operator CAPASKA Mata",
            "parameter_name": "Status Pemeriksaan Mata",
            "sort_order": 20,
        },
        {
            "post_name": "Penyakit Dalam",
            "description": "Input pemeriksaan penyakit dalam CAPASKA",
            "username": "capaska_pd",
            "password": "pd123",
            "operator_name": "Operator CAPASKA Penyakit Dalam",
            "parameter_name": "Status Pemeriksaan Penyakit Dalam",
            "sort_order": 30,
        },
        {
            "post_name": "Kesehatan Gigi & Mulut + Dental panoramik",
            "description": "Input pemeriksaan kesehatan gigi, mulut, dan dental panoramik CAPASKA",
            "username": "capaska_gigi",
            "password": "gigi123",
            "operator_name": "Operator CAPASKA Gigi",
            "parameter_name": "Status Pemeriksaan Gigi & Mulut",
            "sort_order": 40,
        },
        {
            "post_name": "Kesehatan THT",
            "description": "Input pemeriksaan THT CAPASKA",
            "username": "capaska_tht",
            "password": "tht123",
            "operator_name": "Operator CAPASKA THT",
            "parameter_name": "Status Pemeriksaan THT",
            "sort_order": 50,
        },
        {
            "post_name": "Kesehatan Jantung dan Pembuluh Darah",
            "description": "Input pemeriksaan kesehatan jantung dan pembuluh darah CAPASKA",
            "username": "capaska_jantung",
            "password": "jantung123",
            "operator_name": "Operator CAPASKA Jantung",
            "parameter_name": "Status Pemeriksaan Jantung dan Pembuluh Darah",
            "sort_order": 60,
        },
        {
            "post_name": "Ortopedi",
            "description": "Input pemeriksaan ortopedi CAPASKA",
            "username": "capaska_ortopedi",
            "password": "ortopedi123",
            "operator_name": "Operator CAPASKA Ortopedi",
            "parameter_name": "Status Pemeriksaan Ortopedi",
            "sort_order": 70,
        },
        {
            "post_name": "Radiologi",
            "description": "Input pemeriksaan radiologi CAPASKA",
            "username": "capaska_radiologi",
            "password": "radiologi123",
            "operator_name": "Operator CAPASKA Radiologi",
            "parameter_name": "Status Pemeriksaan Radiologi",
            "sort_order": 80,
        },
    ]

    capaska_post_ids = []
    capaska_parameter_ids = []

    for stage in capaska_stage_defs:
        cur.execute("""
        SELECT id
        FROM posts
        WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
        LIMIT 1
        """, (stage["post_name"],))
        post_row = cur.fetchone()

        if post_row:
            post_id = post_row["id"]
            cur.execute("""
            UPDATE posts
            SET description = COALESCE(NULLIF(description, ''), ?),
                program_type = ?,
                is_active = 1
            WHERE id = ?
            """, (
                stage["description"],
                PROGRAM_CAPASKA,
                post_id
            ))
        else:
            cur.execute("""
            INSERT INTO posts (name, description, program_type, is_active)
            VALUES (?, ?, ?, 1)
            """, (
                stage["post_name"],
                stage["description"],
                PROGRAM_CAPASKA
            ))
            post_id = cur.lastrowid

        capaska_post_ids.append(post_id)

        # Buat minimal 1 parameter per post agar progress stage selalu muncul.
        # Kalau post sudah punya parameter aktif, jangan duplikasi.
        cur.execute("""
        SELECT id
        FROM parameters
        WHERE post_id = ?
          AND is_active = 1
          AND program_type = ?
        ORDER BY sort_order ASC, id ASC
        LIMIT 1
        """, (
            post_id,
            PROGRAM_CAPASKA
        ))
        parameter_row = cur.fetchone()

        if parameter_row:
            parameter_id = parameter_row["id"]
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                stage["parameter_name"],
                stage["post_name"],
                post_id,
                "",
                "select",
                "Done",
                "Parameter minimal otomatis untuk menjaga progress stage dan hak akses operator.",
                "",
                json.dumps(["", "Done", "Belum", "Normal", "Abnormal", "Perlu Review"]),
                1,
                stage["sort_order"],
                PROGRAM_CAPASKA
            ))
            parameter_id = cur.lastrowid

        capaska_parameter_ids.append(parameter_id)

        # Buat / update user operator per post.
        cur.execute("""
        SELECT id
        FROM users
        WHERE username = ?
        LIMIT 1
        """, (stage["username"],))
        user_row = cur.fetchone()

        if user_row:
            cur.execute("""
            UPDATE users
            SET name = ?,
                role = 'operator',
                post_id = ?,
                program_type = ?,
                is_active = 1
            WHERE id = ?
            """, (
                stage["operator_name"],
                post_id,
                PROGRAM_CAPASKA,
                user_row["id"]
            ))
        else:
            cur.execute("""
            INSERT INTO users
            (
                name,
                username,
                password,
                role,
                post_id,
                program_type,
                is_active
            )
            VALUES (?, ?, ?, 'operator', ?, ?, 1)
            """, (
                stage["operator_name"],
                stage["username"],
                stage["password"],
                post_id,
                PROGRAM_CAPASKA
            ))

    # Mapping semua parameter CAPASKA ke semua package CAPASKA agar:
    # - parameter muncul pada operator sesuai post
    # - progress stage selalu lengkap
    cur.execute("""
    SELECT id
    FROM packages
    WHERE program_type = ?
      AND is_active = 1
    """, (PROGRAM_CAPASKA,))
    capaska_packages = cur.fetchall()

    for package_row in capaska_packages:
        package_id_for_map = package_row["id"]

        cur.execute("""
        SELECT parameters.id AS parameter_id
        FROM parameters
        JOIN posts ON posts.id = parameters.post_id
        WHERE parameters.program_type = ?
          AND posts.program_type = ?
          AND parameters.is_active = 1
          AND posts.name != 'Admin'
        """, (
            PROGRAM_CAPASKA,
            PROGRAM_CAPASKA
        ))

        parameters_to_map = cur.fetchall()

        for param_row in parameters_to_map:
            parameter_id_for_map = param_row["parameter_id"]

            cur.execute("""
            SELECT id
            FROM package_parameters
            WHERE package_id = ?
              AND parameter_id = ?
            LIMIT 1
            """, (
                package_id_for_map,
                parameter_id_for_map
            ))

            existing_map = cur.fetchone()

            if not existing_map:
                cur.execute("""
                INSERT INTO package_parameters (package_id, parameter_id, sort_order)
                VALUES (?, ?, 0)
                """, (
                    package_id_for_map,
                    parameter_id_for_map
                ))


    # Default account untuk dokter/supervisor review CAPASKA.
    # Dibuat otomatis jika belum ada agar user bisa langsung testing fitur Review Hasil.
    cur.execute("""
    SELECT id
    FROM posts
    WHERE name = 'Review Dokter CAPASKA'
    LIMIT 1
    """)
    review_post = cur.fetchone()

    if review_post:
        review_post_id = review_post["id"]
    else:
        cur.execute("""
        INSERT INTO posts
        (
            name,
            description,
            program_type
        )
        VALUES (?, ?, ?)
        """, (
            "Review Dokter CAPASKA",
            "Post khusus dokter/supervisor untuk review hasil CAPASKA",
            PROGRAM_CAPASKA
        ))
        review_post_id = cur.lastrowid

    default_review_users = [
        (
            "Dokter Review CAPASKA",
            "dokter_review",
            "dokter123",
            "doctor",
            review_post_id,
            PROGRAM_CAPASKA
        ),
        (
            "Supervisor CAPASKA",
            "supervisor_capaska",
            "supervisor123",
            "supervisor",
            review_post_id,
            PROGRAM_CAPASKA
        ),
    ]

    for default_user in default_review_users:
        cur.execute("""
        SELECT id
        FROM users
        WHERE username = ?
        LIMIT 1
        """, (default_user[1],))

        existing_user = cur.fetchone()

        if not existing_user:
            cur.execute("""
            INSERT INTO users
            (
                name,
                username,
                password,
                role,
                post_id,
                program_type,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, default_user)

    conn.commit()
    conn.close()


def display_value(value):
    if value is None:
        return "-"
    value = str(value).strip()
    if value == "" or value.lower() in ["none", "nan", "null"]:
        return "-"
    return value


def safe_strip(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_mcu_date(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return date.today()


def program_label(program_type):
    if program_type == PROGRAM_CAPASKA:
        return "CAPASKA / BPIP"
    if program_type == PROGRAM_CORPORATE:
        return "MCU Corporate"
    return "All Program"


def get_user_program(user):
    return user.get("program_type") or PROGRAM_CORPORATE


def login(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT users.*, posts.name AS post_name
    FROM users
    LEFT JOIN posts ON users.post_id = posts.id
    WHERE users.username = ? AND users.password = ? AND users.is_active = 1
    """, (username, password))
    user = cur.fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT users.*, posts.name AS post_name
    FROM users
    LEFT JOIN posts ON users.post_id = posts.id
    WHERE users.id = ?
      AND users.is_active = 1
    """, (user_id,))
    user = cur.fetchone()
    conn.close()
    return dict(user) if user else None


def get_query_token():
    try:
        token = st.query_params.get("auth_token", "")
        if isinstance(token, list):
            token = token[0] if token else ""
        return str(token).strip()
    except Exception:
        try:
            params = st.experimental_get_query_params()
            token = params.get("auth_token", [""])[0]
            return str(token).strip()
        except Exception:
            return ""


def set_query_token(token):
    try:
        st.query_params["auth_token"] = token
    except Exception:
        try:
            st.experimental_set_query_params(auth_token=token)
        except Exception:
            pass


def clear_query_token():
    try:
        if "auth_token" in st.query_params:
            del st.query_params["auth_token"]
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def create_auth_session(user_id):
    token = secrets.token_urlsafe(32)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO auth_sessions
    (
        token,
        user_id,
        is_active
    )
    VALUES (?, ?, 1)
    """, (
        token,
        user_id
    ))

    conn.commit()
    conn.close()

    return token


def get_user_from_auth_token(token):
    if not token:
        return None

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        auth_sessions.user_id
    FROM auth_sessions
    JOIN users ON users.id = auth_sessions.user_id
    WHERE auth_sessions.token = ?
      AND auth_sessions.is_active = 1
      AND users.is_active = 1
    """, (token,))

    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    user_id = row["user_id"]

    cur.execute("""
    UPDATE auth_sessions
    SET last_seen_at = CURRENT_TIMESTAMP
    WHERE token = ?
    """, (token,))

    conn.commit()
    conn.close()

    return get_user_by_id(user_id)


def restore_login_from_persistent_session():
    token = get_query_token()

    if not token:
        return None

    user = get_user_from_auth_token(token)

    if not user:
        clear_query_token()
        return None

    return user


def invalidate_auth_session(token):
    if not token:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE auth_sessions
    SET is_active = 0
    WHERE token = ?
    """, (token,))

    conn.commit()
    conn.close()


def logout():
    token = get_query_token()
    invalidate_auth_session(token)
    clear_query_token()

    st.session_state.clear()
    st.rerun()


def get_companies():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM companies ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_packages(program_type=None):
    conn = get_connection()
    cur = conn.cursor()
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        cur.execute("""
        SELECT packages.*, companies.name AS company_name
        FROM packages
        LEFT JOIN companies ON packages.company_id = companies.id
        WHERE packages.is_active = 1 AND packages.program_type = ?
        ORDER BY packages.name
        """, (program_type,))
    else:
        cur.execute("""
        SELECT packages.*, companies.name AS company_name
        FROM packages
        LEFT JOIN companies ON packages.company_id = companies.id
        WHERE packages.is_active = 1
        ORDER BY packages.name
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]



def get_or_create_company_id(name, address="", pic_name=""):
    clean_name = safe_strip(name) or "BPIP / CAPASKA"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id
    FROM companies
    WHERE LOWER(name) = LOWER(?)
    LIMIT 1
    """, (clean_name,))

    existing = cur.fetchone()

    if existing:
        conn.close()
        return existing["id"]

    cur.execute("""
    INSERT INTO companies (name, address, pic_name)
    VALUES (?, ?, ?)
    """, (clean_name, address, pic_name))

    company_id = cur.lastrowid
    conn.commit()
    conn.close()

    return company_id


def get_or_create_package_id(name, company_id, program_type=PROGRAM_CAPASKA, description="Auto created from import database"):
    clean_name = safe_strip(name) or "CAPASKA 2025/2026"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id
    FROM packages
    WHERE LOWER(name) = LOWER(?)
      AND program_type = ?
    LIMIT 1
    """, (clean_name, program_type))

    existing = cur.fetchone()

    if existing:
        conn.close()
        return existing["id"]

    cur.execute("""
    INSERT INTO packages (name, description, company_id, is_active, program_type)
    VALUES (?, ?, ?, 1, ?)
    """, (clean_name, description, company_id, program_type))

    package_id = cur.lastrowid

    # Mapping cepat: jika package baru CAPASKA dibuat otomatis saat import,
    # hubungkan langsung ke semua parameter CAPASKA yang sudah ada.
    if program_type == PROGRAM_CAPASKA:
        cur.execute("""
        SELECT parameters.id AS parameter_id
        FROM parameters
        JOIN posts ON posts.id = parameters.post_id
        WHERE parameters.program_type = ?
          AND posts.program_type = ?
          AND parameters.is_active = 1
          AND posts.name != 'Admin'
        """, (
            PROGRAM_CAPASKA,
            PROGRAM_CAPASKA
        ))

        for param_row in cur.fetchall():
            cur.execute("""
            SELECT id
            FROM package_parameters
            WHERE package_id = ?
              AND parameter_id = ?
            LIMIT 1
            """, (
                package_id,
                param_row["parameter_id"]
            ))

            if not cur.fetchone():
                cur.execute("""
                INSERT INTO package_parameters (package_id, parameter_id, sort_order)
                VALUES (?, ?, 0)
                """, (
                    package_id,
                    param_row["parameter_id"]
                ))

    conn.commit()
    conn.close()

    return package_id


def get_posts(program_type=None, include_admin=False):
    conn = get_connection()
    cur = conn.cursor()
    where = []
    params = []
    if not include_admin:
        where.append("name != 'Admin'")
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where.append("program_type = ?")
        params.append(program_type)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    cur.execute(f"SELECT * FROM posts {where_sql} ORDER BY id", params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]



def get_participant_sources(program_type=None):
    conn = get_connection()
    cur = conn.cursor()

    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        cur.execute("""
        SELECT *
        FROM participant_sources
        WHERE program_type = ?
           OR program_type IS NULL
           OR program_type = ''
           OR program_type = 'all'
        ORDER BY created_at DESC, id DESC
        """, (program_type,))
    else:
        cur.execute("""
        SELECT *
        FROM participant_sources
        ORDER BY created_at DESC, id DESC
        """)

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_participant_source_stats(source_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM participant_sources
    WHERE id = ?
    """, (source_id,))
    source = cur.fetchone()

    if not source:
        conn.close()
        return None

    cur.execute("""
    SELECT COUNT(*) AS total
    FROM participants
    WHERE source_id = ?
    """, (source_id,))
    participant_count = cur.fetchone()["total"]

    cur.execute("""
    SELECT COUNT(*) AS total
    FROM examination_results
    WHERE participant_id IN (
        SELECT id
        FROM participants
        WHERE source_id = ?
    )
    """, (source_id,))
    result_count = cur.fetchone()["total"]

    cur.execute("""
    SELECT COUNT(*) AS total
    FROM audit_logs
    WHERE participant_id IN (
        SELECT id
        FROM participants
        WHERE source_id = ?
    )
    """, (source_id,))
    audit_count = cur.fetchone()["total"]

    cur.execute("""
    SELECT COUNT(*) AS total
    FROM participants
    WHERE source_id = ?
      AND barcode_value IS NOT NULL
      AND TRIM(barcode_value) != ''
    """, (source_id,))
    barcode_value_count = cur.fetchone()["total"]

    cur.execute("""
    SELECT barcode_image_path
    FROM participants
    WHERE source_id = ?
      AND barcode_image_path IS NOT NULL
      AND TRIM(barcode_image_path) != ''
    """, (source_id,))
    barcode_paths = [
        row["barcode_image_path"]
        for row in cur.fetchall()
    ]

    conn.close()

    barcode_file_count = 0

    for barcode_path in barcode_paths:
        try:
            if barcode_path and Path(barcode_path).exists():
                barcode_file_count += 1
        except Exception:
            pass

    source_dict = dict(source)

    return {
        "source": source_dict,
        "participant_count": participant_count,
        "result_count": result_count,
        "audit_count": audit_count,
        "barcode_value_count": barcode_value_count,
        "barcode_count": barcode_file_count,
        "barcode_folder": str(BARCODE_DIR).replace("\\", "/"),
    }


def delete_participant_source_database(source_id, delete_barcode_files=True):
    stats = get_participant_source_stats(source_id)

    if not stats:
        raise ValueError("Database instansi tidak ditemukan.")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        id,
        barcode_image_path
    FROM participants
    WHERE source_id = ?
    """, (source_id,))

    participants = [dict(row) for row in cur.fetchall()]
    participant_ids = [row["id"] for row in participants]

    deleted_barcode_files = 0

    if delete_barcode_files:
        for participant in participants:
            barcode_path = participant.get("barcode_image_path")

            if barcode_path:
                try:
                    path = Path(barcode_path)

                    if path.exists() and path.is_file():
                        path.unlink()
                        deleted_barcode_files += 1
                except Exception:
                    pass

    cur.execute("""
    DELETE FROM audit_logs
    WHERE participant_id IN (
        SELECT id
        FROM participants
        WHERE source_id = ?
    )
    """, (source_id,))

    deleted_audits = cur.rowcount

    cur.execute("""
    DELETE FROM examination_results
    WHERE participant_id IN (
        SELECT id
        FROM participants
        WHERE source_id = ?
    )
    """, (source_id,))

    deleted_results = cur.rowcount

    cur.execute("""
    DELETE FROM participants
    WHERE source_id = ?
    """, (source_id,))

    deleted_participants = cur.rowcount

    cur.execute("""
    DELETE FROM participant_sources
    WHERE id = ?
    """, (source_id,))

    deleted_sources = cur.rowcount

    conn.commit()
    conn.close()

    return {
        "source_id": source_id,
        "source_name": stats["source"].get("name"),
        "deleted_sources": deleted_sources,
        "deleted_participants": deleted_participants,
        "deleted_results": deleted_results,
        "deleted_audits": deleted_audits,
        "deleted_barcode_files": deleted_barcode_files,
        "participant_ids_deleted": participant_ids,
    }



def get_users_admin(program_type=None):
    conn = get_connection()
    cur = conn.cursor()
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        cur.execute("""
        SELECT users.id, users.name, users.username, users.role, users.program_type, users.is_active,
               posts.name AS post_name, users.created_at
        FROM users
        LEFT JOIN posts ON users.post_id = posts.id
        WHERE users.program_type = ?
        ORDER BY users.id DESC
        """, (program_type,))
    else:
        cur.execute("""
        SELECT users.id, users.name, users.username, users.role, users.program_type, users.is_active,
               posts.name AS post_name, users.created_at
        FROM users
        LEFT JOIN posts ON users.post_id = posts.id
        ORDER BY users.id DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_parameters_admin(program_type=None):
    conn = get_connection()
    cur = conn.cursor()
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        cur.execute("""
        SELECT parameters.id, parameters.name, parameters.category, parameters.program_type,
               posts.name AS post_name, parameters.unit, parameters.input_type,
               parameters.normal_value, parameters.reference_text, parameters.reference_image_path,
               parameters.config_json, parameters.is_required, parameters.is_active, parameters.sort_order
        FROM parameters
        LEFT JOIN posts ON parameters.post_id = posts.id
        WHERE parameters.program_type = ?
        ORDER BY parameters.id DESC
        """, (program_type,))
    else:
        cur.execute("""
        SELECT parameters.id, parameters.name, parameters.category, parameters.program_type,
               posts.name AS post_name, parameters.unit, parameters.input_type,
               parameters.normal_value, parameters.reference_text, parameters.reference_image_path,
               parameters.config_json, parameters.is_required, parameters.is_active, parameters.sort_order
        FROM parameters
        LEFT JOIN posts ON parameters.post_id = posts.id
        ORDER BY parameters.id DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_participants_admin(program_type=None, limit=500):
    conn = get_connection()
    cur = conn.cursor()
    where = ""
    params = []
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where = "WHERE participants.program_type = ?"
        params.append(program_type)
    params.append(limit)
    cur.execute(f"""
    SELECT participants.id, participants.mcu_id, participants.external_id, participants.province,
           participant_sources.name AS source_name, participants.name, participants.nik, participants.gender,
           participants.birth_date, participants.program_type, companies.name AS company_name,
           packages.name AS package_name, participants.mcu_date, participants.service_date,
           participants.exam_type, participants.doctor_assigned, participants.nurse_assigned, participants.created_at
    FROM participants
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN participant_sources ON participants.source_id = participant_sources.id
    {where}
    ORDER BY participants.id DESC
    LIMIT ?
    """, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_company(name, address, pic_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, address, pic_name) VALUES (?, ?, ?)", (name, address, pic_name))
    conn.commit()
    conn.close()


def create_post(name, description, program_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO posts (name, description, program_type) VALUES (?, ?, ?)", (name, description, program_type))
    conn.commit()
    conn.close()


def create_package(name, description, company_id, program_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO packages (name, description, company_id, is_active, program_type)
    VALUES (?, ?, ?, 1, ?)
    """, (name, description, company_id, program_type))
    conn.commit()
    conn.close()


def create_user(name, username, password, role, post_id, program_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (name, username, password, role, post_id, program_type)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (name, username, password, role, post_id, program_type))
    conn.commit()
    conn.close()


def save_reference_image(uploaded_file):
    if uploaded_file is None:
        return None
    REFERENCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = uploaded_file.name.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{original_name}"
    file_path = REFERENCE_UPLOAD_DIR / filename
    file_path.write_bytes(uploaded_file.getbuffer())
    return str(file_path).replace("\\", "/")


def create_parameter(name, category, post_id, unit, input_type, normal_value, reference_text,
                     reference_image_path, config_json, is_required, sort_order, package_ids, program_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO parameters
    (name, category, post_id, unit, input_type, normal_value, reference_text, reference_image_path,
     config_json, is_required, is_active, sort_order, program_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (
        name, category, post_id, unit, input_type, normal_value, reference_text, reference_image_path,
        config_json, 1 if is_required else 0, sort_order, program_type
    ))
    parameter_id = cur.lastrowid
    for package_id in package_ids:
        cur.execute("""
        INSERT OR IGNORE INTO package_parameters (package_id, parameter_id, sort_order)
        VALUES (?, ?, ?)
        """, (package_id, parameter_id, sort_order))
    conn.commit()
    conn.close()

# =========================
# IMPORT DATABASE PESERTA INSTANSI
# =========================

def clean_import_text(value):
    if pd.isna(value):
        return ""
    value = str(value).strip()
    if value.lower() in ["nan", "none", "null"]:
        return ""
    return value


def normalize_import_date(value):
    if pd.isna(value) or value == "":
        return ""
    try:
        parsed = pd.to_datetime(value)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return clean_import_text(value)



INDONESIA_PROVINCES = [
    "Aceh",
    "Sumatera Utara",
    "Sumatra Utara",
    "Sumatera Barat",
    "Sumatra Barat",
    "Riau",
    "Kepulauan Riau",
    "Jambi",
    "Sumatera Selatan",
    "Sumatra Selatan",
    "Bengkulu",
    "Lampung",
    "Kepulauan Bangka Belitung",
    "Bangka Belitung",
    "DKI Jakarta",
    "Jakarta",
    "Jawa Barat",
    "Jawa Tengah",
    "DI Yogyakarta",
    "Yogyakarta",
    "Jawa Timur",
    "Banten",
    "Bali",
    "Nusa Tenggara Barat",
    "NTB",
    "Nusa Tenggara Timur",
    "NTT",
    "Kalimantan Barat",
    "Kalimantan Tengah",
    "Kalimantan Selatan",
    "Kalimantan Timur",
    "Kalimantan Utara",
    "Sulawesi Utara",
    "Sulawesi Tengah",
    "Sulawesi Selatan",
    "Sulawesi Tenggara",
    "Gorontalo",
    "Sulawesi Barat",
    "Maluku",
    "Maluku Utara",
    "Papua",
    "Papua Barat",
    "Papua Tengah",
    "Papua Pegunungan",
    "Papua Selatan",
    "Papua Barat Daya",
]


def normalize_for_compare(value):
    value = clean_import_text(value).lower()
    value = value.replace(".", "")
    value = value.replace(",", "")
    value = " ".join(value.split())
    value = value.replace("sumatra", "sumatera")
    value = value.replace("d i yogyakarta", "di yogyakarta")
    return value


def is_probably_province_line(line):
    line_norm = normalize_for_compare(line)

    if not line_norm:
        return False

    for province in INDONESIA_PROVINCES:
        province_norm = normalize_for_compare(province)

        if line_norm == province_norm:
            return True

    return False


def detect_province_from_text(value):
    value = clean_import_text(value)

    if not value:
        return ""

    lines = [
        line.strip()
        for line in value.replace("\r", "\n").split("\n")
        if line.strip()
    ]

    for line in lines:
        if is_probably_province_line(line):
            return line.strip()

    value_norm = normalize_for_compare(value)

    for province in INDONESIA_PROVINCES:
        province_norm = normalize_for_compare(province)

        if province_norm and province_norm in value_norm:
            return province

    return ""


def extract_name_from_gender_cell(raw_name, province):
    raw_name = clean_import_text(raw_name)
    province = clean_import_text(province)

    if not raw_name:
        return ""

    lines = [
        line.strip()
        for line in raw_name.replace("\r", "\n").split("\n")
        if line.strip()
    ]

    cleaned_lines = []

    province_norm = normalize_for_compare(province)

    for line in lines:
        line_norm = normalize_for_compare(line)

        if province_norm and line_norm == province_norm:
            continue

        if is_probably_province_line(line):
            continue

        cleaned_lines.append(line.strip())

    if cleaned_lines:
        return " ".join(cleaned_lines).strip()

    return ""



def clean_participant_name_from_import(raw_name, province):
    return extract_name_from_gender_cell(raw_name, province)


def normalize_column_name(value):
    value = clean_import_text(value).lower()
    keep = []

    for char in value:
        if char.isalnum():
            keep.append(char)

    return "".join(keep)


def find_import_column(df, candidates):
    normalized_columns = {}

    for col in df.columns:
        normalized_columns[normalize_column_name(col)] = col

    normalized_candidates = [
        normalize_column_name(candidate)
        for candidate in candidates
    ]

    for candidate in normalized_candidates:
        if candidate in normalized_columns:
            return normalized_columns[candidate]

    # fallback: contains match, untuk header yang punya spasi/newline/simbol tambahan
    for candidate in normalized_candidates:
        for normalized_col, original_col in normalized_columns.items():
            if candidate and candidate in normalized_col:
                return original_col

    return None


def create_participant_source(database_name, institution_name, uploaded_filename, description="", program_type=PROGRAM_CAPASKA):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO participant_sources (name, institution_name, program_type, description, uploaded_filename)
    VALUES (?, ?, ?, ?, ?)
    """, (database_name, institution_name, program_type, description, uploaded_filename))
    source_id = cur.lastrowid
    conn.commit()
    conn.close()
    return source_id


def get_next_capaska_mcu_id(cur, year):
    prefix = f"CAPASKA-{year}"
    cur.execute("""
    SELECT mcu_id FROM participants
    WHERE mcu_id LIKE ?
    ORDER BY mcu_id DESC
    LIMIT 1
    """, (f"{prefix}-%",))
    row = cur.fetchone()
    if not row or not row["mcu_id"]:
        next_number = 1
    else:
        try:
            last_number = int(str(row["mcu_id"]).split("-")[-1])
            next_number = last_number + 1
        except Exception:
            next_number = 1
    return f"{prefix}-{next_number:04d}"


def participant_exists_in_source(cur, source_id, name, gender, province):
    cur.execute("""
    SELECT id FROM participants
    WHERE source_id = ?
      AND UPPER(TRIM(name)) = UPPER(TRIM(?))
      AND UPPER(TRIM(gender)) = UPPER(TRIM(?))
      AND UPPER(TRIM(COALESCE(province, ''))) = UPPER(TRIM(?))
    LIMIT 1
    """, (source_id, name, gender, province))
    row = cur.fetchone()
    return row["id"] if row else None


def insert_or_update_imported_participant(cur, source_id, package_id, company_id, name, gender, province,
                                          service_date, exam_type, doctor_assigned, nurse_assigned,
                                          program_type=PROGRAM_CAPASKA):
    existing_id = participant_exists_in_source(cur, source_id, name, gender, province)
    if service_date:
        try:
            year = str(pd.to_datetime(service_date).year)
        except Exception:
            year = str(datetime.now().year)
    else:
        year = str(datetime.now().year)

    if existing_id:
        cur.execute("""
        UPDATE participants
        SET package_id = ?, company_id = ?, service_date = ?, exam_type = ?,
            doctor_assigned = ?, nurse_assigned = ?, mcu_date = COALESCE(NULLIF(mcu_date, ''), ?)
        WHERE id = ?
        """, (package_id, company_id, service_date, exam_type, doctor_assigned, nurse_assigned, service_date, existing_id))
        return "updated"

    mcu_id = get_next_capaska_mcu_id(cur, year)
    cur.execute("""
    INSERT INTO participants
    (mcu_id, external_id, name, nik, gender, birth_date, company_id, package_id, mcu_date,
     program_type, source_id, province, service_date, exam_type, doctor_assigned, nurse_assigned)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mcu_id, "", name, "", gender, "", company_id, package_id, service_date,
        program_type, source_id, province, service_date, exam_type, doctor_assigned, nurse_assigned
    ))
    return "created"


def choose_header_row(raw_df):
    known_headers = [
        "nama",
        "namapeserta",
        "namalengkap",
        "peserta",
        "nopendaftaran",
        "noregistrasi",
        "nomorregistrasi",
        "nopeserta",
        "idpeserta",
        "idinstansi",
        "nik",
        "jeniskelamin",
        "gender",
        "provinsi",
        "asalprovinsi",
        "asaldomisili",
        "tanggallayanan",
        "tanggalmcu",
        "jenispemeriksaan",
        "dokterbertugas",
        "perawatbertugas",
        "putra",
        "putri",
    ]

    best_index = 0
    best_score = -1

    scan_limit = min(len(raw_df), 20)

    for idx in range(scan_limit):
        row_values = [
            normalize_column_name(value)
            for value in raw_df.iloc[idx].tolist()
        ]

        score = 0

        for value in row_values:
            if not value:
                continue

            for header in known_headers:
                if header == value or header in value or value in header:
                    score += 1
                    break

        if score > best_score:
            best_score = score
            best_index = idx

    return best_index if best_score > 0 else 0


def first_available_column(df, candidates):
    return find_import_column(df, candidates)


def get_row_value(row, column_name):
    if column_name is None:
        return ""

    try:
        return row.get(column_name)
    except Exception:
        return ""


def detect_name_column(df):
    return first_available_column(
        df,
        [
            "Nama Peserta",
            "Nama Lengkap",
            "Nama Lengkap Peserta",
            "Nama",
            "Peserta",
            "Nama Calon",
            "Nama Calon Peserta",
            "Nama Siswa",
            "Nama Pendaftar",
            "Nama Lengkap Siswa",
            "Full Name",
            "Name",
        ]
    )


def import_instansi_excel(
    uploaded_file,
    database_name,
    institution_name,
    package_id,
    company_id,
    description=""
):
    # Import database peserta yang fleksibel.
    # Kolom Putra/Putri TIDAK wajib.
    # Kalau kolom Putra/Putri tidak ada, sistem pakai kolom nama umum seperti:
    # Nama Peserta / Nama Lengkap / Nama / Peserta.
    # Kalau kolom tertentu memang tidak ada, kolom itu diabaikan dan tidak dianggap error.

    xls = pd.ExcelFile(uploaded_file)
    parsed_sheets = []
    skipped_sheets = []

    for sheet_name in xls.sheet_names:
        raw_df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)

        if raw_df.empty:
            skipped_sheets.append({
                "sheet": sheet_name,
                "reason": "Sheet kosong"
            })
            continue

        header_row_index = choose_header_row(raw_df)

        headers = [
            clean_import_text(value) or f"Column_{i}"
            for i, value in enumerate(raw_df.iloc[header_row_index].tolist())
        ]

        df = raw_df.iloc[header_row_index + 1:].copy()
        df.columns = headers
        df = df.dropna(how="all")

        if df.empty:
            skipped_sheets.append({
                "sheet": sheet_name,
                "reason": "Tidak ada data setelah header"
            })
            continue

        service_date_col = first_available_column(df, [
            "Tanggal Layanan",
            "TanggalLayanan",
            "Tanggal MCU",
            "TanggalMCU",
            "Tanggal Pemeriksaan",
            "TanggalPemeriksaan",
            "Tanggal",
        ])

        exam_type_col = first_available_column(df, [
            "Jenis Pemeriksaan",
            "JenisPemeriksaan",
            "Pemeriksaan",
            "Jenis Layanan",
            "JenisLayanan",
        ])

        doctor_col = first_available_column(df, [
            "Dokter Bertugas",
            "DokterBertugas",
            "Dokter",
            "Nama Dokter",
        ])

        nurse_col = first_available_column(df, [
            "Perawat Bertugas",
            "PerawatBertugas",
            "Perawat",
            "Nama Perawat",
        ])

        gender_col = first_available_column(df, [
            "Jenis Kelamin",
            "JenisKelamin",
            "Gender",
            "JK",
            "L/P",
            "LP",
        ])

        province_col = first_available_column(df, [
            "Provinsi",
            "Asal Provinsi",
            "AsalProvinsi",
            "Asal Daerah",
            "AsalDaerah",
            "Domisili",
            "Provinsi Asal",
            "ProvinsiAsal",
        ])

        province_putra_col = first_available_column(df, [
            "Asal Provinsi Putra",
            "AsalProvinsiPutra",
            "Provinsi Putra",
            "ProvinsiPutra",
        ])

        province_putri_col = first_available_column(df, [
            "Asal Provinsi Putri",
            "AsalProvinsiPutri",
            "Provinsi Putri",
            "ProvinsiPutri",
        ])

        putra_col = first_available_column(df, [
            "Putra",
            "Nama Putra",
            "NamaPutra",
            "Peserta Putra",
            "PesertaPutra",
        ])

        putri_col = first_available_column(df, [
            "Putri",
            "Nama Putri",
            "NamaPutri",
            "Peserta Putri",
            "PesertaPutri",
        ])

        name_col = detect_name_column(df)

        external_id_col = first_available_column(df, [
            "ID Instansi",
            "IDInstansi",
            "Nomor ID Instansi",
            "No ID Instansi",
            "No Peserta",
            "NoPeserta",
            "Nomor Peserta",
            "NomorPeserta",
            "ID Peserta",
            "IDPeserta",
            "No Registrasi",
            "NoRegistrasi",
            "Nomor Registrasi",
            "NomorRegistrasi",
        ])

        nik_col = first_available_column(df, [
            "NIK",
            "No KTP",
            "NoKTP",
            "Nomor KTP",
            "NomorKTP",
        ])

        detected = {
            "sheet": sheet_name,
            "header_row_excel": header_row_index + 1,
            "headers": [str(col) for col in df.columns],
            "name_col": str(name_col) if name_col is not None else None,
            "external_id_col": str(external_id_col) if external_id_col is not None else None,
            "nik_col": str(nik_col) if nik_col is not None else None,
            "gender_col": str(gender_col) if gender_col is not None else None,
            "province_col": str(province_col) if province_col is not None else None,
            "province_putra_col": str(province_putra_col) if province_putra_col is not None else None,
            "province_putri_col": str(province_putri_col) if province_putri_col is not None else None,
            "putra_col": str(putra_col) if putra_col is not None else None,
            "putri_col": str(putri_col) if putri_col is not None else None,
            "service_date_col": str(service_date_col) if service_date_col is not None else None,
            "exam_type_col": str(exam_type_col) if exam_type_col is not None else None,
        }

        # Kalau tidak ada kolom nama umum dan tidak ada Putra/Putri,
        # sheet tidak error, tapi dilewati supaya tidak import data yang salah.
        if name_col is None and putra_col is None and putri_col is None:
            skipped_sheets.append({
                "sheet": sheet_name,
                "reason": "Tidak ada kolom nama peserta. Sistem melewati sheet ini tanpa error.",
                "detected": detected,
            })
            continue

        parsed_sheets.append({
            "sheet": sheet_name,
            "df": df,
            "columns": {
                "service_date_col": service_date_col,
                "exam_type_col": exam_type_col,
                "doctor_col": doctor_col,
                "nurse_col": nurse_col,
                "gender_col": gender_col,
                "province_col": province_col,
                "province_putra_col": province_putra_col,
                "province_putri_col": province_putri_col,
                "putra_col": putra_col,
                "putri_col": putri_col,
                "name_col": name_col,
                "external_id_col": external_id_col,
                "nik_col": nik_col,
            },
            "detected": detected,
        })

    if not parsed_sheets:
        raise ValueError(
            "File tidak bisa dijadikan database peserta karena tidak ada kolom nama peserta yang terbaca. "
            "Minimal file harus punya salah satu kolom berikut: Nama Peserta, Nama Lengkap, Nama, Peserta, Putra, atau Putri. "
            f"Detail kolom yang terbaca: {skipped_sheets}"
        )

    source_id = create_participant_source(
        database_name=database_name,
        institution_name=institution_name,
        uploaded_filename=getattr(uploaded_file, "name", ""),
        description=description,
        program_type=PROGRAM_CAPASKA,
    )

    stats = {
        "source_id": source_id,
        "database_name": database_name,
        "sheets_read": [item["sheet"] for item in parsed_sheets],
        "sheets_skipped": skipped_sheets,
        "detected_columns": [item["detected"] for item in parsed_sheets],
        "rows_read": 0,
        "participants_created": 0,
        "participants_updated": 0,
        "participants_skipped": 0,
        "barcodes_ready": 0,
        "notes": [
            "Kolom Putra/Putri tidak wajib.",
            "Jika Putra/Putri tidak ada, sistem memakai kolom Nama Peserta/Nama Lengkap/Nama/Peserta.",
            "Kolom yang tidak ada akan diabaikan.",
            "Namun minimal tetap wajib ada satu kolom nama peserta.",
            "Mode cloud: import dipercepat, QR dibuat saat cetak label.",
        ],
    }

    conn = get_connection()
    cur = conn.cursor()

    # Supabase performance patch:
    # Jangan SELECT mcu_id terakhir setiap baris. Ambil sekali per tahun, lalu increment lokal.
    mcu_year_counters = {}

    def next_mcu_id_fast(year_value):
        year_str = str(year_value or datetime.now().year)
        prefix = f"CAPASKA-{year_str}"

        if year_str not in mcu_year_counters:
            cur.execute("""
            SELECT mcu_id
            FROM participants
            WHERE mcu_id LIKE ?
            ORDER BY mcu_id DESC
            LIMIT 1
            """, (f"{prefix}-%",))

            row = cur.fetchone()

            if not row or not row["mcu_id"]:
                mcu_year_counters[year_str] = 1
            else:
                try:
                    mcu_year_counters[year_str] = int(str(row["mcu_id"]).split("-")[-1]) + 1
                except Exception:
                    mcu_year_counters[year_str] = 1

        next_number = mcu_year_counters[year_str]
        mcu_year_counters[year_str] += 1

        return f"{prefix}-{next_number:04d}"

    for sheet_item in parsed_sheets:
        df = sheet_item["df"]
        cols = sheet_item["columns"]

        stats["rows_read"] += len(df)

        service_date_col = cols["service_date_col"]
        exam_type_col = cols["exam_type_col"]
        doctor_col = cols["doctor_col"]
        nurse_col = cols["nurse_col"]
        gender_col = cols["gender_col"]
        province_col = cols["province_col"]
        province_putra_col = cols["province_putra_col"]
        province_putri_col = cols["province_putri_col"]
        putra_col = cols["putra_col"]
        putri_col = cols["putri_col"]
        name_col = cols["name_col"]
        external_id_col = cols["external_id_col"]
        nik_col = cols["nik_col"]

        for _, row in df.iterrows():
            service_date = normalize_import_date(get_row_value(row, service_date_col)) if service_date_col else ""
            exam_type = clean_import_text(get_row_value(row, exam_type_col)) if exam_type_col else ""
            doctor = clean_import_text(get_row_value(row, doctor_col)) if doctor_col else ""
            nurse = clean_import_text(get_row_value(row, nurse_col)) if nurse_col else ""
            external_id = clean_import_text(get_row_value(row, external_id_col)) if external_id_col else ""
            nik = clean_import_text(get_row_value(row, nik_col)) if nik_col else ""

            gender_raw = clean_import_text(get_row_value(row, gender_col)) if gender_col else ""
            gender_norm = normalize_for_compare(gender_raw)

            candidates = []

            # Prioritas 1: format normal satu baris satu peserta.
            if name_col is not None:
                raw_name = get_row_value(row, name_col)
                province = clean_import_text(get_row_value(row, province_col)) if province_col else ""
                detected_province = detect_province_from_text(raw_name)

                if not province:
                    province = detected_province

                name = clean_participant_name_from_import(raw_name, province or detected_province)

                if name:
                    if "putra" in gender_norm or gender_norm in ["laki laki", "lakilaki", "lk", "male"]:
                        gender = "Putra"
                    elif "putri" in gender_norm or gender_norm in ["perempuan", "pr", "female", "wanita"]:
                        gender = "Putri"
                    else:
                        gender = gender_raw

                    candidates.append({
                        "name": name,
                        "gender": gender,
                        "province": province,
                    })

            # Prioritas 2: format lama ada kolom Putra/Putri.
            # Tetap optional. Kalau kolomnya tidak ada, bagian ini otomatis dilewati.
            if not candidates:
                if "putra" in gender_norm and putra_col is not None:
                    raw_name = get_row_value(row, putra_col)
                    province = clean_import_text(get_row_value(row, province_putra_col)) if province_putra_col else ""
                    detected_province = detect_province_from_text(raw_name)

                    if not province:
                        province = detected_province

                    name = clean_participant_name_from_import(raw_name, province or detected_province)

                    if name:
                        candidates.append({
                            "name": name,
                            "gender": "Putra",
                            "province": province,
                        })

                elif "putri" in gender_norm and putri_col is not None:
                    raw_name = get_row_value(row, putri_col)
                    province = clean_import_text(get_row_value(row, province_putri_col)) if province_putri_col else ""
                    detected_province = detect_province_from_text(raw_name)

                    if not province:
                        province = detected_province

                    name = clean_participant_name_from_import(raw_name, province or detected_province)

                    if name:
                        candidates.append({
                            "name": name,
                            "gender": "Putri",
                            "province": province,
                        })

                else:
                    # Jika gender kosong tapi ada kolom Putra/Putri, import semua nama yang terisi.
                    if putra_col is not None:
                        raw_name = get_row_value(row, putra_col)
                        province = clean_import_text(get_row_value(row, province_putra_col)) if province_putra_col else ""
                        detected_province = detect_province_from_text(raw_name)

                        if not province:
                            province = detected_province

                        name = clean_participant_name_from_import(raw_name, province or detected_province)

                        if name:
                            candidates.append({
                                "name": name,
                                "gender": "Putra",
                                "province": province,
                            })

                    if putri_col is not None:
                        raw_name = get_row_value(row, putri_col)
                        province = clean_import_text(get_row_value(row, province_putri_col)) if province_putri_col else ""
                        detected_province = detect_province_from_text(raw_name)

                        if not province:
                            province = detected_province

                        name = clean_participant_name_from_import(raw_name, province or detected_province)

                        if name:
                            candidates.append({
                                "name": name,
                                "gender": "Putri",
                                "province": province,
                            })

            if not candidates:
                stats["participants_skipped"] += 1
                continue

            for candidate in candidates:
                # Supabase/Streamlit Cloud fast path:
                # Import database selalu membuat source_id baru, jadi tidak perlu SELECT cek existing per baris.
                # External ID dan NIK langsung masuk saat INSERT, tidak UPDATE terpisah.
                if using_postgres():
                    if service_date:
                        try:
                            year = str(pd.to_datetime(service_date).year)
                        except Exception:
                            year = str(datetime.now().year)
                    else:
                        year = str(datetime.now().year)

                    mcu_id = next_mcu_id_fast(year)

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
                        program_type,
                        source_id,
                        province,
                        service_date,
                        exam_type,
                        doctor_assigned,
                        nurse_assigned,
                        barcode_value
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        mcu_id,
                        external_id,
                        candidate["name"],
                        nik,
                        candidate["gender"],
                        "",
                        company_id,
                        package_id,
                        service_date,
                        PROGRAM_CAPASKA,
                        source_id,
                        candidate["province"],
                        service_date,
                        exam_type,
                        doctor,
                        nurse,
                        mcu_id
                    ))

                    stats["participants_created"] += 1
                else:
                    result = insert_or_update_imported_participant(
                        cur=cur,
                        source_id=source_id,
                        package_id=package_id,
                        company_id=company_id,
                        name=candidate["name"],
                        gender=candidate["gender"],
                        province=candidate["province"],
                        service_date=service_date,
                        exam_type=exam_type,
                        doctor_assigned=doctor,
                        nurse_assigned=nurse,
                    )

                    # Update optional external_id dan nik kalau ada.
                    if external_id or nik:
                        cur.execute("""
                        UPDATE participants
                        SET
                            external_id = COALESCE(NULLIF(?, ''), external_id),
                            nik = COALESCE(NULLIF(?, ''), nik)
                        WHERE source_id = ?
                          AND UPPER(TRIM(name)) = UPPER(TRIM(?))
                          AND UPPER(TRIM(COALESCE(gender, ''))) = UPPER(TRIM(COALESCE(?, '')))
                        """, (
                            external_id,
                            nik,
                            source_id,
                            candidate["name"],
                            candidate["gender"],
                        ))

                    if result == "created":
                        stats["participants_created"] += 1
                    else:
                        stats["participants_updated"] += 1

    conn.commit()
    conn.close()

    total_imported = stats["participants_created"] + stats["participants_updated"]

    if total_imported == 0:
        delete_participant_source_database(
            source_id=source_id,
            delete_barcode_files=True
        )
        raise ValueError(
            "Database tidak dibuat karena tidak ada peserta yang berhasil diimport. "
            "Pastikan file Excel memiliki kolom nama peserta dan baris data peserta. "
            f"Detail kolom yang terbaca: {stats.get('detected_columns')}"
        )

    # Supabase/Streamlit Cloud performance:
    # Jangan generate semua QR/barcode saat import karena lambat untuk banyak peserta.
    # Barcode akan dibuat otomatis saat peserta dibuka atau saat admin cetak label.
    stats["barcodes_ready"] = 0
    stats["barcode_generation_mode"] = "on_demand"

    return stats




# =========================
# BARCODE / QR CODE
# =========================

def safe_filename(value):
    value = display_value(value)
    allowed = []

    for char in value:
        if char.isalnum() or char in ["-", "_"]:
            allowed.append(char)
        else:
            allowed.append("_")

    filename = "".join(allowed).strip("_")

    return filename or "barcode"


def make_barcode_value(participant):
    mcu_id = display_value(participant.get("mcu_id"))

    if mcu_id != "-":
        return mcu_id

    participant_id = participant.get("id") or participant.get("participant_id") or "000000"

    return f"PATIENT-{int(participant_id):06d}" if str(participant_id).isdigit() else f"PATIENT-{participant_id}"


def generate_qr_image_file(barcode_value):
    if not QR_AVAILABLE:
        return None

    BARCODE_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_filename(barcode_value)}.png"
    output_path = BARCODE_DIR / filename

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(barcode_value)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    image.save(output_path)

    return str(output_path).replace("\\", "/")


def ensure_barcode_for_participant(participant_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        id,
        mcu_id,
        barcode_value,
        barcode_image_path
    FROM participants
    WHERE id = ?
    """, (participant_id,))

    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    participant = dict(row)

    barcode_value = display_value(participant.get("barcode_value"))

    if barcode_value == "-":
        barcode_value = make_barcode_value(participant)

    barcode_image_path = participant.get("barcode_image_path")
    barcode_path = Path(barcode_image_path) if barcode_image_path else None

    if not barcode_image_path or not barcode_path.exists():
        generated_path = generate_qr_image_file(barcode_value)
        if generated_path:
            barcode_image_path = generated_path

    barcode_created_at_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
    UPDATE participants
    SET
        barcode_value = ?,
        barcode_image_path = COALESCE(NULLIF(?, ''), barcode_image_path),
        barcode_created_at = COALESCE(NULLIF(barcode_created_at, ''), ?)
    WHERE id = ?
    """, (
        barcode_value,
        barcode_image_path or "",
        barcode_created_at_value,
        participant_id
    ))

    conn.commit()
    conn.close()

    return {
        "barcode_value": barcode_value,
        "barcode_image_path": barcode_image_path,
    }


def ensure_barcodes_for_source(source_id):
    if not source_id:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id
    FROM participants
    WHERE source_id = ?
    ORDER BY id ASC
    """, (source_id,))

    ids = [row["id"] for row in cur.fetchall()]
    conn.close()

    count = 0

    for participant_id in ids:
        barcode = ensure_barcode_for_participant(participant_id)

        barcode_image_path = barcode.get("barcode_image_path") if barcode else None

        if barcode_image_path and Path(barcode_image_path).exists():
            count += 1

    return count


def ensure_barcodes_by_filter(program_type=None, source_id=None):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = ["1 = 1"]
    params = []

    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_clauses.append("program_type = ?")
        params.append(program_type)

    if source_id:
        where_clauses.append("source_id = ?")
        params.append(source_id)

    where_sql = " AND ".join(where_clauses)

    cur.execute(f"""
    SELECT id
    FROM participants
    WHERE {where_sql}
    ORDER BY id ASC
    """, params)

    ids = [row["id"] for row in cur.fetchall()]
    conn.close()

    count = 0

    for participant_id in ids:
        barcode = ensure_barcode_for_participant(participant_id)

        barcode_image_path = barcode.get("barcode_image_path") if barcode else None

        if barcode_image_path and Path(barcode_image_path).exists():
            count += 1

    return count


def render_patient_barcode(participant):
    barcode = ensure_barcode_for_participant(participant["id"])

    if not barcode:
        return

    barcode_value = barcode.get("barcode_value")
    barcode_image_path = barcode.get("barcode_image_path")

    with st.container(border=True):
        st.markdown("### Barcode Pasien")
        st.caption("Scan barcode ini untuk memanggil data peserta di semua post pemeriksaan. File QR tersimpan di folder uploads/barcodes.")

        col_qr, col_info = st.columns([0.28, 0.72])

        with col_qr:
            if barcode_image_path and Path(barcode_image_path).exists():
                st.image(
                    barcode_image_path,
                    caption=barcode_value,
                    width=220
                )

                with open(barcode_image_path, "rb") as file:
                    st.download_button(
                        "Download QR",
                        data=file,
                        file_name=f"{safe_filename(barcode_value)}.png",
                        mime="image/png",
                        use_container_width=True
                    )
            elif not QR_AVAILABLE:
                st.warning("QR belum bisa dibuat. Install dulu: pip install qrcode[pil] pillow")
            else:
                st.warning("QR image belum tersedia.")

        with col_info:
            st.write(f"**Barcode Value:** `{barcode_value}`")
            st.write(f"**ID Internal:** {display_value(participant.get('mcu_id'))}")
            st.write(f"**Nama:** {display_value(participant.get('name'))}")
            st.info(
                "Barcode scanner biasanya mengetik otomatis isi QR ke kolom pencarian. "
                "Arahkan kursor ke field search, scan QR, lalu tekan Enter/Cari."
            )



# =========================
# PARTICIPANT
# =========================

def generate_mcu_id(program_type):
    today_code = date.today().strftime("%Y%m%d")
    prefix = "CAPASKA" if program_type == PROGRAM_CAPASKA else "MCU"
    prefix = f"{prefix}-{today_code}"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM participants WHERE mcu_id LIKE ?", (f"{prefix}-%",))
    total = cur.fetchone()["total"]
    conn.close()
    return f"{prefix}-{total + 1:04d}"


def create_participant(mcu_id, external_id, name, nik, gender, birth_date, company_id, package_id, mcu_date, program_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO participants
    (mcu_id, external_id, name, nik, gender, birth_date, company_id, package_id, mcu_date, program_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (mcu_id, external_id, name, nik, gender, birth_date, company_id, package_id, mcu_date, program_type))

    participant_id = cur.lastrowid

    conn.commit()
    conn.close()

    ensure_barcode_for_participant(participant_id)


def update_participant_mcu_date(participant_id, mcu_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE participants SET mcu_date = ? WHERE id = ?", (str(mcu_date), participant_id))
    conn.commit()
    conn.close()


def get_participant_by_id(participant_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT participants.*, companies.name AS company_name, packages.name AS package_name,
           participant_sources.name AS source_name
    FROM participants
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN participant_sources ON participants.source_id = participant_sources.id
    WHERE participants.id = ?
    """, (participant_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def search_participants(keyword, program_type=None, source_id=None, limit=50):
    conn = get_connection()
    cur = conn.cursor()
    keyword_like = f"%{keyword.strip()}%"
    where_program = ""
    where_source = ""
    params = [keyword_like, keyword_like, keyword_like, keyword_like, keyword_like, keyword_like]
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_program = "AND participants.program_type = ?"
        params.append(program_type)
    if source_id:
        where_source = "AND participants.source_id = ?"
        params.append(source_id)
    params.append(limit)
    cur.execute(f"""
    SELECT participants.*, companies.name AS company_name, packages.name AS package_name,
           participant_sources.name AS source_name
    FROM participants
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN participant_sources ON participants.source_id = participant_sources.id
    WHERE (
        participants.name LIKE ? OR participants.external_id LIKE ? OR participants.nik LIKE ?
        OR participants.mcu_id LIKE ? OR participants.province LIKE ? OR participants.barcode_value LIKE ?
    )
    {where_program}
    {where_source}
    ORDER BY participants.name ASC
    LIMIT ?
    """, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# =========================
# EXAMINATION / SUBMISSION
# =========================

def get_parameters_for_post(package_id, post_id, program_type=None):
    conn = get_connection()
    cur = conn.cursor()
    where_program = ""
    params = [package_id, post_id]
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_program = "AND parameters.program_type = ?"
        params.append(program_type)
    cur.execute(f"""
    SELECT parameters.*
    FROM parameters
    JOIN package_parameters ON package_parameters.parameter_id = parameters.id
    WHERE package_parameters.package_id = ?
      AND parameters.post_id = ?
      AND parameters.is_active = 1
      {where_program}
    ORDER BY parameters.sort_order ASC, parameters.id ASC
    """, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_existing_results(participant_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT parameter_id, value FROM examination_results WHERE participant_id = ?", (participant_id,))
    rows = cur.fetchall()
    conn.close()
    return {row["parameter_id"]: row["value"] for row in rows}


def save_result(participant_id, parameter_id, value, user_id, post_id):
    conn = get_connection()
    cur = conn.cursor()
    value = "" if value is None else str(value).strip()
    cur.execute("""
    SELECT value FROM examination_results
    WHERE participant_id = ? AND parameter_id = ?
    """, (participant_id, parameter_id))
    existing = cur.fetchone()
    if existing:
        old_value = existing["value"]
        if str(old_value) != str(value):
            cur.execute("""
            UPDATE examination_results
            SET value = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE participant_id = ? AND parameter_id = ?
            """, (value, user_id, participant_id, parameter_id))
            cur.execute("""
            INSERT INTO audit_logs (user_id, action, participant_id, parameter_id, old_value, new_value)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, "UPDATE_RESULT", participant_id, parameter_id, old_value, value))
    else:
        cur.execute("""
        INSERT INTO examination_results (participant_id, parameter_id, value, input_by, input_post_id)
        VALUES (?, ?, ?, ?, ?)
        """, (participant_id, parameter_id, value, user_id, post_id))
        cur.execute("""
        INSERT INTO audit_logs (user_id, action, participant_id, parameter_id, old_value, new_value)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, "CREATE_RESULT", participant_id, parameter_id, None, value))
    conn.commit()
    conn.close()


def get_audit_logs(program_type=None, limit=300):
    conn = get_connection()
    cur = conn.cursor()
    where_program = ""
    params = []
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_program = "WHERE participants.program_type = ?"
        params.append(program_type)
    params.append(limit)
    cur.execute(f"""
    SELECT audit_logs.timestamp, audit_logs.action, users.name AS user_name,
           participants.mcu_id, participants.external_id, participants.name AS participant_name,
           participants.program_type, parameters.name AS parameter_name,
           audit_logs.old_value, audit_logs.new_value
    FROM audit_logs
    LEFT JOIN users ON audit_logs.user_id = users.id
    LEFT JOIN participants ON audit_logs.participant_id = participants.id
    LEFT JOIN parameters ON audit_logs.parameter_id = parameters.id
    {where_program}
    ORDER BY audit_logs.timestamp DESC
    LIMIT ?
    """, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_my_submission_participants(user_id, program_type=None, keyword="", limit=10):
    conn = get_connection()
    cur = conn.cursor()
    keyword_like = f"%{keyword.strip()}%"
    where_program = ""
    params = [user_id, user_id, keyword_like, keyword_like, keyword_like]
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_program = "AND participants.program_type = ?"
        params.append(program_type)
    params.append(limit)
    cur.execute(f"""
    SELECT DISTINCT participants.id AS participant_id, participants.name AS participant_name,
           participants.external_id, participants.nik, participants.mcu_id,
           packages.name AS package_name, posts.name AS post_name
    FROM examination_results
    LEFT JOIN participants ON examination_results.participant_id = participants.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN posts ON examination_results.input_post_id = posts.id
    WHERE (examination_results.input_by = ? OR examination_results.updated_by = ?)
      AND (participants.name LIKE ? OR participants.external_id LIKE ? OR participants.mcu_id LIKE ?)
      {where_program}
    ORDER BY participants.name ASC
    LIMIT ?
    """, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_result_history(participant_id, parameter_id, limit=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT audit_logs.timestamp, audit_logs.action, users.name AS user_name,
           participants.name AS participant_name, parameters.name AS parameter_name,
           audit_logs.old_value, audit_logs.new_value
    FROM audit_logs
    LEFT JOIN users ON audit_logs.user_id = users.id
    LEFT JOIN participants ON audit_logs.participant_id = participants.id
    LEFT JOIN parameters ON audit_logs.parameter_id = parameters.id
    WHERE audit_logs.participant_id = ? AND audit_logs.parameter_id = ?
    ORDER BY audit_logs.timestamp DESC
    LIMIT ?
    """, (participant_id, parameter_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_my_submission_detail_rows(user_id, program_type=None, keyword="", limit=1000):
    conn = get_connection()
    cur = conn.cursor()
    where_program = ""
    where_keyword = ""
    params = [user_id, user_id, user_id]
    if keyword.strip():
        keyword_like = f"%{keyword.strip()}%"
        where_keyword = """
        AND (
            participants.name LIKE ? OR participants.external_id LIKE ? OR participants.nik LIKE ?
            OR participants.mcu_id LIKE ? OR parameters.name LIKE ? OR examination_results.value LIKE ?
        )
        """
        params.extend([keyword_like, keyword_like, keyword_like, keyword_like, keyword_like, keyword_like])
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_program = "AND participants.program_type = ?"
        params.append(program_type)
    params.append(limit)
    cur.execute(f"""
    SELECT examination_results.participant_id, examination_results.parameter_id,
           COALESCE(examination_results.updated_at, examination_results.created_at) AS waktu,
           CASE WHEN examination_results.updated_by = ? THEN 'UPDATE' ELSE 'CREATE' END AS status_input,
           participants.name AS participant_name, participants.external_id, participants.province,
           participants.nik, participants.mcu_id, participants.program_type,
           companies.name AS company_name, packages.name AS package_name, posts.name AS post_name,
           parameters.name AS parameter_name, parameters.category AS parameter_category,
           examination_results.value, input_user.name AS input_by, update_user.name AS updated_by
    FROM examination_results
    LEFT JOIN participants ON examination_results.participant_id = participants.id
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN parameters ON examination_results.parameter_id = parameters.id
    LEFT JOIN posts ON examination_results.input_post_id = posts.id
    LEFT JOIN users AS input_user ON examination_results.input_by = input_user.id
    LEFT JOIN users AS update_user ON examination_results.updated_by = update_user.id
    WHERE (examination_results.input_by = ? OR examination_results.updated_by = ?)
    {where_keyword}
    {where_program}
    ORDER BY waktu DESC
    LIMIT ?
    """, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stage_progress(participant_id, package_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT posts.id AS post_id, posts.name AS post_name,
        COUNT(DISTINCT CASE WHEN LOWER(TRIM(parameters.name)) LIKE 'score total%'
            OR LOWER(TRIM(parameters.name)) LIKE 'total score%'
            OR LOWER(TRIM(parameters.name)) LIKE '%score total%' THEN parameters.id END) AS total_score_parameters,
        COUNT(DISTINCT CASE WHEN (LOWER(TRIM(parameters.name)) LIKE 'score total%'
            OR LOWER(TRIM(parameters.name)) LIKE 'total score%'
            OR LOWER(TRIM(parameters.name)) LIKE '%score total%')
            AND examination_results.value IS NOT NULL AND TRIM(examination_results.value) != ''
            THEN examination_results.parameter_id END) AS filled_score_parameters,
        COUNT(DISTINCT CASE WHEN NOT (LOWER(TRIM(parameters.name)) LIKE 'value %'
            OR LOWER(TRIM(parameters.name)) LIKE 'score %'
            OR LOWER(TRIM(parameters.name)) LIKE 'total score%'
            OR LOWER(TRIM(parameters.name)) LIKE '%score total%') THEN parameters.id END) AS total_input_parameters,
        COUNT(DISTINCT CASE WHEN NOT (LOWER(TRIM(parameters.name)) LIKE 'value %'
            OR LOWER(TRIM(parameters.name)) LIKE 'score %'
            OR LOWER(TRIM(parameters.name)) LIKE 'total score%'
            OR LOWER(TRIM(parameters.name)) LIKE '%score total%')
            AND examination_results.value IS NOT NULL AND TRIM(examination_results.value) != ''
            THEN examination_results.parameter_id END) AS filled_input_parameters
    FROM package_parameters
    JOIN parameters ON parameters.id = package_parameters.parameter_id
    JOIN posts ON posts.id = parameters.post_id
    LEFT JOIN examination_results ON examination_results.participant_id = ?
        AND examination_results.parameter_id = parameters.id
    WHERE package_parameters.package_id = ?
      AND parameters.is_active = 1
      AND posts.name != 'Admin'
    GROUP BY posts.id, posts.name
    ORDER BY posts.id ASC
    """, (participant_id, package_id))
    rows = cur.fetchall()
    conn.close()
    stages = []
    for row in rows:
        item = dict(row)
        post_name_lower = str(item.get("post_name") or "").lower()
        total_score = item.get("total_score_parameters") or 0
        filled_score = item.get("filled_score_parameters") or 0
        total_input = item.get("total_input_parameters") or 0
        filled_input = item.get("filled_input_parameters") or 0
        if "registrasi" in post_name_lower:
            is_done = True
            progress_text = "Done"
        elif total_score > 0:
            is_done = filled_score > 0
            progress_text = "Done" if is_done else "Belum"
        else:
            is_done = total_input > 0 and filled_input >= total_input
            progress_text = f"{filled_input}/{total_input}"
        item["is_done"] = is_done
        item["status_text"] = "Done" if is_done else "Belum"
        item["progress_text"] = progress_text

        stage_name_key = str(item.get("post_name") or "").strip().lower()
        stage_order_map = {
            "registrasi capaska": 10,
            "kesehatan mata": 20,
            "penyakit dalam": 30,
            "kesehatan gigi & mulut + dental panoramik": 40,
            "kesehatan tht": 50,
            "kesehatan jantung dan pembuluh darah": 60,
            "ortopedi": 70,
            "radiologi": 80,
            "review dokter capaska": 900,
        }
        item["stage_order"] = stage_order_map.get(stage_name_key, 500)

        stages.append(item)

    stages = sorted(stages, key=lambda row: (row.get("stage_order", 500), row.get("post_id", 0)))
    return stages


def is_computed_capaska_parameter(parameter_name):
    name = str(parameter_name or "").strip().lower()
    return (
        name.startswith("value ")
        or name.startswith("score ")
        or name.startswith("total score")
        or "score total" in name
    )


def is_score_column(column_name):
    name = str(column_name or "").strip().lower()
    return (
        name in ["final score", "final score total"]
        or name.startswith("score ")
        or name.startswith("total score")
        or "score total" in name
    )


def to_score_number(value):
    try:
        value = display_value(value)
        if value == "-":
            return 0
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return 0


def reorder_summary_columns_with_final_score(pivot_df):
    if pivot_df.empty:
        return pivot_df
    base_columns = [
        "Nama Peserta", "ID Instansi", "NIK", "ID Internal", "Provinsi",
        "Program", "Instansi/Perusahaan", "Paket", "Post"
    ]
    existing_base_columns = [col for col in base_columns if col in pivot_df.columns]
    score_columns = [col for col in pivot_df.columns if col not in existing_base_columns and is_score_column(col)]
    normal_parameter_columns = [col for col in pivot_df.columns if col not in existing_base_columns and col not in score_columns]
    score_columns = sorted(score_columns, key=lambda x: str(x).lower())
    if score_columns:
        pivot_df["FINAL SCORE"] = pivot_df[score_columns].apply(lambda row: sum(to_score_number(value) for value in row), axis=1)
    else:
        pivot_df["FINAL SCORE"] = 0
    return pivot_df[existing_base_columns + normal_parameter_columns + score_columns + ["FINAL SCORE"]]


def build_history_picker_df(display_df):
    rows = []
    for _, row in display_df.iterrows():
        participant_id = row.get("Participant ID")
        parameter_id = row.get("Parameter ID")
        try:
            history = get_result_history(int(participant_id), int(parameter_id), limit=1)
        except Exception:
            history = []
        if history:
            latest = history[0]
            before_edit = display_value(latest.get("old_value"))
            after_edit = display_value(latest.get("new_value"))
            last_action = display_value(latest.get("action"))
            last_edited_by = display_value(latest.get("user_name"))
            last_edit_at = display_value(latest.get("timestamp"))
        else:
            before_edit = "-"
            after_edit = display_value(row.get("Nilai"))
            last_action = "-"
            last_edited_by = "-"
            last_edit_at = "-"
        rows.append({
            "Participant ID": participant_id,
            "Parameter ID": parameter_id,
            "Nama Peserta": display_value(row.get("Nama Peserta")),
            "ID Internal": display_value(row.get("ID Internal")),
            "Post": display_value(row.get("Post")),
            "Parameter": display_value(row.get("Parameter")),
            "Nilai Saat Ini": display_value(row.get("Nilai")),
            "Before Edit": before_edit,
            "After Edit": after_edit,
            "Last Action": last_action,
            "Last Edited By": last_edited_by,
            "Last Edit At": last_edit_at,
        })
    return pd.DataFrame(rows)


def render_stage_progress_box(participant):
    if not participant:
        return

    participant_id = participant.get("id")
    package_id = participant.get("package_id")

    if not participant_id or not package_id:
        return

    stages = get_stage_progress(participant_id, package_id)

    if not stages:
        return

    total_stage = len(stages)
    done_stage = len([stage for stage in stages if stage.get("is_done")])
    progress_percent = round((done_stage / total_stage) * 100, 1) if total_stage else 0

    with st.container(border=True):
        st.markdown("### Progress Stage")
        st.caption(
            f"{display_value(participant.get('name'))} | "
            f"{display_value(participant.get('mcu_id'))}"
        )

        st.progress(progress_percent / 100)
        st.caption(f"{done_stage}/{total_stage} stage selesai ({progress_percent}%)")

        for stage in stages:
            is_done = bool(stage.get("is_done"))
            post_name = display_value(stage.get("post_name"))
            badge_class = "stage-status-done" if is_done else "stage-status-pending"
            badge_text = "Done" if is_done else "Belum"

            col_check, col_name, col_status = st.columns([0.12, 0.60, 0.28])

            with col_check:
                st.checkbox(
                    " ",
                    value=is_done,
                    disabled=True,
                    key=f"stage_check_{participant_id}_{stage.get('post_id')}"
                )

            with col_name:
                if is_done:
                    st.markdown(f"**{post_name}**")
                else:
                    st.markdown(post_name)

            with col_status:
                st.markdown(
                    f'<div class="{badge_class}">{badge_text}</div>',
                    unsafe_allow_html=True
                )


def get_participant_progress(program_type=None, source_id=None):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = ["1 = 1"]
    params = []

    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_clauses.append("participants.program_type = ?")
        params.append(program_type)

    if source_id:
        where_clauses.append("participants.source_id = ?")
        params.append(source_id)

    where_sql = " AND ".join(where_clauses)

    cur.execute(f"""
    SELECT
        participants.id AS participant_id,
        participants.package_id,
        participants.source_id,
        participants.mcu_id,
        participants.external_id,
        participants.province,
        participants.name AS participant_name,
        participants.program_type,
        companies.name AS company_name,
        packages.name AS package_name,
        participant_sources.name AS source_name,
        participants.mcu_date,
        COUNT(DISTINCT package_parameters.parameter_id) AS total_parameters,
        COUNT(DISTINCT examination_results.parameter_id) AS filled_parameters
    FROM participants
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN participant_sources ON participants.source_id = participant_sources.id
    LEFT JOIN package_parameters ON package_parameters.package_id = participants.package_id
    LEFT JOIN examination_results ON examination_results.participant_id = participants.id
       AND examination_results.parameter_id = package_parameters.parameter_id
       AND examination_results.value IS NOT NULL
       AND TRIM(examination_results.value) != ''
    WHERE {where_sql}
    GROUP BY
        participants.id,
        participants.package_id,
        participants.source_id,
        participants.mcu_id,
        participants.external_id,
        participants.province,
        participants.name,
        participants.program_type,
        companies.name,
        packages.name,
        participant_sources.name,
        participants.mcu_date
    ORDER BY participants.id DESC
    """, params)

    rows = cur.fetchall()
    conn.close()

    data = []

    for row in rows:
        item = dict(row)

        total = item["total_parameters"] or 0
        filled = item["filled_parameters"] or 0
        parameter_progress_percent = round((filled / total) * 100, 1) if total else 0

        stages = []
        try:
            if item.get("participant_id") and item.get("package_id"):
                stages = get_stage_progress(
                    item["participant_id"],
                    item["package_id"]
                )
        except Exception:
            stages = []

        total_stage = len(stages)
        done_stage = len([stage for stage in stages if stage.get("is_done")])

        if total_stage:
            progress_percent = round((done_stage / total_stage) * 100, 1)
            is_complete = done_stage >= total_stage
        else:
            progress_percent = parameter_progress_percent
            is_complete = total > 0 and filled >= total

        item["filled_parameters"] = filled
        item["total_parameters"] = total
        item["done_stage"] = done_stage
        item["total_stage"] = total_stage
        item["progress_percent"] = progress_percent
        item["status_pemeriksaan"] = "Selesai" if is_complete else "Belum Selesai"

        data.append(item)

    return data


def count_export_participants(company_id=None, package_id=None, program_type=None, source_id=None, mcu_date_from=None, mcu_date_to=None):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = ["1 = 1"]
    params = []

    if company_id:
        where_clauses.append("participants.company_id = ?")
        params.append(company_id)

    if package_id:
        where_clauses.append("participants.package_id = ?")
        params.append(package_id)

    if source_id:
        where_clauses.append("participants.source_id = ?")
        params.append(source_id)

    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_clauses.append("participants.program_type = ?")
        params.append(program_type)

    if mcu_date_from:
        where_clauses.append("participants.mcu_date >= ?")
        params.append(mcu_date_from)

    if mcu_date_to:
        where_clauses.append("participants.mcu_date <= ?")
        params.append(mcu_date_to)

    where_sql = " AND ".join(where_clauses)

    cur.execute(f"""
    SELECT COUNT(DISTINCT participants.id) AS total
    FROM participants
    WHERE {where_sql}
    """, params)

    row = cur.fetchone()
    conn.close()

    return row["total"] if row else 0



# =========================
# PRINT LABEL BARCODE PDF
# =========================

def fit_pdf_text(c, text, max_width, font_name="Helvetica", font_size=7):
    text = display_value(text)

    c.setFont(font_name, font_size)

    if c.stringWidth(text, font_name, font_size) <= max_width:
        return text

    ellipsis = "..."

    while text and c.stringWidth(text + ellipsis, font_name, font_size) > max_width:
        text = text[:-1]

    return (text + ellipsis) if text else ellipsis


def get_label_print_participants(source_id=None, program_type=None, keyword="", limit=2000):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = ["1 = 1"]
    params = []

    if source_id:
        where_clauses.append("participants.source_id = ?")
        params.append(source_id)

    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_clauses.append("participants.program_type = ?")
        params.append(program_type)

    keyword = keyword.strip()

    if keyword:
        keyword_like = f"%{keyword}%"
        where_clauses.append("""
        (
            participants.name LIKE ?
            OR participants.mcu_id LIKE ?
            OR participants.external_id LIKE ?
            OR participants.nik LIKE ?
            OR participants.province LIKE ?
            OR participants.barcode_value LIKE ?
        )
        """)
        params.extend([
            keyword_like,
            keyword_like,
            keyword_like,
            keyword_like,
            keyword_like,
            keyword_like,
        ])

    params.append(limit)

    where_sql = " AND ".join(where_clauses)

    cur.execute(f"""
    SELECT
        participants.id,
        participants.mcu_id,
        participants.external_id,
        participants.name,
        participants.nik,
        participants.gender,
        participants.province,
        participants.mcu_date,
        participants.service_date,
        participants.barcode_value,
        participants.barcode_image_path,
        participants.program_type,
        companies.name AS company_name,
        packages.name AS package_name,
        participant_sources.name AS source_name,
        participant_sources.institution_name AS institution_name
    FROM participants
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN participant_sources ON participants.source_id = participant_sources.id
    WHERE {where_sql}
    ORDER BY participants.name ASC, participants.id ASC
    LIMIT ?
    """, params)

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def draw_one_barcode_label(
    c,
    participant,
    x,
    y,
    label_width,
    label_height,
    show_institution=True,
    show_date=False,
    show_border=True
):
    if show_border:
        c.setLineWidth(0.25)
        c.setStrokeColorRGB(0.78, 0.82, 0.88)
        c.roundRect(x + 0.7 * mm, y + 0.7 * mm, label_width - 1.4 * mm, label_height - 1.4 * mm, 2.2 * mm)

    barcode = ensure_barcode_for_participant(participant["id"])
    barcode_value = barcode.get("barcode_value") if barcode else display_value(participant.get("barcode_value"))
    barcode_image_path = barcode.get("barcode_image_path") if barcode else participant.get("barcode_image_path")

    padding = 2.3 * mm
    qr_size = 17.5 * mm
    qr_x = x + label_width - padding - qr_size
    qr_y = y + (label_height - qr_size) / 2

    text_x = x + padding
    text_top = y + label_height - 5.0 * mm
    text_max_width = label_width - qr_size - (padding * 3.2)

    # QR image kanan
    if barcode_image_path and Path(barcode_image_path).exists() and ImageReader:
        try:
            c.drawImage(
                ImageReader(barcode_image_path),
                qr_x,
                qr_y,
                qr_size,
                qr_size,
                preserveAspectRatio=True,
                mask="auto"
            )
        except Exception:
            pass

    # Nama peserta
    c.setFillColorRGB(0.05, 0.09, 0.16)
    name_text = fit_pdf_text(
        c,
        display_value(participant.get("name")).upper(),
        text_max_width,
        "Helvetica-Bold",
        7.2
    )
    c.drawString(text_x, text_top, name_text)

    # ID internal
    line_y = text_top - 4.6 * mm
    id_text = f"ID: {display_value(participant.get('mcu_id'))}"
    id_text = fit_pdf_text(c, id_text, text_max_width, "Helvetica", 6.4)
    c.setFont("Helvetica", 6.4)
    c.drawString(text_x, line_y, id_text)

    # Database/instansi
    line_y -= 3.9 * mm

    if show_institution:
        institution = display_value(participant.get("institution_name") or participant.get("company_name"))
        inst_text = fit_pdf_text(c, institution, text_max_width, "Helvetica", 5.8)
        c.setFont("Helvetica", 5.8)
        c.setFillColorRGB(0.25, 0.32, 0.43)
        c.drawString(text_x, line_y, inst_text)

    if show_date:
        line_y -= 3.7 * mm
        mcu_date = display_value(participant.get("mcu_date") or participant.get("service_date"))
        date_text = f"Tgl: {mcu_date}"
        date_text = fit_pdf_text(c, date_text, text_max_width, "Helvetica", 5.6)
        c.setFont("Helvetica", 5.6)
        c.setFillColorRGB(0.35, 0.40, 0.50)
        c.drawString(text_x, line_y, date_text)

    # Barcode value kecil di bawah QR supaya tetap bisa diketik manual kalau QR gagal scan
    c.setFillColorRGB(0.20, 0.25, 0.33)
    c.setFont("Helvetica", 4.8)
    qr_caption = fit_pdf_text(c, barcode_value, qr_size + 2 * mm, "Helvetica", 4.8)
    c.drawCentredString(qr_x + qr_size / 2, y + 2.3 * mm, qr_caption)



def draw_one_barcode_label_portrait(
    c,
    participant,
    x,
    y,
    label_width,
    label_height,
    show_institution=True,
    show_date=False,
    show_border=False
):
    """
    Layout khusus label roll thermal 30mm x 50mm.
    Dipakai jika label fisik lebarnya 3cm dan panjang feed 5cm.
    """
    if show_border:
        c.setLineWidth(0.25)
        c.setStrokeColorRGB(0.78, 0.82, 0.88)
        c.roundRect(
            x + 0.7 * mm,
            y + 0.7 * mm,
            label_width - 1.4 * mm,
            label_height - 1.4 * mm,
            2.0 * mm
        )

    barcode = ensure_barcode_for_participant(participant["id"])
    barcode_value = barcode.get("barcode_value") if barcode else display_value(participant.get("barcode_value"))
    barcode_image_path = barcode.get("barcode_image_path") if barcode else participant.get("barcode_image_path")

    padding = 2.0 * mm

    # Layout compact:
    # identitas di kiri, QR kecil di kanan, seluruh konten ditempel ke atas
    # agar tidak ada ruang putih panjang di bawah.
    qr_size = 7.0 * mm
    qr_gap = 1.3 * mm
    text_x = x + padding
    text_width = label_width - (padding * 2) - qr_size - qr_gap
    qr_x = x + label_width - padding - qr_size

    # Jika halaman pendek, margin atas/bawah dibuat kecil.
    top_y = y + label_height - 4.2 * mm

    # Nama peserta.
    c.setFillColorRGB(0.05, 0.09, 0.16)
    name_text = fit_pdf_text(
        c,
        display_value(participant.get("name")).upper(),
        text_width,
        "Helvetica-Bold",
        4.1
    )
    c.setFont("Helvetica-Bold", 4.1)
    c.drawString(text_x, top_y, name_text)

    # ID internal.
    id_y = top_y - 3.0 * mm
    id_text = f"ID: {display_value(participant.get('mcu_id'))}"
    id_text = fit_pdf_text(c, id_text, text_width, "Helvetica", 3.8)
    c.setFont("Helvetica", 3.8)
    c.setFillColorRGB(0.10, 0.14, 0.22)
    c.drawString(text_x, id_y, id_text)

    # Instansi / perusahaan.
    line_y = id_y - 2.7 * mm
    if show_institution:
        institution = display_value(participant.get("institution_name") or participant.get("company_name"))
        inst_text = fit_pdf_text(c, institution, text_width, "Helvetica", 3.6)
        c.setFont("Helvetica", 3.6)
        c.setFillColorRGB(0.25, 0.32, 0.43)
        c.drawString(text_x, line_y, inst_text)

    if show_date:
        line_y -= 2.5 * mm
        mcu_date = display_value(participant.get("mcu_date") or participant.get("service_date"))
        date_text = f"Tgl: {mcu_date}"
        date_text = fit_pdf_text(c, date_text, text_width, "Helvetica", 3.2)
        c.setFont("Helvetica", 3.2)
        c.setFillColorRGB(0.35, 0.40, 0.50)
        c.drawString(text_x, line_y, date_text)

    # QR kanan sejajar dengan blok identitas.
    qr_y = top_y - 4.2 * mm

    if barcode_image_path and Path(barcode_image_path).exists() and ImageReader:
        try:
            c.drawImage(
                ImageReader(barcode_image_path),
                qr_x,
                qr_y,
                qr_size,
                qr_size,
                preserveAspectRatio=True,
                mask="auto"
            )
        except Exception:
            pass

    # Nilai barcode tepat di bawah QR, tetap kecil.
    c.setFillColorRGB(0.20, 0.25, 0.33)
    c.setFont("Helvetica", 2.7)
    qr_caption = fit_pdf_text(c, barcode_value, qr_size + 1.0 * mm, "Helvetica", 2.7)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 1.4 * mm, qr_caption)




def draw_one_barcode_label_40x30(
    c,
    participant,
    x,
    y,
    label_width,
    label_height,
    show_institution=True,
    show_date=False,
    show_border=False
):
    """
    Layout khusus thermal Xprinter label 40mm x 30mm.
    1 halaman PDF = 1 stiker fisik.
    Identitas di kiri, QR di kanan.
    """
    if show_border:
        c.setLineWidth(0.25)
        c.setStrokeColorRGB(0.78, 0.82, 0.88)
        c.roundRect(
            x + 0.7 * mm,
            y + 0.7 * mm,
            label_width - 1.4 * mm,
            label_height - 1.4 * mm,
            2.0 * mm
        )

    barcode = ensure_barcode_for_participant(participant["id"])
    barcode_value = barcode.get("barcode_value") if barcode else display_value(participant.get("barcode_value"))
    barcode_image_path = barcode.get("barcode_image_path") if barcode else participant.get("barcode_image_path")

    padding = 2.0 * mm
    qr_size = 10.5 * mm
    qr_gap = 1.5 * mm

    text_x = x + padding
    qr_x = x + label_width - padding - qr_size
    qr_y = y + 9.8 * mm

    text_width = label_width - (padding * 2) - qr_size - qr_gap
    text_top = y + label_height - 8.0 * mm

    c.setFillColorRGB(0.05, 0.09, 0.16)

    name_text = fit_pdf_text(
        c,
        display_value(participant.get("name")).upper(),
        text_width,
        "Helvetica-Bold",
        5.2
    )
    c.setFont("Helvetica-Bold", 5.2)
    c.drawString(text_x, text_top, name_text)

    id_y = text_top - 4.5 * mm
    id_text = f"ID: {display_value(participant.get('mcu_id'))}"
    id_text = fit_pdf_text(c, id_text, text_width, "Helvetica", 4.7)
    c.setFont("Helvetica", 4.7)
    c.setFillColorRGB(0.10, 0.14, 0.22)
    c.drawString(text_x, id_y, id_text)

    inst_y = id_y - 4.1 * mm
    if show_institution:
        institution = display_value(participant.get("institution_name") or participant.get("company_name"))
        inst_text = fit_pdf_text(c, institution, text_width, "Helvetica", 4.5)
        c.setFont("Helvetica", 4.5)
        c.setFillColorRGB(0.25, 0.32, 0.43)
        c.drawString(text_x, inst_y, inst_text)

    if show_date:
        date_y = inst_y - 3.7 * mm
        mcu_date = display_value(participant.get("mcu_date") or participant.get("service_date"))
        date_text = f"Tgl: {mcu_date}"
        date_text = fit_pdf_text(c, date_text, text_width, "Helvetica", 4.0)
        c.setFont("Helvetica", 4.0)
        c.setFillColorRGB(0.35, 0.40, 0.50)
        c.drawString(text_x, date_y, date_text)

    if barcode_image_path and Path(barcode_image_path).exists() and ImageReader:
        try:
            c.drawImage(
                ImageReader(barcode_image_path),
                qr_x,
                qr_y,
                qr_size,
                qr_size,
                preserveAspectRatio=True,
                mask="auto"
            )
        except Exception:
            pass

    c.setFillColorRGB(0.20, 0.25, 0.33)
    c.setFont("Helvetica", 3.2)
    qr_caption = fit_pdf_text(c, barcode_value, qr_size + 2.0 * mm, "Helvetica", 3.2)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 1.8 * mm, qr_caption)



def generate_barcode_label_pdf(
    participants,
    copies_per_participant=6,
    title="label_barcode",
    show_institution=True,
    show_date=False,
    show_border=True,
    print_mode="thermal_xprinter_30x50"
):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("Library reportlab belum terinstall. Jalankan: pip install reportlab")

    if not QR_AVAILABLE:
        raise RuntimeError("Library qrcode belum terinstall. Jalankan: pip install qrcode[pil] pillow")

    if not participants:
        raise ValueError("Tidak ada peserta untuk dibuat label.")

    LABEL_PDF_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = LABEL_PDF_DIR / f"{safe_filename(title)}_{timestamp}.pdf"

    all_labels = []

    copies_per_participant = int(copies_per_participant)

    for participant in participants:
        for _ in range(copies_per_participant):
            all_labels.append(participant)

    if print_mode == "thermal_xprinter_40x30":
        # Ukuran actual stiker dari user: lebar 4cm x tinggi 3cm.
        label_width = 40 * mm
        label_height = 30 * mm
        c = canvas.Canvas(str(output_path), pagesize=(label_width, label_height))

        for idx, participant in enumerate(all_labels):
            if idx > 0:
                c.showPage()

            draw_one_barcode_label_40x30(
                c,
                participant,
                0,
                0,
                label_width,
                label_height,
                show_institution=show_institution,
                show_date=show_date,
                show_border=show_border
            )

        c.save()

        return output_path

    if print_mode == "thermal_xprinter_compact_30x17":
        # Compact content-fit:
        # 1 halaman PDF hanya setinggi konten, untuk menghilangkan space putih panjang.
        label_width = 30 * mm
        label_height = 17 * mm
        c = canvas.Canvas(str(output_path), pagesize=(label_width, label_height))

        for idx, participant in enumerate(all_labels):
            if idx > 0:
                c.showPage()

            draw_one_barcode_label_portrait(
                c,
                participant,
                0,
                0,
                label_width,
                label_height,
                show_institution=show_institution,
                show_date=show_date,
                show_border=show_border
            )

        c.save()

        return output_path

    if print_mode == "thermal_xprinter_30x50":
        # FIX alignment:
        # Label fisik 3cm x 5cm biasanya di driver Xprinter harus diset Width 30mm, Height 50mm.
        # 1 halaman PDF = 1 label ukuran 30mm x 50mm.
        label_width = 30 * mm
        label_height = 50 * mm
        c = canvas.Canvas(str(output_path), pagesize=(label_width, label_height))

        for idx, participant in enumerate(all_labels):
            if idx > 0:
                c.showPage()

            draw_one_barcode_label_portrait(
                c,
                participant,
                0,
                0,
                label_width,
                label_height,
                show_institution=show_institution,
                show_date=show_date,
                show_border=show_border
            )

        c.save()

        return output_path

    if print_mode == "thermal_xprinter_50x30":
        # Mode alternatif bila driver printer diset Width 50mm, Height 30mm.
        label_width = 50 * mm
        label_height = 30 * mm
        c = canvas.Canvas(str(output_path), pagesize=(label_width, label_height))

        for idx, participant in enumerate(all_labels):
            if idx > 0:
                c.showPage()

            draw_one_barcode_label(
                c,
                participant,
                0,
                0,
                label_width,
                label_height,
                show_institution=show_institution,
                show_date=show_date,
                show_border=show_border
            )

        c.save()

        return output_path

    # Mode A4 sticker sheet:
    # 4 kolom x 9 baris = 36 label per halaman.
    label_width = 50 * mm
    label_height = 30 * mm

    page_width, page_height = A4

    labels_per_row = 4
    labels_per_col = 9
    labels_per_page = labels_per_row * labels_per_col

    margin_x = (page_width - (labels_per_row * label_width)) / 2
    margin_y = (page_height - (labels_per_col * label_height)) / 2

    c = canvas.Canvas(str(output_path), pagesize=A4)

    for idx, participant in enumerate(all_labels):
        page_index = idx % labels_per_page

        if idx > 0 and page_index == 0:
            c.showPage()

        row = page_index // labels_per_row
        col = page_index % labels_per_row

        x = margin_x + (col * label_width)
        y = page_height - margin_y - ((row + 1) * label_height)

        draw_one_barcode_label(
            c,
            participant,
            x,
            y,
            label_width,
            label_height,
            show_institution=show_institution,
            show_date=show_date,
            show_border=show_border
        )

    c.save()

    return output_path



# =========================
# EXPORT EXCEL
# =========================

def export_mcu_results_to_excel(company_id=None, package_id=None, program_type=None, source_id=None, mcu_date_from=None, mcu_date_to=None):
    EXPORT_DIR.mkdir(exist_ok=True)
    conn = get_connection()
    where_clauses = ["1 = 1"]
    params = []
    if company_id:
        where_clauses.append("participants.company_id = ?")
        params.append(company_id)
    if package_id:
        where_clauses.append("participants.package_id = ?")
        params.append(package_id)
    if source_id:
        where_clauses.append("participants.source_id = ?")
        params.append(source_id)
    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_clauses.append("participants.program_type = ?")
        params.append(program_type)
    if mcu_date_from:
        where_clauses.append("participants.mcu_date >= ?")
        params.append(mcu_date_from)
    if mcu_date_to:
        where_clauses.append("participants.mcu_date <= ?")
        params.append(mcu_date_to)
    where_sql = " AND ".join(where_clauses)
    query = f"""
    SELECT participants.id AS participant_id, participants.source_id AS source_id, participants.barcode_value, participants.barcode_image_path,
           participants.mcu_id, participants.external_id,
           participant_sources.name AS source_name, participants.province, participants.name AS participant_name,
           participants.nik, participants.gender, participants.birth_date, participants.program_type,
           companies.name AS company_name, packages.name AS package_name, participants.mcu_date,
           parameters.id AS parameter_id, parameters.name AS parameter_name, parameters.category AS parameter_category,
           parameters.unit AS parameter_unit, examination_results.value AS result_value,
           input_users.name AS input_by, update_users.name AS updated_by, posts.name AS input_post,
           examination_results.created_at AS input_at, examination_results.updated_at AS updated_at
    FROM participants
    LEFT JOIN companies ON participants.company_id = companies.id
    LEFT JOIN packages ON participants.package_id = packages.id
    LEFT JOIN participant_sources ON participants.source_id = participant_sources.id
    LEFT JOIN package_parameters ON package_parameters.package_id = participants.package_id
    LEFT JOIN parameters ON parameters.id = package_parameters.parameter_id
    LEFT JOIN examination_results ON examination_results.participant_id = participants.id
        AND examination_results.parameter_id = parameters.id
    LEFT JOIN users AS input_users ON examination_results.input_by = input_users.id
    LEFT JOIN users AS update_users ON examination_results.updated_by = update_users.id
    LEFT JOIN posts ON examination_results.input_post_id = posts.id
    WHERE {where_sql}
    ORDER BY participants.id ASC, parameters.category ASC, parameters.sort_order ASC, parameters.id ASC
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        raise ValueError("Tidak ada data peserta untuk filter yang dipilih.")
    base_columns = [
        "participant_id", "mcu_id", "external_id", "source_name", "province", "participant_name",
        "nik", "gender", "birth_date", "program_type", "company_name", "package_name", "mcu_date"
    ]
    participant_df = df[base_columns].drop_duplicates()
    result_df = df.dropna(subset=["parameter_name"]).copy()
    if result_df.empty:
        final_df = participant_df.copy()
    else:
        pivot_df = result_df.pivot_table(index=base_columns, columns="parameter_name", values="result_value", aggfunc="first").reset_index()
        final_df = participant_df.merge(pivot_df, on=base_columns, how="left")
    final_df = final_df.drop(columns=["participant_id"], errors="ignore")
    final_df = final_df.rename(columns={
        "mcu_id": "ID Internal", "external_id": "ID Instansi", "source_name": "Database Instansi",
        "province": "Provinsi", "participant_name": "Nama Peserta", "nik": "NIK",
        "gender": "Jenis Kelamin", "birth_date": "Tanggal Lahir", "program_type": "Program",
        "company_name": "Instansi/Perusahaan", "package_name": "Paket", "mcu_date": "Tanggal MCU",
    })
    final_df = reorder_summary_columns_with_final_score(final_df)

    # Pastikan Tanggal MCU muncul jelas di Summary export.
    preferred_summary_columns = [
        "Nama Peserta",
        "ID Instansi",
        "NIK",
        "ID Internal",
        "Barcode Value",
        "Provinsi",
        "Program",
        "Instansi/Perusahaan",
        "Paket",
        "Database Instansi",
        "Tanggal MCU",
    ]

    existing_preferred_columns = [
        col for col in preferred_summary_columns
        if col in final_df.columns
    ]

    remaining_columns = [
        col for col in final_df.columns
        if col not in existing_preferred_columns
    ]

    final_df = final_df[existing_preferred_columns + remaining_columns]
    raw_df = df.drop(columns=["participant_id"], errors="ignore")
    progress_df = pd.DataFrame(get_participant_progress(program_type=program_type))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    source_part = f"_source_{source_id}" if source_id else ""
    output_path = EXPORT_DIR / f"mcu_export{source_part}_{timestamp}.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="Summary", index=False)
        raw_preferred_columns = [
            "ID Internal",
            "ID Instansi",
            "Nama Peserta",
            "Barcode Value",
            "Provinsi",
            "Tanggal MCU",
            "Database Instansi",
            "Program",
            "Instansi/Perusahaan",
            "Paket",
        ]

        raw_existing_preferred_columns = [
            col for col in raw_preferred_columns
            if col in raw_df.columns
        ]

        raw_remaining_columns = [
            col for col in raw_df.columns
            if col not in raw_existing_preferred_columns
        ]

        raw_df = raw_df[raw_existing_preferred_columns + raw_remaining_columns]

        raw_df.to_excel(writer, sheet_name="Raw Results", index=False)
        progress_df.to_excel(writer, sheet_name="Progress", index=False)
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter
                for cell in column_cells:
                    if cell.value is not None:
                        max_length = max(max_length, len(str(cell.value)))
                worksheet.column_dimensions[column_letter].width = min(max_length + 2, 45)
    return output_path


def parse_select_options(config_json):
    if not config_json:
        return []
    try:
        data = json.loads(config_json)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("options"), list):
            return data["options"]
    except Exception:
        return []
    return []


def render_generic_dynamic_form(participant, user, active_program_type, effective_post_id, effective_post_name):
    parameters = get_parameters_for_post(participant["package_id"], effective_post_id, active_program_type)
    existing_results = get_existing_results(participant["id"])
    if not parameters:
        st.warning("Tidak ada parameter pemeriksaan untuk post ini.")
        return
    with st.form(f"examination_result_form_{active_program_type}_{effective_post_id}"):
        st.subheader(f"Form Pemeriksaan - {effective_post_name}")
        result_values = {}
        parameter_ids_with_existing_values = set(existing_results.keys())
        for param in parameters:
            st.markdown(f"### {param['name']}")
            if param["reference_text"]:
                st.caption(param["reference_text"])
            if param["reference_image_path"]:
                image_path = Path(param["reference_image_path"])
                if image_path.exists():
                    st.image(str(image_path), caption=f"Referensi: {param['name']}", use_container_width=True)
                else:
                    st.warning(f"Gambar referensi belum ditemukan: {param['reference_image_path']}")
            current_value = safe_strip(existing_results.get(param["id"], ""))
            label = param["name"] if not param["unit"] else f"{param['name']} ({param['unit']})"
            widget_key = f"param_{participant['id']}_{effective_post_id}_{param['id']}"
            input_type = param["input_type"]
            if input_type == "textarea":
                result_values[param["id"]] = st.text_area(label, value=current_value, key=widget_key)
            elif input_type == "select":
                options = parse_select_options(param["config_json"]) or ["", "Normal", "Abnormal", "Lainnya"]
                default_index = options.index(current_value) if current_value in options else 0
                result_values[param["id"]] = st.selectbox(label, options, index=default_index, key=widget_key)
            elif input_type == "checkbox":
                checked = current_value.lower() in ["true", "1", "ya", "yes"]
                result_values[param["id"]] = st.checkbox(label, value=checked, key=widget_key)
            else:
                placeholder = "Masukkan angka" if input_type == "number" else ""
                result_values[param["id"]] = st.text_input(label, value=current_value, placeholder=placeholder, key=widget_key)
            st.divider()
        submit_result_clicked = st.form_submit_button("Simpan Hasil Pemeriksaan")
    if submit_result_clicked:
        saved_count = 0
        for parameter_id, value in result_values.items():
            normalized_value = safe_strip(value)
            if normalized_value == "" and parameter_id not in parameter_ids_with_existing_values:
                continue
            save_result(participant["id"], parameter_id, normalized_value, user["id"], effective_post_id)
            saved_count += 1
        st.success("Hasil pemeriksaan berhasil disimpan.")
        st.info(f"Total field diproses: {saved_count}. Disimpan oleh {user['name']} di post {effective_post_name}.")


def render_search_and_input(active_program_type, allow_post_choice=False):
    st.markdown('<div class="modern-card"><div class="modern-card-title">Cari Peserta</div><div class="modern-muted">Pilih database instansi, lalu cari peserta menggunakan nama lengkap, ID instansi, NIK, ID internal, provinsi, atau scan barcode.</div></div>', unsafe_allow_html=True)
    user = st.session_state.user
    effective_post_id = user["post_id"]
    effective_post_name = user["post_name"]

    sources = get_participant_sources(program_type=active_program_type)

    if not sources:
        st.warning(
            "Belum ada Database Instansi yang tersedia. "
            "Admin harus import dulu lewat Import CAPASKA > Import Database Peserta Instansi."
        )

    source_options = {"Semua Database Instansi": None}
    for source in sources:
        label = f"{source['name']} - {source.get('institution_name') or '-'}"
        source_options[label] = source["id"]
    selected_source_label = st.selectbox("Pilih Database Instansi", list(source_options.keys()))
    selected_source_id = source_options[selected_source_label]

    if allow_post_choice:
        posts = get_posts(program_type=active_program_type, include_admin=False)
        if not posts:
            st.warning(f"Belum ada post untuk program {program_label(active_program_type)}.")
            return
        post_options = {post["name"]: post["id"] for post in posts}
        selected_post_name = st.selectbox("Pilih Post Input", list(post_options.keys()))
        effective_post_id = post_options[selected_post_name]
        effective_post_name = selected_post_name

    with st.form(f"search_participant_form_{active_program_type}"):
        search_keyword = st.text_input("Cari Nama Lengkap / ID Instansi / NIK / Barcode / Provinsi", placeholder="Contoh: Chelsea, CAPASKA-2026-0001, atau scan barcode")
        search_clicked = st.form_submit_button("Cari Peserta")
    if search_clicked:
        if not search_keyword.strip():
            st.error("Masukkan nama peserta, ID instansi, NIK, ID internal, atau provinsi.")
            st.session_state.search_results = []
            st.session_state.selected_participant = None
        else:
            results = search_participants(
                keyword=search_keyword.strip(),
                program_type=active_program_type,
                source_id=selected_source_id,
                limit=50
            )

            st.session_state.search_results = results
            st.session_state.selected_participant = None

            if results:
                st.success(f"Ditemukan {len(results)} peserta. Pilih salah satu dari tabel.")
            else:
                if selected_source_id:
                    st.error(
                        "Peserta tidak ditemukan di Database Instansi yang dipilih. "
                        "Pastikan nama yang dicari memang ada di database ini, atau pilih database lain."
                    )
                else:
                    st.error("Peserta tidak ditemukan.")

    if st.session_state.search_results and st.session_state.selected_participant is None:
        st.subheader("Hasil Pencarian")
        search_result_df = pd.DataFrame(st.session_state.search_results)
        display_columns = {
            "name": "Nama Peserta", "external_id": "ID Instansi", "nik": "NIK", "mcu_id": "ID Internal",
            "source_name": "Database Instansi", "province": "Provinsi", "company_name": "Instansi/Perusahaan",
            "package_name": "Paket", "gender": "Jenis Kelamin", "service_date": "Tanggal Layanan",
            "exam_type": "Jenis Pemeriksaan", "doctor_assigned": "Dokter Bertugas", "nurse_assigned": "Perawat Bertugas",
            "mcu_date": "Tanggal MCU",
        }
        existing_columns = [col for col in display_columns if col in search_result_df.columns]
        display_df = search_result_df[existing_columns].copy().rename(columns=display_columns)
        for col in display_df.columns:
            display_df[col] = display_df[col].apply(display_value)
        st.caption("Klik salah satu baris peserta di tabel, lalu tekan tombol Gunakan Peserta Terpilih.")
        selected_table = st.dataframe(display_df, use_container_width=True, height=350, hide_index=True,
                                      selection_mode="single-row", on_select="rerun",
                                      key=f"participant_search_table_{active_program_type}")
        selected_rows = selected_table.selection.rows
        if selected_rows:
            selected_index = selected_rows[0]
            selected_participant = st.session_state.search_results[selected_index]
            st.success(f"Peserta dipilih: {selected_participant.get('name') or '-'} | ID Internal: {selected_participant.get('mcu_id') or '-'}")
            if st.button("Gunakan Peserta Terpilih"):
                st.session_state.selected_participant = selected_participant
                st.rerun()

    participant = st.session_state.selected_participant
    if participant:
        if participant.get("program_type") != active_program_type:
            st.error("Peserta ini bukan bagian dari program yang sedang aktif.")
            return
        st.divider()
        st.subheader("Data Peserta")
        col1, col2, col3 = st.columns([1, 1, 1.2])
        with col1:
            st.write(f"**Nama:** {display_value(participant.get('name'))}")
            st.write(f"**ID Instansi:** {display_value(participant.get('external_id'))}")
            st.write(f"**ID Internal:** {display_value(participant.get('mcu_id'))}")
            st.write(f"**Database Instansi:** {display_value(participant.get('source_name'))}")

            if not participant.get("source_id"):
                st.warning(
                    "Peserta ini belum terhubung ke Database Instansi baru. "
                    "Kalau ingin input peserta dari database baru, pilih database instansi yang benar lalu cari nama peserta dari database itu."
                )
        with col2:
            st.write(f"**NIK:** {display_value(participant.get('nik'))}")
            st.write(f"**Provinsi:** {display_value(participant.get('province'))}")
            st.write(f"**Jenis Kelamin:** {display_value(participant.get('gender'))}")
            st.write(f"**Perusahaan/Instansi:** {display_value(participant.get('company_name'))}")
            st.write(f"**Jenis Pemeriksaan:** {display_value(participant.get('exam_type'))}")
        with col3:
            st.write(f"**Program:** {program_label(participant.get('program_type'))}")
            st.write(f"**Paket:** {display_value(participant.get('package_name'))}")
            st.write(f"**Dokter Bertugas:** {display_value(participant.get('doctor_assigned'))}")
            st.write(f"**Perawat Bertugas:** {display_value(participant.get('nurse_assigned'))}")
            current_mcu_date = parse_mcu_date(participant.get("mcu_date") or participant.get("service_date"))
            with st.form(f"update_mcu_date_form_{participant['id']}"):
                selected_mcu_date = st.date_input("Tanggal MCU", value=current_mcu_date)
                update_date_clicked = st.form_submit_button("Update Tanggal MCU")
            if update_date_clicked:
                update_participant_mcu_date(participant["id"], selected_mcu_date)
                st.session_state.selected_participant["mcu_date"] = str(selected_mcu_date)
                st.success("Tanggal MCU berhasil diupdate.")
                st.rerun()
            render_stage_progress_box(participant)
        st.write(f"**Post Input:** {effective_post_name}")
        st.divider()
        if active_program_type == PROGRAM_CAPASKA:
            custom_rendered = render_capaska_form(participant, user, effective_post_id, effective_post_name)
            if custom_rendered:
                return
        render_generic_dynamic_form(participant, user, active_program_type, effective_post_id, effective_post_name)

# =========================
# SESSION STATE AND LOGIN
# =========================

check_database_exists()
ensure_runtime_schema()

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    restored_user = restore_login_from_persistent_session()
    if restored_user:
        st.session_state.user = restored_user

if "selected_participant" not in st.session_state:
    st.session_state.selected_participant = None
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "export_file_path" not in st.session_state:
    st.session_state.export_file_path = None
if "submission_refresh_at" not in st.session_state:
    st.session_state.submission_refresh_at = ""

if st.session_state.user is None:
    render_hero("MCU System Login", "Masuk sesuai role petugas untuk mulai pemeriksaan.", "Secure Access")
    render_simple_steps(
        "Panduan Login",
        [
            "Masukkan username dan password petugas.",
            "Setelah login, sistem akan tetap masuk walau halaman di-refresh.",
            "Gunakan tombol Logout jika sudah selesai."
        ]
    )
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_clicked = st.form_submit_button("Login")
    if login_clicked:
        user = login(username.strip(), password.strip())
        if user:
            token = create_auth_session(user["id"])
            set_query_token(token)

            st.session_state.user = user
            st.session_state.selected_participant = None
            st.session_state.search_results = []
            st.success("Login berhasil.")
            st.rerun()
        else:
            st.error("Username atau password salah.")
    st.info("""
    User demo:
    - admin / admin123
    - antro / antro123
    - vital / vital123
    - lab / lab123
    - gigi / gigi123
    - dokter / dokter123

    CAPASKA operator:
    - capaska_registrasi / registrasi123
    - capaska_mata / mata123
    - capaska_pd / pd123
    - capaska_gigi / gigi123
    - capaska_tht / tht123
    - capaska_jantung / jantung123
    - capaska_ortopedi / ortopedi123
    - capaska_radiologi / radiologi123

    Review:
    - dokter_review / dokter123
    - supervisor_capaska / supervisor123
    """)
    st.stop()



# =========================
# HAMBURGER MENU HELPERS
# =========================

def get_menu_options_for_user(user, user_program):
    role = user.get("role")

    if role == "admin":
        return [
            "Dashboard",
            "Master Data",
            "Registrasi Corporate",
            "Input MCU Corporate",
            "Input CAPASKA",
            "Import CAPASKA",
            "Export Excel",
            "Cetak Label Barcode",
            "Review Hasil",
            "Audit Trail",
            "Submission Saya",
            "Logout",
        ]

    # Dokter / Supervisor tidak boleh masuk menu input operator.
    # Fokusnya monitoring dashboard, review hasil, dan audit.
    if role in ["doctor", "supervisor"]:
        if user_program == PROGRAM_CAPASKA:
            return [
                "Dashboard CAPASKA",
                "Review Hasil",
                "Audit Trail",
                "Logout",
            ]

        return [
            "Dashboard Corporate",
            "Review Hasil",
            "Audit Trail",
            "Logout",
        ]

    # Operator CAPASKA hanya input sesuai post dan melihat submission sendiri.
    if user_program == PROGRAM_CAPASKA:
        return [
            "Dashboard CAPASKA",
            "Input CAPASKA",
            "Submission Saya",
            "Logout",
        ]

    # Operator corporate.
    return [
        "Input MCU Corporate",
        "Submission Saya",
        "Logout",
    ]


def render_hamburger_menu(user, user_program):
    """
    Menu dibuat manual-submit agar tidak langsung ganti halaman setiap radio berubah.
    Streamlit tetap rerun saat submit, tetapi pilihan menu tidak diproses sampai user klik tombol.
    """
    menu_options = get_menu_options_for_user(user, user_program)

    if "main_menu" not in st.session_state or st.session_state.main_menu not in menu_options:
        st.session_state.main_menu = menu_options[0]

    if "pending_main_menu" not in st.session_state or st.session_state.pending_main_menu not in menu_options:
        st.session_state.pending_main_menu = st.session_state.main_menu

    st.markdown('<div class="top-menu-shell">', unsafe_allow_html=True)

    col_menu, col_context = st.columns([0.18, 0.82], vertical_alignment="center")

    with col_menu:
        if hasattr(st, "popover"):
            with st.popover("☰ MENU UTAMA", use_container_width=True):
                st.markdown("### Menu")
                st.markdown(f"**User:** {display_value(user.get('name'))}")
                st.markdown(f"**Role:** {display_value(user.get('role'))}")
                st.markdown(f"**Post:** {display_value(user.get('post_name'))}")
                st.markdown(f"**Program:** {program_label(user_program)}")
                st.divider()

                with st.form("main_menu_manual_form", clear_on_submit=False):
                    current_index = menu_options.index(st.session_state.main_menu) if st.session_state.main_menu in menu_options else 0

                    selected_menu = st.radio(
                        "Pilih Menu",
                        menu_options,
                        index=current_index,
                        key="pending_main_menu_radio"
                    )

                    open_menu_clicked = st.form_submit_button(
                        "Buka Menu",
                        use_container_width=True
                    )

                    if open_menu_clicked:
                        st.session_state.main_menu = selected_menu
                        st.session_state.pending_main_menu = selected_menu
                        st.rerun()
        else:
            with st.expander("☰ MENU UTAMA", expanded=False):
                st.markdown("### Menu")
                st.markdown(f"**User:** {display_value(user.get('name'))}")
                st.markdown(f"**Role:** {display_value(user.get('role'))}")
                st.markdown(f"**Post:** {display_value(user.get('post_name'))}")
                st.markdown(f"**Program:** {program_label(user_program)}")
                st.divider()

                with st.form("main_menu_manual_form_fallback", clear_on_submit=False):
                    current_index = menu_options.index(st.session_state.main_menu) if st.session_state.main_menu in menu_options else 0

                    selected_menu = st.radio(
                        "Pilih Menu",
                        menu_options,
                        index=current_index,
                        key="pending_main_menu_radio_fallback"
                    )

                    open_menu_clicked = st.form_submit_button(
                        "Buka Menu",
                        use_container_width=True
                    )

                    if open_menu_clicked:
                        st.session_state.main_menu = selected_menu
                        st.session_state.pending_main_menu = selected_menu
                        st.rerun()

    with col_context:
        st.markdown(
            f"""
            <div class="hamburger-topbar">
                <div class="hamburger-current">{display_value(st.session_state.main_menu)}</div>
                <div class="hamburger-subtitle">
                    {display_value(user.get('name'))} · {display_value(user.get('role'))} · {program_label(user_program)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state.main_menu


user = st.session_state.user
user_program = get_user_program(user)

menu = render_hamburger_menu(user, user_program)

if menu == "Logout":
    logout()



# =========================
# REVIEW HASIL
# =========================

def get_review_result_rows(participant_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        posts.name AS post_name,
        parameters.id AS parameter_id,
        parameters.name AS parameter_name,
        parameters.category AS parameter_category,
        parameters.unit AS parameter_unit,
        parameters.sort_order,
        examination_results.value AS result_value,
        input_user.name AS input_by,
        update_user.name AS updated_by,
        examination_results.created_at AS input_at,
        examination_results.updated_at AS updated_at
    FROM participants
    LEFT JOIN package_parameters
        ON package_parameters.package_id = participants.package_id
    LEFT JOIN parameters
        ON parameters.id = package_parameters.parameter_id
    LEFT JOIN posts
        ON posts.id = parameters.post_id
    LEFT JOIN examination_results
        ON examination_results.participant_id = participants.id
       AND examination_results.parameter_id = parameters.id
    LEFT JOIN users AS input_user
        ON examination_results.input_by = input_user.id
    LEFT JOIN users AS update_user
        ON examination_results.updated_by = update_user.id
    WHERE participants.id = ?
      AND parameters.is_active = 1
    ORDER BY
        posts.id ASC,
        parameters.sort_order ASC,
        parameters.id ASC
    """, (participant_id,))

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_participant_review(participant_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        participant_reviews.*,
        users.name AS reviewed_by_name
    FROM participant_reviews
    LEFT JOIN users ON participant_reviews.reviewed_by = users.id
    WHERE participant_reviews.participant_id = ?
    """, (participant_id,))

    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


def save_participant_review(participant_id, user_id, review_status, final_decision, doctor_note):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO participant_reviews
    (
        participant_id,
        review_status,
        final_decision,
        doctor_note,
        reviewed_by,
        reviewed_at,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT(participant_id) DO UPDATE SET
        review_status = excluded.review_status,
        final_decision = excluded.final_decision,
        doctor_note = excluded.doctor_note,
        reviewed_by = excluded.reviewed_by,
        reviewed_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    """, (
        participant_id,
        review_status,
        final_decision,
        doctor_note,
        user_id
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
        "REVIEW_HASIL",
        participant_id,
        None,
        None,
        f"{review_status} | {final_decision} | {doctor_note}"
    ))

    conn.commit()
    conn.close()


def summarize_score_rows(result_rows):
    score_rows = []

    for row in result_rows:
        parameter_name = display_value(row.get("parameter_name"))
        value = display_value(row.get("result_value"))

        if is_score_column(parameter_name) or parameter_name.upper() == "FINAL SCORE":
            score_rows.append({
                "Post": display_value(row.get("post_name")),
                "Parameter": parameter_name,
                "Nilai": value,
            })

    total_score = 0

    for row in score_rows:
        total_score += to_score_number(row.get("Nilai"))

    return score_rows, total_score


def render_review_detail(participant):
    if not participant:
        return

    st.divider()

    st.subheader("Data Peserta untuk Review")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Nama:** {display_value(participant.get('name'))}")
        st.write(f"**ID Internal:** {display_value(participant.get('mcu_id'))}")
        st.write(f"**ID Instansi:** {display_value(participant.get('external_id'))}")

    with col2:
        st.write(f"**Database:** {display_value(participant.get('source_name'))}")
        st.write(f"**Provinsi:** {display_value(participant.get('province'))}")
        st.write(f"**Jenis Kelamin:** {display_value(participant.get('gender'))}")

    with col3:
        st.write(f"**Paket:** {display_value(participant.get('package_name'))}")
        st.write(f"**Tanggal MCU:** {display_value(participant.get('mcu_date'))}")
        st.write(f"**Program:** {program_label(participant.get('program_type'))}")

    col_progress, col_review = st.columns([1, 1])

    with col_progress:
        render_stage_progress_box(participant)

    result_rows = get_review_result_rows(participant["id"])
    score_rows, total_score = summarize_score_rows(result_rows)
    review = get_participant_review(participant["id"])

    with col_review:
        with st.container(border=True):
            st.markdown("### Summary Review")
            st.metric("Estimasi Final Score", total_score)

            if review:
                st.write(f"**Status Review:** {display_value(review.get('review_status'))}")
                st.write(f"**Keputusan Akhir:** {display_value(review.get('final_decision'))}")
                st.write(f"**Direview Oleh:** {display_value(review.get('reviewed_by_name'))}")
                st.write(f"**Waktu Review:** {display_value(review.get('reviewed_at'))}")
                st.write(f"**Catatan:** {display_value(review.get('doctor_note'))}")
            else:
                st.warning("Belum ada review dokter/supervisor.")

    tab_summary, tab_by_post, tab_scores, tab_review = st.tabs([
        "Ringkasan Hasil",
        "Hasil per Post",
        "Score",
        "Simpan Review",
    ])

    with tab_summary:
        if not result_rows:
            st.info("Belum ada hasil pemeriksaan.")
        else:
            summary_df = pd.DataFrame(result_rows)

            summary_df = summary_df.rename(columns={
                "post_name": "Post",
                "parameter_name": "Parameter",
                "parameter_category": "Kategori",
                "result_value": "Nilai",
                "input_by": "Input Oleh",
                "updated_by": "Update Oleh",
                "input_at": "Input Pada",
                "updated_at": "Update Pada",
            })

            display_columns = [
                "Post",
                "Kategori",
                "Parameter",
                "Nilai",
                "Input Oleh",
                "Update Oleh",
                "Input Pada",
                "Update Pada",
            ]

            display_columns = [
                col for col in display_columns
                if col in summary_df.columns
            ]

            summary_df = summary_df[display_columns].copy()

            for col in summary_df.columns:
                summary_df[col] = summary_df[col].apply(display_value)

            st.dataframe(summary_df, use_container_width=True, height=420)

    with tab_by_post:
        if not result_rows:
            st.info("Belum ada hasil pemeriksaan.")
        else:
            grouped_posts = {}

            for row in result_rows:
                post_name = display_value(row.get("post_name"))
                grouped_posts.setdefault(post_name, []).append(row)

            for post_name, rows in grouped_posts.items():
                with st.expander(post_name, expanded=False):
                    post_df = pd.DataFrame(rows)

                    post_df = post_df.rename(columns={
                        "parameter_name": "Parameter",
                        "parameter_category": "Kategori",
                        "result_value": "Nilai",
                        "input_by": "Input Oleh",
                        "updated_by": "Update Oleh",
                    })

                    display_columns = [
                        "Kategori",
                        "Parameter",
                        "Nilai",
                        "Input Oleh",
                        "Update Oleh",
                    ]

                    display_columns = [
                        col for col in display_columns
                        if col in post_df.columns
                    ]

                    post_df = post_df[display_columns].copy()

                    for col in post_df.columns:
                        post_df[col] = post_df[col].apply(display_value)

                    st.dataframe(post_df, use_container_width=True)

    with tab_scores:
        if not score_rows:
            st.info("Belum ada parameter score yang terbaca.")
        else:
            score_df = pd.DataFrame(score_rows)

            for col in score_df.columns:
                score_df[col] = score_df[col].apply(display_value)

            st.dataframe(score_df, use_container_width=True)
            st.metric("Estimasi Final Score", total_score)

    with tab_review:
        default_status = review.get("review_status") if review else "Belum Direview"
        default_decision = review.get("final_decision") if review else "Menunggu"
        default_note = review.get("doctor_note") if review else ""

        status_options = [
            "Belum Direview",
            "Sudah Direview",
            "Perlu Recheck",
        ]

        decision_options = [
            "Menunggu",
            "Layak",
            "Tidak Layak",
            "Perlu Pemeriksaan Lanjutan",
        ]

        status_index = status_options.index(default_status) if default_status in status_options else 0
        decision_index = decision_options.index(default_decision) if default_decision in decision_options else 0

        with st.form(f"review_form_{participant['id']}"):
            review_status = st.selectbox(
                "Status Review",
                status_options,
                index=status_index
            )

            final_decision = st.selectbox(
                "Keputusan Akhir",
                decision_options,
                index=decision_index
            )

            doctor_note = st.text_area(
                "Catatan Dokter / Supervisor",
                value=default_note,
                placeholder="Contoh: hasil lengkap, perlu recheck THT, atau catatan interpretasi akhir."
            )

            save_review_clicked = st.form_submit_button("Simpan Review Hasil")

        if save_review_clicked:
            save_participant_review(
                participant_id=participant["id"],
                user_id=st.session_state.user["id"],
                review_status=review_status,
                final_decision=final_decision,
                doctor_note=doctor_note.strip()
            )

            st.success("Review hasil berhasil disimpan.")
            st.rerun()



# =========================
# DASHBOARD
# =========================

if menu in ["Dashboard", "Dashboard CAPASKA", "Dashboard Corporate"]:
    if menu == "Dashboard CAPASKA":
        dashboard_program = PROGRAM_CAPASKA
        title = "Dashboard Progress CAPASKA"
    elif menu == "Dashboard Corporate":
        dashboard_program = PROGRAM_CORPORATE
        title = "Dashboard Progress MCU Corporate"
    else:
        dashboard_program = None
        title = "Dashboard Progress Semua Program"

    render_hero(
        title,
        "Klik status Selesai atau Belum Selesai untuk monitoring peserta. Klik baris nama peserta untuk melihat staging pemeriksaan.",
        "Dashboard"
    )

    render_simple_steps(
        "Cara Pakai Dashboard",
        [
            "Pilih database instansi yang ingin dimonitor.",
            "Klik tombol Peserta Selesai atau Peserta Belum Selesai.",
            "Klik salah satu baris nama peserta untuk melihat progress stage.",
            "Klik Buka Detail Review Peserta Ini jika ingin masuk ke halaman Review Hasil."
        ]
    )

    sources = get_participant_sources(program_type=dashboard_program)

    source_options = {"Semua Database Instansi": None}

    for source in sources:
        label = f"{source.get('name') or '-'} - {source.get('institution_name') or '-'} | Source ID: {source.get('id')}"
        source_options[label] = source["id"]

    selected_dashboard_source_label = st.selectbox(
        "Filter Database Instansi",
        list(source_options.keys()),
        key=f"dashboard_source_{dashboard_program}"
    )

    selected_dashboard_source_id = source_options[selected_dashboard_source_label]

    progress = get_participant_progress(
        program_type=dashboard_program,
        source_id=selected_dashboard_source_id
    )

    if not progress:
        st.info("Belum ada peserta.")
    else:
        df = pd.DataFrame(progress)

        total_participants = len(df)
        complete_participants = len(df[df["status_pemeriksaan"] == "Selesai"])
        incomplete_participants = len(df[df["status_pemeriksaan"] != "Selesai"])
        avg_progress = round(df["progress_percent"].mean(), 1)

        if "dashboard_status_filter" not in st.session_state:
            st.session_state.dashboard_status_filter = "Semua"

        col_total, col_done, col_pending, col_avg = st.columns(4)

        with col_total:
            st.metric("Total Peserta", total_participants)
            if st.button("Lihat Semua", use_container_width=True):
                st.session_state.dashboard_status_filter = "Semua"

        with col_done:
            st.metric("Selesai", complete_participants)
            if st.button("Peserta Selesai", use_container_width=True):
                st.session_state.dashboard_status_filter = "Selesai"

        with col_pending:
            st.metric("Belum Selesai", incomplete_participants)
            if st.button("Peserta Belum Selesai", use_container_width=True):
                st.session_state.dashboard_status_filter = "Belum Selesai"

        with col_avg:
            st.metric("Rata-rata Progress", f"{avg_progress}%")
            if st.button("Refresh Dashboard", use_container_width=True):
                st.rerun()

        active_filter = st.session_state.dashboard_status_filter

        if active_filter == "Selesai":
            filtered_df = df[df["status_pemeriksaan"] == "Selesai"].copy()
        elif active_filter == "Belum Selesai":
            filtered_df = df[df["status_pemeriksaan"] != "Selesai"].copy()
        else:
            filtered_df = df.copy()

        st.subheader(f"Daftar Peserta: {active_filter}")
        st.caption("Klik satu baris peserta untuk melihat detail staging pemeriksaan.")

        if filtered_df.empty:
            st.warning(f"Tidak ada peserta dengan status: {active_filter}")
        else:
            display_df = filtered_df.rename(columns={
                "participant_id": "Participant ID",
                "participant_name": "Nama Peserta",
                "mcu_id": "ID Internal",
                "external_id": "ID Instansi",
                "province": "Provinsi",
                "source_name": "Database Instansi",
                "company_name": "Instansi/Perusahaan",
                "package_name": "Paket",
                "mcu_date": "Tanggal MCU",
                "status_pemeriksaan": "Status",
                "done_stage": "Stage Selesai",
                "total_stage": "Total Stage",
                "progress_percent": "Progress %",
                "filled_parameters": "Parameter Terisi",
                "total_parameters": "Total Parameter",
            })

            visible_columns = [
                "Participant ID",
                "Nama Peserta",
                "ID Internal",
                "ID Instansi",
                "Provinsi",
                "Database Instansi",
                "Paket",
                "Tanggal MCU",
                "Status",
                "Stage Selesai",
                "Total Stage",
                "Progress %",
            ]

            visible_columns = [
                col for col in visible_columns
                if col in display_df.columns
            ]

            display_df = display_df[visible_columns].copy()

            for col in display_df.columns:
                display_df[col] = display_df[col].apply(display_value)

            selected_table = st.dataframe(
                display_df,
                use_container_width=True,
                height=420,
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun",
                key=f"dashboard_progress_table_{dashboard_program}_{active_filter}_{selected_dashboard_source_id}"
            )

            selected_rows = selected_table.selection.rows

            if selected_rows:
                selected_index = selected_rows[0]
                selected_participant_id = int(filtered_df.iloc[selected_index]["participant_id"])
                selected_participant = get_participant_by_id(selected_participant_id)

                if selected_participant:
                    st.divider()
                    st.subheader("Detail Staging Peserta")
                    st.write(f"**Nama:** {display_value(selected_participant.get('name'))}")
                    st.write(f"**ID Internal:** {display_value(selected_participant.get('mcu_id'))}")
                    st.write(f"**Database:** {display_value(selected_participant.get('source_name'))}")

                    render_stage_progress_box(selected_participant)

                    if st.button("Buka Detail Review Peserta Ini", use_container_width=True):
                        st.session_state.review_selected_participant_id = selected_participant_id
                        st.session_state.main_menu = "Review Hasil"
                        st.rerun()


# =========================
# MASTER DATA
# =========================

if menu == "Master Data":
    render_hero("Master Data Admin", "Kelola perusahaan, paket, post, user, parameter, dan database instansi.", "Admin Panel")
    data_scope_label = st.selectbox("Filter Tampilan Data", ["Semua", "MCU Corporate", "CAPASKA / BPIP"])
    data_scope = PROGRAM_CORPORATE if data_scope_label == "MCU Corporate" else PROGRAM_CAPASKA if data_scope_label == "CAPASKA / BPIP" else None

    tab_company, tab_package, tab_post, tab_user, tab_parameter, tab_source, tab_list = st.tabs([
        "Perusahaan", "Paket MCU", "Post Pemeriksaan", "User / Operator", "Parameter", "Database Instansi", "Daftar Data"
    ])

    with tab_company:
        st.subheader("Tambah Perusahaan / Instansi")
        with st.form("create_company_form"):
            company_name = st.text_input("Nama Perusahaan / Instansi")
            company_address = st.text_area("Alamat")
            company_pic = st.text_input("PIC")
            submit_company = st.form_submit_button("Simpan Perusahaan")
        if submit_company:
            if not company_name.strip():
                st.error("Nama perusahaan wajib diisi.")
            else:
                try:
                    create_company(company_name.strip(), company_address.strip(), company_pic.strip())
                    st.success("Perusahaan berhasil ditambahkan.")
                except Exception as e:
                    st.error(f"Gagal tambah perusahaan: {e}")

    with tab_package:
        st.subheader("Tambah Paket Pemeriksaan")
        companies = get_companies()
        if not companies:
            st.warning("Tambahkan perusahaan terlebih dahulu.")
        else:
            company_options = {company["name"]: company["id"] for company in companies}
            package_program_label = st.selectbox("Program Paket", ["MCU Corporate", "CAPASKA / BPIP"], key="package_program_select")
            package_program = PROGRAM_CAPASKA if package_program_label == "CAPASKA / BPIP" else PROGRAM_CORPORATE
            with st.form("create_package_form"):
                package_name = st.text_input("Nama Paket")
                package_description = st.text_area("Deskripsi Paket")
                selected_company_name = st.selectbox("Perusahaan / Instansi", list(company_options.keys()))
                submit_package = st.form_submit_button("Simpan Paket")
            if submit_package:
                if not package_name.strip():
                    st.error("Nama paket wajib diisi.")
                else:
                    try:
                        create_package(package_name.strip(), package_description.strip(), company_options[selected_company_name], package_program)
                        st.success("Paket berhasil ditambahkan.")
                    except Exception as e:
                        st.error(f"Gagal tambah paket: {e}")

    with tab_post:
        st.subheader("Tambah Post Pemeriksaan")
        post_program_label = st.selectbox("Program Post", ["MCU Corporate", "CAPASKA / BPIP"], key="post_program_select")
        post_program = PROGRAM_CAPASKA if post_program_label == "CAPASKA / BPIP" else PROGRAM_CORPORATE
        with st.form("create_post_form"):
            post_name = st.text_input("Nama Post")
            post_description = st.text_area("Deskripsi")
            submit_post = st.form_submit_button("Simpan Post")
        if submit_post:
            if not post_name.strip():
                st.error("Nama post wajib diisi.")
            else:
                try:
                    create_post(post_name.strip(), post_description.strip(), post_program)
                    st.success("Post berhasil ditambahkan.")
                except Exception as e:
                    st.error(f"Gagal tambah post: {e}")

    with tab_user:
        st.subheader("Tambah User / Operator")
        new_user_program_label = st.selectbox("Program User", ["MCU Corporate", "CAPASKA / BPIP", "All Program"], key="user_program_select")
        new_user_program = PROGRAM_CAPASKA if new_user_program_label == "CAPASKA / BPIP" else PROGRAM_ALL if new_user_program_label == "All Program" else PROGRAM_CORPORATE
        posts = get_posts(program_type=None if new_user_program == PROGRAM_ALL else new_user_program, include_admin=True)
        post_options = {post["name"]: post["id"] for post in posts}
        with st.form("create_user_form"):
            new_user_name = st.text_input("Nama User")
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["admin", "operator", "doctor", "supervisor"])
            new_post_name = st.selectbox("Post User", list(post_options.keys()))
            submit_user = st.form_submit_button("Simpan User")
        if submit_user:
            if not new_user_name.strip() or not new_username.strip() or not new_password.strip():
                st.error("Nama user, username, dan password wajib diisi.")
            else:
                try:
                    create_user(new_user_name.strip(), new_username.strip(), new_password.strip(), new_role, post_options[new_post_name], new_user_program)
                    st.success("User berhasil ditambahkan.")
                except Exception as e:
                    st.error(f"Gagal tambah user: {e}")

    with tab_parameter:
        st.subheader("Tambah Parameter Pemeriksaan")
        param_program_label = st.selectbox("Program Parameter", ["MCU Corporate", "CAPASKA / BPIP"], key="parameter_program_select")
        param_program = PROGRAM_CAPASKA if param_program_label == "CAPASKA / BPIP" else PROGRAM_CORPORATE
        posts = get_posts(program_type=param_program, include_admin=False)
        packages = get_packages(program_type=param_program)
        if not posts:
            st.warning("Belum ada post untuk program ini.")
        elif not packages:
            st.warning("Belum ada paket untuk program ini.")
        else:
            post_options = {post["name"]: post["id"] for post in posts}
            package_options = {package["name"]: package["id"] for package in packages}
            with st.form("create_parameter_form"):
                param_name = st.text_input("Nama Parameter")
                param_category = st.text_input("Kategori", placeholder="Contoh: Vital Sign, Lab, Gigi")
                param_post_name = st.selectbox("Post Pemeriksaan", list(post_options.keys()))
                param_unit = st.text_input("Satuan")
                param_input_type = st.selectbox("Tipe Input", ["text", "number", "textarea", "select", "checkbox"])
                param_normal_value = st.text_input("Nilai Normal / Acuan")
                param_reference_text = st.text_area("Instruksi / Teks Referensi")
                param_reference_image = st.file_uploader("Upload Gambar Referensi", type=["png", "jpg", "jpeg"])
                param_config_json = st.text_area("Config JSON", placeholder='Contoh: {"options":["Normal","Abnormal"]}')
                param_is_required = st.checkbox("Wajib Diisi", value=False)
                param_sort_order = st.number_input("Urutan Tampil", min_value=0, value=0, step=1)
                selected_package_names = st.multiselect("Masukkan ke Paket", list(package_options.keys()), default=list(package_options.keys()))
                submit_parameter = st.form_submit_button("Simpan Parameter")
            if submit_parameter:
                if not param_name.strip():
                    st.error("Nama parameter wajib diisi.")
                elif not selected_package_names:
                    st.error("Minimal pilih 1 paket.")
                else:
                    try:
                        reference_image_path = save_reference_image(param_reference_image)
                        selected_package_ids = [package_options[name] for name in selected_package_names]
                        create_parameter(param_name.strip(), param_category.strip(), post_options[param_post_name], param_unit.strip(), param_input_type,
                                         param_normal_value.strip(), param_reference_text.strip(), reference_image_path, param_config_json.strip(),
                                         param_is_required, int(param_sort_order), selected_package_ids, param_program)
                        st.success("Parameter berhasil ditambahkan.")
                    except Exception as e:
                        st.error(f"Gagal tambah parameter: {e}")

    with tab_source:
        st.subheader("Daftar Database Instansi")

        sources = get_participant_sources(program_type=data_scope)
        sources_df = pd.DataFrame(sources)

        if sources_df.empty:
            st.info("Belum ada database instansi.")
        else:
            st.dataframe(sources_df, use_container_width=True)

        st.divider()

        st.subheader("Cleansing / Hapus Database Instansi")
        st.warning(
            "Fitur ini akan menghapus database instansi terpilih beserta peserta, hasil pemeriksaan, audit log terkait, "
            "dan file QR barcode jika opsi hapus file QR diaktifkan. Aksi ini tidak bisa dibatalkan."
        )

        if not sources:
            st.info("Tidak ada database instansi yang bisa dihapus.")
        else:
            source_options = {}

            for source in sources:
                label = (
                    f"{source.get('name') or '-'} - "
                    f"{source.get('institution_name') or '-'} | "
                    f"Source ID: {source.get('id')}"
                )
                source_options[label] = source

            st.markdown("### QR Barcode Database")
            st.caption(
                "File QR disimpan di folder: uploads/barcodes. "
                "Kalau File QR masih 0, klik tombol Generate / Refresh QR di bawah ini."
            )

            qr_source_label = st.selectbox(
                "Pilih Database untuk Generate / Cek QR",
                list(source_options.keys()),
                key="qr_source_select"
            )

            qr_source = source_options[qr_source_label]
            qr_source_id = qr_source["id"]
            qr_stats = get_participant_source_stats(qr_source_id)

            if qr_stats:
                qr_col1, qr_col2, qr_col3 = st.columns(3)

                with qr_col1:
                    st.metric("Peserta", qr_stats["participant_count"])

                with qr_col2:
                    st.metric("Barcode Value", qr_stats.get("barcode_value_count", 0))

                with qr_col3:
                    st.metric("File QR", qr_stats["barcode_count"])

            if not QR_AVAILABLE:
                st.warning(
                    "Library QR belum terinstall. Jalankan di CMD: pip install qrcode[pil] pillow"
                )

            if st.button("Generate / Refresh File QR untuk Database Ini"):
                if not QR_AVAILABLE:
                    st.error("QR belum bisa dibuat. Install dulu: pip install qrcode[pil] pillow")
                else:
                    total_qr_files = ensure_barcodes_for_source(qr_source_id)
                    st.success(
                        f"QR berhasil dibuat/direfresh untuk {total_qr_files} peserta. "
                        "File tersimpan di folder uploads/barcodes."
                    )
                    st.info("Kalau angka File QR belum berubah, klik menu lain lalu kembali ke Database Instansi.")

            st.divider()

            with st.form("delete_participant_source_form"):
                selected_source_label = st.selectbox(
                    "Pilih Database Instansi yang Akan Dihapus",
                    list(source_options.keys())
                )

                selected_source = source_options[selected_source_label]
                selected_source_id = selected_source["id"]
                selected_source_name = selected_source.get("name") or ""

                stats = get_participant_source_stats(selected_source_id)

                if stats:
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.metric("Peserta", stats["participant_count"])

                    with col2:
                        st.metric("Barcode Value", stats.get("barcode_value_count", 0))

                    with col3:
                        st.metric("File QR", stats["barcode_count"])

                    with col4:
                        st.metric("Hasil Pemeriksaan", stats["result_count"])

                    with col5:
                        st.metric("Audit Log", stats["audit_count"])

                st.caption(
                    f"Database yang akan dihapus: {selected_source_name}. "
                    "Untuk konfirmasi, ketik HAPUS di bawah ini."
                )

                confirmation = st.text_input(
                    "Ketik HAPUS untuk konfirmasi",
                    placeholder="HAPUS"
                )

                delete_qr_files = st.checkbox(
                    "Hapus file QR barcode dari folder uploads/barcodes",
                    value=True
                )

                delete_clicked = st.form_submit_button(
                    "Hapus Database Instansi"
                )

            if delete_clicked:
                if confirmation.strip().upper() != "HAPUS":
                    st.error(
                        "Konfirmasi salah. Ketik HAPUS untuk melanjutkan penghapusan database."
                    )
                else:
                    try:
                        delete_stats = delete_participant_source_database(
                            source_id=selected_source_id,
                            delete_barcode_files=delete_qr_files
                        )

                        st.session_state.selected_participant = None
                        st.session_state.search_results = []

                        st.success(
                            f"Database berhasil dihapus: {delete_stats['source_name']}"
                        )
                        st.json(delete_stats)

                        st.info("Refresh halaman atau pindah menu untuk melihat daftar terbaru.")

                    except Exception as e:
                        st.error(f"Gagal hapus database instansi: {e}")

    with tab_list:
        st.subheader("Daftar Perusahaan")
        st.dataframe(pd.DataFrame(get_companies()), use_container_width=True)
        st.divider()
        st.subheader("Daftar Paket")
        st.dataframe(pd.DataFrame(get_packages(program_type=data_scope)), use_container_width=True)
        st.divider()
        st.subheader("Daftar Post")
        st.dataframe(pd.DataFrame(get_posts(program_type=data_scope, include_admin=True)), use_container_width=True)
        st.divider()
        st.subheader("Daftar User")
        st.dataframe(pd.DataFrame(get_users_admin(program_type=data_scope)), use_container_width=True)
        st.divider()
        st.subheader("Daftar Parameter")
        st.dataframe(pd.DataFrame(get_parameters_admin(program_type=data_scope)), use_container_width=True)
        st.divider()
        st.subheader("Daftar Peserta")
        st.dataframe(pd.DataFrame(get_participants_admin(program_type=data_scope)), use_container_width=True)


# =========================
# REGISTRATION AND INPUT
# =========================

if menu == "Registrasi Corporate":
    render_hero("Registrasi Peserta MCU Corporate", "Daftarkan peserta baru untuk pemeriksaan corporate.", "Registration")
    companies = get_companies()
    packages = get_packages(program_type=PROGRAM_CORPORATE)
    if not companies:
        st.error("Belum ada data perusahaan.")
        st.stop()
    if not packages:
        st.error("Belum ada data paket MCU Corporate.")
        st.stop()
    company_options = {company["name"]: company["id"] for company in companies}
    package_options = {package["name"]: package["id"] for package in packages}
    default_mcu_id = generate_mcu_id(PROGRAM_CORPORATE)
    with st.form("registration_form"):
        st.subheader("Data Peserta")
        mcu_id = st.text_input("ID Internal Sistem", value=default_mcu_id)
        external_id = st.text_input("Nomor ID Instansi", placeholder="Opsional")
        name = st.text_input("Nama Peserta")
        nik = st.text_input("NIK")
        gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
        birth_date = st.date_input("Tanggal Lahir")
        company_name = st.selectbox("Perusahaan", list(company_options.keys()))
        package_name = st.selectbox("Paket MCU", list(package_options.keys()))
        mcu_date = st.date_input("Tanggal MCU", value=date.today())
        submit_clicked = st.form_submit_button("Simpan Peserta")
    if submit_clicked:
        if not mcu_id.strip() or not name.strip():
            st.error("ID internal dan nama peserta wajib diisi.")
        else:
            try:
                create_participant(mcu_id.strip(), external_id.strip(), name.strip(), nik.strip(), gender, str(birth_date),
                                   company_options[company_name], package_options[package_name], str(mcu_date), PROGRAM_CORPORATE)
                st.success(f"Peserta berhasil didaftarkan: {name}")
                st.info(f"ID Internal: {mcu_id}")
            except Exception as e:
                st.error(f"Gagal menyimpan peserta: {e}")

if menu == "Input MCU Corporate":
    render_hero("Input Pemeriksaan MCU Corporate", "Cari peserta corporate dan input hasil pemeriksaan sesuai post.", "Corporate MCU")
    render_search_and_input(PROGRAM_CORPORATE, allow_post_choice=user["role"] in ["admin", "supervisor"])

if menu == "Input CAPASKA":
    render_hero("Input Pemeriksaan CAPASKA / BPIP", "Pilih database instansi, cari peserta, lalu input parameter sesuai post.", "Operator Mode")
    render_simple_steps(
        "Langkah Operator",
        [
            "Pilih database instansi.",
            "Scan barcode atau ketik nama peserta.",
            "Pilih peserta yang benar.",
            "Isi pemeriksaan sesuai post, lalu simpan."
        ]
    )
    render_search_and_input(PROGRAM_CAPASKA, allow_post_choice=user["role"] in ["admin", "supervisor"])


# =========================
# SUBMISSION SAYA
# =========================

if menu == "Submission Saya":
    render_hero("Submission Saya", "Lihat, cari, edit, dan audit hasil input pemeriksaan milik akun ini.", "My Work")
    active_program = PROGRAM_CAPASKA if user_program == PROGRAM_CAPASKA else PROGRAM_CORPORATE if user_program == PROGRAM_CORPORATE else None
    st.subheader("Cari Submission")
    search_keyword = st.text_input("Ketik minimal 3 huruf nama peserta / ID instansi / ID internal", placeholder="Contoh: chel, CHELSEA, CAPASKA-2025-0075")
    selected_suggestion_keyword = search_keyword
    if len(search_keyword.strip()) >= 3:
        suggestions = search_my_submission_participants(user["id"], active_program, search_keyword.strip(), 10)
        if suggestions:
            suggestion_options = {}
            for item in suggestions:
                label = f"{item.get('participant_name') or '-'} | ID Instansi: {item.get('external_id') or '-'} | ID Internal: {item.get('mcu_id') or '-'} | Post: {item.get('post_name') or '-'}"
                suggestion_options[label] = item
            selected_label = st.selectbox("Rekomendasi Peserta", list(suggestion_options.keys()))
            selected_item = suggestion_options[selected_label]
            selected_suggestion_keyword = selected_item.get("participant_name") or search_keyword
        else:
            st.caption("Belum ada rekomendasi peserta untuk keyword ini.")

    col_status, col_limit, col_refresh = st.columns([1, 1, 1])
    with col_status:
        status_filter = st.selectbox("Status", ["Semua", "CREATE", "UPDATE"])
    with col_limit:
        limit_data = st.selectbox("Limit Data", [100, 300, 500, 1000], index=3)
    with col_refresh:
        st.write("")
        st.write("")
        if st.button("Refresh Tabel", use_container_width=True):
            st.session_state.submission_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()
    if st.session_state.submission_refresh_at:
        st.caption(f"Terakhir refresh: {st.session_state.submission_refresh_at}")

    detail_rows = get_my_submission_detail_rows(user["id"], active_program, selected_suggestion_keyword, limit_data)
    if not detail_rows:
        st.info("Belum ada submission yang cocok.")
    else:
        raw_df = pd.DataFrame(detail_rows)
        display_df = raw_df.rename(columns={
            "participant_id": "Participant ID", "parameter_id": "Parameter ID", "waktu": "Waktu", "status_input": "Status",
            "participant_name": "Nama Peserta", "external_id": "ID Instansi", "province": "Provinsi", "nik": "NIK",
            "mcu_id": "ID Internal", "program_type": "Program", "company_name": "Instansi/Perusahaan",
            "package_name": "Paket", "post_name": "Post", "parameter_name": "Parameter",
            "parameter_category": "Kategori", "value": "Nilai", "input_by": "Input Oleh", "updated_by": "Update Oleh",
        })
        if status_filter != "Semua":
            display_df = display_df[display_df["Status"].astype(str) == status_filter]
        for col in display_df.columns:
            display_df[col] = display_df[col].apply(display_value)
        st.caption(f"Total data ditemukan: {len(display_df)} baris input")
        if display_df.empty:
            st.warning("Tidak ada submission yang cocok dengan filter.")
        else:
            tab_summary, tab_edit, tab_history = st.tabs(["Tampilan Horizontal", "Edit Parameter", "History Edit"])
            with tab_summary:
                title_col, refresh_col = st.columns([3, 1])
                with title_col:
                    st.subheader("Ringkasan Submission")
                with refresh_col:
                    if st.button("Refresh Ringkasan", use_container_width=True):
                        st.session_state.submission_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.rerun()
                index_columns = ["Nama Peserta", "ID Instansi", "NIK", "ID Internal", "Provinsi", "Program", "Instansi/Perusahaan", "Paket", "Post"]
                existing_index_columns = [col for col in index_columns if col in display_df.columns]
                summary_df = display_df.copy()
                summary_df["Parameter"] = summary_df["Parameter"].astype(str)
                summary_df["Nilai"] = summary_df["Nilai"].astype(str)
                pivot_df = summary_df.pivot_table(index=existing_index_columns, columns="Parameter", values="Nilai", aggfunc="last").reset_index()
                pivot_df.columns.name = None
                for col in pivot_df.columns:
                    pivot_df[col] = pivot_df[col].apply(display_value)
                pivot_df = reorder_summary_columns_with_final_score(pivot_df)
                st.dataframe(pivot_df, use_container_width=True, height=500)
                st.download_button("Download Tampilan Horizontal CSV", pivot_df.to_csv(index=False).encode("utf-8"),
                                   file_name=f"submission_horizontal_{user['username']}.csv", mime="text/csv")
            with tab_edit:
                st.subheader("Edit Parameter")
                st.info("Edit dilakukan pada jawaban pemeriksaan, bukan pada field Value atau Score. Value dan Total Score dihitung ulang otomatis oleh form CAPASKA.")
                editable_source_df = display_df.copy()
                editable_source_df = editable_source_df[~editable_source_df["Parameter"].apply(is_computed_capaska_parameter)]
                editable_columns = ["Participant ID", "Parameter ID", "Waktu", "Status", "Nama Peserta", "ID Instansi", "ID Internal", "Post", "Parameter", "Nilai", "Input Oleh", "Update Oleh"]
                editable_columns = [col for col in editable_columns if col in editable_source_df.columns]
                if editable_source_df.empty:
                    st.warning("Tidak ada parameter jawaban yang bisa diedit. Field Value dan Score tidak diedit manual.")
                else:
                    edit_df = editable_source_df[editable_columns].copy()
                    edit_df.insert(0, "Edit", False)
                    edited_df = st.data_editor(edit_df, use_container_width=True, height=350, hide_index=True,
                                               column_config={"Edit": st.column_config.CheckboxColumn("Edit"), "Participant ID": None, "Parameter ID": None},
                                               disabled=[col for col in edit_df.columns if col != "Edit"], key="submission_edit_table")
                    selected_rows = edited_df[edited_df["Edit"] == True]
                    if len(selected_rows) > 1:
                        st.warning("Pilih hanya 1 parameter untuk diedit.")
                    elif len(selected_rows) == 1:
                        selected_row = selected_rows.iloc[0]
                        participant_detail = get_participant_by_id(int(selected_row["Participant ID"]))
                        if not participant_detail:
                            st.error("Data peserta tidak ditemukan.")
                        else:
                            st.divider()
                            st.write(f"**Peserta:** {display_value(selected_row['Nama Peserta'])}")
                            st.write(f"**Post:** {display_value(selected_row['Post'])}")
                            st.write(f"**Parameter dipilih:** {display_value(selected_row['Parameter'])}")
                            st.write(f"**Jawaban saat ini:** {display_value(selected_row['Nilai'])}")
                            custom_rendered = render_capaska_form(participant_detail, user, user["post_id"], user["post_name"])
                            if not custom_rendered:
                                st.error("Form khusus CAPASKA untuk post ini belum tersedia.")
                    else:
                        st.info("Centang kolom Edit pada parameter jawaban yang ingin diubah.")
            with tab_history:
                st.subheader("History Before / After Edit")
                history_pick_df = build_history_picker_df(display_df)
                if history_pick_df.empty:
                    st.info("Belum ada history untuk ditampilkan.")
                else:
                    history_pick_df.insert(0, "Lihat History", False)
                    selected_history_df = st.data_editor(history_pick_df, use_container_width=True, height=420, hide_index=True,
                                                         column_config={"Lihat History": st.column_config.CheckboxColumn("History"), "Participant ID": None, "Parameter ID": None},
                                                         disabled=[col for col in history_pick_df.columns if col != "Lihat History"], key="submission_history_table")
                    selected_history_rows = selected_history_df[selected_history_df["Lihat History"] == True]
                    if len(selected_history_rows) > 1:
                        st.warning("Pilih hanya 1 parameter untuk melihat history lengkap.")
                    elif len(selected_history_rows) == 1:
                        selected_history = selected_history_rows.iloc[0]
                        history = get_result_history(int(selected_history["Participant ID"]), int(selected_history["Parameter ID"]), limit=50)
                        st.divider()
                        st.write(f"**Peserta:** {display_value(selected_history['Nama Peserta'])}")
                        st.write(f"**Post:** {display_value(selected_history['Post'])}")
                        st.write(f"**Parameter:** {display_value(selected_history['Parameter'])}")
                        st.write(f"**Nilai Saat Ini:** {display_value(selected_history['Nilai Saat Ini'])}")
                        if not history:
                            st.info("Belum ada history detail untuk parameter ini.")
                        else:
                            history_df = pd.DataFrame(history).rename(columns={
                                "timestamp": "Waktu", "action": "Action", "user_name": "User", "participant_name": "Nama Peserta",
                                "parameter_name": "Parameter", "old_value": "Before Edit", "new_value": "After Edit",
                            })
                            display_columns = [col for col in ["Waktu", "Action", "User", "Nama Peserta", "Parameter", "Before Edit", "After Edit"] if col in history_df.columns]
                            history_df = history_df[display_columns].copy()
                            for col in history_df.columns:
                                history_df[col] = history_df[col].apply(display_value)
                            st.dataframe(history_df, use_container_width=True, height=350)
                            st.download_button("Download History CSV", history_df.to_csv(index=False).encode("utf-8"), file_name=f"history_edit_{user['username']}.csv", mime="text/csv")
                    else:
                        st.info("Centang 1 parameter untuk melihat history lengkap.")


# =========================
# IMPORT CAPASKA
# =========================

if menu == "Import CAPASKA":
    render_hero("Import Excel CAPASKA - BPIP", "Import database peserta instansi atau hasil pemeriksaan CAPASKA.", "Admin Import")
    tab_import_result, tab_import_database = st.tabs(["Import Hasil Pemeriksaan CAPASKA", "Import Database Peserta Instansi"])
    with tab_import_result:
        st.info("Upload file Excel CAPASKA hasil pemeriksaan.")
        with st.form("import_capaska_form"):
            uploaded_file = st.file_uploader("Upload Excel CAPASKA", type=["xlsx"], key="capaska_result_upload")
            import_clicked = st.form_submit_button("Import ke Database")
        if import_clicked:
            if uploaded_file is None:
                st.error("Pilih file Excel terlebih dahulu.")
            else:
                try:
                    with st.spinner("Sedang import data CAPASKA..."):
                        stats = import_capaska_excel(uploaded_file=uploaded_file, user_id=user["id"])
                    ensure_runtime_schema()
                    st.success("Import CAPASKA selesai.")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Rows Dibaca", stats["rows_read"])
                    col1.metric("Rows Diimport", stats["rows_imported"])
                    col2.metric("Peserta Baru", stats["participants_created"])
                    col2.metric("Parameter Baru", stats["parameters_created"])
                    col3.metric("Hasil Baru", stats["results_created"])
                    col3.metric("Hasil Diupdate", stats["results_updated"])
                    st.json(stats)
                except Exception as e:
                    st.error(f"Gagal import CAPASKA: {e}")
    with tab_import_database:
        st.subheader("Import Database Peserta Instansi")

        st.info(
            "Ini untuk import master peserta dari instansi. "
            "Database yang dibuat di sini akan muncul di dropdown operator: Pilih Database Instansi. "
            "Minimal wajib ada kolom nama peserta."
        )

        template_df = pd.DataFrame([
            {
                "Nama Peserta": "Contoh Peserta",
                "ID Instansi": "OPSIONAL-001",
                "NIK": "",
                "Jenis Kelamin": "Putra",
                "Provinsi": "Bali",
                "Tanggal Layanan": str(date.today()),
                "Jenis Pemeriksaan": "CAPASKA",
                "Dokter Bertugas": "",
                "Perawat Bertugas": "",
            }
        ])

        st.download_button(
            "Download Template Excel/CSV Database Peserta",
            data=template_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="template_database_peserta_capaska.csv",
            mime="text/csv"
        )

        companies = get_companies()
        packages = get_packages(program_type=PROGRAM_CAPASKA)

        st.info(
            "Import ini fleksibel dan otomatis deteksi header. "
            "Tidak wajib memakai template. Minimal file memiliki kolom nama peserta, misalnya: "
            "Nama Peserta, Nama Lengkap, Nama, Peserta, Putra, atau Putri."
        )

        company_options = {
            f"Pakai existing: {company['name']}": company['id']
            for company in companies
        }

        package_options = {
            f"Pakai existing: {package['name']}": package['id']
            for package in packages
        }

        with st.form("import_instansi_database_form"):
            database_name = st.text_input(
                "Nama Database",
                placeholder="Contoh: CAPASKA BPIP 26 Juni 2025"
            )

            institution_name = st.text_input(
                "Nama Instansi / Database Source",
                value="BPIP / CAPASKA",
                help="Nama ini akan muncul di dropdown operator: Pilih Database Instansi."
            )

            st.markdown("#### Mapping Database")

            if company_options:
                selected_company_label = st.selectbox(
                    "Instansi / Perusahaan Tujuan",
                    ["Buat otomatis dari nama instansi"] + list(company_options.keys()),
                    index=0,
                    help="Pilih existing jika sudah ada, atau biarkan otomatis agar sistem membuat master data."
                )
            else:
                selected_company_label = "Buat otomatis dari nama instansi"
                st.caption("Belum ada master perusahaan. Sistem akan membuat otomatis dari Nama Instansi.")

            company_name_for_create = st.text_input(
                "Nama Perusahaan/Instansi jika dibuat otomatis",
                value="BPIP / CAPASKA"
            )

            if package_options:
                selected_package_label = st.selectbox(
                    "Paket Pemeriksaan",
                    ["Buat otomatis dari nama paket"] + list(package_options.keys()),
                    index=0,
                    help="Pilih existing jika sudah ada, atau biarkan otomatis agar sistem membuat paket."
                )
            else:
                selected_package_label = "Buat otomatis dari nama paket"
                st.caption("Belum ada master paket CAPASKA. Sistem akan membuat otomatis.")

            package_name_for_create = st.text_input(
                "Nama Paket jika dibuat otomatis",
                value="CAPASKA 2025/2026"
            )

            description = st.text_area(
                "Catatan Database",
                placeholder="Opsional. Contoh: database peserta sesi pemeriksaan tanggal 26 Juni 2025"
            )

            uploaded_database_file = st.file_uploader(
                "Upload Excel Database Peserta Instansi",
                type=["xlsx", "xls"],
                key="instansi_database_upload",
                help="Template tidak wajib. Sistem akan auto-detect header dari file Excel."
            )

            import_database_clicked = st.form_submit_button(
                "Import Database Peserta"
            )

        if import_database_clicked:
            if not database_name.strip():
                st.error("Nama Database wajib diisi.")
            elif uploaded_database_file is None:
                st.error("Upload file Excel terlebih dahulu.")
            else:
                try:
                    with st.spinner("Menyiapkan master data dan import database peserta..."):
                        if selected_company_label.startswith("Pakai existing:"):
                            company_id = company_options[selected_company_label]
                        else:
                            company_id = get_or_create_company_id(
                                company_name_for_create.strip() or institution_name.strip() or "BPIP / CAPASKA"
                            )

                        if selected_package_label.startswith("Pakai existing:"):
                            package_id = package_options[selected_package_label]
                        else:
                            package_id = get_or_create_package_id(
                                package_name_for_create.strip() or "CAPASKA 2025/2026",
                                company_id=company_id,
                                program_type=PROGRAM_CAPASKA
                            )

                        stats = import_instansi_excel(
                            uploaded_file=uploaded_database_file,
                            database_name=database_name.strip(),
                            institution_name=institution_name.strip() or company_name_for_create.strip() or "BPIP / CAPASKA",
                            package_id=package_id,
                            company_id=company_id,
                            description=description.strip()
                        )

                    ensure_runtime_schema()

                    if stats.get("participants_created", 0) == 0 and stats.get("participants_updated", 0) == 0:
                        st.warning(
                            f"Database dibuat: {database_name.strip()}, tetapi belum ada peserta yang berhasil diimport. "
                            "Cek detail detected_columns untuk melihat kolom nama yang terbaca."
                        )
                    else:
                        st.success(
                            f"Database peserta berhasil dibuat: {database_name.strip()}"
                        )

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Source ID", stats.get("source_id", "-"))
                        st.metric("Rows Dibaca", stats.get("rows_read", 0))

                    with col2:
                        st.metric("Peserta Baru", stats.get("participants_created", 0))
                        st.metric("Peserta Update", stats.get("participants_updated", 0))

                    with col3:
                        st.metric("Peserta Skip", stats.get("participants_skipped", 0))

                    with st.expander("Detail hasil import / detected columns", expanded=False):
                        st.json(stats)

                    st.info(
                        "Sekarang operator bisa buka menu Input CAPASKA, lalu pilih database ini di field Pilih Database Instansi."
                    )

                except Exception as e:
                    st.error("Gagal import database peserta instansi.")
                    st.warning(
                        "Format minimal wajib memiliki kolom nama peserta. "
                        "Contoh header yang didukung: Nama Peserta, Nama Lengkap, Nama, Peserta, Putra, atau Putri. "
                        "Kolom lain seperti Jenis Kelamin, Provinsi, Tanggal Layanan, Dokter, dan Perawat bersifat opsional."
                    )
                    st.exception(e)


def count_export_participants(company_id=None, package_id=None, program_type=None, source_id=None, mcu_date_from=None, mcu_date_to=None):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = ["1 = 1"]
    params = []

    if company_id:
        where_clauses.append("participants.company_id = ?")
        params.append(company_id)

    if package_id:
        where_clauses.append("participants.package_id = ?")
        params.append(package_id)

    if source_id:
        where_clauses.append("participants.source_id = ?")
        params.append(source_id)

    if program_type in [PROGRAM_CORPORATE, PROGRAM_CAPASKA]:
        where_clauses.append("participants.program_type = ?")
        params.append(program_type)

    if mcu_date_from:
        where_clauses.append("participants.mcu_date >= ?")
        params.append(mcu_date_from)

    if mcu_date_to:
        where_clauses.append("participants.mcu_date <= ?")
        params.append(mcu_date_to)

    where_sql = " AND ".join(where_clauses)

    cur.execute(f"""
    SELECT COUNT(DISTINCT participants.id) AS total
    FROM participants
    WHERE {where_sql}
    """, params)

    row = cur.fetchone()
    conn.close()

    return row["total"] if row else 0


# =========================
# EXPORT EXCEL
# =========================


if menu == "Review Hasil":
    render_hero(
        "Review Hasil Pemeriksaan",
        "Dokter atau supervisor dapat melihat progress, hasil semua post, score, dan menyimpan catatan review.",
        "Review"
    )

    current_user = st.session_state.user
    current_program = get_user_program(current_user)

    if current_user["role"] == "admin":
        review_program_label = st.selectbox(
            "Program Review",
            ["CAPASKA / BPIP", "MCU Corporate"],
            key="review_program_label"
        )
        review_program = PROGRAM_CAPASKA if review_program_label == "CAPASKA / BPIP" else PROGRAM_CORPORATE
    elif current_program in [PROGRAM_CAPASKA, PROGRAM_CORPORATE]:
        review_program = current_program
    else:
        review_program = PROGRAM_CAPASKA

    sources = get_participant_sources(program_type=review_program)

    source_options = {"Semua Database Instansi": None}

    for source in sources:
        label = f"{source.get('name') or '-'} - {source.get('institution_name') or '-'} | Source ID: {source.get('id')}"
        source_options[label] = source["id"]

    selected_review_source_label = st.selectbox(
        "Pilih Database Instansi",
        list(source_options.keys()),
        key="review_source_select"
    )

    selected_review_source_id = source_options[selected_review_source_label]

    review_keyword = st.text_input(
        "Cari Nama / ID Internal / ID Instansi / Barcode",
        placeholder="Ketik minimal 2 karakter atau scan barcode",
        key="review_keyword"
    )

    participants = []

    if review_keyword.strip() and len(review_keyword.strip()) < 2:
        st.warning("Ketik minimal 2 karakter untuk mencari peserta.")
    else:
        participants = search_participants(
            keyword=review_keyword.strip(),
            program_type=review_program,
            source_id=selected_review_source_id,
            limit=100
        )

    if "review_selected_participant_id" in st.session_state:
        preselected_id = st.session_state.review_selected_participant_id
    else:
        preselected_id = None

    if participants:
        options = {}

        for participant in participants:
            label = (
                f"{participant.get('name') or '-'} | "
                f"ID: {participant.get('mcu_id') or '-'} | "
                f"Provinsi: {participant.get('province') or '-'} | "
                f"Database: {participant.get('source_name') or '-'}"
            )
            options[label] = participant["id"]

        default_index = 0

        if preselected_id:
            for idx, label in enumerate(options.keys()):
                if options[label] == preselected_id:
                    default_index = idx
                    break

        selected_review_label = st.selectbox(
            "Pilih Peserta untuk Review",
            list(options.keys()),
            index=default_index,
            key="review_participant_select"
        )

        selected_participant_id = options[selected_review_label]
        st.session_state.review_selected_participant_id = selected_participant_id
        participant = get_participant_by_id(selected_participant_id)

        if participant:
            render_review_detail(participant)

    elif preselected_id:
        participant = get_participant_by_id(preselected_id)

        if participant:
            st.info("Menampilkan peserta dari pilihan dashboard.")
            render_review_detail(participant)
        else:
            st.warning("Peserta yang dipilih tidak ditemukan.")

    else:
        st.info("Cari peserta atau scan barcode untuk mulai review hasil.")



if menu == "Cetak Label Barcode":
    render_hero(
        "Cetak Label Barcode",
        "Generate PDF label barcode untuk thermal Xprinter 3 cm x 5 cm atau mode landscape/A4.",
        "Label Print"
    )

    render_simple_steps(
        "Cara Cetak Label",
        [
            "Pilih database instansi.",
            "Ketik minimal 2 huruf nama peserta, lalu pilih nama yang ingin dicetak.",
            "Atur jumlah stiker per peserta, biasanya 5 sampai 8.",
            "Klik Generate PDF, download, lalu print ke Xprinter. Untuk stiker die-cut Xprinter, gunakan mode STABIL 30mm x 50mm. Mode ini tidak dipendekkan agar tidak berantakan."
        ]
    )

    if not REPORTLAB_AVAILABLE:
        st.warning("Library PDF belum terinstall. Jalankan di CMD: pip install reportlab")

    if not QR_AVAILABLE:
        st.warning("Library QR belum terinstall. Jalankan di CMD: pip install qrcode[pil] pillow")

    current_user = st.session_state.user
    current_program = get_user_program(current_user)

    if current_user["role"] == "admin":
        label_program_label = st.selectbox(
            "Program Label",
            ["CAPASKA / BPIP", "MCU Corporate"],
            key="label_program_label"
        )
        label_program = PROGRAM_CAPASKA if label_program_label == "CAPASKA / BPIP" else PROGRAM_CORPORATE
    else:
        label_program = current_program

    sources = get_participant_sources(program_type=label_program)

    source_options = {"Semua Database Instansi": None}

    for source in sources:
        label = f"{source.get('name') or '-'} - {source.get('institution_name') or '-'} | Source ID: {source.get('id')}"
        source_options[label] = source["id"]

    with st.container(border=True):
        st.subheader("Filter Peserta")

        selected_source_label = st.selectbox(
            "Database Instansi",
            list(source_options.keys()),
            help="Pilih database tertentu supaya label tidak tercampur.",
            key="label_source_select"
        )

        keyword = st.text_input(
            "Cari Peserta / ID Internal / Barcode",
            placeholder="Ketik minimal 2 karakter, contoh: chel / CAPASKA-2026-0001",
            key="label_keyword_live"
        )

        st.caption(
            "Pencarian otomatis berjalan saat keyword berubah. "
            "Kosongkan keyword untuk menampilkan semua peserta pada database terpilih."
        )

        st.subheader("Opsi Label")

        col1, col2, col3 = st.columns(3)

        with col1:
            copies_per_participant = st.number_input(
                "Jumlah Stiker per Peserta",
                min_value=1,
                max_value=12,
                value=6,
                step=1,
                help="Untuk kebutuhan kamu biasanya 5 sampai 8.",
                key="label_copies_per_participant"
            )

        with col2:
            show_institution = st.checkbox(
                "Tampilkan Instansi",
                value=True,
                key="label_show_institution"
            )

        with col3:
            show_date = st.checkbox(
                "Tampilkan Tanggal MCU",
                value=False,
                key="label_show_date"
            )

        print_mode_label = st.selectbox(
            "Mode Print",
            [
                "Thermal Xprinter 4x3 cm - Landscape 40mm x 30mm",
                "Thermal Xprinter STABIL - 30mm x 50mm (Anti kebalik)",
                "Thermal Xprinter Compact - Fit Konten 30mm x 17mm (opsional)",
                "Thermal Xprinter 5x3 cm - Landscape 50mm x 30mm",
                "A4 Sticker Sheet 5x3 cm - 4 kolom x 9 baris"
            ],
            index=0,
            help="Pilih ukuran sesuai stiker fisik. Untuk stiker lebar 4cm tinggi 3cm, gunakan mode 40mm x 30mm.",
            key="label_print_mode"
        )

        show_border = st.checkbox(
            "Tampilkan garis batas label",
            value=False,
            help="Untuk thermal Xprinter biasanya matikan border. Aktifkan hanya untuk test alignment.",
            key="label_show_border"
        )

    selected_source_id = source_options.get(selected_source_label)

    # AUTO RETRIEVE:
    # Karena filter tidak lagi berada di dalam st.form, daftar peserta langsung
    # diperbarui saat database/keyword/opsi berubah.
    # Untuk mencegah beban query terlalu besar, keyword 1 karakter tidak dipakai.
    active_keyword = keyword.strip()

    if active_keyword and len(active_keyword) < 2:
        preview_participants = []
        st.warning("Ketik minimal 2 karakter untuk mulai mencari peserta.")
    else:
        preview_participants = get_label_print_participants(
            source_id=selected_source_id,
            program_type=label_program,
            keyword=active_keyword,
            limit=5000
        )

    if print_mode_label.startswith("Thermal Xprinter 4x3"):
        selected_print_mode = "thermal_xprinter_40x30"
    elif print_mode_label.startswith("Thermal Xprinter STABIL") or print_mode_label.startswith("Thermal Xprinter 3x5"):
        selected_print_mode = "thermal_xprinter_30x50"
    elif print_mode_label.startswith("Thermal Xprinter Compact"):
        selected_print_mode = "thermal_xprinter_compact_30x17"
    elif print_mode_label.startswith("Thermal Xprinter 5x3"):
        selected_print_mode = "thermal_xprinter_50x30"
    else:
        selected_print_mode = "a4_sheet_50x30"

    if selected_print_mode == "thermal_xprinter_40x30":
        layout_info = "Mode Xprinter: 1 halaman PDF = 1 stiker fisik ukuran 40mm x 30mm"
    elif selected_print_mode == "thermal_xprinter_compact_30x17":
        layout_info = "Mode Compact: 1 halaman PDF = 1 label fit konten ukuran 30mm x 17mm"
    elif selected_print_mode == "thermal_xprinter_30x50":
        layout_info = "Mode Xprinter stabil: 1 halaman PDF = 1 stiker fisik ukuran 30mm x 50mm"
    elif selected_print_mode == "thermal_xprinter_50x30":
        layout_info = "Mode Thermal Xprinter: 1 halaman PDF = 1 label ukuran 50mm x 30mm"
    else:
        layout_info = "Mode A4: 4 kolom x 9 baris = 36 label/halaman"

    st.info(
        f"Ukuran label: sesuai mode print | {layout_info} | "
        f"Jumlah peserta sesuai filter: {len(preview_participants)}"
    )

    selected_participants = []

    if preview_participants:
        st.subheader("Pilih Nama Peserta yang Akan Dicetak")

        print_all = st.checkbox(
            "Cetak semua peserta sesuai filter",
            value=False,
            help="Matikan checkbox ini untuk memilih nama tertentu saja.",
            key="label_print_all"
        )

        participant_options = {}

        for participant in preview_participants:
            label = (
                f"{participant.get('name') or '-'} | "
                f"ID: {participant.get('mcu_id') or '-'} | "
                f"Provinsi: {participant.get('province') or '-'} | "
                f"Barcode: {participant.get('barcode_value') or '-'}"
            )
            participant_options[label] = participant

        if print_all:
            selected_participants = preview_participants
            st.success(f"Mode cetak semua aktif: {len(selected_participants)} peserta akan dicetak.")
        else:
            selected_labels = st.multiselect(
                "Pilih satu atau beberapa nama peserta",
                list(participant_options.keys()),
                placeholder="Ketik nama peserta lalu pilih dari daftar",
                help="Admin bisa memilih nama tertentu saja, tidak harus semua peserta.",
                key=f"label_selected_names_{selected_source_id}_{active_keyword}"
            )

            selected_participants = [
                participant_options[label]
                for label in selected_labels
            ]

            st.caption(f"Peserta terpilih: {len(selected_participants)} dari {len(preview_participants)} peserta sesuai filter.")

        preview_df = pd.DataFrame(preview_participants)[[
            "name",
            "mcu_id",
            "external_id",
            "province",
            "source_name",
            "barcode_value",
        ]].head(100)

        preview_df = preview_df.rename(columns={
            "name": "Nama Peserta",
            "mcu_id": "ID Internal",
            "external_id": "ID Instansi",
            "province": "Provinsi",
            "source_name": "Database Instansi",
            "barcode_value": "Barcode Value",
        })

        for col in preview_df.columns:
            preview_df[col] = preview_df[col].apply(display_value)

        st.dataframe(preview_df, use_container_width=True, height=360)
    else:
        if not active_keyword:
            st.warning("Belum ada peserta pada filter/database ini.")
        elif len(active_keyword) >= 2:
            st.warning("Tidak ada peserta yang cocok dengan keyword tersebut.")

    generate_selected_clicked = st.button(
        "Generate PDF Label Peserta Terpilih",
        use_container_width=True
    )

    if generate_selected_clicked:
        try:
            if not selected_participants:
                st.error("Pilih minimal 1 peserta, atau aktifkan 'Cetak semua peserta sesuai filter'.")
            else:
                for participant in selected_participants:
                    ensure_barcode_for_participant(participant["id"])

                source_title = selected_source_label.split("|")[0].strip() if selected_source_label else "semua_database"

                pdf_path = generate_barcode_label_pdf(
                    participants=selected_participants,
                    copies_per_participant=copies_per_participant,
                    title=f"label_barcode_{source_title}",
                    show_institution=show_institution,
                    show_date=show_date,
                    show_border=show_border,
                    print_mode=selected_print_mode
                )

                total_labels = len(selected_participants) * int(copies_per_participant)

                if selected_print_mode in ["thermal_xprinter_40x30", "thermal_xprinter_compact_30x17", "thermal_xprinter_30x50", "thermal_xprinter_50x30"]:
                    total_pages = total_labels
                    page_note = "1 halaman = 1 label thermal"
                else:
                    total_pages = (total_labels + 35) // 36
                    page_note = "36 label per halaman A4"

                st.success(
                    f"PDF label berhasil dibuat. Total peserta terpilih: {len(selected_participants)} | "
                    f"Total label: {total_labels} | Estimasi halaman: {total_pages} ({page_note})"
                )

                with open(pdf_path, "rb") as file:
                    st.download_button(
                        "Download PDF Label Barcode",
                        file,
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        use_container_width=True
                    )

                if selected_print_mode == "thermal_xprinter_40x30":
                    st.warning(
                        "Ukuran actual stiker: Paper Width 40mm, Paper Height 30mm, Orientation Landscape, "
                        "Scale 100%, Fit to Page OFF, Auto Rotate OFF. Ini sesuai info: lebar 4cm, tinggi 3cm."
                    )
                elif selected_print_mode == "thermal_xprinter_30x50":
                    st.warning(
                        "Mode ini untuk stiker die-cut Xprinter seperti foto: Paper Width 30mm, Height 50mm, "
                        "Orientation Portrait, Scale 100%, Fit to Page OFF, Auto Rotate OFF. "
                        "Konten dipadatkan di atas supaya tidak terpotong/terbalik."
                    )
                elif selected_print_mode == "thermal_xprinter_compact_30x17":
                    st.warning(
                        "Mode compact hanya untuk continuous label atau driver yang tidak auto-rotate. "
                        "Jika hasil print miring/kebalik, kembali ke mode Anti kebalik 30mm x 50mm."
                    )
                elif selected_print_mode == "thermal_xprinter_50x30":
                    st.warning(
                        "Mode alternatif: set Xprinter Paper Width 50mm, Height 30mm, orientation Landscape, "
                        "scale 100% / Actual Size, Fit to Page OFF."
                    )
                else:
                    st.warning(
                        "Saat print A4: pilih Paper A4, Scale 100% / Actual Size, jangan pilih Fit to Page."
                    )

        except Exception as e:
            st.error(f"Gagal membuat PDF label barcode: {e}")



if menu == "Export Excel":
    render_hero("Export Excel Data MCU", "Export hasil pemeriksaan berdasarkan program, paket, database instansi, dan tanggal.", "Excel Export")

    export_program_label = st.selectbox(
        "Program Export",
        ["Semua Program", "MCU Corporate", "CAPASKA / BPIP"],
        key="export_program_label"
    )

    if export_program_label == "MCU Corporate":
        export_program = PROGRAM_CORPORATE
    elif export_program_label == "CAPASKA / BPIP":
        export_program = PROGRAM_CAPASKA
    else:
        export_program = None

    companies = get_companies()
    packages = get_packages(program_type=export_program)

    if export_program == PROGRAM_CORPORATE:
        sources = []
    elif export_program == PROGRAM_CAPASKA:
        sources = get_participant_sources(program_type=PROGRAM_CAPASKA)
    else:
        sources = get_participant_sources(program_type=None)

    company_options = {"Semua Perusahaan / Instansi": None}
    company_options.update({
        company["name"]: company["id"]
        for company in companies
    })

    package_options = {"Semua Paket": None}
    package_options.update({
        package["name"]: package["id"]
        for package in packages
    })

    source_options = {"Semua Database Instansi": None}
    for source in sources:
        label = f"{source.get('name') or '-'} - {source.get('institution_name') or '-'} | Source ID: {source.get('id')}"
        source_options[label] = source["id"]

    with st.form("export_excel_form"):
        st.subheader("Filter Export")

        company_name = st.selectbox(
            "Perusahaan / Instansi",
            list(company_options.keys())
        )

        package_name = st.selectbox(
            "Paket",
            list(package_options.keys())
        )

        selected_source_name = st.selectbox(
            "Database Instansi",
            list(source_options.keys()),
            help="Pilih database peserta tertentu. Jika pilih Semua Database Instansi, export mengambil semua data sesuai filter lain."
        )

        use_date_filter = st.checkbox(
            "Gunakan filter tanggal MCU",
            value=False,
            help="Matikan filter ini kalau ingin export semua tanggal."
        )

        col1, col2 = st.columns(2)

        with col1:
            date_from = st.date_input("Tanggal MCU Dari", value=date.today())

        with col2:
            date_to = st.date_input("Tanggal MCU Sampai", value=date.today())

        export_clicked = st.form_submit_button("Generate Excel")

    selected_source_id = source_options.get(selected_source_name)
    selected_company_id = company_options.get(company_name)
    selected_package_id = package_options.get(package_name)
    selected_date_from = str(date_from) if use_date_filter else None
    selected_date_to = str(date_to) if use_date_filter else None

    st.info(
        f"Filter aktif: Database Instansi = {selected_source_name} | "
        f"Source ID = {selected_source_id if selected_source_id else 'Semua'} | "
        f"Tanggal = {selected_date_from or 'Semua'} s/d {selected_date_to or 'Semua'}"
    )

    preview_total = count_export_participants(
        company_id=selected_company_id,
        package_id=selected_package_id,
        program_type=export_program,
        source_id=selected_source_id,
        mcu_date_from=selected_date_from,
        mcu_date_to=selected_date_to,
    )

    st.caption(f"Preview jumlah peserta sesuai filter: {preview_total}")

    if st.button("Generate / Refresh Barcode untuk Filter Ini"):
        total_barcode = ensure_barcodes_by_filter(
            program_type=export_program,
            source_id=selected_source_id
        )
        st.success(f"Barcode siap untuk {total_barcode} peserta.")

    if export_clicked:
        st.session_state.export_file_path = None

        try:
            if selected_source_id:
                st.warning(
                    f"Export dibatasi hanya untuk Database Instansi terpilih: {selected_source_name}"
                )

            output_path = export_mcu_results_to_excel(
                company_id=selected_company_id,
                package_id=selected_package_id,
                program_type=export_program,
                source_id=selected_source_id,
                mcu_date_from=selected_date_from,
                mcu_date_to=selected_date_to,
            )

            st.session_state.export_file_path = str(output_path)
            st.session_state.export_filter_label = selected_source_name
            st.session_state.export_source_id = selected_source_id

            st.success("File Excel berhasil dibuat.")

        except Exception as e:
            st.error(f"Gagal export Excel: {e}")

    if st.session_state.export_file_path:
        export_file_path = Path(st.session_state.export_file_path)

        if export_file_path.exists():
            st.caption(
                f"File siap download untuk filter: {st.session_state.get('export_filter_label', '-')} | "
                f"Source ID: {st.session_state.get('export_source_id', '-')}"
            )

            with open(export_file_path, "rb") as file:
                st.download_button(
                    "Download Excel",
                    file,
                    file_name=export_file_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# =========================
# AUDIT TRAIL
# =========================

if menu == "Audit Trail":
    render_hero("Audit Trail", "Riwayat input dan perubahan data hasil pemeriksaan.", "Audit")
    audit_program_label = st.selectbox("Filter Program", ["Semua Program", "MCU Corporate", "CAPASKA / BPIP"])
    audit_program = PROGRAM_CORPORATE if audit_program_label == "MCU Corporate" else PROGRAM_CAPASKA if audit_program_label == "CAPASKA / BPIP" else None
    logs = get_audit_logs(program_type=audit_program, limit=300)
    if not logs:
        st.info("Belum ada aktivitas input atau update.")
    else:
        df = pd.DataFrame(logs)
        for col in df.columns:
            df[col] = df[col].apply(display_value)
        st.dataframe(df, use_container_width=True)
