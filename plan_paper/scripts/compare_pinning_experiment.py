import subprocess, re, statistics

FASTQ = "/home/student/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq"
DBDIR = "/home/student/AccuracyDrift/databases"
# (binary path, expected size) - the expected size is cross-checked against
# what the binary itself prints, so a build mixup gets caught immediately
# instead of silently mislabeling results.
BINS = {
    "RR-4096":       ("/home/student/tools/kraken2-fresh-bin-s2-standalone/kraken2", 4096),
    "RR-65536":      ("/home/student/tools/kraken2-fresh-bin-s2-standalone-65536/kraken2", 65536),
    "RR-262144":     ("/home/student/tools/kraken2-fresh-bin-s2-standalone-262144/kraken2", 262144),
    "Pinned-4096":   ("/home/student/tools/kraken2-fresh-bin-s2-pinned/kraken2", 4096),
    "Pinned-65536":  ("/home/student/tools/kraken2-fresh-bin-s2-pinned-65536/kraken2", 65536),
    "Pinned-262144": ("/home/student/tools/kraken2-fresh-bin-s2-pinned-262144/kraken2", 262144),
}
DBS = ["sample_targeted", "standard_8gb", "pluspf_103gb"]
THREADS = [1, 16, 32, 64, 96]
RUNS = 3

def run_once(binary, db, threads, expected_size):
    cmd = ["perf", "stat", "-e",
           "cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles",
           "numactl", "--cpunodebind=0", "--membind=0",
           binary, "--db", f"{DBDIR}/{db}", "--threads", str(threads),
           "--output", "/dev/null", "--report", "/dev/null", FASTQ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    elapsed = re.search(r"([\d.]+) seconds time elapsed", out)
    llcmiss = re.search(r"#\s+([\d.]+)% of all LL-cache accesses", out)
    stat = re.search(r"\[S2-(?:STANDALONE|PINNED)\] size=(\d+) ways=(\d+) hits=(\d+) misses=(\d+) total=(\d+) hit_rate=([\d.]+)%", out)
    size_ok = None
    if stat:
        actual_size = int(stat.group(1))
        size_ok = (actual_size == expected_size)
        if not size_ok:
            print(f"  !! SIZE MISMATCH: expected {expected_size}, binary reports {actual_size}", flush=True)
    return {
        "elapsed": float(elapsed.group(1)) if elapsed else None,
        "llcmiss": float(llcmiss.group(1)) if llcmiss else None,
        "hit_rate": float(stat.group(6)) if stat else None,
        "size_ok": size_ok,
    }

results = {}
for db in DBS:
    for t in THREADS:
        for b in BINS:
            results[(db, t, b)] = []
        for i in range(RUNS):
            for b, (path, exp_size) in BINS.items():
                results[(db, t, b)].append(run_once(path, db, t, exp_size))
        print(f"done: {db} T={t}", flush=True)

def avg(runs, field):
    vals = [r[field] for r in runs if r[field] is not None]
    return statistics.mean(vals) if vals else float("nan")
def cv(runs, field):
    vals = [r[field] for r in runs if r[field] is not None]
    if len(vals) < 2 or statistics.mean(vals) == 0: return float("nan")
    return 100 * statistics.stdev(vals) / statistics.mean(vals)

# Flag if any run's binary reported an unexpected size - printed once at
# the end so a mismatch can't get lost in 270 runs of output.
bad = [(db, t, b) for (db, t, b), runs in results.items() for r in runs if r["size_ok"] is False]
if bad:
    print(f"\n!!! {len(bad)} SIZE-MISMATCH RUNS FOUND - see 'SIZE MISMATCH' lines above, do not trust results until resolved !!!\n")
else:
    print("\nAll binaries reported their expected size on every run - safe to trust the table below.\n")

print(f"{'DB':<18}{'T':>4}  {'Bin':<14}  {'Elapsed(avg)':>13}  {'CV%':>6}  {'LLCMiss%':>9}  {'HitRate%':>9}")
for db in DBS:
    for t in THREADS:
        for b in BINS:
            runs = results[(db, t, b)]
            e, ecv = avg(runs, "elapsed"), cv(runs, "elapsed")
            l = avg(runs, "llcmiss")
            hr = avg(runs, "hit_rate")
            print(f"{db:<18}{t:>4}  {b:<14}  {e:>13.4f}  {ecv:>6.2f}  {l:>9.2f}  {hr:>9.4f}")
