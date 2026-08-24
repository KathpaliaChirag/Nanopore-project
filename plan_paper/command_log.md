# Command Log — Sept 13 Paper Push

Running record of every command actually run toward the 3-piece paper package (LLC-adaptive cache, bitmask cell, cell-width reduction) set at Meeting 11 (2026-08-19), executed per `planning/week5plan.md` onward. This is the log of what happened, not what was planned — `planning/weekNplan.md` files are the plan, this file is the receipt.

> [!NOTE]
> One entry per command (or tight command group). Each entry: what, why, result. Append only — don't rewrite history here, correct forward instead. Commit this file alongside whatever code/data change it describes, not in a separate batch later.

**Format per entry:**

```
### YYYY-MM-DD HH:MM — <short label, e.g. "S1.1 — thread-local cache slot">
**Command:**
​```bash
<exact command run>
​```
**Why:** <one line — what step this is, from which plan>
**Input → Output:** <optional — see below>
**Result:** <what happened — output, benchmark numbers, pass/fail, commit hash if applicable>
```

**When to add "Input → Output":** only where the command transforms something and that transform isn't obvious from the command text alone — a build (source tree → binary), a benchmark (fastq + DB → latency/cache-miss numbers), a data step (raw pod5 → basecalled fastq). One line, plain terms, no ML/systems jargon left undefined — whoever reads this later may not have touched this exact command before. Skip it for anything mechanical where there's nothing to explain (`cd`, `ls`, `git commit`, the proxy/auth setup) — the field exists to save a future reader from re-deriving what a command does, not to pad every entry.

**Example (illustrative only — no real run has happened yet, don't treat these numbers as data):**

```
### YYYY-MM-DD HH:MM — S1.2 — first benchmark of the single-slot cache
**Command:**
​```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  ~/tools/kraken2-src-fresh/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 32 --output /dev/null --report /dev/null \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
​```
**Why:** S1.2 in week5plan.md — first real number for the single-slot cache, logged against the 4.405s S0 baseline.
**Input → Output:** takes a fastq of reads + a kraken2 database, classifies every read against it; perf stat wraps the run and reports cache-miss counts and wall-clock time alongside kraken2's own classification output.
**Result:** <wall-clock time>, <LLC miss rate> — compare against the S0 baseline, log honestly either way, tag `safe/S1.2` if it's a real safe zone.
```

---

## Log

*(empty — first entry goes here once S1/B1 work actually starts on Luna)*
