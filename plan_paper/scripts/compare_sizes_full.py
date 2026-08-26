# S2 size-sweep script - actually run on Luna on 2026-08-26 to test whether
# S2's placeholder size (4,096 sets) was simply too small for Luna's real
# working set, by sweeping to 16x/256x/1024x bigger and comparing against
# S0/S1 with the same validated interleaved methodology.
#
# Found the opposite of "too small": flat through 65,536 sets, then a
# catastrophic cliff at 1,048,576+ (up to 22x slower, LLC-miss 13%->89%),
# worse at higher thread counts - pointing at thread_local per-thread
# memory-initialization cost, not cache capacity. See plan_paper/command_log.md's
# "Size sweep" entry and the published artifact for the full analysis.
#
# Requires kraken2-fresh-bin-s0, -s1, -s2, -s2-65536, -s2-1048576, and
# -s2-4194304 to already exist (the last three built via
# plan_paper/scripts/build_size_variants.sh).

import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
BINS = {
    "S0":          "/home/student/tools/kraken2-fresh-bin-s0/kraken2",
    "S1":          "/home/student/tools/kraken2-fresh-bin-s1/kraken2",
    "S2-4096":     "/home/student/tools/kraken2-fresh-bin-s2/kraken2",
    "S2-65536":    "/home/student/tools/kraken2-fresh-bin-s2-65536/kraken2",
    "S2-1048576":  "/home/student/tools/kraken2-fresh-bin-s2-1048576/kraken2",
    "S2-4194304":  "/home/student/tools/kraken2-fresh-bin-s2-4194304/kraken2",
}
DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 16, 32, 64, 96]
RUNS = 3

def run_once(binary, db, threads):
    cmd = ["perf", "stat", "-e",
           "cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles",
           "numactl", "--cpunodebind=0", "--membind=0",
           binary, "--db", f"{DBDIR}/{db}", "--threads", str(threads),
           "--output", "/dev/null", "--report", "/dev/null", FASTQ]
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
        for b in BINS:
            results[(db, t, b)] = []
        for i in range(RUNS):
            for b, path in BINS.items():
                results[(db, t, b)].append(run_once(path, db, t))
        print(f"done: {db} T={t}", flush=True)

def avg(runs, field):
    vals = [r[field] for r in runs if r[field] is not None]
    return statistics.mean(vals) if vals else float("nan")
def cv(runs, field):
    vals = [r[field] for r in runs if r[field] is not None]
    if len(vals) < 2 or statistics.mean(vals) == 0: return float("nan")
    return 100 * statistics.stdev(vals) / statistics.mean(vals)

print()
print(f"{'DB':<18}{'T':>4}  {'Bin':<12}  {'Elapsed(avg)':>13}  {'CV%':>6}  {'LLCMiss%':>9}")
for db in DBS:
    for t in THREADS:
        for b in BINS:
            runs = results[(db, t, b)]
            print(f"{db:<18}{t:>4}  {b:<12}  {avg(runs,'elapsed'):>13.4f}  {cv(runs,'elapsed'):>6.2f}  {avg(runs,'llcmiss'):>9.2f}")
