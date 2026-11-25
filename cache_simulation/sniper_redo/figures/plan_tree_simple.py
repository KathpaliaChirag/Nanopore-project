#!/usr/bin/env python3
"""Simplest tree flowchart: each experiment with a one-line description. Full slide (1920x1080), pure white.
Dependency: pycairo only.   usage: python3 plan_tree_simple.py <outdir>   writes plan_tree_simple.png (3840x2160), .pdf, .svg
"""
import math
import os
import sys

import cairo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


WHITE, INK, MUTED, GRID, LINE = (1.0, 1.0, 1.0), rgb("#12141A"), rgb("#565A60"), rgb("#E4E5E8"), rgb("#9A9DA3")
TEAL, ORANGE_D = rgb("#0F766E"), rgb("#B45309")
FONT = "Liberation Sans"
W, H = 1920, 1080

MINOR = [("Experiment 0", "Minor work"), ("Experiment 1", "Minor work"), ("Experiment 2", "Minor work")]
MAJOR = [("Simulator set up", "Model Luna's CPU and caches in the Sniper simulator"),
         ("Cache design study", "Change LLC and L2 ways, replacement policy and size"),
         ("Prefetcher study", "Add L1 and L2 hardware prefetchers"),
         ("Scaling study", "Repeat with more reads, a 16 GB database and 4 to 16 cores")]


def text(c, x, y, s, size, color=INK, bold=False, anchor="l"):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)
    w = c.text_extents(s).x_advance
    if anchor == "m":
        x -= w / 2.0
    elif anchor == "r":
        x -= w
    c.move_to(x, y + size * 0.35)
    c.show_text(s)


def rrect(c, x, y, w, h, r):
    c.new_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


def box(c, x, y, w, h, fill, stroke, lw=4, r=16):
    rrect(c, x, y, w, h, r)
    if fill is not None:
        c.set_source_rgb(*fill)
        c.fill_preserve()
    c.set_source_rgb(*stroke)
    c.set_line_width(lw)
    c.stroke()


def line(c, pts, w=4, color=LINE):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)
    c.stroke()


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 60, 74, "Experiments", 68, INK, bold=True)
    leaves = MINOR + MAJOR
    y0, step, bh = 170, 126, 100
    cy = [y0 + step * i + bh / 2.0 + 10 for i in range(len(leaves))]
    XR, WR = 60, 270
    XB, WB = 440, 290
    XL, WL = 830, 1030
    cm = sum(cy[:3]) / 3.0
    cM = sum(cy[3:]) / 4.0
    cr = (cm + cM) / 2.0
    xt1, xt2 = 385, 780
    # connectors
    line(c, [(XR + WR, cr), (xt1, cr)])
    line(c, [(xt1, cm), (xt1, cM)])
    line(c, [(xt1, cm), (XB, cm)])
    line(c, [(xt1, cM), (XB, cM)])
    line(c, [(XB + WB, cm), (xt2, cm)])
    line(c, [(xt2, cy[0]), (xt2, cy[2])])
    line(c, [(XB + WB, cM), (xt2, cM)])
    line(c, [(xt2, cy[3]), (xt2, cy[6])])
    for y in cy:
        line(c, [(xt2, y), (XL, y)])
    # root and branches
    box(c, XR, cr - 80, WR, 160, INK, INK, r=20)
    text(c, XR + WR / 2.0, cr - 30, "kraken2", 38, WHITE, bold=True, anchor="m")
    text(c, XR + WR / 2.0, cr + 24, "cache study", 38, WHITE, bold=True, anchor="m")
    box(c, XB, cm - 55, WB, 110, WHITE, TEAL, lw=5)
    text(c, XB + WB / 2.0, cm, "Minor work", 38, TEAL, bold=True, anchor="m")
    box(c, XB, cM - 55, WB, 110, WHITE, ORANGE_D, lw=5)
    text(c, XB + WB / 2.0, cM, "Major work", 38, ORANGE_D, bold=True, anchor="m")
    # leaves: experiment name + one line
    for i, (name, one) in enumerate(leaves):
        top = cy[i] - bh / 2.0
        box(c, XL, top, WL, bh, WHITE, GRID if i < 3 else INK, lw=4)
        text(c, XL + 32, cy[i] - 20, name, 38, INK, bold=True)
        text(c, XL + 32, cy[i] + 26, one, 30, MUTED)


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    s = make(os.path.join(OUT, f"plan_tree_simple.{ext}"))
    draw(cairo.Context(s))
    s.finish()
s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(s)
ctx.scale(2, 2)
draw(ctx)
s.write_to_png(os.path.join(OUT, "plan_tree_simple.png"))
print("wrote", OUT)
