#!/bin/bash
# Build the 175-genome ESKAPE database (eskape_big) from NCBI RefSeq.
#
# Produces:  databases/eskape_big/{hash.k2d,taxo.k2d,opts.k2d}  208 MB
#            plus library/ (175 .fna), seqid2taxid.map, taxonomy/
# Then optionally the -M subsampled variants (48 MB and 16 MB).
#
# Needs the IITD proxy for NCBI (https_proxy is already in the environment).
# Runtime: ~20 min download + ~20 min per build_db pass. Run builds one at a time.
set -euo pipefail
cd /home/dell/summer

OUT=databases/eskape_big
BIN=/home/dell/summer/kraken2_bin
N=${N:-25}                 # genomes per species
SEED=1111111111111111101010101010101   # l=31, 7 minimizer spaces (kraken2 default)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# species dir on the NCBI FTP  ->  NCBI species taxid
declare -A SPECIES=(
  [Enterococcus_faecium]=1352       # E
  [Staphylococcus_aureus]=1280      # S
  [Klebsiella_pneumoniae]=573       # K
  [Acinetobacter_baumannii]=470     # A   <-- absent from the old 6-genome library
  [Pseudomonas_aeruginosa]=287      # P
  [Enterobacter_cloacae]=550        # E   (genus 547; see note at the end)
  [Escherichia_coli]=562            # not ESKAPE, but 5,172 reads in our samples
)

mkdir -p "$OUT/library" "$OUT/taxonomy" "$TMP/dl"

# ---- 1. per-species assembly catalogue, and pick N genomes -------------------
: > "$TMP/list.tsv"
for sp in "${!SPECIES[@]}"; do
  curl -sfL "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/bacteria/$sp/assembly_summary.txt" \
       -o "$TMP/$sp.txt"
  # columns: 1 accession, 5 refseq_category, 11 version_status,
  #          12 assembly_level, 20 ftp_path
  python3 - "$sp" "${SPECIES[$sp]}" "$N" "$TMP/$sp.txt" >> "$TMP/list.tsv" <<'PY'
import sys
sp, tid, n, path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
rows=[]
for line in open(path):
    if line.startswith('#'): continue
    f=line.rstrip('\n').split('\t')
    if len(f)<20 or f[10]!='latest' or f[11]!='Complete Genome': continue
    rows.append((f[4], f[0], f[19]))
# reference/representative genomes first, then evenly spaced through the rest,
# so the sample spans the species instead of clustering by submission date
ref =[r for r in rows if r[0] in ('reference genome','representative genome')]
rest=[r for r in rows if r[0] not in ('reference genome','representative genome')]
pick=ref[:n]
need=n-len(pick)
if need>0 and rest:
    pick+=rest[::max(1,len(rest)//need)][:need]
for _,acc,ftp in pick:
    fn=ftp.rstrip('/').split('/')[-1]+'_genomic.fna.gz'
    print(f"{sp}\t{tid}\t{acc}\t{ftp}/{fn}")
PY
  printf '  %-26s %3d selected\n' "$sp" "$(grep -c "^$sp" "$TMP/list.tsv")"
done
echo "total selected: $(wc -l < "$TMP/list.tsv")"

# ---- 2. download ------------------------------------------------------------
# NOTE: curl 7.81 on this box has no --remove-on-error, so download to a temp
# name and move on success; a failed transfer must not leave a truncated .fna.gz
ok=0; fail=0
while IFS=$'\t' read -r sp tid acc url; do
  dest="$OUT/library/${sp}__${acc}.fna"
  [ -s "$dest" ] && { ok=$((ok+1)); continue; }
  if curl -sfL "$url" -o "$TMP/dl/$acc.gz" </dev/null && [ -s "$TMP/dl/$acc.gz" ]; then
    gunzip -c "$TMP/dl/$acc.gz" > "$dest"; ok=$((ok+1))
  else
    fail=$((fail+1)); echo "  FAIL $acc"
  fi
done < "$TMP/list.tsv"
echo "downloaded ok=$ok fail=$fail"

# ---- 3. seqid2taxid.map: every contig -> its SPECIES taxid ------------------
# species-level, not strain-level, so the database answers at rank S
: > "$OUT/seqid2taxid.map"
while IFS=$'\t' read -r sp tid acc url; do
  f="$OUT/library/${sp}__${acc}.fna"
  [ -s "$f" ] || continue
  grep '^>' "$f" | sed "s/^>\([^ ]*\).*/\1\t$tid/" >> "$OUT/seqid2taxid.map"
done < "$TMP/list.tsv"
echo "seqid2taxid.map: $(wc -l < "$OUT/seqid2taxid.map") contigs"

# ---- 4. NCBI taxonomy ------------------------------------------------------
if [ ! -s "$OUT/taxonomy/nodes.dmp" ]; then
  curl -sfL https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -o "$TMP/taxdump.tar.gz"
  tar -xzf "$TMP/taxdump.tar.gz" -C "$OUT/taxonomy" nodes.dmp names.dmp
fi

# ---- 5. size the table -----------------------------------------------------
EST=$(cat "$OUT"/library/*.fna | "$BIN/estimate_capacity" -k 35 -l 31 -S "$SEED" -p 4 | tail -1)
CAP=$(python3 -c "print(int($EST/0.70/1e6+1)*1000000)")   # 70% load, rounded up
echo "distinct minimizers ~$EST  ->  -c $CAP"

# ---- 6. build --------------------------------------------------------------
# -p 1 is MANDATORY: multi-threaded build_db segfaults on this hardware.
cat "$OUT"/library/*.fna | "$BIN/build_db" \
    -H "$OUT/hash.k2d" -t "$OUT/taxo.k2d" -o "$OUT/opts.k2d" \
    -n "$OUT/taxonomy" -m "$OUT/seqid2taxid.map" \
    -c "$CAP" -k 35 -l 31 -p 1 -S "$SEED" 2>&1 | tee "$OUT/build.log"

# ---- 7. optional -M variants, one at a time --------------------------------
# -M/-c sets the skip threshold: min_acceptable_hash_value = (1 - M/c) * 2^64.
# Stay at or below ~80% skip; beyond that the -T confidence score collapses.
for M in 12000000 4000000; do
  V="databases/eskape_big_M$M"; mkdir -p "$V"
  cat "$OUT"/library/*.fna | "$BIN/build_db" \
      -H "$V/hash.k2d" -t "$V/taxo.k2d" -o "$V/opts.k2d" \
      -n "$OUT/taxonomy" -m "$OUT/seqid2taxid.map" \
      -c "$CAP" -M "$M" -k 35 -l 31 -p 1 -S "$SEED" 2>&1 | tee "$V/build.log"
done

# KNOWN GAP: the "E" of ESKAPE is the Enterobacter GENUS (547), not E. cloacae.
# Our samples' dominant Enterobacter is E. hormaechei (83 reads vs cloacae's 36),
# which has 668 complete RefSeq genomes to cloacae's 82. Add Enterobacter_hormaechei,
# _asburiae, _kobei, _roggenkampii, _bugandensis to SPECIES above to fix it.
# KNOWN GAP: no decoy set. See reports/findings/ESKAPE_DB_REPORT.md section 7.2.
