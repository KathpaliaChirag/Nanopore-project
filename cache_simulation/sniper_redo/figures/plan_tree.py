#!/usr/bin/env python3
"""Full-slide (1920x1080) tree-style flowchart of the project plan: root -> minor / major work -> tasks -> outcomes.
Dependency: pycairo only.   usage: python3 plan_tree.py <outdir>   writes plan_tree.png (3840x2160), .pdf, .svg
Pure white background, same palette as the graphs. Done tasks carry a tick; open follow-ups are dashed.
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
LINE = rgb("#9A9DA3")
TEAL, GREEN, ORANGE_D, BLUE_D = rgb("#0F766E"), rgb("#047857"), rgb("#B45309"), rgb("#1E4FB8")
TEAL_L, ORANGE_L, BLUE_L, GREY_L = rgb("#E7F1F0"), rgb("#FDE3C8"), rgb("#E3EBFB"), rgb("#F3F4F6")
DASH = rgb("#B9BBC0")
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


def rrect(c, x, y, w, h, r):
    c.new_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


def box(c, x, y, w, h, fill, stroke, lw=3.5, dashed=False, r=14):
    rrect(c, x, y, w, h, r)
    if fill is not None:
        c.set_source_rgb(*fill)
        c.fill_preserve()
    c.set_source_rgb(*stroke)
    c.set_line_width(lw)
    if dashed:
        c.set_dash([12, 9])
    c.stroke()
    c.set_dash([])


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
    c.set_line_cap(cairo.LINE_CAP_BUTT)


def open_circle(c, cx, cy, r):
    c.new_path()
    c.arc(cx, cy, r, 0, 2 * math.pi)
    c.set_source_rgb(*DASH)
    c.set_line_width(3.5)
    c.set_dash([6, 5])
    c.stroke()
    c.set_dash([])


def line(c, pts, w=3.5, color=LINE):
    c.set_source_rgb(*color)
    c.set_line_width(w)
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)
    c.stroke()


def arrow_head(c, x, y, color=LINE):
    c.set_source_rgb(*color)
    c.move_to(x, y)
    c.line_to(x - 13, y - 8)
    c.line_to(x - 13, y + 8)
    c.close_path()
    c.fill()


# ---- the tree ---------------------------------------------------------------------------------------------------
# (task name, task sub-line, outcome text, outcome kind, task state)
MINOR = [("Experiment 0", "minor work", "Finished", "grey", "done"),
         ("Experiment 1", "minor work", "Finished", "grey", "done"),
         ("Experiment 2", "minor work", "Finished", "grey", "done")]
MAJOR = [("Simulator set up", "Sniper model of Luna", "Baseline fixed and checked", "grey", "done"),
         ("Cache design study", "LLC and L2 · 30 variants", "No effect (≤ 0.3%, two L2 exceptions)", "blue", "done"),
         ("Prefetcher study", "L1, L2, both · depth 1 to 16", "+3% to +4% on one core", "orange", "done"),
         ("Scaling study", "reads, 16 GB, cores", "Up to +25% on 4 to 16 cores", "orange", "done"),
         ("Real-machine check", "open follow-up", "CPU prefetchers off vs on, on Luna", "open", "open"),
         ("Long-read test", "open follow-up", "about 5 M bases per run", "open", "open")]
OUTCOME_STYLE = {"grey": (GREY_L, MUTED, GRID), "blue": (BLUE_L, BLUE_D, BLUE_D), "orange": (ORANGE_L, ORANGE_D, ORANGE_D),
                 "open": (None, MUTED, DASH)}


def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 60, 66, "Project plan: work done and what came out", 62, INK, bold=True)
    text(c, 60, 124, "Hardware-cache study of kraken2 on a Sniper model of the Luna server", 29, MUTED)
    # legend (top right)
    check(c, 1450, 82, 17, GREEN)
    text(c, 1478, 82, "done", 26, INK)
    open_circle(c, 1590, 82, 17)
    text(c, 1618, 82, "open follow-up", 26, INK)

    y0, step, bh = 196, 78, 68
    rows = MINOR + MAJOR
    cy = [y0 + step * i + bh / 2.0 + 8 for i in range(len(rows))]
    XB, WB = 400, 250              # branch column
    XT, WT = 740, 520              # task column
    XO, WO = 1330, 530             # outcome column
    XR, WR = 60, 275               # root
    # centres of the two branches and the root
    cm = sum(cy[:3]) / 3.0
    cM = sum(cy[3:]) / len(MAJOR)
    cr = (cm + cM) / 2.0
    # connectors first (so boxes sit on top)
    x_trunk1, x_trunk2 = 355, 695
    line(c, [(XR + WR, cr), (x_trunk1, cr)])
    line(c, [(x_trunk1, cm), (x_trunk1, cM)])
    line(c, [(x_trunk1, cm), (XB, cm)])
    line(c, [(x_trunk1, cM), (XB, cM)])
    line(c, [(XB + WB, cm), (x_trunk2, cm)])
    line(c, [(x_trunk2, cy[0]), (x_trunk2, cy[2])])
    for i in range(3):
        line(c, [(x_trunk2, cy[i]), (XT, cy[i])])
    line(c, [(XB + WB, cM), (x_trunk2, cM)])
    line(c, [(x_trunk2, cy[3]), (x_trunk2, cy[-1])])
    for i in range(3, len(rows)):
        line(c, [(x_trunk2, cy[i]), (XT, cy[i])])
    for i in range(len(rows)):
        line(c, [(XT + WT, cy[i]), (XO - 14, cy[i])])
        arrow_head(c, XO, cy[i])
    # root
    box(c, XR, cr - 92, WR, 184, INK, INK, r=18)
    for k, s in enumerate(("kraken2", "hardware-cache", "study")):
        text(c, XR + WR / 2.0, cr - 52 + k * 52, s, 33, WHITE, bold=True, anchor="m")
    # branches
    box(c, XB, cm - 58, WB, 116, WHITE, GRID, lw=4, r=16)
    text(c, XB + WB / 2.0, cm - 16, "Minor work", 34, TEAL, bold=True, anchor="m")
    text(c, XB + WB / 2.0, cm + 24, "Experiments 0 to 2", 24, MUTED, anchor="m")
    box(c, XB, cM - 58, WB, 116, WHITE, INK, lw=4, r=16)
    text(c, XB + WB / 2.0, cM - 16, "Major work", 34, ORANGE_D, bold=True, anchor="m")
    text(c, XB + WB / 2.0, cM + 24, "the cache study", 24, MUTED, anchor="m")
    # tasks and outcomes
    for i, (name, sub, out, kind, state) in enumerate(rows):
        top = cy[i] - bh / 2.0
        minor = i < 3
        if state == "done":
            box(c, XT, top, WT, bh, WHITE, GRID if minor else INK, lw=3.5, r=14)
            check(c, XT + 40, cy[i], 20, TEAL if minor else GREEN)
        else:
            box(c, XT, top, WT, bh, WHITE, DASH, lw=3.5, dashed=True, r=14)
            open_circle(c, XT + 40, cy[i], 20)
        text(c, XT + 80, cy[i] - 13, name, 29, INK if state == "done" else MUTED, bold=True)
        text(c, XT + 80, cy[i] + 18, sub, 22, MUTED)
        fill, fg, edge = OUTCOME_STYLE[kind]
        box(c, XO, top, WO, bh, fill, edge, lw=3.0 if kind != "open" else 3.5, dashed=(kind == "open"), r=14)
        text(c, XO + 22, cy[i], out, 25 if len(out) < 40 else 23, fg, bold=(kind in ("blue", "orange")))
    # result bar
    box(c, 60, 936, W - 120, 92, TEAL_L, TEAL, lw=4, r=18)
    text(c, W / 2.0, 982, "Result: prefetching helps (+3% to +25%), cache design does not (≤ 0.3%)   ·   206 simulation runs",
         35, INK, bold=True, anchor="m")


for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
    s = make(os.path.join(OUT, f"plan_tree.{ext}"))
    draw(cairo.Context(s))
    s.finish()
s = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
ctx = cairo.Context(s)
ctx.scale(2, 2)
draw(ctx)
s.write_to_png(os.path.join(OUT, "plan_tree.png"))
print("wrote", OUT)
