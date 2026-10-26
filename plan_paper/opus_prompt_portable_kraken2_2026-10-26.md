GOAL: research how to make kraken2 fast as a general program on ANY machine (1-channel laptop, ARM/Jetson, 8 GB RAM box, big 2-socket server, cold or warm disk), not tuned to Luna. Cover algorithm, data structure, db format, I/O, memory, threading, compiler. Read-only research and writing: no ssh, no builds, no commits.

READ FIRST: plan_paper/talk_track_sir_2026-10-21.md (S8-S19 already done, do not re-propose), research_brief_db_structure_trie_dictionary_2026-10-21.md, next_steps_plan_2026-10-21.md. Facts: the table keeps only a 16-26 bit key fingerprint, so hash.k2d cannot be converted, a new format needs a rebuild; lookup is 19.5% of cpu on the 50MB db, scanner 38.5%; golden rule is byte-identical output, any exact or lossy change needs a stated accuracy check. Luna numbers are ONE data point, never generalize from them.

SPAWN 5 agents, fixed roles (you relay outputs): (1) data structures and algorithms: hash variants, tries, MPHF, filters, minimizer scheme. (2) storage and memory: db file format, compression, mmap vs copy, cold disk, huge pages, NUMA, RAM-limited runs. (3) cpu and parallelism: scanner, SIMD, threads, input lock, ARM vs x86, compiler/PGO. (4) hardware spread: per idea, what happens on laptop, Jetson (4 MB cache, slow emmc), small-RAM box, big server. (5) skeptic: demands evidence, attacks assumptions, checks prior art (Centrifuge, Centrifuger, Metabuli, Sylph, kache-hash, MegIS, SSHash).

CYCLE (repeat until all 5 sign off, max 5 cycles, then record dissent):
R1 each agent proposes up to 5 ideas: mechanism from zero, why current code is slow, predicted gain per hardware class, code cost in days, risk, cheapest test.
R2 each agent counters every other agent's top picks: what breaks, which machine it hurts, what is cheaper.
R3 reconcile into one ranked list, list open dissent, save cycle_N_conclusion.md.
Next cycle: every agent first reads the last conclusion AND the full old transcript, writes counters to it, then reruns R1-R3. Stop when the list stops changing and all 5 agree.

THEN 2 VERIFICATION ROUNDS with NEW agents who did not debate:
V1 audit: re-derive every number, check every claim against repo files or fetched sources (give url), tag [repo]/[measured]/[arith]/[guess]/[external]/[UNCLEAR]. Delete or downgrade what fails.
V2 red-team: try to break each top-5 idea on laptop, Jetson, small-RAM box, big server and cold-cache runs. Mark which ideas need a startup switch chosen from detected cache size, cores, storage speed.

RULES: no invented numbers or citations, unknown stays [UNCLEAR]. Reader knows nothing: define terms in brackets on first use, state the wrong intuition first, give a worked number example. Lowercase, no em-dashes, short sentences.

OUTPUT in plan_paper/portable_kraken2/: cycle_N_*.md transcripts and FINAL.md: ranked table (idea, aspect, gain per hardware class, days, risk, evidence), what to measure first, what NOT to do and why, 10-line summary for sir.
