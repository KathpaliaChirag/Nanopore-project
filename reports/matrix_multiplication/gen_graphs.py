import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUT = os.path.join(os.path.dirname(__file__), "graphs")
os.makedirs(OUT, exist_ok=True)

BG      = "#1e1e2e"
PANEL   = "#2a2a3e"
TEXT    = "#cdd6f4"
GRID    = "#3a3a5e"
ACCENT  = ["#89b4fa", "#a6e3a1", "#f38ba8", "#fab387", "#cba6f7",
           "#89dceb", "#f9e2af", "#74c7ec", "#b4befe", "#94e2d5",
           "#eba0ac", "#f2cdcd"]

def style_ax(ax, title="", xlabel="", ylabel=""):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6, linestyle="--", zorder=0)
    ax.set_axisbelow(True)
    if title:  ax.set_title(title, color=TEXT, fontsize=11, pad=10)
    if xlabel: ax.set_xlabel(xlabel, color=TEXT, fontsize=9)
    if ylabel: ax.set_ylabel(ylabel, color=TEXT, fontsize=9)

def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"saved {path}")

VARIANTS = [
    "naive_ijk","ikj_order","kij_order","transpose_B","tiled",
    "omp_parallel","omp_tiled","unrolled_ikj","avx2_manual",
    "auto_vec_O3","tiled_avx2","prefetch_ikj"
]
LABELS = [
    "naive","ikj","kij","transpose","tiled",
    "omp","omp+tile","unrolled","AVX2",
    "auto-vec","tile+AVX2","prefetch"
]

# ── WSL2 wall times ─────────────────────────────────────────────────────────
wsl2_1024 = [9961,393,472,1717,425,460,579,415,324,389,335,961]
wsl2_2048 = [120536,3620,8556,13774,3125,6177,3878,4542,3860,3645,2500,8173]
wsl2_10000 = [None,420796,1177606,1636624,298841,290699,112506,535330,462351,423079,236546,927112]

# GRAPH 1 — WSL2 time N=1024 (log scale)
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(LABELS, wsl2_1024, color=ACCENT[:12], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, wsl2_1024):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.12,
            f"{val:,}", ha='center', va='bottom', color=TEXT, fontsize=7.5, fontweight='bold')
ax.set_yscale('log')
style_ax(ax, "WSL2 — execution time, N=1024  (log scale)", "variant", "time (ms)")
ax.tick_params(axis='x', rotation=30)
fig.tight_layout()
save(fig, "01_wsl2_time_1024.png")

# GRAPH 2 — WSL2 time N=2048 (log scale)
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(LABELS, wsl2_2048, color=ACCENT[:12], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, wsl2_2048):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.12,
            f"{val:,}", ha='center', va='bottom', color=TEXT, fontsize=7.5, fontweight='bold')
ax.set_yscale('log')
style_ax(ax, "WSL2 — execution time, N=2048  (log scale)", "variant", "time (ms)")
ax.tick_params(axis='x', rotation=30)
fig.tight_layout()
save(fig, "02_wsl2_time_2048.png")

# GRAPH 3 — WSL2 time N=10000 (no naive, log scale)
labels_10k = LABELS[1:]
vals_10k   = [v for v in wsl2_10000 if v is not None]
colors_10k = ACCENT[1:12]
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(labels_10k, vals_10k, color=colors_10k, edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, vals_10k):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.12,
            f"{val:,}", ha='center', va='bottom', color=TEXT, fontsize=7.5, fontweight='bold')
ax.set_yscale('log')
style_ax(ax, "WSL2 — execution time, N=10000  (log scale, naive skipped)", "variant", "time (ms)")
ax.tick_params(axis='x', rotation=30)
fig.tight_layout()
save(fig, "03_wsl2_time_10000.png")

# ── Luna IPC N=1024 ──────────────────────────────────────────────────────────
luna_ipc = [0.220,0.810,0.986,1.288,1.419,1.170,1.316,1.189,1.142,0.835,2.838,4.001]
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(LABELS, luna_ipc, color=ACCENT[:12], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, luna_ipc):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.04,
            f"{val:.2f}", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
ax.axhline(1.0, color="#f38ba8", linewidth=1.2, linestyle="--", zorder=4, label="IPC = 1.0")
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
style_ax(ax, "Luna CPU — IPC at N=1024  (accurate hardware counters)", "variant", "instructions per cycle")
ax.tick_params(axis='x', rotation=30)
fig.tight_layout()
save(fig, "04_luna_ipc_1024.png")

# ── Luna L1 + LLC miss rates N=1024 ─────────────────────────────────────────
luna_l1_miss = [48.87,15.81,9.17,0.23,25.68,10.76,19.86,9.10,10.84,16.06,13.08,0.65]
luna_llc_miss = [0.022,0.074,0.295,3.997,0.960,0.395,16.36,0.092,0.019,0.282,4.965,1.581]

x = np.arange(len(LABELS))
w = 0.38
fig, ax = plt.subplots(figsize=(13, 5), facecolor=BG)
b1 = ax.bar(x - w/2, luna_l1_miss, w, label="L1 miss %", color=ACCENT[0], edgecolor=BG, linewidth=0.5, zorder=3)
b2 = ax.bar(x + w/2, luna_llc_miss, w, label="LLC miss %", color=ACCENT[2], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(b1, luna_l1_miss):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.4,
            f"{val:.1f}", ha='center', va='bottom', color=TEXT, fontsize=7, fontweight='bold')
for bar, val in zip(b2, luna_llc_miss):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.4,
            f"{val:.2f}", ha='center', va='bottom', color=TEXT, fontsize=7, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(LABELS, rotation=30, ha='right')
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=9)
style_ax(ax, "Luna CPU — L1 and LLC miss rates at N=1024", "variant", "miss rate (%)")
fig.tight_layout()
save(fig, "05_luna_miss_rates_1024.png")

# ── Luna stall % N=1024 ─────────────────────────────────────────────────────
luna_stall = [83.34,44.56,41.68,17.22,29.02,32.06,37.31,33.02,35.83,46.86,13.47,6.84]
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(LABELS, luna_stall, color=ACCENT[:12], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, luna_stall):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
            f"{val:.1f}%", ha='center', va='bottom', color=TEXT, fontsize=7.5, fontweight='bold')
ax.axhline(50, color="#f38ba8", linewidth=1.2, linestyle="--", zorder=4, label="50% stall line")
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
style_ax(ax, "Luna CPU — stall % of total cycles at N=1024", "variant", "stalled cycles (%)")
ax.tick_params(axis='x', rotation=30)
fig.tight_layout()
save(fig, "06_luna_stall_pct_1024.png")

# ── TMA breakdown ─────────────────────────────────────────────────────────
tma_labels  = ["naive\nN=1024","naive\nN=2048","tiled+AVX2\nN=1024","tiled+AVX2\nN=2048","tiled+AVX2\nN=10000","omp+tile\nN=10000"]
mem_bound   = [67.0, 54.7, 10.8, 20.9, 39.1, 30.6]
core_bound  = [16.5, 20.8, 32.4, 33.1, 17.1, 25.9]
dram_bound  = [0.1,  0.3,  0.2,  0.3,  2.3,  14.7]
l3_bound    = [85.4, 85.9, 1.0,  0.8,  1.4,  4.5]

x = np.arange(len(tma_labels))
w = 0.2
fig, ax = plt.subplots(figsize=(13, 5), facecolor=BG)
ax.bar(x - 1.5*w, mem_bound,  w, label="memory bound %",  color=ACCENT[0], edgecolor=BG, linewidth=0.4, zorder=3)
ax.bar(x - 0.5*w, core_bound, w, label="core bound %",    color=ACCENT[1], edgecolor=BG, linewidth=0.4, zorder=3)
ax.bar(x + 0.5*w, dram_bound, w, label="DRAM bound %",    color=ACCENT[2], edgecolor=BG, linewidth=0.4, zorder=3)
ax.bar(x + 1.5*w, l3_bound,   w, label="L3 bound %",      color=ACCENT[3], edgecolor=BG, linewidth=0.4, zorder=3)
for i, (mb, cb, db, lb) in enumerate(zip(mem_bound, core_bound, dram_bound, l3_bound)):
    for off, val, col in [(-1.5*w,mb,ACCENT[0]),(-0.5*w,cb,ACCENT[1]),(0.5*w,db,ACCENT[2]),(1.5*w,lb,ACCENT[3])]:
        ax.text(x[i]+off, val+0.5, f"{val:.1f}", ha='center', va='bottom', color=TEXT, fontsize=7, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(tma_labels, fontsize=8)
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8, loc='upper right')
style_ax(ax, "Luna CPU — TMA (top-down microarchitecture analysis) breakdown", "configuration", "% of pipeline slots")
fig.tight_layout()
save(fig, "07_tma_breakdown.png")

# ── GPU GFLOPS N=10000 ───────────────────────────────────────────────────────
gpu_labels = ["naive\n(GPU)","coalesced","shared\ntiled","shared\ntiled 2D","cuBLAS\nsgemm","cuBLAS\ntensor TF32","WMMA\nFP16"]
gpu_gflops_10k = [None, 384.0, 5915.3, 29398.9, 44475.3, 122923.1, 50000.9]
# naive_gpu skipped at N=10000 in data (no entry), fill with N=4096 projected or omit
gpu_labels_10k = gpu_labels[1:]
gpu_vals_10k   = gpu_gflops_10k[1:]
gpu_colors     = ACCENT[1:7]

fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG)
bars = ax.bar(gpu_labels_10k, gpu_vals_10k, color=gpu_colors, edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, gpu_vals_10k):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+500,
            f"{val:,.0f}", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
ax.axhline(88000, color="#cba6f7", linewidth=1.2, linestyle="--", zorder=4, label="L40S FP32 peak ~88 TFLOPS")
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
style_ax(ax, "GPU (L40S) — GFLOPS at N=10000", "kernel", "GFLOPS")
fig.tight_layout()
save(fig, "08_gpu_gflops_10000.png")

# ── Cross-size scaling (selected variants) ──────────────────────────────────
scale_labels = ["ikj","tiled","omp+tile","tile+AVX2","prefetch"]
scale_1024   = [393,   425,   579,       335,         961]
scale_2048   = [3620,  3125,  3878,      2500,        8173]
expected_8x  = [v*8 for v in scale_1024]

x = np.arange(len(scale_labels))
w = 0.28
fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG)
ax.bar(x - w,   scale_1024,  w, label="N=1024", color=ACCENT[0], edgecolor=BG, linewidth=0.4, zorder=3)
ax.bar(x,        scale_2048,  w, label="N=2048 (actual)", color=ACCENT[1], edgecolor=BG, linewidth=0.4, zorder=3)
ax.bar(x + w,   expected_8x, w, label="N=2048 (ideal 8×)", color=ACCENT[2], alpha=0.55, edgecolor=BG, linewidth=0.4, zorder=3)
for i, (a, b, e) in enumerate(zip(scale_1024, scale_2048, expected_8x)):
    ax.text(x[i]-w,   a+50,  f"{a:,}",  ha='center', va='bottom', color=TEXT, fontsize=7)
    ax.text(x[i],     b+50,  f"{b:,}",  ha='center', va='bottom', color=TEXT, fontsize=7)
    ax.text(x[i]+w,   e+50,  f"{e:,}",  ha='center', va='bottom', color=TEXT, fontsize=7, alpha=0.7)
ax.set_xticks(x); ax.set_xticklabels(scale_labels)
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
style_ax(ax, "scaling N=1024 → N=2048 vs ideal 8× (WSL2, ms)", "variant", "time (ms)")
fig.tight_layout()
save(fig, "09_scaling_1024_2048.png")

# ── Luna time N=1024 bar ─────────────────────────────────────────────────────
luna_time_1024 = [5703.91,333.65,400.89,717.4,267.05,352.21,426.59,352.05,330.22,321.8,220.4,501.4]
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(LABELS, luna_time_1024, color=ACCENT[:12], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, luna_time_1024):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()*1.06,
            f"{val:.0f}", ha='center', va='bottom', color=TEXT, fontsize=7.5, fontweight='bold')
ax.set_yscale('log')
style_ax(ax, "Luna CPU — execution time at N=1024, ms  (log scale)", "variant", "time (ms)")
ax.tick_params(axis='x', rotation=30)
fig.tight_layout()
save(fig, "10_luna_time_1024.png")

# ── Luna N=10000 wall time ────────────────────────────────────────────────────
luna_10k_labels = ["ikj","kij","transpose","tiled","omp","omp+tile","unrolled","AVX2","auto-vec","tile+AVX2","prefetch"]
luna_10k_vals   = [552098, 660594, 799485, 135663, 883941, 256721, 634317, 629533, 553386, 168350, 884051]
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
bars = ax.bar(luna_10k_labels, luna_10k_vals, color=ACCENT[1:12], edgecolor=BG, linewidth=0.5, zorder=3)
for bar, val in zip(bars, luna_10k_vals):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()*1.08,
            f"{val//1000}s", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
ax.set_yscale('log')
style_ax(ax, "Luna CPU — execution time, N=10000  (log scale, naive skipped)", "variant", "time (ms)")
ax.tick_params(axis='x', rotation=30)
ax.annotate("tiled wins\non bare metal", xy=(3, 135663), xytext=(4.5, 100000),
            arrowprops=dict(arrowstyle='->', color=ACCENT[2], lw=1.5),
            color=ACCENT[2], fontsize=8, fontweight='bold')
fig.tight_layout()
save(fig, "11_luna_time_10000.png")

# ── Platform flip graph: WSL2 vs Luna at N=10000 ─────────────────────────────
flip_labels = ["ikj", "tiled", "omp+tile", "tile+AVX2"]
wsl2_flip   = [420796, 298841, 112506,  236546]
luna_flip   = [552098, 135663, 256721,  168350]

x = np.arange(len(flip_labels))
w = 0.35
fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
b1 = ax.bar(x - w/2, wsl2_flip, w, label="WSL2 (AMD Ryzen 7 5800H)", color=ACCENT[0], edgecolor=BG, linewidth=0.4, zorder=3)
b2 = ax.bar(x + w/2, luna_flip, w, label="Luna (Xeon Platinum 8468, bare metal)", color=ACCENT[1], edgecolor=BG, linewidth=0.4, zorder=3)
for bar, val in zip(b1, wsl2_flip):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+4000,
            f"{val//1000}s", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
for bar, val in zip(b2, luna_flip):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+4000,
            f"{val//1000}s", ha='center', va='bottom', color=TEXT, fontsize=8, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(flip_labels)
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
style_ax(ax, "WSL2 vs Luna: N=10000 wall time (ms) — winner flips between platforms", "variant", "time (ms)")
ax.annotate("WSL2 winner", xy=(2-w/2, 112506), xytext=(0.5, 50000),
            arrowprops=dict(arrowstyle='->', color=ACCENT[0], lw=1.5),
            color=ACCENT[0], fontsize=8, fontweight='bold')
ax.annotate("Luna winner", xy=(1+w/2, 135663), xytext=(2.5, 60000),
            arrowprops=dict(arrowstyle='->', color=ACCENT[1], lw=1.5),
            color=ACCENT[1], fontsize=8, fontweight='bold')
fig.tight_layout()
save(fig, "12_platform_flip_10000.png")

# ── IPC trend across N (Luna) ─────────────────────────────────────────────────
ipc_variants = ["tiled_avx2", "prefetch", "tiled", "ikj"]
ipc_colors   = [ACCENT[10], ACCENT[11], ACCENT[4], ACCENT[1]]
# IPC values from extracted_data.json
ipc_data = {
    "tiled_avx2": [2.838, 2.937, 3.202],
    "prefetch":   [4.001, 4.045, 1.990],
    "tiled":      [1.419, 1.383, 2.221],
    "ikj":        [0.810, 0.769, 0.360],
}
sizes = ["N=1024", "N=2048", "N=10000"]
x = np.arange(len(sizes))
w = 0.2
fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
for i, (label, color) in enumerate(zip(ipc_variants, ipc_colors)):
    vals = ipc_data[label]
    offset = (i - 1.5) * w
    bars = ax.bar(x + offset, vals, w, label=label, color=color, edgecolor=BG, linewidth=0.4, zorder=3)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.04,
                f"{val:.2f}", ha='center', va='bottom', color=TEXT, fontsize=7, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(sizes)
ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
ax.axhline(1.0, color="#f38ba8", linewidth=1.0, linestyle="--", zorder=4, alpha=0.6)
style_ax(ax, "Luna CPU — IPC trend across matrix sizes", "matrix size", "IPC")
fig.tight_layout()
save(fig, "13_ipc_trend_across_sizes.png")

print("all graphs generated.")
