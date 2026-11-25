#!/usr/bin/env python3
"""Tall one-column dot plot: every cache tweak we tested, one dot per row, pure white, reference palette.

Dependency: pycairo only.   usage:  python3 dotplot_column.py ../data/hw_results_all.csv  <outdir>
writes dotplot_column.png (2x raster), .pdf and .svg (vector).  Every number is computed from the CSV.

Metric: simulated time saved (%) = (t_base - t_variant) / t_base * 100, t = Sniper simulated time of the slowest core;
base = the same run with unmodified hardware (no prefetcher).  Right of 0 = faster.
Default condition: 8 GB database, 1 core, 50 reads.  Rows in the last section vary ONE of those settings and use the
L1 + L2 prefetchers, each against the same condition without prefetchers.
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
STRIP = rgb("#F3F4F6")
TEAL = rgb("#0F766E")       # cache design
ORANGE = rgb("#FB923C")     # hardware prefetcher
ORANGE_D = rgb("#B45309")
BLUE = rgb("#2F6FED")       # prefetcher under other conditions
BLUE_D = rgb("#1E4FB8")
RED = rgb("#B91C2C")        # slower
GREEN_D = rgb("#047857")    # faster
BAND = rgb("#D5E8E5")
FONT = "Liberation Sans"

runs = {}
for r in csv.DictReader(open(CSV_PATH)):
    if r["rc"] == "0":
        runs[(r["variant"], int(r["cores"]), int(r["reads"]), r["db"])] = r


def saved(variant, db="8gb", cores=1, reads=50):
    a, b = runs[(variant, cores, reads, db)], runs[("base", cores, reads, db)]
    try:
        ta, tb = float(a["sim_time_fs"]), float(b["sim_time_fs"])
    except ValueError:
        ta, tb = float(a["cycles_M"]), float(b["cycles_M"])
    return (1.0 - ta / tb) * 100.0


# ---- rows: ("h", header text, kind) or ("r", label, kind, value) ---------------------------------------------------
ROWS = []


def header(text, kind):
    ROWS.append(("h", text, kind))


def row(label, kind, value):
    ROWS.append(("r", label, kind, value))


header("LLC: last-level cache  (baseline: 15-way, 2.25 MB per core, LRU)", "design")
for lab, v in (("1-way (direct-mapped)", "llc_assoc1"), ("2-way", "llc_assoc2"), ("4-way", "llc_assoc4"),
               ("8-way", "llc_assoc8"), ("16-way", "llc_assoc16"),
               ("SRRIP replacement", "llc_srrip"), ("random replacement", "llc_random"), ("NRU replacement", "llc_nru"),
               ("NMRU replacement", "llc_nmru"), ("PLRU replacement (8-way)", "llc8_plru"), ("SRRIP replacement (8-way)", "llc8_srrip"),
               ("half size", "llc_half"), ("2x size", "llc_x2"), ("4x size", "llc_x4")):
    row(lab, "design", saved(v))
header("L2 cache  (baseline: 16-way, 2 MB, LRU)", "design")
for lab, v in (("4-way", "l2_assoc4"), ("8-way", "l2_assoc8"), ("32-way", "l2_assoc32"),
               ("SRRIP replacement", "l2_srrip"), ("random replacement", "l2_random"), ("PLRU replacement (8-way)", "l2_8_plru"),
               ("1 MB (half size)", "l2_1mb"), ("4 MB (2x size)", "l2_4mb")):
    row(lab, "design", saved(v))
header("Hardware prefetcher  (baseline: none)", "pf")
for lab, v in (("L1, depth 1 (control)", "pf_l1_n1"), ("L1, depth 2", "pf_l1_n2"), ("L1, depth 4", "pf_l1_simple"),
               ("L1, depth 8", "pf_l1_n8"), ("L1, depth 16", "pf_l1_n16"), ("L1, depth 4, 32 streams", "pf_l1_f32"),
               ("L2, depth 8, 64 streams", "pf_l2_simple"), ("L1 + L2 together", "pf_both")):
    row(lab, "pf", saved(v))
header("L1 + L2 prefetchers under other conditions  (each vs the same run without them)", "cond")
for lab, kw in (("10 reads", dict(reads=10)), ("25 reads", dict(reads=25)), ("50 reads (reference)", dict()),
                ("100 reads", dict(reads=100)), ("16 GB database", dict(db="16gb")),
                ("4 cores", dict(cores=4)), ("8 cores", dict(cores=8)), ("16 cores", dict(cores=16)),
                ("16 GB + 8 cores", dict(db="16gb", cores=8)), ("16 GB + 16 cores", dict(db="16gb", cores=16))):
    row(lab, "cond", saved("pf_both", **kw))

# ---- geometry ------------------------------------------------------------------------------------------------------
W = 1300
X0, X1 = 440, 1100
XMIN, XMAX = -3.0, 27.0
XV = W - 40                     # right edge of the value column
ROW_H, HDR_H = 46, 56
Y0 = 235
Y1 = Y0 + sum(HDR_H if r[0] == "h" else ROW_H for r in ROWS)
H = int(Y1 + 330)
TICKS = (0, 5, 10, 15, 20, 25)


def px(v):
    return X0 + (v - XMIN) / (XMAX - XMIN) * (X1 - X0)


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


def tw(c, s, size, bold=False):
    font(c, size, bold)
    return c.text_extents(s).x_advance


def line(c, x1, y1, x2, y2, w=1.5, color=INK):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.move_to(x1, y1)
    c.line_to(x2, y2)
    c.stroke()


def dot(c, x, y, fill, outline, r=10):
    c.new_path()
    c.arc(x, y, r, 0, 2 * math.pi)
    c.set_source_rgb(*fill)
    c.fill_preserve()
    c.set_source_rgb(*outline)
    c.set_line_width(1.8)
    c.stroke()


KIND = {"design": (TEAL, TEAL, MUTED), "pf": (ORANGE, ORANGE_D, ORANGE_D), "cond": (BLUE, BLUE_D, BLUE_D)}


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 30, 48, "Which cache tweaks speed kraken2 up?", 44, INK, bold=True)
    text(c, 30, 98, "One dot = one run (8 GB, 1 core, 50 reads unless stated). Right of 0 = faster than without the tweak.", 24, MUTED)
    x = 30
    for kind, lab in (("design", "cache design: size, ways, policy"), ("pf", "hardware prefetcher"),
                      ("cond", "prefetchers, other conditions")):
        fill, outline, _ = KIND[kind]
        dot(c, x + 12, 146, fill, outline, 10)
        text(c, x + 34, 146, lab, 23)
        x += 34 + tw(c, lab, 23) + 40

    # noise band, grid, zero line
    c.set_source_rgb(*BAND)
    c.rectangle(px(-1), Y0, px(1) - px(-1), Y1 - Y0)
    c.fill()
    text(c, px(0), Y0 - 16, "within 1%", 21, MUTED, anchor="m")
    for t in TICKS:
        if t:
            line(c, px(t), Y0, px(t), Y1, 1.0, GRID)
    line(c, px(0), Y0, px(0), Y1, 2.0, INK)

    # rows
    y = Y0
    for r in ROWS:
        if r[0] == "h":   # opaque strip drawn over the band and zero line so the header text stays clean
            c.set_source_rgb(*STRIP)
            c.rectangle(24, y, W - 48, HDR_H)
            c.fill()
            c.set_source_rgb(*KIND[r[2]][0])
            c.rectangle(24, y, 8, HDR_H)
            c.fill()
            text(c, 46, y + HDR_H / 2.0, r[1], 24, INK, bold=True)
            y += HDR_H
            continue
        _, label, kind, v = r
        fill, outline, vcol = KIND[kind]
        cy = y + ROW_H / 2.0
        line(c, 24, y + ROW_H, W - 24, y + ROW_H, 1.0, GRID)
        text(c, X0 - 18, cy, label, 26, INK, anchor="r", bold=(label.startswith("L1 + L2 together")))
        dot(c, px(v), cy, fill, outline, 10)
        s = f"{abs(v):.1f}%" if round(abs(v), 1) == 0 else (("−" if v < 0 else "+") + f"{abs(v):.1f}%")
        col = RED if v < -1.0 else (vcol if v > 1.0 else MUTED)
        text(c, XV, cy, s, 26, col, bold=abs(v) > 1.0, anchor="r")
        y += ROW_H
    text(c, XV, Y0 - 16, "saved", 21, MUTED, bold=True, anchor="r")

    # axis
    line(c, X0, Y1, X1, Y1, 2.0, INK)
    for t in TICKS:
        line(c, px(t), Y1, px(t), Y1 + 9, 2.0, INK)
        text(c, px(t), Y1 + 34, str(t), 24, MUTED, anchor="m")
    text(c, X0, Y1 + 74, "← slower", 24, RED)
    text(c, X1, Y1 + 74, "faster →", 24, GREEN_D, anchor="r")
    text(c, (X0 + X1) / 2.0, Y1 + 118, "Time saved vs the unmodified cache (%)", 26, INK, anchor="m")

    # footer
    n = sum(1 for r in ROWS if r[0] == "r")
    notes = [
        "Time saved = (baseline simulated time − tweaked simulated time) / baseline simulated time × 100, the time the simulated",
        "CPU would take (slowest core). Sniper simulation of the real kraken2 classifier; reads are small (7.9 K to 164 K bases),",
        "so effects at production scale may differ. Depth counts the address being read, so depth 1 fetches nothing extra (a control).",
        f"{n} dots = {n} simulation runs.",
    ]
    for i, s in enumerate(notes):
        text(c, 30, Y1 + 175 + 34 * i, s, 21, MUTED)


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    surf = make(os.path.join(OUT, f"dotplot_column.{ext}"))
    draw(cairo.Context(surf))
    surf.finish()
surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(surf)
ctx.scale(2, 2)
draw(ctx)
surf.write_to_png(os.path.join(OUT, "dotplot_column.png"))
print("wrote", OUT, "rows:", sum(1 for r in ROWS if r[0] == "r"), "size:", W, H)
