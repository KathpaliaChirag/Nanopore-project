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
- (empty — add entries as profiling work is executed)

**report1.md** →
- [2026-05-16] System setup documented: Windows 11 + WSL2, Ryzen 7 5800H, GTX 1650 4GB, Valgrind 3.22.0 installed, perf not available on WSL2 custom kernel

**meeting_minutes.md** →
- Meeting 1: 2026-05-11 (intro — nanopore, Dorado, Kraken-2, ESKAPE)
- Meeting 2: 2026-05-15 (golden dataset, reduced DB, Colab pipeline)
- Meeting 3: 2026-05-18 (Kolin sir — 2 GitHub repos, profiling tools, SIMD/cache blocking)

**summary.md** →
- Quick reference: all 4 pipeline stages with commands
- ESKAPE pathogen table, research goals, hardware constraints, key findings

**updates.md** →
- 2026-05-11, 2026-05-12, 2026-05-13, 2026-05-16, 2026-05-18

**daily_summary.md** →
- 2026-05-20
