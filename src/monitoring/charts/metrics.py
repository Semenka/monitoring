"""Built-in metric + chart definitions.

Importing this module registers everything with monitoring.charts.registry.

Units follow UAE / ADNOC field conventions:
  - Liquid rate: BBL/D (barrels per day) — "BOPD" / "BWPD"
  - Gas   rate: MMscf/D
  - Cumulative liquid: MMbbl
  - Cumulative gas:    Bcf
  - Pressure: psi
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from monitoring.charts.registry import register_chart, register_metric
from monitoring.domain import schema as S
from monitoring.transforms import derived


# Convert "monthly cumulative volume" → "average rate over the period".
# DuckDB has already SUM()-ed both volume and days_on for the chosen
# aggregation level (D / M / Y), so dividing yields a volume-weighted rate.
def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.replace(0, pd.NA)


# === Daily rates (UAE field units) =========================================

@register_metric("oil_rate", "Oil rate", unit="BOPD",
                 needs=[S.OIL_VOL, S.DAYS_ON])
def _oil_rate(df): return _safe_div(df[S.OIL_VOL], df[S.DAYS_ON])


@register_metric("water_rate", "Water rate", unit="BWPD",
                 needs=[S.WATER_VOL, S.DAYS_ON])
def _water_rate(df): return _safe_div(df[S.WATER_VOL], df[S.DAYS_ON])


@register_metric("gas_rate", "Gas rate", unit="MMscf/d",
                 needs=[S.GAS_VOL, S.DAYS_ON])
def _gas_rate(df):
    # Source gas volume is in mscf; rate target is MMscf/d → divide by 1000.
    return _safe_div(df[S.GAS_VOL] / 1000.0, df[S.DAYS_ON])


@register_metric("wtr_inj_rate", "Water injection rate", unit="BWIPD",
                 needs=[S.WTR_INJ, S.DAYS_ON])
def _wtr_inj_rate(df): return _safe_div(df[S.WTR_INJ], df[S.DAYS_ON])


@register_metric("gas_inj_rate", "Gas injection rate", unit="MMscf/d",
                 needs=[S.GAS_INJ, S.DAYS_ON])
def _gas_inj_rate(df): return _safe_div(df[S.GAS_INJ] / 1000.0, df[S.DAYS_ON])


# === Cumulative volumes ====================================================
# These are computed downstream of the query, so they need a "running sum"
# applied per entity within the builder. We tag them with `cumulative=True`.

@register_metric("cum_oil",  "Cumulative oil",   unit="MMbbl",
                 needs=[S.OIL_VOL],   cumulative=True)
def _cum_oil(df):  return df[S.OIL_VOL] / 1e6


@register_metric("cum_water", "Cumulative water", unit="MMbbl",
                 needs=[S.WATER_VOL], cumulative=True)
def _cum_water(df): return df[S.WATER_VOL] / 1e6


@register_metric("cum_gas",  "Cumulative gas",   unit="Bcf",
                 needs=[S.GAS_VOL],   cumulative=True)
def _cum_gas(df):  return df[S.GAS_VOL] / 1e6      # mscf → Bcf (×10^-6)


@register_metric("cum_wtr_inj", "Cumulative water injection", unit="MMbbl",
                 needs=[S.WTR_INJ], cumulative=True)
def _cum_wtr_inj(df): return df[S.WTR_INJ] / 1e6


@register_metric("cum_gas_inj", "Cumulative gas injection", unit="Bcf",
                 needs=[S.GAS_INJ], cumulative=True)
def _cum_gas_inj(df): return df[S.GAS_INJ] / 1e6


# === Ratios ================================================================

@register_metric("gor", "GOR", unit="scf/bbl",
                 needs=[S.OIL_VOL, S.GAS_VOL], kind="ratio")
def _gor(df): return derived.gor(df)


@register_metric("wct", "Water cut", unit="frac",
                 needs=[S.OIL_VOL, S.WATER_VOL], kind="ratio")
def _wct(df): return derived.wct(df)


@register_metric("wor", "Water-Oil Ratio", unit="bbl/bbl",
                 needs=[S.OIL_VOL, S.WATER_VOL], kind="ratio")
def _wor(df): return _safe_div(df[S.WATER_VOL], df[S.OIL_VOL])


@register_metric("vrr", "Voidage Replacement Ratio", unit="ratio",
                 needs=[S.OIL_VOL, S.WATER_VOL, S.GAS_VOL,
                        S.WTR_INJ, S.GAS_INJ], kind="ratio")
def _vrr(df): return derived.voidage_replacement(df)


# === Pressures (optional; only register chart if columns mapped) ===========

@register_metric("bhp", "Bottomhole pressure", unit="psi",
                 needs=[S.BHP], levels=("well",), kind="pressure")
def _bhp(df): return df[S.BHP]


@register_metric("thp", "Tubing head pressure", unit="psi",
                 needs=[S.THP], levels=("well",), kind="pressure")
def _thp(df): return df[S.THP]


# === Charts ================================================================

# --- Production rates (one phase per chart, UAE units) ---
register_chart("rate_oil",   "Oil rate",   ["oil_rate"],   kind="line", category="production",
               y_title="BOPD")
register_chart("rate_water", "Water rate", ["water_rate"], kind="line", category="production",
               y_title="BWPD")
register_chart("rate_gas",   "Gas rate",   ["gas_rate"],   kind="line", category="production",
               y_title="MMscf/d")

# --- Cumulative production (one chart per phase) ---
register_chart("cum_oil_chart",   "Cumulative oil",   ["cum_oil"],   kind="line",
               category="production", per_entity=True, y_title="MMbbl")
register_chart("cum_water_chart", "Cumulative water", ["cum_water"], kind="line",
               category="production", per_entity=True, y_title="MMbbl")
register_chart("cum_gas_chart",   "Cumulative gas",   ["cum_gas"],   kind="line",
               category="production", per_entity=True, y_title="Bcf")

# --- Overview: stacked production mix (KPIs already on the tab) ---
register_chart("prod_mix", "Production mix (oil / water / gas)",
               ["oil_rate", "water_rate", "gas_rate"], kind="lines_dual",
               category="overview", per_entity=False)

# --- Injection (separate per phase, UAE units) ---
register_chart("inj_water_rate", "Water injection rate", ["wtr_inj_rate"],
               kind="line", category="injection", y_title="BWIPD")
register_chart("inj_gas_rate", "Gas injection rate", ["gas_inj_rate"],
               kind="line", category="injection", y_title="MMscf/d")
register_chart("cum_inj_water", "Cumulative water injection", ["cum_wtr_inj"],
               kind="line", category="injection", per_entity=True, y_title="MMbbl")
register_chart("cum_inj_gas",   "Cumulative gas injection",   ["cum_gas_inj"],
               kind="line", category="injection", per_entity=True, y_title="Bcf")

# --- Ratios (Field & Reservoir) ---
register_chart("gor_trend", "GOR vs time",        ["gor"], kind="line",
               applicable_levels=("field", "reservoir"), category="ratio",
               y_title="scf/bbl")
register_chart("wct_trend", "Water cut vs time",  ["wct"], kind="line",
               applicable_levels=("field", "reservoir"), category="ratio",
               y_title="fraction")
register_chart("wor_trend", "WOR vs time",        ["wor"], kind="line_log",
               applicable_levels=("field", "reservoir"), category="ratio",
               y_title="bbl/bbl (log)")
register_chart("vrr_trend", "Voidage Replacement Ratio (VRR)", ["vrr"], kind="line",
               applicable_levels=("field", "reservoir"), category="ratio",
               y_title="ratio")

# --- Pressures (Well only) ---
register_chart("bhp_trend", "Bottomhole pressure", ["bhp"], kind="line",
               applicable_levels=("well",), category="pressure",
               y_title="psi")
register_chart("thp_trend", "Tubing head pressure", ["thp"], kind="line",
               applicable_levels=("well",), category="pressure",
               y_title="psi")

# --- Diagnostics (cross-plots) ---
register_chart("decline_oil", "Decline curve (semilog oil rate)", ["oil_rate"],
               kind="line_logy", category="diagnostic", y_title="BOPD (log)")
register_chart("wct_vs_np",   "WCT vs cumulative oil",  ["wct"],
               kind="xy", category="diagnostic",
               x_metric="cum_oil", y_title="WCT (frac)", x_title="Np (MMbbl)")
register_chart("gor_vs_np",   "GOR vs cumulative oil",  ["gor"],
               kind="xy", category="diagnostic",
               x_metric="cum_oil", y_title="GOR (scf/bbl)", x_title="Np (MMbbl)")
register_chart("wp_vs_np",    "Wp vs Np",               ["cum_water"],
               kind="xy", category="diagnostic",
               x_metric="cum_oil", y_title="Wp (MMbbl)", x_title="Np (MMbbl)")
