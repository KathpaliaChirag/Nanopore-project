GOAL: research how to make kraken2 fast as a general program on ANY machine (1-channel laptop, ARM/Jetson, 8 GB RAM box, big 2-socket server, cold or warm disk), not tuned to Luna. Cover every aspect: algorithm, storage, I/O, cpu, compiler. Research and writing only: no ssh, no remote builds. Commit after every round (small commits prefixed portable_kraken2:), never push.

READ FIRST: plan_paper/talk_track_sir_2026-10-21.md (S8-S19 done, do not re-propose) and the other plan_paper/*_2026-10-21.md files. Facts: the table keeps only a key fingerprint, so a new format needs a db rebuild; lookup is 19.5% of cpu on the 50MB db, scanner 38.5%; golden rule is byte-identical output, any lossy or exact change needs an accuracy check. Luna numbers are ONE data point, never generalize.

LITERATURE: before every R1 each agent reads at least 3 NEW real papers or docs (arxiv, pmc, biorxiv, vldb, kernel docs) on optimisation strategy for its area. Cite url plus the exact claim used, never from memory.

SPAWN 5 agents, fixed roles (you relay): (1) data structures and algorithms: hashing, tries, MPHF, filters, minimizers. (2) storage and memory: db format, compression, mmap vs copy, cold disk, huge pages, NUMA. (3) cpu: scanner, SIMD, threads, input lock, ARM vs x86, compiler/PGO. (4) hardware spread: per idea, effect on laptop, Jetson, small-RAM box, big server. (5) skeptic: demands evidence, attacks assumptions, checks prior art (Centrifuger, Metabuli, kache-hash, MegIS, SSHash).

CYCLE (no cap: continue while any counter changes the ranked list; stop after 2 unchanged cycles with all 5 agreeing):
R1 each agent proposes up to 5 ideas: mechanism from zero, gain per hardware class, days, risk, cheapest test.
R2 each agent counters every other agent's top picks: what breaks, which machine it hurts, what is cheaper.
R3 reconcile into one ranked list with open dissent, save cycle_N_conclusion.md, update FINAL.md, commit.
Next cycle: every agent first reads the last conclusion AND the full old transcript, writes counters to it, reads new papers, reruns R1-R3.

THEN 2 VERIFICATION ROUNDS with NEW agents who did not debate:
V1 audit: re-derive every number, check every claim against repo files or fetched sources, tag [repo]/[measured]/[arith]/[guess]/[external]/[UNCLEAR]. Delete or downgrade what fails.
V2 red-team: try to break each top-5 idea on laptop, Jetson, small-RAM box, big server, cold cache. Mark which need a startup switch chosen from detected cache size, cores, storage speed.

RULES: no invented numbers or citations, unknown stays [UNCLEAR]. Reader knows nothing: define terms in brackets on first use, state the wrong intuition first, give a worked number example. Lowercase, no em-dashes, short sentences.

OUTPUT in plan_paper/portable_kraken2/: cycle_N_*.md and FINAL.md (ranked table with gain per hardware class, days, risk, evidence; what to measure first; what NOT to do and why; 10-line summary for sir).
