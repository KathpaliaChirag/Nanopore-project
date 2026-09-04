# Luna - knowledge base

Luna is a Dell R760 server at IIT Delhi. You'll use it for profiling and running Nanopore bioinformatics pipelines.
Login: `student@luna.cse.iitd.ac.in`
Internet needs the IITD proxy: run `python3 ~/iitd-login.py -d` inside a tmux session.

---

## Files in this folder

Everything below lives in this folder so you know where to look before hunting through the rest of the repo.

| File | Purpose |
|---|---|
| bash_history.md | every command run on Luna, with explanations and status |
| luna_stats.md | hardware specs, storage, GPU, perf counter status, tool inventory |
| install_tools.md | installation commands for all tools |
| user_guide.md | SSH login, internet setup, first steps for new users |
| user_management.md | adding users, giving sudo, copying tools to new accounts |
| profiling/plan.md | 4-phase profiling plan: matmul, Kraken2, Dorado, AMX |
| profiling/results_kraken2.md | Kraken2 profiling results |
| profiling/results_dorado.md | Dorado GPU profiling results |
| profiling/results_matmul_luna.md | matrix multiply benchmark results on Luna |

---

## Hardware summary

You need these numbers before interpreting any profiling result on Luna, since cache and DRAM behavior only make sense against the real topology.

| Property | Value |
|---|---|
| CPU | 2x Intel Xeon Platinum 8468 (Sapphire Rapids) |
| Cores | 96 physical / 192 logical |
| L3 Cache | 210 MB total |
| RAM | 503 GB |
| GPU | 2x NVIDIA L40S (46 GB VRAM each) |
| CUDA | 12.9 |
| Storage | 938 GB root, 238 GB free (as of 2026-05-29) |
| OS | Ubuntu 22.04 LTS, kernel 6.8.0-78 |

---

## Tools installed (as of 2026-05-29)

| Tool | Path | Version |
|---|---|---|
| perf | /usr/bin/perf | 6.8.12 |
| gprof | /usr/bin/gprof | binutils |
| kraken2 | ~/tools/kraken2/kraken2 | 2.1.3 |
| dorado | ~/tools/dorado/bin/dorado | 1.4.0 |
| flamegraph.pl | ~/tools/FlameGraph/flamegraph.pl | latest |
| numactl | /usr/bin/numactl | - |
| valgrind | /usr/bin/valgrind | 3.18.1 |
| gperftools | apt | - |

nsys/ncu/nvcc aren't confirmed in PATH yet - still need to run `find /usr /opt -name nsys`.

---

## Data on Luna (as of 2026-05-29)

| Path | Contents |
|---|---|
| ~/data/pod5/ | FBE01990_24778b97_03e50f91_10.pod5 (~4GB raw nanopore signals) |
| ~/data/kraken2_db/ | standard-8 pre-built database (k2_standard_08gb_20240112) |

---

## Directory structure on Luna

```
~/
├── archives/         tarballs and scratch files
├── data/
│   ├── kraken2_db/   standard-8 database
│   └── pod5/         raw nanopore signal files
├── results/
│   ├── basecalling/  dorado output (fastq, bam)
│   ├── classification/ kraken2 output
│   └── profiling/    perf, nsys, flamegraph outputs
├── scripts/          run scripts
├── tools/
│   ├── dorado/
│   ├── FlameGraph/
│   ├── kraken2/
│   └── kraken2-src/
└── iitd-login.py
```

---

## Current status

- all tools installed and verified working
- pod5 file and kraken2 database in place
- next: Dorado basecalling run, then Kraken2 classification, then profiling
