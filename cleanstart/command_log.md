# cleanstart command log

every command actually run, in order: why, then result. same pattern as cache_simulation/command_log.md.

---

### [0] 2026-09-19 - folder created on this machine

created `cleanstart/` in the repo root (README.md + this file). Luna copy: `~/cleanstart` (created by hand, see step 1).

---

### [1] 2026-09-19 - Luna inventory check + create ~/cleanstart

```bash
ssh -i ~/.ssh/luna_claude student@luna.cse.iitd.ac.in 'mkdir -p ~/cleanstart && ls -la <S0 classify> <luna.cfg> <laptop.cfg>; ls -d ~/chirag_K/AccuracyDrift/databases/*/; find ~ -name "*.pod5" -size +1G'
```

**why:** confirm S0 binary, hardware configs, databases, and any existing large pod5 exist before choosing the fixed baseline. ssh access to Luna works from this machine (key `~/.ssh/luna_claude`), older notes saying it does not are out of date.

**result:**
- S0 classify exists: `~/chirag_K/tools/kraken2-src-baseline/src/classify` (264 KB, built Aug 3)
- `luna.cfg` (Sep 8) and `laptop.cfg` (Sep 15) exist in `~/cache_simulation/snipersim/config/`
- databases: standard_8gb, standard_16gb, pluspf_103gb, sample_targeted, eskape_genomes, plus centrifuge/centrifuger/metabuli ones
- pod5 files over 1 GB already on Luna: `~/chirag_K/data/pod5/fbe/FBE01990_24778b97_03e50f91_{0,3,5,6,7,9,10,11,13,14}.pod5` (at least 10, so no need to fetch one)
- `~/cleanstart` created, empty

---

### [2] 2026-09-19 - fix the inputs: reads file + 3 databases

```bash
ssh ... 'du -sh ~/chirag_K/AccuracyDrift/databases/*/; find ~ -name "*.fastq" -size +50M | count reads (wc -l / 4)'
ssh ... 'ls -lh .../sample_targeted/ .../standard_8gb/ .../standard_16gb/'
```

**why:** CK asked for any pod5, 3 databases (50 MB, 8 GB, 16 GB), and a fastq with ~104K reads. instead of basecalling again, look for an existing fastq near 104K.

**result:**
- reads: `~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_10.fastq` = **104,980 reads**, 723 MB (sup basecall of pod5 `_10`). closest to 104K of the existing fastqs. no dorado run needed.
- 50 MB db = `sample_targeted` (`hash.k2d` is exactly 50 MB, same db the old "50mb" runs used). 8 GB = `standard_8gb` (7.6 GB). 16 GB = `standard_16gb` (`hash.k2d` 15 GB).
- caveat: detailed-mode Sniper cannot run 104K reads. each run will use a fixed slice, size to be decided next.

---

### [3] 2026-09-19 - create 10/50/100-read slices on Luna

```bash
SRC=~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_10.fastq; W=~/cleanstart/workloads; mkdir -p $W
for n in 10 50 100; do head -n $((n*4)) $SRC > $W/reads_$n.fastq; done
```

**why:** CK chose 10, 50 and 100 reads per run (3 read counts x 3 databases = 9 workloads per hardware setting). fastq = 4 lines per read, so `head -n 4N` takes the first N reads. slices are nested prefixes of one file, so runs differ only in amount of work, not in which reads are used. kept separate from the old `cache_simulation/workloads` so nothing old is reused by accident.

**result:** all three verified (read count = N, same first read id `@eee06777-c6a0-45dc-8f87-edbc7fa56f2d`):

| file | reads | size | total bases |
|---|---|---|---|
| reads_10.fastq | 10 | 732 KB | 372,413 |
| reads_50.fastq | 50 | 4.3 MB | 2,209,336 |
| reads_100.fastq | 100 | 11 MB | 5,262,723 |

base count grows unevenly (read lengths vary a lot), so "100 reads" is ~14x the work of "10 reads", not 10x.
