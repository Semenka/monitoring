"""Sanity checks on a built warehouse."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from monitoring.config import load_db_config
from monitoring.io import warehouse


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_db_config(args.config)
    con = warehouse.get_conn(cfg)

    n_rows = con.execute("SELECT COUNT(*) FROM v_monthly").fetchone()[0]
    n_ents = con.execute("SELECT COUNT(*) FROM v_entity").fetchone()[0]
    n_wells = con.execute(
        "SELECT COUNT(DISTINCT entity_id) FROM v_hierarchy WHERE well IS NOT NULL"
    ).fetchone()[0]

    neg = con.execute(
        """SELECT SUM((oil_vol<0)::INT) + SUM((water_vol<0)::INT) +
                  SUM((gas_vol<0)::INT) + SUM((wtr_inj<0)::INT) +
                  SUM((gas_inj<0)::INT)
           FROM v_monthly"""
    ).fetchone()[0] or 0

    print(f"Warehouse   : {cfg.warehouse_path}")
    print(f"Monthly rows: {n_rows:,}")
    print(f"Entities    : {n_ents:,}  (wells: {n_wells:,})")
    print(f"Negatives   : {neg}")

    con.close()
    return 1 if neg > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
