# S1.2 measurement script - actually run on Luna on 2026-08-25 to compare
# the unpatched (S0) and S1.1-patched (S1) binaries fairly.
#
# IMPORTANT METHODOLOGY NOTE: an earlier, simpler version of this comparison
# (run S0's full sweep, then S1's full sweep, separately) produced a
# misleading result - a dramatic-looking improvement on pluspf_103gb at
# 1 thread that turned out to be a page-cache warmth artifact (S1's sweep
# benefited from S0's sweep having already read the same 103GB file).
# This version fixes that by interleaving S0 and S1 within each cell
# (S0,S1,S0,S1,S0,S1 - not blocked), so both get an even mix of cold/warm
# cache positions. See plan_paper/command_log.md's "S1.2 measured" entry
# for the full story.
#
# Requires kraken2-fresh-bin-s0 and kraken2-fresh-bin-s1 to already exist
# (built via `./install_kraken2.sh <dir>` from the pre- and post-S1.1-patch
# source trees respectively).

import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
S0_BIN = "/home/student/tools/kraken2-fresh-bin-s0/kraken2"
S1_BIN = "/home/student/tools/kraken2-fresh-bin-s1/kraken2"
DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 16, 32, 64, 96]
RUNS = 3  # 3 of each, interleaved S0/S1/S0/S1/S0/S1 per cell - not blocked,
          # so page-cache warmth (or any other time-drift) affects both
          # binaries roughly equally instead of favoring whichever runs second.

def run_once(binary, db, threads):
    cmd = ["perf", "stat", "-e",
           "cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles",
           "numactl", "--cpunodebind=0", "--membind=0",
           binary, "--db", f"{DBDIR}/{db}", "--threads", str(threads),
           "--output", "/dev/null", "--report", "/dev/null", FASTQ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    # pull just the 4 numbers we care about out of perf's normal text output -
    # percentages/IPC are always plain decimals regardless of locale, so no
    # special number-parsing needed here.
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
        s0_runs, s1_runs = [], []
        for i in range(RUNS):
            s0_runs.append(run_once(S0_BIN, db, t))   # S0 first this round...
            s1_runs.append(run_once(S1_BIN, db, t))   # ...then S1, same round - alternating, not blocked
        results[(db, t, "S0")] = s0_runs
        results[(db, t, "S1")] = s1_runs
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
print(f"{'DB':<18}{'T':>4}  {'Bin':<3}  {'Elapsed(avg)':>13}  {'Elapsed CV%':>11}  {'CacheMiss%':>11}  {'LLCMiss%':>9}  {'IPC':>5}")
for db in DBS:
    for t in THREADS:
        for b in ["S0", "S1"]:
            runs = results[(db, t, b)]
            e, ecv = avg(runs, "elapsed"), cv(runs, "elapsed")
            c = avg(runs, "cachemiss"); l = avg(runs, "llcmiss"); i = avg(runs, "ipc")
            print(f"{db:<18}{t:>4}  {b:<3}  {e:>13.4f}  {ecv:>11.2f}  {c:>11.2f}  {l:>9.2f}  {i:>5.2f}")
