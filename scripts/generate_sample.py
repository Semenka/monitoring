"""Generate a synthetic OFM-shaped sample database for dev / demo.

Creates CSV files in `data/staging/sample/` that follow the canonical schema
defined in `configs/sample.yaml`. Running `convert_mdb --config configs/sample.yaml`
then builds a DuckDB warehouse from them, so the dashboard is immediately usable
without real OFM data.
"""
from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from monitoring.config import load_db_config

RNG = np.random.default_rng(42)


def _build_hierarchy() -> pd.DataFrame:
    """Field → Reservoir → Well tree matching ADNOC Onshore SE naming."""
    rows: list[dict] = []
    rows.append({"entity_id": "ASSET", "name": "QW_MN", "level": "ASSET", "parent_id": None})

    fields = [("QSWR", "Qusahwira"), ("MNDR", "Mender"), ("BIDA", "Bida Al Qemzan")]
    reservoirs = {
        "QSWR": ["Kharaib", "Shuaiba"],
        "MNDR": ["Thamama-F", "Thamama-G"],
        "BIDA": ["Kharaib", "Arab-D"],
    }
    wells_per_res = 4

    for f_id, f_name in fields:
        rows.append({"entity_id": f_id, "name": f_name, "level": "FIELD", "parent_id": "ASSET"})
        for r_name in reservoirs[f_id]:
            r_id = f"{f_id}-{r_name.upper().replace('-', '')}"
            rows.append({"entity_id": r_id, "name": r_name, "level": "RESERVOIR", "parent_id": f_id})
            for w in range(1, wells_per_res + 1):
                w_id = f"{r_id}-W{w:02d}"
                w_name = f"{f_name[:3].upper()}-{r_name[0]}{w:02d}"
                rows.append({"entity_id": w_id, "name": w_name, "level": "WELL", "parent_id": r_id})
    return pd.DataFrame(rows)


def _well_profile(i: int, months: pd.DatetimeIndex) -> pd.DataFrame:
    """Synthesize a plausible declining oil profile with water breakthrough and GOR rise."""
    t = np.arange(len(months))
    peak = 800 + RNG.integers(200, 2500)                     # bbl/d
    decline = 0.002 + 0.003 * RNG.random()                   # per month
    oil_rate = peak * np.exp(-decline * t)                   # bbl/d
    noise = RNG.normal(1.0, 0.06, size=len(t))
    oil_rate = np.maximum(oil_rate * noise, 0)

    # Water cut grows sigmoidally from ~5% to ~85%
    wct_curve = 0.05 + 0.80 / (1 + np.exp(-(t - len(t) * 0.5) / (len(t) * 0.08)))
    water_rate = oil_rate * wct_curve / (1 - wct_curve + 1e-6)

    # GOR starts at 500 scf/bbl, drifts up
    gor = 500 + 10 * t + RNG.normal(0, 50, size=len(t))
    gas_rate = (oil_rate * gor) / 1000                       # mscf/d

    # Injector wells (every 4th) produce nothing but inject water
    is_injector = (i % 4 == 3)
    if is_injector:
        oil_rate[:] = 0
        water_rate[:] = 0
        gas_rate[:] = 0
        wtr_inj = 2000 + 800 * np.sin(t / 6) + RNG.normal(0, 100, size=len(t))
        wtr_inj = np.maximum(wtr_inj, 0)
        gas_inj = np.zeros_like(t, dtype=float)
    else:
        wtr_inj = np.zeros_like(t, dtype=float)
        gas_inj = np.zeros_like(t, dtype=float)

    days_on = np.clip(30 - RNG.integers(0, 4, size=len(t)), 0, 31)

    bhp = 3200 - 3 * t + RNG.normal(0, 25, size=len(t))
    thp = 900 - 1.2 * t + RNG.normal(0, 20, size=len(t))

    return pd.DataFrame({
        "date": months,
        "oil_vol": oil_rate * days_on,
        "water_vol": water_rate * days_on,
        "gas_vol": gas_rate * days_on,
        "wtr_inj": wtr_inj * days_on,
        "gas_inj": gas_inj * days_on,
        "days_on": days_on,
        "bhp": bhp,
        "thp": thp,
    })


def main() -> int:
    cfg = load_db_config("configs/sample.yaml")
    out_dir = cfg.staging_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    entities = _build_hierarchy()
    months = pd.date_range("2016-01-01", "2026-03-01", freq="MS")

    well_ids = entities.loc[entities["level"] == "WELL", "entity_id"].tolist()
    frames = []
    for i, wid in enumerate(well_ids):
        p = _well_profile(i, months)
        p.insert(1, "entity_id", wid)
        frames.append(p)
    monthly = pd.concat(frames, ignore_index=True)

    static_rows = []
    for i, wid in enumerate(well_ids):
        static_rows.append({
            "entity_id": wid,
            "well_type": "INJECTOR" if i % 4 == 3 else "PRODUCER",
            "status": "ACTIVE",
            "completion_date": (date(2015, 1, 1)).isoformat(),
        })
    static = pd.DataFrame(static_rows)

    # Write with OFM-style filenames matching cfg.tables.*.source
    entities.to_csv(out_dir / f"{cfg.tables.entity.source}.csv", index=False)
    monthly.to_csv(out_dir / f"{cfg.tables.monthly.source}.csv", index=False)
    static.to_csv(out_dir / f"{cfg.tables.static.source}.csv", index=False)

    # Touch the .mdb placeholder so mtime metadata works for cache invalidation
    Path(cfg.mdb_file).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.mdb_file).touch(exist_ok=True)

    print(f"Sample data written to {out_dir}: "
          f"{len(entities)} entities, {len(monthly)} monthly rows, {len(static)} static rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
