"""End-to-end ETL: download (optional) → extract .mdb → build DuckDB warehouse.

Usage:
    python -m scripts.convert_mdb --config configs/qw_mn.yaml
    python -m scripts.convert_mdb --config configs/qw_mn.yaml --download
    python -m scripts.convert_mdb --config configs/qw_mn.yaml --tables-only
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running as a script: ensure repo/src is on sys.path.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

from monitoring.config import load_db_config
from monitoring.io import mdb_extract, warehouse
from monitoring.io.gdrive import fetch_from_env


def _list_tables(cfg) -> None:
    tables = mdb_extract.list_tables(cfg.mdb_path)
    print(f"Tables in {cfg.mdb_path.name}:")
    for t in tables:
        print(f"  - {t}")


def _extract(cfg) -> None:
    needed = [
        cfg.tables.entity.source,
        cfg.tables.monthly.source,
    ]
    if cfg.tables.static:
        needed.append(cfg.tables.static.source)
    print(f"Extracting {len(needed)} tables to {cfg.staging_dir} …")
    mdb_extract.bulk_extract(cfg.mdb_path, needed, cfg.staging_dir)
    print("Done.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to YAML DB config")
    ap.add_argument("--download", action="store_true",
                    help="Fetch .mdb from Google Drive using GDRIVE_FILE_ID_<NAME> env var")
    ap.add_argument("--fetch-only", action="store_true", help="Download and exit")
    ap.add_argument("--tables-only", action="store_true",
                    help="Just list tables in the .mdb and exit")
    ap.add_argument("--force", action="store_true", help="Rebuild warehouse even if cached")
    args = ap.parse_args()

    load_dotenv()
    cfg = load_db_config(args.config)

    if args.download:
        env_var = f"GDRIVE_FILE_ID_{cfg.name.upper()}"
        file_id = os.environ.get(env_var)
        if not file_id:
            print(f"Warning: {env_var} not set; skipping download.", file=sys.stderr)
        else:
            cfg.mdb_path.parent.mkdir(parents=True, exist_ok=True)
            fetch_from_env(env_var, cfg.mdb_path)

    if args.fetch_only:
        return 0

    if not cfg.mdb_path.exists() and not cfg.synthetic:
        print(
            f"ERROR: {cfg.mdb_path} not found. Download it manually from Google Drive "
            f"and place it at that path, then re-run.",
            file=sys.stderr,
        )
        return 2

    if args.tables_only:
        _list_tables(cfg)
        return 0

    if not cfg.synthetic:
        _extract(cfg)

    print(f"Building DuckDB warehouse at {cfg.warehouse_path} …")
    warehouse.build_duckdb(cfg, force=args.force)
    print(f"Warehouse ready: {cfg.warehouse_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
