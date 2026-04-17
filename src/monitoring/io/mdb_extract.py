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


def multi_extract(
    mdb_files: list[str | Path], tables: list[str], staging_dir: str | Path
) -> dict[str, Path]:
    """Extract the same set of tables from multiple .mdb files and concatenate.

    Used for multi-part OFM exports (ASAB is split across _1_1/_2_1/_3_1 files).
    Only files that actually contain the requested table contribute rows.
    """
    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    for t in tables:
        combined = staging / f"{t}.csv"
        wrote_header = False
        with combined.open("w") as dest:
            for mdb in mdb_files:
                try:
                    tables_in_file = set(list_tables(mdb))
                except subprocess.CalledProcessError:
                    continue
                if t not in tables_in_file:
                    continue
                tmp = staging / f"_{t}.part.csv"
                dump_table(mdb, t, tmp)
                with tmp.open("r") as src:
                    header = src.readline()
                    if not wrote_header:
                        dest.write(header)
                        wrote_header = True
                    dest.writelines(src)
                tmp.unlink(missing_ok=True)
        if not wrote_header:
            raise RuntimeError(f"Table {t!r} not found in any of: {[str(p) for p in mdb_files]}")
        out[t] = combined
    return out
