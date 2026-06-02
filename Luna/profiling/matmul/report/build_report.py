"""
build_report.py - parse all matmul profiling data and emit graphs + numbers.

Sources:
  WSL2 CPU:  All_Matric_Mul_perf_stats/PERF_REPORT.md (hardcoded in DATA below)
  Luna CPU:  Luna/profiling/matmul/perf_results_luna/{N1024,N2048,N10000,tma}/*.txt
  Luna GPU:  Luna/profiling/matmul_gpu_bundle/timing.log

Outputs:
  Luna/profiling/matmul/report/graphs/*.png
  Luna/profiling/matmul/report/extracted_data.json  (for the report doc)

Indian-style number formatting on Luna (e.g. 1,75,73,24,911) is handled by
stripping all commas before float conversion - works for both styles.
"""

import os, re, json, glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]   # repo root
LUNA_CPU = ROOT / "Luna/profiling/matmul/perf_results_luna"
GPU_LOG  = ROOT / "Luna/profiling/matmul_gpu_bundle/timing.log"
OUT      = Path(__file__).parent / "graphs"
OUT.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------------------
# WSL2 reference numbers - transcribed from All_Matric_Mul_perf_stats/PERF_REPORT.md
# These are the authoritative WSL2 results we already analysed.
# -------------------------------------------------------------------------
WSL2 = {
    "binaries": ["naive_ijk","ikj_order","kij_order","transpose_B","tiled",
                 "omp_parallel","omp_tiled","unrolled_ikj","avx2_manual",
                 "auto_vec_O3","tiled_avx2","prefetch_ikj"],
    "time_ms": {
        1024: [9961, 393, 472, 1717, 425, 460, 579, 415, 324, 389, 335, 961],
        2048: [120536, 3620, 8556, 13774, 3125, 6177, 3878, 4542, 3860, 3645, 2500, 8173],
        10000:[None, 420796, 1177606, 1636624, 298841, 290699, 112506, 535330,
               462351, 423079, 236546, 927112],
    },
    "l3_miss_pct": {
        1024: [22.0, 6.0, 2.2, 1.8, 4.1, 5.9, 3.3, 4.9, 2.3, 6.6, 12.3, 4.2],
        2048: [27.6, 3.5, 4.3, 1.7, 3.7, 1.9, 3.6, 1.5, 2.5, 3.3, 15.9, 2.0],
    },
}

# -------------------------------------------------------------------------
# Luna CPU - parse perf stat _pipe.txt and _stall.txt files
# -------------------------------------------------------------------------
def num(s):
    """Strip commas (handles both Western 1,234 and Indian 1,75,73,24,911)."""
    if s is None: return None
    return float(s.replace(",", "").strip())

def parse_pipe(path):
    """Returns dict of metric -> value from a perf stat pipe output file."""
    if not Path(path).exists(): return None
    txt = Path(path).read_text()
    out = {}
    pats = {
        "task_clock_ms":  r"([\d,\.]+)\s+msec\s+task-clock",
        "cycles":         r"([\d,]+)\s+cycles\s",
        "instructions":   r"([\d,]+)\s+instructions",
        "branches":       r"([\d,]+)\s+branches\s",
        "branch_misses":  r"([\d,]+)\s+branch-misses",
        "cache_refs":     r"([\d,]+)\s+cache-references",
        "cache_misses":   r"([\d,]+)\s+cache-misses",
        "llc_loads":      r"([\d,]+)\s+LLC-loads",
        "llc_load_misses":r"([\d,]+)\s+LLC-load-misses",
        "l1_loads":       r"([\d,]+)\s+L1-dcache-loads",
        "l1_load_misses": r"([\d,]+)\s+L1-dcache-load-misses",
    }
    for k, p in pats.items():
        m = re.search(p, txt)
        if m: out[k] = num(m.group(1))
    if "cycles" in out and "instructions" in out and out["cycles"]:
        out["ipc"] = out["instructions"] / out["cycles"]
    if "llc_loads" in out and "llc_load_misses" in out and out["llc_loads"]:
        out["llc_miss_pct"] = 100.0 * out["llc_load_misses"] / out["llc_loads"]
    if "l1_loads" in out and "l1_load_misses" in out and out["l1_loads"]:
        out["l1_miss_pct"]  = 100.0 * out["l1_load_misses"] / out["l1_loads"]
    return out

def parse_stall(path):
    if not Path(path).exists(): return None
    txt = Path(path).read_text()
    out = {}
    pats = {
        "stalls_total":   r"([\d,]+)\s+cycle_activity\.stalls_total",
        "stalls_l1d":     r"([\d,]+)\s+cycle_activity\.stalls_l1d_miss",
        "stalls_l2":      r"([\d,]+)\s+cycle_activity\.stalls_l2_miss",
        "stalls_l3":      r"([\d,]+)\s+cycle_activity\.stalls_l3_miss",
        "mem_stalls_l3":  r"([\d,]+)\s+memory_activity\.stalls_l3_miss",
    }
    for k, p in pats.items():
        m = re.search(p, txt)
        if m: out[k] = num(m.group(1))
    return out

def parse_tma(path):
    """Pull the TMA percentage breakdown from one tma file."""
    if not Path(path).exists(): return None
    txt = Path(path).read_text()
    out = {}
    pats = {
        "memory_bound":      r"([\d\.]+)\s*%\s*tma_memory_bound",
        "core_bound":        r"([\d\.]+)\s*%\s*tma_core_bound",
        "dram_bound":        r"([\d\.]+)\s*%\s*tma_dram_bound",
        "l3_bound":          r"([\d\.]+)\s*%\s*tma_l3_bound",
        "l2_bound":          r"([\d\.]+)\s*%\s*tma_l2_bound",
        "l1_bound":          r"([\d\.]+)\s*%\s*tma_l1_bound",
        "branch_mispredicts":r"([\d\.]+)\s*%\s*tma_branch_mispredicts",
        "machine_clears":    r"([\d\.]+)\s*%\s*tma_machine_clears",
        "ilp":               r"([\d\.]+)\s*tma_info_core_ilp",
    }
    for k, p in pats.items():
        m = re.search(p, txt)
        if m: out[k] = float(m.group(1))
    return out

LUNA_BINS = ["naive_ijk","ikj_order","kij_order","transpose_B","tiled",
             "omp_parallel","omp_tiled","unrolled_ikj","avx2_manual",
             "auto_vec_O3","tiled_avx2","prefetch_ikj"]

def load_luna_cpu():
    data = {N: {} for N in (1024, 2048, 10000)}
    for N in data:
        for b in LUNA_BINS:
            pipe  = parse_pipe (LUNA_CPU / f"N{N}" / f"{b}_pipe.txt")
            stall = parse_stall(LUNA_CPU / f"N{N}" / f"{b}_stall.txt")
            if pipe is None: continue
            merged = dict(pipe)
            if stall:
                merged.update(stall)
                if "stalls_total" in merged and "cycles" in merged and merged["cycles"]:
                    merged["stall_pct"] = 100.0 * merged["stalls_total"] / merged["cycles"]
            data[N][b] = merged
    # TMA
    data["tma"] = {}
    for f in (LUNA_CPU / "tma").glob("*_tma.txt"):
        key = f.stem.replace("_tma","")
        data["tma"][key] = parse_tma(f)
    return data

# -------------------------------------------------------------------------
# Luna GPU - parse the timing log
# -------------------------------------------------------------------------
def load_gpu():
    out = {}
    if not GPU_LOG.exists(): return out
    cur_N = None
    for line in GPU_LOG.read_text().splitlines():
        m = re.match(r"---\s*N=(\d+)\s*---", line)
        if m:
            cur_N = int(m.group(1))
            out.setdefault(cur_N, {})
            continue
        m = re.match(r"(\S+)\s+N=(\d+)\s+time=\s*([\d\.]+)\s+ms\s+([\d\.]+)\s+GFLOPS", line)
        if m and cur_N == int(m.group(2)):
            out[cur_N][m.group(1)] = {"time_ms": float(m.group(3)),
                                      "gflops":  float(m.group(4))}
    return out

# -------------------------------------------------------------------------
# Plotting
# -------------------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 140, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
    "axes.grid": True, "grid.alpha": 0.25,
})

def bar_compare_walltime(wsl, luna, N, out_path):
    """Side-by-side WSL2 vs Luna wall time per variant."""
    bins = WSL2["binaries"]
    w = WSL2["time_ms"][N]
    l = [luna[N].get(b, {}).get("task_clock_ms") for b in bins]
    x = np.arange(len(bins)); width = 0.4
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - width/2, w, width, label="WSL2 (Ryzen 7 5800H)", color="#cc5555")
    ax.bar(x + width/2, [v if v else 0 for v in l], width,
           label="Luna (Xeon 8468)", color="#3377bb")
    ax.set_yscale("log")
    ax.set_xticks(x); ax.set_xticklabels(bins, rotation=35, ha="right")
    ax.set_ylabel("wall time (ms, log scale)")
    ax.set_title(f"CPU matmul wall time - N={N}  (WSL2 vs Luna)")
    ax.legend()
    fig.savefig(out_path); plt.close(fig)

def bar_tma_stacked(tma, out_path):
    """Stacked bar: memory_bound / core_bound / branch / other for key (bin,N)."""
    keys = ["naive_ijk_N1024","naive_ijk_N2048","tiled_avx2_N1024",
            "tiled_avx2_N2048","tiled_avx2_N10000","omp_tiled_N10000"]
    mem  = [tma[k]["memory_bound"]      for k in keys]
    core = [tma[k]["core_bound"]        for k in keys]
    br   = [tma[k]["branch_mispredicts"]for k in keys]
    mc   = [tma[k]["machine_clears"]    for k in keys]
    other= [max(0, 100 - m - c - b - x) for m,c,b,x in zip(mem,core,br,mc)]
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x, mem,   label="memory_bound", color="#cc4444")
    ax.bar(x, core,  bottom=mem,                     label="core_bound", color="#44aa44")
    bot2 = [a+b for a,b in zip(mem,core)]
    ax.bar(x, br,    bottom=bot2, label="branch_mispredicts", color="#dd9933")
    bot3 = [a+b for a,b in zip(bot2,br)]
    ax.bar(x, mc,    bottom=bot3, label="machine_clears", color="#9966cc")
    bot4 = [a+b for a,b in zip(bot3,mc)]
    ax.bar(x, other, bottom=bot4, label="retiring/other", color="#888888")
    ax.set_xticks(x); ax.set_xticklabels(keys, rotation=25, ha="right")
    ax.set_ylabel("% of pipeline slots")
    ax.set_title("Top-Down Microarchitecture (TMA) breakdown - Luna Sapphire Rapids")
    ax.set_ylim(0, 110); ax.legend(loc="upper right", ncol=3, fontsize=8)
    fig.savefig(out_path); plt.close(fig)

def bar_l3_bound(tma, out_path):
    """Headline: % slots stalled on L3 miss."""
    keys = ["naive_ijk_N1024","naive_ijk_N2048","tiled_avx2_N1024",
            "tiled_avx2_N2048","tiled_avx2_N10000","omp_tiled_N10000"]
    v = [tma[k]["l3_bound"] for k in keys]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = ["#cc3333" if x > 50 else "#cc8833" if x > 10 else "#33aa33" for x in v]
    bars = ax.bar(keys, v, color=colors)
    for bar, val in zip(bars, v):
        ax.text(bar.get_x()+bar.get_width()/2, val+1, f"{val:.1f}%",
                ha="center", fontsize=9)
    ax.set_ylabel("% slots stalled on L3 miss (tma_l3_bound)")
    ax.set_title("L3-bound % - the headline 'DRAM stall' number")
    ax.set_xticklabels(keys, rotation=20, ha="right")
    fig.savefig(out_path); plt.close(fig)

def bar_ilp(tma, out_path):
    """ILP (instructions in flight) - shows pipeline filling up after tiling."""
    keys = ["naive_ijk_N1024","naive_ijk_N2048","tiled_avx2_N1024",
            "tiled_avx2_N2048","tiled_avx2_N10000","omp_tiled_N10000"]
    v = [tma[k]["ilp"] for k in keys]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(keys, v, color="#2266aa")
    for i, val in enumerate(v):
        ax.text(i, val+0.1, f"{val:.2f}", ha="center", fontsize=9)
    ax.set_xticklabels(keys, rotation=20, ha="right")
    ax.set_ylabel("ILP (avg uops in-flight per cycle)")
    ax.set_title("ILP - parallelism unlocked by tiling + vectorisation")
    fig.savefig(out_path); plt.close(fig)

def line_gflops_gpu(gpu, out_path):
    """GFLOPS vs N for every GPU variant - log y."""
    sizes = sorted(gpu.keys())
    bins  = list(gpu[sizes[0]].keys())
    fig, ax = plt.subplots(figsize=(9, 5))
    markers = "ovs^Dxp*"
    for i, b in enumerate(bins):
        ys = [gpu[N].get(b, {}).get("gflops") for N in sizes]
        ax.plot(sizes, ys, marker=markers[i%len(markers)], label=b, linewidth=1.5)
    ax.set_yscale("log"); ax.set_xscale("log")
    ax.set_xlabel("N"); ax.set_ylabel("GFLOPS (log scale)")
    ax.set_title("GPU matmul throughput - NVIDIA L40S")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_xticks(sizes); ax.set_xticklabels([str(n) for n in sizes])
    fig.savefig(out_path); plt.close(fig)

def bar_speedup_vs_cpu(luna_cpu, gpu, out_path):
    """At N=10000, ratio of CPU best vs each GPU variant."""
    N = 10000
    cpu_best = min(v["task_clock_ms"] for v in luna_cpu[N].values()
                   if "task_clock_ms" in v)
    bins = [b for b in gpu[N] if b != "naive_gpu"]
    speedups = [cpu_best / gpu[N][b]["time_ms"] for b in bins]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.barh(bins, speedups, color="#33aa66")
    for bar, val in zip(bars, speedups):
        ax.text(val*1.02, bar.get_y()+bar.get_height()/2,
                f"{val:,.0f}x", va="center", fontsize=9)
    ax.set_xscale("log")
    ax.set_xlabel("speedup factor vs Luna CPU best (omp_tiled), log scale")
    ax.set_title(f"GPU vs CPU at N={N} - speedup factor (Luna CPU best = 1x)")
    fig.savefig(out_path); plt.close(fig)

def bar_walltime_n10000_combined(wsl, luna, gpu, out_path):
    """The cross-platform headline chart - N=10000 wall time, all three."""
    rows = []
    # CPU - WSL2 best
    wsl_best_idx = min(range(len(WSL2["binaries"])),
                       key=lambda i: WSL2["time_ms"][10000][i] or 1e18)
    rows.append(("WSL2 best (omp_tiled)", WSL2["time_ms"][10000][wsl_best_idx], "#aa3333"))
    # CPU - Luna best
    luna_b = min(luna[10000].items(), key=lambda kv: kv[1]["task_clock_ms"])
    rows.append((f"Luna best ({luna_b[0]})", luna_b[1]["task_clock_ms"], "#3366cc"))
    # GPU variants (skip naive at N=10000)
    for b, v in gpu[10000].items():
        rows.append((f"GPU {b}", v["time_ms"], "#33aa66"))
    rows.sort(key=lambda r: r[1], reverse=True)
    labels = [r[0] for r in rows]; vals = [r[1] for r in rows]; cols = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels, vals, color=cols)
    for bar, val in zip(bars, vals):
        ax.text(val*1.05, bar.get_y()+bar.get_height()/2,
                f"{val:,.0f} ms", va="center", fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("wall time (ms, log scale)")
    ax.set_title("Cross-platform matmul wall time at N=10000")
    fig.savefig(out_path); plt.close(fig)

def bar_l3miss_wsl_vs_luna(wsl, luna_cpu, out_path):
    """LLC miss% comparison WSL2 vs Luna at N=1024 and N=2048."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for ax, N in zip(axes, (1024, 2048)):
        bins = WSL2["binaries"]
        w = WSL2["l3_miss_pct"][N]
        l = [luna_cpu[N].get(b, {}).get("llc_miss_pct") for b in bins]
        x = np.arange(len(bins)); width = 0.4
        ax.bar(x - width/2, w, width, label="WSL2", color="#cc5555")
        ax.bar(x + width/2, [v if v is not None else 0 for v in l], width,
               label="Luna", color="#3377bb")
        ax.set_xticks(x); ax.set_xticklabels(bins, rotation=40, ha="right", fontsize=8)
        ax.set_ylabel("LLC miss %"); ax.set_title(f"N={N}")
        ax.legend(fontsize=8)
    fig.suptitle("LLC-load miss % - WSL2 vs Luna")
    fig.savefig(out_path); plt.close(fig)

def bar_ipc_wsl_vs_luna(wsl_ipc, luna_cpu, out_path):
    """IPC: WSL2 (inflated by Hyper-V) vs Luna (true)."""
    # WSL2 IPC from PERF_REPORT.md table 1-A
    wsl_ipc_N1024 = [0.23, 1.15, 1.29, 0.87, 1.50, 1.49, 1.67, 1.59, 1.97, 1.16, 3.04, 3.37]
    bins = WSL2["binaries"]
    luna_ipc = [luna_cpu[1024].get(b, {}).get("ipc") for b in bins]
    x = np.arange(len(bins)); width = 0.4
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - width/2, wsl_ipc_N1024, width, label="WSL2 (inflated by Hyper-V)", color="#cc5555")
    ax.bar(x + width/2, [v if v else 0 for v in luna_ipc], width,
           label="Luna (true)", color="#3377bb")
    ax.set_xticks(x); ax.set_xticklabels(bins, rotation=35, ha="right")
    ax.set_ylabel("IPC (instructions per cycle)")
    ax.set_title("IPC at N=1024 - WSL2 was inflated 4-14x by Hyper-V cycle throttling")
    ax.legend()
    fig.savefig(out_path); plt.close(fig)

def bar_gpu_pct_peak(gpu, out_path):
    """GPU % of peak FP32/TF32 throughput at N=4096."""
    # L40S peak from NVIDIA spec.
    PEAK_FP32 = 91300.0   # GFLOPS (91.3 TFLOPS)
    PEAK_TF32 = 366000.0  # GFLOPS (366 TFLOPS) - sparse 2x doubles this further
    PEAK_FP16 = 733000.0  # GFLOPS (733 TFLOPS with FP16 dense)
    N = 4096
    rows = []
    for b, v in gpu[N].items():
        if "tensor" in b: peak = PEAK_TF32; label = "TF32"
        elif "wmma" in b or "fp16" in b: peak = PEAK_FP16; label = "FP16"
        else: peak = PEAK_FP32; label = "FP32"
        pct = 100 * v["gflops"] / peak
        rows.append((f"{b} ({label})", pct, v["gflops"], peak))
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.barh([r[0] for r in rows], [r[1] for r in rows], color="#5577bb")
    for bar, r in zip(bars, rows):
        ax.text(r[1]+1, bar.get_y()+bar.get_height()/2,
                f"{r[1]:.1f}% ({r[2]/1000:.0f} TFLOPS / {r[3]/1000:.0f} peak)",
                va="center", fontsize=8)
    ax.set_xlabel("% of peak throughput")
    ax.set_xlim(0, max(r[1] for r in rows)*1.4)
    ax.set_title(f"L40S - achieved % of peak throughput at N={N}")
    fig.savefig(out_path); plt.close(fig)

# -------------------------------------------------------------------------
# main
# -------------------------------------------------------------------------
def main():
    print("Loading data...")
    luna_cpu = load_luna_cpu()
    gpu = load_gpu()

    # Print quick correctness check
    print("\n=== Luna CPU sanity check (N=1024) ===")
    for b in LUNA_BINS:
        d = luna_cpu[1024].get(b, {})
        print(f"  {b:15s} time={d.get('task_clock_ms','?'):>10}  "
              f"IPC={d.get('ipc',0):.2f}  "
              f"LLC-miss%={d.get('llc_miss_pct',0):.2f}  "
              f"stall%={d.get('stall_pct',0):.1f}")

    print("\n=== Luna TMA ===")
    for k, v in luna_cpu["tma"].items():
        print(f"  {k}: mem={v.get('memory_bound')} core={v.get('core_bound')} "
              f"L3={v.get('l3_bound')} ILP={v.get('ilp')}")

    print("\n=== GPU timing ===")
    for N in sorted(gpu.keys()):
        for b, v in gpu[N].items():
            print(f"  N={N:<6d} {b:22s} {v['time_ms']:>8.2f} ms  {v['gflops']:>10.1f} GFLOPS")

    print("\nGenerating graphs...")
    bar_compare_walltime(WSL2, luna_cpu, 1024, OUT/"01_walltime_N1024.png")
    bar_compare_walltime(WSL2, luna_cpu, 2048, OUT/"02_walltime_N2048.png")
    bar_ipc_wsl_vs_luna(WSL2, luna_cpu, OUT/"03_ipc_wsl_vs_luna.png")
    bar_l3miss_wsl_vs_luna(WSL2, luna_cpu, OUT/"04_llc_miss_wsl_vs_luna.png")
    bar_tma_stacked(luna_cpu["tma"], OUT/"05_tma_stacked.png")
    bar_l3_bound(luna_cpu["tma"], OUT/"06_l3_bound_headline.png")
    bar_ilp(luna_cpu["tma"], OUT/"07_ilp.png")
    line_gflops_gpu(gpu, OUT/"08_gpu_gflops_scaling.png")
    bar_gpu_pct_peak(gpu, OUT/"09_gpu_pct_peak.png")
    bar_speedup_vs_cpu(luna_cpu, gpu, OUT/"10_gpu_vs_cpu_speedup.png")
    bar_walltime_n10000_combined(WSL2, luna_cpu, gpu, OUT/"11_n10000_crossplatform.png")
    print(f"Wrote graphs to {OUT}")

    # Dump extracted data for the report
    json_out = {
        "luna_cpu_N1024":  {b: luna_cpu[1024].get(b, {}) for b in LUNA_BINS},
        "luna_cpu_N2048":  {b: luna_cpu[2048].get(b, {}) for b in LUNA_BINS},
        "luna_cpu_N10000": {b: luna_cpu[10000].get(b, {}) for b in LUNA_BINS},
        "luna_cpu_tma":    luna_cpu["tma"],
        "gpu_timing":      gpu,
        "wsl2_walltime":   WSL2["time_ms"],
        "wsl2_l3_miss_pct":WSL2["l3_miss_pct"],
    }
    (Path(__file__).parent / "extracted_data.json").write_text(
        json.dumps(json_out, indent=2, default=str))
    print("Wrote extracted_data.json")

if __name__ == "__main__":
    main()
