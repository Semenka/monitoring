"""Visual theme: a clean, minimal Plotly template plus a restrained palette.

Inspired by minimal academic / portfolio sites — generous whitespace, light
gridlines, small serif/grotesk font, restrained color usage. Each fluid phase
gets a fixed canonical color used everywhere it appears.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio


# Canonical fluid colors (used consistently across all charts).
PHASE_COLORS = {
    "oil":      "#1F1A17",   # near-black
    "water":    "#2E7CB8",   # muted blue
    "gas":      "#D08C2A",   # ochre
    "wtr_inj":  "#5BA3D0",   # lighter blue
    "gas_inj":  "#E0B074",   # lighter ochre
    "gor":      "#7A4E2E",   # warm brown
    "wct":      "#3F6E8E",   # steel blue
    "bhp":      "#5C5C5C",   # graphite
    "thp":      "#9C9C9C",   # silver
    "vrr":      "#7A8A6E",   # sage
    "wor":      "#A14F4F",   # muted rust
}

# Default categorical sequence when colour-by-entity (e.g. wells).
ENTITY_PALETTE = [
    "#1F1A17", "#2E7CB8", "#D08C2A", "#7A8A6E", "#A14F4F",
    "#5C5C5C", "#7A4E2E", "#3F6E8E", "#9C9C9C", "#B58A4A",
]


def _build_template() -> go.layout.Template:
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family="Inter, -apple-system, Helvetica, Arial, sans-serif",
                      size=12, color="#2A2A2A"),
            title=dict(font=dict(family="Charter, Georgia, serif", size=15, color="#1A1A1A"),
                       x=0.0, xanchor="left", pad=dict(l=8, t=2, b=8)),
            colorway=ENTITY_PALETTE,
            plot_bgcolor="#FCFAF6",
            paper_bgcolor="#FCFAF6",
            xaxis=dict(
                showgrid=True, gridcolor="#EAE6DE", gridwidth=1,
                zeroline=False, showline=True, linecolor="#C8C2B6",
                ticks="outside", tickcolor="#C8C2B6", tickfont=dict(size=11),
            ),
            yaxis=dict(
                showgrid=True, gridcolor="#EAE6DE", gridwidth=1,
                zeroline=False, showline=True, linecolor="#C8C2B6",
                ticks="outside", tickcolor="#C8C2B6", tickfont=dict(size=11),
            ),
            legend=dict(
                bgcolor="rgba(252,250,246,0)",
                bordercolor="#EAE6DE", borderwidth=0,
                font=dict(size=11), orientation="h",
                yanchor="bottom", y=-0.25, xanchor="left", x=0,
            ),
            margin=dict(l=44, r=20, t=46, b=70),
            hoverlabel=dict(bgcolor="white", bordercolor="#C8C2B6",
                            font=dict(family="Inter, sans-serif", size=11)),
        )
    )


def install_template(name: str = "monitoring") -> str:
    pio.templates[name] = _build_template()
    pio.templates.default = name
    return name
