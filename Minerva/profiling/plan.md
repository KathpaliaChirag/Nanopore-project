# Minerva Profiling Pipeline — Plan

## Context

WSL2 profiling confirmed the bottlenecks (report.md / report1.md):
- **Kraken-2**: memory-bound — 34.24% cache miss rate, 67% runtime in `CompactHashTable::Get()`, IPC = 0.55
- **Dorado**: compute-bound — 82% GPU time is GEMM

Minerva gives us what WSL2 *cannot*:
1. Real `LLC-load-misses` hardware counters (Hyper-V blocks these on WSL2)
2. Accurate IPC (WSL2 clock distorted — 0.734 GHz, unreliable)
3. Per-function LLC miss rates via cachegrind (251 GB RAM holds 8 GB DB in memory — faster)
4. Full ncu metrics on A40 (GTX 1650 on WSL2 couldn't expose SM throughput properly)

**Timeline:** 1–2 months. Goal is the most complete profiling picture possible — install and use every tool.

---

## Phase 1 — Sudo Actions (do first, before access expires)

### 1.1 perf paranoia — MOST CRITICAL
```bash
sudo sysctl -w kernel.perf_event_paranoid=1
echo 'kernel.perf_event_paranoid = 1' | sudo tee /etc/sysctl.d/99-perf.conf
cat /proc/sys/kernel/perf_event_paranoid   # verify: prints 1
```
> paranoia=1 allows hardware counters + perf record for regular users.
> We don't need `-a` system-wide mode so 1 is safe on a shared server.

### 1.2 Fix nsys PATH (nsys installed at /usr/lib/nsight-systems/bin/nsys but not on PATH)
```bash
echo 'export PATH=/usr/lib/nsight-systems/bin:$PATH' | sudo tee /etc/profile.d/nsys.sh
source /etc/profile.d/nsys.sh
nsys --version   # verify
```

### 1.3 Load LIKWID kernel module (sudo, after LIKWID is installed via conda/source)
```bash
sudo modprobe msr
echo 'msr' | sudo tee -a /etc/modules
sudo chmod +s $(which likwid-perfctr)
sudo chmod +s $(which likwid-pin)
```

### 1.4 Install Intel VTune (standalone .sh installer — no apt)
```bash
# Transfer installer from local machine to Minerva first, then:
chmod +x ~/vtune_installer.sh
sudo ~/vtune_installer.sh -a --eula accept --install-dir /opt/intel/vtune
echo 'source /opt/intel/vtune/latest/env/vars.sh' | sudo tee /etc/profile.d/vtune.sh
source /etc/profile.d/vtune.sh
vtune --version   # verify
```

### 1.5 Install DCGM (dpkg — no apt)
```bash
# Download .deb from https://developer.nvidia.com/dcgm then:
sudo dpkg -i ~/dcgm.deb
sudo systemctl enable nvidia-dcgm
sudo systemctl start nvidia-dcgm
dcgmi discovery -l   # verify: should list both A40 GPUs
```

### 1.6 Per-user tool installs (no sudo — see Minerva/install_tools.md)
valgrind, heaptrack, gperftools, LIKWID, FlameGraph — installed per user via conda or source.
```bash
# Each user runs this themselves:
git clone https://github.com/brendangregg/FlameGraph ~/FlameGraph
# See install_tools.md for valgrind/heaptrack/gperftools/LIKWID via conda
```

---

## Phase 2 — Data Setup (as CK user)

### 2.1 Transfer data from WSL2
```bash
rsync -avP ~/barcode02.fastq CK@minerva:~/
rsync -avP ~/eskape_db/ CK@minerva:~/k2_standard_08gb/
```

### 2.2 Build Kraken-2 with profiling flags
```bash
git clone https://github.com/DerrickWood/kraken2 ~/kraken2-src
cd ~/kraken2-src
sed -i 's/CXXFLAGS=/CXXFLAGS=-pg -g /' src/Makefile   # src/Makefile not root Makefile
./install_kraken2.sh ~/kraken2-build-pg
~/kraken2-build-pg/classify --version   # verify
```

---

## Phase 3 — Kraken-2 CPU Profiling

Run in this order. Kick off 3.8 (cachegrind) last as it runs for 30 min.

### 3.1 perf stat — real LLC counters (~2 min)
```bash
pv ~/barcode02.fastq | perf stat \
  -e cycles,instructions,cache-misses,cache-references,LLC-load-misses,LLC-loads,branch-misses \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_perf.txt - > /dev/null
```

| Metric | WSL2 | Minerva target |
|---|---|---|
| cache miss rate | 34.24% | real hardware value |
| LLC-load-misses | `<not supported>` | actual count |
| IPC | unreliable (0.734 GHz) | expect ~0.5, confirms memory stall |

LLC miss rate = `LLC-load-misses / LLC-loads × 100`

### 3.2 perf record + flame graph (~2 min)
```bash
pv ~/barcode02.fastq | perf record -g -F 999 \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_perf_record.txt - > /dev/null

perf report --stdio | head -60
perf script | ~/FlameGraph/stackcollapse-perf.pl | ~/FlameGraph/flamegraph.pl \
  > ~/kraken2_flame.svg
```

### 3.3 gprof — reproducibility check (~2 min)
```bash
pv ~/barcode02.fastq | ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_gprof.txt - > /dev/null
gprof ~/kraken2-build-pg/classify gmon.out | head -40
```
WSL2 baseline: 67.35% `CompactHashTable::Get()`, 18.74% `MinimizerScanner::NextMinimizer()`.

### 3.4 Intel VTune — microarchitecture + memory access (~5 min)
```bash
vtune -collect memory-access \
  -result-dir ~/vtune_mem \
  -- ~/kraken2-build-pg/classify \
     -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
     -o ~/k2_standard_08gb/opts.k2d -R ~/report_vtune.txt \
     < ~/barcode02.fastq > /dev/null
vtune -report summary -result-dir ~/vtune_mem
```
Adds: per-source-line memory stall attribution, CPI waterfall, NUMA access patterns across 2 sockets.

### 3.5 LIKWID — memory bandwidth per NUMA node (~2 min)
```bash
sudo modprobe msr
likwid-perfctr -C 0 -g MEM_DP \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_likwid.txt \
  < ~/barcode02.fastq > /dev/null
```
Adds: memory bandwidth in GB/s vs Xeon 6330 theoretical ceiling (~230 GB/s dual-socket).

### 3.6 gperftools/pprof — low-overhead sampling (~2 min)
```bash
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libprofiler.so CPUPROFILE=~/gperf.prof \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_gperf.txt \
  < ~/barcode02.fastq > /dev/null
pprof --text ~/kraken2-build-pg/classify ~/gperf.prof | head -30
pprof --svg ~/kraken2-build-pg/classify ~/gperf.prof > ~/gperf_callgraph.svg
```

### 3.7 heaptrack — heap allocation analysis (~2 min)
```bash
heaptrack ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_heap.txt \
  < ~/barcode02.fastq > /dev/null
heaptrack_print heaptrack.classify.*.gz | head -50
```
Adds: where Kraken-2 allocates heap memory and how much.

### 3.8 cachegrind — per-function LLC miss rates (~30 min, start last)
```bash
pv ~/barcode02.fastq | valgrind --tool=cachegrind \
  --cachegrind-out-file=$HOME/cg.out \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_cg.txt - > /dev/null
cg_annotate --auto=yes ~/cg.out > ~/cachegrind_report.txt
head -80 ~/cachegrind_report.txt
```
Record: `DLmr` count for `CompactHashTable::Get()` — per-function LLC data unavailable on WSL2.

### 3.9 perf mem — memory latency (~2 min, optional)
```bash
pv ~/barcode02.fastq | perf mem record \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_mem.txt - > /dev/null
perf mem report --stdio | head -40
```

---

## Phase 4 — Dorado GPU Profiling

**Prerequisite:** confirm a `.pod5` file is accessible on Minerva before starting.

### 4.1 Get Dorado if not present
```bash
wget https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-linux-x64.tar.gz
tar -xzf dorado-1.4.0-linux-x64.tar.gz
DORADO=~/dorado-1.4.0-linux-x64/bin/dorado
POD5=~/data/file.pod5   # adjust to actual path
```

### 4.2 nsys — full GPU timeline (~10–20 min)
```bash
nsys profile \
  --output ~/results/dorado_fast_profile \
  --trace cuda,nvtx \
  --stats true \
  -- $DORADO basecaller fast $POD5 --output-dir ~/results/bam_fast
```
WSL2 baseline: 82% GEMM, `cudaStreamSynchronize` = 98.9% of CUDA API time.

### 4.3 ncu — per-kernel metrics on A40 (~15 min)
```bash
ncu --metrics \
  sm__throughput.avg.pct_of_peak_sustained_elapsed,\
  dram__throughput.avg.pct_of_peak_sustained_elapsed,\
  sm__warps_active.avg.pct_of_peak_sustained_active \
  --output ~/results/ncu_report \
  -- $DORADO basecaller fast $POD5 --output-dir ~/results/bam_ncu
```

### 4.4 DCGM — power + thermal during run
```bash
dcgmi stats --enable -g 0
$DORADO basecaller fast $POD5 --output-dir ~/results/bam_dcgm
dcgmi stats --disable -g 0
dcgmi stats -g 0 -j
```
Adds: power draw over time, temperature under load, sustained vs burst perf — detects thermal throttling.

### 4.5 Compare fast vs hac under nsys
Run both models. Key question: same GEMM bottleneck or does hac shift it?

---

## Execution Order and Time

```
Phase 1 (sudo)           NOW       ~20 min   one-time installs
Phase 2 (data + build)   next      ~30 min

Phase 3.1 perf stat      ~2 min    ← start here (highest value)
Phase 3.2 perf record    ~2 min
Phase 3.3 gprof          ~2 min
Phase 3.4 VTune          ~5 min
Phase 3.5 LIKWID         ~2 min
Phase 3.6 gperftools     ~2 min
Phase 3.7 heaptrack      ~2 min
Phase 3.8 cachegrind     ~30 min   ← kick off, leave running
Phase 3.9 perf mem       ~2 min    ← run in parallel with cachegrind

Phase 4.1 nsys           ~10–20 min
Phase 4.2 ncu            ~15 min
Phase 4.3 DCGM           runs during 4.1
Phase 4.4 fast vs hac    ~30 min total

Total active time:   ~2 hours
Total wall time:     ~2.5 hours
```

---

## Verification (pass/fail)

| Check | Pass condition |
|---|---|
| Phase 1 | `perf_event_paranoid` = 1; valgrind, nsys, vtune, likwid all return version strings |
| Phase 3.1 | LLC counters show real numbers, not `<not supported>` |
| Phase 3.1 | IPC ~0.5, matches AMD uProf 0.55 |
| Phase 3.3 | `CompactHashTable::Get()` ~67% — reproducible across hardware |
| Phase 3.4 | VTune CPI waterfall shows memory-stall dominant |
| Phase 3.5 | LIKWID shows memory bandwidth in GB/s |
| Phase 3.8 | `DLmr` for `CompactHashTable::Get()` is nonzero and dominant |
| Phase 4.2 | nsys shows GEMM-dominant pattern on A40 |
| Phase 4.3 | SM throughput % on A40 is a real number |
