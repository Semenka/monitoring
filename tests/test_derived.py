import pandas as pd
import pytest

from monitoring.domain import schema as S
from monitoring.transforms import derived


def _df(oil, water, gas):
    return pd.DataFrame({S.OIL_VOL: oil, S.WATER_VOL: water, S.GAS_VOL: gas})


def test_gor_basic():
    df = _df([100, 200], [0, 0], [100, 50])  # gas in mscf
    # gor = gas*1000/oil => 1000 scf/bbl, 250 scf/bbl
    assert list(derived.gor(df)) == [1000.0, 250.0]


def test_wct_basic():
    df = pd.DataFrame({S.OIL_VOL: [80, 50], S.WATER_VOL: [20, 50]})
    assert list(derived.wct(df)) == [0.2, 0.5]


def test_gor_zero_oil_is_nan():
    df = _df([0, 100], [0, 0], [10, 10])
    result = list(derived.gor(df))
    assert pd.isna(result[0])
    assert result[1] == 100.0


def test_cumulative_metric_runs_per_entity():
    """Registry-level check: cum_oil runs a per-entity cumsum in date order."""
    import monitoring.charts.metrics  # noqa: F401 — registers metrics
    from monitoring.charts.builders import _values_for

    df = pd.DataFrame({
        "date":       pd.to_datetime(["2020-01-01", "2020-02-01", "2020-01-01", "2020-02-01"]),
        "entity":     ["A", "A", "B", "B"],
        S.OIL_VOL:    [10.0, 20.0, 5.0, 15.0],
        S.DAYS_ON:    [30, 30, 30, 30],
        S.WATER_VOL:  [0, 0, 0, 0],
        S.GAS_VOL:    [0, 0, 0, 0],
        S.WTR_INJ:    [0, 0, 0, 0],
        S.GAS_INJ:    [0, 0, 0, 0],
        S.BHP:        [0, 0, 0, 0],
        S.THP:        [0, 0, 0, 0],
    })
    out = _values_for(df, "cum_oil")
    # cum_oil divides by 1e6 → expected cumulative oil in MMbbl
    assert list(out) == pytest.approx([10 / 1e6, 30 / 1e6, 5 / 1e6, 20 / 1e6])
