# teaching the 50MB ESKAPE db from the 103GB db (2026-10-14)

sir's question after the S8 slide: why run on 103GB at all. run one pod5 on both dbs, find the
genomes/pathogens the 50MB db misses or gets wrong, take those hashes and keys from the 103GB db,
append them to the 50MB db, and keep it ESKAPE only. this file is what was tried, what worked, and
what did not. every number is measured on luna (held-out pod5 files unless stated).

## 1. how big is the gap

one pod5 (`reads_hac.fastq`, 104,918 reads) through both dbs with the S19 binary, per-read calls compared
(`scripts/eskape_aug/gap_analysis.py`):

| bucket | 50MB | 103GB |
|---|---|---|
| P. aeruginosa | 55,077 | 43,630 |
| K. pneumoniae | 10,411 | 9,677 |
| A. baumannii | 0 (genome absent) | 341 |
| E. cloacae | 503 | 76 |
| other classified | 22,970 | 50,002 |
| unclassified | 15,945 (15.2%) | 1,191 (1.1%) |

the two dbs agree on the bucket for 67.1% of reads. the 33% disagreement splits into two different problems:

- **missed (recall)**: 103GB calls an ESKAPE species, 50MB calls unclassified/other: 6,962 reads (6.6%).
  mostly P. aeruginosa (4,150) and K. pneumoniae (1,853) reads from strains that are not the one reference genome.
- **wrong or too specific (precision)**: 50MB calls an ESKAPE species, 103GB calls something else: 19,240 reads (18.3%).
  12,487 are P. aeruginosa reads that 103GB calls plain genus *Pseudomonas*, the rest are
  K. pneumoniae vs Klebsiella / E. coli / K. quasipneumoniae and a few real cross-species errors.

## 2. why "just copy the hashes and keys across" cannot work

the header of `hash.k2d` (first 32 bytes) gives the cell layout:

| db | cells | keys | key bits | value bits |
|---|---|---|---|---|
| 50MB | 12,861,805 | 8,874,833 | 26 | 6 |
| 103GB | 27.75 billion | 19.4 billion | **16** | 16 |

a cell stores only the top `key_bits` of the 64-bit hash plus the taxon. in 103GB that is 16 bits, and
the position gives roughly 34 more, so about 50 of 64 hash bits are known: an estimated ~10,000 candidate minimizers
per cell. the keys cannot be read back out of the file, so the table cannot be enumerated or merged cell by cell.
(the same limit applies to the 50MB table, which is why it has to be regenerated from its genomes, section 3.)

## 3. what does work: teacher-gated transplant

keys cannot be listed, but they can be looked up. every read minimizer is a known key, so ask the 103GB db
("teacher") what it stores for it and write that into the small db ("student").
`scripts/eskape_aug/transplant.cc`, using stock kraken2 objects:

1. regenerate the student's own content from its 6 genomes + `seqid2taxid.map` into a table of any capacity
   (check against the real 50MB table: 17 sequences, 8,869,535 keys vs 8,873,809, 125 of 28,060,427 lookups differ).
2. **genome pass**: for every minimizer of the student's own genomes, `t = teacher.Get(m)`; if the teacher label
   is more general than the student's, move the student label up (LCA). no reads needed.
3. **read pass**: for every distinct minimizer of the training reads, `t = teacher.Get(m)`. absent in teacher means
   a sequencing-error k-mer and is skipped (this is the free error filter: 69% of the distinct read minimizers are absent).
   otherwise map `t` to the nearest ancestor that exists in the student taxonomy, and
   - if the student already has the key: set `LCA(old, mapped)` (always, any rank),
   - if not: add it, only if the teacher label is inside an allowed genus clade (the gate keeps the db ESKAPE-only).
4. extend the student taxonomy with the competitor taxa the teacher assigns to the training pod5
   (71 taxa with at least 25 reads inside an ESKAPE genus or Escherichia, plus A. baumannii).
   nodes 42 to 107, value bits 6 to 7, key bits 26 to 25.

the teacher value is already the LCA over every genome in 103GB, so an existing student entry can only
move up and absent entries get filled in. both dbs use k=35, l=31 and the same toggle mask, so keys are interchangeable.

## 4. results (held-out pod5_0 = 132,074 reads, never used for training)

agreement = fraction of reads where student and 103GB land in the same bucket (ESKAPE species / other / unclassified).

| variant | what it is | agree | unclassified | missed | wrong | table |
|---|---|---|---|---|---|---|
| 50MB original | 6 genomes | 65.6% | 15.1% | 6.6% | 19.7% | 51MB |
| V1 | precision only, no new keys (old gate) | 64.9% | 15.1% | 11.7% | 15.3% | 51MB |
| V2 | + new keys from 1 pod5 (old gate) | 80.2% | 3.8% | 2.6% | 15.1% | 13.4M keys |
| V3 | V2 but ESKAPE genera only (no Escherichia) | 78.9% | 4.4% | 2.6% | 15.8% | 12.8M keys |
| V4 | V2 + extended taxonomy | 82.0% | 3.6% | 2.4% | 13.5% | 13.4M keys |
| V5g | extended tax + genome pass, no reads | 55.3% | 15.1% | 35.9% | 0.4% | 8.9M keys |
| V5 | extended tax + genome pass + 1 pod5 | 91.5% | 3.6% | 5.3% | 0.9% | 13.4M keys |
| T3 | V5 with 3 pod5 (398k reads) | 93.6% | 3.5% | 3.3% | 0.9% | 14.8M keys |
| **T5 = final** | V5 with 5 pod5 (671k reads) | **94.4%** | **3.5%** | **2.5%** | **0.9%** | 15.7M keys, **90MB** |
| V6 | extended tax + genome pass + the 200 ESKAPE genomes, no reads | 78.3% | 8.5% | 15.2% | 0.7% | 25.4M keys |

pod5_15 (about 30,400 reads, also held out) gives the same picture: baseline 66.5%, V5 91.0%, T3 93.3%, T5 94.1%,
V6 77.7%.

species counts on pod5_0:

| species | 50MB | final 90MB | 103GB |
|---|---|---|---|
| P. aeruginosa | 70,327 | 52,102 | 54,082 |
| K. pneumoniae | 12,434 | 11,249 | 11,388 |
| A. baumannii | 0 | 369 | 375 |
| E. cloacae | 589 | 47 | 99 |
| other classified | 28,757 | 63,737 | 64,860 |
| unclassified | 19,963 | 4,570 | 1,270 |

## 5. what the experiments say

- **precision fix is universal, recall needs strain diversity.** the genome pass alone (V5g) drops false
  species calls from 19.7% to 0.4%, but with no new keys the db cannot reproduce the teacher's species-level calls,
  so reads fall to genus (missed 35.9%). the new keys (from reads in V5/T5, or from genomes in V6) restore it.
- **a gate bug plus a missing genome pass cost 9 points.** the first versions only generalized entries whose teacher label was inside an
  allowed genus or a family/order, so labels the teacher says are shared at phylum or domain level stayed at
  strain level (the student kept calling "P. aeruginosa PAO1" for reads the teacher calls Pseudomonas).
  the gate must apply only to new keys. V4 (82.0%) to V5 (91.5%) is this fix together with the genome pass; the two were
  not measured separately.
- **taxonomy nodes matter.** competitor species (Pseudomonas sp. p1(2021b), P. paraeruginosa, K. quasipneumoniae,
  E. coli) need their own node or their k-mers collapse into the genus and the tie that makes the teacher say
  "genus" never forms.
- **A. baumannii comes back with no genome**: 0 reads to 369 (teacher 375), because its k-mers enter from reads
  once the taxon exists in the taxonomy.
- **more training pod5 files help but flatten**: 91.5% (1) to 93.6% (3) to 94.4% (5); keys 13.4M, 14.8M, 15.7M.
- **keeping it ESKAPE-only costs about 1 point** (V2 vs V3) because E. coli is a real competitor in these reads.

## 6. size and speed (S19 binary, 32 threads, 1,872,777 reads, 3 interleaved reps)

| db | file | RAM | time |
|---|---|---|---|
| 50MB original | 51MB | 51MB | 7.9s |
| final student | 90MB | 90MB | 8.3s |
| 103GB teacher | 111GB | 111GB | 12.3s |

with the S19 build the big db is only 1.5x slower on luna because its load is now parallel and uses huge pages.
the student's advantage is memory: 1,200x smaller, so it runs on a machine that cannot hold 103GB
(orion has 64GB). on the stock binary the 103GB db took ~90s.

## 7. caveats

- **103GB is the reference, not the truth.** agreement with it is a measure of matching the project's gold-standard
  ceiling. where it says genus *Pseudomonas* for reads that are probably P. aeruginosa (NCBI has many P. aeruginosa
  assemblies filed under other names), matching it is less specific, not more correct. there is no ground-truth
  label for these reads.
- **the 94% is sample-adaptive.** training and test pod5 files are from the same sequencing run and organisms.
  the sample-independent number is V6 (78.3%): the 200 ESKAPE assemblies, no reads from this sample. the
  taxonomy extension list was also derived from the training pod5's teacher report.
- one held-out comparison per pod5 (two held-out files), single run each, no confidence intervals.
- the table was compacted to 69.8% load with capacity 22.5M; occupancy above that was not tested.
- reads are nanopore HAC reads; the error filter (absent in teacher) removes errors that happen to produce no
  teacher key but not errors that happen to produce a real k-mer.

## 8. what is still open

1. a cross-sample test: a different run, ideally a different species mix. this is what decides whether the read-driven
   part generalizes or is a per-sample cache of the teacher.
2. V6 + reads together, and more genomes (strain-diverse assemblies from the 103GB's own taxa) so recall does not
   need the sample at all.
3. choose the taxonomy extension without the sample (top competitors per genus from the teacher's own taxonomy).
4. combine with the bitmask cell from sir's thesis 2: 7 value bits now leave 25 key bits; the false-positive
   rate at 25 bits was not re-measured here.
5. the same transplant on orion (arm64) with the 90MB db: not run, orion unreachable.

## files

`scripts/eskape_aug/transplant.cc` (tool), `gap_analysis.py`, `eval_variants.sh`, `extra_taxids.txt`;
training logs in `data/eskape_aug/`. build: `g++ -O2 -std=c++11 -fopenmp -I. -o transplant transplant.cc
compact_hash.o mmap_file.o taxonomy.o mmscanner.o seqreader.o omp_hack.o utilities.o` inside a built stock
kraken2 `src/`.
