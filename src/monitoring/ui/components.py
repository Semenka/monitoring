"""Small reusable Streamlit UI widgets."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def kpi_card(label: str, value: float | str, unit: str = "", help: str | None = None) -> None:
    st.metric(label, f"{value:,.0f} {unit}" if isinstance(value, (int, float)) else str(value), help=help)


def download_csv(
    df: pd.DataFrame,
    filename: str,
    label: str = "Download CSV",
    key: str | None = None,
) -> None:
    if df.empty:
        return
    st.download_button(
        label, df.to_csv(index=False).encode(),
        file_name=filename, mime="text/csv",
        key=key or f"dl_{filename}",
    )


def data_quality_checks(con) -> pd.DataFrame:
    checks = []
    # Hierarchy reconciliation at field level
    row = con.execute(
        """
        WITH field_total AS (
            SELECT h.field, SUM(m.oil_vol) AS field_oil
            FROM v_monthly m JOIN v_hierarchy h USING (entity_id)
            WHERE h.well IS NOT NULL
            GROUP BY h.field
        ),
        well_total AS (
            SELECT h.field, SUM(m.oil_vol) AS well_oil
            FROM v_monthly m JOIN v_hierarchy h USING (entity_id)
            WHERE h.well IS NOT NULL
            GROUP BY h.field
        )
        SELECT f.field, f.field_oil, w.well_oil,
               ABS(f.field_oil - w.well_oil) / NULLIF(f.field_oil, 0) AS rel_err
        FROM field_total f JOIN well_total w USING (field)
        """
    ).df()
    checks.append(row)

    neg = con.execute(
        """SELECT COUNT(*) AS negative_volumes FROM v_monthly
           WHERE oil_vol < 0 OR water_vol < 0 OR gas_vol < 0 OR wtr_inj < 0 OR gas_inj < 0"""
    ).df()
    checks.append(neg)

    bad_days = con.execute(
        """SELECT COUNT(*) AS rows_days_gt_31 FROM v_monthly WHERE days_on > 31"""
    ).df()
    checks.append(bad_days)
    return pd.concat(checks, axis=1)
