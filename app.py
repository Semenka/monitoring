"""Streamlit entrypoint: ADNOC Onshore South East production dashboard."""
from __future__ import annotations

import streamlit as st

from monitoring.charts import theme
# Register all built-in metrics/charts by import side-effect.
import monitoring.charts.metrics  # noqa: F401
from monitoring.ui import pages, sidebar


# Install the clean plotly template for every chart.
theme.install_template()

st.set_page_config(
    page_title="ADNOC OSE — Production",
    page_icon="🛢",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Karpathy-style minimal CSS — warm off-white background, narrow content
# column, serif headings, sans-serif body, restrained accents, subtle rules.
_CSS = """
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #FCFAF6;
    color: #1F1A17;
}
[data-testid="stHeader"] { background: transparent; }

.block-container {
    max-width: 1280px;
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

/* Typography */
html, body, [data-testid="stAppViewContainer"] * {
    font-family: Inter, -apple-system, "Helvetica Neue", Arial, sans-serif;
}
h1, h2, h3, h4, .section-title {
    font-family: Charter, "Iowan Old Style", Georgia, serif;
    color: #1A1A1A;
    letter-spacing: 0.1px;
    font-weight: 500;
}
h1 { font-size: 1.75rem; margin-bottom: 0.1rem; }
h1 + p, .title-tag { color: #6B6357; font-size: 0.92rem; }

/* Section headings inside tabs */
.section-title {
    font-size: 1.05rem;
    padding: 0.9rem 0 0.4rem 0;
    margin-top: 1.0rem;
    border-bottom: 1px solid #E5DFD3;
    margin-bottom: 0.9rem;
    color: #2A2620;
}
.section-title .section-subtitle {
    font-family: Inter, sans-serif;
    font-weight: 400;
    color: #8B8374;
    font-size: 0.88rem;
    font-style: italic;
}

/* Tabs: de-emphasised, underline only */
[data-baseweb="tab-list"] {
    gap: 1.6rem !important;
    border-bottom: 1px solid #E5DFD3;
    background: transparent !important;
}
[data-baseweb="tab"] {
    background: transparent !important;
    padding: 0.5rem 0 !important;
    color: #6B6357 !important;
    font-size: 0.95rem;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: #1A1A1A !important;
    border-bottom: 2px solid #C9A44C !important;
    font-weight: 500;
}

/* KPI metrics — strip the box */
[data-testid="stMetric"] {
    background: transparent;
    border: none;
    padding: 0.2rem 0;
}
[data-testid="stMetricLabel"] {
    color: #6B6357;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] {
    font-family: Charter, Georgia, serif;
    font-size: 1.6rem;
    color: #1A1A1A;
    font-weight: 500;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #F5F1E8;
    border-right: 1px solid #E5DFD3;
}
section[data-testid="stSidebar"] * { color: #2A2620; }
section[data-testid="stSidebar"] h2 {
    font-family: Charter, Georgia, serif;
    font-size: 1.05rem;
    color: #1A1A1A;
}

/* Tables */
[data-testid="stDataFrame"] {
    border: 1px solid #E5DFD3;
    border-radius: 4px;
}

/* Alerts: soft cream variants */
[data-testid="stAlertContainer"] {
    background: #F5EFE0 !important;
    border: 1px solid #E5DFD3 !important;
    color: #2A2620 !important;
}

/* Remove most hover shadows to feel calmer */
.stButton > button, .stDownloadButton > button {
    background: #1A1A1A;
    color: #FCFAF6;
    border: 1px solid #1A1A1A;
    border-radius: 3px;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: #2A2620; color: #FCFAF6;
}

/* Caption tone */
.stCaption, .caption, small { color: #8B8374; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

st.markdown(
    "<h1>ADNOC Onshore South East — Production</h1>"
    "<p class='title-tag'>Field · Reservoir · Well · Diagnostics — "
    "OFM-backed interactive dashboard</p>",
    unsafe_allow_html=True,
)

cfg, f = sidebar.render_sidebar()

st.markdown(
    f"<div class='caption' style='margin: 0.3rem 0 1.0rem 0; color:#6B6357; font-size:0.88rem;'>"
    f"<b>{cfg.name}</b> &nbsp;·&nbsp; {f.level.capitalize()} "
    f"&nbsp;·&nbsp; {len(f.selected)} selected "
    f"&nbsp;·&nbsp; {f.start} → {f.end} "
    f"&nbsp;·&nbsp; {f.freq}"
    "</div>",
    unsafe_allow_html=True,
)

pages.render(cfg, f)
