# Handover: decide what to say on each midterm slide

Written 2026-09-24 (Thursday) from a long working session. Read this fully before replying to CK.

## 1. Situation and deadline

- Prof. Kolin Paul ("sir") wants the midterm ppt. Sir's mail (2026-09-21): at most 10 slides, 10 minutes, link shared as view-anyone-with-link, due Thursday 2026-09-24 noon, online presentation about 2026-09-25.
- Format sir asked for: title, motivation/problem, state of the art to beat, plan plus where we are (graphs and preliminary results), and a promise for the final ppt on the last slide.
- The deck is combined with Chirag Suthar. Credit him where the work is joint or his (cell width report, prefetch).
- CK's real deck is being built in Canva (his screenshots show Canva's toolbar). The HTML deck referenced below was only an idea board; CK copies things from it.

## 2. Your job in this chat

CK will paste slide images one at a time. For each slide:

1. Rate it out of 10 with one or two lines of reasoning.
2. List concrete improvements (legibility from the back of a room, one message per slide, number sizes, clutter, anything a claim says that the data does not support).
3. Write what to say, sized to the time CK gives you. If he gives no time, use the default budget in section 5.
4. Say if anything is missing or risky. Keep this separate from the script.

Rules that come from CK:

- His outline is fixed (section 3). Do not add slides, findings, comparators or "helpful" extras. If you think something should be added, label it "optional suggestion" and let CK decide. If a slide needs content CK has not named, ask him.
- No Sniper/simulator numbers anywhere. CK does not trust them yet. Sniper is future work only.
- Never call the adaptive cache work "Patch 4". Use stage names (S1, S2) or "software cache".
- Sir is always "sir". Chirag Suthar's work is credited by name.
- Real measured numbers only. If a number cannot be traced to section 4, say so instead of using it.
- Keep replies short. CK likes a short recap plus a numbered action list.

## 3. CK's slide outline (fixed)

1. Title
2. Motivation (one slide only): ESKAPE pathogens, why detection is hard, nanopore workflow
3. Kraken2 benchmarking A: wall time and cache-miss rate vs read count and database size
4. Kraken2 benchmarking B: database size and the accuracy issue
5. Flowchart of the things tried (CK explains this aloud; may not exist yet in the deck)
6. Cell width: 32-bit to 24/16-bit results (joint with Chirag Suthar)
7. Software cache results
8. Future: cache modelling on Sniper (no numbers)
9. Future: minimizer prefetching in batches (Chirag Suthar's work)
10. Promise for the final ppt

## 4. Fact sheet (all measured this week unless marked)

Setup for the Kraken2 benchmarks: Luna, 32 threads pinned to numactl node0, kraken2 v2.17.1 stock binary (`kraken2-fresh-bin-s0`), perf stat wrapped. Databases: sample_targeted (50MB), standard_8gb, standard_16gb, pluspf_103gb (103GB). Read counts: 10, 1,000, 104,918, 1,872,777.

### Slides 3-4: wall time and LLC cache-miss rate (no --memory-mapping)

| DB | 10 reads | 1,000 | 104,918 | 1,872,777 | LLC miss % at the same four points |
|---|---|---|---|---|---|
| 50MB | 0.084s | 0.298s | 1.244s | 13.881s | 70.8, 19.1, 11.8, 11.5 |
| 8GB | 4.396s | 4.337s | 5.313s | 18.535s | 92.2, 92.8, 79.2, 56.8 |
| 16GB | 9.086s | 7.956s | 8.937s | 22.304s | 90.5, 94.5, 82.2, 58.0 |
| 103GB | 51.347s | 51.187s | 53.950s | 79.463s | 97.7, 97.5, 84.1, 71.9 |

Reading: small reads counts are dominated by database load time (10 reads on 103GB still takes 51s). Cache-miss rate falls as read count grows because later reads reuse hot k-mers. Small DB is cache-resident almost immediately, the 103GB DB never is.

### Slide 4: accuracy vs database size (fixed input reads_hac, 104,918 reads, 32T)

DBs 50MB, 142MB, 3.8GB, 7.6GB, 15GB, 103GB. Classification accuracy 84.8, 65.3, 66.1, 95.8, 97.8, 98.9 percent. LLC miss 11.9, 30.5, 59.0, 77.7, 79.7, 90.2 percent. Wall time 1.28, 1.39, 3.50, 5.53, 10.12, 53.6 s.

Caveats: the 142MB and 3.8GB databases no longer exist on Luna. Their accuracy and LLC values are last-recorded (kraken2 v2.1.3, 2026-08-03) and their wall times are SCALED estimates, not measured (log-size interpolation of the v2.17.1/v2.1.3 ratio). Ask CK which of the other four values were re-measured before saying "measured". Do not compare Kraken2 accuracy against Centrifuge/Metabuli on a slide: the classified-percentage gap (Kraken2 65% vs 86-92%) has an explanation that was never confirmed.

### Slide 3 or 5: where the cycles go (perf record, symbols regrouped by me into categories)

- Small DB (sample_targeted, thread count not recorded): hash lookup 32.7%, minimizer extraction 31.3%, classification logic 11.0%, I/O 5.3%, memory management 4.9%, other 14.8%.
- Large scale (1,872,777 reads, 103GB DB, 32T, with --memory-mapping): hash lookup 64.5%, minimizer 12.4%, classification 11.6%, I/O 4.2%, memory 1.7%, other 5.7%. Without --memory-mapping: 60.3 / 11.9 / 11.3 / 4.3 / 1.8 / 10.5.
- The hot function is `CompactHashTable::Get()`. Category grouping is my own, so say "about" and do not present it as perf's own categories.

### --memory-mapping (only if CK wants it on a slide; it is not in his outline)

Speedup of --memory-mapping over default, per read count 10 / 1,000 / 104,918 / 1,872,777: 50MB 1.1x, 1.1x, 1.0x, 1.1x slower; 8GB 40.0x, 9.2x, 3.8x, 1.2x; 16GB 56.8x, 12.6x, 6.0x, 1.4x; 103GB 79.0x, 17.1x, 12.9x, 2.5x. Example: 103GB at 10 reads 51.3s to 0.65s. Caveat: both runs read the same database file back to back, so the default run likely had a warm page cache. It is not a cold-start comparison.

### Slide 6: cell width (joint with Chirag Suthar)

1 thread, pod5_2.fastq (151,591 reads, 499.98 Mbp), stock 2.17.1, no prefetch, mean of 3.

| Cell | DB size | Runtime | Cache-miss | Classified |
|---|---|---|---|---|
| 32-bit | 48.8MB | 23.611s | 59.43% | 84.26% |
| 24-bit | 36.6MB | 22.783s | 53.41% | 84.27% |
| 20-bit | 36.6MB | 22.820s | 53.23% | 85.00% |
| 16-bit | 24.4MB | 20.203s | 41.20% | 91.29% |

Runtime is 14% lower at 16-bit. IMPORTANT: classified percentage RISING is not a good sign. It comes from more hash collisions (false positives). The species counts show it: E. faecium 5 to 802 reads and S. aureus 3 to 552 reads from 32-bit to 16-bit, K. pneumoniae 14,427 to 17,425, E. cloacae 628 to 2,441, while the dominant species barely move (P. aeruginosa 79,402 to 81,151). The HTML idea deck has a line on its cellwidth slide saying "fewer false positives, not less accuracy". That line is wrong. Do not let it into the real deck. The joint report (`dorado-kraken-research/docs/reports/kraken2opti_report.tex`) has the exponential false-positive law and a 1,728-run cross-hardware sweep.

### Slide 7: software cache

What exists: S0 is stock Kraken2. Stock already has a 1-minimizer check (`last_minimizer` and `last_taxon`) but it is function-local and resets every read. S1 (`kraken2-fresh-bin-s1`, commit fbf993d) only makes that same 16-byte pair thread_local so it survives across reads. 16 bytes per thread (8 byte minimizer plus 8 byte taxid; taxid_t is uint64_t), 512 bytes at 32 threads.

S0 vs S1, 32T, wall time seconds (S0 then S1):

| DB | 10 reads | 1,000 | 104,918 | 1,872,777 |
|---|---|---|---|---|
| 50MB | 0.12 / 0.11 | 0.30 / 0.29 | 1.27 / 1.05 | 15.70 / 13.16 |
| 8GB | 4.53 / 4.57 | 4.63 / 4.66 | 5.57 / 5.40 | 19.74 / 15.93 |
| 16GB | 8.46 / 8.59 | 8.56 / 8.59 | 9.51 / 9.40 | 24.27 / 20.76 |
| 103GB | 61.73 / 61.31 | 60.57 / 60.71 | 62.61 / 62.48 | 85.71 / 87.93 |

At 1,872,777 reads S1 is 1.19x, 1.24x, 1.17x faster on 50MB, 8GB, 16GB and 0.97x (slower) on 103GB. Low read counts are noise.

Honest caveats, all load-bearing:

- The cause of S1's speedup is NOT established. LLC miss rate barely changes (under 0.25 percentage points in an earlier controlled 3-run study). A different Luna session on 2026-09-24 ran an ablation on a later lineage and found the 4-way cache adds nothing; its win came from pipeline effects (per-input-file OpenMP barrier, serial FASTQ parser). The 1.87M-read input is 16 files, so file-boundary effects may be part of what S1 shows too. That is an untested hypothesis, do not state it as fact.
- 4-way cache (S2, 4,096 sets x 4 ways, 16,384 entries, about 260KB per thread, about 8MB at 32T): the standalone build measured badly slower (8.3x slower on 50MB at 1.87M reads, 2.35x on 103GB). Known causes: global std::atomic hit/miss counters contending across threads, plus an old broken set-index hash (fixed later in commit a240d60, 8.9x higher hit rate). So that slowdown is a measurement artifact of that build, not evidence about 4-way caches in general. Do not put the 4-way slowdown on a slide as a result.
- Absolute times vary between sessions on the same machine. 103GB at 10 reads was 51.3s in one sweep and 61.7s in another. 103GB at 1.87M reads was 79.5s, 85.7s, and 95.3s in three different runs. Say "one machine, one run per cell" out loud.

### The 2026-09-24 speedup result (NOT in CK's outline, ask him)

A Luna session took stock Kraken2 to a build called S15: 1.8x to 4.4x faster at 1.87M reads and 10-17x faster at small read counts, byte-identical output in all 16 cells (50MB 16.6s to 9.4s, 8GB 21.1s to 9.4s, 16GB 26.8s to 11.7s, 103GB 95.3s to 21.6s). Real wins: multi-file streaming, parallel pread table load, hugepage table, memchr in the FASTQ parser, batched prefetch (only helps 103GB), reciprocal modulo. Caveats: one machine, warm page cache, transparent-hugepage mode varies (103GB timing 13-21s), one run per cell. Full write-up: `plan_paper/s6_s15_speedup_report_2026-09-24.md`. This is the strongest thing CK has for slides 7 to 10 (the "promise" or "where we are"), but CK said to add only what he names, so raise it as a question, not a slide.

### Slides 8-9: future work

- Slide 8: cache modelling on Sniper. No numbers. Sniper results are untrusted by CK.
- Slide 9: minimizer prefetching in batches, Chirag Suthar's `kraken2_prefetch.patch`. Do NOT quote the -20.34% figure as a Luna number; it is not one. A port of the batched prefetch exists on Luna (commit c4e7a0d) and helps only the 103GB DB in the later ablation, null on 8GB/16GB.

### Slide 2: motivation facts (background literature, not our measurements)

- ESKAPE: Enterococcus faecium, Staphylococcus aureus, Klebsiella pneumoniae, Acinetobacter baumannii, Pseudomonas aeruginosa, Enterobacter species. Term from Rice, J Infect Dis 2008; Boucher et al., Clin Infect Dis 2009 is the usual citation.
- The WHO Bacterial Priority Pathogens List is about RESISTANT strains (for example carbapenem-resistant A. baumannii, vancomycin-resistant E. faecium, MRSA), not the species as such. Say "resistant strains of these are on the WHO priority list", not "all six species are". Check the exact wording against the WHO 2024 list before saying it.
- Nanopore workflow details come from published papers: over 95% of reads still human after depletion in one whole-blood study; about 2h depletion, 1h extraction, 4h PCR plus sequencing in one (fungal bloodstream infection) workflow; blood culture often over 48h. Present them as "in one published workflow".
- The one number of ours on the pipeline slide is the 64.5% hash-lookup share.
- Images in the HTML deck: CDC Public Health Image Library, public domain. The "E. faecium" picture is actually an Enterococcus faecalis micrograph, and the Klebsiella and Enterobacter pictures are agar-culture photos, not electron micrographs. Caption them accordingly if CK reuses them.

## 5. Default time budget (10 minutes, adjust to what CK says)

| Slide | Time | Job |
|---|---|---|
| 1 Title | 0:20 | who, what, one-line scope |
| 2 Motivation | 1:15 | why ESKAPE detection is urgent and hard; nanopore makes it fast; classification is the bottleneck |
| 3 Benchmarking A | 1:15 | wall time and cache-miss vs read count and DB size |
| 4 Benchmarking B | 1:00 | DB size vs accuracy; the accuracy problem |
| 5 Things tried | 1:15 | walk the flowchart aloud |
| 6 Cell width | 1:15 | speed gain and the false-positive cost (joint with Chirag Suthar) |
| 7 Software cache | 1:15 | what it is, what we saw, what we do not know |
| 8 Sniper | 0:45 | future, no numbers |
| 9 Prefetching | 0:45 | future, Chirag Suthar |
| 10 Promise | 0:35 | what the final ppt will show |

Total 9:40, which leaves 20 seconds of slack. If sir's session is combined with Chirag Suthar, ask CK who speaks which slides and how the 10 minutes are split.

## 6. What to check on every slide

- One message that fits in one sentence. If it needs two, suggest splitting or cutting.
- Numbers readable from the back of the room (bar labels and axis text at least about 12pt equivalent on a projected slide).
- Every claim on the slide is backed by a row in section 4. Flag anything that goes beyond it.
- Units and read counts are stated (32T, one machine, reads count).
- Color and type consistent across slides (the idea deck used Podkova headings, IBM Plex Sans body, JetBrains Mono for numbers).
- Honest caveat is on the slide or in the script, not hidden.
- Speaker load: not more than about 3 ideas per minute of talking.

## 7. Where things are

- HTML idea deck (30+ slides, mostly variants): https://claude.ai/artifact/9puQ4kv5EW3ZTMxnqGQsa9 (private to CK).
- Chart images and their generator scripts: `presentations/midterm_assets/` (readcount grid and combined charts, memory-mapping comparison, cache comparison, accuracy chart, composition, cell width, species).
- Raw sweep data: `presentations/midterm_assets/M_sweep_results_raw.txt`, `presentations/midterm_assets/cache_sweep_results_raw.txt`.
- Command log: `plan_paper/command_log.md`. Cache investigation handoff: `plan_paper/handoff_s2_speedup_investigation_2026-09-23.md`. Speedup report: `plan_paper/s6_s15_speedup_report_2026-09-24.md`.
- Memory notes (auto memory folder): midterm deck outline, S6-S15 speedup, Sniper choice.
- Luna access is not needed for this task. If CK asks for a new number, tell him what run it needs before anyone touches Luna.

## 8. First message to send CK

Confirm the deadline (today noon) and ask three things: how many minutes he wants per slide or in total, who presents which slides, and whether the S15 speedup result should appear anywhere. Then ask for slide 1.
