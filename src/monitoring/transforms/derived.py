"""Derived production metrics: GOR, WCT, VRR."""
from __future__ import annotations

import pandas as pd

from monitoring.domain import schema as S


def gor(df: pd.DataFrame) -> pd.Series:
    """Gas-Oil Ratio in scf/bbl. Safe against zero oil."""
    oil = df[S.OIL_VOL].replace(0, pd.NA)
    # gas in mscf -> scf via *1000
    return (df[S.GAS_VOL] * 1000) / oil


def wct(df: pd.DataFrame) -> pd.Series:
    """Water cut (0..1)."""
    total_liquid = df[S.OIL_VOL] + df[S.WATER_VOL]
    return df[S.WATER_VOL] / total_liquid.replace(0, pd.NA)


def voidage_replacement(df: pd.DataFrame) -> pd.Series:
    """Voidage replacement ratio: injected / produced (rough surface proxy)."""
    produced = df[S.OIL_VOL] + df[S.WATER_VOL] + df[S.GAS_VOL] * 5.615 / 1000  # mscf→bbl approx
    injected = df[S.WTR_INJ] + df[S.GAS_INJ] * 5.615 / 1000
    return injected / produced.replace(0, pd.NA)
