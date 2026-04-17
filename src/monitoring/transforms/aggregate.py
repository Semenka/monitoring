"""Aggregation helpers (used on client side after DuckDB returns a tidy frame)."""
from __future__ import annotations

import pandas as pd


def pivot_by_entity(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Wide frame: index=date, columns=entity, values=value_col."""
    return df.pivot_table(index="date", columns="entity", values=value_col, aggfunc="sum").sort_index()


def totals_by_date(df: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    return df.groupby("date")[value_cols].sum().reset_index()
