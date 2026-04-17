"""Built-in metric + chart definitions.

Importing this module registers everything with monitoring.charts.registry.
"""
from __future__ import annotations

from monitoring.charts.registry import register_chart, register_metric
from monitoring.domain import schema as S
from monitoring.transforms import derived


# --- Raw volumes -----------------------------------------------------------

@register_metric("oil", "Oil production", unit="bbl", needs=[S.OIL_VOL])
def _oil(df): return df[S.OIL_VOL]


@register_metric("water", "Water production", unit="bbl", needs=[S.WATER_VOL])
def _water(df): return df[S.WATER_VOL]


@register_metric("gas", "Gas production", unit="mscf", needs=[S.GAS_VOL])
def _gas(df): return df[S.GAS_VOL]


@register_metric("wtr_inj", "Water injection", unit="bbl", needs=[S.WTR_INJ])
def _wtr_inj(df): return df[S.WTR_INJ]


@register_metric("gas_inj", "Gas injection", unit="mscf", needs=[S.GAS_INJ])
def _gas_inj(df): return df[S.GAS_INJ]


# --- Derived ratios --------------------------------------------------------

@register_metric("gor", "GOR", unit="scf/bbl", needs=[S.OIL_VOL, S.GAS_VOL], kind="ratio")
def _gor(df): return derived.gor(df)


@register_metric("wct", "Water cut", unit="frac", needs=[S.OIL_VOL, S.WATER_VOL], kind="ratio")
def _wct(df): return derived.wct(df)


# --- Pressures (optional) --------------------------------------------------

@register_metric("bhp", "Bottomhole pressure", unit="psi", needs=[S.BHP],
                 levels=("well",), kind="pressure")
def _bhp(df): return df[S.BHP]


@register_metric("thp", "Tubing head pressure", unit="psi", needs=[S.THP],
                 levels=("well",), kind="pressure")
def _thp(df): return df[S.THP]


# --- Charts ----------------------------------------------------------------

register_chart("prod_oil", "Oil production",  ["oil"],   kind="line")
register_chart("prod_water", "Water production", ["water"], kind="line")
register_chart("prod_gas", "Gas production",  ["gas"],   kind="line")
register_chart("prod_stacked", "Production mix (oil/water/gas-equiv)",
               ["oil", "water", "gas"], kind="stacked", per_entity=False,
               y_title="volume")

register_chart("inj_water", "Water injection", ["wtr_inj"], kind="line")
register_chart("inj_gas", "Gas injection",   ["gas_inj"], kind="line")

register_chart("gor_trend", "GOR",  ["gor"], kind="line",
               applicable_levels=("field", "reservoir"), per_entity=True)
register_chart("wct_trend", "Water cut (WCT)", ["wct"], kind="line",
               applicable_levels=("field", "reservoir"), per_entity=True)

register_chart("bhp_trend", "BHP", ["bhp"], kind="line",
               applicable_levels=("well",), per_entity=True)
register_chart("thp_trend", "THP", ["thp"], kind="line",
               applicable_levels=("well",), per_entity=True)
