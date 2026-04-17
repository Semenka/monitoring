"""Streamlit entrypoint: ADNOC Onshore South East production dashboard."""
from __future__ import annotations

import streamlit as st

# Register all built-in metrics/charts by import side-effect.
import monitoring.charts.metrics  # noqa: F401
from monitoring.ui import pages, sidebar


st.set_page_config(
    page_title="ADNOC OSE Production Dashboard",
    page_icon=":oil_drum:",
    layout="wide",
)

st.title("ADNOC Onshore South East – Production Dashboard")

cfg, f = sidebar.render_sidebar()
st.caption(
    f"**Database:** {cfg.name}  ·  "
    f"**Level:** {f.level.capitalize()}  ·  "
    f"**Entities:** {len(f.selected)}  ·  "
    f"**Period:** {f.start} → {f.end}  ·  "
    f"**Aggregation:** {f.freq}"
)

pages.render(cfg, f)
