#!/usr/bin/env python3
"""Glossary picture: full forms of the replacement-policy short names (and the other short names) used on the graphs.
Dependency: pycairo only.   usage:  python3 policy_glossary.py <outdir>      writes policy_glossary.png (2x), .pdf, .svg
Pure white background, palette of the reference charts.
"""
import math
import os
import sys

import cairo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


WHITE = (1.0, 1.0, 1.0)
INK = rgb("#12141A")
MUTED = rgb("#565A60")
GRID = rgb("#E4E5E8")
STRIP = rgb("#F3F4F6")
TEAL = rgb("#0F766E")
ORANGE_D = rgb("#B45309")
BLUE_D = rgb("#1E4FB8")
FONT = "Liberation Sans"
W, H = 1920, 1080

POLICIES = [  # short name, full form, plain meaning, tag
    ("LRU", "Least Recently Used", "Throw out the item that has gone unused the longest. This is the unmodified default.", "baseline"),
    ("SRRIP", "Static Re-Reference Interval Prediction",
     "A small counter per item predicts when it will be used again; throw out the one predicted furthest away. "
     "Resists one-time scans.", ""),
    ("Random", "Random replacement", "Throw out any item at random. The cheapest policy: nothing to track.", ""),
    ("NRU", "Not Recently Used", "One 'used lately' bit per item; throw out an item whose bit says it was not used lately.", ""),
    ("NMRU", "Not Most Recently Used", "Throw out any item except the one used most recently (the pick among the rest is random).", ""),
    ("PLRU", "Pseudo-Least Recently Used", "A cheap tree of bits that approximates LRU. Sniper only supports it for 4 or 8 ways, "
                                           "so it was tested on an 8-way cache.", ""),
]
OTHERS = [
    ("LLC", "Last-Level Cache", "the biggest cache, shared by the cores, the last stop before main memory"),
    ("L2", "Level-2 cache", "the middle cache, private to each core"),
    ("L1", "Level-1 cache", "the smallest, fastest cache, right next to the core"),
    ("way", "one slot", "associativity = how many slots (ways) a block of data may sit in"),
]


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


def wrap(c, s, size, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if tw(c, trial, size) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def line(c, x1, y1, x2, y2, w=1.5, color=INK):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.move_to(x1, y1)
    c.line_to(x2, y2)
    c.stroke()


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 60, 66, "Replacement policies: what the short names stand for", 52, INK, bold=True)
    text(c, 60, 122, "When a cache slot set is full and new data arrives, the policy decides which old item to throw out.", 27, MUTED)
    # column headers
    c.set_source_rgb(*STRIP)
    c.rectangle(40, 160, W - 80, 54)
    c.fill()
    text(c, 70, 187, "Short name", 25, MUTED, bold=True)
    text(c, 330, 187, "Full form", 25, MUTED, bold=True)
    text(c, 1040, 187, "In plain words", 25, MUTED, bold=True)
    y = 214
    row_h = 92
    for short, full, meaning, tag in POLICIES:
        line(c, 40, y + row_h, W - 40, y + row_h, 1.0, GRID)
        cy = y + row_h / 2.0
        text(c, 70, cy, short, 42, TEAL, bold=True)
        if tag:
            tx = 70 + tw(c, short, 42, True) + 18
            chip_w = tw(c, tag, 21, True) + 22          # measure first: tw() resets the drawing colour
            c.set_source_rgb(*ORANGE_D)
            c.rectangle(tx, cy - 17, chip_w, 34)
            c.fill()
            text(c, tx + 11, cy, tag, 21, WHITE, bold=True)
        fl = wrap(c, full, 31, 680)
        for i, s in enumerate(fl):
            text(c, 330, cy + (i - (len(fl) - 1) / 2.0) * 38, s, 31, INK, bold=True)
        ml = wrap(c, meaning, 26, 830)
        for i, s in enumerate(ml):
            text(c, 1040, cy + (i - (len(ml) - 1) / 2.0) * 34, s, 26, MUTED)
        y += row_h
    # footnote about (8-way)
    text(c, 60, y + 34, "“(8-way)” after a name = the same policy on an 8-way cache (the unmodified LLC is 15-way). "
                        "PLRU only works for 4 or 8 ways, so SRRIP (8-way) is the fair comparison.", 24, INK)
    # other short names
    y += 66
    text(c, 60, y + 4, "Other short names on the graphs", 30, BLUE_D, bold=True)
    for i, (short, full, meaning) in enumerate(OTHERS):   # one column, one line each, so nothing can overlap
        yy = y + 50 + i * 40
        text(c, 60, yy, short, 30, TEAL, bold=True)
        text(c, 170, yy, full, 27, INK, bold=True)
        text(c, 170 + tw(c, full, 27, True) + 16, yy, "– " + meaning, 24, MUTED)


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    s = make(os.path.join(OUT, f"policy_glossary.{ext}"))
    draw(cairo.Context(s))
    s.finish()
s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(s)
ctx.scale(2, 2)
draw(ctx)
s.write_to_png(os.path.join(OUT, "policy_glossary.png"))
print("wrote", OUT)
