#!/usr/bin/env python3
"""研究模式的小图表：一条折线，或者几根柱。

照 AUDIT-AND-IDEAS.md 4.12 第 8 轮：不画网格线、坐标轴和刻度；线宽 0.12u，颜色用 ink；
高亮的点或柱用重点色，没有重点色就用 ink；只标一个关键值，字号 u。
输出内联 SVG，bento_render 把它放进 chart 格标签下面的图区。
"""
from __future__ import annotations

import html

LINE_W = 0.12      # 线宽，单位 u
DOT_R = 0.38       # 高亮点半径
LABEL_GAP = 0.45   # 数值标注的基线离点（或柱顶）多远，另加点的半径
BAR_GAP = 0.35     # 柱间距，按柱宽的比例
BAR_RADIUS = 0.55  # 柱的圆头半径，单位 u（第 10 轮评审：苹果的界面元素都是圆头）
MUTED = {"#000000": "#c7c7c7", "#ffffff": "#4d4d4d"}   # 有高亮时，其余的柱用灰


def _fmt(v: float) -> str:
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _text_w(text: str, u: float) -> float:
    try:
        from bento_render import text_em
        return text_em(text) * u
    except Exception:
        return len(text) * 0.6 * u


def _n(v: float) -> str:
    return "%.2f" % v


def svg(series, highlight=None, kind="line", width=300.0, height=200.0, u=20.0, ink="#000000",
        accent=None, highlight_label=None) -> str:
    """series: numbers; highlight: index of the one value to mark and label, or None; kind: line or bar."""
    vals = [float(v) for v in series]
    if len(vals) < 2:
        raise ValueError("series needs at least two values")
    if highlight is not None and not 0 <= int(highlight) < len(vals):
        raise ValueError("highlight index out of range")
    if kind not in ("line", "bar"):
        raise ValueError("kind is line or bar")
    hi_colour = accent or ink
    label = None
    if highlight is not None:
        highlight = int(highlight)
        label = str(highlight_label) if highlight_label not in (None, "") else _fmt(vals[highlight])
    edge = (DOT_R + LINE_W) * u
    top = (1.2 + LABEL_GAP + DOT_R) * u if label else edge      # room for the value above the highest point
    parts = []
    bars = []                                   # (x0, x1, top) of each bar, to keep the value label off them
    if kind == "line":
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        x0, x1 = edge, width - edge
        y0, y1 = top, height - edge
        pts = [(x0 + (x1 - x0) * i / (len(vals) - 1), y1 - (y1 - y0) * (v - lo) / span) for i, v in enumerate(vals)]
        parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round" '
                     'stroke-linecap="round"/>' % (" ".join("%s,%s" % (_n(x), _n(y)) for x, y in pts), ink,
                                                    _n(LINE_W * u)))
        if highlight is not None:
            hx, hy = pts[highlight]
            parts.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (_n(hx), _n(hy), _n(DOT_R * u), hi_colour))
            anchor_x, anchor_y = hx, hy - (DOT_R + LABEL_GAP) * u
    else:
        lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
        span = (hi - lo) or 1.0
        n = len(vals)
        bw = width / (n + (n - 1) * BAR_GAP)
        base = top + (height - top) * hi / span
        others = MUTED.get(ink.lower(), ink) if highlight is not None else ink
        for i, v in enumerate(vals):
            x = i * bw * (1 + BAR_GAP)
            y_end = top + (height - top) * (hi - v) / span
            y, h = min(base, y_end), abs(base - y_end)
            fill = hi_colour if i == highlight else others
            hh = max(h, LINE_W * u)
            bars.append((x, x + bw, y))
            r = min(bw / 2, BAR_RADIUS * u, hh / 2)            # round ends, like the bars in Apple's own charts
            parts.append('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"/>' % (
                _n(x), _n(y), _n(bw), _n(hh), _n(r), fill))
        if highlight is not None:
            v = vals[highlight]
            anchor_x = highlight * bw * (1 + BAR_GAP) + bw / 2
            anchor_y = top + (height - top) * (hi - max(v, 0.0)) / span - LABEL_GAP * u
    if label:
        # Centred over its point or bar, nudged inward just enough to stay inside the chart.
        tw = _text_w(label, u)
        anchor = "middle"
        anchor_x = min(max(anchor_x, tw / 2), max(tw / 2, width - tw / 2))
        # A label wider than its bar must also clear the neighbouring bars it reaches over (round 10 review).
        under = [top_y for x0, x1, top_y in bars if x1 > anchor_x - tw / 2 and x0 < anchor_x + tw / 2]
        if under:
            anchor_y = min(anchor_y, min(under) - LABEL_GAP * u)
        parts.append('<text class="chart-label" x="%s" y="%s" text-anchor="%s" font-size="%s" fill="%s">%s</text>'
                     % (_n(anchor_x), _n(anchor_y), anchor, _n(u), ink, html.escape(label)))
    return ('<svg class="chart" xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">%s</svg>'
            % (_n(width), _n(height), _n(width), _n(height), "".join(parts)))
