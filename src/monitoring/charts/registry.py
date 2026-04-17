"""Metric + chart registries.

Adding a new parameter (e.g. BHP) becomes ~10 lines:

    @register_metric("bhp", "Bottomhole Pressure", unit="psi",
                     needs=["bhp"], levels=("well",))
    def _bhp(df): return df["bhp"]

    @register_chart("bhp_trend", "BHP", ["bhp"], kind="line",
                    applicable_levels=("well",), category="pressure",
                    y_title="psi")

Charts registered here appear automatically on the matching tabs as long as
the underlying column is mapped in the YAML config.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    unit: str
    needs: tuple[str, ...]
    derive: Callable                         # (df) -> Series
    levels: frozenset[str]                   # {'field','reservoir','well'}
    kind: str = "volume"                     # 'volume'|'ratio'|'pressure'
    cumulative: bool = False                 # apply running sum per entity before plot


@dataclass(frozen=True)
class Chart:
    id: str
    title: str
    metrics: tuple[str, ...]
    kind: str                                # 'line'|'line_log'|'line_logy'|
                                              # 'stacked'|'bar'|'area'|'xy'|'lines_dual'
    applicable_levels: frozenset[str]
    category: str = "production"             # 'overview'|'production'|'injection'|'ratio'|'pressure'|'diagnostic'
    per_entity: bool = True                  # color by entity vs by metric
    y_title: str | None = None
    x_title: str | None = None
    x_metric: str | None = None              # for kind='xy' cross-plots


class _Registry:
    def __init__(self) -> None:
        self.metrics: dict[str, Metric] = {}
        self.charts: dict[str, Chart] = {}

    def register_metric(
        self,
        id: str,
        label: str,
        unit: str,
        needs: Iterable[str],
        levels: Iterable[str] = ("field", "reservoir", "well"),
        kind: str = "volume",
        cumulative: bool = False,
    ):
        def deco(fn: Callable):
            self.metrics[id] = Metric(
                id=id, label=label, unit=unit, needs=tuple(needs),
                derive=fn, levels=frozenset(levels), kind=kind,
                cumulative=cumulative,
            )
            return fn
        return deco

    def register_chart(
        self,
        id: str,
        title: str,
        metrics: Iterable[str],
        kind: str,
        applicable_levels: Iterable[str] = ("field", "reservoir", "well"),
        category: str = "production",
        per_entity: bool = True,
        y_title: str | None = None,
        x_title: str | None = None,
        x_metric: str | None = None,
    ):
        self.charts[id] = Chart(
            id=id, title=title, metrics=tuple(metrics), kind=kind,
            applicable_levels=frozenset(applicable_levels),
            category=category, per_entity=per_entity,
            y_title=y_title, x_title=x_title, x_metric=x_metric,
        )
        return self.charts[id]

    def charts_for_level(self, level: str) -> list[Chart]:
        return [c for c in self.charts.values() if level in c.applicable_levels]

    def charts_by_category(self, level: str, category: str) -> list[Chart]:
        return [c for c in self.charts.values()
                if level in c.applicable_levels and c.category == category]

    def available_metrics(self, level: str, mapped_cols: set[str]) -> list[Metric]:
        return [
            m for m in self.metrics.values()
            if level in m.levels and set(m.needs).issubset(mapped_cols)
        ]


REGISTRY = _Registry()
register_metric = REGISTRY.register_metric
register_chart = REGISTRY.register_chart
