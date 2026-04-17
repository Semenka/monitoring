"""Simple unit toggles between field and SI units."""
from __future__ import annotations

BBL_TO_M3 = 0.158987
MSCF_TO_KSM3 = 0.0283168  # thousand std m3 per mscf (close enough for UI)


def convert_volume(series, from_unit: str, to_unit: str):
    if from_unit == to_unit:
        return series
    key = (from_unit, to_unit)
    factor = {
        ("bbl", "m3"): BBL_TO_M3,
        ("m3", "bbl"): 1 / BBL_TO_M3,
        ("mscf", "ksm3"): MSCF_TO_KSM3,
        ("ksm3", "mscf"): 1 / MSCF_TO_KSM3,
    }.get(key)
    if factor is None:
        return series
    return series * factor
