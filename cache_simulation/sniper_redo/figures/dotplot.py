#!/usr/bin/env python3
"""Which hardware-cache tweaks speed kraken2 up?  Dot plot (v4): pure white, palette of the reference charts.

Dependency: pycairo only (matplotlib is not installable on Luna: PyPI needs the campus login).
usage:  python3 dotplot.py ../data/hw_results_all.csv  <outdir>
writes: dotplot.png (2440x1920 px), dotplot.pdf and dotplot.svg (vector, half-size units).  Background: pure #FFFFFF.

Every number is computed from the results CSV; nothing is typed in.
metric : saved % = (t_base - t_variant) / t_base * 100, t = Sniper simulated time of the slowest core (sim_time_fs);
         base = the same cores / reads / database with unmodified hardware (no prefetcher).
         Four 4-core 50-read rows lost their stats file: their (0.1 M rounded) cycle counts are used for both the
         variant and its base, and those points are drawn hollow.
layout : two stacked blocks that share the same panel columns, each with its OWN x scale:
         top    = cache-design tweaks (18 rows), zoomed to -3..+1.5 % so their small spreads are visible
         bottom = hardware prefetchers (9 rows), -1..+24 %, plus a small panel with the 100-read runs
         one row per variant, one dot per run, 5 conditions side by side.
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


# ---- palette: measured from the reference charts; text/line variants darkened to pass contrast on white -----------
WHITE = (1.0, 1.0, 1.0)
INK = rgb("#12141A")
MUTED = rgb("#565A60")
GRID = rgb("#E4E5E8")
FAINT = rgb("#B9BBC0")
TEAL = rgb("#0F766E")       # cache design (the reference's dark teal)
ORANGE = rgb("#FB923C")     # hardware prefetcher (the reference's orange)
ORANGE_D = rgb("#B45309")   # orange as text / outline
RED = rgb("#B91C2C")        # slower
GREEN_D = rgb("#047857")    # faster
BAND = rgb("#D5E8E5")       # +-1 % noise band
PF_ROW = rgb("#FFEFDD")     # prefetcher rows
FONT = "Liberation Sans"

# ---- data --------------------------------------------------------------------------------------------------------
runs = {}
for r in csv.DictReader(open(CSV_PATH)):
    if r["rc"] == "0":
        runs[(r["variant"], int(r["cores"]), int(r["reads"]), r["db"])] = r


def saved(variant, cores, reads, db):
    """-> (saved percent, used_cycle_fallback) or None when the run or its base is missing."""
    a = runs.get((variant, cores, reads, db))
    b = runs.get(("base", cores, reads, db))
    if a is None or b is None:
        return None
    try:
        ta, tb, fb = float(a["sim_time_fs"]), float(b["sim_time_fs"]), False
    except ValueError:
        ta, tb, fb = float(a["cycles_M"]), float(b["cycles_M"]), True
    return (1.0 - ta / tb) * 100.0, fb


# ---- spec ----------------------------------------------------------------------------------------------------------
TOP_GROUPS = [  # (group line 1, line 2, [(row label, variant)])
    ("LLC", "associativity", [("1-way", "llc_assoc1"), ("2-way", "llc_assoc2"), ("4-way", "llc_assoc4"),
                              ("8-way", "llc_assoc8"), ("16-way", "llc_assoc16")]),
    ("LLC", "replacement", [("SRRIP", "llc_srrip"), ("random", "llc_random"), ("NRU", "llc_nru"), ("NMRU", "llc_nmru"),
                            ("8-way PLRU", "llc8_plru"), ("8-way SRRIP", "llc8_srrip")]),
    ("LLC", "size", [("half", "llc_half"), ("2x", "llc_x2"), ("4x", "llc_x4")]),
    ("L2", "associativity", [("4-way", "l2_assoc4"), ("8-way", "l2_assoc8"), ("32-way", "l2_assoc32")]),
    ("L2", "replacement", [("SRRIP", "l2_srrip"), ("random", "l2_random"), ("8-way PLRU", "l2_8_plru")]),
    ("L2", "size", [("1 MB (half)", "l2_1mb"), ("4 MB (2x)", "l2_4mb")]),
]
BOT_GROUPS = [
    ("L1", "prefetcher", [("depth 1 (control)", "pf_l1_n1"), ("depth 2", "pf_l1_n2"), ("depth 4", "pf_l1_simple"),
                          ("depth 8", "pf_l1_n8"), ("depth 16", "pf_l1_n16"), ("depth 4, 32 streams", "pf_l1_f32")]),
    ("L2", "prefetcher", [("depth 8, 64 streams", "pf_l2_simple")]),
    ("L1 + L2", "prefetchers", [("depth 4 + depth 8", "pf_both")]),
]
COLS = [  # (database, cores, reads, title, bases caption)
    ("8gb", 1, 10, "8 GB · 1 core · 10 reads", "7.9 K bases"),
    ("8gb", 1, 25, "8 GB · 1 core · 25 reads", "37 K bases"),
    ("8gb", 1, 50, "8 GB · 1 core · 50 reads", "91 K bases"),
    ("16gb", 1, 50, "16 GB · 1 core · 50 reads", "91 K bases"),
    ("8gb", 4, 50, "8 GB · 4 cores · 50 reads", "91 K bases"),
]
BRACKETS = [(0, 2, "more reads (8 GB, 1 core)"), (3, 3, "bigger database"), (4, 4, "more cores")]
HUNDRED = [("8gb", 1, 100, "1 core"), ("8gb", 4, 100, "4 cores")]   # the 100-read runs (L1 + L2 only)

W, H = 2440, 1960
X_LEFT, COL_W, COL_GAP = 540, 252, 26
TOP = dict(step=34, xr=(-3.0, 1.5), ticks=(-3, -2, -1, 0, 1))
BOT = dict(step=44, xr=(-1.0, 24.0), ticks=(0, 5, 10, 15, 20))
Y0T = 392
Y1T = Y0T + TOP["step"] * sum(len(g[2]) for g in TOP_GROUPS)
Y0B = Y1T + 205
Y1B = Y0B + BOT["step"] * sum(len(g[2]) for g in BOT_GROUPS)


def col_x0(i):
    return X_LEFT + i * (COL_W + COL_GAP)


XR_BEST = col_x0(5) + COL_W + 100
XR_WORST = col_x0(5) + COL_W + 196


# ---- helpers -------------------------------------------------------------------------------------------------------
def font(c, size, bold=False, color=INK):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)


def tw(c, s, size, bold=False):
    font(c, size, bold)
    return c.text_extents(s).x_advance


def text(c, x, y, s, size, color=INK, bold=False, anchor="l"):
    """y = vertical centre of the text."""
    font(c, size, bold, color)
    w = c.text_extents(s).x_advance
    if anchor == "r":
        x -= w
    elif anchor == "m":
        x -= w / 2.0
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


def dot(c, x, y, r, color, outline, hollow=False):
    c.new_path()
    c.arc(x, y, r, 0, 2 * math.pi)
    if hollow:
        c.set_source_rgb(*WHITE)
        c.fill_preserve()
        c.set_source_rgb(*outline)
        c.set_line_width(3.0)
        c.stroke()
    else:
        c.set_source_rgb(*color)
        c.fill_preserve()
        c.set_source_rgb(*outline)
        c.set_line_width(1.6)
        c.stroke()


def fmt(v, nd=1):
    s = f"{abs(v):.{nd}f}"
    if round(abs(v), nd) == 0:
        return s
    return ("−" + s) if v < 0 else ("+" + s)


# ---- one block (rows share panel columns; own x scale) ------------------------------------------------------------
def block(c, groups, kind, y0, step, xr, ticks, ncols, stats, tint):
    y1 = y0 + step * sum(len(g[2]) for g in groups)
    fill, outline = (TEAL, TEAL) if kind == "design" else (ORANGE, ORANGE_D)

    def px(i, v):
        return col_x0(i) + (v - xr[0]) / (xr[1] - xr[0]) * COL_W

    if tint:  # one continuous band behind the whole row, labels and table included
        c.set_source_rgb(*PF_ROW)
        c.rectangle(24, y0, XR_WORST + 24 - 24, y1 - y0)
        c.fill()
    for ci in range(ncols):
        x0 = col_x0(ci)
        c.set_source_rgb(*BAND)
        c.rectangle(px(ci, -1), y0, px(ci, 1) - px(ci, -1), y1 - y0)
        c.fill()
        for t in ticks:
            if t != 0:
                line(c, px(ci, t), y0, px(ci, t), y1, 1.0, GRID)
        line(c, px(ci, 0), y0, px(ci, 0), y1, 2.0, INK)
        k = 0
        for g in groups:
            for label, variant in g[2]:
                cy = y0 + step * (k + 0.5)
                res = saved(variant, COLS[ci][1], COLS[ci][2], COLS[ci][0])
                if res is None:
                    line(c, x0 + 6, cy, x0 + COL_W - 6, cy, 2.0, FAINT, [3, 6])
                else:
                    v, fb = res
                    stats.setdefault(variant, []).append(v)
                    xv = px(ci, v)
                    dot(c, xv, cy, 8.5, fill, outline, hollow=fb)
                    if abs(v) > 1.0:
                        text(c, xv + 15, cy, fmt(v), 19, RED if v < 0 else ORANGE_D, bold=True)
                k += 1
        line(c, x0, y1, x0 + COL_W, y1, 2.0, INK)
        for t in ticks:
            line(c, px(ci, t), y1, px(ci, t), y1 + 8, 2.0, INK)
            text(c, px(ci, t), y1 + 30, ("−" + str(-t)) if t < 0 else str(t), 20, MUTED, anchor="m")
    return px, y1


def labels(c, groups, kind, y0, step, stats):
    k = 0
    for gi, (g1, g2, items) in enumerate(groups):
        top = y0 + step * k
        if gi:
            line(c, 30, top, XR_WORST + 24, top, 1.0, GRID)
        mid = top + step * len(items) / 2.0
        gcol = ORANGE_D if kind == "pf" else MUTED
        if len(items) == 1:
            text(c, 30, mid, g1 + " " + g2, 22, gcol, bold=True)
        else:
            text(c, 30, mid - 13, g1, 22, gcol, bold=True)
            text(c, 30, mid + 13, g2, 22, gcol, bold=True)
        for label, variant in items:
            cy = y0 + step * (k + 0.5)
            text(c, X_LEFT - 22, cy, label, 21, INK, anchor="r", bold=(kind == "pf"))
            if variant in stats:
                b, w = max(stats[variant]), min(stats[variant])
                text(c, XR_BEST, cy, fmt(b), 20, ORANGE_D if b > 1 else MUTED, bold=abs(b) > 1, anchor="r")
                text(c, XR_WORST, cy, fmt(w), 20, RED if w < -1 else MUTED, bold=abs(w) > 1, anchor="r")
            k += 1


# ---- the figure ----------------------------------------------------------------------------------------------------
def draw(c):
    c.set_source_rgb(*WHITE)
    c.paint()
    stats_top, stats_bot = {}, {}

    # header
    text(c, 30, 54, "Which cache tweaks speed kraken2 up?", 52, INK, bold=True)
    text(c, 30, 106, "One dot = one simulation run of kraken2 on a model of the Luna CPU, small inputs (7.9 K to 164 K bases). Position = "
                     "simulated time saved vs the unmodified cache: right of 0 = faster, left = slower.", 24, MUTED)
    x, y = 30, 158
    items = [("dot", TEAL, TEAL, "cache design: size, ways, replacement policy"),
             ("dot", ORANGE, ORANGE_D, "hardware prefetcher"),
             ("band", None, None, "within ±1% of base (conservative noise band)"),
             ("hollow", TEAL, TEAL, "from rounded cycle counts (about ±0.4 points, estimated)"),
             ("dotted", None, None, "not run")]
    for kind, col, outl, lab in items:
        if kind == "dot":
            dot(c, x + 14, y, 9, col, outl)
        elif kind == "hollow":
            dot(c, x + 14, y, 8, col, outl, hollow=True)
        elif kind == "band":
            c.set_source_rgb(*BAND); c.rectangle(x, y - 12, 38, 24); c.fill()
        else:
            line(c, x, y, x + 36, y, 2.0, FAINT, [3, 5])
        off = 36 if kind in ("dot", "hollow") else 50
        text(c, x + off, y, lab, 23)
        x += off + tw(c, lab, 23) + 52

    # brackets and column titles (top block)
    for a, b, lab in BRACKETS:
        xa, xb = col_x0(a), col_x0(b) + COL_W
        line(c, xa, 250, xb, 250, 2.0, MUTED)
        line(c, xa, 250, xa, 258, 2.0, MUTED)
        line(c, xb, 250, xb, 258, 2.0, MUTED)
        text(c, (xa + xb) / 2.0, 230, lab, 21, MUTED, anchor="m")
    for ci, (db, cores, reads, title, bases) in enumerate(COLS):
        text(c, col_x0(ci) + COL_W / 2.0, 292, title, 22, INK, bold=True, anchor="m")
        text(c, col_x0(ci) + COL_W / 2.0, 322, bases, 20, MUTED, anchor="m")
    text(c, XR_BEST, 360, "best", 21, MUTED, bold=True, anchor="r")
    text(c, XR_WORST, 360, "worst", 21, MUTED, bold=True, anchor="r")
    text(c, (XR_BEST + XR_WORST) / 2.0 + 10, 384, "across all panels", 17, MUTED, anchor="m")

    # TOP block: cache design, zoomed scale
    px_t, y1t = block(c, TOP_GROUPS, "design", Y0T, TOP["step"], TOP["xr"], TOP["ticks"], 5, stats_top, False)
    labels(c, TOP_GROUPS, "design", Y0T, TOP["step"], stats_top)
    text(c, X_LEFT, y1t + 62, "← slower", 21, RED)
    text(c, col_x0(4) + COL_W, y1t + 62, "faster →", 21, GREEN_D, anchor="r")
    text(c, (X_LEFT + col_x0(4) + COL_W) / 2.0, y1t + 62, "zoomed scale: time saved (%), −3 to +1.5", 22, INK, anchor="m")

    # callout in the empty sixth column of the top block
    cx, cy0 = col_x0(5), Y0T
    design_vals = [v for g in TOP_GROUPS for _, var in g[2] for ci in range(5)
                   for v in [(saved(var, COLS[ci][1], COLS[ci][2], COLS[ci][0]) or (None,))[0]]
                   if v is not None and var not in ("l2_1mb", "l2_random")]
    dmax = max(abs(v) for v in design_vals)
    v1mb, vrnd = saved("l2_1mb", 1, 50, "8gb")[0], saved("l2_random", 1, 50, "8gb")[0]
    c.set_source_rgb(*GRID); c.set_line_width(2.0)
    c.rectangle(cx, cy0, COL_W, 330); c.stroke()
    lines = [("Cache design", True, INK), (f"every other change", False, INK), (f"stays within ±{dmax:.1f}%", False, INK),
             ("of base: noise.", False, INK), ("", False, INK),
             ("Exceptions (50 reads):", True, INK), (f"L2 1 MB   {fmt(v1mb)}%", True, RED),
             (f"L2 random {fmt(vrnd)}%", True, RED), ("", False, INK),
             ("Scale: 1 tick = 1%.", False, MUTED)]
    for i, (s, b, col) in enumerate(lines):
        text(c, cx + 16, cy0 + 28 + 31 * i, s, 20, col, bold=b)

    # BOTTOM block: prefetchers
    text(c, 30, Y0B - 100, "Hardware prefetchers", 30, ORANGE_D, bold=True)
    text(c, 30, Y0B - 62, "own scale: time saved (%), −1 to +24", 21, MUTED)
    text(c, col_x0(5) + COL_W / 2.0, Y0B - 92, "8 GB · 100 reads", 22, INK, bold=True, anchor="m")
    text(c, col_x0(5) + COL_W / 2.0, Y0B - 64, "164 K bases · L1 + L2 only", 20, MUTED, anchor="m")
    text(c, col_x0(5) + COL_W / 2.0, Y0B - 38, "left dot = 1 core, right dot = 4 cores", 19, MUTED, anchor="m")
    px_b, y1b = block(c, BOT_GROUPS, "pf", Y0B, BOT["step"], BOT["xr"], BOT["ticks"], 5, stats_bot, True)
    # sixth panel: the 100-read runs (only L1 + L2 was run)
    xr = BOT["xr"]
    p6 = lambda v: col_x0(5) + (v - xr[0]) / (xr[1] - xr[0]) * COL_W
    rowy = Y0B + BOT["step"] * (sum(len(g[2]) for g in BOT_GROUPS) - 0.5)
    c.set_source_rgb(*BAND); c.rectangle(p6(-1), Y0B, p6(1) - p6(-1), y1b - Y0B); c.fill()
    for t in BOT["ticks"]:
        if t != 0:
            line(c, p6(t), Y0B, p6(t), y1b, 1.0, GRID)
    line(c, p6(0), Y0B, p6(0), y1b, 2.0, INK)
    line(c, col_x0(5), y1b, col_x0(5) + COL_W, y1b, 2.0, INK)
    for t in BOT["ticks"]:
        line(c, p6(t), y1b, p6(t), y1b + 8, 2.0, INK)
        text(c, p6(t), y1b + 30, str(t), 20, MUTED, anchor="m")
    for db, cores, reads, lab in HUNDRED:
        res = saved("pf_both", cores, reads, db)
        if res:
            v, fb = res
            stats_bot.setdefault("pf_both", []).append(v)
            dot(c, p6(v), rowy, 8.5, ORANGE, ORANGE_D, hollow=fb)
            if cores == 1:
                text(c, p6(v) + 15, rowy, fmt(v), 19, ORANGE_D, bold=True)
            else:
                text(c, p6(v) - 15, rowy, fmt(v), 19, ORANGE_D, bold=True, anchor="r")
    labels(c, BOT_GROUPS, "pf", Y0B, BOT["step"], stats_bot)
    text(c, X_LEFT, y1b + 62, "← slower", 21, RED)
    text(c, col_x0(5) + COL_W, y1b + 62, "faster →", 21, GREEN_D, anchor="r")
    text(c, (X_LEFT + col_x0(5) + COL_W) / 2.0, y1b + 62, "Simulated time saved vs the unmodified cache (%)", 24, INK, anchor="m")

    # footer
    dmax_note = dmax
    n_top = sum(len(v) for v in stats_top.values())
    n_bot = sum(len(v) for v in stats_bot.values())
    fy = y1b + 130
    notes = [
        "Time saved (%) = (baseline simulated time − variant simulated time) / baseline simulated time × 100: the time the simulated CPU would "
        "take (slowest core). Baseline = unmodified cache: LLC 15-way 2.25 MB per core, L2 16-way 2 MB, LRU, no prefetcher.",
        "Sniper simulation of the real kraken2 classifier. Reads are small (7.9 K to 164 K bases), so effects at production scale may differ. "
        "Depth counts the address being read, so depth 1 fetches nothing extra (a built-in control).",
        f"Best / worst = highest and lowest value over all panels where the variant was run. {n_top + n_bot} runs plotted. "
        "The two halves use different x scales so that small effects stay visible.",
        f"The measured spread of cache-design variants in these panels is ±{dmax_note:.1f}%; the ±1% band is a conservative margin. "
        "The hollow depth 8 / 16 / 32-stream points at 4 cores cannot be told apart.",
    ]
    for i, s in enumerate(notes):
        text(c, 30, fy + 34 * i, s, 19, MUTED)


# ---- output ---------------------------------------------------------------------------------------------------------
for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W / 2, H / 2)), ("svg", lambda p: cairo.SVGSurface(p, W / 2, H / 2))):
    surf = make(os.path.join(OUT, f"dotplot.{ext}"))
    ctx = cairo.Context(surf)
    ctx.scale(0.5, 0.5)
    draw(ctx)
    surf.finish()
surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
draw(cairo.Context(surf))
surf.write_to_png(os.path.join(OUT, "dotplot.png"))
print("wrote", OUT)
