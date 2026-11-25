#!/usr/bin/env python3
"""Publication figures for the Sniper hardware-cache study of kraken2.

Dependency: pycairo only (no matplotlib, because Luna cannot reach PyPI without the campus login).
usage:  python3 plot_figs.py ../data/hw_results_all.csv  <outdir>

Every number is computed from the results CSV, none is typed in. For each figure it writes
  figN_name.pdf   vector, white background (journal / paper use)
  figN_name.svg   vector, white background
  figN_name_slide.png   2x raster on the slide background colour (for the deck)

Metric: simulated time of a run (slowest core), as a percent change against the "base" run with the
same core count, read count and database. base = Sniper default hardware, no prefetcher.
"""
import csv
import math
import os
import sys

import cairo

CSV_PATH, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------- data
rows = {}
for r in csv.DictReader(open(CSV_PATH)):
    if r["rc"] == "0":
        rows[(r["variant"], int(r["cores"]), int(r["reads"]), r["db"])] = r


def change(variant, cores, reads, db):
    """percent change in simulated time vs base at the same cores/reads/db (negative = faster)."""
    a = rows[(variant, cores, reads, db)]
    b = rows[("base", cores, reads, db)]
    try:
        ta, tb = float(a["sim_time_fs"]), float(b["sim_time_fs"])
    except ValueError:  # four 4-core rows lost their stats file: fall back to the printed cycle count for both
        ta, tb = float(a["cycles_M"]), float(b["cycles_M"])
    return (ta / tb - 1.0) * 100.0


def saved(variant, cores, reads, db):
    """percent of simulated time saved (positive = faster)."""
    return -change(variant, cores, reads, db)


# ----------------------------------------------------------------------------- style
FONT = "Liberation Sans"
INK = (0.11, 0.12, 0.14)
MUTED = (0.38, 0.41, 0.46)
RULE = (0.84, 0.85, 0.87)
BLUE = (0.0, 0.447, 0.698)      # Okabe-Ito blue
ORANGE = (0.835, 0.369, 0.0)    # Okabe-Ito vermillion
AMBER = (0.80, 0.55, 0.0)       # darkened Okabe-Ito orange-yellow, readable on white
GREY = (0.55, 0.57, 0.60)
SLIDE_BG = (0.984, 0.984, 0.976)  # must match --paper in the deck css (#fbfbf9)


def set_font(c, size, bold=False, color=INK):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)


def text(c, x, y, s, size, color=INK, bold=False, anchor="l"):
    """y is the vertical centre of the text."""
    set_font(c, size, bold, color)
    e = c.text_extents(s)
    if anchor == "r":
        x -= e.x_advance
    elif anchor == "m":
        x -= e.x_advance / 2.0
    c.move_to(x, y + size * 0.35)
    c.show_text(s)


def line(c, x1, y1, x2, y2, w=1.5, color=INK, dash=None):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.set_dash(dash or [])
    c.move_to(x1, y1)
    c.line_to(x2, y2)
    c.stroke()
    c.set_dash([])


def dot(c, x, y, r, color, hollow=False, bg=(1, 1, 1)):
    c.arc(x, y, r, 0, 2 * math.pi)
    if hollow:
        c.set_source_rgb(*bg)
        c.fill_preserve()
        c.set_source_rgb(*color)
        c.set_line_width(2.2)
        c.stroke()
    else:
        c.set_source_rgb(*color)
        c.fill()


def fmt(v, sign=False, nd=1):
    s = f"{abs(v):.{nd}f}"
    if v < 0 or (v == 0 and False):
        return "−" + s
    return ("+" if sign and v > 0 else "") + s


def ylabel(c, x, cy, s, size=24):
    c.save()
    c.translate(x, cy)
    c.rotate(-math.pi / 2)
    text(c, 0, 0, s, size, MUTED, anchor="m")
    c.restore()


def render(name, w, h, draw):
    """draw(c, bg) is called once per output so the PDF/SVG are white and the PNG matches the slide."""
    for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, w, h)), ("svg", lambda p: cairo.SVGSurface(p, w, h))):
        surf = make(os.path.join(OUT, f"{name}.{ext}"))
        c = cairo.Context(surf)
        c.set_source_rgb(1, 1, 1)
        c.paint()
        draw(c, (1, 1, 1))
        surf.finish()
    scale = 2
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * scale, h * scale)
    c = cairo.Context(surf)
    c.scale(scale, scale)
    c.set_source_rgb(*SLIDE_BG)
    c.paint()
    draw(c, SLIDE_BG)
    surf.write_to_png(os.path.join(OUT, f"{name}_slide.png"))


# ----------------------------------------------------------------------------- generic line chart
def line_chart(c, bg, W, H, cats, series, ymax, yticks, ylab, xlab, right_pad=210, val_labels=True, ymin=0):
    L, R, T, B = 110, right_pad, 30, 100
    x0, x1, y0, y1 = L, W - R, T, H - B

    def px(i):
        return x0 + 40 + (x1 - x0 - 80) * i / (len(cats) - 1)

    def py(v):
        return y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)

    for t in yticks:
        line(c, x0, py(t), x1, py(t), 1.0, RULE)
        text(c, x0 - 14, py(t), f"{t:g}", 24, MUTED, anchor="r")
    line(c, x0, py(0), x1, py(0), 2.0, INK)
    if ymin < 0:
        line(c, x0, y1, x1, y1, 1.0, RULE)
    for i, lab in enumerate(cats):
        line(c, px(i), y1, px(i), y1 + 8, 2.0, INK)
        text(c, px(i), y1 + 34, str(lab), 26, INK, anchor="m")
    text(c, (x0 + x1) / 2, H - 22, xlab, 26, INK, anchor="m")
    ylabel(c, 28, (y0 + y1) / 2, ylab)
    for s in series:
        pts = [(i, v) for i, v in enumerate(s["vals"]) if v is not None]
        for (i1, v1), (i2, v2) in zip(pts, pts[1:]):
            if (i2 - i1) > 1:
                continue
            line(c, px(i1), py(v1), px(i2), py(v2), s.get("w", 3.2), s["color"], [10, 8] if s.get("dashed") else None)
        for i, v in pts:
            dot(c, px(i), py(v), s.get("r", 7), s["color"], hollow=s.get("hollow", False), bg=bg)
            if val_labels and s.get("labels", True) and i not in s.get("skip", ()):
                text(c, px(i), py(v) + (26 if i in s.get("below", ()) else -24), f"{v:.1f}", 22, s["color"], bold=True, anchor="m")
        i, v = pts[-1]
        text(c, px(i) + 22, py(v) + s.get("label_dy", 0), s["label"], 24, s["color"], bold=True)


# ----------------------------------------------------------------------------- figure 1: organisation is flat
def fig1(c, bg):
    W, H = 1040, 680
    items = [  # (label, variant, highlight)
        ("LLC 1-way", "llc_assoc1"), ("LLC 2-way", "llc_assoc2"), ("LLC 4-way", "llc_assoc4"),
        ("LLC 8-way", "llc_assoc8"), ("LLC 16-way", "llc_assoc16"), None,
        ("LLC SRRIP", "llc_srrip"), ("LLC random", "llc_random"), ("LLC NRU", "llc_nru"),
        ("LLC NMRU", "llc_nmru"), ("LLC 8-way PLRU", "llc8_plru"), ("LLC 8-way SRRIP", "llc8_srrip"), None,
        ("LLC half size", "llc_half"), ("LLC 2x size", "llc_x2"), ("LLC 4x size", "llc_x4"), None,
        ("L2 4-way", "l2_assoc4"), ("L2 8-way", "l2_assoc8"), ("L2 32-way", "l2_assoc32"), None,
        ("L2 SRRIP", "l2_srrip"), ("L2 random", "l2_random"), ("L2 8-way PLRU", "l2_8_plru"), None,
        ("L2 1 MB (half)", "l2_1mb"), ("L2 4 MB (double)", "l2_4mb"),
    ]
    L, R, T, B = 300, 50, 16, 96
    x0, x1, y0, y1 = L, W - R, T, H - B
    xmin, xmax = -1.0, 3.0

    def px(v):
        return x0 + (v - xmin) / (xmax - xmin) * (x1 - x0)

    n = len(items)
    step = (y1 - y0) / n
    for t in (-1, 0, 1, 2, 3):
        line(c, px(t), y0, px(t), y1, 2.0 if t == 0 else 1.0, INK if t == 0 else RULE)
        text(c, px(t), y1 + 26, fmt(t, nd=0) if t != 0 else "0", 24, MUTED, anchor="m")
    text(c, (x0 + x1) / 2, H - 22, "Change in simulated time vs base (%)", 26, INK, anchor="m")
    for k, it in enumerate(items):
        cy = y0 + step * (k + 0.5)
        if it is None:
            line(c, 40, cy, x1, cy, 0.8, RULE)
            continue
        label, variant = it
        v = change(variant, 1, 50, "8gb")
        hot = v > 1.0
        text(c, x0 - 16, cy, label, 21, INK, anchor="r")
        dot(c, px(v), cy, 7.5, ORANGE if hot else BLUE)
        if hot:
            text(c, px(v) + 16, cy, fmt(v, sign=True, nd=2) + "%", 21, ORANGE, bold=True)


# ----------------------------------------------------------------------------- figure 2: prefetch depth
def fig2(c, bg):
    W, H = 1100, 640
    depths = [("pf_l1_n1", 1), ("pf_l1_n2", 2), ("pf_l1_simple", 4), ("pf_l1_n8", 8), ("pf_l1_n16", 16)]
    cats = [d for _, d in depths]
    series = []
    for reads, color, dy in ((10, BLUE, 0), (25, AMBER, 0), (50, INK, 0)):
        series.append({"vals": [saved(v, 1, reads, "8gb") for v, _ in depths], "color": color,
                       "label": f"{reads} reads", "label_dy": dy, "labels": reads != 25, "skip": (0,)})
    line_chart(c, bg, W, H, cats, series, 12, [0, 3, 6, 9, 12], "Simulated time saved (%)",
               "L1 prefetcher depth (cache lines ahead)", right_pad=170)


# ----------------------------------------------------------------------------- figure 3: gain vs core count
def fig3(c, bg):
    W, H = 1100, 640
    cores = [1, 4, 8, 16]

    def both(db):
        out = []
        for n in cores:
            try:
                out.append(saved("pf_both", n, 50, db))
            except KeyError:
                out.append(None)
        return out

    def control(db):
        out = []
        for n in cores:
            try:
                out.append(saved("llc_assoc4", n, 50, db))
            except KeyError:
                out.append(None)
        return out

    series = [
        {"vals": both("16gb"), "color": ORANGE, "label": "16 GB", "label_dy": -4, "below": (0,)},
        {"vals": both("8gb"), "color": BLUE, "label": "8 GB", "label_dy": 12},
        {"vals": control("8gb"), "color": GREY, "label": "4-way LLC", "hollow": True, "labels": False, "w": 2.0, "r": 6, "label_dy": 2},
    ]
    line_chart(c, bg, W, H, cores, series, 28, [0, 7, 14, 21, 28], "Simulated time saved (%)",
               "Cores simulated (50 reads)", right_pad=190, ymin=-2.5)
    text(c, 150, 70, "L1 + L2 prefetchers vs none", 22, MUTED)


# ----------------------------------------------------------------------------- figure 4: reads vs cores
def fig4(c, bg):
    W, H = 1100, 640
    reads = [10, 25, 50]
    series = [
        {"vals": [saved("pf_both", 4, r, "8gb") for r in reads], "color": ORANGE, "label": "4 cores"},
        {"vals": [saved("pf_both", 1, r, "8gb") for r in reads], "color": BLUE, "label": "1 core", "below": (0,)},
    ]
    line_chart(c, bg, W, H, reads, series, 18, [0, 6, 12, 18], "Simulated time saved (%)",
               "Reads classified (8 GB database)", right_pad=190)
    text(c, 150, 70, "L1 + L2 prefetchers vs none", 22, MUTED)


render("fig1_organisation_flat", 1040, 680, fig1)
render("fig2_prefetch_depth", 1100, 640, fig2)
render("fig3_gain_vs_cores", 1100, 640, fig3)
render("fig4_reads_vs_cores", 1100, 640, fig4)

# numbers quoted on the slides, printed so they can be checked against the figures
print("fig1 LLC variants, change at 50 reads / 8 GB:",
      {v: round(change(v, 1, 50, "8gb"), 2) for v in ("llc_assoc1", "llc_assoc4", "llc_assoc16", "llc_srrip", "llc_x4", "llc_half")})
print("fig1 worst L2:", {v: round(change(v, 1, 50, "8gb"), 2) for v in ("l2_1mb", "l2_random")})
print("fig3 pf_both saved %:", {(db, n): round(saved("pf_both", n, 50, db), 1)
                                  for db in ("8gb", "16gb") for n in (1, 4, 8, 16) if ("pf_both", n, 50, db) in rows})
print("fig4 pf_both saved %:", {(n, r): round(saved("pf_both", n, r, "8gb"), 1) for n in (1, 4) for r in (10, 25, 50)})
print("wrote figures to", OUT)
