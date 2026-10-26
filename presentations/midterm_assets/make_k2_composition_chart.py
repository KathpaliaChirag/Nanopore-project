# -*- coding: utf-8 -*-
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DB_ORDER = ["sample_targeted", "standard_8gb", "standard_16gb", "pluspf_103gb"]
DB_LABELS = {
    "sample_targeted": "50 MB",
    "standard_8gb": "7.6 GB",
    "standard_16gb": "15 GB",
    "pluspf_103gb": "103 GB",
}

with open("k2_perf_raw.txt", "r", encoding="utf-8") as f:
    raw = f.read()

blocks = re.split(r"#+ (\w[\w_]*) #+", raw)
# blocks[0] is empty/preamble, then alternating (name, content)
data = {}
for i in range(1, len(blocks), 2):
    name = blocks[i].strip()
    content = blocks[i + 1]
    rows = []
    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([\d.]+)%\s+(.+)$", line)
        if not m:
            continue
        pct = float(m.group(1))
        sym = m.group(2).strip()
        rows.append((pct, sym))
    data[name] = rows


def categorize(sym):
    if sym.startswith("0xffffffff"):
        return "Kernel (page faults / TLB)"
    if sym.startswith("0x0000"):
        return "Other / unresolved"
    if "CompactHashTable::Get" in sym:
        return "Hash-table lookup"
    if "MinimizerScanner" in sym or "murmurhash3" in sym:
        return "Minimizer scan"
    if any(k in sym for k in ["ClassifySequence", "AddHitlistString", "_Map_base",
                                "HyperLogLogPlusMinus", "getRank", "IsAAncestorOfB",
                                "_Rb_tree"]):
        return "Classify bookkeeping"
    if any(k in sym for k in ["ks_getuntil2", "memmove", "streambuf", "ostream",
                                "ostreambuf_iterator", "num_put", "locale"]):
        return "I/O & report writing"
    if any(k in sym for k in ["malloc", "free", "cfree", "unlink_chunk"]):
        return "Allocator"
    return "Other / unresolved"


CATS = ["Hash-table lookup", "Minimizer scan", "Classify bookkeeping",
        "I/O & report writing", "Kernel (page faults / TLB)", "Allocator", "Other / unresolved"]

totals = {db: {c: 0.0 for c in CATS} for db in DB_ORDER}
for db in DB_ORDER:
    for pct, sym in data[db]:
        cat = categorize(sym)
        totals[db][cat] += pct

# fold anything under 0.1% cumulative tail (perf's percent-limit already cut most)
# normalize each row to sum to 100 (accounts for the <0.1% tail perf dropped)
for db in DB_ORDER:
    s = sum(totals[db].values())
    if s > 0:
        rest = 100.0 - s
        totals[db]["Other / unresolved"] += rest

print("Category breakdown (%):")
for db in DB_ORDER:
    print(f"\n{db}:")
    for c in CATS:
        print(f"  {c}: {totals[db][c]:.2f}")
    print(f"  TOTAL: {sum(totals[db].values()):.2f}")

# ---------- build the stacked horizontal bar, Dorado-figure style ----------
COLORS = {
    "Hash-table lookup": "#a13a2c",
    "Minimizer scan": "#1f5c52",
    "Classify bookkeeping": "#c9932f",
    "I/O & report writing": "#7a5fa0",
    "Kernel (page faults / TLB)": "#3a6ea5",
    "Allocator": "#9aa1ac",
    "Other / unresolved": "#d8dbe0",
}

fig, ax = plt.subplots(figsize=(9.6, 3.4), dpi=260)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

y_pos = np.arange(len(DB_ORDER))
left = np.zeros(len(DB_ORDER))
for cat in CATS:
    vals = np.array([totals[db][cat] for db in DB_ORDER])
    bars = ax.barh(y_pos, vals, left=left, color=COLORS[cat], height=0.6,
                    edgecolor="white", linewidth=0.6, label=cat, zorder=3)
    for i, v in enumerate(vals):
        if v >= 4:
            ax.text(left[i] + v / 2, y_pos[i], f"{v:.0f}", ha="center", va="center",
                     fontsize=8.5, fontweight="bold", color="white", zorder=4)
    left += vals

ax.set_yticks(y_pos)
ax.set_yticklabels([f"{DB_LABELS[db]}" for db in DB_ORDER], fontsize=10, fontweight="bold", color="#15181f")
ax.set_xlim(0, 100)
ax.set_xticks(range(0, 101, 10))
ax.set_xlabel("share of CPU cycle samples (%)", fontsize=9.5, color="#15181f", fontweight="bold")
ax.invert_yaxis()
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#15181f")
ax.tick_params(axis="x", labelsize=8, colors="#5c6572")
ax.grid(axis="x", color="#e6e8ed", linewidth=0.6, zorder=0)

ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=4, fontsize=8, frameon=False)
fig.suptitle("Kraken2 CPU cycle composition per database size (Luna, 32T, 104,918 reads)",
             fontsize=11, color="#15181f", fontweight="bold", y=1.02)
fig.tight_layout(pad=0.8)
fig.savefig("k2_composition.png", facecolor="white", bbox_inches="tight", pad_inches=0.12)
plt.close(fig)
print("\nsaved k2_composition.png")
