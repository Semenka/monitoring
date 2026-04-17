"""Per-database configuration loader.

A YAML config maps the real OFM table/column names to a canonical schema so the
rest of the codebase never sees vendor-specific names. Dropping in a new OFM
database is a matter of writing a new YAML file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class TableColumns(BaseModel):
    model_config = {"extra": "allow"}


class EntityTable(BaseModel):
    source: str
    columns: dict[str, str | None]


class MonthlyTable(BaseModel):
    source: str
    date_col: str
    entity_col: str
    columns: dict[str, str | None]


class StaticTable(BaseModel):
    source: str
    columns: dict[str, str | None] = Field(default_factory=dict)


class DBTables(BaseModel):
    entity: EntityTable
    monthly: MonthlyTable
    static: StaticTable | None = None


class DBConfig(BaseModel):
    name: str
    mdb_file: str
    tables: DBTables
    units: dict[str, str] = Field(default_factory=dict)
    level_values: dict[str, str] = Field(
        default_factory=lambda: {"field": "FIELD", "reservoir": "RESERVOIR", "well": "WELL"}
    )
    synthetic: bool = False

    @property
    def mdb_path(self) -> Path:
        return Path(self.mdb_file)

    @property
    def warehouse_path(self) -> Path:
        return Path("data/warehouse") / f"{self.name.lower()}.duckdb"

    @property
    def staging_dir(self) -> Path:
        return Path("data/staging") / self.name.lower()


def load_db_config(path: str | Path) -> DBConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    return DBConfig.model_validate(data)


def list_configs(configs_dir: str | Path = "configs") -> list[Path]:
    return sorted(p for p in Path(configs_dir).glob("*.yaml") if not p.name.startswith("_"))
