#!/usr/bin/env python3
"""Simple dot plot: which cache tweaks speed kraken2 up?  One panel, pure white, palette of the reference charts.

Dependency: pycairo only.   usage:  python3 dotplot_simple.py ../data/hw_results_all.csv  <outdir>
writes dotplot_simple.png (2x raster), .pdf and .svg (vector).  Every number is computed from the CSV.
Condition: 8 GB database, 1 core, 50 reads.  Metric: simulated time saved (%) vs the unmodified cache (right = faster).
"""
import csv
import math
import os
import sys

import cairo

CSV_PATH, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


WHITE = (1.0, 1.0, 1.0)
INK = rgb("#12141A")
MUTED = rgb("#565A60")
GRID = rgb("#E4E5E8")
TEAL = rgb("#0F766E")      # cache design
ORANGE = rgb("#FB923C")    # hardware prefetcher
ORANGE_D = rgb("#B45309")
RED = rgb("#B91C2C")       # slower
GREEN_D = rgb("#047857")
BAND = rgb("#D5E8E5")
FONT = "Liberation Sans"

runs = {}
for r in csv.DictReader(open(CSV_PATH)):
    if r["rc"] == "0":
        runs[(r["variant"], int(r["cores"]), int(r["reads"]), r["db"])] = r


def saved(variant):
    a, b = runs[(variant, 1, 50, "8gb")], runs[("base", 1, 50, "8gb")]
    return (1.0 - float(a["sim_time_fs"]) / float(b["sim_time_fs"])) * 100.0


GROUPS = [
    ("LLC associativity (1 to 16 way)", "design", ["llc_assoc1", "llc_assoc2", "llc_assoc4", "llc_assoc8", "llc_assoc16"]),
    ("LLC replacement policy (6)", "design", ["llc_srrip", "llc_random", "llc_nru", "llc_nmru", "llc8_plru", "llc8_srrip"]),
    ("LLC size (half to 4x)", "design", ["llc_half", "llc_x2", "llc_x4"]),
    ("L2 associativity (4 to 32 way)", "design", ["l2_assoc4", "l2_assoc8", "l2_assoc32"]),
    ("L2 replacement policy (3)", "design", ["l2_srrip", "l2_random", "l2_8_plru"]),
    ("L2 size (1 MB and 4 MB)", "design", ["l2_1mb", "l2_4mb"]),
    ("L1 prefetcher (depth 1 to 16)", "pf", ["pf_l1_n1", "pf_l1_n2", "pf_l1_simple", "pf_l1_n8", "pf_l1_n16", "pf_l1_f32"]),
    ("L2 prefetcher", "pf", ["pf_l2_simple"]),
    ("L1 + L2 prefetchers", "pf", ["pf_both"]),
]
W, H = 1100, 720
L, R, T, B = 400, 50, 140, 100
X0, X1, Y0, Y1 = L, W - R, T, H - B
XMIN, XMAX = -3.0, 6.0


def font(c, size, bold=False, color=INK):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)


def text(c, x, y, s, size, color=INK, bold=False, anchor="l"):
    font(c, size, bold, color)
    w = c.text_extents(s).x_advance
    if anchor == "r":
        x -= w
    elif anchor == "m":
        x -= w / 2.0
    c.move_to(x, y + size * 0.35)
    c.show_text(s)


def line(c, x1, y1, x2, y2, w=1.5, color=INK):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.move_to(x1, y1)
    c.line_to(x2, y2)
    c.stroke()


def dot(c, x, y, fill, outline):
    c.new_path()
    c.arc(x, y, 8, 0, 2 * math.pi)
    c.set_source_rgb(*fill)
    c.fill_preserve()
    c.set_source_rgb(*outline)
    c.set_line_width(1.5)
    c.stroke()


def px(v):
    return X0 + (v - XMIN) / (XMAX - XMIN) * (X1 - X0)


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 24, 30, "Which cache tweaks speed kraken2 up?", 30, INK, bold=True)
    text(c, 24, 68, "One dot = one run (8 GB database, 1 core, 50 reads). Right of 0 = faster than the unmodified cache.", 22, MUTED)
    dot(c, 38, 108, TEAL, TEAL)
    text(c, 58, 108, "cache design: size, ways, policy", 23)
    dot(c, 470, 108, ORANGE, ORANGE_D)
    text(c, 490, 108, "hardware prefetcher", 23)

    n = len(GROUPS)
    step = (Y1 - Y0) / n
    c.set_source_rgb(*BAND)
    c.rectangle(px(-1), Y0, px(1) - px(-1), Y1 - Y0)
    c.fill()
    text(c, px(1) - 8, Y1 - 24, "within 1%", 20, MUTED, anchor="r")
    for t in (-2, 0, 2, 4, 6):
        line(c, px(t), Y0, px(t), Y1, 2.0 if t == 0 else 1.0, INK if t == 0 else GRID)
        text(c, px(t), Y1 + 26, ("−" + str(-t)) if t < 0 else str(t), 23, MUTED, anchor="m")
    for k, (label, kind, variants) in enumerate(GROUPS):
        cy = Y0 + step * (k + 0.5)
        if k:
            line(c, 24, Y0 + step * k, X1, Y0 + step * k, 1.0, GRID)
        text(c, X0 - 16, cy, label, 21, INK, anchor="r", bold=(kind == "pf"))
        vals = [saved(v) for v in variants]
        fill, outline = (TEAL, TEAL) if kind == "design" else (ORANGE, ORANGE_D)
        for v in vals:
            dot(c, px(v), cy, fill, outline)
        if max(vals) > 1.0:
            text(c, px(max(vals)) + 16, cy, f"best +{max(vals):.1f}%", 21, ORANGE_D, bold=True)
        if min(vals) < -1.0:
            v = min(vals)
            if v < -2.0:
                text(c, px(v) + 16, cy, f"−{abs(v):.1f}%", 21, RED, bold=True)
            else:
                text(c, px(v) - 16, cy, f"−{abs(v):.1f}%", 21, RED, bold=True, anchor="r")
    line(c, X0, Y1, X1, Y1, 1.5, INK)
    text(c, px(-3), Y1 + 56, "← slower", 22, RED)
    text(c, px(6), Y1 + 56, "faster →", 22, GREEN_D, anchor="r")
    text(c, (X0 + X1) / 2, H - 12, "Time saved vs the unmodified cache (%)", 24, INK, anchor="m")


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    surf = make(os.path.join(OUT, f"dotplot_simple.{ext}"))
    draw(cairo.Context(surf))
    surf.finish()
surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(surf)
ctx.scale(2, 2)
draw(ctx)
surf.write_to_png(os.path.join(OUT, "dotplot_simple.png"))
print("wrote", OUT)
