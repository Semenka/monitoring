"""Extract tables from an OFM .mdb file using the `mdbtools` CLI.

Falls back to a no-op if mdbtools is unavailable — in that case, the caller is
expected to generate a synthetic CSV set instead (see scripts/generate_sample.py).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class MdbToolsNotFound(RuntimeError):
    pass


def have_mdbtools() -> bool:
    return shutil.which("mdb-tables") is not None and shutil.which("mdb-export") is not None


def list_tables(mdb_file: str | Path) -> list[str]:
    if not have_mdbtools():
        raise MdbToolsNotFound("mdbtools not installed; `sudo apt-get install mdbtools`.")
    out = subprocess.check_output(["mdb-tables", "-1", str(mdb_file)], text=True)
    return [t.strip() for t in out.splitlines() if t.strip()]


def dump_table(mdb_file: str | Path, table: str, dest_csv: str | Path) -> Path:
    if not have_mdbtools():
        raise MdbToolsNotFound("mdbtools not installed; `sudo apt-get install mdbtools`.")
    dest = Path(dest_csv)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w") as f:
        subprocess.check_call(
            ["mdb-export", "-b", "strip", "-D", "%Y-%m-%d %H:%M:%S", str(mdb_file), table],
            stdout=f,
        )
    return dest


def bulk_extract(mdb_file: str | Path, tables: list[str], staging_dir: str | Path) -> dict[str, Path]:
    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for t in tables:
        out[t] = dump_table(mdb_file, t, staging / f"{t}.csv")
    return out
