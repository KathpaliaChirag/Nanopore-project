# Nanopore Project — Updates Log

Chronological journal of what we covered each session.

---

## 2026-05-11 — 1st mentor meeting (3–5 pm)

Topics introduced briefly by **mam**:
1. Nanopore sequencing — physical mechanism, device structure, k-mer window, signal/squiggle, POD-5
2. Sample prep pipeline — DNA prep, adaptor ligation, MinION/PromethION, AMR/MBR terms
3. Basecalling tools — Dorado, Guppy, Bonito; neural inference on squiggles; signal compression (VQ, Shannon, Euclidean)
4. Kraken-2 — k-mer hashing for species ID; memory cost; **my research angle**
5. ESKAPE pathogens, AMR/MBR, Kraken-2's diagnostic role
6. Planned experiments (Exp-2, Exp-3); review **Kolin sir's** mail on `perf` + Nsight

Next meeting / deadline: **2026-05-17**.

---

## 2026-05-12 — Study session 1

- Set up `knowledge_base.md` and `updates.md`.
- Started **Topic 1: Nanopore sequencing**.
  - Chunk 1/4 ✓ — what sequencing means + how nanopore reads DNA electrically (KB §1.1)
  - Chunk 2/4 ✓ — device structure: flow cell → membrane → channels → pores; parallel reads (KB §1.2)
  - Chunk 3/4 ✓ — k-mer window (5–6 bp), 4096 patterns, "voice" of DNA, why NN is needed (segmentation + classification) (KB §1.3)
  - Chunk 4/4 ✓ — POD-5 raw signal format, squiggle visualization (KB §1.4 — Claude wrote, user to review later)
  - **Topic 1 complete.** Ready for Topic 2 (sample prep pipeline).
- Started **Topic 2: Sample preparation pipeline**.
  - Chunk 1/4 ✓ — why prep exists + A-T/G-C pairing recap (KB §2.1 intro + §2.3 — Claude wrote)
  - **Workflow shift:** Claude writes KB directly from now on; user asks questions / adds notes; Claude checks in each chunk.
  - Chunk 2/4 ✓ — fragmentation, end prep, Y-adapter structure (motor protein, leader, tether/docking), ligation, kit names LSK/RAD (KB §2.1 deep dive)
  - Chunk 3/4 — how the adapter actually gets DNA into the pore (mechanics of capture) — *deferred to day 2*

---

## 2026-05-16 — Study session 3 (day 3) — Inference setup

- **Goal for today:** run basecalling inference on POD-5 data from mam.
- **Dorado installation — complete.**
  - Found that ONT no longer hosts binaries on GitHub (0 assets on all releases).
  - Located the actual CDN download URL: `cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-win64.zip`
  - Downloaded (~2.8 GB), extracted, verified: `dorado.exe --version` → `1.4.0` ✓
  - Installed at: `Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe`
  - GPU (NVIDIA) will be auto-detected at runtime — no extra config needed.
  - Installation details added to KB §7.1.
- **POD-5 data from mam:** downloading — pending.
- **Next:** once POD-5 arrives, identify flow cell chemistry from file metadata, then run `dorado basecaller hac <file.pod5> --output-dir results\`.
- **Reviewed Kolin sir's mail** — fully understood and added to KB §8.
  - Two sub-projects: Hot-K-mer LRU cache (Kraken-2, CPU) + Signal-to-Base cache (Dorado, GPU)
  - Key tech: Intel TBB, AVX-512, LSH, CUDA shared memory
  - **Immediate deliverable: 2-page profile report using perf + Nsight by ~2026-05-25**
  - Profiling plan: WSL2 on local machine is the best option (Colab won't work — no root/Nsight access)
  - Open question for mam/Kolin sir tomorrow: is there a lab server we can SSH into?

---

## 2026-05-13 — Study session 2 (day 2)

- **Calibration update:** user is a CSE student. Bio is context, not core. Lightening bio depth in remaining Topic 2; leaning hard into Topic 3 (basecaller NN) and Topic 4 (Kraken-2 hashing + memory) which are the CSE-relevant parts.
- Topic 2 remaining (Chunks 3 + 4): condensed into a single wrap-up — pore capture mechanics, MinION/PromethION specs, AMR/MBR terminology. (KB §2.2, §2.4, §2.5)
- **Open question for mam:** what specifically does "MBR" stand for in this context? (Flagged in KB §2.5)
- **Topic 2 complete.** Ready for Topic 3 (basecalling) — the first CSE-heavy topic.
- Started **Topic 3: Basecalling**.
  - Chunk 1/4 ✓ — basecalling as ML problem: seq2seq framing, CTC analogy to speech, training data source, GPU runtime / Nsight hook (KB §3.0)
  - Chunk 2/4 — NN architecture deep-dive (CNN + RNN/Transformer + CTC) → batched into KB §3.2
- **Batch write** (user requested efficient mode): all remaining KB sections written in one pass for self-paced reading.
  - §3.1 Dorado/Guppy/Bonito tool comparison
  - §3.2 NN architecture (5-stage pipeline, model sizes, GPU bottlenecks for Nsight)
  - §3.3 VQ + Shannon source coding + Euclidean vectors (basecaller as lossy compressor)
  - §4.1 K-mer hashing, minimizers, LCA classification
  - §4.2 Why DB is 100 GB
  - §4.3 Memory-efficiency research angle (Bloom filters, learned indexes, nanopore long-read advantage)
  - §5.1 ESKAPE pathogens
  - §5.2 AMR drivers, MBR still flagged
  - §5.3 Clinical workflow + why memory matters
- **All theory topics (1–5) now in KB.** Topic 6 (experiments) is the remaining piece — that's hands-on, not theory; will start when user is ready.
