import pandas as pd

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
