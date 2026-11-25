#!/usr/bin/env python3
"""Publication figures for the Sniper hardware-cache study of kraken2 (v2: titles, legends, callouts).

Dependency: pycairo only (no matplotlib: Luna cannot reach PyPI without the campus login).
usage:  python3 plot_figs.py ../data/hw_results_all.csv  <outdir>

Every number is computed from the results CSV, none is typed in. Per figure it writes
  figN_name.pdf / .svg   vector, white background (paper use)
  figN_name_slide.png    2x raster on the slide background colour (deck use)

Metric: simulated time of a run (slowest core) against the "base" run with the same core count, read
count and database. base = Sniper default hardware = no prefetcher, unmodified caches.
"""
import csv
import math
import os
import sys

import cairo

CSV_PATH, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------- data
rows = {}
for r in csv.DictReader(open(CSV_PATH)):
    if r["rc"] == "0":
        rows[(r["variant"], int(r["cores"]), int(r["reads"]), r["db"])] = r


def change(variant, cores, reads, db):
    """percent change in simulated time vs base (negative = faster)."""
    a = rows[(variant, cores, reads, db)]
    b = rows[("base", cores, reads, db)]
    try:
        ta, tb = float(a["sim_time_fs"]), float(b["sim_time_fs"])
    except ValueError:  # four 4-core rows lost their stats file: use the printed cycle count for both
        ta, tb = float(a["cycles_M"]), float(b["cycles_M"])
    return (ta / tb - 1.0) * 100.0


def saved(variant, cores, reads, db):
    """percent of simulated time saved (positive = faster)."""
    return -change(variant, cores, reads, db)


# ----------------------------------------------------------------------------- style
FONT = "Liberation Sans"
INK = (0.11, 0.12, 0.14)
MUTED = (0.38, 0.41, 0.46)
RULE = (0.84, 0.85, 0.87)
BAND = (0.925, 0.945, 0.97)
BLUE = (0.0, 0.447, 0.698)
ORANGE = (0.835, 0.369, 0.0)
AMBER = (0.80, 0.55, 0.0)
GREY = (0.50, 0.52, 0.56)
SLIDE_BG = (0.984, 0.984, 0.976)  # = --paper in the deck css (#fbfbf9)


def set_font(c, size, bold=False, color=INK):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    c.set_source_rgb(*color)


def tw(c, s, size, bold=False):
    set_font(c, size, bold)
    return c.text_extents(s).x_advance


def text(c, x, y, s, size, color=INK, bold=False, anchor="l"):
    """y is the vertical centre of the text."""
    set_font(c, size, bold, color)
    e = c.text_extents(s)
    if anchor == "r":
        x -= e.x_advance
    elif anchor == "m":
        x -= e.x_advance / 2.0
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


def dot(c, x, y, r, color, hollow=False, bg=(1, 1, 1)):
    c.new_path()
    c.arc(x, y, r, 0, 2 * math.pi)
    if hollow:
        c.set_source_rgb(*bg)
        c.fill_preserve()
        c.set_source_rgb(*color)
        c.set_line_width(2.2)
        c.stroke()
    else:
        c.set_source_rgb(*color)
        c.fill()


def ylabel(c, x, cy, s, size=23):
    c.save()
    c.translate(x, cy)
    c.rotate(-math.pi / 2)
    text(c, 0, 0, s, size, MUTED, anchor="m")
    c.restore()


def header(c, bg, title, sub, legend_items):
    """title (what question), subtitle (what is plotted, which way is better), legend row."""
    text(c, 24, 30, title, 30, INK, bold=True)
    text(c, 24, 68, sub, 22, MUTED)
    x = 24
    for kind, color, label in legend_items:
        if kind == "line":
            line(c, x, 108, x + 38, 108, 3.2, color)
            dot(c, x + 19, 108, 7, color)
        elif kind == "dot":
            dot(c, x + 19, 108, 8, color)
        elif kind == "hollow":
            dot(c, x + 19, 108, 7, color, hollow=True, bg=bg)
        text(c, x + 50, 108, label, 23, INK)
        x += 50 + tw(c, label, 23) + 64


def render(name, w, h, draw):
    for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, w, h)), ("svg", lambda p: cairo.SVGSurface(p, w, h))):
        surf = make(os.path.join(OUT, f"{name}.{ext}"))
        c = cairo.Context(surf)
        c.set_source_rgb(1, 1, 1)
        c.paint()
        draw(c, (1, 1, 1))
        surf.finish()
    scale = 2
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * scale, h * scale)
    c = cairo.Context(surf)
    c.scale(scale, scale)
    c.set_source_rgb(*SLIDE_BG)
    c.paint()
    draw(c, SLIDE_BG)
    surf.write_to_png(os.path.join(OUT, f"{name}_slide.png"))


# ----------------------------------------------------------------------------- generic line chart
def line_chart(c, bg, W, H, cats, series, ymax, yticks, ylab, xlab, head, anns=(), right_pad=190, ymin=0):
    L, R, T, B = 110, right_pad, 150, 96
    x0, x1, y0, y1 = L, W - R, T, H - B

    def px(i):
        return x0 + 40 + (x1 - x0 - 80) * i / (len(cats) - 1)

    def py(v):
        return y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)

    header(c, bg, *head)
    for t in yticks:
        line(c, x0, py(t), x1, py(t), 1.0, RULE)
        text(c, x0 - 14, py(t), f"{t:g}", 23, MUTED, anchor="r")
    line(c, x0, py(0), x1, py(0), 2.0, INK)
    if ymin < 0:
        line(c, x0, y1, x1, y1, 1.0, RULE)
    for i, lab in enumerate(cats):
        line(c, px(i), y1, px(i), y1 + 8, 2.0, INK)
        text(c, px(i), y1 + 34, str(lab), 25, INK, anchor="m")
    text(c, (x0 + x1) / 2, H - 20, xlab, 24, INK, anchor="m")
    ylabel(c, 28, (y0 + y1) / 2, ylab)
    for s in series:
        pts = [(i, v) for i, v in enumerate(s["vals"]) if v is not None]
        for (i1, v1), (i2, v2) in zip(pts, pts[1:]):
            if (i2 - i1) > 1:
                continue  # never join across a missing category
            line(c, px(i1), py(v1), px(i2), py(v2), s.get("w", 3.2), s["color"])
        for i, v in pts:
            dot(c, px(i), py(v), s.get("r", 7), s["color"], hollow=s.get("hollow", False), bg=bg)
            if s.get("labels", True) and i not in s.get("skip", ()):
                text(c, px(i), py(v) + (26 if i in s.get("below", ()) else -24), f"{v:.1f}", 22, s["color"], bold=True, anchor="m")
        i, v = pts[-1]
        text(c, px(i) + 22, py(v) + s.get("label_dy", 0), s["label"], 23, s["color"], bold=True)
    for a in anns:
        text(c, px(a["i"]) + a.get("dx", 0), py(a["v"]) + a.get("dy", 0), a["text"], 22, a.get("color", MUTED),
             bold=a.get("bold", False), anchor=a.get("anchor", "l"))


# ----------------------------------------------------------------------------- figure 1: organisation is flat
def fig1(c, bg):
    W, H = 1100, 730
    groups = [  # (name lines, [(label, variant)])
        (("LLC", "associativity"), [("1-way", "llc_assoc1"), ("2-way", "llc_assoc2"), ("4-way", "llc_assoc4"),
                                    ("8-way", "llc_assoc8"), ("16-way", "llc_assoc16")]),
        (("LLC", "replacement"), [("SRRIP", "llc_srrip"), ("random", "llc_random"), ("NRU", "llc_nru"),
                                  ("NMRU", "llc_nmru"), ("8-way PLRU", "llc8_plru"), ("8-way SRRIP", "llc8_srrip")]),
        (("LLC", "size"), [("half", "llc_half"), ("2x", "llc_x2"), ("4x", "llc_x4")]),
        (("L2", "associativity"), [("4-way", "l2_assoc4"), ("8-way", "l2_assoc8"), ("32-way", "l2_assoc32")]),
        (("L2", "replacement"), [("SRRIP", "l2_srrip"), ("random", "l2_random"), ("8-way PLRU", "l2_8_plru")]),
        (("L2", "size"), [("1 MB (half)", "l2_1mb"), ("4 MB (2x)", "l2_4mb")]),
    ]
    header(c, bg, "Does changing the cache's design speed kraken2 up?",
           "One dot = one run (8 GB database, 1 core, 50 reads). Left of 0 = faster, right = slower.",
           [("dot", BLUE, "under 1% (noise level)"), ("dot", ORANGE, "over 1% slower")])
    L, R, T, B = 300, 40, 140, 100
    x0, x1, y0, y1 = L, W - R, T, H - B
    xmin, xmax = -1.0, 3.0

    def px(v):
        return x0 + (v - xmin) / (xmax - xmin) * (x1 - x0)

    n = sum(len(g[1]) for g in groups)
    step = (y1 - y0) / n
    c.set_source_rgb(*BAND)
    c.rectangle(px(-1), y0, px(1) - px(-1), y1 - y0)
    c.fill()
    text(c, px(1) - 10, y1 - step * 0.5, "within 1% of base", 20, MUTED, anchor="r")
    for t in (-1, 0, 1, 2, 3):
        line(c, px(t), y0, px(t), y1, 2.0 if t == 0 else 1.0, INK if t == 0 else RULE)
        text(c, px(t), y1 + 26, f"{t}" if t >= 0 else "−" + str(-t), 23, MUTED, anchor="m")
    k = 0
    for gi, (names, items) in enumerate(groups):
        top = y0 + step * k
        if gi:
            line(c, 24, top, x1, top, 1.0, RULE)
        mid = top + step * len(items) / 2.0
        text(c, 24, mid - 12, names[0], 21, MUTED, bold=True)
        text(c, 24, mid + 12, names[1], 21, MUTED, bold=True)
        for label, variant in items:
            cy = y0 + step * (k + 0.5)
            v = change(variant, 1, 50, "8gb")
            hot = v > 1.0
            text(c, x0 - 16, cy, label, 21, INK, anchor="r")
            dot(c, px(v), cy, 7.5, ORANGE if hot else BLUE)
            if hot:
                text(c, px(v) + 16, cy, f"+{v:.2f}%", 21, ORANGE, bold=True)
            k += 1
    text(c, px(-1), y1 + 60, "← faster", 22, MUTED)
    text(c, px(3), y1 + 60, "slower →", 22, MUTED, anchor="r")
    text(c, (x0 + x1) / 2, H - 12, "Change in simulated time vs the unmodified cache (%)", 24, INK, anchor="m")


# ----------------------------------------------------------------------------- figure 2: prefetch depth
def fig2(c, bg):
    W, H = 1100, 690
    depths = [("pf_l1_n1", 1), ("pf_l1_n2", 2), ("pf_l1_simple", 4), ("pf_l1_n8", 8), ("pf_l1_n16", 16)]
    cats = [d for _, d in depths]
    series = []
    for reads, color in ((10, BLUE), (25, AMBER), (50, INK)):
        series.append({"vals": [saved(v, 1, reads, "8gb") for v, _ in depths], "color": color,
                       "label": f"{reads} reads", "labels": reads != 25, "skip": (0,), "below": (1, 2, 3, 4) if reads == 50 else ()})
    head = ("Does fetching ahead help?",
            "One L1 prefetcher; 8 GB database, 1 core. Higher = faster than no prefetcher.",
            [("line", BLUE, "10 reads"), ("line", AMBER, "25 reads"), ("line", INK, "50 reads")])
    anns = [
        {"i": 0, "v": -0.7, "text": "1 line ahead: no effect", "dx": -10, "color": MUTED},
        {"i": 1, "v": 11.5, "text": "2 lines already gets most of the gain", "dx": -40},
        {"i": 3, "v": 7.4, "text": "levels off beyond 4 lines", "anchor": "m"},
    ]
    line_chart(c, bg, W, H, cats, series, 12.4, [0, 3, 6, 9, 12], "Time saved vs no prefetcher (%)",
               "How far ahead the prefetcher fetches (cache lines)", head, anns, right_pad=170, ymin=-1.2)


# ----------------------------------------------------------------------------- figure 3: gain vs core count
def fig3(c, bg):
    W, H = 1100, 690
    cores = [1, 4, 8, 16]

    def get(variant, db):
        out = []
        for n in cores:
            try:
                out.append(saved(variant, n, 50, db))
            except KeyError:
                out.append(None)
        return out

    series = [
        {"vals": get("pf_both", "16gb"), "color": ORANGE, "label": "16 GB", "label_dy": -4, "below": (0,)},
        {"vals": get("pf_both", "8gb"), "color": BLUE, "label": "8 GB", "label_dy": 12},
        {"vals": get("llc_assoc4", "8gb"), "color": GREY, "label": "control", "hollow": True, "labels": False,
         "w": 2.0, "r": 6, "label_dy": 2},
    ]
    head = ("Does the gain hold with more cores?",
            "L1 + L2 prefetchers together, 50 reads. Higher = faster than no prefetcher.",
            [("line", BLUE, "8 GB database"), ("line", ORANGE, "16 GB database"),
             ("hollow", GREY, "control: 4-way LLC, nothing else")])
    anns = [
        {"i": 1, "v": 24.0, "text": "16 GB: no 4-core run", "anchor": "m"},
        {"i": 0, "v": -1.5, "text": "the control stays near 0, so the gap above it is the prefetchers", "dx": -10},
    ]
    line_chart(c, bg, W, H, cores, series, 28, [0, 7, 14, 21, 28], "Time saved vs no prefetcher (%)",
               "Cores simulated", head, anns, right_pad=170, ymin=-2.8)


# ----------------------------------------------------------------------------- figure 4: reads vs cores
def fig4(c, bg):
    W, H = 1100, 690
    reads = [10, 25, 50]
    series = [
        {"vals": [saved("pf_both", 4, r, "8gb") for r in reads], "color": ORANGE, "label": "4 cores"},
        {"vals": [saved("pf_both", 1, r, "8gb") for r in reads], "color": BLUE, "label": "1 core", "below": (0,)},
    ]
    head = ("Does the gain depend on how many reads we run?",
            "L1 + L2 prefetchers together, 8 GB database. Higher = faster than no prefetcher.",
            [("line", BLUE, "1 core"), ("line", ORANGE, "4 cores")])
    anns = [
        {"i": 1, "v": 8.6, "text": "1 core: the gain shrinks as reads are added", "dx": 34},
        {"i": 0, "v": 16.8, "text": "4 cores: the gain grows", "dx": -10},
    ]
    line_chart(c, bg, W, H, reads, series, 18, [0, 6, 12, 18], "Time saved vs no prefetcher (%)",
               "Reads classified", head, anns, right_pad=190)


render("fig1_organisation_flat", 1100, 730, fig1)
render("fig2_prefetch_depth", 1100, 690, fig2)
render("fig3_gain_vs_cores", 1100, 690, fig3)
render("fig4_reads_vs_cores", 1100, 690, fig4)

print("fig1 LLC max |change|:", max(abs(change(v, 1, 50, "8gb")) for v in
      ("llc_assoc1", "llc_assoc2", "llc_assoc4", "llc_assoc8", "llc_assoc16", "llc_srrip", "llc_random", "llc_nru",
       "llc_nmru", "llc8_plru", "llc8_srrip", "llc_half", "llc_x2", "llc_x4")))
print("fig1 L2 worst:", {v: round(change(v, 1, 50, "8gb"), 2) for v in ("l2_1mb", "l2_random")})
print("fig3 pf_both saved %:", {(db, n): round(saved("pf_both", n, 50, db), 1)
                                  for db in ("8gb", "16gb") for n in (1, 4, 8, 16) if ("pf_both", n, 50, db) in rows})
print("fig4 pf_both saved %:", {(n, r): round(saved("pf_both", n, r, "8gb"), 1) for n in (1, 4) for r in (10, 25, 50)})
print("wrote figures to", OUT)
