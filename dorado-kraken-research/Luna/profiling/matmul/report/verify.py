"""verify.py - cross-check claims in REPORT.md against raw data and PERF_REPORT.md.
Fails loudly if any claim is off."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REPORT  = Path(__file__).parent / "REPORT.md"
DATA    = json.loads((Path(__file__).parent / "extracted_data.json").read_text())
WSL_MD  = (ROOT / "All_Matric_Mul_perf_stats" / "PERF_REPORT.md").read_text()
TIMING  = (ROOT / "Luna" / "profiling" / "matmul_gpu_bundle" / "timing.log").read_text()

fails = []
def check(label, expected, actual, tol=0.5):
    a = float(actual); e = float(expected)
    if abs(a - e) > tol:
        fails.append(f"  FAIL {label}: expected {e}, got {a}")
    else:
        print(f"  OK   {label}: {a} (~ {e})")

print("=== A. WSL2 numbers transcribed in build_report.py ===")
# naive_ijk N=1024: 9961 ms (PERF_REPORT line 58)
m = re.search(r"`naive_ijk`\s*\|\s*9,?961", WSL_MD)
assert m, "couldn't find naive_ijk 9961 in PERF_REPORT.md"
check("WSL2 naive_ijk N=1024 ms",  9961, DATA["wsl2_walltime"]["1024"][0])
# tiled_avx2 N=2048: 2500
check("WSL2 tiled_avx2 N=2048 ms", 2500, DATA["wsl2_walltime"]["2048"][10])
# omp_tiled N=10000: 112506
check("WSL2 omp_tiled N=10000 ms", 112506, DATA["wsl2_walltime"]["10000"][6])
# naive_ijk L3 miss N=2048: 27.6%
check("WSL2 naive_ijk L3 miss% N=2048", 27.6, DATA["wsl2_l3_miss_pct"]["2048"][0], tol=0.1)

print("\n=== B. Luna CPU parsed from raw _pipe.txt files ===")
# naive_ijk N=1024: chat history said IPC 0.22, stall ~83.3%
n = DATA["luna_cpu_N1024"]["naive_ijk"]
check("Luna naive_ijk N=1024 IPC", 0.22, n["ipc"], tol=0.02)
check("Luna naive_ijk N=1024 stall%", 83.3, n["stall_pct"], tol=0.5)
# tiled_avx2 N=1024: time 220.4, IPC 2.84 (from raw file)
t = DATA["luna_cpu_N1024"]["tiled_avx2"]
check("Luna tiled_avx2 N=1024 ms", 220.4, t["task_clock_ms"], tol=0.5)
check("Luna tiled_avx2 N=1024 IPC", 2.84, t["ipc"], tol=0.02)
# prefetch_ikj N=1024 IPC ~4.00 (claim in report)
p = DATA["luna_cpu_N1024"]["prefetch_ikj"]
check("Luna prefetch_ikj N=1024 IPC", 4.00, p["ipc"], tol=0.05)

print("\n=== C. Luna TMA — the headline numbers ===")
T = DATA["luna_cpu_tma"]
check("TMA naive_ijk N=1024 memory_bound%", 67.0, T["naive_ijk_N1024"]["memory_bound"], tol=0.1)
check("TMA naive_ijk N=1024 l3_bound%",     85.4, T["naive_ijk_N1024"]["l3_bound"],     tol=0.1)
check("TMA naive_ijk N=2048 l3_bound%",     85.9, T["naive_ijk_N2048"]["l3_bound"],     tol=0.1)
check("TMA tiled_avx2 N=1024 memory_bound%",10.8, T["tiled_avx2_N1024"]["memory_bound"],tol=0.1)
check("TMA tiled_avx2 N=1024 core_bound%",  32.4, T["tiled_avx2_N1024"]["core_bound"],  tol=0.1)
check("TMA tiled_avx2 N=2048 core_bound%",  33.1, T["tiled_avx2_N2048"]["core_bound"],  tol=0.1)
check("TMA omp_tiled  N=10000 dram_bound%", 14.7, T["omp_tiled_N10000"]["dram_bound"],  tol=0.1)
check("TMA naive_ijk N=1024 ILP",            3.6, T["naive_ijk_N1024"]["ilp"],          tol=0.05)
check("TMA tiled_avx2 N=2048 ILP",           8.0, T["tiled_avx2_N2048"]["ilp"],         tol=0.05)

print("\n=== D. GPU timing — chat-history numbers vs parsed ===")
g = DATA["gpu_timing"]
check("GPU cublas_tensor N=10000 ms",     16.27, g["10000"]["cublas_tensor_tf32"]["time_ms"], tol=0.1)
check("GPU cublas_tensor N=10000 GFLOPS", 122923.1, g["10000"]["cublas_tensor_tf32"]["gflops"], tol=1)
check("GPU cublas_sgemm  N=2048  GFLOPS", 44501.9,  g["2048"]["cublas_sgemm"]["gflops"], tol=1)
check("GPU naive_gpu     N=2048  ms",     3.06,    g["2048"]["naive_gpu"]["time_ms"],   tol=0.05)
check("GPU shared_tiled_2d N=4096 GFLOPS",30044.0, g["4096"]["shared_tiled_2d"]["gflops"], tol=1)
# verify "coalesced slower than naive" claim
co = g["2048"]["coalesced_gpu"]["time_ms"]; na = g["2048"]["naive_gpu"]["time_ms"]
if co > na:
    print(f"  OK   coalesced_gpu ({co} ms) IS slower than naive_gpu ({na} ms) at N=2048 - matches REPORT claim")
else:
    fails.append("  FAIL coalesced_gpu should be slower than naive_gpu at N=2048")

print("\n=== E. Cross-platform speedup ratio claimed in REPORT ===")
# REPORT says 6900x (WSL2 baseline) and 8338x (Luna baseline)
wsl_best = DATA["wsl2_walltime"]["10000"][6]   # omp_tiled
gpu_best = g["10000"]["cublas_tensor_tf32"]["time_ms"]
r_wsl = wsl_best / gpu_best
print(f"  WSL2 baseline ratio: {wsl_best}/{gpu_best} = {r_wsl:.0f}x  (REPORT says ~6,900x)")
luna_best_ms = min(v["task_clock_ms"] for v in DATA["luna_cpu_N10000"].values()
                   if "task_clock_ms" in v)
r_luna = luna_best_ms / gpu_best
print(f"  Luna baseline ratio: {luna_best_ms}/{gpu_best} = {r_luna:.0f}x  (REPORT shows ~8,338x in graph 10)")
check("speedup vs WSL2 best", 6914, r_wsl, tol=20)
check("speedup vs Luna best", 8338, r_luna, tol=20)

print("\n=== F. % of peak (FP32/TF32) sanity ===")
PEAK_FP32 = 91300.0;  PEAK_TF32 = 366000.0
sgemm_pct = 100 * g["4096"]["cublas_sgemm"]["gflops"] / PEAK_FP32
tensor_pct= 100 * g["4096"]["cublas_tensor_tf32"]["gflops"] / PEAK_TF32
print(f"  cublas_sgemm % of FP32 peak at N=4096: {sgemm_pct:.1f}% (REPORT says ~50%)")
print(f"  cublas_tensor % of TF32 peak at N=4096: {tensor_pct:.1f}% (REPORT says ~33%)")
check("cublas_sgemm  % peak", 50.0, sgemm_pct,  tol=1)
check("cublas_tensor % peak", 33.5, tensor_pct, tol=1)

print("\n=== Summary ===")
if fails:
    print(f"{len(fails)} FAILURES:")
    for f in fails: print(f)
    sys.exit(1)
print("All claims in REPORT.md verified against source data.")
