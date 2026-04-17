"""Build a DuckDB warehouse with canonical views from staged CSVs.

The canonical schema lives in `monitoring.domain.schema`; the YAML config maps
real OFM columns to those names. We store metadata (.mdb mtime + config hash)
in a `_meta` table so the warehouse can be rebuilt when the source changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from monitoring.config import DBConfig
from monitoring.domain import schema as S


def _config_hash(cfg: DBConfig) -> str:
    return hashlib.sha1(cfg.model_dump_json().encode()).hexdigest()[:12]


def _source_mtime(cfg: DBConfig) -> float:
    mtimes = [p.stat().st_mtime for p in cfg.mdb_paths if p.exists()]
    return max(mtimes) if mtimes else 0.0


def _select_mapping(columns: dict[str, str | None]) -> list[tuple[str, str | None]]:
    """Return [(canonical, source_or_none), ...] preserving declaration order."""
    return list(columns.items())


def _build_col_exprs(mapping: list[tuple[str, str | None]]) -> list[str]:
    parts: list[str] = []
    for canonical, source in mapping:
        if source is None:
            parts.append(f"NULL AS {canonical}")
        else:
            parts.append(f'"{source}" AS {canonical}')
    return parts


def build_duckdb(cfg: DBConfig, force: bool = False) -> Path:
    """Build DuckDB warehouse from staging CSVs. Returns the warehouse path."""
    wh = cfg.warehouse_path
    wh.parent.mkdir(parents=True, exist_ok=True)

    meta_key = {"mtime": _source_mtime(cfg), "hash": _config_hash(cfg)}
    if wh.exists() and not force:
        try:
            con = duckdb.connect(str(wh))
            existing = con.execute("SELECT meta FROM _meta LIMIT 1").fetchone()
            con.close()
            if existing and json.loads(existing[0]) == meta_key:
                return wh
        except Exception:
            pass  # fall through and rebuild
        wh.unlink(missing_ok=True)

    staging = cfg.staging_dir
    entity_csv = staging / f"{cfg.tables.entity.source}.csv"
    monthly_csv = staging / f"{cfg.tables.monthly.source}.csv"
    static_csv = (
        staging / f"{cfg.tables.static.source}.csv" if cfg.tables.static else None
    )

    if not entity_csv.exists() or not monthly_csv.exists():
        raise FileNotFoundError(
            f"Staging CSVs missing for {cfg.name}. Expected {entity_csv} and {monthly_csv}."
        )

    con = duckdb.connect(str(wh))

    # Raw tables
    con.execute(
        f"CREATE TABLE raw_entity AS SELECT * FROM read_csv_auto('{entity_csv.as_posix()}', HEADER=TRUE)"
    )
    con.execute(
        f"CREATE TABLE raw_monthly AS SELECT * FROM read_csv_auto('{monthly_csv.as_posix()}', HEADER=TRUE)"
    )
    if static_csv and static_csv.exists():
        con.execute(
            f"CREATE TABLE raw_static AS SELECT * FROM read_csv_auto('{static_csv.as_posix()}', HEADER=TRUE)"
        )

    # Canonical views
    ent_cols = _build_col_exprs(_select_mapping(cfg.tables.entity.columns))
    con.execute(f"CREATE VIEW v_entity AS SELECT {', '.join(ent_cols)} FROM raw_entity")

    mon = cfg.tables.monthly
    date_expr = f'CAST("{mon.date_col}" AS TIMESTAMP) AS {S.DATE}'
    entity_expr = f'"{mon.entity_col}" AS {S.ENTITY_ID}'
    mon_cols = _build_col_exprs(_select_mapping(mon.columns))
    con.execute(
        f"CREATE VIEW v_monthly AS SELECT {date_expr}, {entity_expr}, "
        f"{', '.join(mon_cols)} FROM raw_monthly"
    )

    if static_csv and static_csv.exists() and cfg.tables.static:
        st_cols = _build_col_exprs(_select_mapping(cfg.tables.static.columns))
        con.execute(
            f'CREATE VIEW v_static AS SELECT "{mon.entity_col}" AS {S.ENTITY_ID}, '
            f"{', '.join(st_cols)} FROM raw_static"
        )

    # Hierarchy helper: field/reservoir/well labels for each well entity
    con.execute(_hierarchy_sql(cfg))

    # Meta
    con.execute("CREATE TABLE _meta (meta JSON)")
    con.execute("INSERT INTO _meta VALUES (?)", [json.dumps(meta_key)])

    con.close()
    return wh


def _hierarchy_sql(cfg: DBConfig) -> str:
    """Walk parent_id chain to resolve field/reservoir/well names for every entity."""
    lv = cfg.level_values
    return f"""
    CREATE VIEW v_hierarchy AS
    WITH RECURSIVE walk AS (
        SELECT {S.ENTITY_ID} AS id, {S.ENTITY_ID} AS start, {S.ENTITY_NAME} AS name,
               UPPER({S.ENTITY_LEVEL}) AS level, {S.ENTITY_PARENT} AS parent
        FROM v_entity
        UNION ALL
        SELECT e.{S.ENTITY_ID}, w.start, e.{S.ENTITY_NAME},
               UPPER(e.{S.ENTITY_LEVEL}), e.{S.ENTITY_PARENT}
        FROM v_entity e JOIN walk w ON e.{S.ENTITY_ID} = w.parent
    )
    SELECT start AS {S.ENTITY_ID},
           MAX(CASE WHEN level = '{lv["field"].upper()}' THEN name END)     AS field,
           MAX(CASE WHEN level = '{lv["reservoir"].upper()}' THEN name END) AS reservoir,
           MAX(CASE WHEN level = '{lv["well"].upper()}' THEN name END)      AS well,
           MAX(CASE WHEN id = start THEN level END)                         AS start_level
    FROM walk
    GROUP BY start
    """


def get_conn(cfg: DBConfig) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(cfg.warehouse_path), read_only=True)
