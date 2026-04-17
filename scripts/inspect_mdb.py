"""Dump OFM table list, schemas, row counts, and column samples to a Markdown
report. Run this against any real .mdb in `data/raw/` to discover the actual
table/column names, then update the matching `configs/<db>.yaml`.

Usage:
    python scripts/inspect_mdb.py --config configs/qw_mn.yaml \
        --out docs/db_inspection_qw_mn.md
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from monitoring.config import load_db_config
from monitoring.io import mdb_extract


def _schema_for(mdb: Path, table: str) -> str:
    try:
        return subprocess.check_output(
            ["mdb-schema", "-T", table, str(mdb)], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return ""


def _row_count(mdb: Path, table: str) -> int:
    try:
        out = subprocess.check_output(
            ["mdb-export", "-q", "'", str(mdb), table], text=True, stderr=subprocess.DEVNULL
        )
        return max(0, out.count("\n") - 1)  # minus header
    except subprocess.CalledProcessError:
        return -1


def _sample_rows(mdb: Path, table: str, n: int = 3) -> str:
    try:
        out = subprocess.check_output(
            ["mdb-export", str(mdb), table], text=True, stderr=subprocess.DEVNULL
        )
        lines = out.splitlines()
        return "\n".join(lines[: n + 1])
    except subprocess.CalledProcessError:
        return ""


def inspect(cfg_path: str, out_path: str) -> int:
    cfg = load_db_config(cfg_path)
    if not cfg.mdb_paths or any(not p.exists() for p in cfg.mdb_paths):
        print(f"ERROR: one or more .mdb files in {cfg_path} are missing locally:",
              file=sys.stderr)
        for p in cfg.mdb_paths:
            print(f"  {'OK ' if p.exists() else 'MISSING'}: {p}", file=sys.stderr)
        print("\nDownload the missing files into data/raw/ first.", file=sys.stderr)
        return 2

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# {cfg.name} database inspection\n")
    for p in cfg.mdb_paths:
        size_mb = p.stat().st_size / 1e6
        lines.append(f"- **{p.name}** ({size_mb:,.1f} MB)")
    lines.append("")

    seen_tables: dict[str, list[Path]] = {}
    for p in cfg.mdb_paths:
        for t in mdb_extract.list_tables(p):
            seen_tables.setdefault(t, []).append(p)

    lines.append(f"## Tables (n={len(seen_tables)})\n")
    lines.append("| Table | In files | Approx rows |")
    lines.append("|-------|----------|-------------|")
    for t in sorted(seen_tables):
        files = ", ".join(p.name for p in seen_tables[t])
        # Row count from the first file that has the table
        n = _row_count(seen_tables[t][0], t)
        lines.append(f"| `{t}` | {files} | {n if n >= 0 else 'n/a'} |")
    lines.append("")

    lines.append("## Schemas and samples\n")
    for t in sorted(seen_tables):
        first = seen_tables[t][0]
        schema = _schema_for(first, t).strip()
        sample = _sample_rows(first, t, n=3).strip()
        lines.append(f"### `{t}` (from {first.name})\n")
        if schema:
            lines.append("```sql")
            lines.append(schema)
            lines.append("```")
        if sample:
            lines.append("\nFirst rows:\n")
            lines.append("```csv")
            lines.append(sample)
            lines.append("```")
        lines.append("")

    out.write_text("\n".join(lines))
    print(f"Wrote {out} ({sum(1 for _ in lines)} lines).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    return inspect(args.config, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
