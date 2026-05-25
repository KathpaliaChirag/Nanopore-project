# Index

Master overview of all files in this memory repo.
Update this every time a new major topic is pushed.

---

## Index

**knowledge_base.md** →
- §0 Pipeline overview (POD-5 → Dorado → Kraken-2)
- §1 Nanopore sequencing (physical mechanism, k-mer window, POD-5 format)
- §2 Sample preparation (DNA extraction, Y-adapter, ligation kits)
- §3 Basecalling (Dorado/Guppy/Bonito, CNN+Transformer+CTC pipeline)
- §4 Kraken-2 (k-mer hashing, 180 GB DB, memory-efficiency research)
- §5 ESKAPE pathogens + AMR/MBR clinical context
- §7–9 Dorado installation, POD-5 metadata, GTX 1650 basecalling results
- §8 Kolin sir's caching project (Hot-K-mer LRU cache + Signal-to-Base cache)
- §11 Full Colab pipeline results (fast/hac/sup modes, all 14 barcodes)

**plan.md** →
- [2026-05-18] Full profiling plan: Nsight (Dorado GPU) + gprof + cachegrind + perf (Kraken-2 CPU)
- Phase 0: Setup (WSL2 vs Linux, build Kraken-2 from source with -pg)
- Phase 1: Dorado GPU profiling with Nsight Systems + Nsight Compute
- Phase 2: Kraken-2 CPU profiling (gprof / cachegrind / perf)
- Phase 3: Interpret results (memory-bound vs compute-bound verdict)
- Phase 4: 2-page report structure for Kolin sir (due ~2026-05-25)

**report.md** →
- Phase 1a: Dorado fast model nsys profiling — 186.8s, 27.2M samples/s, compute-bound (beam_search 26%, GEMM 17%, LSTM 23%)
- Phase 1b: Dorado HAC model nsys profiling — 502.0s, 10.1M samples/s, CUTLASS LstmKernel 69.8%, 2.69× slower than fast
- Phase 1c: Dorado optimization analysis — INT8 quantization and beam search rewrite are real targets; cache does not help Dorado
- Phase 1d: CPU vs GPU comparison — 35× speedup, beam_search consistent bottleneck on both
- Phase 1e: CPU vs GPU scaling (200/400/600 MB) — speedup widens 24×→31× with file size
- Phase 1f: Fast model re-profiling (post Ubuntu reinstall, _15.pod5) — 44.95s, 30,275 reads, results confirmed
- Phase 1g: HAC model re-profiling (post Ubuntu reinstall, _15.pod5) — 116.6s, 30,275 reads, LstmKernel 70.0% confirmed
- Phase 2a: Kraken-2 classification + gprof — 93% classified, CompactHashTable::Get() = 80.65% CPU time, memory-bound verdict

**daily_summary.md** →
- 2026-05-20
- 2026-05-21
- 2026-05-22
- 2026-05-25
