#!/usr/bin/env python3
"""Five slide-sized (16:9) dot plots: an overview plus LLC, L2, hardware prefetcher, and prefetchers-under-other-conditions.

Dependency: pycairo only.   usage:  python3 dotplot_parts.py ../data/hw_results_all.csv  <outdir>
writes, for each part: <name>.png (3840x2160, 2x), <name>.pdf, <name>.svg (vector 1920x1080).  Pure white background.
Every number is computed from the CSV.  Metric: simulated time saved (%) = (t_base - t_variant) / t_base * 100 with t = Sniper
simulated time of the slowest core; base = the same run with unmodified hardware (for the prefetcher parts: NO prefetcher).
Default condition: 8 GB database, 1 core, 50 reads.  One dot = one simulation run (the overview shows the biggest effect per row).
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
TEAL = rgb("#0F766E")
ORANGE = rgb("#FB923C")
ORANGE_D = rgb("#B45309")
BLUE = rgb("#2F6FED")
BLUE_D = rgb("#1E4FB8")
RED = rgb("#B91C2C")
GREEN_D = rgb("#047857")
BAND = rgb("#D5E8E5")
FONT = "Liberation Sans"
KIND = {"design": (TEAL, TEAL, MUTED), "pf": (ORANGE, ORANGE_D, ORANGE_D), "cond": (BLUE, BLUE_D, BLUE_D)}
KIND_LEGEND = {"design": "cache design: size, ways, replacement policy", "pf": "hardware prefetcher (vs no prefetcher)",
               "cond": "L1 + L2 prefetchers (vs the same run without them)"}

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


# ---- the five parts -----------------------------------------------------------------------------------------------
def rows_llc():
    out = [("h", "Associativity (ways)")]
    out += [("r", l, "design", saved(v)) for l, v in (("1-way (direct-mapped)", "llc_assoc1"), ("2-way", "llc_assoc2"),
                                                       ("4-way", "llc_assoc4"), ("8-way", "llc_assoc8"), ("16-way", "llc_assoc16"))]
    out += [("h", "Replacement policy")]
    out += [("r", l, "design", saved(v)) for l, v in (("SRRIP", "llc_srrip"), ("random", "llc_random"), ("NRU", "llc_nru"),
                                                       ("NMRU", "llc_nmru"), ("PLRU (8-way)", "llc8_plru"), ("SRRIP (8-way)", "llc8_srrip"))]
    out += [("h", "Size")]
    out += [("r", l, "design", saved(v)) for l, v in (("half size", "llc_half"), ("2x size", "llc_x2"), ("4x size", "llc_x4"))]
    return out


def rows_l2():
    out = [("h", "Associativity (ways)")]
    out += [("r", l, "design", saved(v)) for l, v in (("4-way", "l2_assoc4"), ("8-way", "l2_assoc8"), ("32-way", "l2_assoc32"))]
    out += [("h", "Replacement policy")]
    out += [("r", l, "design", saved(v)) for l, v in (("SRRIP", "l2_srrip"), ("random", "l2_random"), ("PLRU (8-way)", "l2_8_plru"))]
    out += [("h", "Size")]
    out += [("r", l, "design", saved(v)) for l, v in (("1 MB (half)", "l2_1mb"), ("4 MB (2x)", "l2_4mb"))]
    return out


def rows_pf():
    out = [("h", "L1 prefetcher (depth = addresses requested per trigger)")]
    out += [("r", l, "pf", saved(v)) for l, v in (("depth 1 (control)", "pf_l1_n1"), ("depth 2", "pf_l1_n2"),
                                                   ("depth 4", "pf_l1_simple"), ("depth 8", "pf_l1_n8"), ("depth 16", "pf_l1_n16"),
                                                   ("depth 4, 32 streams", "pf_l1_f32"))]
    out += [("h", "L2 prefetcher")]
    out += [("r", "depth 8, 64 streams", "pf", saved("pf_l2_simple"))]
    out += [("h", "Both together")]
    out += [("r", "L1 + L2 prefetchers", "pf", saved("pf_both"))]
    return out


def rows_cond():
    out = [("h", "More reads (8 GB, 1 core)")]
    out += [("r", l, "cond", saved("pf_both", reads=n)) for l, n in (("10 reads", 10), ("25 reads", 25), ("50 reads (reference)", 50), ("100 reads", 100))]
    out += [("h", "Bigger database (1 core, 50 reads)")]
    out += [("r", "16 GB database", "cond", saved("pf_both", db="16gb"))]
    out += [("h", "More cores (8 GB, 50 reads)")]
    out += [("r", f"{n} cores", "cond", saved("pf_both", cores=n)) for n in (4, 8, 16)]
    out += [("h", "Bigger database and more cores (50 reads)")]
    out += [("r", f"16 GB + {n} cores", "cond", saved("pf_both", db="16gb", cores=n)) for n in (8, 16)]
    return out


def rows_overview():
    groups = [
        ("LLC associativity (1 to 16 way)", "design", ["llc_assoc1", "llc_assoc2", "llc_assoc4", "llc_assoc8", "llc_assoc16"]),
        ("LLC replacement policy (6)", "design", ["llc_srrip", "llc_random", "llc_nru", "llc_nmru", "llc8_plru", "llc8_srrip"]),
        ("LLC size (half to 4x)", "design", ["llc_half", "llc_x2", "llc_x4"]),
        ("L2 associativity (4 to 32 way)", "design", ["l2_assoc4", "l2_assoc8", "l2_assoc32"]),
        ("L2 replacement policy (3)", "design", ["l2_srrip", "l2_random", "l2_8_plru"]),
        ("L2 size (1 MB and 4 MB)", "design", ["l2_1mb", "l2_4mb"]),
        ("L1 prefetcher (depth 1 to 16)", "pf", ["pf_l1_n1", "pf_l1_n2", "pf_l1_simple", "pf_l1_n8", "pf_l1_n16", "pf_l1_f32"]),
        ("L2 prefetcher", "pf", ["pf_l2_simple"]),
        ("L1 + L2 prefetchers", "pf", ["pf_both"]),
    ]
    out = []
    for label, kind, variants in groups:
        vals = [saved(v) for v in variants]
        out.append(("r", label, kind, max(vals) if kind == "pf" else max(vals, key=abs)))
    return out


PARTS = [
    dict(name="part0_overview", title="Which cache tweaks speed kraken2 up?",
         sub="One dot per row = the biggest effect among the variants tried (8 GB, 1 core, 50 reads). Right of 0 = faster.",
         rows=rows_overview, xr=(-3.0, 6.0), ticks=(-2, 0, 2, 4, 6), kinds=("design", "pf"),
         foot=["Time saved vs the unmodified cache. Cache-design rows are compared with the unmodified cache; prefetcher rows with NO prefetcher."]),
    dict(name="part1_llc", title="LLC (last-level cache): no tweak helps",
         sub="Each dot = one run vs the unmodified LLC (15-way, 2.25 MB per core, LRU). 8 GB, 1 core, 50 reads. Right of 0 = faster.",
         rows=rows_llc, xr=(-3.0, 1.5), ticks=(-3, -2, -1, 0, 1), kinds=("design",),
         foot=["Every LLC change stays within 0.3% of the unmodified cache. In these small runs each cache line is touched about once,",
               "so a bigger or smarter LLC has little to reuse."]),
    dict(name="part2_l2", title="L2 cache: halving it or going random hurts a little",
         sub="Each dot = one run vs the unmodified L2 (16-way, 2 MB, LRU). 8 GB, 1 core, 50 reads. Right of 0 = faster.",
         rows=rows_l2, xr=(-3.0, 1.5), ticks=(-3, -2, -1, 0, 1), kinds=("design",),
         foot=["Same scale as the LLC image. A 1 MB L2 is 2.4% slower and random replacement 1.1% slower; everything else is within noise."]),
    dict(name="part3_prefetcher", title="Hardware prefetcher: faster by 3% to 4% on one core",
         sub="Each dot = one run with a prefetcher vs the SAME run with NO prefetcher. 8 GB, 1 core, 50 reads. Right of 0 = faster.",
         rows=rows_pf, xr=(-1.0, 6.0), ticks=(0, 1, 2, 3, 4, 5, 6), kinds=("pf",),
         foot=["The prefetcher spots a steady step between addresses and fetches the next ones early. Depth counts the address being read,",
               "so depth 1 fetches nothing extra and shows no speed-up (a built-in control)."]),
    dict(name="part4_conditions", title="L1 + L2 prefetchers: bigger gains with more cores",
         sub="Each dot = one run with both prefetchers vs the same condition with NO prefetcher. Right of 0 = faster.",
         rows=rows_cond, xr=(-3.0, 27.0), ticks=(0, 5, 10, 15, 20, 25), kinds=("cond",),
         foot=["On one core the gain shrinks as reads grow (11.9% to 3.1%); on 4 to 16 cores it is 15% to 25%. Reads are small (7.9 K to 164 K bases),",
               "so production-scale gains may differ."]),
]

W, H = 1920, 1080
X0, X1 = 600, 1500
XV = W - 70


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


def dot(c, x, y, fill, outline, r):
    c.new_path()
    c.arc(x, y, r, 0, 2 * math.pi)
    c.set_source_rgb(*fill)
    c.fill_preserve()
    c.set_source_rgb(*outline)
    c.set_line_width(2.0)
    c.stroke()


def draw(c, part):
    rows = part["rows"]()
    xr, ticks = part["xr"], part["ticks"]

    def px(v):
        return X0 + (v - xr[0]) / (xr[1] - xr[0]) * (X1 - X0)

    c.set_source_rgb(*WHITE)
    c.paint()
    text(c, 60, 68, part["title"], 54, INK, bold=True)
    text(c, 60, 126, part["sub"], 27, MUTED)
    x = 60
    for kind in part["kinds"]:
        fill, outline, _ = KIND[kind]
        dot(c, x + 12, 178, fill, outline, 11)
        text(c, x + 34, 178, KIND_LEGEND[kind], 25)
        x += 34 + tw(c, KIND_LEGEND[kind], 25) + 50

    Y0, Y1 = 250, 840
    n_rows = sum(1 for r in rows if r[0] == "r")
    n_hdr = sum(1 for r in rows if r[0] == "h")
    row_h = min(66.0, (Y1 - Y0) / (n_rows + 0.8 * n_hdr))
    hdr_h = 0.8 * row_h if n_hdr else 0
    y1 = Y0 + n_rows * row_h + n_hdr * hdr_h
    fsz = max(22, min(32, row_h * 0.62))
    r_dot = max(8, min(13, row_h * 0.26))

    c.set_source_rgb(*BAND)
    c.rectangle(px(-1), Y0, px(1) - px(-1), y1 - Y0)
    c.fill()
    text(c, px(0), Y0 - 16, "within 1%", 22, MUTED, anchor="m")
    text(c, XV, Y0 - 16, "saved", 22, MUTED, bold=True, anchor="r")
    for t in ticks:
        if t:
            line(c, px(t), Y0, px(t), y1, 1.0, GRID)
    line(c, px(0), Y0, px(0), y1, 2.2, INK)
    y = Y0
    for r in rows:
        if r[0] == "h":
            c.set_source_rgb(*STRIP)
            c.rectangle(40, y, W - 80, hdr_h)
            c.fill()
            text(c, 60, y + hdr_h / 2.0, r[1], max(22, fsz - 3), INK, bold=True)
            y += hdr_h
            continue
        _, label, kind, v = r
        fill, outline, vcol = KIND[kind]
        cy = y + row_h / 2.0
        line(c, 40, y + row_h, W - 40, y + row_h, 1.0, GRID)
        text(c, X0 - 22, cy, label, fsz, INK, anchor="r")
        dot(c, px(v), cy, fill, outline, r_dot)
        s = f"{abs(v):.1f}%" if round(abs(v), 1) == 0 else (("−" if v < 0 else "+") + f"{abs(v):.1f}%")
        col = RED if v < -1.0 else (vcol if v > 1.0 else MUTED)
        text(c, XV, cy, s, fsz, col, bold=abs(v) > 1.0, anchor="r")
        y += row_h
    line(c, X0, y1, X1, y1, 2.2, INK)
    for t in ticks:
        line(c, px(t), y1, px(t), y1 + 9, 2.2, INK)
        text(c, px(t), y1 + 36, ("−" + str(-t)) if t < 0 else str(t), 26, MUTED, anchor="m")
    text(c, X0, y1 + 78, "← slower", 26, RED)
    text(c, X1, y1 + 78, "faster →", 26, GREEN_D, anchor="r")
    text(c, (X0 + X1) / 2.0, y1 + 78, "Time saved (%)", 28, INK, anchor="m")
    for i, s in enumerate(part["foot"]):
        text(c, 60, 1000 + 30 * i, s, 22, MUTED)


for part in PARTS:
    for ext, make in (("pdf", lambda p: cairo.PDFSurface(p, W, H)), ("svg", lambda p: cairo.SVGSurface(p, W, H))):
        surf = make(os.path.join(OUT, f"{part['name']}.{ext}"))
        draw(cairo.Context(surf), part)
        surf.finish()
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W * 2, H * 2)
    ctx = cairo.Context(surf)
    ctx.scale(2, 2)
    draw(ctx, part)
    surf.write_to_png(os.path.join(OUT, f"{part['name']}.png"))
print("wrote", OUT)
