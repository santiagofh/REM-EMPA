from pathlib import Path

import streamlit as st

from dashboard_empa_pages import SECTIONS, render_home_page, render_section_page


BASE_DIR = Path(__file__).resolve().parent


st.set_page_config(
    page_title="Dashboard REM EMPA",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --gob-red: #FE6565;
        --gob-blue: #006FB3;
        --gob-blue-soft: #EAF4FA;
    }

    .stApp h1, .stApp h2, .stApp h3 {
        color: var(--gob-blue);
        font-weight: 700;
    }

    .stApp [data-testid="stMetric"] {
        background: linear-gradient(180deg, #ffffff 0%, var(--gob-blue-soft) 100%);
        border: 1px solid #cfe6f4;
        border-radius: 12px;
        padding: 0.5rem 0.75rem;
    }

    .stApp button[kind="primary"] {
        background-color: var(--gob-red);
        border-color: var(--gob-red);
    }

    .stApp button[kind="secondary"] {
        border-color: var(--gob-blue);
        color: var(--gob-blue);
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid #cfe6f4;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.logo(
    str(BASE_DIR / "assets" / "seremi_sidebar_logo.svg"),
    size="large",
    icon_image=str(BASE_DIR / "assets" / "seremi_sidebar_icon.svg"),
)


def page_cobertura() -> None:
    render_section_page("cobertura")


def page_nutricion() -> None:
    render_section_page("nutricion")


def page_riesgo() -> None:
    render_section_page("riesgo")


def page_profesional() -> None:
    render_section_page("profesional")


navigation = st.navigation(
    [
        st.Page(render_home_page, title="Inicio", icon=":material/home:"),
        st.Page(page_cobertura, title=SECTIONS["cobertura"], icon=":material/monitoring:"),
        st.Page(page_nutricion, title=SECTIONS["nutricion"], icon=":material/balance:"),
        st.Page(page_riesgo, title=SECTIONS["riesgo"], icon=":material/favorite:"),
        st.Page(page_profesional, title=SECTIONS["profesional"], icon=":material/badge:"),
    ],
    position="sidebar",
    expanded=True,
)

navigation.run()

st.markdown(
    """
    <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        background-color: #FFF3CD;
        border: 1px solid #FFC107;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 600;
        color: #856404;
        z-index: 9999;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    ">
        Datos Provisorios
    </div>
    """,
    unsafe_allow_html=True,
)
