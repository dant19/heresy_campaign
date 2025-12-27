import math
from dataclasses import dataclass
from typing import Tuple, List

import pandas as pd
import plotly.graph_objects as go

from heresy.rules import status_from_cp, side_from_cp


@dataclass
class HexGeom:
    size: float = 1.0
    pointy_top: bool = True


def hex_to_xy(q: int, r: int, geom: HexGeom) -> Tuple[float, float]:
    s = geom.size
    if geom.pointy_top:
        x = s * math.sqrt(3) * (q + r / 2)
        y = s * 1.5 * r
    else:
        x = s * 1.5 * q
        y = s * math.sqrt(3) * (r + q / 2)
    return x, y


def hex_corners(x: float, y: float, geom: HexGeom) -> List[Tuple[float, float]]:
    s = geom.size
    pts = []
    for i in range(6):
        angle_deg = 60 * i - (30 if geom.pointy_top else 0)
        a = math.radians(angle_deg)
        pts.append((x + s * math.cos(a), y + s * math.sin(a)))
    return pts


def cp_color(cp: int) -> str:
    if cp == 0:
        return "rgb(26,28,40)"
    a = max(0.18, abs(cp) / 6.0)
    if cp > 0:
        r = int(35 + 25 * a)
        g = int(120 + 95 * a)
        b = int(190 + 55 * a)
        return f"rgb({r},{g},{b})"
    r = int(170 + 75 * a)
    g = int(55 + 40 * a)
    b = int(45 + 25 * a)
    return f"rgb({r},{g},{b})"


def tile_glyph(is_planet: bool) -> str:
    return "⦿" if is_planet else "✦"


def make_map(df: pd.DataFrame, geom: HexGeom) -> go.Figure:
    fig = go.Figure()

    for _, row in df.iterrows():
        q, r = int(row["q"]), int(row["r"])
        name = str(row["name"])
        is_planet = bool(row["is_planet"])
        cp = int(row["cp"])

        status = status_from_cp(cp)
        side = side_from_cp(cp)

        x, y = hex_to_xy(q, r, geom)
        corners = hex_corners(x, y, geom)
        xs = [p[0] for p in corners] + [corners[0][0]]
        ys = [p[1] for p in corners] + [corners[0][1]]

        if status == "Secure":
            dash, width, outline = "solid", 3.2, "rgba(240,234,220,0.72)"
        elif status == "Held":
            dash, width, outline = "solid", 2.3, "rgba(209,184,122,0.58)"
        else:
            dash, width, outline = "dash", 1.35, "rgba(240,234,220,0.35)"

        hover = (
            f"<b>{name}</b><br>"
            f"{'Planet' if is_planet else 'Void'}<br>"
            f"CP: {cp} ({side})<br>"
            f"Status: {status}<br>"
            f"Coord: ({q},{r})"
        )

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                fill="toself",
                fillcolor=cp_color(cp),
                line=dict(width=width, dash=dash, color=outline),
                hoverinfo="text",
                text=hover,
                showlegend=False,
            )
        )

        if is_planet:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="markers+text",
                    marker=dict(size=26, color="rgba(12,12,18,0.25)", line=dict(width=2.6, color="rgba(209,184,122,0.95)")),
                    text=[tile_glyph(True)],
                    textfont=dict(size=22, color="rgba(240,234,220,0.98)"),
                    textposition="middle center",
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="text",
                    text=[tile_glyph(False)],
                    textfont=dict(size=14, color="rgba(240,234,220,0.35)"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    fig.update_layout(
        dragmode=False,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True, scaleanchor="x", scaleratio=1),
        height=680,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f0eadc"),
    )
    return fig
