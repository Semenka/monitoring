"""Tab renderers: Overview / Production / Injection / Ratios / Wells / Data Quality.

Every `st.plotly_chart` call is given a unique `key` to avoid Streamlit's
"DuplicateElementId" error; every chart is rendered from exactly one tab
(via its `category` in the registry).
"""
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
    import duckdb
    con = duckdb.connect(warehouse_path, read_only=True)
    f = FilterState(level=f_tuple[0], selected=list(f_tuple[1]),
                    start=f_tuple[2], end=f_tuple[3], freq=f_tuple[4])
    df = fetch_production(con, f)
    con.close()
    return df


def _render_grid(charts: list[Chart], df: pd.DataFrame, prefix: str) -> None:
    """Render charts in two columns; `prefix` scopes the element keys per tab."""
    if not charts:
        st.caption("No charts available for this level/category.")
        return
    cols = st.columns(2)
    for i, chart in enumerate(charts):
        with cols[i % 2]:
            st.plotly_chart(
                builders.build(chart, df),
                use_container_width=True,
                key=f"{prefix}_{chart.id}",
            )


def render(cfg: DBConfig, f: FilterState) -> None:
    f_tuple = (f.level, tuple(f.selected), f.start, f.end, f.freq)
    df = _load(cfg.name, str(cfg.warehouse_path), f_tuple)

    tabs = st.tabs(["Overview", "Production", "Injection", "Ratios", "Wells table", "Data quality"])

    with tabs[0]:
        _overview(df, cfg, f)

    with tabs[1]:
        _render_grid(REGISTRY.charts_by_category(f.level, "production"), df, prefix="prod")

    with tabs[2]:
        _render_grid(REGISTRY.charts_by_category(f.level, "injection"), df, prefix="inj")

    with tabs[3]:
        charts = (REGISTRY.charts_by_category(f.level, "ratio")
                  + REGISTRY.charts_by_category(f.level, "pressure"))
        if not charts:
            st.caption("No ratio/pressure charts at this level.")
        _render_grid(charts, df, prefix="ratio")

    with tabs[4]:
        _wells_table(cfg, f)

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
    c1.metric("Cumulative oil",   f"{total_oil/1e6:,.2f} MMbbl")
    c2.metric("Cumulative water", f"{total_water/1e6:,.2f} MMbbl")
    c3.metric("Cumulative gas",   f"{total_gas/1e6:,.2f} MMmscf")
    c4.metric(f"{f.level.capitalize()}s in view", f"{active_entities}")

    overview_charts = REGISTRY.charts_by_category(f.level, "overview")
    for chart in overview_charts:
        st.plotly_chart(
            builders.build(chart, df),
            use_container_width=True,
            key=f"overview_{chart.id}",
        )


def _wells_table(cfg: DBConfig, f: FilterState) -> None:
    con = warehouse.get_conn(cfg)
    base_col = {"field": "field", "reservoir": "reservoir", "well": "well"}[f.level]
    where = ""
    params: list = []
    if f.selected:
        placeholders = ",".join(["?"] * len(f.selected))
        where = f"WHERE h.{base_col} IN ({placeholders})"
        params = f.selected

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

    if df.empty:
        st.info("No rows for the current selection.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, key="wells_table_df")
    components.download_csv(df, f"wells_{cfg.name.lower()}.csv", key="wells_dl")


def _data_quality(cfg: DBConfig) -> None:
    con = warehouse.get_conn(cfg)
    recon = con.execute(
        """
        SELECT h.field,
               SUM(m.oil_vol) AS well_sum_oil
        FROM v_monthly m JOIN v_hierarchy h USING (entity_id)
        WHERE h.well IS NOT NULL
        GROUP BY h.field
        ORDER BY 1
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

    st.subheader("Total oil per field (wells reconciliation)")
    st.dataframe(recon, use_container_width=True, hide_index=True, key="dq_recon_df")

    st.subheader("Out-of-range counts")
    st.dataframe(neg_counts, use_container_width=True, hide_index=True, key="dq_neg_df")

    st.caption("Expect zero negative volumes and days_on ≤ 31 per month.")
