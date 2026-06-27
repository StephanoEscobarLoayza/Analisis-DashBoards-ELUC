# =============================================================================
# Dashboard Electro Ucayali S.A.
# main.py — v6 (antigüedad titulares · módulo CLIENTES enriquecido)
# =============================================================================

# ##############################################################################
# FASE 0 — IMPORTS & CONFIGURACIÓN DE PÁGINA
# ##############################################################################

import io
import os
import math
import datetime

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client, Client

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image as RLImage, PageBreak,
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

st.set_page_config(
    page_title="Dashboard Electro Ucayali S.A.",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={},
)

# ##############################################################################
# FASE 1 — CONEXIÓN A SUPABASE Y CARGA DE DATOS
# ##############################################################################

# ── Credenciales ──────────────────────────────────────────────────────────
# NUNCA escribir las claves en el código fuente. Se leen desde, en este orden:
#   1) st.secrets   → archivo .streamlit/secrets.toml  (recomendado)
#   2) variables de entorno SUPABASE_URL / SUPABASE_KEY
# Para un dashboard de SOLO LECTURA usa la clave 'anon' con políticas RLS de
# SELECT, no la 'service_role' (que da acceso total a la base de datos).
def _get_secret(nombre: str, defecto: str = "") -> str:
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass
    return os.environ.get(nombre, defecto)

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")
TABLE = "eluc_resumen"

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "⚠️ Faltan credenciales de Supabase. Define SUPABASE_URL y SUPABASE_KEY "
        "en `.streamlit/secrets.toml` o como variables de entorno."
    )
    st.stop()

# Columnas nuevas de antigüedad agregadas al SELECT
COLS_ANTIGUEDAD = [
    "n_titulares",
    "titulares_mas_10",
    "titulares_5_10",
    "titulares_menos_5",
    "titulares_con_corte",
    "altas_antes_2000",
    "altas_2000s",
    "altas_2010s",
    "altas_2020s",
]

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame | None:
    try:
        sb = get_supabase()
        all_rows = []
        page_size = 1000
        offset = 0

        # Columnas base + todas las nuevas de antigüedad
        select_cols = (
            "departamento,provincia,distrito,tarifa,periodo,"
            "consumo_kwh,facturacion,status_cliente,"
            + ",".join(COLS_ANTIGUEDAD)
        )

        while True:
            resp = (
                sb.table(TABLE)
                .select(select_cols)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            rows = resp.data
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size

        if not all_rows:
            return None

        df = pd.DataFrame(all_rows)

        # ── Tipos numéricos base ──
        df["consumo_kwh"] = pd.to_numeric(df["consumo_kwh"], errors="coerce").fillna(0)
        df["facturacion"]  = pd.to_numeric(df["facturacion"],  errors="coerce").fillna(0)
        df["periodo"]      = df["periodo"].astype(str)
        df["anio"]         = df["periodo"].str[:4].astype(int)
        df["mes"]          = df["periodo"].str[4:6].astype(int)

        # ── Tipos numéricos de las nuevas columnas ──
        cols_int = [
            "n_titulares",
            "titulares_mas_10",
            "titulares_5_10",
            "titulares_menos_5",
            "titulares_con_corte",   # ← la dejamos
            "altas_antes_2000",
            "altas_2000s",
            "altas_2010s",
            "altas_2020s",
        ]
        for c in cols_int:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

        # ── Texto normalizado ──
        df["status_cliente"] = df["status_cliente"].fillna("DESCONOCIDO").str.upper()
        df["tarifa"]         = df["tarifa"].fillna("SIN TARIFA").str.upper()
        df["departamento"]   = df["departamento"].str.upper()
        df["provincia"]      = df["provincia"].str.upper()
        df["distrito"]       = df["distrito"].str.upper()

        # ── Precio implícito ──
        df["precio_kwh"] = df.apply(
            lambda r: round(r["facturacion"] / r["consumo_kwh"], 4)
            if r["consumo_kwh"] > 0 else 0, axis=1
        )
        return df

    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None


# ##############################################################################
# FASE 2 — CONSTANTES Y DICCIONARIOS DE MÓDULOS
# ##############################################################################

MESES_CORTO = ["Ene","Feb","Mar","Abr","May","Jun",
                "Jul","Ago","Sep","Oct","Nov","Dic"]

MODULOS = [
    {"key": "CONSUMO",    "label": "Consumo",    "icon": "⚡", "color": "#3b82f6", "bg": "#0f1e3d"},
    {"key": "GEOGRAFIA",  "label": "Geografía",  "icon": "🗺️",  "color": "#22c55e", "bg": "#0a1f10"},
    {"key": "TARIFAS",    "label": "Tarifas",    "icon": "💰", "color": "#f59e0b", "bg": "#1f1500"},
    {"key": "CLIENTES",   "label": "Clientes",   "icon": "👥", "color": "#a855f7", "bg": "#1a0a2e"},
    {"key": "EFICIENCIA", "label": "Eficiencia", "icon": "📈", "color": "#ec4899", "bg": "#2e0a1a"},
    {"key": "PROYECCION", "label": "Proyección", "icon": "🔮", "color": "#06b6d4", "bg": "#001f2e"},
]

MOD_ACCENT  = {m["key"]: m["color"] for m in MODULOS}
MOD_LABELS  = {
    "CONSUMO":    "Análisis de Consumo Energético",
    "GEOGRAFIA":  "Geografía y Territorio",
    "TARIFAS":    "Estructura Tarifaria",
    "CLIENTES":   "Cartera de Clientes",
    "EFICIENCIA": "Eficiencia Operacional",
    "PROYECCION": "Proyección y Regresión Lineal",
}
MOD_NUMBER   = {m["key"]: i+1 for i, m in enumerate(MODULOS)}
LINE_PALETTE = ["#3b5bdb","#16a34a","#f59e0b","#e03131","#9c36b5","#0891b2",
                "#ec4899","#14b8a6","#f97316","#8b5cf6"]

# ── Datos históricos de altas por año ──
@st.cache_data(ttl=3600)
def load_altas() -> dict:
    try:
        sb = get_supabase()
        resp = sb.table("eluc_altas_por_anio").select("anio,n_altas").execute()
        return {row["anio"]: row["n_altas"] for row in resp.data}
    except Exception:
        return {}

ALTAS_HISTORICAS = load_altas()

# ── Totales globales de titulares ──
@st.cache_data(ttl=3600)
def load_totales() -> dict:
    try:
        sb = get_supabase()
        resp = sb.table("eluc_totales").select("clave,valor").execute()
        return {row["clave"]: row["valor"] for row in resp.data}
    except Exception:
        return {}

TOTALES = load_totales()


# ##############################################################################
# FASE 3 — HELPERS DE FORMATO Y LAYOUT DE GRÁFICOS
# ##############################################################################

def fmt(v: float) -> str:
    if v >= 1_000_000: return f"{v/1e6:.1f}M"
    if v >= 1_000:     return f"{v/1e3:.0f}K"
    return f"{int(v):,}"


def fmt_soles(v: float) -> str:
    if v >= 1_000_000: return f"S/ {v/1e6:.2f}M"
    if v >= 1_000:     return f"S/ {v/1e3:.1f}K"
    return f"S/ {v:,.2f}"


def periodo_a_label(periodo_str: str) -> str:
    """'202501' → 'Ene 25'"""
    try:
        anio = int(str(periodo_str)[:4])
        mes  = int(str(periodo_str)[4:6])
        return f"{MESES_CORTO[mes-1]} {str(anio)[2:]}"
    except Exception:
        return str(periodo_str)


# ── Paleta de colores y estilos base ──
TXT       = "#1e293b"
FONT_DICT = dict(family="Segoe UI, system-ui, sans-serif", color="#1e293b", size=11)
AXIS_STD  = dict(
    gridcolor="#f1f5f9", linecolor="#cbd5e1", zeroline=False,
    tickfont=dict(color="#1e293b", size=10),
    title_font=dict(color="#1e293b", size=11),
)


def base_layout(height: int = 300) -> dict:
    return dict(
        plot_bgcolor="white", paper_bgcolor="white",
        font=FONT_DICT,
        margin=dict(l=55, r=20, t=35, b=60),
        height=height,
        xaxis=dict(**AXIS_STD),
        yaxis=dict(**AXIS_STD),
    )


def axis_x_mensual(n: int) -> dict:
    """Eje X con etiquetas 'Ene 25', rotadas 45°, sin colapso"""
    return dict(
        type="category",
        gridcolor="#f1f5f9", linecolor="#e2e8f0", zeroline=False,
        tickangle=-45,
        tickfont=dict(color=TXT, size=10),
        title_font=dict(color=TXT, size=11),
        nticks=min(n, 18),
        automargin=True,
    )


def fig_to_image(fig, width=800, height=360):
    try:
        fig.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None

# ##############################################################################
# FASE 4 — ESTILOS CSS GLOBALES
# ##############################################################################

CSS = """
<style>
    /* ── Base ── */
    .stApp { background-color: #f0f2f5 !important; }
    .stApp p, .stApp span, .stApp label, .stApp small, .stApp li { color: #1e293b !important; }
 
    /* ── Header limpio ── */
    header[data-testid="stHeader"] {
        height: 3rem !important; min-height: 3rem !important;
        padding: 0 !important; background: transparent !important;
    }
    [data-testid="stToolbar"] > div:last-child { display: none !important; }
    [data-testid="stDecoration"]               { display: none !important; }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
 
    /* ── Main — color global EXCEPTO botón PDF ── */
    section[data-testid="stMain"] { background-color: #f0f2f5 !important; }
    section[data-testid="stMain"] *:not(.pdf-btn):not(.pdf-btn *) { color: #1e293b !important; }
 
    /* ── Sidebar ── */
    [data-testid="stSidebar"] { background-color: #0a0f1e !important; }
    [data-testid="stSidebar"], [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span, [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label { color: #c8d0de !important; }
    [data-testid="stSidebar"] h1 {
        color: #ffffff !important; font-size: 20px !important; font-weight: 700 !important;
    }
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[data-testid="stBaseButton-headerNoPadding"] { display: none !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] * {
        color: #c8d0de !important; background-color: #1a2035 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #6b7280 !important; font-size: 10px !important;
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;
    }
 
    /* ── Métricas ── */
    [data-testid="metric-container"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-left: 4px solid var(--accent, #3b82f6) !important;
        border-radius: 12px !important;
        padding: 18px 20px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    }
    [data-testid="stMetricLabel"] p {
        font-size: 11px !important; color: #64748b !important;
        text-transform: uppercase !important; letter-spacing: 0.5px !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 26px !important; font-weight: 700 !important; color: #1e293b !important;
    }
    [data-testid="stMetricDelta"] { font-size: 12px !important; }
 
    /* ── Tipografía ── */
    h1, h2, h3, h4 { color: #1e293b !important; }
    h2 { font-size: 22px !important; font-weight: 700 !important; }
    h3 { font-size: 15px !important; font-weight: 600 !important; }
 
    /* ── Botón PDF ── */
    div.pdf-btn button,
    div.pdf-btn [data-testid="stDownloadButton"] button {
        background-color: #1d4ed8 !important;
        background: #1d4ed8 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 8px !important;
        min-width: 260px !important;
    }
    div.pdf-btn button *,
    div.pdf-btn button span,
    div.pdf-btn button p,
    div.pdf-btn [data-testid="stDownloadButton"] button *,
    div.pdf-btn [data-testid="stDownloadButton"] button span,
    div.pdf-btn [data-testid="stDownloadButton"] button p {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
 
    /* ── Selectores área principal ── */
    section[data-testid="stMain"] [data-testid="stSelectbox"] label,
    section[data-testid="stMain"] [data-testid="stSelectbox"] p,
    section[data-testid="stMain"] [data-testid="stSelectbox"] span { color: #1e293b !important; }
    section[data-testid="stMain"] [data-testid="stSelectbox"] > div > div {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        color: #1e293b !important;
    }
    [data-baseweb="select"] * { color: #1e293b !important; }
    [data-baseweb="menu"]   * { color: #1e293b !important; background-color: #ffffff !important; }
    [data-baseweb="popover"] * { color: #1e293b !important; background-color: #ffffff !important; }
 
    /* ── Tablas ── */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important; overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    }
    [data-testid="stDataFrame"] table { background: #ffffff !important; }
    [data-testid="stDataFrame"] thead th {
        background-color: #1e3a5f !important; color: #ffffff !important;
        font-weight: 700 !important; font-size: 12px !important;
        padding: 10px 14px !important; border: none !important;
        text-transform: uppercase !important; letter-spacing: 0.5px !important;
    }
    [data-testid="stDataFrame"] tbody tr:nth-child(even) td { background-color: #f8fafc !important; }
    [data-testid="stDataFrame"] tbody tr:hover td { background-color: #eff6ff !important; }
    [data-testid="stDataFrame"] tbody td {
        color: #1e293b !important; font-size: 13px !important;
        padding: 9px 14px !important; border-bottom: 1px solid #f1f5f9 !important;
    }
    [data-testid="stDataFrame"] * { color: #1e293b !important; }
 
    hr { border-color: #2d3347; }
    section[data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stMain"] [data-testid="stMarkdownContainer"] strong {
        color: #1e293b !important;
    }

    /* ── Card de conclusión automática ── */
    .conclusion-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%);
        border-left: 5px solid #a855f7;
        border-radius: 0 12px 12px 0;
        padding: 18px 22px;
        margin: 16px 0 8px 0;
    }
    .conclusion-card p,
    .conclusion-card span,
    .conclusion-card b,
    .conclusion-card * {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
    }
</style>
"""
 
st.markdown(CSS, unsafe_allow_html=True)

# ##############################################################################
# FASE 5 — CARGA DE DATOS Y ESTADO DE SESIÓN
# ##############################################################################

df_full = load_data()
if df_full is None:
    st.error("⚠️ No se pudo cargar datos desde Supabase. Verifica las credenciales.")
    st.stop()

if "modulo_sel" not in st.session_state:
    st.session_state.modulo_sel = "CONSUMO"

periodos_sorted = sorted(df_full["periodo"].unique().tolist())
per_min_label   = periodo_a_label(periodos_sorted[0])
per_max_label   = periodo_a_label(periodos_sorted[-1])

# ##############################################################################
# FASE 6 — SIDEBAR: MENÚ DE MÓDULOS Y FILTROS GLOBALES EN CASCADA
# ##############################################################################

with st.sidebar:
    st.markdown("""
    <div style='padding:8px 0 4px 0'>
        <p style='color:#4b6584;font-size:11px;margin:0;letter-spacing:1.5px;font-weight:600'>ELECTRO UCAYALI S.A.</p>
        <h1 style='color:#ffffff;font-size:19px;font-weight:700;margin:4px 0 0 0;line-height:1.3'>
            ⚡ Panel de Control<br>Análisis Energético
        </h1>
    </div>
    <hr style='border-color:#1a2035;margin:14px 0'>
    <p style='color:#4b6584;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px'>
        MÓDULOS
    </p>
    """, unsafe_allow_html=True)

    params = st.query_params
    if "mod" in params and params["mod"] in [m["key"] for m in MODULOS]:
        st.session_state.modulo_sel = params["mod"]

    menu_html = ""
    for m in MODULOS:
        is_active = st.session_state.modulo_sel == m["key"]
        card_bg  = m["bg"]    if is_active else "rgba(255,255,255,0.02)"
        border_c = m["color"] if is_active else "rgba(255,255,255,0.05)"
        txt_col  = m["color"] if is_active else "#9ca3af"
        fw       = "700" if is_active else "500"
        menu_html += (
            f'<a href="?mod={m["key"]}" target="_self" style="text-decoration:none;display:block;margin-bottom:5px;">'
            f'<div style="display:flex;align-items:center;gap:10px;background:{card_bg};'
            f'border:1.5px solid {border_c};border-radius:10px;padding:10px 12px;">'
            f'<div style="width:34px;height:34px;background:{m["bg"]};border-radius:8px;'
            f'display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;'
            f'border:1px solid {m["color"]}44;">{m["icon"]}</div>'
            f'<span style="color:{txt_col};font-size:14px;font-weight:{fw};">{m["label"]}</span>'
            f'</div></a>'
        )
    st.markdown(menu_html, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a2035;margin:14px 0'>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4b6584;font-size:10px;letter-spacing:1.5px;"
        "text-transform:uppercase;margin-bottom:8px'>FILTROS GLOBALES</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<p style='color:#9ca3af;font-size:12px;margin-bottom:2px'>Período</p>", unsafe_allow_html=True)
    per_opts = ["Todos"] + periodos_sorted
    sel_per  = st.selectbox(
        "Período", per_opts,
        format_func=lambda x: f"Todos ({per_min_label}–{per_max_label})" if x == "Todos"
                               else periodo_a_label(x),
        label_visibility="collapsed",
    )

    # ── Provincia ──
    st.markdown("<p style='color:#9ca3af;font-size:12px;margin-bottom:2px;margin-top:8px'>Provincia</p>",
                unsafe_allow_html=True)
    prov_opts = ["Todas"] + sorted(df_full["provincia"].dropna().unique().tolist())
    sel_prov  = st.selectbox("Provincia", prov_opts, label_visibility="collapsed")

    # ── Distrito — cascada según provincia ──
    if sel_prov != "Todas":
        dist_disponibles = sorted(
            df_full[df_full["provincia"] == sel_prov]["distrito"].dropna().unique().tolist()
        )
    else:
        dist_disponibles = sorted(df_full["distrito"].dropna().unique().tolist())

    st.markdown("<p style='color:#9ca3af;font-size:12px;margin-bottom:2px;margin-top:8px'>Distrito</p>",
                unsafe_allow_html=True)
    dist_opts = ["Todos"] + dist_disponibles
    sel_dist  = st.selectbox("Distrito", dist_opts, label_visibility="collapsed")

    # ── Tarifa — cascada según provincia + distrito seleccionados ──
    df_para_tarifa = df_full.copy()
    if sel_prov != "Todas":
        df_para_tarifa = df_para_tarifa[df_para_tarifa["provincia"] == sel_prov]
    if sel_dist != "Todos":
        df_para_tarifa = df_para_tarifa[df_para_tarifa["distrito"] == sel_dist]

    tarifas_disponibles = sorted(df_para_tarifa["tarifa"].dropna().unique().tolist())
    n_tarifas           = len(tarifas_disponibles)

    st.markdown("<p style='color:#9ca3af;font-size:12px;margin-bottom:2px;margin-top:8px'>Tarifa</p>",
                unsafe_allow_html=True)

    if n_tarifas == 1:
        st.markdown(
            f"<p style='color:#f59e0b;font-size:10px;margin:0 0 4px 0'>"
            f"ℹ️ Solo 1 tarifa disponible aquí</p>",
            unsafe_allow_html=True,
        )

    tar_opts   = ["Todas"] + tarifas_disponibles
    sel_tarifa = st.selectbox("Tarifa", tar_opts, label_visibility="collapsed")

    # ── Footer del sidebar ──
    st.markdown("<hr style='border-color:#1a2035;margin:14px 0'>", unsafe_allow_html=True)
    n_per = df_full["periodo"].nunique()
    st.markdown(
        f"<div style='font-size:10px;color:#4b6584'>"
        f"Datos: Electro Ucayali S.A.<br>"
        f"{per_min_label} – {per_max_label} · {n_per} períodos<br>"
        f"{len(df_full):,} registros · {df_full['distrito'].nunique()} distritos</div>",
        unsafe_allow_html=True,
    )

# ##############################################################################
# FASE 7 — FILTRADO GLOBAL DEL DATAFRAME
# ##############################################################################

df = df_full.copy()
if sel_per != "Todos":
    df = df[df["periodo"] == sel_per]
if sel_prov != "Todas":
    df = df[df["provincia"] == sel_prov]
if sel_dist != "Todos":
    df = df[df["distrito"] == sel_dist]
if sel_tarifa != "Todas":
    df = df[df["tarifa"] == sel_tarifa]

mod    = st.session_state.modulo_sel
accent = MOD_ACCENT.get(mod, "#3b82f6")

# ── Breadcrumb ──
_filtros = []
if sel_per != "Todos": _filtros.append(periodo_a_label(sel_per))
if sel_prov != "Todas": _filtros.append(sel_prov.title())
if sel_dist != "Todos": _filtros.append(sel_dist.title())
if sel_tarifa != "Todas": _filtros.append(sel_tarifa)
_filtro_txt = " · ".join(_filtros) if _filtros else "Todos los datos"

st.markdown(
    f"<p style='font-size:12px;color:#94a3b8;margin-bottom:2px'>"
    f"Dashboard Electro Ucayali / "
    f"<strong style='color:#1e293b'>{mod.title()}</strong> &nbsp;"
    f"<span style='background:#e8edf5;color:{accent};font-size:11px;font-weight:600;"
    f"padding:2px 10px;border-radius:20px'>MÓDULO {MOD_NUMBER[mod]}</span>"
    f"&nbsp;<span style='font-size:11px;color:#64748b'>{_filtro_txt}</span></p>",
    unsafe_allow_html=True,
)

# ##############################################################################
# FASE 8 — GENERADOR DE PDF
# ##############################################################################

def construir_conclusiones(mod, df, df_full, sel_per, sel_prov, sel_dist, sel_tarifa):
    """Interpretación de nivel gerencial que se adapta al módulo y a los filtros.
    Devuelve un dict:
      - 'sintesis'        : str  (párrafo ejecutivo)
      - 'hallazgos'       : list[str]
      - 'recomendaciones' : list[dict] con claves {area, prio, texto}
      - 'nota'            : str  (nota metodológica al pie)
    El texto usa etiquetas HTML simples (<b>...</b>) que ReportLab interpreta."""
    vacio = {"sintesis": "", "hallazgos": [], "recomendaciones": [], "nota": ""}
    if df is None or len(df) == 0:
        vacio["sintesis"] = ("No hay datos para el filtro seleccionado, por lo que no es posible "
                             "generar conclusiones. Amplíe o modifique los filtros del panel.")
        return vacio

    sintesis = ""
    hallazgos = []
    recs = []
    def rec(area, prio, texto):
        recs.append({"area": area, "prio": prio, "texto": texto})

    # ── Alcance (común) ──
    if sel_per != "Todos":
        alcance_per = f"el periodo {periodo_a_label(sel_per)}"
    else:
        alcance_per = f"el rango {per_min_label}-{per_max_label} ({df['periodo'].nunique()} meses)"
    if sel_dist != "Todos":
        alcance_geo = f"el distrito de {sel_dist.title()}"
    elif sel_prov != "Todas":
        alcance_geo = f"la provincia de {sel_prov.title()}"
    else:
        alcance_geo = "el conjunto de la concesion de Electro Ucayali"
    alcance_tar = "" if sel_tarifa == "Todas" else f", limitado a la tarifa {sel_tarifa}"

    # =====================================================================
    # CONSUMO
    # =====================================================================
    if mod == "CONSUMO":
        total_kwh  = df["consumo_kwh"].sum()
        total_fact = df["facturacion"].sum()
        precio     = total_fact / total_kwh if total_kwh > 0 else 0
        by_per = (df.groupby("periodo")["consumo_kwh"].sum()
                  .reset_index().sort_values("periodo"))
        tendencia_txt, var = "estable", 0.0
        if len(by_per) >= 4:
            x = np.arange(len(by_per))
            slope = np.polyfit(x, by_per["consumo_kwh"].values, 1)[0]
            primero, ultimo = by_per["consumo_kwh"].iloc[0], by_per["consumo_kwh"].iloc[-1]
            var = (ultimo - primero) / primero * 100 if primero > 0 else 0
            tendencia_txt = "estable" if abs(var) < 1.0 else ("creciente" if slope > 0 else "decreciente")

        sintesis = (
            f"Durante {alcance_per}, {alcance_geo}{alcance_tar} registro un consumo de "
            f"{fmt(total_kwh)} kWh y una facturacion de {fmt_soles(total_fact)}, con un precio medio "
            f"de S/ {precio:.4f} por kWh. La demanda se comporta de forma <b>{tendencia_txt}</b>, "
            f"escenario que define el tipo de decisiones de inversion y planificacion energetica que "
            f"conviene priorizar.")

        hallazgos.append(
            f"<b>Magnitud del negocio.</b> El consumo facturado asciende a {fmt(total_kwh)} kWh "
            f"({fmt_soles(total_fact)}). Sobre este volumen, una mejora de apenas S/ 0.01 en el precio "
            f"implicito equivale a unos {fmt_soles(total_kwh*0.01)} adicionales en el periodo.")
        if tendencia_txt == "creciente":
            hallazgos.append(
                f"<b>Demanda en expansion.</b> El consumo crecio {var:+.1f}% entre el primer y el "
                f"ultimo mes, lo que anticipa mayor exigencia sobre la infraestructura.")
            rec("Operaciones / Red", "Alta",
                "<b>Anticipar capacidad y compra de energia.</b> Dimensionar contratos de suministro "
                "y reforzar las subestaciones y alimentadores mas exigidos antes de que el crecimiento "
                "comprometa la continuidad del servicio.")
        elif tendencia_txt == "decreciente":
            hallazgos.append(
                f"<b>Demanda a la baja.</b> El consumo cayo {var:+.1f}% en el periodo; de sostenerse, "
                f"presiona los ingresos y obliga a revisar la estructura de costos.")
            rec("Comercial", "Alta",
                "<b>Proteger ingresos.</b> Investigar la causa de la caida (migracion de clientes, "
                "eficiencia o factores economicos) y activar campanas de retencion para estabilizar "
                "la demanda.")
        else:
            hallazgos.append(
                "<b>Demanda madura y estable.</b> El consumo no muestra cambios estructurales, lo que "
                "da previsibilidad de ingresos pero limita el crecimiento organico.")
            rec("Operaciones / Red", "Media",
                "<b>Reorientar la inversion hacia eficiencia.</b> Con demanda estable, el retorno esta "
                "menos en ampliar capacidad y mas en reducir perdidas tecnicas y no tecnicas, mejorar "
                "la medicion y optimizar la cobranza.")

        dn = df[df["status_cliente"] == "NORMAL"]
        if len(dn) > 0 and dn["mes"].nunique() > 1:
            bm = dn.groupby("mes")["consumo_kwh"].mean()
            mpico, mbajo = MESES_CORTO[int(bm.idxmax())-1], MESES_CORTO[int(bm.idxmin())-1]
            hallazgos.append(
                f"<b>Estacionalidad marcada.</b> El consumo promedio alcanza su pico en {mpico} y su "
                f"minimo en {mbajo}, patron determinante para la planificacion de la compra de energia "
                f"y el balance oferta-demanda.")
            rec("Planificacion", "Media",
                f"<b>Planificar por temporada.</b> Concentrar mantenimientos en {mbajo} (menor demanda) "
                f"y asegurar respaldo de energia para {mpico} (mayor demanda) reduce sobrecostos y "
                f"riesgo operativo.")

    # =====================================================================
    # GEOGRAFIA
    # =====================================================================
    elif mod == "GEOGRAFIA":
        by_d = (df.groupby("distrito")
                .agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"), tit=("n_titulares","sum"))
                .reset_index().sort_values("kwh", ascending=False))
        n = len(by_d); tot = by_d["kwh"].sum()
        by_d["precio"] = by_d["fact"] / by_d["kwh"].replace(0, 1)
        top = by_d.iloc[0] if n > 0 else None
        top_pct = (top["kwh"] / tot * 100) if (top is not None and tot > 0) else 0
        top3 = (by_d.head(3)["kwh"].sum() / tot * 100) if tot > 0 else 0

        if n == 1:
            sintesis = (
                f"El analisis se concentra en {top['distrito'].title()}, que durante {alcance_per} "
                f"consumio {fmt(top['kwh'])} kWh y facturo {fmt_soles(top['fact'])}. El foco esta en "
                f"entender el comportamiento de este territorio y sus oportunidades especificas.")
        else:
            sintesis = (
                f"Durante {alcance_per}, el consumo de {alcance_geo}{alcance_tar} se reparte entre "
                f"{n} distritos. {top['distrito'].title()} lidera con el {top_pct:.1f}% del total y los "
                f"tres principales concentran el {top3:.1f}%. El grado de concentracion territorial es "
                f"el factor central para decidir donde priorizar inversion y gestion de riesgo.")

        if n > 0:
            hallazgos.append(
                f"<b>Distrito clave.</b> {top['distrito'].title()} aporta {top_pct:.1f}% del consumo "
                f"({fmt(top['kwh'])} kWh) y {fmt_soles(top['fact'])} de facturacion. Es el activo mas "
                f"valioso de la cartera territorial.")
        if n >= 3:
            if top3 >= 70:
                hallazgos.append(
                    f"<b>Riesgo de concentracion.</b> El {top3:.1f}% del consumo depende de solo tres "
                    f"distritos; una falla mayor en cualquiera afectaria a la mayor parte del negocio.")
                rec("Riesgo / Red", "Alta",
                    "<b>Blindar los nodos criticos.</b> Priorizar redundancia de red, mantenimiento "
                    "preventivo y planes de contingencia en los distritos de mayor consumo para "
                    "proteger la continuidad de los ingresos.")
            else:
                hallazgos.append(
                    f"<b>Demanda distribuida.</b> Los tres distritos principales suman {top3:.1f}%, una "
                    f"distribucion relativamente equilibrada que reduce la exposicion a un unico punto.")
            rec("Comercial", "Media",
                f"<b>Focalizar la inversion comercial.</b> Concentrar captacion, cobranza y calidad de "
                f"servicio en {top['distrito'].title()} y los distritos lideres maximiza el retorno por "
                f"sol invertido.")

        dp = by_d[by_d["kwh"] > 0]
        if len(dp) > 1:
            pmax = dp.sort_values("precio", ascending=False).iloc[0]
            pmin = dp.sort_values("precio").iloc[0]
            hallazgos.append(
                f"<b>Asimetria de precio (posibles perdidas no tecnicas).</b> El precio implicito va de "
                f"S/ {pmin['precio']:.4f}/kWh en {pmin['distrito'].title()} a S/ {pmax['precio']:.4f}/kWh "
                f"en {pmax['distrito'].title()}. Una desviacion asi suele reflejar perdidas tecnicas o no "
                f"tecnicas (hurto, conexiones irregulares, medicion deficiente), el principal KPI de "
                f"gestion de una distribuidora y componente del calculo tarifario ante el regulador.")
            rec("Datos / Calidad", "Alta",
                f"<b>Auditar los extremos.</b> Revisar la medicion y las perdidas en "
                f"{pmax['distrito'].title()} (precio anomalo) permite recuperar ingresos o corregir "
                f"errores antes de que escalen.")

    # =====================================================================
    # TARIFAS
    # =====================================================================
    elif mod == "TARIFAS":
        by_t = (df.groupby("tarifa")
                .agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"), tit=("n_titulares","sum"))
                .reset_index().sort_values("kwh", ascending=False))
        tot = by_t["kwh"].sum()
        by_t["precio"] = by_t["fact"] / by_t["kwh"].replace(0, 1)
        dom = by_t.iloc[0] if len(by_t) > 0 else None
        dom_pct = (dom["kwh"] / tot * 100) if (dom is not None and tot > 0) else 0

        sintesis = (
            f"La estructura tarifaria de {alcance_geo} durante {alcance_per} esta dominada por la "
            f"tarifa {dom['tarifa'] if dom is not None else 'N/D'} ({dom_pct:.1f}% del consumo). El "
            f"equilibrio del mix tarifario determina tanto la rentabilidad como la exposicion de la "
            f"empresa a cambios regulatorios.")

        if dom is not None:
            hallazgos.append(
                f"<b>Exposicion regulatoria.</b> La tarifa {dom['tarifa']} concentra el {dom_pct:.1f}% "
                f"del consumo, de modo que los ingresos dependen casi por completo del pliego tarifario "
                f"que fija el regulador (Osinergmin) y de los subsidios asociados. Es una concentracion "
                f"de riesgo regulatorio.")
            if dom_pct >= 80:
                rec("Comercial", "Alta",
                    "<b>Diversificar el mix de clientes.</b> Captar clientes de tarifas de mayor margen "
                    "(comerciales e industriales) reduce la dependencia de una unica tarifa y mejora la "
                    "resiliencia de los ingresos ante cambios regulatorios.")
        pt = by_t[by_t["kwh"] > 0].sort_values("precio", ascending=False)
        if len(pt) > 0:
            mejor = pt.iloc[0]
            hallazgos.append(
                f"<b>Donde esta el margen.</b> La tarifa {mejor['tarifa']} ofrece el mayor precio "
                f"implicito (S/ {mejor['precio']:.4f}/kWh): cada cliente de este segmento aporta mas "
                f"ingreso por unidad consumida.")
            rec("Comercial", "Media",
                f"<b>Estrategia comercial dirigida.</b> Disenar una propuesta para atraer y retener "
                f"clientes {mejor['tarifa']} eleva el ingreso medio sin aumentar el numero total de "
                f"conexiones.")
        if len(by_t) > 1:
            rec("Finanzas / Regulatorio", "Media",
                "<b>Monitoreo regulatorio.</b> Dado el peso de la tarifa principal, anticipar el impacto "
                "de futuras revisiones del pliego tarifario sobre los ingresos es clave para el "
                "presupuesto.")

    # =====================================================================
    # CLIENTES
    # =====================================================================
    elif mod == "CLIENTES":
        hay_filtro = (sel_prov != "Todas" or sel_dist != "Todos"
                      or sel_tarifa != "Todas" or sel_per != "Todos")
        if hay_filtro:
            up = df["periodo"].max(); du = df[df["periodo"] == up]
            tot = int(du["n_titulares"].sum())
            m10 = int(du["titulares_mas_10"].sum()); c510 = int(du["titulares_5_10"].sum())
            me5 = int(du["titulares_menos_5"].sum())
        else:
            upf = df_full["periodo"].max(); duf = df_full[df_full["periodo"] == upf]
            tot = TOTALES.get("total_titulares",   int(duf["n_titulares"].sum()))
            m10 = TOTALES.get("titulares_mas_10",  int(duf["titulares_mas_10"].sum()))
            c510 = TOTALES.get("titulares_5_10",   int(duf["titulares_5_10"].sum()))
            me5 = TOTALES.get("titulares_menos_5", int(duf["titulares_menos_5"].sum()))
        p10 = p510 = p5 = 0
        if tot > 0:
            p10, p510, p5 = m10/tot*100, c510/tot*100, me5/tot*100
        perfil = ("madura y consolidada" if p10 >= 50
                  else "en expansion" if p5 >= p10 else "equilibrada")
        bs = df.groupby("status_cliente")["n_titulares"].sum()
        pnorm = (bs["NORMAL"] / bs.sum() * 100) if (bs.sum() > 0 and "NORMAL" in bs.index) else 0

        sintesis = (
            f"La cartera de {alcance_geo} suma {tot:,} titulares y es {perfil}: {p10:.1f}% supera los "
            f"10 años de antiguedad y {p5:.1f}% son clientes nuevos. Con un {pnorm:.1f}% en estado "
            f"activo, la fotografia define si la prioridad estrategica debe ser crecer, retener o "
            f"sanear la cartera.")

        if p10 >= 50:
            hallazgos.append(
                f"<b>Base fiel pero de bajo crecimiento.</b> {p10:.1f}% de los titulares supera los 10 "
                f"años: ingresos muy estables, pero crecimiento organico limitado.")
            rec("Comercial", "Media",
                "<b>Equilibrar fidelizacion y captacion.</b> Mantener la calidad de servicio a la base "
                "consolidada y, en paralelo, fijar metas de nuevas conexiones en zonas de expansion "
                "urbana para no estancar el crecimiento.")
        else:
            hallazgos.append(
                f"<b>Cartera en renovacion.</b> {p5:.1f}% son clientes nuevos, senal de captacion "
                f"activa que conviene consolidar para asegurar su permanencia.")
            rec("Comercial", "Media",
                "<b>Asegurar la permanencia de los nuevos.</b> Reforzar el acompanamiento y la "
                "experiencia de los clientes recientes reduce la fuga temprana y protege la inversion "
                "en captacion.")
        hallazgos.append(
            f"<b>Calidad de cartera y morosidad.</b> El {pnorm:.1f}% esta en estado NORMAL; el resto "
            f"(anulados/depurados) es cartera improductiva. Este ratio alimenta los indicadores de "
            f"morosidad y eficiencia de cobranza que reporta la distribuidora. "
            f"{'El nivel actual es sano.' if pnorm >= 95 else 'El nivel de inactivos/anulados merece revision.'}")
        if pnorm < 95:
            rec("Datos / Calidad", "Alta",
                "<b>Sanear la cartera.</b> Investigar el origen de los registros no activos "
                "(anulados/depurados) y depurar o recuperar segun corresponda mejora la calidad de la "
                "informacion y la cobranza.")
        if not hay_filtro and ALTAS_HISTORICAS:
            ap = max(ALTAS_HISTORICAS.items(), key=lambda x: x[1])
            hallazgos.append(
                f"<b>Memoria de crecimiento.</b> El año de mayor incorporacion historica fue {ap[0]} "
                f"({ap[1]:,} nuevas conexiones), referencia util para fijar metas realistas de captacion.")

    # =====================================================================
    # EFICIENCIA
    # =====================================================================
    elif mod == "EFICIENCIA":
        tot_tit = int(df["n_titulares"].sum())
        fact_tit = (df["facturacion"].sum() / tot_tit) if tot_tit > 0 else 0
        kwh_tit  = (df["consumo_kwh"].sum() / tot_tit) if tot_tit > 0 else 0
        by_per = (df.groupby("periodo")["consumo_kwh"].sum()
                  .reset_index().sort_values("periodo"))
        var = 0.0
        if len(by_per) >= 2:
            va, vu = by_per["consumo_kwh"].iloc[-2], by_per["consumo_kwh"].iloc[-1]
            var = (vu - va) / va * 100 if va > 0 else 0

        sintesis = (
            f"En {alcance_geo} durante {alcance_per}, cada titular factura en promedio "
            f"{fmt_soles(fact_tit)} y consume {kwh_tit:.0f} kWh al mes. Estos indicadores de "
            f"rendimiento por cliente son la base para decidir donde mejorar margen y eficiencia "
            f"operativa.")

        hallazgos.append(
            f"<b>Valor por cliente.</b> El ingreso medio mensual por titular es {fmt_soles(fact_tit)}. "
            f"Pequenas mejoras en cobranza o reduccion de perdidas, multiplicadas por la base de "
            f"clientes, tienen impacto economico considerable.")
        if len(by_per) >= 2:
            hallazgos.append(
                f"<b>Senal reciente.</b> El consumo del ultimo mes vario {var:+.1f}% frente al previo "
                f"({'aceleracion' if var >= 0 else 'desaceleracion'} de la demanda), dato a vigilar en "
                f"la operacion de corto plazo.")
        td = (df.groupby("distrito")
              .agg(fact=("facturacion","sum"), tit=("n_titulares","sum")).reset_index())
        td["ticket"] = td["fact"] / td["tit"].replace(0, 1)
        td = td[td["tit"] > 0].sort_values("ticket", ascending=False)
        if len(td) > 0:
            best, worst = td.iloc[0], td.iloc[-1]
            hallazgos.append(
                f"<b>Brecha de rentabilidad.</b> La facturacion por titular va de S/ {worst['ticket']:.2f} "
                f"en {worst['distrito'].title()} a S/ {best['ticket']:.2f} en {best['distrito'].title()} "
                f"al mes, lo que revela territorios mas y menos rentables.")
            rec("Comercial / Operaciones", "Media",
                f"<b>Gestion diferenciada por distrito.</b> Priorizar servicios de valor en "
                f"{best['distrito'].title()} (mayor ticket) y analizar las causas del bajo rendimiento "
                f"en {worst['distrito'].title()} (perdidas, mix de clientes o morosidad).")
        rec("Operaciones / Red", "Alta",
            "<b>Reducir perdidas como palanca de margen.</b> Un programa sostenido de control de "
            "perdidas tecnicas y no tecnicas suele ofrecer mejor retorno que el crecimiento de "
            "clientes en una cartera ya consolidada.")

    # =====================================================================
    # PROYECCION
    # =====================================================================
    elif mod == "PROYECCION":
        by_per = (df.groupby("periodo")["consumo_kwh"].sum()
                  .reset_index().sort_values("periodo"))
        n = len(by_per)
        if n >= 4:
            x = np.arange(n); y = by_per["consumo_kwh"].values.astype(float)
            coef = np.polyfit(x, y, 1); yfit = np.polyval(coef, x)
            ss_res = np.sum((y - yfit)**2); ss_tot = np.sum((y - y.mean())**2)
            r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
            y6 = max(0, np.polyval(coef, n + 5))
            var = (y6 - y[-1]) / y[-1] * 100 if y[-1] > 0 else 0
            dirc = "al alza" if coef[0] > 0 else "a la baja"
            confiable = r2 >= 0.6

            sintesis = (
                f"Proyectando el consumo de {alcance_geo} a 6 meses, el modelo lineal apunta {dirc} hasta "
                f"{fmt(y6)} kWh ({var:+.1f}% frente al ultimo mes real), con un ajuste R2 de {r2:.2f}. "
                f"La fiabilidad de esta proyeccion condiciona cuanto peso debe darsele en las decisiones "
                f"de inversion.")

            hallazgos.append(
                f"<b>Direccion esperada.</b> De mantenerse la tendencia, el consumo se ubicaria en "
                f"{fmt(y6)} kWh en seis meses ({var:+.1f}%).")
            if confiable:
                hallazgos.append(
                    f"<b>Ajuste razonable.</b> Un R2 de {r2:.2f} indica que la tendencia explica buena "
                    f"parte del comportamiento; la proyeccion es un insumo solido para planificar.")
                if coef[0] > 0:
                    rec("Operaciones / Red", "Alta",
                        "<b>Asegurar suministro y red.</b> Anticipar la compra de energia y el refuerzo "
                        "de la infraestructura para acompanar el crecimiento previsto evita cuellos de "
                        "botella.")
                else:
                    rec("Finanzas", "Alta",
                        "<b>Ajustar el presupuesto a la baja.</b> Revisar proyecciones de ingresos y "
                        "estructura de costos ante la tendencia decreciente, e investigar sus causas.")
            else:
                hallazgos.append(
                    f"<b>Alta incertidumbre.</b> Un R2 de {r2:.2f} indica que el consumo no sigue una "
                    f"tendencia lineal clara; la proyeccion es referencia, no certeza.")
                rec("Planificacion", "Alta",
                    "<b>Decidir con escenarios, no con un solo numero.</b> Usar el escenario pesimista "
                    "para el presupuesto base y complementar con analisis estacional y de nuevos "
                    "proyectos antes de comprometer inversiones de largo plazo.")
            rec("Planificacion", "Media",
                "<b>Planificar por bandas.</b> Trabajar con los escenarios optimista y pesimista, en "
                "lugar de un valor unico, permite tomar decisiones robustas frente a la variabilidad.")
        else:
            sintesis = ("No hay suficientes meses de datos para una proyeccion fiable bajo el filtro "
                        "actual. Amplie el rango de periodos para habilitar el analisis predictivo.")
            rec("Datos / Calidad", "Media",
                "<b>Ampliar la ventana de datos.</b> Reunir al menos 4 a 6 meses consecutivos permite "
                "estimar tendencias con un minimo de confianza estadistica.")

    # ── Nota metodológica (al pie, no es una recomendación) ──
    nota = ("Nota: estas conclusiones se generan automaticamente a partir de los datos filtrados y se "
            "recalculan al cambiar periodo, provincia, distrito o tarifa. Para cuantificar con precision "
            "las perdidas de energia y la eficiencia de cobranza (KPIs centrales del sector), el siguiente "
            "paso seria incorporar dos campos: energia inyectada por distrito y monto efectivamente "
            "recaudado; con los datos actuales ambos solo se infieren.")

    # Corrección de contracciones del español
    def _c(s): return s.replace(" de el ", " del ").replace(" a el ", " al ")
    sintesis = _c(sintesis)
    hallazgos = [_c(h) for h in hallazgos]
    for r in recs:
        r["texto"] = _c(r["texto"])

    return {"sintesis": sintesis, "hallazgos": hallazgos, "recomendaciones": recs, "nota": nota}


def generar_pdf(df: pd.DataFrame, df_full: pd.DataFrame, mod: str,
                sel_per, sel_prov: str, sel_dist: str, sel_tarifa: str, figuras: dict) -> bytes:

    from reportlab.pdfgen import canvas as rl_canvas
    from pypdf import PdfWriter, PdfReader

    # ── Colores corporativos ──
    AZUL_OSC  = colors.HexColor("#0a1428")
    AZUL_MED  = colors.HexColor("#1d4ed8")
    AZUL_CLAR = colors.HexColor("#3b82f6")
    VERDE     = colors.HexColor("#16a34a")
    AMBAR     = colors.HexColor("#f59e0b")
    GRIS_OSC  = colors.HexColor("#374151")
    GRIS_MED  = colors.HexColor("#64748b")
    GRIS_CLAR = colors.HexColor("#f8fafc")
    BORDE     = colors.HexColor("#e2e8f0")
    BLANCO    = colors.white
    PAGE_W, PAGE_H = A4

    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    per = periodo_a_label(sel_per) if sel_per != "Todos" else f"{per_min_label}-{per_max_label}"
    if sel_dist != "Todos":
        cobertura = sel_dist.title()
    elif sel_prov != "Todas":
        cobertura = sel_prov.title()
    else:
        cobertura = "Nacional"

    mod_info   = next((m for m in MODULOS if m["key"] == mod), MODULOS[0])
    accent_hex = mod_info["color"]

    styles = getSampleStyleSheet()
    s_sec = ParagraphStyle("Se", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold", textColor=AZUL_MED,
        spaceBefore=14, spaceAfter=6, leading=17)
    s_subsec = ParagraphStyle("Ss", parent=styles["Normal"],
        fontSize=10, fontName="Helvetica-Bold", textColor=GRIS_OSC,
        spaceBefore=8, spaceAfter=4, leading=13)
    s_nota = ParagraphStyle("N", parent=styles["Normal"],
        fontSize=7.5, fontName="Helvetica-Oblique",
        textColor=GRIS_MED, spaceAfter=4)
    s_footer = ParagraphStyle("F", parent=styles["Normal"],
        fontSize=7, fontName="Helvetica-Oblique",
        textColor=GRIS_MED, leading=10)
    s_footer_r = ParagraphStyle("FR", parent=styles["Normal"],
        fontSize=7, fontName="Helvetica",
        textColor=GRIS_MED, leading=10, alignment=TA_RIGHT)

    # ══════════════════════════════════════════════
    # PDF 1 — PORTADA con canvas puro
    # ══════════════════════════════════════════════
    buf_cover = io.BytesIO()
    c = rl_canvas.Canvas(buf_cover, pagesize=A4)
    W, H = PAGE_W, PAGE_H
    accent  = colors.HexColor(accent_hex)
    azul_os = colors.HexColor("#0a1428")
    azul_md = colors.HexColor("#0f2040")
    azul_lt = colors.HexColor("#1a3560")
    gris_sl = colors.HexColor("#94a3b8")
    celeste = colors.HexColor("#93c5fd")

    c.setFillColor(azul_os)
    c.roundRect(0.5*cm, 0.5*cm, W - 1*cm, H - 1*cm, 10, fill=1, stroke=0)
    c.setFillColor(azul_md)
    c.roundRect(0.5*cm, H - 3.1*cm, W - 1*cm, 2.6*cm, 10, fill=1, stroke=0)
    c.setFillColor(azul_os)
    c.rect(0.5*cm, H - 3.1*cm, W - 1*cm, 1.0*cm, fill=1, stroke=0)
    c.setStrokeColor(accent)
    c.setLineWidth(3)
    c.line(2.0*cm, H - 1.05*cm, W - 2.0*cm, H - 1.05*cm)
    c.setFillColor(gris_sl)
    c.setFont("Helvetica", 7.5)
    c.drawString(2.3*cm, H - 0.92*cm, "INFORME EJECUTIVO")
    c.setFillColor(celeste)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawRightString(W - 2.3*cm, H - 0.92*cm, f"MODULO {MOD_NUMBER[mod_info['key']]} DE 6")

    cx, cy = W / 2, H - 5.7*cm
    c.setFillColor(colors.HexColor("#0f2a50"))
    c.circle(cx, cy, 1.35*cm, fill=1, stroke=0)
    c.setFillColor(azul_lt)
    c.setStrokeColor(accent)
    c.setLineWidth(2.5)
    c.circle(cx, cy, 1.1*cm, fill=1, stroke=1)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(cx, cy - 0.28*cm, "E")

    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx, H - 7.8*cm, "ELECTRO UCAYALI S.A.")
    c.setFillColor(gris_sl)
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, H - 8.5*cm, "Sistema de Gestion Energetica")

    sep_y  = H - 9.4*cm
    dot_r  = 0.055*cm
    gap    = 0.38*cm
    n_dots = 7
    start_x = cx - (n_dots - 1) * gap / 2
    for i in range(n_dots):
        col = accent if i == n_dots // 2 else colors.HexColor("#1e3a5f")
        c.setFillColor(col)
        c.circle(start_x + i * gap, sep_y, dot_r, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#0d1f3c"))
    c.roundRect(cx - 3.2*cm, H - 10.7*cm, 6.4*cm, 0.85*cm, 5, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#1e3a5f"))
    c.setLineWidth(0.5)
    c.roundRect(cx - 3.2*cm, H - 10.7*cm, 6.4*cm, 0.85*cm, 5, fill=0, stroke=1)
    c.setFillColor(gris_sl)
    c.setFont("Helvetica", 8)
    c.drawCentredString(cx, H - 10.15*cm, "Informe Ejecutivo")

    titulo = MOD_LABELS[mod_info["key"]]
    words  = titulo.split()
    mid    = len(words) // 2
    if len(titulo) > 26:
        linea1 = " ".join(words[:mid])
        linea2 = " ".join(words[mid:])
    else:
        linea1 = titulo
        linea2 = ""

    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 22)
    if linea2:
        c.drawCentredString(cx, H - 11.9*cm, linea1)
        c.drawCentredString(cx, H - 12.9*cm, linea2)
        base_y = H - 13.9*cm
    else:
        c.drawCentredString(cx, H - 12.4*cm, linea1)
        base_y = H - 13.4*cm

    c.setStrokeColor(accent)
    c.setLineWidth(1.5)
    c.line(cx - 2.5*cm, base_y, cx + 2.5*cm, base_y)

    meta_y = base_y - 1.2*cm
    row_h  = 1.0*cm
    hay_filtro_reg = (sel_prov != "Todas" or sel_dist != "Todos" or sel_tarifa != "Todas" or sel_per != "Todos")
    if hay_filtro_reg:
        total_reg_pdf = int(df["n_titulares"].sum()) if "n_titulares" in df.columns else len(df)
    else:
        total_reg_pdf = TOTALES.get("total_registros", 1132087)

    meta = [
        ("Periodo analizado",    per),
        ("Cobertura geografica", cobertura),
        ("Registros incluidos",  f"{total_reg_pdf:,}"),
    ]
    for i, (lbl, val) in enumerate(meta):
        y      = meta_y - i * row_h
        bg_col = colors.HexColor("#0d1f3c") if i % 2 == 0 else colors.HexColor("#0a1830")
        c.setFillColor(bg_col)
        c.roundRect(2.0*cm, y - 0.32*cm, W - 4.0*cm, 0.76*cm, 4, fill=1, stroke=0)
        c.setFillColor(accent)
        c.roundRect(2.0*cm, y - 0.32*cm, 0.22*cm, 0.76*cm, 2, fill=1, stroke=0)
        c.setFillColor(gris_sl)
        c.setFont("Helvetica", 8)
        c.drawString(2.5*cm, y + 0.06*cm, lbl)
        c.setFillColor(BLANCO)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(W - 2.5*cm, y + 0.06*cm, val)

    c.setFillColor(colors.HexColor("#060e1e"))
    c.roundRect(0.5*cm, 0.5*cm, W - 1*cm, 1.8*cm, 10, fill=1, stroke=0)
    c.setFillColor(azul_os)
    c.rect(0.5*cm, 1.3*cm, W - 1*cm, 0.7*cm, fill=1, stroke=0)
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(2.0*cm, 2.05*cm, W - 2.0*cm, 2.05*cm)
    c.setFillColor(gris_sl)
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(2.3*cm, 1.05*cm, f"Generado el {now}")
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", 7)
    c.drawRightString(W - 2.3*cm, 1.05*cm, "USO INTERNO - CONFIDENCIAL")

    c.save()
    buf_cover.seek(0)

    # ══════════════════════════════════════════════
    # PDF 2 — CONTENIDO con SimpleDocTemplate
    # ══════════════════════════════════════════════
    buf_content = io.BytesIO()

    doc = SimpleDocTemplate(
        buf_content, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.2*cm, bottomMargin=1.8*cm
    )

    accent_col     = colors.HexColor(accent_hex)
    accent_col_mod = colors.HexColor(MOD_ACCENT.get(mod, "#1d4ed8"))

    def header_pagina():
        hdr = Table([[
            Paragraph(
                f"<b>ELECTRO UCAYALI S.A.</b> · {MOD_LABELS[mod]}",
                ParagraphStyle("h", fontSize=8, fontName="Helvetica",
                               textColor=BLANCO, leading=11)),
            Paragraph(
                f"Generado: {now}",
                ParagraphStyle("hr", fontSize=8, fontName="Helvetica",
                               textColor=colors.HexColor("#93c5fd"),
                               leading=11, alignment=TA_RIGHT)),
        ]], colWidths=[PAGE_W - 3.6*cm - 4.5*cm, 4.5*cm])
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), AZUL_OSC),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (0,0),   12),
            ("RIGHTPADDING",  (-1,-1), (-1,-1), 12),
            ("ROUNDEDCORNERS", [6]),
        ]))
        return hdr

    def rl_tabla(df_tbl: pd.DataFrame, accent=AZUL_MED) -> Table:
        cols   = df_tbl.columns.tolist()
        n_cols = len(cols)
        avail_w = PAGE_W - 3.6*cm
        col_w   = avail_w / n_cols
        header_row = [
            Paragraph(f"<b>{col}</b>", ParagraphStyle("TH", fontSize=8,
                fontName="Helvetica-Bold", textColor=BLANCO,
                alignment=TA_CENTER, leading=10))
            for col in cols
        ]
        data = [header_row]
        for _, row in df_tbl.iterrows():
            fila = []
            for val in row:
                fila.append(Paragraph(str(val), ParagraphStyle("TD", fontSize=8,
                    fontName="Helvetica", textColor=GRIS_OSC,
                    alignment=TA_LEFT, leading=10)))
            data.append(fila)
        t = Table(data, colWidths=[col_w]*n_cols, repeatRows=1)
        n_rows = len(data)
        style_cmds = [
            ("BACKGROUND",    (0,0), (-1,0),   accent),
            ("TEXTCOLOR",     (0,0), (-1,0),   BLANCO),
            ("FONTNAME",      (0,0), (-1,0),   "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0),   8),
            ("ALIGN",         (0,0), (-1,0),   "CENTER"),
            ("VALIGN",        (0,0), (-1,-1),  "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1),  5),
            ("BOTTOMPADDING", (0,0), (-1,-1),  5),
            ("LEFTPADDING",   (0,0), (-1,-1),  6),
            ("RIGHTPADDING",  (0,0), (-1,-1),  6),
            ("LINEBELOW",     (0,0), (-1,0),   0.5, accent),
            ("LINEBELOW",     (0,1), (-1,-1),  0.3, BORDE),
            ("BOX",           (0,0), (-1,-1),  0.5, BORDE),
        ]
        for i in range(1, n_rows):
            bg = GRIS_CLAR if i % 2 == 0 else BLANCO
            style_cmds.append(("BACKGROUND", (0,i), (-1,i), bg))
        t.setStyle(TableStyle(style_cmds))
        return t

    story = []
    story.append(header_pagina())
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"{mod_info['icon']} {MOD_LABELS[mod]}", s_sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_col, spaceAfter=8))

    hay_filtro_reg = (sel_prov != "Todas" or sel_dist != "Todos" or sel_tarifa != "Todas" or sel_per != "Todos")
    if hay_filtro_reg:
        total_reg_pdf = int(df["n_titulares"].sum()) if "n_titulares" in df.columns else len(df)
    else:
        total_reg_pdf = TOTALES.get("total_registros", 1132087)

    resumen_data = [
        ["Periodo",    per],
        ["Cobertura",  cobertura],
        ["Registros",  f"{total_reg_pdf:,}"],
        ["Distritos",  str(df["distrito"].nunique())],
        ["Provincias", str(df["provincia"].nunique())],
    ]
    res_tbl = Table(resumen_data, colWidths=[4*cm, PAGE_W-3.6*cm-4*cm])
    res_tbl.setStyle(TableStyle([
        ("FONTNAME",      (0,0), (0,-1),  "Helvetica-Bold"),
        ("FONTNAME",      (1,0), (1,-1),  "Helvetica"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("TEXTCOLOR",     (0,0), (0,-1),  GRIS_MED),
        ("TEXTCOLOR",     (1,0), (1,-1),  GRIS_OSC),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW",     (0,0), (-1,-1), 0.3, BORDE),
        ("BACKGROUND",    (0,0), (0,-1),  GRIS_CLAR),
    ]))
    story.append(res_tbl)
    story.append(Spacer(1, 14))

    # ── Conclusiones e interpretación ejecutiva (dinámicas por módulo y filtros) ──
    try:
        concl = construir_conclusiones(
            mod, df, df_full, sel_per, sel_prov, sel_dist, sel_tarifa
        )
    except Exception:
        concl = {"sintesis": "", "hallazgos": [], "recomendaciones": [], "nota": ""}

    if concl.get("sintesis") or concl.get("hallazgos") or concl.get("recomendaciones"):
        CONT_W = PAGE_W - 3.6 * cm           # ancho útil de la página
        story.append(Paragraph("Conclusiones e interpretacion ejecutiva", s_sec))
        story.append(HRFlowable(width="100%", thickness=1.5, color=accent_col, spaceAfter=10))

        s_sint = ParagraphStyle(
            "Sint", parent=styles["Normal"], fontSize=9.5, fontName="Helvetica",
            textColor=GRIS_OSC, leading=14, alignment=TA_JUSTIFY,
        )
        s_bul = ParagraphStyle(
            "Bul", parent=styles["Normal"], fontSize=9.5, fontName="Helvetica",
            textColor=GRIS_OSC, leading=13.5, leftIndent=12, bulletIndent=2, spaceAfter=6,
        )
        s_rec = ParagraphStyle(
            "Rec", parent=styles["Normal"], fontSize=9.5, fontName="Helvetica",
            textColor=GRIS_OSC, leading=13.5,
        )
        s_num = ParagraphStyle(
            "Num", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold",
            textColor=colors.white, alignment=TA_CENTER, leading=13,
        )
        s_foot = ParagraphStyle(
            "Foot", parent=styles["Normal"], fontSize=7.5, fontName="Helvetica-Oblique",
            textColor=GRIS_MED, leading=10, spaceBefore=8,
        )

        # 1) Síntesis ejecutiva: callout con barra lateral de color (sin choques)
        if concl.get("sintesis"):
            story.append(Paragraph("Sintesis ejecutiva", s_subsec))
            callout = Table([["", Paragraph(concl["sintesis"], s_sint)]],
                            colWidths=[4, CONT_W - 4])
            callout.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (0, 0), accent_col),
                ("BACKGROUND",   (1, 0), (1, 0), GRIS_CLAR),
                ("LEFTPADDING",  (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("LEFTPADDING",  (1, 0), (1, 0), 11),
                ("RIGHTPADDING", (1, 0), (1, 0), 11),
                ("TOPPADDING",   (1, 0), (1, 0), 10),
                ("BOTTOMPADDING",(1, 0), (1, 0), 10),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
                ("LINEABOVE",    (0, 0), (-1, 0), 0.5, colors.HexColor("#e2e8f0")),
                ("LINEBELOW",    (0, 0), (-1, 0), 0.5, colors.HexColor("#e2e8f0")),
            ]))
            story.append(callout)
            story.append(Spacer(1, 12))

        # 2) Hallazgos clave
        if concl.get("hallazgos"):
            story.append(Paragraph("Hallazgos clave", s_subsec))
            for txt in concl["hallazgos"]:
                story.append(Paragraph(txt, s_bul, bulletText="•"))
            story.append(Spacer(1, 8))

        # 3) Recomendaciones y decisiones: plan de acción numerado con área/prioridad
        recs = concl.get("recomendaciones", [])
        if recs:
            story.append(Paragraph("Recomendaciones y decisiones", s_subsec))
            filas = []
            for i, r in enumerate(recs, 1):
                prio = r.get("prio", "Media")
                col_prio = "#dc2626" if prio.lower().startswith("alt") else "#64748b"
                badge = Table([[Paragraph(str(i), s_num)]], colWidths=[18], rowHeights=[18])
                badge.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), accent_col),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]))
                tag = (f'<font color="{col_prio}" size="7"><b>{r.get("area","").upper()}'
                       f' &nbsp;·&nbsp; PRIORIDAD {prio.upper()}</b></font>'
                       f'<br/>{r.get("texto","")}')
                filas.append([badge, Paragraph(tag, s_rec)])
            tabla_rec = Table(filas, colWidths=[26, CONT_W - 26])
            estilo = [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("LEFTPADDING", (1, 0), (1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e2e8f0")),
            ]
            tabla_rec.setStyle(TableStyle(estilo))
            story.append(tabla_rec)

        # 4) Nota metodológica (al pie, en gris pequeño)
        if concl.get("nota"):
            story.append(Paragraph(concl["nota"], s_foot))

        story.append(Spacer(1, 16))

    # Gráficos
    if figuras:
        story.append(Paragraph("Visualizaciones", s_sec))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDE, spaceAfter=8))
        for tit, fig in figuras.items():
            story.append(Paragraph(tit, s_subsec))
            img_b = fig_to_image(fig, width=900, height=370)
            if img_b:
                img_h = (PAGE_W - 3.6*cm) * 370 / 900
                story.append(RLImage(io.BytesIO(img_b),
                                     width=PAGE_W - 3.6*cm,
                                     height=img_h))
            else:
                story.append(Paragraph(
                    "Grafico no disponible — instala kaleido: pip install kaleido",
                    s_nota))
            story.append(Spacer(1, 10))

    story.append(Spacer(1, 6))
    story.append(Paragraph("Datos detallados", s_sec))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDE, spaceAfter=8))

    if mod == "CONSUMO":
        by_per = (
            df.groupby("periodo")
            .agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"))
            .reset_index().sort_values("periodo", ascending=False)
        )
        by_per["label"]  = by_per["periodo"].apply(periodo_a_label)
        by_per["precio"] = (by_per["fact"] / by_per["kwh"].replace(0, np.nan)).fillna(0).round(4)
        tbl_df = pd.DataFrame({
            "Periodo":          by_per["label"],
            "Consumo (kWh)":    by_per["kwh"].apply(fmt),
            "Facturacion (S/)": by_per["fact"].apply(fmt_soles),
            "Precio S/kWh":     by_per["precio"].apply(lambda x: f"{x:.4f}"),
        })
        story.append(Paragraph("Detalle mensual de consumo y facturacion", s_subsec))
        story.append(rl_tabla(tbl_df, accent_col_mod))

    elif mod == "GEOGRAFIA":
        by_dist = (
            df.groupby(["provincia","distrito"])
            .agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"),
                 registros=("n_titulares","sum"))
            .reset_index().sort_values("kwh", ascending=False)
        )
        by_dist["precio"] = (by_dist["fact"] / by_dist["kwh"].replace(0,1)).round(4)
        by_dist["pct"]    = (by_dist["kwh"] / by_dist["kwh"].sum() * 100).round(1)
        by_dist.insert(0, "#", range(1, len(by_dist)+1))
        tbl_df = pd.DataFrame({
            "#":             by_dist["#"],
            "Distrito":      by_dist["distrito"],
            "Provincia":     by_dist["provincia"],
            "Consumo (kWh)": by_dist["kwh"].apply(fmt),
            "% total":       by_dist["pct"].apply(lambda x: f"{x:.1f}%"),
            "Facturacion":   by_dist["fact"].apply(fmt_soles),
            "Precio S/kWh":  by_dist["precio"].apply(lambda x: f"{x:.4f}"),
            "Registros":     by_dist["registros"].apply(lambda x: f"{x:,}"),
        })
        story.append(Paragraph("Ranking de distritos por consumo", s_subsec))
        story.append(rl_tabla(tbl_df, accent_col_mod))

    elif mod == "TARIFAS":
        by_tar = df.groupby("tarifa").agg(
            kwh=("consumo_kwh","sum"), fact=("facturacion","sum"),
            registros=("n_titulares","sum"),
        ).reset_index().sort_values("kwh", ascending=False)
        by_tar["precio"]   = (by_tar["fact"] / by_tar["kwh"].replace(0,1)).round(4)
        by_tar["pct_kwh"]  = (by_tar["kwh"] / by_tar["kwh"].sum() * 100).round(1)
        by_tar["pct_fact"] = (by_tar["fact"] / by_tar["fact"].sum() * 100).round(1)
        tbl_df = pd.DataFrame({
            "Tarifa":        by_tar["tarifa"],
            "Consumo (kWh)": by_tar["kwh"].apply(fmt),
            "% consumo":     by_tar["pct_kwh"].apply(lambda x: f"{x:.1f}%"),
            "Facturacion":   by_tar["fact"].apply(fmt_soles),
            "% facturacion": by_tar["pct_fact"].apply(lambda x: f"{x:.1f}%"),
            "Precio S/kWh":  by_tar["precio"].apply(lambda x: f"{x:.4f}"),
            "Registros":     by_tar["registros"].apply(lambda x: f"{x:,}"),
        })
        story.append(Paragraph("Detalle por tipo de tarifa", s_subsec))
        story.append(rl_tabla(tbl_df, accent_col_mod))

    elif mod == "CLIENTES":
        by_status = df.groupby("status_cliente").agg(
            kwh=("consumo_kwh","sum"), fact=("facturacion","sum"),
            registros=("n_titulares","sum"),
        ).reset_index().sort_values("registros", ascending=False)
        by_status["kwh_prom"]  = (by_status["kwh"] / by_status["registros"].replace(0,1)).round(2)
        by_status["fact_prom"] = (by_status["fact"] / by_status["registros"].replace(0,1)).round(2)
        by_status["pct"]       = (by_status["registros"] / by_status["registros"].sum() * 100).round(1)
        tbl_df = pd.DataFrame({
            "Status":         by_status["status_cliente"],
            "Registros":      by_status["registros"].apply(lambda x: f"{x:,}"),
            "% total":        by_status["pct"].apply(lambda x: f"{x:.1f}%"),
            "kWh total":      by_status["kwh"].apply(fmt),
            "kWh promedio":   by_status["kwh_prom"].apply(lambda x: f"{x:.1f}"),
            "Facturacion":    by_status["fact"].apply(fmt_soles),
            "Fact. promedio": by_status["fact_prom"].apply(lambda x: f"S/ {x:.2f}"),
        })
        story.append(Paragraph("Resumen por status de cliente", s_subsec))
        story.append(rl_tabla(tbl_df, accent_col_mod))

        # Tabla antigüedad en PDF — misma lógica que Fase 12
        hay_filtro_pdf = (sel_prov != "Todas" or sel_dist != "Todos" or sel_tarifa != "Todas" or sel_per != "Todos")
        ult_per_pdf    = df["periodo"].max()
        if hay_filtro_pdf:
            df_ult_pdf = df[df["periodo"] == ult_per_pdf]
            total_tit  = int(df_ult_pdf["n_titulares"].sum())       if "n_titulares"      in df.columns else 0
            mas10      = int(df_ult_pdf["titulares_mas_10"].sum())   if "titulares_mas_10" in df.columns else 0
            cinco10    = int(df_ult_pdf["titulares_5_10"].sum())     if "titulares_5_10"   in df.columns else 0
            menos5     = int(df_ult_pdf["titulares_menos_5"].sum())  if "titulares_menos_5" in df.columns else 0
        else:
            ult_per_full = df_full["periodo"].max()
            df_ult_full  = df_full[df_full["periodo"] == ult_per_full]
            total_tit    = TOTALES.get("total_titulares",   int(df_ult_full["n_titulares"].sum()))
            mas10        = TOTALES.get("titulares_mas_10",  int(df_ult_full["titulares_mas_10"].sum()))
            cinco10      = TOTALES.get("titulares_5_10",    int(df_ult_full["titulares_5_10"].sum()))
            menos5       = TOTALES.get("titulares_menos_5", int(df_ult_full["titulares_menos_5"].sum()))
        if total_tit > 0:
            ant_df = pd.DataFrame({
                "Segmento":      ["Consolidados +10 años", "Intermedios 5-10 años", "Nuevos <5 años"],
                "Titulares":     [f"{mas10:,}", f"{cinco10:,}", f"{menos5:,}"],
                "Participacion": [f"{mas10/total_tit*100:.1f}%",
                                  f"{cinco10/total_tit*100:.1f}%",
                                  f"{menos5/total_tit*100:.1f}%"],
            })
            story.append(Spacer(1, 8))
            story.append(Paragraph("Segmentacion por antiguedad de titulares", s_subsec))
            story.append(rl_tabla(ant_df, accent_col_mod))

    elif mod == "EFICIENCIA":
        tbl_ef = df.groupby("periodo").agg(
            kwh=("consumo_kwh","sum"), fact=("facturacion","sum"),
            n=("n_titulares","sum"),
        ).reset_index().sort_values("periodo", ascending=False)
        tbl_ef["label"]  = tbl_ef["periodo"].apply(periodo_a_label)
        tbl_ef["ticket"] = (tbl_ef["fact"] / tbl_ef["n"].replace(0,1)).round(2)
        tbl_ef["kwh_n"]  = (tbl_ef["kwh"] / tbl_ef["n"].replace(0,1)).round(2)
        tbl_ef["precio"] = (tbl_ef["fact"] / tbl_ef["kwh"].replace(0,1)).round(4)
        tbl_df = pd.DataFrame({
            "Periodo":       tbl_ef["label"],
            "Consumo (kWh)": tbl_ef["kwh"].apply(fmt),
            "Facturacion":   tbl_ef["fact"].apply(fmt_soles),
            "kWh/registro":  tbl_ef["kwh_n"].apply(lambda x: f"{x:.1f}"),
            "Ticket prom.":  tbl_ef["ticket"].apply(lambda x: f"S/ {x:.2f}"),
            "Precio S/kWh":  tbl_ef["precio"].apply(lambda x: f"{x:.4f}"),
            "N registros":   tbl_ef["n"].apply(lambda x: f"{x:,}"),
        })
        story.append(Paragraph("Resumen mensual de eficiencia operacional", s_subsec))
        story.append(rl_tabla(tbl_df, accent_col_mod))

    elif mod == "PROYECCION":
        by_per_proj = (
            df.groupby("periodo")["consumo_kwh"]
            .sum().reset_index().sort_values("periodo")
        )
        by_per_proj.columns = ["periodo", "valor"]
        by_per_proj["label"] = by_per_proj["periodo"].apply(periodo_a_label)
        n_puntos = len(by_per_proj)
        if n_puntos >= 4:
            x_idx  = np.arange(n_puntos)
            y_vals = by_per_proj["valor"].values.astype(float)
            coeffs = np.polyfit(x_idx, y_vals, 1)
            sigma  = np.std(y_vals - np.polyval(coeffs, x_idx))
            last_per = int(by_per_proj["periodo"].iloc[-1])
            anio_f, mes_f = last_per // 100, last_per % 100
            fut_labels, y_fut, y_opt, y_pes = [], [], [], []
            for i in range(6):
                mes_f += 1
                if mes_f > 12: mes_f = 1; anio_f += 1
                fut_labels.append(f"{MESES_CORTO[mes_f-1]} {str(anio_f)[2:]}")
                y_c = max(0, np.polyval(coeffs, n_puntos+i))
                y_fut.append(y_c)
                y_opt.append(max(0, y_c+sigma))
                y_pes.append(max(0, y_c-sigma))
            tbl_df = pd.DataFrame({
                "Periodo":         fut_labels,
                "Central (kWh)":   [fmt(v) for v in y_fut],
                "Optimista (kWh)": [fmt(v) for v in y_opt],
                "Pesimista (kWh)": [fmt(v) for v in y_pes],
                "Var. vs ultimo":  [
                    f"{((v-y_vals[-1])/y_vals[-1]*100):+.1f}%" if y_vals[-1]>0 else "N/A"
                    for v in y_fut
                ],
            })
            story.append(Paragraph("Proyeccion de consumo - proximos 6 meses", s_subsec))
            story.append(rl_tabla(tbl_df, accent_col_mod))
        else:
            story.append(Paragraph("Datos insuficientes para proyeccion.", s_nota))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDE, spaceAfter=6))
    ftbl = Table([[
        Paragraph("Electro Ucayali S.A. — Informe generado automaticamente. "
                  "Uso interno exclusivo.", s_footer),
        Paragraph(f"Modulo {MOD_NUMBER[mod]}/6 · {now}", s_footer_r),
    ]], colWidths=[PAGE_W-3.6*cm-3.5*cm, 3.5*cm])
    ftbl.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",  (0,0), (-1,-1), 0),
    ]))
    story.append(ftbl)

    doc.build(story)
    buf_content.seek(0)

    writer = PdfWriter()
    for reader in [PdfReader(buf_cover), PdfReader(buf_content)]:
        for page in reader.pages:
            writer.add_page(page)

    buf_final = io.BytesIO()
    writer.write(buf_final)
    buf_final.seek(0)
    return buf_final.read()

st.markdown("---")

# ##############################################################################
# FASE 9 — MÓDULO 1: CONSUMO ENERGÉTICO
# ##############################################################################

if mod == "CONSUMO":
    st.markdown("## ⚡ Consumo Energético")
    st.caption("Evolución mensual de kWh consumidos, estacionalidad y relación con facturación")

    total_kwh  = df["consumo_kwh"].sum()
    total_fact = df["facturacion"].sum()
    precio_imp = (total_fact / total_kwh) if total_kwh > 0 else 0

    by_per = (
        df.groupby("periodo")
        .agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"))
        .reset_index()
        .sort_values("periodo")
    )
    by_per["label"] = by_per["periodo"].apply(periodo_a_label)
    kwh_prom = by_per["kwh"].mean() if len(by_per) > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Consumo total acumulado", f"{total_kwh/1e6:.2f}M kWh", f"{len(by_per)} períodos")
    k2.metric("Facturación total", fmt_soles(total_fact), "período filtrado")
    k3.metric("Consumo mensual promedio", f"{kwh_prom/1e3:.1f}K kWh", "por período")
    k4.metric("Precio implícito", f"S/ {precio_imp:.4f}/kWh", "facturación / consumo")

    st.markdown("")

    n_per = len(by_per)
    st.markdown("**Evolución mensual del consumo (kWh)**")
    max_kwh    = by_per["kwh"].max() if n_per > 0 else 0
    bar_colors = [
        "#16a34a" if v == max_kwh else "#93c5fd"
        for v in by_per["kwh"]
    ]
    fig_c = go.Figure()
    fig_c.add_trace(go.Bar(
        x=by_per["label"], y=by_per["kwh"] / 1e3,
        marker_color=bar_colors, marker_cornerradius=4,
        text=[f"{v/1e3:.1f}K" for v in by_per["kwh"]],
        textposition="outside", textfont=dict(size=9, color=TXT),
        hovertemplate="<b>%{x}</b>: %{y:.1f}K kWh<extra></extra>",
    ))
    if n_per >= 4:
        x_idx   = np.arange(n_per)
        coeffs  = np.polyfit(x_idx, by_per["kwh"].values / 1e3, 1)
        trend_y = np.polyval(coeffs, x_idx)
        fig_c.add_trace(go.Scatter(
            x=by_per["label"], y=trend_y,
            mode="lines", name="Tendencia",
            line=dict(color="#f59e0b", width=2, dash="dash"),
            hovertemplate="Tendencia %{x}: %{y:.1f}K<extra></extra>",
        ))
    layout_c = base_layout(300)
    layout_c["margin"] = dict(l=55, r=20, t=35, b=80)
    fig_c.update_layout(**layout_c, showlegend=n_per >= 4)
    fig_c.update_xaxes(**axis_x_mensual(n_per))
    fig_c.update_yaxes(
        title="Consumo (K kWh)", ticksuffix="K",
        tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
    )
    st.plotly_chart(fig_c, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Consumo promedio por mes del año (estacionalidad)**")
        st.caption("Solo clientes con status NORMAL")
        df_norm = df[df["status_cliente"] == "NORMAL"]
        by_mes = df_norm.groupby("mes")["consumo_kwh"].mean().reindex(range(1,13), fill_value=0)
        mes_v  = [by_mes[i] for i in range(1,13)]
        max_m  = max(mes_v) if any(v>0 for v in mes_v) else 1
        min_m  = min(v for v in mes_v if v > 0) if any(v>0 for v in mes_v) else 0
        bar_cm = ["#16a34a" if v==max_m else ("#e03131" if v==min_m else "#93c5fd") for v in mes_v]
        fig_mes = go.Figure(go.Bar(
            x=MESES_CORTO, y=mes_v,
            marker_color=bar_cm, marker_cornerradius=4,
            text=[f"{v/1e3:.1f}K" for v in mes_v], textposition="outside",
            textfont=dict(size=9, color=TXT),
            hovertemplate="<b>%{x}</b>: %{y:,.0f} kWh prom.<extra></extra>",
        ))
        fig_mes.update_layout(**base_layout(280), showlegend=False)
        fig_mes.update_xaxes(tickfont=dict(color=TXT, size=10))
        fig_mes.update_yaxes(
            title="kWh promedio", ticksuffix="K",
            tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
            gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
        )
        st.plotly_chart(fig_mes, use_container_width=True)

    with col_b:
        st.markdown("**Evolución mensual de facturación (S/)**")
        max_f = by_per["fact"].max() if len(by_per) > 0 else 0
        bar_cf = ["#f59e0b" if v == max_f else "#fde68a" for v in by_per["fact"]]
        fig_fact = go.Figure(go.Bar(
            x=by_per["label"], y=by_per["fact"] / 1e3,
            marker_color=bar_cf, marker_cornerradius=4,
            text=[f"S/{v/1e3:.1f}K" for v in by_per["fact"]],
            textposition="outside", textfont=dict(size=9, color="#92400e"),
            hovertemplate="<b>%{x}</b>: S/ %{y:.1f}K<extra></extra>",
        ))
        layout_f = base_layout(280)
        layout_f["margin"] = dict(l=55, r=20, t=35, b=80)
        fig_fact.update_layout(**layout_f, showlegend=False)
        fig_fact.update_xaxes(**axis_x_mensual(n_per))
        fig_fact.update_yaxes(
            title="Facturación (K S/)", ticksuffix="K",
            tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
            gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
        )
        st.plotly_chart(fig_fact, use_container_width=True)

    st.markdown("**Precio implícito mensual (S/ por kWh)**")
    by_per["precio"] = (by_per["fact"] / by_per["kwh"].replace(0, np.nan)).fillna(0).round(4)
    fig_prec = go.Figure(go.Scatter(
        x=by_per["label"], y=by_per["precio"],
        mode="lines+markers",
        line=dict(color="#8b5cf6", width=2.5),
        marker=dict(size=7, color="#8b5cf6"),
        fill="tozeroy", fillcolor="rgba(139,92,246,0.08)",
        hovertemplate="<b>%{x}</b>: S/ %{y:.4f}/kWh<extra></extra>",
    ))
    layout_p = base_layout(220)
    layout_p["margin"] = dict(l=65, r=20, t=30, b=80)
    fig_prec.update_layout(**layout_p, showlegend=False)
    fig_prec.update_xaxes(**axis_x_mensual(n_per))
    fig_prec.update_yaxes(
        title="S/ por kWh",
        tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False,
    )
    st.plotly_chart(fig_prec, use_container_width=True)

    st.markdown("**Detalle mensual**")
    tbl_show = pd.DataFrame({
        "periodo": by_per["periodo"],
        "Período": by_per["label"],
        "Consumo (kWh)": by_per["kwh"].apply(fmt),
        "Facturación": by_per["fact"].apply(fmt_soles),
        "Precio impl. (S/·kWh)": by_per["precio"].apply(lambda x: f"{x:.4f}"),
    })
    tbl_show = (
        tbl_show.sort_values("periodo", ascending=False)
        .drop(columns="periodo")
    )
    st.dataframe(tbl_show, use_container_width=True, hide_index=True)

    st.session_state["figuras_CONSUMO"] = {
        "Evolución mensual del consumo": fig_c,
        "Estacionalidad mensual": fig_mes,
        "Precio implícito mensual": fig_prec,
    }

# ##############################################################################
# FASE 10 — MÓDULO 2: GEOGRAFÍA
# ##############################################################################

elif mod == "GEOGRAFIA":
    st.markdown("## 🗺️ Geografía y Análisis Territorial")
    st.caption(f"Distribución del consumo y facturación por distrito — {df['distrito'].nunique()} distritos activos")

    by_dist = (
        df.groupby(["provincia","distrito"])
        .agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"),
             registros=("n_titulares","sum"))
        .reset_index()
        .sort_values("kwh", ascending=False)
    )
    by_dist["precio"] = (by_dist["fact"] / by_dist["kwh"].replace(0,1)).round(4)
    by_dist["pct"]    = (by_dist["kwh"] / by_dist["kwh"].sum() * 100).round(1)
    by_dist["etiq"]   = by_dist["distrito"] + "\n(" + by_dist["provincia"].str[:8] + ")"

    hay_filtro_geo = (sel_prov != "Todas" or sel_dist != "Todos" or sel_tarifa != "Todas" or sel_per != "Todos")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Distritos activos", df["distrito"].nunique(), f"{df['provincia'].nunique()} provincias")
    top_d = by_dist.iloc[0]
    k2.metric("Mayor consumo", top_d["distrito"], fmt(top_d["kwh"])+" kWh")
    k3.metric("Mayor facturación", by_dist.loc[by_dist["fact"].idxmax(),"distrito"],
              fmt_soles(by_dist["fact"].max()))
    if hay_filtro_geo:
        total_reg_mostrar = int(df["n_titulares"].sum())
        label_reg = f"{df['periodo'].nunique()} períodos acumulados"
    else:
        total_reg_mostrar = TOTALES.get("total_registros", 1132087)
        label_reg = "registros facturados en el año"
    k4.metric("Registros facturados", f"{total_reg_mostrar:,}", label_reg)

    st.markdown("")

    st.markdown("**Consumo total por distrito (kWh)**")
    dist_s = by_dist.sort_values("kwh", ascending=True)
    pal_ext = LINE_PALETTE * 3
    bar_col = [pal_ext[i % len(pal_ext)] for i in range(len(dist_s))]

    fig_dist = go.Figure(go.Bar(
        x=dist_s["kwh"] / 1e3,
        y=dist_s["distrito"],
        orientation="h",
        marker_color=bar_col,
        marker_cornerradius=3,
        text=[f"{v/1e3:.0f}K" for v in dist_s["kwh"]],
        textposition="outside",
        textfont=dict(color=TXT, size=10),
        customdata=dist_s["provincia"],
        hovertemplate="<b>%{y}</b> (%{customdata})<br>%{x:.1f}K kWh<extra></extra>",
    ))
    n_dist = len(dist_s)
    fig_dist.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        font=FONT_DICT,
        margin=dict(l=130, r=90, t=15, b=15),
        height=max(340, n_dist * 28),
        showlegend=False,
        xaxis=dict(gridcolor="#f1f5f9", ticksuffix="K", zeroline=False,
                   tickfont=dict(color=TXT), title_font=dict(color=TXT),
                   title="Consumo (K kWh)"),
        yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(color=TXT, size=11),
                   title_font=dict(color=TXT), automargin=True),
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Facturación por distrito (S/)**")
        dist_fs = by_dist.sort_values("fact", ascending=True)
        fig_df = go.Figure(go.Bar(
            x=dist_fs["fact"] / 1e3, y=dist_fs["distrito"],
            orientation="h",
            marker_color=[pal_ext[i % len(pal_ext)] for i in range(len(dist_fs))],
            marker_cornerradius=3,
            text=[f"S/{v/1e3:.0f}K" for v in dist_fs["fact"]],
            textposition="outside", textfont=dict(color=TXT, size=9),
            hovertemplate="<b>%{y}</b>: S/ %{x:.1f}K<extra></extra>",
        ))
        fig_df.update_layout(
            plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
            margin=dict(l=130, r=80, t=15, b=15),
            height=max(320, n_dist * 26), showlegend=False,
            xaxis=dict(gridcolor="#f1f5f9", ticksuffix="K", zeroline=False,
                       tickfont=dict(color=TXT), title="Facturación (K S/)"),
            yaxis=dict(tickfont=dict(color=TXT, size=10), automargin=True),
        )
        st.plotly_chart(fig_df, use_container_width=True)

    with col_g2:
        st.markdown("**Precio implícito por distrito (S/·kWh)**")
        dist_ps  = by_dist[by_dist["kwh"]>0].sort_values("precio", ascending=True)
        median_p = dist_ps["precio"].median()
        bar_cp   = ["#e03131" if v > median_p*1.15 else "#3b5bdb" for v in dist_ps["precio"]]
        fig_prec = go.Figure(go.Bar(
            x=dist_ps["precio"], y=dist_ps["distrito"],
            orientation="h",
            marker_color=bar_cp, marker_cornerradius=3,
            text=[f"S/{v:.4f}" for v in dist_ps["precio"]],
            textposition="outside", textfont=dict(color=TXT, size=9),
            hovertemplate="<b>%{y}</b>: S/ %{x:.4f}/kWh<extra></extra>",
        ))
        fig_prec.update_layout(
            plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
            margin=dict(l=130, r=90, t=15, b=15),
            height=max(320, n_dist * 26), showlegend=False,
            xaxis=dict(gridcolor="#f1f5f9", zeroline=False,
                       tickfont=dict(color=TXT), title="S/ por kWh"),
            yaxis=dict(tickfont=dict(color=TXT, size=10), automargin=True),
        )
        st.plotly_chart(fig_prec, use_container_width=True)

    st.markdown("**Evolución mensual de consumo — Top 6 distritos**")
    top6_dist = by_dist.head(6)["distrito"].tolist()
    by_dm = (
        df[df["distrito"].isin(top6_dist)]
        .groupby(["periodo","distrito"])["consumo_kwh"]
        .sum().reset_index().sort_values("periodo")
    )
    by_dm["label"] = by_dm["periodo"].apply(periodo_a_label)
    periodos_unicos = sorted(by_dm["periodo"].unique())

    fig_dm = go.Figure()
    for i, dist in enumerate(top6_dist):
        sub = by_dm[by_dm["distrito"]==dist]
        fig_dm.add_trace(go.Scatter(
            x=sub["label"], y=sub["consumo_kwh"]/1e3,
            name=dist, mode="lines+markers",
            line=dict(color=pal_ext[i], width=2.2),
            marker=dict(size=6),
            hovertemplate=f"<b>{dist}</b> %{{x}}: %{{y:.1f}}K kWh<extra></extra>",
        ))
    layout_dm = base_layout(300)
    layout_dm["margin"] = dict(l=55, r=20, t=40, b=80)
    fig_dm.update_layout(**layout_dm)
    fig_dm.update_layout(legend=dict(orientation="h", y=1.12,
                                     font=dict(size=10, color=TXT),
                                     bgcolor="rgba(0,0,0,0)"))
    fig_dm.update_xaxes(**axis_x_mensual(len(periodos_unicos)))
    fig_dm.update_yaxes(
        title="Consumo (K kWh)", ticksuffix="K",
        tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
    )
    st.plotly_chart(fig_dm, use_container_width=True)

    st.markdown("**Ranking completo de distritos**")
    rank = by_dist.reset_index(drop=True).copy()
    rank.insert(0, "#", range(1, len(rank)+1))
    tbl_g = pd.DataFrame({
        "#": rank["#"],
        "Distrito": rank["distrito"],
        "Provincia": rank["provincia"],
        "Consumo (kWh)": rank["kwh"].apply(fmt),
        "% del total": rank["pct"].apply(lambda x: f"{x:.1f}%"),
        "Facturación": rank["fact"].apply(fmt_soles),
        "Precio S/·kWh": rank["precio"].apply(lambda x: f"{x:.4f}"),
        "N° registros": rank["registros"].apply(lambda x: f"{x:,}"),
    })
    st.dataframe(tbl_g, use_container_width=True, hide_index=True)

    st.session_state["figuras_GEOGRAFIA"] = {
        "Consumo por distrito (kWh)": fig_dist,
        "Evolución mensual Top 6 distritos": fig_dm,
        "Precio implícito por distrito": fig_prec,
    }

# ##############################################################################
# FASE 11 — MÓDULO 3: TARIFAS
# ##############################################################################

elif mod == "TARIFAS":
    st.markdown("## 💰 Estructura Tarifaria")
    _tarifas_txt = " · ".join(sorted(df["tarifa"].dropna().unique().tolist())) or "sin tarifas"
    st.caption(f"Distribución de registros, consumo y precio por tipo de tarifa ({_tarifas_txt})")

    by_tar = df.groupby("tarifa").agg(
        kwh=("consumo_kwh","sum"),
        fact=("facturacion","sum"),
        registros=("n_titulares","sum"),
    ).reset_index().sort_values("kwh", ascending=False)
    by_tar["precio"]   = (by_tar["fact"] / by_tar["kwh"].replace(0,1)).round(4)
    by_tar["pct_kwh"]  = (by_tar["kwh"] / by_tar["kwh"].sum() * 100).round(1)
    by_tar["pct_fact"] = (by_tar["fact"] / by_tar["fact"].sum() * 100).round(1)
    by_tar["pct_reg"]  = (by_tar["registros"] / by_tar["registros"].sum() * 100).round(1)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tipos de tarifa", len(by_tar), "BT5B · BT5D · BT8")
    top_tar = by_tar.iloc[0] if len(by_tar) > 0 else None
    if top_tar is not None:
        k2.metric("Tarifa dominante", top_tar["tarifa"],
                  f"{top_tar['pct_kwh']:.1f}% del consumo")
        k3.metric("Mayor precio impl.",
                  by_tar.loc[by_tar["precio"].idxmax(),"tarifa"],
                  f"S/ {by_tar['precio'].max():.4f}/kWh")
    k4.metric("Consumo total", fmt(df["consumo_kwh"].sum())+" kWh", "período filtrado")

    st.markdown("")
    TAR_PAL = {"BT5B": "#3b5bdb", "BT5D": "#16a34a", "BT8": "#f59e0b"}
    tar_col = [TAR_PAL.get(t, "#94a3b8") for t in by_tar["tarifa"]]

    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        st.markdown("**% Consumo por tarifa**")
        fig_p1 = go.Figure(go.Pie(
            labels=by_tar["tarifa"], values=by_tar["kwh"],
            marker_colors=tar_col, hole=0.52,
            textinfo="percent+label",
            textfont=dict(color=TXT, size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} kWh · %{percent}<extra></extra>",
        ))
        fig_p1.update_layout(
            paper_bgcolor="white", plot_bgcolor="white", font=FONT_DICT,
            margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=False,
        )
        st.plotly_chart(fig_p1, use_container_width=True)

    with col_t2:
        st.markdown("**% Facturación por tarifa**")
        fig_p2 = go.Figure(go.Pie(
            labels=by_tar["tarifa"], values=by_tar["fact"],
            marker_colors=tar_col, hole=0.52,
            textinfo="percent+label",
            textfont=dict(color=TXT, size=11),
            hovertemplate="<b>%{label}</b><br>S/ %{value:,.0f} · %{percent}<extra></extra>",
        ))
        fig_p2.update_layout(
            paper_bgcolor="white", plot_bgcolor="white", font=FONT_DICT,
            margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=False,
        )
        st.plotly_chart(fig_p2, use_container_width=True)

    with col_t3:
        st.markdown("**% Registros por tarifa**")
        fig_p3 = go.Figure(go.Pie(
            labels=by_tar["tarifa"], values=by_tar["registros"],
            marker_colors=tar_col, hole=0.52,
            textinfo="percent+label",
            textfont=dict(color=TXT, size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,} registros · %{percent}<extra></extra>",
        ))
        fig_p3.update_layout(
            paper_bgcolor="white", plot_bgcolor="white", font=FONT_DICT,
            margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=False,
        )
        st.plotly_chart(fig_p3, use_container_width=True)

    st.markdown("**Precio implícito por tarifa (S/·kWh)**")
    fig_tp = go.Figure(go.Bar(
        x=by_tar["tarifa"], y=by_tar["precio"],
        marker_color=tar_col, marker_cornerradius=6,
        text=[f"S/ {v:.4f}" for v in by_tar["precio"]],
        textposition="outside", textfont=dict(color=TXT, size=12),
        width=0.4,
        hovertemplate="<b>%{x}</b>: S/ %{y:.4f}/kWh<extra></extra>",
    ))
    fig_tp.update_layout(**base_layout(240), showlegend=False)
    fig_tp.update_xaxes(tickfont=dict(color=TXT, size=12))
    fig_tp.update_yaxes(
        title="S/ por kWh",
        tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
    )
    st.plotly_chart(fig_tp, use_container_width=True)

    st.markdown("**Evolución mensual del consumo por tarifa (kWh)**")
    by_tm = (
        df.groupby(["periodo","tarifa"])["consumo_kwh"]
        .sum().reset_index().sort_values("periodo")
    )
    by_tm["label"] = by_tm["periodo"].apply(periodo_a_label)
    periodos_tm    = sorted(by_tm["periodo"].unique())

    fig_tm = go.Figure()
    for tar in by_tar["tarifa"]:
        sub = by_tm[by_tm["tarifa"]==tar]
        fig_tm.add_trace(go.Scatter(
            x=sub["label"], y=sub["consumo_kwh"]/1e3,
            name=tar, mode="lines+markers",
            line=dict(color=TAR_PAL.get(tar,"#94a3b8"), width=2.5),
            marker=dict(size=7),
            hovertemplate=f"<b>{tar}</b> %{{x}}: %{{y:.1f}}K kWh<extra></extra>",
        ))
    layout_tm = base_layout(300)
    layout_tm["margin"] = dict(l=55, r=20, t=40, b=80)
    fig_tm.update_layout(**layout_tm)
    fig_tm.update_layout(legend=dict(orientation="h", y=1.12,
                                     font=dict(size=11, color=TXT),
                                     bgcolor="rgba(0,0,0,0)"))
    fig_tm.update_xaxes(**axis_x_mensual(len(periodos_tm)))
    fig_tm.update_yaxes(
        title="Consumo (K kWh)", ticksuffix="K",
        tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
    )
    st.plotly_chart(fig_tm, use_container_width=True)

    st.markdown("**Consumo por tarifa y distrito (kWh)**")
    by_td = df.groupby(["distrito","tarifa"])["consumo_kwh"].sum().reset_index()
    by_td["kwh_k"] = by_td["consumo_kwh"] / 1e3
    fig_td = go.Figure()
    for tar in by_tar["tarifa"]:
        sub = by_td[by_td["tarifa"]==tar].sort_values("consumo_kwh", ascending=False)
        fig_td.add_trace(go.Bar(
            name=tar, x=sub["distrito"], y=sub["kwh_k"],
            marker_color=TAR_PAL.get(tar,"#94a3b8"), marker_cornerradius=3,
            hovertemplate=f"<b>%{{x}}</b> · {tar}: %{{y:.1f}}K kWh<extra></extra>",
        ))
    fig_td.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
        margin=dict(l=55, r=20, t=40, b=90),
        height=320, barmode="group",
        xaxis=dict(tickangle=-40, tickfont=dict(color=TXT, size=10),
                   gridcolor="#f1f5f9", automargin=True),
        yaxis=dict(title="Consumo (K kWh)", ticksuffix="K",
                   gridcolor="#f1f5f9", tickfont=dict(color=TXT),
                   title_font=dict(color=TXT, size=11), rangemode="tozero"),
        legend=dict(orientation="h", y=1.12, font=dict(size=11, color=TXT)),
    )
    st.plotly_chart(fig_td, use_container_width=True)

    st.markdown("**Detalle por tarifa**")
    tbl_t = pd.DataFrame({
        "Tarifa": by_tar["tarifa"],
        "Consumo (kWh)": by_tar["kwh"].apply(fmt),
        "% consumo": by_tar["pct_kwh"].apply(lambda x: f"{x:.1f}%"),
        "Facturación": by_tar["fact"].apply(fmt_soles),
        "% facturación": by_tar["pct_fact"].apply(lambda x: f"{x:.1f}%"),
        "Precio S/·kWh": by_tar["precio"].apply(lambda x: f"{x:.4f}"),
        "N° registros": by_tar["registros"].apply(lambda x: f"{x:,}"),
        "% registros": by_tar["pct_reg"].apply(lambda x: f"{x:.1f}%"),
    })
    st.dataframe(tbl_t, use_container_width=True, hide_index=True)

    st.session_state["figuras_TARIFAS"] = {
        "Evolución mensual por tarifa": fig_tm,
        "Consumo por tarifa y distrito": fig_td,
        "Precio implícito por tarifa": fig_tp,
    }

# ##############################################################################
# FASE 12 — MÓDULO 4: CLIENTES
# ##############################################################################

elif mod == "CLIENTES":
    st.markdown("## 👥 Cartera de Clientes")
    st.caption("Análisis por status, antigüedad de titulares y evolución mensual")

    # ── Agregados base ──
    by_status = df.groupby("status_cliente").agg(
        kwh=("consumo_kwh","sum"),
        fact=("facturacion","sum"),
        registros=("n_titulares","sum"),
    ).reset_index().sort_values("registros", ascending=False)
    by_status["kwh_prom"]  = (by_status["kwh"] / by_status["registros"].replace(0,1)).round(2)
    by_status["fact_prom"] = (by_status["fact"] / by_status["registros"].replace(0,1)).round(2)
    by_status["pct"]       = (by_status["registros"] / by_status["registros"].sum() * 100).round(1)

    # ── Datos de antigüedad (columnas nuevas de la BD) ──
    hay_filtro = (sel_prov != "Todas" or sel_dist != "Todos" or sel_tarifa != "Todas" or sel_per != "Todos")
    if hay_filtro:
        ultimo_per      = df["periodo"].max()
        df_ult          = df[df["periodo"] == ultimo_per]
        total_titulares = int(df_ult["n_titulares"].sum())      if "n_titulares"      in df.columns else 0
        tit_mas10       = int(df_ult["titulares_mas_10"].sum()) if "titulares_mas_10" in df.columns else 0
        tit_5_10        = int(df_ult["titulares_5_10"].sum())   if "titulares_5_10"   in df.columns else 0
        tit_menos5      = int(df_ult["titulares_menos_5"].sum())if "titulares_menos_5" in df.columns else 0
    else:
        ultimo_per_full = df_full["periodo"].max()
        df_ult_full     = df_full[df_full["periodo"] == ultimo_per_full]
        total_titulares = TOTALES.get("total_titulares",   int(df_ult_full["n_titulares"].sum()))
        tit_mas10       = TOTALES.get("titulares_mas_10",  int(df_ult_full["titulares_mas_10"].sum()))
        tit_5_10        = TOTALES.get("titulares_5_10",    int(df_ult_full["titulares_5_10"].sum()))
        tit_menos5      = TOTALES.get("titulares_menos_5", int(df_ult_full["titulares_menos_5"].sum()))
    tit_con_corte = 0
    pct_mas10  = tit_mas10  / total_titulares * 100 if total_titulares > 0 else 0
    pct_5_10   = tit_5_10   / total_titulares * 100 if total_titulares > 0 else 0
    pct_menos5 = tit_menos5 / total_titulares * 100 if total_titulares > 0 else 0

    if hay_filtro and total_titulares > 0:
        altas_filtradas = {
            1990: int(df_ult["altas_antes_2000"].sum()) if "altas_antes_2000" in df.columns else 0,
            2000: int(df_ult["altas_2000s"].sum())      if "altas_2000s"      in df.columns else 0,
            2010: int(df_ult["altas_2010s"].sum())      if "altas_2010s"      in df.columns else 0,
            2020: int(df_ult["altas_2020s"].sum())      if "altas_2020s"      in df.columns else 0,
        }
        altas_para_grafico   = dict(sorted({k: v for k, v in altas_filtradas.items() if v > 0}.items()))
        titulo_grafico_altas = "Altas por década (filtro activo)"
    else:
        altas_para_grafico   = ALTAS_HISTORICAS
        titulo_grafico_altas = "Altas históricas por año — nuevas conexiones"

    altas_sorted_f = sorted(altas_para_grafico.items(), key=lambda x: x[1], reverse=True)
    anio_pico   = altas_sorted_f[0][0] if altas_sorted_f else 2021
    altas_pico  = altas_sorted_f[0][1] if altas_sorted_f else 0
    anio_pico2  = altas_sorted_f[1][0] if len(altas_sorted_f) > 1 else anio_pico
    altas_pico2 = altas_sorted_f[1][1] if len(altas_sorted_f) > 1 else altas_pico

    # ── KPIs fila 1: titulares y antigüedad ──
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total titulares únicos",  f"{total_titulares:,}",  "cartera activa")
    k2.metric("Base consolidada +10 años", f"{pct_mas10:.1f}%",
              f"{tit_mas10:,} titulares")
    k3.metric("Año pico de altas", str(anio_pico),
              f"{altas_pico:,} nuevas conexiones")
    meses_filtro = df["periodo"].nunique()
    k4.metric("Períodos en análisis", str(meses_filtro),
              f"{per_min_label} – {per_max_label}")

    st.markdown("")

    # ══════════════════════════════════════════════════════════════════════════
    # SECCIÓN A: ANTIGÜEDAD DE TITULARES
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🏛️ Antigüedad de la cartera de titulares")

    col_ant1, col_ant2 = st.columns([1, 1.6])

    with col_ant1:
        # ── Barras horizontales: segmentación de antigüedad ──
        st.markdown("**Segmentación por antigüedad**")

        seg_labels = [
            "Nuevos · < 5 años\n(desde 2020)",
            "Intermedios · 5-10 años\n(2015-2019)",
            "Consolidados · +10 años\n(antes 2015)",
        ]
        seg_valores = [tit_menos5, tit_5_10, tit_mas10]
        seg_pcts    = [pct_menos5, pct_5_10, pct_mas10]
        seg_cols    = ["#06b6d4", "#f59e0b", "#a855f7"]

        fig_seg = go.Figure()
        for i, (lbl, val, pct_v, col_v) in enumerate(
            zip(seg_labels, seg_valores, seg_pcts, seg_cols)
        ):
            fig_seg.add_trace(go.Bar(
                x=[val],
                y=[lbl],
                orientation="h",
                marker_color=col_v,
                marker_cornerradius=5,
                text=[f"{val:,}  ({pct_v:.1f}%)"],
                textposition="inside",          # ← dentro de la barra
                textfont=dict(size=11, color="white"),  # ← blanco para contrastar
                hovertemplate=f"<b>{lbl.split(chr(10))[0]}</b><br>"
                      f"{val:,} titulares · {pct_v:.1f}%<extra></extra>",
                showlegend=False,
            ))

        fig_seg.update_layout(
            plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
            margin=dict(l=210, r=30, t=10, b=40),  # r pequeño, l para etiquetas
            height=230, showlegend=False, barmode="overlay",
            xaxis=dict(
                gridcolor="#f1f5f9", zeroline=False,
                tickfont=dict(color=TXT), title="Titulares",
                range=[0, max(seg_valores) * 1.15],  # solo 15% extra
            ),
            yaxis=dict(
                tickfont=dict(color=TXT, size=10),
                automargin=False,
            ),
        )
        st.plotly_chart(fig_seg, use_container_width=True)

    with col_ant2:
        # ── Gráfico de altas históricas por año ──
        st.markdown(f"**{titulo_grafico_altas}**")
        anios   = sorted(altas_para_grafico.keys())
        valores = [altas_para_grafico[a] for a in anios]

        # Colores: pico 1998=verde, pico 2021=azul, resto gris-azul
        bar_col_h = []
        for a in anios:
            v = altas_para_grafico[a]
            if a == anio_pico2:
                bar_col_h.append("#16a34a")
            elif a == anio_pico:
                bar_col_h.append("#3b5bdb")
            elif v >= 4000:
                bar_col_h.append("#60a5fa")
            else:
                bar_col_h.append("#cbd5e1")

        fig_altas = go.Figure(go.Bar(
            x=[str(a) for a in anios],
            y=valores,
            marker_color=bar_col_h,
            marker_cornerradius=2,
            hovertemplate="<b>%{x}</b>: %{y:,} altas<extra></extra>",
        ))

        # Anotaciones de los 2 picos
        fig_altas.add_annotation(
            x=str(anio_pico2), y=altas_pico2,
            text=f"<b>{altas_pico2:,}</b><br>Pico '{str(anio_pico2)[2:]}",
            showarrow=True, arrowhead=2, arrowcolor="#16a34a",
            ax=0, ay=-38, font=dict(size=9, color="#15803d"),
            bgcolor="white", bordercolor="#16a34a", borderwidth=1, borderpad=3,
        )
        fig_altas.add_annotation(
            x=str(anio_pico), y=altas_pico,
            text=f"<b>{altas_pico:,}</b><br>Pico '{str(anio_pico)[2:]}",
            showarrow=True, arrowhead=2, arrowcolor="#3b5bdb",
            ax=0, ay=-38, font=dict(size=9, color="#1d4ed8"),
            bgcolor="white", bordercolor="#3b5bdb", borderwidth=1, borderpad=3,
        )

        layout_altas = base_layout(280)
        layout_altas["margin"] = dict(l=45, r=20, t=40, b=50)
        fig_altas.update_layout(**layout_altas, showlegend=False)
        fig_altas.update_xaxes(
            tickangle=-55,
            tickfont=dict(color=TXT, size=9),
            dtick=5,  # mostrar cada 5 años para no saturar
            automargin=True,
        )
        fig_altas.update_yaxes(
            title="N° altas",
            tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
            gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
        )
        st.plotly_chart(fig_altas, use_container_width=True)

    # ── Leyenda de colores del gráfico de altas ──
    st.markdown(
        "<div style='display:flex;gap:20px;font-size:11px;color:#64748b;"
        "margin:-4px 0 12px 0;flex-wrap:wrap'>"
        f"<span>🟩 <b>{anio_pico2}</b>: Mayor pico ({altas_pico2:,} altas)</span>"
        f"<span>🟦 <b>{anio_pico}</b>: Pico más reciente ({altas_pico:,} altas)</span>"
        + ("<span>🔵 Décadas con más altas</span>" if hay_filtro else "<span>🔵 Años con +4,000 altas</span><span>⬜ Años de actividad normal</span>")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── Conclusión automática ──
    _segmento_dom = (
        "consolidada (+10 años)" if pct_mas10 >= 50
        else "intermedia (5-10 años)" if pct_5_10 >= 30
        else "nueva (menos de 5 años)"
    )
    _tendencia_reciente = (
        f"pico en {anio_pico}" if altas_pico > altas_pico2
        else f"pico en {anio_pico2}"
    )
    st.markdown(
        f"<div class='conclusion-card'>"
        f"<p style='font-size:13px;font-weight:700;margin:0 0 6px 0;"
        f"color:#e2e8f0 !important;-webkit-text-fill-color:#e2e8f0 !important'>"
        f"📊 Análisis de antigüedad — conclusión</p>"
        f"<p style='font-size:12px;line-height:1.8;margin:0;"
        f"color:#cbd5e1 !important;-webkit-text-fill-color:#cbd5e1 !important'>"
        f"La cartera de "
        f"<b style='color:#a855f7 !important;-webkit-text-fill-color:#a855f7 !important'>"
        f"{total_titulares:,} titulares</b> de Electro Ucayali "
        f"es predominantemente "
        f"<b style='color:#c084fc !important;-webkit-text-fill-color:#c084fc !important'>"
        f"{_segmento_dom}</b>: "
        f"<b style='color:#e2e8f0 !important;-webkit-text-fill-color:#e2e8f0 !important'>"
        f"{pct_mas10:.1f}%</b> lleva más de 10 años como cliente, "
        f"lo que representa una base estable y de alta fidelización. "
        f"El {pct_5_10:.1f}% (segmento intermedio) y el {pct_menos5:.1f}% de nuevos clientes "
        f"reflejan expansión sostenida. Los dos grandes picos de incorporación fueron "
        f"<b style='color:#86efac !important;-webkit-text-fill-color:#86efac !important'>"
        f"{anio_pico2} ({altas_pico2:,} altas)</b> "
        f"y "
        f"<b style='color:#93c5fd !important;-webkit-text-fill-color:#93c5fd !important'>"
        f"{anio_pico} ({altas_pico:,} altas)</b>."
        f"</p></div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # SECCIÓN B: STATUS DE CLIENTES (análisis original enriquecido)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 👤 Status de la cartera")

    STATUS_COL = {
        "NORMAL": "#16a34a", "ANULADO": "#e03131",
        "ANULADO A SOLICITUD": "#f97316", "DEPURADO": "#f59e0b", "DESCONOCIDO": "#94a3b8",
    }

    # KPIs de status
    k1s, k2s, k3s, k4s = st.columns(4)
    hay_filtro_status = (sel_prov != "Todas" or sel_dist != "Todos" or sel_tarifa != "Todas" or sel_per != "Todos")
    if hay_filtro_status:
        total_reg_status = int(df["n_titulares"].sum())
    else:
        total_reg_status = TOTALES.get("total_registros", 1132087)
    k1s.metric("Total registros", f"{total_reg_status:,}", "período filtrado")
    norm = by_status[by_status["status_cliente"]=="NORMAL"]
    if len(norm) > 0:
        k2s.metric("Clientes NORMAL", f"{int(norm['registros'].values[0]):,}",
                   f"{norm['pct'].values[0]:.1f}% del total")
    total_tit_status = int(df["n_titulares"].sum()) if int(df["n_titulares"].sum()) > 0 else 1
    k3s.metric("Consumo prom./registro", f"{df['consumo_kwh'].sum()/total_tit_status:.1f} kWh", "promedio global")
    k4s.metric("Facturación prom./registro", fmt_soles(df["facturacion"].sum()/total_tit_status), "promedio global")

    st.markdown("")

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.markdown("**Distribución por status de cliente**")
        sc = [STATUS_COL.get(s,"#3b5bdb") for s in by_status["status_cliente"]]
        fig_st = go.Figure(go.Pie(
            labels=by_status["status_cliente"], values=by_status["registros"],
            marker_colors=sc, hole=0.52,
            textinfo="percent+label",
            textfont=dict(color=TXT, size=10),
            hovertemplate="<b>%{label}</b><br>%{value:,} registros · %{percent}<extra></extra>",
        ))
        fig_st.update_layout(
            paper_bgcolor="white", plot_bgcolor="white", font=FONT_DICT,
            margin=dict(l=10,r=10,t=10,b=10), height=270, showlegend=False,
        )
        st.plotly_chart(fig_st, use_container_width=True)

    with col_c2:
        st.markdown("**Consumo promedio por status (kWh/registro)**")
        sts    = by_status.sort_values("kwh_prom", ascending=True)
        bar_sc = [STATUS_COL.get(s,"#3b5bdb") for s in sts["status_cliente"]]
        fig_skwh = go.Figure(go.Bar(
            x=sts["kwh_prom"], y=sts["status_cliente"], orientation="h",
            marker_color=bar_sc, marker_cornerradius=4,
            text=[f"{v:.1f} kWh" for v in sts["kwh_prom"]], textposition="outside",
            textfont=dict(color=TXT, size=10),
            hovertemplate="%{y}: %{x:.1f} kWh prom.<extra></extra>",
        ))
        fig_skwh.update_layout(
            plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
            margin=dict(l=160, r=100, t=10, b=10), height=270, showlegend=False,
            xaxis=dict(gridcolor="#f1f5f9", zeroline=False, ticksuffix=" kWh",
                       tickfont=dict(color=TXT), title_font=dict(color=TXT)),
            yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(color=TXT, size=10),
                       automargin=True),
        )
        st.plotly_chart(fig_skwh, use_container_width=True)

    st.markdown("**Evolución mensual de registros activos (NORMAL)**")
    by_per_n = (
        df[df["status_cliente"]=="NORMAL"]
        .groupby("periodo")["n_titulares"].sum()
        .reset_index().sort_values("periodo")
    )
    by_per_n.columns = ["periodo","registros"]
    by_per_n["label"] = by_per_n["periodo"].apply(periodo_a_label)

    if len(by_per_n) >= 2:
        fig_ev = go.Figure(go.Scatter(
            x=by_per_n["label"], y=by_per_n["registros"],
            mode="lines+markers",
            line=dict(color="#16a34a", width=2.5),
            fill="tozeroy", fillcolor="rgba(22,163,74,0.09)",
            marker=dict(size=6, color="#16a34a"),
            text=[f"{v:,}" for v in by_per_n["registros"]],
            textposition="top center", textfont=dict(size=9, color="#16a34a"),
            hovertemplate="%{x}: %{y:,} registros NORMAL<extra></extra>",
        ))
        layout_ev = base_layout(240)
        layout_ev["margin"] = dict(l=65, r=20, t=30, b=80)
        fig_ev.update_layout(**layout_ev, showlegend=False)
        fig_ev.update_xaxes(**axis_x_mensual(len(by_per_n)))
        fig_ev.update_yaxes(
            title="Registros NORMAL",
            tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
            gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
        )
        st.plotly_chart(fig_ev, use_container_width=True)
    else:
        st.info("No hay suficientes períodos para mostrar evolución mensual.")
        fig_ev = go.Figure()

    st.markdown("**Registros por status y distrito**")
    by_sd = df.groupby(["distrito","status_cliente"])["n_titulares"].sum().reset_index()
    by_sd.columns = ["distrito","status","registros"]
    fig_sd = go.Figure()
    for st_k, col in STATUS_COL.items():
        sub = by_sd[by_sd["status"]==st_k]
        if len(sub) > 0:
            fig_sd.add_trace(go.Bar(
                name=st_k, x=sub["distrito"], y=sub["registros"],
                marker_color=col, marker_cornerradius=3,
                hovertemplate=f"<b>%{{x}}</b> · {st_k}: %{{y:,}}<extra></extra>",
            ))
    fig_sd.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
        margin=dict(l=55, r=20, t=40, b=90),
        height=320, barmode="stack",
        xaxis=dict(tickangle=-40, tickfont=dict(color=TXT, size=10),
                   gridcolor="#f1f5f9", automargin=True),
        yaxis=dict(title="N° registros", gridcolor="#f1f5f9",
                   tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
                   rangemode="tozero"),
        legend=dict(orientation="h", y=1.12, font=dict(size=10, color=TXT)),
    )
    st.plotly_chart(fig_sd, use_container_width=True)

    st.markdown("**Resumen por status**")
    tbl_c = pd.DataFrame({
        "Status": by_status["status_cliente"],
        "Registros": by_status["registros"].apply(lambda x: f"{x:,}"),
        "% total": by_status["pct"].apply(lambda x: f"{x:.1f}%"),
        "kWh total": by_status["kwh"].apply(fmt),
        "kWh promedio": by_status["kwh_prom"].apply(lambda x: f"{x:.1f}"),
        "Facturación": by_status["fact"].apply(fmt_soles),
        "Fact. promedio": by_status["fact_prom"].apply(lambda x: f"S/ {x:.2f}"),
    })
    st.dataframe(tbl_c, use_container_width=True, hide_index=True)

    # ── Tabla de antigüedad ──
    st.markdown("**Detalle de antigüedad de titulares**")
    tbl_ant = pd.DataFrame({
        "Segmento":      ["Consolidados +10 años (antes 2015)",
                          "Intermedios 5-10 años (2015-2019)",
                          "Nuevos <5 años (desde 2020)",
                          "Total cartera"],
        "Titulares":     [f"{tit_mas10:,}", f"{tit_5_10:,}", f"{tit_menos5:,}",
                          f"{total_titulares:,}"],
        "Participación": [f"{pct_mas10:.1f}%", f"{pct_5_10:.1f}%",
                          f"{pct_menos5:.1f}%", "100.0%"],
        "Perfil":        ["Base consolidada · alta fidelización",
                          "Segmento de crecimiento",
                          "Clientes recientes · post-pandemia",
                          "—"],
    })
    st.dataframe(tbl_ant, use_container_width=True, hide_index=True)

    # Guardar figuras para PDF
    st.session_state["figuras_CLIENTES"] = {
        "Altas históricas por año": fig_altas,
        "Segmentación por antigüedad": fig_seg,
        "Distribución por status": fig_st,
        "Evolución mensual registros NORMAL": fig_ev,
        "Registros por status y distrito": fig_sd,
    }

# ##############################################################################
# FASE 13 — MÓDULO 5: EFICIENCIA OPERACIONAL
# ##############################################################################

elif mod == "EFICIENCIA":
    st.markdown("## 📈 Eficiencia Operacional")
    st.caption("KPIs de rendimiento, ticket promedio por distrito, heatmap estacional")

    by_per = (
        df.groupby("periodo").agg(kwh=("consumo_kwh","sum"), fact=("facturacion","sum"))
        .reset_index().sort_values("periodo")
    )
    by_per["label"] = by_per["periodo"].apply(periodo_a_label)

    periodos_s = sorted(by_per["periodo"].tolist())
    var_m = None
    if len(periodos_s) >= 2:
        v_ant  = by_per[by_per["periodo"]==periodos_s[-2]]["kwh"].values[0]
        v_ult  = by_per[by_per["periodo"]==periodos_s[-1]]["kwh"].values[0]
        var_m  = ((v_ult - v_ant) / v_ant * 100) if v_ant > 0 else 0

    tot_tit = df["n_titulares"].sum()
    ticket_prom = (df["facturacion"].sum() / tot_tit) if tot_tit > 0 else 0
    kwh_prom_r  = (df["consumo_kwh"].sum() / tot_tit) if tot_tit > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ticket promedio", fmt_soles(ticket_prom), "por registro")
    k2.metric("kWh promedio/registro", f"{kwh_prom_r:.1f}", "promedio global")
    if var_m is not None:
        k3.metric("Var. consumo último mes",
                  f"{'+' if var_m>=0 else ''}{var_m:.1f}%",
                  f"{periodo_a_label(periodos_s[-2])} → {periodo_a_label(periodos_s[-1])}")
    k4.metric("Períodos disponibles", df["periodo"].nunique(), "en la selección")

    st.markdown("")

    st.markdown("**Tendencia histórica del consumo mensual**")
    fig_tend = go.Figure(go.Scatter(
        x=by_per["label"], y=by_per["kwh"]/1e3,
        mode="lines+markers",
        line=dict(color="#3b5bdb", width=2.5),
        marker=dict(size=6, color="#3b5bdb"),
        fill="tozeroy", fillcolor="rgba(59,91,219,0.07)",
        hovertemplate="%{x}: %{y:.1f}K kWh<extra></extra>",
    ))
    layout_t = base_layout(240)
    layout_t["margin"] = dict(l=55, r=20, t=30, b=80)
    fig_tend.update_layout(**layout_t, showlegend=False)
    fig_tend.update_xaxes(**axis_x_mensual(len(by_per)))
    fig_tend.update_yaxes(
        title="Consumo (K kWh)", ticksuffix="K",
        tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False, rangemode="tozero",
    )
    st.plotly_chart(fig_tend, use_container_width=True)

    col_e1, col_e2 = st.columns(2)

    with col_e1:
        st.markdown("**Variación mensual del consumo (%)**")
        if len(by_per) >= 2:
            crec_data = []
            for i in range(1, len(by_per)):
                v_prev = by_per["kwh"].iloc[i-1]
                v_cur  = by_per["kwh"].iloc[i]
                crec   = round((v_cur - v_prev)/v_prev * 100, 1) if v_prev > 0 else 0
                crec_data.append({"label": by_per["label"].iloc[i], "crec": crec})
            crec_df  = pd.DataFrame(crec_data)
            bar_cr   = ["#16a34a" if v>=0 else "#e03131" for v in crec_df["crec"]]
            fig_crec = go.Figure(go.Bar(
                x=crec_df["label"], y=crec_df["crec"],
                marker_color=bar_cr, marker_cornerradius=4,
                text=[f"{v:+.1f}%" for v in crec_df["crec"]],
                textposition="outside", textfont=dict(size=9, color=TXT),
                hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
            ))
            layout_cr = base_layout(260)
            layout_cr["margin"] = dict(l=45, r=20, t=30, b=80)
            fig_crec.update_layout(**layout_cr, showlegend=False)
            fig_crec.update_xaxes(**axis_x_mensual(len(crec_df)))
            fig_crec.update_yaxes(
                title="Variación (%)", ticksuffix="%",
                tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
                gridcolor="#f1f5f9", zeroline=True, zerolinecolor="#e2e8f0",
            )
            st.plotly_chart(fig_crec, use_container_width=True)
        else:
            st.info("Se necesitan al menos 2 períodos.")
            fig_crec = go.Figure()

    with col_e2:
        st.markdown("**Heatmap estacional — consumo relativo al promedio mensual**")
        pivot = df.pivot_table(index="distrito", columns="mes",
                               values="consumo_kwh", aggfunc="sum")
        pivot.columns = [MESES_CORTO[c-1] for c in pivot.columns]
        pivot = pivot.fillna(0)
        pivot_pct = pivot.div(pivot.mean(axis=1).replace(0, np.nan), axis=0).multiply(100).round(1)

        fig_heat = go.Figure(go.Heatmap(
            z=pivot_pct.values,
            x=pivot_pct.columns.tolist(),
            y=pivot_pct.index.tolist(),
            text=[[f"{v:.0f}%" if not np.isnan(v) else "" for v in row]
                  for row in pivot_pct.values],
            texttemplate="%{text}",
            textfont=dict(size=8, color=TXT),
            hovertemplate="<b>%{y}</b> · %{x}: %{z:.1f}% del prom.<extra></extra>",
            colorscale=[[0,"#fff7ed"],[0.4,"#fed7aa"],[0.5,"#f0f9ff"],[0.6,"#bfdbfe"],[1,"#1d4ed8"]],
            zmid=100, zmin=60, zmax=140, showscale=True,
            colorbar=dict(
                title="% vs prom.", thickness=12,
                tickvals=[70,85,100,115,130],
                ticktext=["70%","85%","100%","115%","130%"],
                tickfont=dict(size=8, color=TXT),
            ),
        ))
        fig_heat.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=130, r=70, t=10, b=15),
            height=max(300, len(pivot_pct)*22 + 60),
            font=FONT_DICT,
            xaxis=dict(tickfont=dict(color=TXT, size=10), automargin=True),
            yaxis=dict(tickfont=dict(color=TXT, size=10), automargin=True),
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown("**Ticket promedio (S/·registro) por distrito**")
    tick_d = df.groupby("distrito").agg(
        fact=("facturacion","sum"), n=("n_titulares","sum")
    ).reset_index()
    tick_d["ticket"] = (tick_d["fact"] / tick_d["n"].replace(0,1)).round(2)
    tick_d = tick_d.sort_values("ticket", ascending=True)
    med_t  = tick_d["ticket"].median()
    bar_td = ["#f59e0b" if v > med_t*1.1 else "#3b5bdb" for v in tick_d["ticket"]]
    fig_tick = go.Figure(go.Bar(
        x=tick_d["ticket"], y=tick_d["distrito"], orientation="h",
        marker_color=bar_td, marker_cornerradius=3,
        text=[f"S/{v:.2f}" for v in tick_d["ticket"]], textposition="outside",
        textfont=dict(color=TXT, size=10),
        hovertemplate="%{y}: S/ %{x:.2f} prom.<extra></extra>",
    ))
    fig_tick.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", font=FONT_DICT,
        margin=dict(l=160, r=90, t=15, b=15),
        height=max(300, len(tick_d)*28), showlegend=False,
        xaxis=dict(gridcolor="#f1f5f9", zeroline=False,
                   tickfont=dict(color=TXT), title="S/ promedio"),
        yaxis=dict(tickfont=dict(color=TXT, size=11), automargin=True),
    )
    st.plotly_chart(fig_tick, use_container_width=True)

    st.markdown("**Resumen mensual de eficiencia**")
    tbl_ef = df.groupby("periodo").agg(
        kwh=("consumo_kwh","sum"), fact=("facturacion","sum"), n=("n_titulares","sum"),
    ).reset_index().sort_values("periodo", ascending=False)
    tbl_ef["label"]  = tbl_ef["periodo"].apply(periodo_a_label)
    tbl_ef["ticket"] = (tbl_ef["fact"] / tbl_ef["n"].replace(0,1)).round(2)
    tbl_ef["kwh_n"]  = (tbl_ef["kwh"] / tbl_ef["n"].replace(0,1)).round(2)
    tbl_ef["precio"] = (tbl_ef["fact"] / tbl_ef["kwh"].replace(0,1)).round(4)
    st.dataframe(pd.DataFrame({
        "Período": tbl_ef["label"],
        "Consumo (kWh)": tbl_ef["kwh"].apply(fmt),
        "Facturación": tbl_ef["fact"].apply(fmt_soles),
        "kWh/registro": tbl_ef["kwh_n"].apply(lambda x: f"{x:.1f}"),
        "Ticket prom.": tbl_ef["ticket"].apply(lambda x: f"S/ {x:.2f}"),
        "Precio S/·kWh": tbl_ef["precio"].apply(lambda x: f"{x:.4f}"),
        "N° registros": tbl_ef["n"].apply(lambda x: f"{x:,}"),
    }), use_container_width=True, hide_index=True)

    st.session_state["figuras_EFICIENCIA"] = {
        "Tendencia histórica mensual": fig_tend,
        "Variación mensual (%)": fig_crec,
        "Heatmap estacional por distrito": fig_heat,
        "Ticket promedio por distrito": fig_tick,
    }

# ##############################################################################
# FASE 14 — MÓDULO 6: PROYECCIÓN
# ##############################################################################

elif mod == "PROYECCION":
    st.markdown("## 🔮 Proyección y Tendencia")
    st.caption("Proyección mensual basada en tendencia histórica · Escenarios central, optimista y pesimista")

    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    with col_cfg1:
        variable = st.selectbox(
            "Variable a proyectar",
            ["Consumo (kWh)", "Facturación (S/)", "Registros activos"],
        )
    with col_cfg2:
        distritos_disp = ["Nacional"] + sorted(df_full["distrito"].dropna().unique().tolist())
        dist_proj = st.selectbox("Cobertura", distritos_disp)
    with col_cfg3:
        horizonte = st.selectbox(
            "Meses a proyectar", [3, 6, 12], index=1,
            format_func=lambda x: f"{x} meses",
        )

    dproj = df_full.copy()
    if dist_proj != "Nacional":
        dproj = dproj[dproj["distrito"] == dist_proj]
    # "Registros activos" = titulares facturados con status NORMAL
    if variable == "Registros activos":
        dproj = dproj[dproj["status_cliente"] == "NORMAL"]

    col_map = {
        "Consumo (kWh)":     "consumo_kwh",
        "Facturación (S/)":  "facturacion",
        "Registros activos": "n_titulares",
    }
    agg_fn  = "sum"
    col_use = col_map[variable]
    unidad  = "kWh" if variable == "Consumo (kWh)" else ("S/" if variable == "Facturación (S/)" else "reg.")

    by_per_proj = (
        dproj.groupby("periodo")[col_use]
        .agg(agg_fn)
        .reset_index()
        .sort_values("periodo")
    )
    by_per_proj.columns = ["periodo", "valor"]
    by_per_proj["label"] = by_per_proj["periodo"].apply(periodo_a_label)
    n_puntos = len(by_per_proj)

    if n_puntos < 4:
        st.warning("⚠️ Se necesitan al menos 4 períodos de datos. Quita algún filtro y vuelve a intentarlo.")
        st.stop()

    x_idx    = np.arange(n_puntos)
    y_vals   = by_per_proj["valor"].values.astype(float)
    coeffs   = np.polyfit(x_idx, y_vals, 1)
    y_fit    = np.polyval(coeffs, x_idx)
    residuos = y_vals - y_fit
    sigma    = np.std(residuos)

    ss_res  = np.sum(residuos**2)
    ss_tot  = np.sum((y_vals - np.mean(y_vals))**2)
    r2      = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    mae     = np.mean(np.abs(residuos))
    cv_rmse = (np.sqrt(np.mean(residuos**2)) / np.mean(y_vals) * 100) if np.mean(y_vals) > 0 else 0

    x_fut  = np.arange(n_puntos, n_puntos + horizonte)
    y_fut  = np.maximum(0, np.polyval(coeffs, x_fut))
    y_opt  = np.maximum(0, y_fut + sigma)
    y_pes  = np.maximum(0, y_fut - sigma)

    last_per = int(by_per_proj["periodo"].iloc[-1])
    fut_labels = []
    anio_f, mes_f = last_per // 100, last_per % 100
    for _ in range(horizonte):
        mes_f += 1
        if mes_f > 12:
            mes_f = 1; anio_f += 1
        fut_labels.append(f"{MESES_CORTO[mes_f-1]} {str(anio_f)[2:]}")

    if r2 >= 0.85:
        cal_icon, cal_texto, cal_color, cal_bg = "🟢", "Excelente ajuste", "#15803d", "#f0fdf4"
        cal_desc = "La tendencia histórica es muy consistente. La proyección es confiable."
    elif r2 >= 0.60:
        cal_icon, cal_texto, cal_color, cal_bg = "🟡", "Ajuste aceptable", "#b45309", "#fffbeb"
        cal_desc = "Existe una tendencia clara pero con variaciones. Usa los escenarios como referencia."
    else:
        cal_icon, cal_texto, cal_color, cal_bg = "🔴", "Ajuste moderado", "#b91c1c", "#fef2f2"
        cal_desc = "Los datos tienen alta variabilidad. Los escenarios tienen mayor incertidumbre."

    crecimiento_pct = ((y_fut[-1] - y_vals[-1]) / y_vals[-1] * 100) if y_vals[-1] > 0 else 0
    tendencia_txt   = "📈 Crecimiento sostenido" if coeffs[0] > 0 else "📉 Tendencia a la baja"

    def _fv(v):
        if variable == "Facturación (S/)":
            return fmt_soles(v)
        return fmt(v) + f" {unidad}"

    st.markdown("")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Calidad del modelo (R²)", f"{r2:.2f}", f"{cal_icon} {cal_texto}")
    k2.metric("Tendencia mensual", _fv(abs(coeffs[0])), tendencia_txt)
    k3.metric(f"Proyectado · {fut_labels[-1]}", _fv(y_fut[-1]), f"{crecimiento_pct:+.1f}% vs último mes real")
    k4.metric("Margen de error típico", _fv(mae), f"±{cv_rmse:.1f}% del valor mensual")

    st.markdown(
        f"<div style='background:{cal_bg};border-left:4px solid {cal_color};"
        f"border-radius:0 8px 8px 0;padding:10px 16px;margin:6px 0 18px 0'>"
        f"<span style='font-size:13px;color:{cal_color};font-weight:600'>"
        f"{cal_icon} {cal_texto}</span> &nbsp;·&nbsp; "
        f"<span style='font-size:12px;color:#374151'>{cal_desc}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### 📊 Histórico y proyección mensual")

    labels_all = by_per_proj["label"].tolist() + fut_labels
    n_all      = len(labels_all)
    x_all      = np.arange(n_all)
    banda_sup  = np.maximum(0, np.polyval(coeffs, x_all) + sigma)
    banda_inf  = np.maximum(0, np.polyval(coeffs, x_all) - sigma)

    fig_reg = go.Figure()
    fig_reg.add_trace(go.Scatter(x=labels_all, y=banda_sup, mode="lines",
        line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig_reg.add_trace(go.Scatter(x=labels_all, y=banda_inf, mode="lines",
        fill="tonexty", fillcolor="rgba(59,91,219,0.10)",
        line=dict(width=0), name="Rango probable", hoverinfo="skip"))
    fig_reg.add_trace(go.Scatter(x=by_per_proj["label"], y=by_per_proj["valor"],
        mode="lines+markers", name="Histórico",
        line=dict(color="#1e3a5f", width=2.8),
        marker=dict(size=8, color="#1e3a5f", line=dict(color="white", width=1.5)),
        hovertemplate="<b>%{x}</b> · Real: %{y:,.0f} " + unidad + "<extra></extra>"))
    fig_reg.add_trace(go.Scatter(x=by_per_proj["label"], y=y_fit,
        mode="lines", name="Proyección central",
        line=dict(color="#f59e0b", width=1.8, dash="dot"),
        hovertemplate="%{x} tendencia: %{y:,.0f}<extra></extra>"))
    fig_reg.add_trace(go.Scatter(x=fut_labels, y=y_fut,
        mode="lines+markers", name="Proyección central",
        line=dict(color="#16a34a", width=2.8, dash="dash"),
        marker=dict(size=10, symbol="diamond", color="#16a34a", line=dict(color="white", width=1.5)),
        hovertemplate="<b>%{x}</b> · Central: %{y:,.0f} " + unidad + "<extra></extra>",
        showlegend=False))
    fig_reg.add_trace(go.Scatter(x=fut_labels, y=y_opt,
        mode="lines+markers", name="Optimista",
        line=dict(color="#22c55e", width=1.6, dash="dot"),
        marker=dict(size=6, color="#22c55e"),
        hovertemplate="<b>%{x}</b> · Optimista: %{y:,.0f} " + unidad + "<extra></extra>"))
    fig_reg.add_trace(go.Scatter(x=fut_labels, y=y_pes,
        mode="lines+markers", name="Pesimista",
        line=dict(color="#e03131", width=1.6, dash="dot"),
        marker=dict(size=6, color="#e03131"),
        hovertemplate="<b>%{x}</b> · Pesimista: %{y:,.0f} " + unidad + "<extra></extra>"))

    sep_x = (n_puntos - 0.5) / (n_all - 1) if n_all > 1 else 0.5
    fig_reg.add_shape(type="line", xref="paper", yref="paper",
        x0=sep_x, x1=sep_x, y0=0, y1=1,
        line=dict(color="#94a3b8", width=1.5, dash="dot"))
    fig_reg.add_annotation(xref="paper", yref="paper",
        x=sep_x + 0.01, y=0.97,
        text="← Real &nbsp;|&nbsp; Proyección →",
        showarrow=False, font=dict(color="#64748b", size=10),
        xanchor="left", bgcolor="white", bordercolor="#e2e8f0", borderwidth=1, borderpad=4)

    layout_reg = base_layout(400)
    layout_reg["margin"] = dict(l=65, r=20, t=55, b=80)
    fig_reg.update_layout(**layout_reg)
    fig_reg.update_layout(legend=dict(orientation="h", y=1.14,
        font=dict(size=11, color=TXT), bgcolor="rgba(0,0,0,0)"))
    fig_reg.update_xaxes(**axis_x_mensual(n_all))
    fig_reg.update_yaxes(tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
        gridcolor="#f1f5f9", zeroline=False, rangemode="tozero")
    st.plotly_chart(fig_reg, use_container_width=True)

    st.markdown(
        "<div style='display:flex;gap:24px;font-size:11px;color:#64748b;"
        "margin:-8px 0 20px 0;flex-wrap:wrap'>"
        "<span>🔵 <b>Histórico</b>: datos reales mes a mes</span>"
        "<span>🟡 <b>Proyección central</b>: sigue la tendencia histórica</span>"
        "<span>🟢 <b>Optimista</b>: si el consumo sube más de lo esperado</span>"
        "<span>🔴 <b>Pesimista</b>: si el consumo baja más de lo esperado</span>"
        "<span style='background:#dbeafe;padding:1px 8px;border-radius:4px'>"
        "📐 <b>Rango probable</b>: zona donde es más probable que caiga el dato real</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### 📋 Proyección mes a mes")
    tbl_proj = pd.DataFrame({
        "Período":          fut_labels,
        "📊 Central":       [_fv(v) for v in y_fut],
        "🟢 Optimista":     [_fv(v) for v in y_opt],
        "🔴 Pesimista":     [_fv(v) for v in y_pes],
        "Var. vs último real": [
            f"{((v - y_vals[-1]) / y_vals[-1] * 100):+.1f}%" if y_vals[-1] > 0 else "—"
            for v in y_fut
        ],
    })
    st.dataframe(tbl_proj, use_container_width=True, hide_index=True)

    st.markdown("### 📉 ¿Cómo varió el consumo cada mes?")
    st.caption("Porcentaje de cambio respecto al mes anterior — verde = subió, rojo = bajó")

    if n_puntos >= 2:
        var_hist = []
        for i in range(1, n_puntos):
            v_p = y_vals[i-1]
            v_c = y_vals[i]
            pct = round((v_c - v_p) / v_p * 100, 1) if v_p > 0 else 0
            var_hist.append({"label": by_per_proj["label"].iloc[i], "pct": pct})
        var_df   = pd.DataFrame(var_hist)
        mean_var = var_df["pct"].mean()
        bar_vc   = ["#16a34a" if v >= 0 else "#e03131" for v in var_df["pct"]]

        fig_var = go.Figure()
        fig_var.add_trace(go.Bar(
            x=var_df["label"], y=var_df["pct"],
            marker_color=bar_vc, marker_cornerradius=5,
            text=[f"{v:+.1f}%" for v in var_df["pct"]],
            textposition="outside", textfont=dict(size=9.5, color=TXT),
            hovertemplate="%{x}: %{y:+.1f}% vs mes anterior<extra></extra>",
        ))
        fig_var.add_hline(y=mean_var, line_dash="dot", line_color="#8b5cf6", line_width=1.8,
            annotation_text=f"Promedio: {mean_var:+.1f}%",
            annotation_font_color="#8b5cf6", annotation_position="top right")
        layout_var = base_layout(240)
        layout_var["margin"] = dict(l=45, r=20, t=35, b=80)
        fig_var.update_layout(**layout_var, showlegend=False)
        fig_var.update_xaxes(**axis_x_mensual(len(var_df)))
        fig_var.update_yaxes(title="Cambio mensual (%)", ticksuffix="%",
            tickfont=dict(color=TXT), title_font=dict(color=TXT, size=11),
            gridcolor="#f1f5f9", zeroline=True, zerolinecolor="#cbd5e1")
        st.plotly_chart(fig_var, use_container_width=True)
    else:
        fig_var = go.Figure()

    st.markdown(
        "<div style='background:#f8fafc;border-left:4px solid #3b5bdb;"
        "border-radius:0 8px 8px 0;padding:12px 18px;margin-top:8px'>"
        "<p style='font-size:12px;color:#374151;margin:0;line-height:1.9'>"
        "<b>¿Cómo se calcula?</b> Se traza una línea de tendencia sobre los datos históricos "
        "(mínimos cuadrados). La proyección central sigue esa línea hacia adelante. "
        "El escenario <b>optimista</b> suma la variabilidad típica de los meses anteriores; "
        "el <b>pesimista</b> la resta. "
        f"El <b>R² = {r2:.2f}</b> indica que el {r2*100:.0f}% de los cambios históricos "
        f"se explican por la tendencia — {'muy buena base para proyectar.' if r2 >= 0.7 else 'hay variabilidad adicional a considerar.'}"
        "</p></div>",
        unsafe_allow_html=True,
    )

    st.session_state["figuras_PROYECCION"] = {
        f"Proyección — {variable} · {dist_proj}": fig_reg,
        "Variación histórica mensual":            fig_var,
    }

# ##############################################################################
# FASE 15 — BOTÓN DE EXPORTACIÓN PDF
# ##############################################################################

st.markdown("---")
figuras_pdf = st.session_state.get(f"figuras_{mod}", {})

try:
    pdf_bytes = generar_pdf(df, df_full, mod, sel_per, sel_prov, sel_dist, sel_tarifa, figuras_pdf)
except Exception as e:
    st.warning(f"⚠️ Error generando PDF: {e}")
    pdf_bytes = b""

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
st.markdown('<div class="pdf-btn">', unsafe_allow_html=True)
st.download_button(
    label=f"📄 Exportar PDF — {MOD_LABELS[mod]}",
    data=pdf_bytes,
    file_name=f"informe_ELUC_{mod}_{ts}.pdf",
    mime="application/pdf",
    key="pdf_download",
    type="primary",
    disabled=(len(pdf_bytes) == 0),
)
st.markdown('</div>', unsafe_allow_html=True)