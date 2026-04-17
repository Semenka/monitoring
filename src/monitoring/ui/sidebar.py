"""Sidebar filter widgets."""
from __future__ import annotations

from datetime import date

import streamlit as st

from monitoring.config import DBConfig, list_configs, load_db_config
from monitoring.domain.queries import FilterState, available_levels, date_bounds
from monitoring.io import warehouse


def render_sidebar() -> tuple[DBConfig, FilterState]:
    st.sidebar.header("Dashboard controls")

    configs = list_configs()
    if not configs:
        st.sidebar.error("No configs found in `configs/`. Add a YAML config to proceed.")
        st.stop()

    names = [p.stem for p in configs]
    selected = st.sidebar.selectbox("Database", names, index=0, key="db_select")
    cfg = load_db_config([p for p in configs if p.stem == selected][0])

    if not cfg.warehouse_path.exists():
        st.sidebar.error(
            f"Warehouse `{cfg.warehouse_path}` not found.\n"
            f"Run: `python -m scripts.convert_mdb --config configs/{selected}.yaml`"
        )
        st.stop()

    con = warehouse.get_conn(cfg)
    level = st.sidebar.radio("Level", ["Field", "Reservoir", "Well"], horizontal=True).lower()

    options = available_levels(con, level)
    selected_names = st.sidebar.multiselect(
        f"{level.capitalize()}s", options,
        default=options[: min(5, len(options))],
    )

    dmin, dmax = date_bounds(con)
    if dmin is None or dmax is None:
        st.sidebar.error("No production dates found in warehouse.")
        st.stop()
    drange = st.sidebar.date_input(
        "Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax
    )
    if isinstance(drange, tuple) and len(drange) == 2:
        start, end = drange
    else:
        start, end = dmin, dmax

    freq_label = st.sidebar.selectbox("Aggregation", ["Monthly", "Yearly", "Daily"], index=0)
    freq = {"Daily": "D", "Monthly": "M", "Yearly": "Y"}[freq_label]

    con.close()

    return cfg, FilterState(level=level, selected=selected_names, start=start, end=end, freq=freq)
