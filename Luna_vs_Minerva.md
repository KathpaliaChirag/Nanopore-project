# Luna vs Minerva — Full Comparison

> Luna: dell-R760 | Minerva: minerva
> Both: Ubuntu 22.04 LTS, CUDA 12.9, Driver 575.64.03
> Audited: 2026-05-28

---

## CPU

| Property | Minerva | Luna | Winner |
|---|---|---|---|
| Model | Xeon Gold 6330 | **Xeon Platinum 8468** | Luna |
| Microarchitecture | Ice Lake (2021) | **Sapphire Rapids (2023)** | Luna |
| Sockets | 2 | 2 | Tie |
| Cores per socket | 28 | **48** | Luna |
| Total physical cores | 56 | **96** | Luna (+71%) |
| Total logical CPUs | 112 | **192** | Luna |
| Base clock | 2.00 GHz | **3.80 GHz** | Luna (+90%) |
| Max turbo | ~3.9 GHz | **~3.8 GHz** | Tie |
| SIMD | AVX-512 | **AVX-512 + AMX** | Luna |
| AMX (tile matrix multiply) | No | **Yes** | Luna only |
| AVX-512 width | 512-bit | **512-bit** | Tie |
| FP64 SIMD throughput | 4 doubles/instr | **8 doubles/instr (ZMM)** | Luna (same — both 512-bit) |

> **AMX** (Advanced Matrix Extensions) on Luna's Sapphire Rapids is a hardware tile multiply unit — can multiply 16×64 × 64×16 BF16 matrices in a single instruction. Only available on Xeon Platinum 8468 and newer.

---

## Cache Hierarchy

| Level | Minerva | Luna | Winner |
|---|---|---|---|
| L1d per core | 48 KB | 48 KB | Tie |
| L1i per core | 32 KB | 32 KB | Tie |
| L2 per core | **1 MB** | **2 MB** | Luna (2×) |
| L3 total | ~66 MB (2 × ~33 MB) | **210 MB (2 × 105 MB)** | Luna (3.2×) |

> **Impact on workloads:**
> - N=1024 matmul (24 MB): fits in Luna's L3 (210 MB), overflows Minerva's L3 (66 MB)
> - N=2048 matmul (96 MB): fits in Luna's L3, far exceeds Minerva's
> - Kraken-2 8 GB DB: neither L3 holds it — both DRAM-bound, but Luna's 3.8 GHz helps
> - Luna's larger L3 means IPC will be higher and stall-BE% will be lower for the same workloads

---

## RAM

| Property | Minerva | Luna | Winner |
|---|---|---|---|
| Total RAM | 251 GB | **503 GB** | Luna (2×) |
| Available (idle) | ~219 GB | **~451 GB** | Luna |
| Swap | 59 GB | 59 GB | Tie |
| Kraken-2 standard DB (180 GB) | Fits with ~39 GB margin | **Fits with ~271 GB margin** | Luna |
| Kraken-2 + OS + other jobs | Tight | **Comfortable** | Luna |

---

## GPU

| Property | Minerva | Luna | Winner |
|---|---|---|---|
| Model | 2× NVIDIA A40 | **2× NVIDIA L40S** | Luna |
| Architecture | Ampere (2020) | **Ada Lovelace (2022)** | Luna |
| VRAM per card | 46 GB GDDR6 | 46 GB GDDR6 | Tie |
| Total VRAM | ~90 GB | **~92 GB** | Tie |
| FP32 throughput per card | ~37.4 TFLOPS | **~91.6 TFLOPS** | Luna (**2.5×**) |
| FP16 throughput per card | ~74.8 TFLOPS | **~183 TFLOPS** | Luna (2.5×) |
| BF16 throughput per card | ~74.8 TFLOPS | **~183 TFLOPS** | Luna (2.5×) |
| Power cap per card | 300W | 350W | — |
| CUDA version | 12.9 | 12.9 | Tie |
| Driver | 575.64.03 | 575.64.03 | Tie |

> **For Dorado basecalling:** Dorado is dominated by GEMM (82%+ GPU time). L40S at ~2.5× more FP32 means Dorado fast/hac model should run ~2–2.5× faster on Luna per card.

---

## Storage

| Property | Minerva | Luna | Winner |
|---|---|---|---|
| Root disk size | 3.4 TB | 938 GB | Minerva |
| Root disk used | 3.2 TB | 655 GB | — |
| Root disk free | **9.1 GB (CRITICAL — 100%)** | **236 GB (74%)** | Luna |
| /dev/shm (tmpfs) | 126 GB | **252 GB** | Luna |
| Risk level |  Full — jobs may fail |  Fine | Luna |

> Minerva root disk is critically full (100%). Luna has 236 GB free — comfortable for benchmarks, datasets, and build artifacts.

---

## OS and Kernel

| Property | Minerva | Luna |
|---|---|---|
| OS | Ubuntu 22.04.4 LTS | Ubuntu 22.04 LTS |
| Kernel | 6.8.0-65-generic | **6.8.0-78-generic** (newer) |
| Architecture | x86_64 | x86_64 |

---

## Profiling Readiness

| Tool / Setting | Minerva | Luna |
|---|---|---|
| `perf` binary |  `/usr/bin/perf` |  `/usr/bin/perf` |
| `perf_event_paranoid` |  1 (fixed) |  **1 (confirmed 2026-05-28)** |
| Hardware counters (LLC, stall-BE, TMA) |  Works |  Works |
| TMA (Top-down Analysis) |  Ice Lake TMAM |  **Sapphire Rapids TMAM** (newer, more metrics) |
| `gcc` / `g++` |  11.4.0 |  11.4.0 |
| `nsys` (Nsight Systems) |  PATH fixed → `/usr/lib/nsight-systems/bin/nsys` |  Not in PATH (may be installed — needs `find`) |
| `ncu` (Nsight Compute) |  2021.3.1.0 |  Not in PATH |
| `nvcc` (CUDA compiler) | Unknown |  Not in PATH |
| `valgrind` | Available via conda |  Not installed |
| `numactl` | Unknown |  Not installed |
| `likwid` | Not installed |  Not installed |
| `btop` | Not documented |  Installed |

> Luna hardware counters are ready. GPU profiling tools (nsys, ncu) still need PATH fix or install — same situation as Minerva before the nsys fix.

---

## Users and Access

| Property | Minerva | Luna |
|---|---|---|
| Admin account | chayanika | chayanika |
| Our account | CK | CK (to be set up) |
| Users on system | 15 users | chayanika (+ student to be created) |
| Disk competition | Heavy (multiple TB users) | Light (mostly empty) |

---

## Benchmark Results (Matmul, WSL2 → to be re-run on both)

| Metric | WSL2 | Expected on Minerva | Expected on Luna |
|---|---|---|---|
| IPC (naive_ijk) | 0.23† (wrong) | ~0.3–0.5 | ~0.3–0.5 |
| IPC (tiled_avx2) | 3.04† (wrong) | ~3–5 | **~4–7** (higher clock + L3) |
| LLC-load-misses | Not supported |  |  |
| stalled-cycles-backend | Not supported |  |  |
| N=1024 naive_ijk time | 9,961ms | ~6,000ms | **~2,000ms** (3.8 GHz + L3 fits) |
| N=1024 tiled_avx2 time | 335ms | ~200ms | **~80ms** (higher clock + AVX-512 wider use) |

---

## Verdict

### Luna wins on every hardware dimension:

| Dimension | Winner | Margin |
|---|---|---|
| CPU compute (single-thread) | **Luna** | 3.8 vs 2.0 GHz = 1.9× clock |
| CPU compute (multi-thread) | **Luna** | 192 vs 112 logical CPUs = 1.7× |
| Cache (L2) | **Luna** | 2× per core |
| Cache (L3) | **Luna** | 3.2× total |
| RAM | **Luna** | 2× |
| GPU compute | **Luna** | 2.5× FP32 per card |
| Disk health | **Luna** | 236 GB free vs 9 GB (critical) |
| Matrix multiply (AMX) | **Luna only** | Hardware tile unit not on Minerva |

### Minerva's only current advantages:

| Advantage | Notes |
|---|---|
| nsys / ncu in PATH | Already fixed on Minerva; Luna needs same fix |
| More disk space (total) | 3.4 TB vs 938 GB — but Minerva is full, Luna has 236 GB free |

### Use each for:

| Task | Use | Why |
|---|---|---|
| Kraken-2 CPU profiling | **Luna** | 3.8 GHz + 210 MB L3 — accurate IPC, TMA metrics |
| Dorado GPU basecalling | **Luna** | L40S 2.5× faster than A40 per card |
| Matrix multiply benchmarks | **Luna** | AVX-512 + AMX + larger L3 changes the story |
| NUMA experiments | **Luna** | 2-socket, 503 GB, numactl available after install |
| Anything right now | **Luna** | Disk is healthy; Minerva is at 100% — risky |

**Bottom line: Luna is the better machine in every meaningful way for this project. Run all future benchmarks on Luna.**
