"""Plotly chart builders driven by (DataFrame, Chart spec)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from monitoring.charts.registry import REGISTRY, Chart


def _prepare(df: pd.DataFrame, metric_id: str) -> pd.DataFrame:
    """Return a tidy (date, entity, value) frame for a single metric."""
    metric = REGISTRY.metrics[metric_id]
    out = df[["date", "entity"]].copy()
    out["value"] = metric.derive(df)
    out["metric"] = metric.label
    return out.dropna(subset=["value"])


def build(chart: Chart, df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_fig(chart.title)

    if chart.kind == "line":
        frames = [_prepare(df, m) for m in chart.metrics]
        long = pd.concat(frames, ignore_index=True)
        color = "entity" if chart.per_entity else "metric"
        fig = px.line(
            long, x="date", y="value", color=color,
            line_group="metric" if chart.per_entity and len(chart.metrics) > 1 else None,
            labels={"value": chart.y_title or REGISTRY.metrics[chart.metrics[0]].unit,
                    "date": "Date"},
        )
    elif chart.kind == "stacked":
        frames = [_prepare(df, m) for m in chart.metrics]
        long = pd.concat(frames, ignore_index=True)
        totals = long.groupby(["date", "metric"], as_index=False)["value"].sum()
        fig = px.area(totals, x="date", y="value", color="metric",
                      labels={"value": chart.y_title or "", "date": "Date"})
    elif chart.kind == "bar":
        frames = [_prepare(df, m) for m in chart.metrics]
        long = pd.concat(frames, ignore_index=True)
        totals = long.groupby(["date", "metric"], as_index=False)["value"].sum()
        fig = px.bar(totals, x="date", y="value", color="metric", barmode="group",
                     labels={"value": chart.y_title or "", "date": "Date"})
    else:
        raise ValueError(f"Unknown chart kind: {chart.kind}")

    fig.update_layout(
        title=chart.title,
        legend_title_text="",
        margin=dict(l=40, r=20, t=50, b=40),
        hovermode="x unified",
    )
    return fig


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        annotations=[dict(
            text="No data in current selection", x=0.5, y=0.5,
            xref="paper", yref="paper", showarrow=False, font=dict(size=14, color="#888"),
        )],
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig
