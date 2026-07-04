# Luna — Tool Installs

> Native Linux (no Hyper-V) — full hardware PMU counters available without workarounds.
> btop installed 2026-05-28 | numactl not yet installed
>  perf_event_paranoid = 4 (verified 2026-05-28) — hardware counters blocked for non-root. Fix below is #1 priority.

---

## Fix btop locale (no sudo needed)

```bash
# Temporary (every session)
btop --utf-force

# Permanent fix
echo 'export LANG=en_US.UTF-8' >> ~/.bashrc
echo 'export LC_ALL=en_US.UTF-8' >> ~/.bashrc
source ~/.bashrc
btop
```

---

## Needs sudo (chayanika)

### numactl — NUMA topology + memory binding
```bash
sudo apt install numactl
numactl --hardware     # see NUMA memory layout
numactl --show         # current NUMA policy
```

### perf_event_paranoid — enable hardware counters for all users
```bash
# Check current value (should be ≤1)
cat /proc/sys/kernel/perf_event_paranoid

# Set to 1 if it shows 4 (blocks hardware events)
sudo sysctl -w kernel.perf_event_paranoid=1
echo 'kernel.perf_event_paranoid=1' | sudo tee /etc/sysctl.d/99-perf.conf
```

### LIKWID — hardware counters + memory bandwidth per NUMA node
```bash
git clone https://github.com/RRZE-HPC/likwid ~/likwid-src
cd ~/likwid-src
make -j$(nproc)
sudo make install
sudo modprobe msr
echo 'msr' | sudo tee -a /etc/modules
sudo chmod +s /usr/local/bin/likwid-perfctr /usr/local/bin/likwid-pin
likwid-perfctr --version
```

### Intel VTune — CPI waterfall, memory stall analysis
```bash
# Download from https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html
chmod +x vtune_installer.sh
sudo ./vtune_installer.sh -a --eula accept --install-dir /opt/intel/vtune
echo 'source /opt/intel/vtune/latest/env/vars.sh' | sudo tee /etc/profile.d/vtune.sh
source /etc/profile.d/vtune.sh
vtune --version
```

### DCGM — GPU power/thermal monitoring during Dorado runs
```bash
wget <dcgm-ubuntu2204-deb-url> -O ~/dcgm.deb
sudo dpkg -i ~/dcgm.deb
sudo systemctl enable nvidia-dcgm && sudo systemctl start nvidia-dcgm
dcgmi discovery -l
```

### valgrind — cachegrind (per-function LLC miss rates)
```bash
sudo apt install valgrind
valgrind --version
```

---

## Per user, no sudo

### FlameGraph — SVG call graphs from perf record
```bash
git clone https://github.com/brendangregg/FlameGraph ~/FlameGraph
```

### gperftools / pprof — low-overhead CPU sampling
```bash
# via conda if available, else:
sudo apt install google-perftools libgoogle-perftools-dev
```

### Kraken-2 with profiling flags
```bash
git clone https://github.com/DerrickWood/kraken2 ~/kraken2-src
cd ~/kraken2-src
sed -i 's/CXXFLAGS=/CXXFLAGS=-pg -g /' src/Makefile
./install_kraken2.sh ~/kraken2-build-pg
```

### Dorado
```bash
wget https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-linux-x64.tar.gz
tar -xzf dorado-1.4.0-linux-x64.tar.gz
```

---

## Luna-Specific: AVX-512 + AMX matrix multiply variants

Luna's Xeon Platinum 8468 supports AVX-512 (8 doubles/instruction vs AVX2's 4)
and AMX (hardware matrix tile multiply unit). Worth building extra variants:

```bash
# AVX-512 version of matmul (see avx512_manual.c when written)
gcc -O3 -march=native -mavx512f -mfma -o avx512_manual avx512_manual.c

# Check AMX support
grep -m1 amx /proc/cpuinfo

# Intel AMX requires OS support (XSAVE for tile registers)
# Check: xgetbv should show tile state enabled
```

---

## Luna perf — full event set (works here, blocked on WSL2)

```bash
perf stat -e \
  cycles,instructions,\
  cache-misses,cache-references,\
  LLC-load-misses,LLC-loads,\
  L1-dcache-load-misses,L1-dcache-loads,\
  stalled-cycles-backend,stalled-cycles-frontend,\
  mem-loads,mem-stores \
  ./tiled_avx2 1024
```

### TMA (Top-down Microarchitecture Analysis) — Sapphire Rapids native
```bash
# Direct TMA metrics (no VTune needed)
perf stat -e \
  tma_memory_bound,tma_core_bound,\
  tma_backend_bound,tma_frontend_bound,\
  tma_l1_bound,tma_l2_bound,tma_l3_bound,tma_dram_bound \
  ./naive_ijk 1024
```
