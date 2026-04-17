"""Entrypoint for Streamlit Community Cloud (which looks for `streamlit_app.py`).

Delegates to the main `app.py`. On first launch we build the sample DuckDB
warehouses so the deployed dashboard is immediately explorable without having
to upload the real OFM databases.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from monitoring.config import load_db_config


def _ensure_sample_warehouse() -> None:
    """Build every sample warehouse on first launch (cheap, ~5 s)."""
    for yaml_path in sorted((ROOT / "configs").glob("sample*.yaml")):
        cfg = load_db_config(yaml_path)
        if cfg.warehouse_path.exists():
            continue
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate_sample.py"),
             cfg.name.lower().replace("sample_", "") or "qw_mn"],
            check=False,
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "convert_mdb.py"),
             "--config", str(yaml_path), "--force"],
            check=False,
        )


_ensure_sample_warehouse()

# Load and execute the main app script
exec(compile((ROOT / "app.py").read_text(), "app.py", "exec"))
