"""Entity hierarchy utilities."""
from __future__ import annotations

import duckdb
import pandas as pd

from monitoring.domain import schema as S


def entity_tree(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return one row per entity, with resolved field/reservoir/well labels."""
    return con.execute(
        f"""
        SELECT e.{S.ENTITY_ID}, e.{S.ENTITY_NAME}, UPPER(e.{S.ENTITY_LEVEL}) AS level,
               h.field, h.reservoir, h.well
        FROM v_entity e
        LEFT JOIN v_hierarchy h USING ({S.ENTITY_ID})
        ORDER BY h.field, h.reservoir, h.well
        """
    ).df()


def wells_of(con: duckdb.DuckDBPyConnection, level: str, names: list[str]) -> list[str]:
    """Resolve a selection at some level to the list of well entity_ids under it."""
    if not names:
        return []
    col = level.lower()
    placeholders = ",".join(["?"] * len(names))
    rows = con.execute(
        f"SELECT DISTINCT entity_id FROM v_hierarchy "
        f"WHERE {col} IN ({placeholders}) AND well IS NOT NULL",
        names,
    ).fetchall()
    return [r[0] for r in rows]
