"""Tab renderers: Overview · Production · Injection · Ratios · Diagnostics ·
Pressure · Wells table · Data quality.

Every `st.plotly_chart` call carries a unique `key` to avoid Streamlit's
`DuplicateElementId` error; each chart is rendered from exactly one tab (via
its `category` in the registry).
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


def _render_grid(charts: list[Chart], df: pd.DataFrame, prefix: str, cols_per_row: int = 2) -> None:
    if not charts:
        st.caption("No charts available for this level.")
        return
    cols = st.columns(cols_per_row)
    for i, chart in enumerate(charts):
        with cols[i % cols_per_row]:
            st.plotly_chart(
                builders.build(chart, df),
                use_container_width=True,
                key=f"{prefix}_{chart.id}",
            )


def _section(title: str, subtitle: str | None = None) -> None:
    st.markdown(
        f"<div class='section-title'>{title}"
        + (f"<span class='section-subtitle'> — {subtitle}</span>" if subtitle else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def render(cfg: DBConfig, f: FilterState) -> None:
    f_tuple = (f.level, tuple(f.selected), f.start, f.end, f.freq)
    df = _load(cfg.name, str(cfg.warehouse_path), f_tuple)

    tabs = st.tabs([
        "Overview", "Production", "Injection", "Ratios",
        "Diagnostics", "Pressure", "Wells", "Data quality",
    ])

    with tabs[0]:
        _overview(df, cfg, f)

    with tabs[1]:
        _section("Production rates", "Per-phase oil / water / gas flow rates (UAE field units)")
        rate_charts = [c for c in REGISTRY.charts_by_category(f.level, "production")
                       if not c.metrics[0].startswith("cum_")]
        _render_grid(rate_charts, df, prefix="prod_rate", cols_per_row=3)

        _section("Cumulative production")
        cum_charts = [c for c in REGISTRY.charts_by_category(f.level, "production")
                      if c.metrics[0].startswith("cum_")]
        _render_grid(cum_charts, df, prefix="prod_cum", cols_per_row=3)

    with tabs[2]:
        _section("Injection rates")
        inj_rate = [c for c in REGISTRY.charts_by_category(f.level, "injection")
                    if not c.metrics[0].startswith("cum_")]
        _render_grid(inj_rate, df, prefix="inj_rate")

        _section("Cumulative injection")
        inj_cum = [c for c in REGISTRY.charts_by_category(f.level, "injection")
                   if c.metrics[0].startswith("cum_")]
        _render_grid(inj_cum, df, prefix="inj_cum")

    with tabs[3]:
        ratio = REGISTRY.charts_by_category(f.level, "ratio")
        if not ratio:
            st.caption("Ratios are shown at Field & Reservoir level.")
        _section("Fluid ratios")
        _render_grid(ratio, df, prefix="ratio")

    with tabs[4]:
        diag = REGISTRY.charts_by_category(f.level, "diagnostic")
        if not diag:
            st.caption("No diagnostic plots available at this level.")
        _section("Diagnostic plots",
                 "Decline curves, recovery cross-plots and WOR/GOR diagnostics")
        _render_grid(diag, df, prefix="diag")

    with tabs[5]:
        pres = REGISTRY.charts_by_category(f.level, "pressure")
        if not pres:
            st.caption("Pressure charts are shown at Well level (requires `bhp`/`thp` "
                       "to be mapped in the YAML config).")
        _section("Pressures")
        _render_grid(pres, df, prefix="pres")

    with tabs[6]:
        _wells_table(cfg, f)

    with tabs[7]:
        _data_quality(cfg)


def _overview(df: pd.DataFrame, cfg: DBConfig, f: FilterState) -> None:
    if df.empty:
        st.info("Make a selection in the sidebar to see data.")
        return

    total_oil = df[S.OIL_VOL].sum()
    total_water = df[S.WATER_VOL].sum()
    total_gas = df[S.GAS_VOL].sum()
    total_days = df[S.DAYS_ON].sum()
    avg_oil_rate = total_oil / total_days if total_days else 0
    avg_gas_rate = (total_gas / 1000.0) / total_days if total_days else 0
    wct_overall = total_water / (total_oil + total_water) if (total_oil + total_water) else 0
    active_entities = df["entity"].nunique()

    _section(f"{cfg.name}", f"{f.level.capitalize()} view · {active_entities} selected")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cumulative oil",   f"{total_oil/1e6:,.2f}",  help="MMbbl")
    c2.metric("Average oil rate", f"{avg_oil_rate:,.0f}",    help="BOPD")
    c3.metric("Cumulative gas",   f"{total_gas/1e6:,.2f}",  help="Bcf")
    c4.metric("Water cut (avg)",  f"{wct_overall*100:,.1f}%")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Cumulative water", f"{total_water/1e6:,.2f}", help="MMbbl")
    c6.metric("Avg gas rate",     f"{avg_gas_rate:,.2f}",    help="MMscf/d")
    c7.metric("Days on (sum)",    f"{int(total_days):,}")
    c8.metric(f"{f.level.capitalize()}s", f"{active_entities}")

    _section("Production overview")
    overview_charts = REGISTRY.charts_by_category(f.level, "overview")
    for chart in overview_charts:
        st.plotly_chart(
            builders.build(chart, df),
            use_container_width=True,
            key=f"overview_{chart.id}",
        )


def _wells_table(cfg: DBConfig, f: FilterState) -> None:
    _section("Well-level aggregates")
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
               SUM(m.oil_vol)   / 1e6  AS cum_oil_mmbbl,
               SUM(m.water_vol) / 1e6  AS cum_water_mmbbl,
               SUM(m.gas_vol)   / 1e6  AS cum_gas_bcf,
               SUM(m.wtr_inj)   / 1e6  AS cum_wtr_inj_mmbbl,
               SUM(m.gas_inj)   / 1e6  AS cum_gas_inj_bcf,
               SUM(m.oil_vol)   / NULLIF(SUM(m.days_on), 0)          AS avg_oil_bopd,
               SUM(m.water_vol) / NULLIF(SUM(m.days_on), 0)          AS avg_water_bwpd,
               (SUM(m.gas_vol)/1000.0) / NULLIF(SUM(m.days_on), 0)   AS avg_gas_mmscfd,
               100.0 * SUM(m.water_vol)
                     / NULLIF(SUM(m.oil_vol) + SUM(m.water_vol), 0)  AS wct_pct,
               1000.0 * SUM(m.gas_vol)
                     / NULLIF(SUM(m.oil_vol), 0)                     AS gor_scf_bbl
        FROM v_monthly m JOIN v_hierarchy h USING (entity_id)
        {where}
        GROUP BY h.field, h.reservoir, h.well
        ORDER BY cum_oil_mmbbl DESC NULLS LAST
        """, params
    ).df()
    con.close()

    if df.empty:
        st.info("No rows for the current selection.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key="wells_table_df",
        column_config={
            "cum_oil_mmbbl":     st.column_config.NumberColumn("Cum oil",      format="%.2f MMbbl"),
            "cum_water_mmbbl":   st.column_config.NumberColumn("Cum water",    format="%.2f MMbbl"),
            "cum_gas_bcf":       st.column_config.NumberColumn("Cum gas",      format="%.2f Bcf"),
            "cum_wtr_inj_mmbbl": st.column_config.NumberColumn("Cum W inj",    format="%.2f MMbbl"),
            "cum_gas_inj_bcf":   st.column_config.NumberColumn("Cum G inj",    format="%.2f Bcf"),
            "avg_oil_bopd":      st.column_config.NumberColumn("Avg oil rate", format="%.0f BOPD"),
            "avg_water_bwpd":    st.column_config.NumberColumn("Avg water",    format="%.0f BWPD"),
            "avg_gas_mmscfd":    st.column_config.NumberColumn("Avg gas",      format="%.2f MMscf/d"),
            "wct_pct":           st.column_config.NumberColumn("WCT",          format="%.1f%%"),
            "gor_scf_bbl":       st.column_config.NumberColumn("GOR",          format="%.0f scf/bbl"),
        },
    )
    components.download_csv(df, f"wells_{cfg.name.lower()}.csv", key="wells_dl")


def _data_quality(cfg: DBConfig) -> None:
    _section("Data quality")
    con = warehouse.get_conn(cfg)

    recon = con.execute(
        """
        SELECT h.field,
               COUNT(DISTINCT h.well)         AS n_wells,
               SUM(m.oil_vol)   / 1e6         AS cum_oil_mmbbl,
               SUM(m.water_vol) / 1e6         AS cum_water_mmbbl,
               SUM(m.gas_vol)   / 1e6         AS cum_gas_bcf
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

    st.markdown("**Hierarchy reconciliation** — totals per field (wells sum)")
    st.dataframe(recon, use_container_width=True, hide_index=True, key="dq_recon_df",
                 column_config={
                     "cum_oil_mmbbl":   st.column_config.NumberColumn("Oil",   format="%.2f MMbbl"),
                     "cum_water_mmbbl": st.column_config.NumberColumn("Water", format="%.2f MMbbl"),
                     "cum_gas_bcf":     st.column_config.NumberColumn("Gas",   format="%.2f Bcf"),
                 })

    st.markdown("**Out-of-range counts** — expect zeros")
    st.dataframe(neg_counts, use_container_width=True, hide_index=True, key="dq_neg_df")
