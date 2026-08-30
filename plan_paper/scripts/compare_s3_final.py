# S3.4 - final benchmark of the fully-wired S3 formula against S0 (no
# cache) and the original committed S2 baseline (safe/S2.4: fixed 4,096
# sets, thread_local static array, non-zero sentinel + new[]), across
# the full DB x thread-count matrix, per the user's suggestion on
# 2026-08-30. Same validated interleaved-3-run methodology as every
# prior comparison script in this project (compare_sizes_full.py etc.).
#
# S2-baseline isolates "does the S3 engineering effort actually help
# over the naive fixed-size cache" - S2-final is today's real, shipped
# state: S3.0 (heap-pointer fix) + S3.1/S3.2 (LLC-topology-aware,
# thread-scaled sizing formula, f=0.25 placeholder) + S3.3 (zero-
# sentinel + calloc, fixing the residual slowdown).
#
# Requires kraken2-fresh-bin-s0 and kraken2-fresh-bin-s2 (today's real,
# fully-wired build) to already exist, plus kraken2-fresh-bin-s2-baseline
# (build from classify.cc.pre-s3.0.bak, the exact pre-S3.0 safe/S2.4
# state, same technique as every temporary comparator binary this
# project has built):
#
#   cp classify.cc classify.cc.s3-final.bak   # save today's real state first
#   cp classify.cc.pre-s3.0.bak classify.cc
#   cd .. && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s2-baseline && cd src
#   cp classify.cc.s3-final.bak classify.cc   # restore immediately

import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
BINS = {
    "S0":          "/home/student/tools/kraken2-fresh-bin-s0/kraken2",
    "S2-baseline": "/home/student/tools/kraken2-fresh-bin-s2-baseline/kraken2",
    "S2-final":    "/home/student/tools/kraken2-fresh-bin-s2/kraken2",
}
DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 8, 16, 32, 64, 96]
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
print(f"{'DB':<18}{'T':>4}  {'Bin':<14}  {'Elapsed(avg)':>13}  {'CV%':>6}  {'LLCMiss%':>9}")
for db in DBS:
    for t in THREADS:
        for b in BINS:
            runs = results[(db, t, b)]
            print(f"{db:<18}{t:>4}  {b:<14}  {avg(runs,'elapsed'):>13.4f}  {cv(runs,'elapsed'):>6.2f}  {avg(runs,'llcmiss'):>9.2f}")
