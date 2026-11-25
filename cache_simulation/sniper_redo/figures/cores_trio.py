#!/usr/bin/env python3
"""Three pictures for the multicore prefetcher result: line chart, table, colour-coded formula.
Reads 10 / 50 / 100, cores 4 / 8 / 16, 8 GB database, L1 + L2 prefetchers vs no prefetcher.

Dependency: pycairo only.   usage:  python3 cores_trio.py ../data/hw_results_all.csv  <outdir>
writes cores_chart, cores_table, cores_formula as .png (2x), .pdf, .svg.  Pure white background; every number from the CSV.
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
BLUE = rgb("#2F6FED")
BLUE_D = rgb("#1E4FB8")
ORANGE = rgb("#FB923C")
ORANGE_D = rgb("#B45309")
GREEN = rgb("#1F9E6D")
GREEN_D = rgb("#047857")
TEAL = rgb("#0F766E")
FONT = "Liberation Sans"

READS = (10, 50, 100)
CORES = (4, 8, 16)
SER = {10: (BLUE, BLUE_D), 50: (ORANGE, ORANGE_D), 100: (GREEN, GREEN_D)}   # (line/marker colour, text colour)

runs = {}
for r in csv.DictReader(open(CSV_PATH)):
    if r["rc"] == "0":
        runs[(r["variant"], int(r["cores"]), int(r["reads"]), r["db"])] = r


def pair(cores, reads):
    """-> (base simulated time us, with-prefetch time us, saved %)"""
    a, b = runs[("pf_both", cores, reads, "8gb")], runs[("base", cores, reads, "8gb")]
    ta, tb = float(a["sim_time_fs"]) / 1e9, float(b["sim_time_fs"]) / 1e9
    return tb, ta, (1.0 - ta / tb) * 100.0


def font(c, size, bold=False, color=INK):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)


def tw(c, s, size, bold=False):
    font(c, size, bold)
    return c.text_extents(s).x_advance


def text(c, x, y, s, size, color=INK, bold=False, anchor="l"):
    font(c, size, bold, color)
    w = c.text_extents(s).x_advance
    if anchor == "r":
        x -= w
    elif anchor == "m":
        x -= w / 2.0
    c.move_to(x, y + size * 0.35)
    c.show_text(s)


def segments(c, x, y, parts, size):
    """draw coloured text pieces one after another; parts = [(text, colour, bold)]."""
    for s, col, b in parts:
        text(c, x, y, s, size, col, b)
        x += tw(c, s, size, b)
    return x


def line(c, x1, y1, x2, y2, w=1.5, color=INK):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.move_to(x1, y1)
    c.line_to(x2, y2)
    c.stroke()


def dot(c, x, y, fill, outline, r=8):
    c.new_path()
    c.arc(x, y, r, 0, 2 * math.pi)
    c.set_source_rgb(*fill)
    c.fill_preserve()
    c.set_source_rgb(*outline)
    c.set_line_width(1.8)
    c.stroke()


# ---- 1. line chart -----------------------------------------------------------------------------------------------
def chart(c):
    W, H = 1100, 700
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 24, 32, "Does the prefetcher gain grow with more cores?", 32, INK, bold=True)
    text(c, 24, 72, "L1 + L2 prefetchers together, 8 GB database. Higher = faster than no prefetcher.", 22, MUTED)
    x = 24
    for n in READS:
        fill, tcol = SER[n]
        line(c, x, 112, x + 38, 112, 4.0, fill)
        dot(c, x + 19, 112, fill, tcol, 7)
        lab = f"{n} reads"
        text(c, x + 50, 112, lab, 23)
        x += 50 + tw(c, lab, 23) + 46
    L, R, T, B = 110, 240, 160, 100
    x0, x1, y0, y1 = L, W - R, T, H - B
    ymax = 30.0

    def px(i):
        return x0 + 70 + (x1 - x0 - 140) * i / (len(CORES) - 1)

    def py(v):
        return y1 - v / ymax * (y1 - y0)

    for t in (0, 6, 12, 18, 24, 30):
        line(c, x0, py(t), x1, py(t), 1.0, GRID)
        text(c, x0 - 14, py(t), str(t), 23, MUTED, anchor="r")
    line(c, x0, py(0), x1, py(0), 2.0, INK)
    for i, n in enumerate(CORES):
        line(c, px(i), y1, px(i), y1 + 8, 2.0, INK)
        text(c, px(i), y1 + 34, str(n), 26, INK, anchor="m")
    text(c, (x0 + x1) / 2.0, H - 22, "Cores simulated", 24, INK, anchor="m")
    c.save()
    c.translate(30, (y0 + y1) / 2.0)
    c.rotate(-math.pi / 2)
    text(c, 0, 0, "Time saved vs no prefetcher (%)", 23, MUTED, anchor="m")
    c.restore()
    pos = {10: ("below", "above", "above"), 50: ("above", "below", "below"), 100: ("above", "above", "above")}
    dy_end = {10: -20, 50: 20, 100: 0}
    for n in READS:
        fill, tcol = SER[n]
        vals = [pair(k, n)[2] for k in CORES]
        for i in range(len(CORES) - 1):
            line(c, px(i), py(vals[i]), px(i + 1), py(vals[i + 1]), 4.0, fill)
        for i, v in enumerate(vals):
            dot(c, px(i), py(v), fill, tcol, 8)
            text(c, px(i), py(v) + (28 if pos[n][i] == "below" else -26), f"{v:.1f}", 23, tcol, bold=True, anchor="m")
        text(c, px(len(CORES) - 1) + 52, py(vals[-1]) + dy_end[n], f"{n} reads", 23, tcol, bold=True)
    return W, H


# ---- 2. table ----------------------------------------------------------------------------------------------------
def table(c):
    W, H = 1140, 540
    c.set_source_rgb(*WHITE)
    c.paint()
    cx = [30, 260, 550, 840]          # column left edges: row label, then three data columns of width 290
    cw = 290
    hdr_y, hdr_h, row_h = 24, 76, 128
    c.set_source_rgb(*STRIP)
    c.rectangle(30, hdr_y, W - 60, hdr_h)
    c.fill()
    for j, n in enumerate(READS):
        fill, tcol = SER[n]
        text(c, cx[j + 1] + cw / 2.0, hdr_y + hdr_h / 2.0 - 4, f"{n} reads", 32, tcol, bold=True, anchor="m")
        c.set_source_rgb(*fill)
        c.rectangle(cx[j + 1] + 30, hdr_y + hdr_h - 8, cw - 60, 6)
        c.fill()
    for i, k in enumerate(CORES):
        y = hdr_y + hdr_h + i * row_h
        line(c, 30, y + row_h, W - 30, y + row_h, 1.5, GRID)
        text(c, cx[0] + 14, y + row_h / 2.0, f"{k} cores", 32, INK, bold=True)
        for j, n in enumerate(READS):
            base, pf, saved = pair(k, n)
            text(c, cx[j + 1] + cw / 2.0, y + 38, f"{base / 1000:.1f} → {pf / 1000:.1f}", 31, INK, anchor="m")
            text(c, cx[j + 1] + cw / 2.0, y + 86, f"{saved:.1f}%", 38, SER[n][1], bold=True, anchor="m")
    text(c, 30, H - 36, "Simulated ms: no prefetcher → with prefetchers.  Coloured % = time saved.  8 GB database.", 22, MUTED)
    return W, H


# ---- 3. formula --------------------------------------------------------------------------------------------------
def formula(c):
    W, H = 1100, 560
    c.set_source_rgb(*WHITE)
    c.paint()
    base, pf, saved = pair(8, 100)
    text(c, 30, 44, "How it is calculated", 38, BLUE_D, bold=True)
    segments(c, 30, 124, [("Saved %", BLUE_D, True), ("  =  ( ", INK, False), ("base", TEAL, True), ("  −  ", INK, False),
                          ("with prefetch", ORANGE_D, True), (" )  ÷  ", INK, False), ("base", TEAL, True),
                          ("  ×  100", INK, False)], 40)
    segments(c, 30, 204, [("base", TEAL, True), ("  =  simulated time with no prefetcher", INK, False)], 29)
    segments(c, 30, 246, [("with prefetch", ORANGE_D, True), ("  =  simulated time with the L1 + L2 prefetchers on", INK, False)], 29)
    segments(c, 30, 288, [("simulated time", MUTED, True), ("  =  time the simulated CPU needs; the slowest core decides", INK, False)], 29)
    text(c, 30, 328, "(Sniper cycles divided by the 2.1 GHz clock)", 24, MUTED)
    line(c, 30, 372, W - 30, 372, 2.0, GRID)
    text(c, 30, 410, "Example: 8 cores, 100 reads, 8 GB database (times in microseconds)", 26, MUTED, bold=True)
    segments(c, 30, 480, [("( ", INK, False), (f"{base:,.1f}", TEAL, True), ("  −  ", INK, False), (f"{pf:,.1f}", ORANGE_D, True),
                          (" )  ÷  ", INK, False), (f"{base:,.1f}", TEAL, True), ("  ×  100  =  ", INK, False),
                          (f"{saved:.1f}%", BLUE_D, True)], 38)
    return W, H


for name, fn in (("cores_chart", chart), ("cores_table", table), ("cores_formula", formula)):
    surf = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    size = fn(cairo.Context(surf))
    W, H = size
    for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
        s = make(os.path.join(OUT, f"{name}.{ext}"))
        fn(cairo.Context(s))
        s.finish()
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
    ctx = cairo.Context(s)
    ctx.scale(2, 2)
    fn(ctx)
    s.write_to_png(os.path.join(OUT, f"{name}.png"))
print("wrote", OUT)
