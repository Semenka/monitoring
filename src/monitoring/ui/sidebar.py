"""Sidebar filter widgets."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from monitoring.config import DBConfig, list_configs, load_db_config
from monitoring.domain.queries import FilterState, available_levels, date_bounds
from monitoring.io import warehouse


def _label_for(cfg: DBConfig) -> str:
    status = "ready" if cfg.warehouse_path.exists() else "not built"
    tag = " (demo)" if cfg.synthetic else ""
    return f"{cfg.name}{tag} — {status}"


def render_sidebar() -> tuple[DBConfig, FilterState]:
    st.sidebar.header("Dashboard controls")

    configs = list_configs()
    if not configs:
        st.sidebar.error("No configs found in `configs/`. Add a YAML config to proceed.")
        st.stop()

    parsed = [load_db_config(p) for p in configs]
    # Ready first, then the rest. Demo samples float up within each bucket.
    parsed.sort(key=lambda c: (not c.warehouse_path.exists(), not c.synthetic, c.name))

    labels = [_label_for(c) for c in parsed]
    idx = st.sidebar.selectbox(
        "Database", list(range(len(parsed))),
        format_func=lambda i: labels[i],
        index=0,
        key="db_select",
    )
    cfg = parsed[idx]

    if not cfg.warehouse_path.exists():
        st.sidebar.warning(
            f"Warehouse `{cfg.warehouse_path}` not built.\n\n"
            f"**To enable {cfg.name}:**\n"
            f"1. Download the `.mdb` file(s) from Google Drive into `data/raw/`.\n"
            f"2. Run `python scripts/convert_mdb.py --config configs/{Path(configs[idx]).stem}.yaml`\n\n"
            "Then select a ready database above."
        )
        ready = [c for c in parsed if c.warehouse_path.exists()]
        if not ready:
            st.sidebar.info("Tip: run `python scripts/generate_sample.py && "
                            "python scripts/convert_mdb.py --config configs/sample.yaml` "
                            "to explore the dashboard with synthetic data.")
            st.stop()
        # fall back to first ready DB
        cfg = ready[0]
        st.sidebar.info(f"Showing **{cfg.name}** instead.")

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
