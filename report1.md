# Profiling Report — Nanopore Pipeline
**Prepared by:** Chirag Kathpalia

---

## System Setup

| Component | Detail |
|---|---|
| OS | Windows 11 Home |
| WSL2 Kernel | 6.6.87.2-microsoft-standard-WSL2 |
| Linux Distro | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Architecture | x86_64 |
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |

## Tools Installed

| Tool | Version |
|---|---|
| Valgrind | 3.22.0 |
| build-essential | 12.10ubuntu1 |
| git | 2.43.0 |
| cmake | 3.28.3 |
| perf | Built from WSL2-Linux-Kernel source (tag linux-msft-wsl-6.6.87.2). Hardware counters work (cycles, instructions, cache-misses, branches). LLC-specific counters (LLC-loads, LLC-load-misses) show `<not supported>` — Hyper-V does not expose them. Per-function LLC data covered by cachegrind. |
