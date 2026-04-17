"""Canonical column names used throughout the dashboard.

The YAML config translates vendor-specific OFM columns to these names; the rest
of the codebase never references real OFM names.
"""
from __future__ import annotations

# Entity table
ENTITY_ID = "entity_id"
ENTITY_NAME = "name"
ENTITY_LEVEL = "level"
ENTITY_PARENT = "parent_id"

# Monthly production table
DATE = "date"
OIL_VOL = "oil_vol"
WATER_VOL = "water_vol"
GAS_VOL = "gas_vol"
WTR_INJ = "wtr_inj"
GAS_INJ = "gas_inj"
DAYS_ON = "days_on"
BHP = "bhp"
THP = "thp"

VOLUME_COLS = [OIL_VOL, WATER_VOL, GAS_VOL, WTR_INJ, GAS_INJ]
OPTIONAL_COLS = [BHP, THP]

LEVELS = ("field", "reservoir", "well")
