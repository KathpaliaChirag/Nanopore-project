#!/usr/bin/env python3
"""Full-slide (1920x1080) project status picture on a pure white background.
Dependency: pycairo only.   usage: python3 plan_slide.py <outdir>   writes plan_slide.png (3840x2160), .pdf, .svg
The artwork covers the whole slide (content runs margin to margin, top to bottom); background is #FFFFFF.
"""
import math
import os
import sys

import cairo

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


WHITE, INK, MUTED, GRID = (1.0, 1.0, 1.0), rgb("#12141A"), rgb("#565A60"), rgb("#E4E5E8")
TEAL, GREEN, ORANGE_D, BLUE_D = rgb("#0F766E"), rgb("#047857"), rgb("#B45309"), rgb("#1E4FB8")
TEAL_L, ORANGE_L, GREY_L = rgb("#E7F1F0"), rgb("#FDE3C8"), rgb("#E4E5E8")
FONT = "Liberation Sans"
W, H = 1920, 1080


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


def wrap(c, s, size, max_w, bold=False):
    lines, cur = [], ""
    for word in s.split():
        t = (cur + " " + word).strip()
        if tw(c, t, size, bold) <= max_w:
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


def check(c, cx, cy, r, color):
    c.new_path()
    c.arc(cx, cy, r, 0, 2 * math.pi)
    c.set_source_rgb(*color)
    c.fill()
    c.set_source_rgb(*WHITE)
    c.set_line_width(r * 0.18)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.move_to(cx - r * 0.45, cy + r * 0.02)
    c.line_to(cx - r * 0.12, cy + r * 0.36)
    c.line_to(cx + r * 0.46, cy - r * 0.34)
    c.stroke()


def chip(c, x, y, label, fg, bg):
    w = tw(c, label, 22, True) + 28
    rrect(c, x, y, w, 38, 19)
    c.set_source_rgb(*bg)
    c.fill()
    text(c, x + 14, y + 19, label, 22, fg, bold=True)
    return w


STEPS = [
    ("Experiments 0, 1, 2", "Minor experiments, finished.", "MINOR", "minor"),
    ("Simulator set up", "Sniper model of Luna, fair same-source baseline.", "MAJOR", "major"),
    ("Cache design study", "LLC and L2: ways, policy, size (30 variants). No effect on speed.", "MAJOR", "major"),
    ("Prefetcher study", "L1, L2 and both, depth 1 to 16: +3% to +4% on one core.", "MAJOR", "major"),
    ("Scaling study", "10 to 100 reads, 16 GB, 4 to 16 cores: up to +25%.", "MAJOR", "major"),
    ("Result", "Prefetching helps; cache design does not.", "", "result"),
]


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 60, 74, "Project status: the planned work is done", 66, INK, bold=True)
    text(c, 60, 134, "Hardware-cache study of kraken2 on a Sniper model of the Luna server", 30, MUTED)
    # pipeline of six boxes across the full width
    bw, gap, y0, bh = 266, 40.8, 180, 410
    for i, (title, body, tag, kind) in enumerate(STEPS):
        x = 60 + i * (bw + gap)
        rrect(c, x, y0, bw, bh, 18)
        if kind == "result":
            c.set_source_rgb(*TEAL_L)
            c.fill_preserve()
            c.set_source_rgb(*TEAL)
        else:
            c.set_source_rgb(*WHITE)
            c.fill_preserve()
            c.set_source_rgb(*(GRID if kind == "minor" else INK))
        c.set_line_width(4)
        c.stroke()
        check(c, x + 44, y0 + 54, 26, TEAL if kind in ("minor", "result") else GREEN)
        text(c, x + 84, y0 + 54, "DONE", 24, TEAL if kind in ("minor", "result") else GREEN, bold=True)
        ty = y0 + 124
        for s in wrap(c, title, 33, bw - 40, True):
            text(c, x + 20, ty, s, 33, INK, bold=True)
            ty += 40
        ty += 10
        for s in wrap(c, body, 25, bw - 40):
            text(c, x + 20, ty, s, 25, MUTED if kind != "result" else INK)
            ty += 33
        if tag:
            chip(c, x + 20, y0 + bh - 58, tag, MUTED if kind == "minor" else ORANGE_D, GREY_L if kind == "minor" else ORANGE_L)
        if i < len(STEPS) - 1:
            text(c, x + bw + gap / 2.0, y0 + bh / 2.0, "→", 40, MUTED, anchor="m")
    # key numbers across the full width
    cw, cgap, cy0 = 573, 40.5, 636
    stats = [("206", "simulation runs", TEAL), ("≤ 0.3%", "effect of any cache-design change (two L2 exceptions)", BLUE_D),
             ("+3% to +25%", "prefetcher gain, one core to 16 cores", ORANGE_D)]
    for i, (num, label, col) in enumerate(stats):
        x = 60 + i * (cw + cgap)
        c.set_source_rgb(*INK)
        c.rectangle(x, cy0, cw, 5)
        c.fill()
        text(c, x, cy0 + 96, num, 88, col, bold=True)
        ly = cy0 + 164
        for s in wrap(c, label, 30, cw):
            text(c, x, ly, s, 30, INK)
            ly += 38
    # open follow-ups strip
    rrect(c, 60, 910, W - 120, 118, 16)
    c.set_source_rgb(*rgb("#B9BBC0"))
    c.set_line_width(3)
    c.set_dash([14, 10])
    c.stroke()
    c.set_dash([])
    text(c, 92, 952, "Optional follow-ups still open", 30, INK, bold=True)
    text(c, 92, 996, "Real-machine check on Luna (CPU prefetchers off vs on)   ·   Long-read test (about 5 M bases)", 29, MUTED)


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    s = make(os.path.join(OUT, f"plan_slide.{ext}"))
    draw(cairo.Context(s))
    s.finish()
s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(s)
ctx.scale(2, 2)
draw(ctx)
s.write_to_png(os.path.join(OUT, "plan_slide.png"))
print("wrote", OUT)
