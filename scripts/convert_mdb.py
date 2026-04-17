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
    for p in cfg.mdb_paths:
        tables = mdb_extract.list_tables(p)
        print(f"Tables in {p.name}:")
        for t in tables:
            print(f"  - {t}")


def _extract(cfg) -> None:
    needed = [
        cfg.tables.entity.source,
        cfg.tables.monthly.source,
    ]
    if cfg.tables.static:
        needed.append(cfg.tables.static.source)
    print(f"Extracting {len(needed)} tables from {len(cfg.mdb_paths)} .mdb file(s) "
          f"to {cfg.staging_dir} …")
    if len(cfg.mdb_paths) == 1:
        mdb_extract.bulk_extract(cfg.mdb_paths[0], needed, cfg.staging_dir)
    else:
        mdb_extract.multi_extract(cfg.mdb_paths, needed, cfg.staging_dir)
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
        # Prefer explicit per-file IDs in config; fall back to env var with DB name.
        file_ids = list(cfg.gdrive_file_ids)
        if not file_ids:
            env_var = f"GDRIVE_FILE_ID_{cfg.name.upper()}"
            file_id = os.environ.get(env_var)
            if file_id:
                file_ids = [file_id]
        if not file_ids:
            print(f"Warning: no Drive file IDs configured for {cfg.name}; skipping download.",
                  file=sys.stderr)
        else:
            import gdown
            for fid, dest in zip(file_ids, cfg.mdb_paths):
                dest.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://drive.google.com/uc?id={fid}"
                print(f"Downloading {fid} -> {dest}")
                gdown.download(url, str(dest), quiet=False)

    if args.fetch_only:
        return 0

    missing = [p for p in cfg.mdb_paths if not p.exists()]
    if missing and not cfg.synthetic:
        print(
            f"ERROR: {len(missing)} .mdb file(s) not found: "
            f"{[str(p) for p in missing]}. Download them manually from Google Drive "
            f"and place them at those paths, then re-run.",
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
