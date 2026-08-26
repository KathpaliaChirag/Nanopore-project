# S2.4 measurement script - actually run on Luna on 2026-08-26 to compare
# the unpatched (S0), S1.1-patched (S1), and S2-patched (S2, 4,096 sets)
# binaries fairly. Same interleaving fix validated in compare_s0_s1.py,
# extended to three binaries instead of two.
#
# Requires kraken2-fresh-bin-s0, kraken2-fresh-bin-s1, and kraken2-fresh-bin-s2
# to already exist.

import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
BINS = {
    "S0": "/home/student/tools/kraken2-fresh-bin-s0/kraken2",
    "S1": "/home/student/tools/kraken2-fresh-bin-s1/kraken2",
    "S2": "/home/student/tools/kraken2-fresh-bin-s2/kraken2",
}
DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 16, 32, 64, 96]
RUNS = 3  # 3 of each, interleaved S0,S1,S2 / S0,S1,S2 / S0,S1,S2 per cell -
          # not blocked, so all three get an even mix of "cold"/"warm" cache
          # positions instead of whichever runs last being favored.

def run_once(binary, db, threads):
    cmd = ["perf", "stat", "-e",
           "cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles",
           "numactl", "--cpunodebind=0", "--membind=0",
           binary, "--db", f"{DBDIR}/{db}", "--threads", str(threads),
           "--output", "/dev/null", "--report", "/dev/null", FASTQ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    elapsed = re.search(r"([\d.]+) seconds time elapsed", out)
    cachemiss = re.search(r"#\s+([\d.]+)% of all cache refs", out)
    llcmiss = re.search(r"#\s+([\d.]+)% of all LL-cache accesses", out)
    ipc = re.search(r"#\s+([\d.]+)\s+insn per cycle", out)
    return {
        "elapsed": float(elapsed.group(1)) if elapsed else None,
        "cachemiss": float(cachemiss.group(1)) if cachemiss else None,
        "llcmiss": float(llcmiss.group(1)) if llcmiss else None,
        "ipc": float(ipc.group(1)) if ipc else None,
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
    if len(vals) < 2 or statistics.mean(vals) == 0:
        return float("nan")
    return 100 * statistics.stdev(vals) / statistics.mean(vals)

print()
print(f"{'DB':<18}{'T':>4}  {'Bin':<3}  {'Elapsed(avg)':>13}  {'CV%':>6}  {'CacheMiss%':>11}  {'LLCMiss%':>9}  {'IPC':>5}")
for db in DBS:
    for t in THREADS:
        for b in BINS:
            runs = results[(db, t, b)]
            e, ecv = avg(runs, "elapsed"), cv(runs, "elapsed")
            c = avg(runs, "cachemiss"); l = avg(runs, "llcmiss"); i = avg(runs, "ipc")
            print(f"{db:<18}{t:>4}  {b:<3}  {e:>13.4f}  {ecv:>6.2f}  {c:>11.2f}  {l:>9.2f}  {i:>5.2f}")
