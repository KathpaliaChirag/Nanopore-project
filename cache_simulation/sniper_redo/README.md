# sniper redo (started 2026-11-24): same-source cache-off baseline, cache modelling, single and multicore

why: the first Sniper study compared a no-cache build (S0) from a different source tree against cache builds (16 to 34 M extra instructions in S0), used a half-size LLC slice (config error), and only ever ran single-core. this redo builds EVERY variant from one source tree (the sizepin-65536 tree) with compile-time switches, checks each against the baseline classifier for identical output, uses the corrected luna2.cfg (LLC slice 2250 KB), and adds multicore.

variants (all from one tree, code/sn_patch.py + code/build.sh): off (cache never hits or allocates), w1/w4/w8/w16 (1/4/8/16 ways at 4,096 sets), s2048/s16384/s65536 (4 ways at 2,048/16,384/65,536 sets; entry 16 B so 128 KB / 1 MB / 4 MB).
workloads: short set = nested prefixes of workloads/50reads.fastq (10/25/50 reads = 7.9 K / 37 K / 91 K bases); long set = the existing long_10/25/50.fastq (0.35 M / 0.9 M / 1.87 M bases).
single core: run-sniper -n 1; multicore: -n 4 with general/total_cores=4, classify -p 4 and K2_BLOCK=10000 so small inputs split into several blocks (otherwise they fit in one 3 M-base block and only one core works).
runner: code/sn_job.sh (one run, appends one row to results.csv), chains in code/chain1.sh and chain2.sh. results: results.csv (copied here as results.csv when the run finishes).

## results (2026-11-24): hardware cache only

the software-cache grid was stopped (user redirected: the goal is a better HARDWARE cache). `data/swcache_results_partial.csv` keeps the few runs that finished and is not analysed.

hardware grid: cache-off binary (classify_off) on luna2.cfg, one hardware property changed per run via `-c` overrides (code/hw_job.sh, variants in code/hw_variants.txt and code/hw_variants_pf.txt). 174 runs in data/hw_results_all.csv (deduplicated; raw in data/hw_results_raw.csv): 8 GB single-core (10/25/50 reads, 31 variants), 16 GB single-core (12 variants), 8 GB 4-core (12 variants).
findings: LLC/L2 associativity, replacement policy and LLC size all within 0.3% of base; only a smaller L2 (+2.4% at 50 reads) and L2 random (+1.1%) are worse. hardware prefetchers are faster everywhere: 8 GB 1-core -4 to -12%, 16 GB -3 to -10%, 4-core 8 GB -13 to -16% (growing with reads). full write-up with tables and caveats: RESULTS_hardware_cache.html.
unsupported in Sniper: PLRU at 15 ways, 32/128-byte lines (DRAM model hard-coded to 64 B).
known data issue: 4 four-core 50-read rows (pf_l1_n8, pf_l1_n16, pf_l1_f32, llc_assoc4) have sim_time NA because two copies of the run raced and one deleted the other's output folder; the write-up uses their cycle counts (about +-0.5%).

## 8 and 16 cores (2026-11-25)

16 runs: 8 and 16 cores x 8 GB and 16 GB x {base, pf_both, pf_l1_simple, llc_assoc4}, 50 reads, K2_BLOCK=1 (one read per block, output checked identical to stock at 8 and 64 threads). 12/32/64 cores were started then stopped on request (only 8 and 16 wanted).
findings: prefetchers -17.4 to -18.2% (8 GB), -23.3 to -24.9% (16 GB); 4-way LLC control within +-0.9%. caveat: 50 reads is about 3 reads per core at 16 cores and instructions rise 52M -> 87M (8c) -> 130M (16c) from thread startup, so the gain may include a startup effect; not tested. see RESULTS_hardware_cache.html section 4f.

## figures and slides (2026-11-25)

figures/plot_figs.py draws the four deck figures from data/hw_results_all.csv with pycairo only (matplotlib could not be installed on Luna: PyPI needs the campus login). run: `python3 plot_figs.py ../data/hw_results_all.csv out` (needs pycairo and the Liberation Sans font; Luna has both). outputs per figure: vector .pdf and .svg (white background, for a paper) and a 2x _slide.png. every percentage is computed from the CSV; nothing is typed in. figures/out/ holds the committed outputs.
the 7-slide deck is a Slides artifact built from these PNGs; metric and caveats are the same as RESULTS_hardware_cache.html. rounding fix: the 4-core L1+L2 gain is 12.7/14.5/15.8 (the page briefly said 12.8 and 15.9 from rounding a rounded number).

## deck v2 (2026-11-25): explanatory rebuild

the first deck only showed results and the graphs had no legends. rebuilt: figures/plot_figs.py v2 (title = the question each graph answers, subtitle = what is plotted and which way is better, legend, direct labels, callouts, group labels on the dot plot, a control series on the cores graph). deck source is in deck/project/ (11 slides: what kraken2 does, what a cache is, the four design knobs, what a prefetcher does, how we measured, four result slides each with how-to-read / what-we-found / why, and what we can and cannot claim). the Slides artifact is built from these files; the figure PNGs are uploaded assets, so re-upload figures/out/*_slide.png if the figures change.

## 100-read file (2026-11-25)

r100.fastq = our 50-read file (r50, unchanged, first 50 reads) + 50 more reads from the same source basecalled file (~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_15.fastq), taken in file order from the same length range (300 to 8,700 bases), skipping r50's reads. r50 was not the first 50 or a consecutive block of that file (its original selection rule was not recoverable), so the extra 50 are NOT picked by the same rule: mean length 1,458 vs 1,827 for r50. total 164,285 bases (1.8x r50), 97% classified by stock kraken2 on the 8 GB db. raw reads are not committed (real sequencing data). runs: code/r100_chain.sh (base + pf_both at 1, 4, 8, 16 cores, 8 GB; 8 and 16 cores use K2_BLOCK=1, 4 cores K2_BLOCK=10000 like the earlier 4-core series).

## 100-read results (2026-11-25, finished 21:57 IST, 70 min for 8 runs)

8 GB, base vs pf_both, r100.fastq (164,285 bases): saved 3.1% (1 core), 22.0% (4), 24.6% (8), 25.4% (16). one-core gain keeps falling with reads (11.9, 5.6, 4.0, 3.1) but the multicore gain RISES at 100 reads, so the earlier "mostly start-up work" explanation is weakened. base time barely changes with cores at 100 reads (17.9, 19.6, 18.2, 17.5 ms): something serial dominates; untested hypothesis = the serial in-order FASTQ reader (streaming, prefetch-friendly). 206 runs total in data/hw_results_all.csv. figures/plot_figs.py fig6 now has a 100-read line. slide 2 of deck2 and the results page are updated.
