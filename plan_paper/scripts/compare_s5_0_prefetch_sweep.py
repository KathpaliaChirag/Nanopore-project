# S5.0 - controlled -B sweep across the FULL DB x thread-count grid,
# same as S3.4's compare_s3_final.py (2026-08-31). Widened from an
# earlier 2-DB/2-thread draft after reconsidering: prefetching's benefit
# depends on the core's spare memory-level-parallelism slots (~12
# outstanding requests), which many threads compete for at high T - the
# effect could plausibly be LARGEST at low T (less contention for that
# shared capacity) and smallest at 32T/96T, i.e. the opposite of where a
# narrower sweep would have looked. Full grid catches that either way.
#
# B values (1, 4, 8, 16, 32) match Suthar's own tested points
# (mtp1/reports/PREFETCH.md) so results are comparable to his curve
# shape, plus 1 as the true stock-equivalent baseline (verified byte-
# identical to S0 on 2026-08-31) - his sweep didn't need a separate
# baseline column since -B 1 was already his stock comparator too.
#
# Calls `classify` directly, not the `kraken2` wrapper - the wrapper's
# Getopt::Long option list has no idea what -B is (confirmed the hard way
# on 2026-08-31: passing -B through the wrapper silently misrouted "1" as
# an input filename). Flags below are exactly what the wrapper itself
# builds before exec'ing classify (read directly from
# kraken2-fresh-bin-s5-0/kraken2 lines 119-137), plus -B.
#
# Same validated interleaved-3-run methodology as every prior comparison
# script in this project (compare_s3_final.py etc.): for each rep, run
# every B value once before repeating, so a page-cache-warmth or thermal
# drift confound can't land on one B value more than another.
#
# Requires kraken2-fresh-bin-s5-0/classify (built from the safe/S5.0-
# prefetch tag). Run inside tmux - the full grid is 3 DBs x 6 thread
# counts x 5 B values x 3 reps = 270 runs, comparable in scale to S3.4's
# 162-run sweep (~80-90 min) but larger - expect a few hours, unattended.
#
#   tmux new -s s5sweep
#   python3 /tmp/compare_s5_0_prefetch_sweep.py | tee ~/s5_0_prefetch_sweep.txt
#   # Ctrl+B, D to detach; reattach later with: tmux attach -t s5sweep

import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
CLASSIFY = "/home/student/tools/kraken2-fresh-bin-s5-0/classify"

DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 8, 16, 32, 64, 96]
B_VALUES = [1, 4, 8, 16, 32]
RUNS = 3

def run_once(db, threads, b):
    cmd = ["perf", "stat", "-e",
           "cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles",
           "numactl", "--cpunodebind=0", "--membind=0",
           CLASSIFY,
           "-H", f"{DBDIR}/{db}/hash.k2d",
           "-t", f"{DBDIR}/{db}/taxo.k2d",
           "-o", f"{DBDIR}/{db}/opts.k2d",
           "-p", str(threads), "-T", "0", "-Q", "0", "-g", "2", "-B", str(b),
           "-O", "/dev/null", "-R", "/dev/null",
           FASTQ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    elapsed = re.search(r"([\d.]+) seconds time elapsed", out)
    llcmiss = re.search(r"#\s+([\d.]+)% of all LL-cache accesses", out)
    return {
        "elapsed": float(elapsed.group(1)) if elapsed else None,
        "llcmiss": float(llcmiss.group(1)) if llcmiss else None,
    }

results = {}
for db in DBS:
    for t in THREADS:
        for b in B_VALUES:
            results[(db, t, b)] = []
        for i in range(RUNS):
            for b in B_VALUES:
                results[(db, t, b)].append(run_once(db, t, b))
        print(f"done: {db} T={t}", flush=True)

def avg(runs, field):
    vals = [r[field] for r in runs if r[field] is not None]
    return statistics.mean(vals) if vals else float("nan")
def cv(runs, field):
    vals = [r[field] for r in runs if r[field] is not None]
    if len(vals) < 2 or statistics.mean(vals) == 0: return float("nan")
    return 100 * statistics.stdev(vals) / statistics.mean(vals)

print()
print(f"{'DB':<18}{'T':>4}  {'B':>4}  {'Elapsed(avg)':>13}  {'CV%':>6}  {'LLCMiss%':>9}  {'vs B=1':>8}")
for db in DBS:
    for t in THREADS:
        base = avg(results[(db, t, 1)], "elapsed")
        for b in B_VALUES:
            runs = results[(db, t, b)]
            e = avg(runs, "elapsed")
            rel = 100 * (e - base) / base if base else float("nan")
            print(f"{db:<18}{t:>4}  {b:>4}  {e:>13.4f}  {cv(runs,'elapsed'):>6.2f}  {avg(runs,'llcmiss'):>9.2f}  {rel:>+7.2f}%")
