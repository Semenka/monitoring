"""Level-aware production queries built on the canonical DuckDB warehouse."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd

from monitoring.domain import schema as S


FREQ_MAP = {"D": "day", "M": "month", "Y": "year"}


@dataclass
class FilterState:
    level: str                    # 'field' | 'reservoir' | 'well'
    selected: list[str]           # names at that level (e.g. well names)
    start: date | None = None
    end: date | None = None
    freq: str = "M"               # 'D' | 'M' | 'Y'


def _group_col(level: str) -> str:
    return {"field": "field", "reservoir": "reservoir", "well": "well"}[level.lower()]


def fetch_production(con: duckdb.DuckDBPyConnection, f: FilterState) -> pd.DataFrame:
    """Return a tidy DataFrame keyed by (date, entity_label) with canonical volume cols.

    Volumes are summed; BHP/THP averaged. Empty selection returns an empty frame.
    """
    group = _group_col(f.level)
    params: list = []
    where = ["1=1"]

    if f.selected:
        placeholders = ",".join(["?"] * len(f.selected))
        where.append(f"h.{group} IN ({placeholders})")
        params.extend(f.selected)

    if f.start is not None:
        where.append(f"m.{S.DATE} >= ?")
        params.append(f.start)
    if f.end is not None:
        where.append(f"m.{S.DATE} <= ?")
        params.append(f.end)

    trunc = FREQ_MAP[f.freq]

    sql = f"""
    SELECT
        date_trunc('{trunc}', m.{S.DATE})::DATE AS {S.DATE},
        h.{group} AS entity,
        SUM(m.{S.OIL_VOL})   AS {S.OIL_VOL},
        SUM(m.{S.WATER_VOL}) AS {S.WATER_VOL},
        SUM(m.{S.GAS_VOL})   AS {S.GAS_VOL},
        SUM(m.{S.WTR_INJ})   AS {S.WTR_INJ},
        SUM(m.{S.GAS_INJ})   AS {S.GAS_INJ},
        SUM(m.{S.DAYS_ON})   AS {S.DAYS_ON},
        AVG(m.{S.BHP})       AS {S.BHP},
        AVG(m.{S.THP})       AS {S.THP}
    FROM v_monthly m
    JOIN v_hierarchy h USING ({S.ENTITY_ID})
    WHERE {' AND '.join(where)} AND h.{group} IS NOT NULL
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return con.execute(sql, params).df()


def date_bounds(con: duckdb.DuckDBPyConnection) -> tuple[date | None, date | None]:
    row = con.execute(f"SELECT MIN({S.DATE}), MAX({S.DATE}) FROM v_monthly").fetchone()
    if not row or row[0] is None:
        return None, None
    return row[0].date() if hasattr(row[0], "date") else row[0], (
        row[1].date() if hasattr(row[1], "date") else row[1]
    )


def available_levels(con: duckdb.DuckDBPyConnection, level: str) -> list[str]:
    col = _group_col(level)
    return [
        r[0]
        for r in con.execute(
            f"SELECT DISTINCT {col} FROM v_hierarchy WHERE {col} IS NOT NULL ORDER BY 1"
        ).fetchall()
    ]
