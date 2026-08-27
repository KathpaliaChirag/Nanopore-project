import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
BINS = {
    "S0":            "/home/student/tools/kraken2-fresh-bin-s0/kraken2",
    "S1":            "/home/student/tools/kraken2-fresh-bin-s1/kraken2",
    "S2-nested":     "/home/student/tools/kraken2-fresh-bin-s2/kraken2",
    "S2-standalone": "/home/student/tools/kraken2-fresh-bin-s2-standalone/kraken2",
}
DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 16, 32, 64, 96]
RUNS = 3  # interleaved across all 4 binaries per cell, same fairness reasoning as every prior comparison this session

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
    # only the standalone binary prints this line - nested S2 has no
    # instrumentation (that's exactly the gap this whole exercise exists to fix)
    hitrate = re.search(r"\[S2-STANDALONE\] hits=(\d+) misses=(\d+) total=(\d+) hit_rate=([\d.]+)%", out)
    return {
        "elapsed": float(elapsed.group(1)) if elapsed else None,
        "llcmiss": float(llcmiss.group(1)) if llcmiss else None,
        "hits": int(hitrate.group(1)) if hitrate else None,
        "misses": int(hitrate.group(2)) if hitrate else None,
        "hit_rate": float(hitrate.group(4)) if hitrate else None,
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
print(f"{'DB':<18}{'T':>4}  {'Bin':<14}  {'Elapsed(avg)':>13}  {'CV%':>6}  {'LLCMiss%':>9}  {'HitRate%':>9}")
for db in DBS:
    for t in THREADS:
        for b in BINS:
            runs = results[(db, t, b)]
            e, ecv = avg(runs, "elapsed"), cv(runs, "elapsed")
            l = avg(runs, "llcmiss")
            hr = avg(runs, "hit_rate")
            hr_str = f"{hr:.4f}" if hr == hr else "n/a"  # NaN check - only S2-standalone has this
            print(f"{db:<18}{t:>4}  {b:<14}  {e:>13.4f}  {ecv:>6.2f}  {l:>9.2f}  {hr_str:>9}")
