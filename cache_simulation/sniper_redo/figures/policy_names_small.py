#!/usr/bin/env python3
"""Small, simple picture: short name -> full form for the replacement-policy labels used on the graphs.
Dependency: pycairo only.   usage: python3 policy_names_small.py <outdir>   writes policy_names_small.png (2x), .pdf, .svg
Pure white background, palette of the reference charts."""
import os
import sys

import cairo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


WHITE, INK, GRID, TEAL, MUTED = (1.0, 1.0, 1.0), rgb("#12141A"), rgb("#E4E5E8"), rgb("#0F766E"), rgb("#565A60")
ROWS = [("SRRIP", "Static Re-Reference Interval Prediction"), ("random", "Random replacement"),
        ("NRU", "Not Recently Used"), ("NMRU", "Not Most Recently Used"),
        ("PLRU (8-way)", "Pseudo-Least Recently Used (8-way)"),
        ("SRRIP (8-way)", "Static Re-Reference Interval Prediction (8-way)")]
W, ROW_H, TOP = 1040, 62, 24
H = TOP * 2 + ROW_H * len(ROWS)


def text(c, x, y, s, size, color, bold=False, anchor="l"):
    c.select_font_face("Liberation Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)
    w = c.text_extents(s).x_advance
    if anchor == "r":
        x -= w
    c.move_to(x, y + size * 0.35)
    c.show_text(s)


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    for i, (short, full) in enumerate(ROWS):
        y = TOP + i * ROW_H
        cy = y + ROW_H / 2.0
        if i:
            c.set_source_rgb(*GRID)
            c.set_line_width(1.2)
            c.move_to(24, y)
            c.line_to(W - 24, y)
            c.stroke()
        text(c, 250, cy, short, 30, TEAL, bold=True, anchor="r")
        text(c, 272, cy, "=", 28, MUTED)
        text(c, 312, cy, full, 30, INK)


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    s = make(os.path.join(OUT, f"policy_names_small.{ext}"))
    draw(cairo.Context(s))
    s.finish()
s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(s)
ctx.scale(2, 2)
draw(ctx)
s.write_to_png(os.path.join(OUT, "policy_names_small.png"))
print("wrote", OUT)
