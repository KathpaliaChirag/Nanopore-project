#!/usr/bin/env python3
"""Colourful tree of the experiments, named and numbered exactly as on slides 24 to 32 of the Canva deck
"Kraken-2 midterm presentation".  Full slide (1920x1080), pure white background.
Dependency: pycairo only.   usage: python3 plan_tree_colorful.py <outdir>   writes plan_tree_colorful.png (3840x2160), .pdf, .svg
Experiments 0, 1, 2 = minor work; 3, 4, 5 = major work (as described by the user).
"""
import math
import os
import sys

import cairo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


WHITE, INK, MUTED, LINE = (1.0, 1.0, 1.0), rgb("#12141A"), rgb("#565A60"), rgb("#9A9DA3")
TEAL, ORANGE_D = rgb("#0F766E"), rgb("#B45309")
FONT = "Liberation Sans"
W, H = 1920, 1080

# (number, short name, one line, colour of the experiment, tinted fill)   colours come from the reference charts
EXPS = [
    (0, "Memory mapping", "Wall time with vs without memory mapping, on all databases", rgb("#2F6FED"), rgb("#EAF0FE")),
    (1, "Cell width", "Impact of cell width: benefits and trade-offs", rgb("#1F9E6D"), rgb("#E6F5EF")),
    (2, "Thread-local caching", "Impact of thread-local caching on Kraken2 performance", rgb("#0F766E"), rgb("#E7F1F0")),
    (3, "Double hashing", "5.5x fewer probes but 5.7x more cache misses", rgb("#D92B3A"), rgb("#FCE9EB")),
    (4, "Cache tweaks and prefetcher gains", "LLC and L2 tweaks, and hardware prefetcher gains with more cores", rgb("#FB923C"), rgb("#FFF1E3")),
    (5, "Prefetching", "Batched prefetch (-B): many memory fetches in flight at once", rgb("#E8C520"), rgb("#FBF5D6")),
]
DARK = {0: rgb("#1E4FB8"), 1: rgb("#047857"), 2: rgb("#0F766E"), 3: rgb("#B01E2C"), 4: rgb("#B45309"), 5: rgb("#8A6A00")}


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


def tw(c, s, size, bold=False):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    return c.text_extents(s).x_advance


def wrap(c, s, size, max_w):
    lines, cur = [], ""
    for word in s.split():
        t = (cur + " " + word).strip()
        if tw(c, t, size) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def rrect(c, x, y, w, h, r):
    c.new_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


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
    text(c, 60, 74, "Kraken2: Experiments", 68, INK, bold=True)
    y0, step, bh = 164, 144, 124
    cy = [y0 + step * i + bh / 2.0 for i in range(6)]
    XR, WR = 60, 270
    XB, WB = 440, 290
    XL, WL = 830, 1030
    cm, cM = sum(cy[:3]) / 3.0, sum(cy[3:]) / 3.0
    cr = (cm + cM) / 2.0
    xt1, xt2 = 385, 780
    line(c, [(XR + WR, cr), (xt1, cr)])
    line(c, [(xt1, cm), (xt1, cM)])
    line(c, [(xt1, cm), (XB, cm)])
    line(c, [(xt1, cM), (XB, cM)])
    line(c, [(XB + WB, cm), (xt2, cm)])
    line(c, [(XB + WB, cM), (xt2, cM)])
    line(c, [(xt2, cy[0]), (xt2, cy[2])])
    line(c, [(xt2, cy[3]), (xt2, cy[5])])
    for i, (num, name, one, col, tint) in enumerate(EXPS):
        line(c, [(xt2, cy[i]), (XL, cy[i])], 5, col)
    # root and branches
    rrect(c, XR, cr - 80, WR, 160, 20)
    c.set_source_rgb(*INK)
    c.fill()
    text(c, XR + WR / 2.0, cr - 30, "kraken2", 38, WHITE, bold=True, anchor="m")
    text(c, XR + WR / 2.0, cr + 24, "experiments", 38, WHITE, bold=True, anchor="m")
    for ccy, label, col in ((cm, "Minor work", TEAL), (cM, "Major work", ORANGE_D)):
        rrect(c, XB, ccy - 55, WB, 110, 16)
        c.set_source_rgb(*WHITE)
        c.fill_preserve()
        c.set_source_rgb(*col)
        c.set_line_width(6)
        c.stroke()
        text(c, XB + WB / 2.0, ccy, label, 38, col, bold=True, anchor="m")
    # experiments: coloured leaf with a number badge
    for i, (num, name, one, col, tint) in enumerate(EXPS):
        top = cy[i] - bh / 2.0
        rrect(c, XL, top, WL, bh, 18)
        c.set_source_rgb(*tint)
        c.fill_preserve()
        c.set_source_rgb(*col)
        c.set_line_width(5)
        c.stroke()
        c.new_path()
        c.arc(XL + 62, cy[i], 38, 0, 2 * math.pi)
        c.set_source_rgb(*col)
        c.fill()
        text(c, XL + 62, cy[i], str(num), 46, WHITE if num != 5 else INK, bold=True, anchor="m")
        text(c, XL + 126, cy[i] - 28, f"Experiment-{num} · {name}", 36, DARK[num], bold=True)
        for k, s in enumerate(wrap(c, one, 29, WL - 126 - 30)):
            text(c, XL + 126, cy[i] + 18 + k * 34, s, 29, MUTED)


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    s = make(os.path.join(OUT, f"plan_tree_colorful.{ext}"))
    draw(cairo.Context(s))
    s.finish()
s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(s)
ctx.scale(2, 2)
draw(ctx)
s.write_to_png(os.path.join(OUT, "plan_tree_colorful.png"))
print("wrote", OUT)
