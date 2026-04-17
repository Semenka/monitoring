"""Tab renderers: Overview / Production / Injection / Ratios / Wells / Data Quality."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from monitoring.charts import builders
from monitoring.charts.registry import REGISTRY, Chart
from monitoring.config import DBConfig
from monitoring.domain import schema as S
from monitoring.domain.queries import FilterState, fetch_production
from monitoring.io import warehouse
from monitoring.ui import components


@st.cache_data(ttl=3600, show_spinner="Loading production data …")
def _load(db_name: str, warehouse_path: str, f_tuple: tuple) -> pd.DataFrame:
    # f_tuple = (level, selected, start, end, freq)
    import duckdb
    con = duckdb.connect(warehouse_path, read_only=True)
    f = FilterState(level=f_tuple[0], selected=list(f_tuple[1]),
                    start=f_tuple[2], end=f_tuple[3], freq=f_tuple[4])
    df = fetch_production(con, f)
    con.close()
    return df


def _render_charts(df: pd.DataFrame, level: str, group: str) -> None:
    charts: list[Chart] = [c for c in REGISTRY.charts.values()
                           if level in c.applicable_levels
                           and all(m in REGISTRY.metrics for m in c.metrics)
                           and REGISTRY.metrics[c.metrics[0]].kind == group]
    if not charts:
        st.info(f"No charts registered for group={group} at level={level}.")
        return
    cols = st.columns(2)
    for i, chart in enumerate(charts):
        with cols[i % 2]:
            st.plotly_chart(builders.build(chart, df), use_container_width=True)


def render(cfg: DBConfig, f: FilterState) -> None:
    f_tuple = (f.level, tuple(f.selected), f.start, f.end, f.freq)
    df = _load(cfg.name, str(cfg.warehouse_path), f_tuple)

    tabs = st.tabs(["Overview", "Production", "Injection", "Ratios", "Wells table", "Data quality"])

    # Overview
    with tabs[0]:
        _overview(df, cfg, f)

    # Production
    with tabs[1]:
        _render_charts(df, f.level, "volume")
        vol_charts = [c for c in REGISTRY.charts.values()
                      if f.level in c.applicable_levels and c.id == "prod_stacked"]
        for c in vol_charts:
            st.plotly_chart(builders.build(c, df), use_container_width=True)

    # Injection
    with tabs[2]:
        inj = [c for c in REGISTRY.charts.values()
               if f.level in c.applicable_levels and c.id.startswith("inj_")]
        cols = st.columns(2)
        for i, chart in enumerate(inj):
            with cols[i % 2]:
                st.plotly_chart(builders.build(chart, df), use_container_width=True)

    # Ratios
    with tabs[3]:
        ratios = [c for c in REGISTRY.charts.values()
                  if f.level in c.applicable_levels
                  and REGISTRY.metrics[c.metrics[0]].kind in ("ratio", "pressure")]
        if not ratios:
            st.caption("No ratio charts at this level. Switch to Field or Reservoir for GOR/WCT.")
        cols = st.columns(2)
        for i, chart in enumerate(ratios):
            with cols[i % 2]:
                st.plotly_chart(builders.build(chart, df), use_container_width=True)

    # Wells table
    with tabs[4]:
        _wells_table(cfg, f)

    # Data quality
    with tabs[5]:
        _data_quality(cfg)


def _overview(df: pd.DataFrame, cfg: DBConfig, f: FilterState) -> None:
    if df.empty:
        st.info("Make a selection in the sidebar to see data.")
        return
    total_oil = df[S.OIL_VOL].sum()
    total_water = df[S.WATER_VOL].sum()
    total_gas = df[S.GAS_VOL].sum()
    active_entities = df["entity"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cumulative oil", f"{total_oil/1e6:,.2f} MMbbl")
    c2.metric("Cumulative water", f"{total_water/1e6:,.2f} MMbbl")
    c3.metric("Cumulative gas", f"{total_gas/1e6:,.2f} MMmscf")
    c4.metric(f"{f.level.capitalize()}s in view", f"{active_entities}")

    c = REGISTRY.charts["prod_stacked"]
    st.plotly_chart(builders.build(c, df), use_container_width=True)


def _wells_table(cfg: DBConfig, f: FilterState) -> None:
    con = warehouse.get_conn(cfg)
    placeholders = ",".join(["?"] * len(f.selected)) if f.selected else "NULL"
    if f.level == "well":
        base_col, vals = "well", f.selected
    elif f.level == "reservoir":
        base_col, vals = "reservoir", f.selected
    else:
        base_col, vals = "field", f.selected

    where = ""
    params = []
    if vals:
        where = f"WHERE h.{base_col} IN ({placeholders})"
        params = vals

    df = con.execute(
        f"""
        SELECT h.field, h.reservoir, h.well,
               SUM(m.oil_vol) AS oil_bbl,
               SUM(m.water_vol) AS water_bbl,
               SUM(m.gas_vol) AS gas_mscf,
               SUM(m.wtr_inj) AS wtr_inj_bbl,
               SUM(m.gas_inj) AS gas_inj_mscf
        FROM v_monthly m JOIN v_hierarchy h USING (entity_id)
        {where}
        GROUP BY h.field, h.reservoir, h.well
        ORDER BY oil_bbl DESC NULLS LAST
        """, params
    ).df()
    con.close()
    st.dataframe(df, use_container_width=True, hide_index=True)
    components.download_csv(df, f"wells_{cfg.name.lower()}.csv")


def _data_quality(cfg: DBConfig) -> None:
    con = warehouse.get_conn(cfg)
    recon = con.execute(
        """
        SELECT h.field,
               SUM(m.oil_vol) FILTER (WHERE h.well IS NOT NULL) AS well_sum,
               (SELECT SUM(m2.oil_vol) FROM v_monthly m2 JOIN v_hierarchy h2 USING (entity_id)
                WHERE h2.field = h.field AND h2.well IS NOT NULL) AS field_total
        FROM v_monthly m JOIN v_hierarchy h USING (entity_id)
        WHERE h.well IS NOT NULL
        GROUP BY h.field
        """
    ).df()

    neg_counts = con.execute(
        """SELECT
             SUM((oil_vol<0)::INT)   AS oil_neg,
             SUM((water_vol<0)::INT) AS water_neg,
             SUM((gas_vol<0)::INT)   AS gas_neg,
             SUM((wtr_inj<0)::INT)   AS wtr_inj_neg,
             SUM((gas_inj<0)::INT)   AS gas_inj_neg,
             SUM((days_on>31)::INT)  AS days_gt_31
           FROM v_monthly"""
    ).df()
    con.close()

    st.subheader("Hierarchy reconciliation (wells sum vs field)")
    st.dataframe(recon, use_container_width=True, hide_index=True)

    st.subheader("Out-of-range counts")
    st.dataframe(neg_counts, use_container_width=True, hide_index=True)

    st.caption("Expect zero negative volumes and days_on ≤ 31 per month.")
