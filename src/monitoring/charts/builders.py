"""Plotly chart builders driven by (DataFrame, Chart spec).

Supported chart kinds:
  line       — one trace per (entity, metric)
  line_log   — same but log y-axis
  line_logy  — alias of line_log
  stacked    — stacked area, one trace per metric, summed across entities
  bar        — grouped bars, one per metric
  xy         — cross-plot of two metrics (e.g. WCT vs Np)
  lines_dual — overview chart with one trace per metric (oil/water/gas) on
               twin y-axes (gas on the right)
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from monitoring.charts.registry import REGISTRY, Chart
from monitoring.charts.theme import PHASE_COLORS


def _values_for(df: pd.DataFrame, metric_id: str) -> pd.Series:
    """Compute one metric's values, applying cumulative sum per entity if asked."""
    metric = REGISTRY.metrics[metric_id]
    raw = metric.derive(df)
    if not metric.cumulative:
        return raw
    # Cumulative sum per entity, in date order; restore original row order.
    tmp = pd.DataFrame(
        {"date": df["date"].values, "entity": df["entity"].values, "v": raw.values},
        index=df.index,
    )
    tmp = tmp.sort_values(["entity", "date"])
    tmp["v"] = tmp.groupby("entity")["v"].cumsum()
    return tmp.sort_index()["v"]


def _tidy(df: pd.DataFrame, metric_id: str) -> pd.DataFrame:
    """Return tidy (date, entity, value, metric) frame for a single metric."""
    metric = REGISTRY.metrics[metric_id]
    out = df[["date", "entity"]].copy()
    out["value"] = _values_for(df, metric_id)
    out["metric"] = metric.label
    return out.dropna(subset=["value"])


def _phase_color_for(metric_id: str) -> str | None:
    # Map "oil_rate" / "cum_oil" / "rate_oil" → "oil" colour, etc.
    for phase in PHASE_COLORS:
        if phase in metric_id:
            return PHASE_COLORS[phase]
    return None


def build(chart: Chart, df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_fig(chart.title)

    if chart.kind in ("line", "line_log", "line_logy"):
        return _build_line(chart, df, log_y=(chart.kind != "line"))
    if chart.kind == "stacked":
        return _build_stacked(chart, df)
    if chart.kind == "bar":
        return _build_bar(chart, df)
    if chart.kind == "xy":
        return _build_xy(chart, df)
    if chart.kind == "lines_dual":
        return _build_lines_dual(chart, df)
    raise ValueError(f"Unknown chart kind: {chart.kind}")


def _build_line(chart: Chart, df: pd.DataFrame, *, log_y: bool) -> go.Figure:
    frames = [_tidy(df, m) for m in chart.metrics]
    long = pd.concat(frames, ignore_index=True)
    if long.empty:
        return _empty_fig(chart.title)

    color = "entity" if chart.per_entity else "metric"
    fig = px.line(
        long, x="date", y="value", color=color,
        line_group="metric" if chart.per_entity and len(chart.metrics) > 1 else None,
    )
    if not chart.per_entity:
        # Single metric / total: paint with phase colour if we can find one.
        c = _phase_color_for(chart.metrics[0])
        if c:
            for tr in fig.data:
                tr.line.color = c

    # Smooth the line a bit
    for tr in fig.data:
        tr.line.width = 1.6
        tr.mode = "lines"

    fig.update_layout(
        title=chart.title,
        yaxis=dict(title=chart.y_title or REGISTRY.metrics[chart.metrics[0]].unit,
                   type="log" if log_y else "linear"),
        xaxis=dict(title=""),
        hovermode="x unified",
    )
    return fig


def _build_stacked(chart: Chart, df: pd.DataFrame) -> go.Figure:
    frames = [_tidy(df, m) for m in chart.metrics]
    long = pd.concat(frames, ignore_index=True)
    totals = long.groupby(["date", "metric"], as_index=False)["value"].sum()
    color_map = {REGISTRY.metrics[m].label: _phase_color_for(m) for m in chart.metrics}
    fig = px.area(totals, x="date", y="value", color="metric",
                  color_discrete_map={k: v for k, v in color_map.items() if v})
    fig.update_layout(
        title=chart.title,
        yaxis=dict(title=chart.y_title or ""),
        xaxis=dict(title=""),
    )
    return fig


def _build_bar(chart: Chart, df: pd.DataFrame) -> go.Figure:
    frames = [_tidy(df, m) for m in chart.metrics]
    long = pd.concat(frames, ignore_index=True)
    totals = long.groupby(["date", "metric"], as_index=False)["value"].sum()
    fig = px.bar(totals, x="date", y="value", color="metric", barmode="group")
    fig.update_layout(title=chart.title, yaxis=dict(title=chart.y_title or ""),
                      xaxis=dict(title=""))
    return fig


def _build_xy(chart: Chart, df: pd.DataFrame) -> go.Figure:
    """Cross-plot of two metrics (e.g. WCT vs Np). Per-entity scatter+line."""
    if not chart.x_metric:
        raise ValueError(f"chart {chart.id} kind=xy requires x_metric")
    y_metric = chart.metrics[0]
    x = _values_for(df, chart.x_metric)
    y = _values_for(df, y_metric)
    plotted = pd.DataFrame({
        "date": df["date"].values,
        "entity": df["entity"].values,
        "x": x.values, "y": y.values,
    }).dropna()
    if plotted.empty:
        return _empty_fig(chart.title)
    plotted = plotted.sort_values(["entity", "date"])
    fig = px.line(plotted, x="x", y="y", color="entity", markers=True,
                  hover_data={"date": True})
    for tr in fig.data:
        tr.line.width = 1.4
        if hasattr(tr, "marker"):
            tr.marker.size = 4
    fig.update_layout(
        title=chart.title,
        xaxis=dict(title=chart.x_title or chart.x_metric),
        yaxis=dict(title=chart.y_title or REGISTRY.metrics[y_metric].unit),
        hovermode="closest",
    )
    return fig


def _build_lines_dual(chart: Chart, df: pd.DataFrame) -> go.Figure:
    """Overview chart: oil/water on left axis, gas on right axis."""
    fig = go.Figure()
    for m_id in chart.metrics:
        tidy = _tidy(df, m_id).groupby("date", as_index=False)["value"].sum()
        c = _phase_color_for(m_id) or "#888"
        on_right = "gas" in m_id
        fig.add_trace(go.Scatter(
            x=tidy["date"], y=tidy["value"], name=REGISTRY.metrics[m_id].label,
            line=dict(color=c, width=1.8), mode="lines",
            yaxis="y2" if on_right else "y",
        ))
    fig.update_layout(
        title=chart.title,
        yaxis=dict(title="Liquid (BPD)", side="left"),
        yaxis2=dict(title="Gas (MMscf/d)", overlaying="y", side="right",
                    showgrid=False),
        xaxis=dict(title=""),
        hovermode="x unified",
    )
    return fig


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        annotations=[dict(
            text="No data in current selection", x=0.5, y=0.5,
            xref="paper", yref="paper", showarrow=False,
            font=dict(size=13, color="#888"),
        )],
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig
