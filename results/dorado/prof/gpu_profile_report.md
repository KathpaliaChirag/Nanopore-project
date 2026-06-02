# Dorado GPU Profiling Report

**Date:** 2026-06-02  
**Input:** `FBE01990_24778b97_03e50f91_7.pod5` (4 GB)  
**GPU:** NVIDIA RTX 4050 Laptop — 6141 MB VRAM, 60W TDP  
**Dorado:** v1.4.0  
**Models:** `dna_r10.4.1_e8.2_400bps_fast@v5.2.0`, `dna_r10.4.1_e8.2_400bps_hac@v5.2.0`

---

## Results

| Metric | Fast | HAC |
|---|---|---|
| Runtime | 118s | 293s |
| Throughput | ~33.9 MB/s | ~13.7 MB/s |
| SM avg (CUDA cores) | **97.6%** | **99.5%** |
| SM max | 100% | 100% |
| Mem BW avg | 84.7% | 32.4% |
| Mem BW max | 100% | 52% |
| VRAM avg used | 3243 MB (52%) | 3578 MB (58%) |
| VRAM max used | 3471 MB (56%) | 3633 MB (59%) |

---

## Interpretation

### Fast model — compute + memory bound
- SM at 97.6% and Mem BW at 84.7% — both high simultaneously.
- The fast model has a small network, so weights need to be reloaded from VRAM frequently → drives memory bandwidth up.
- GPU is fully saturated with no idle periods.

### HAC model — purely compute bound
- SM at 99.5% (maxed) but Mem BW only 32.4%.
- Classic signature of a large neural network with high arithmetic intensity: model weights sit in VRAM and are reused for many FLOPs per byte loaded.
- Low Mem BW here is **not a problem** — it means the model is working efficiently, doing more math per memory access.
- HAC is 2.5× slower than fast (293s vs 118s), consistent with a much larger model.

### No CPU/disk bottleneck
- A CPU or I/O bottleneck shows up as SM dropping to 30–50% between batches with spikes to 100%.
- Both runs show flat 97–99% SM throughout — the GPU was never starved for data.

### VRAM headroom
- Fast uses up to 3.5 GB (56% of 6 GB).
- HAC uses up to 3.6 GB (59% of 6 GB).
- ~2.5 GB headroom remains — safe margin if adding `--modified-bases` or increasing `--batchsize`.

---

## Verdict

**The GPU is fully saturated in both modes.** There is no software tuning (batchsize, threads, I/O) that will meaningfully improve throughput. The bottleneck is raw GPU compute capacity. To go faster, a more powerful GPU (e.g., RTX 4080/4090 or A100) would be required.
