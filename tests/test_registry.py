"""Registry contains expected metrics & charts at the right levels."""
from __future__ import annotations

import monitoring.charts.metrics  # noqa: F401  (registers on import)
from monitoring.charts.registry import REGISTRY


def test_core_metrics_registered():
    for m_id in (
        "oil_rate", "water_rate", "gas_rate",
        "wtr_inj_rate", "gas_inj_rate",
        "cum_oil", "cum_water", "cum_gas",
        "gor", "wct", "wor", "vrr",
    ):
        assert m_id in REGISTRY.metrics


def test_pressure_metrics_are_well_only():
    for m_id in ("bhp", "thp"):
        assert REGISTRY.metrics[m_id].levels == frozenset({"well"})


def test_gor_wct_not_at_well_level_by_default():
    for c_id in ("gor_trend", "wct_trend"):
        chart = REGISTRY.charts[c_id]
        assert "well" not in chart.applicable_levels


def test_every_chart_references_known_metrics():
    for chart in REGISTRY.charts.values():
        for m_id in chart.metrics:
            assert m_id in REGISTRY.metrics, f"{chart.id} references unknown metric {m_id}"


def test_every_chart_has_known_category():
    allowed = {"overview", "production", "injection", "ratio", "pressure", "diagnostic"}
    for chart in REGISTRY.charts.values():
        assert chart.category in allowed, f"{chart.id} has unknown category {chart.category!r}"


def test_no_chart_appears_in_multiple_tabs():
    """Each category maps 1:1 to a tab; chart ids must be unique so keys don't collide."""
    seen: dict[str, str] = {}
    for chart in REGISTRY.charts.values():
        assert chart.id not in seen, f"Duplicate chart id {chart.id}"
        seen[chart.id] = chart.category
