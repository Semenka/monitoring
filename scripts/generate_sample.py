"""Generate synthetic OFM-shaped sample databases for dev / demo.

Each sample DB follows the canonical schema from `configs/sample*.yaml`.
Running `convert_mdb --config configs/sample.yaml` (or sample_asab / sample_sahil
/ sample_shah) then builds a DuckDB warehouse from them.

These samples let reviewers experience the dashboard end-to-end without
downloading the real 220 MB – 3 GB OFM exports.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from monitoring.config import load_db_config


@dataclass
class SampleSpec:
    config: str                            # e.g. "configs/sample.yaml"
    fields: list[tuple[str, str]]          # [(field_id, field_name), ...]
    reservoirs: dict[str, list[str]]       # field_id -> reservoir names
    wells_per_res: int = 4
    start: str = "2016-01-01"
    end: str = "2026-03-01"
    seed: int = 42


SPECS: dict[str, SampleSpec] = {
    "qw_mn": SampleSpec(
        config="configs/sample.yaml",
        fields=[("QSWR", "Qusahwira"), ("MNDR", "Mender"), ("BIDA", "Bida Al Qemzan")],
        reservoirs={
            "QSWR": ["Kharaib", "Shuaiba"],
            "MNDR": ["Thamama-F", "Thamama-G"],
            "BIDA": ["Kharaib", "Arab-D"],
        },
        seed=42,
    ),
    "asab": SampleSpec(
        config="configs/sample_asab.yaml",
        fields=[("ASAB", "Asab")],
        reservoirs={"ASAB": ["Thamama-A", "Thamama-B", "Thamama-C", "Habshan"]},
        wells_per_res=6,
        seed=7,
    ),
    "sahil": SampleSpec(
        config="configs/sample_sahil.yaml",
        fields=[("SAHL", "Sahil")],
        reservoirs={"SAHL": ["Thamama-G", "Thamama-H", "Arab-D"]},
        wells_per_res=5,
        seed=13,
    ),
    "shah": SampleSpec(
        config="configs/sample_shah.yaml",
        fields=[("SHAH", "Shah")],
        reservoirs={"SHAH": ["Arab-D", "Arab-C", "Habshan"]},
        wells_per_res=5,
        seed=21,
    ),
}


def _build_hierarchy(spec: SampleSpec) -> pd.DataFrame:
    rows: list[dict] = []
    asset_name = Path(spec.config).stem.replace("sample_", "").upper() or "ASSET"
    rows.append({"entity_id": "ASSET", "name": asset_name, "level": "ASSET", "parent_id": None})

    for f_id, f_name in spec.fields:
        rows.append({"entity_id": f_id, "name": f_name, "level": "FIELD", "parent_id": "ASSET"})
        for r_name in spec.reservoirs[f_id]:
            r_id = f"{f_id}-{r_name.upper().replace('-', '')}"
            rows.append({"entity_id": r_id, "name": r_name, "level": "RESERVOIR", "parent_id": f_id})
            for w in range(1, spec.wells_per_res + 1):
                w_id = f"{r_id}-W{w:02d}"
                w_name = f"{f_name[:3].upper()}-{r_name[0]}{w:02d}"
                rows.append({"entity_id": w_id, "name": w_name, "level": "WELL", "parent_id": r_id})
    return pd.DataFrame(rows)


def _well_profile(rng: np.random.Generator, i: int, months: pd.DatetimeIndex) -> pd.DataFrame:
    t = np.arange(len(months))
    peak = 800 + rng.integers(200, 2500)
    decline = 0.002 + 0.003 * rng.random()
    oil_rate = np.maximum(peak * np.exp(-decline * t) * rng.normal(1.0, 0.06, size=len(t)), 0)

    wct_curve = 0.05 + 0.80 / (1 + np.exp(-(t - len(t) * 0.5) / (len(t) * 0.08)))
    water_rate = oil_rate * wct_curve / (1 - wct_curve + 1e-6)
    gor = 500 + 10 * t + rng.normal(0, 50, size=len(t))
    gas_rate = (oil_rate * gor) / 1000

    is_injector = (i % 4 == 3)
    if is_injector:
        oil_rate[:] = water_rate[:] = gas_rate[:] = 0
        wtr_inj = np.maximum(2000 + 800 * np.sin(t / 6) + rng.normal(0, 100, size=len(t)), 0)
        gas_inj = np.zeros_like(t, dtype=float)
    else:
        wtr_inj = np.zeros_like(t, dtype=float)
        gas_inj = np.zeros_like(t, dtype=float)

    days_on = np.clip(30 - rng.integers(0, 4, size=len(t)), 0, 31)
    bhp = 3200 - 3 * t + rng.normal(0, 25, size=len(t))
    thp = 900 - 1.2 * t + rng.normal(0, 20, size=len(t))

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


def generate(spec: SampleSpec) -> None:
    rng = np.random.default_rng(spec.seed)
    cfg = load_db_config(spec.config)
    out_dir = cfg.staging_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    entities = _build_hierarchy(spec)
    months = pd.date_range(spec.start, spec.end, freq="MS")

    well_ids = entities.loc[entities["level"] == "WELL", "entity_id"].tolist()
    frames = []
    for i, wid in enumerate(well_ids):
        p = _well_profile(rng, i, months)
        p.insert(1, "entity_id", wid)
        frames.append(p)
    monthly = pd.concat(frames, ignore_index=True)

    static = pd.DataFrame([
        {
            "entity_id": wid,
            "well_type": "INJECTOR" if i % 4 == 3 else "PRODUCER",
            "status": "ACTIVE",
            "completion_date": date(2015, 1, 1).isoformat(),
        }
        for i, wid in enumerate(well_ids)
    ])

    entities.to_csv(out_dir / f"{cfg.tables.entity.source}.csv", index=False)
    monthly.to_csv(out_dir / f"{cfg.tables.monthly.source}.csv", index=False)
    static.to_csv(out_dir / f"{cfg.tables.static.source}.csv", index=False)

    placeholder = cfg.mdb_path
    placeholder.parent.mkdir(parents=True, exist_ok=True)
    placeholder.touch(exist_ok=True)

    print(f"[{cfg.name}] {len(entities)} entities, {len(monthly)} monthly rows, "
          f"{len(static)} static rows → {out_dir}")


def main() -> int:
    names = sys.argv[1:] or list(SPECS.keys())
    for n in names:
        if n not in SPECS:
            raise SystemExit(f"Unknown sample {n!r}. Available: {list(SPECS)}")
        generate(SPECS[n])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
