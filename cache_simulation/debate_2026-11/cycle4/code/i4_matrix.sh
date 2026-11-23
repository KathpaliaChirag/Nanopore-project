#!/bin/bash
# i4_matrix.sh: cycle 4 round 5, agent I4. end-to-end check that bin_trunc (parallel reader + pre-pass + exact tail replay)
# is byte-identical to stock S19 on truncated and malformed FASTQ. tiny inputs only (<= 6 MB), db sample_targeted, threads <= 8.
#   usage: bash i4_matrix.sh [group ...]   groups: c multi sweep big control   (default: all)
set -u
H=$HOME
STOCK=${STOCK:-$H/chirag_K/tools/kraken2-fresh-bin-s19}
NEW=${NEW:-$H/e1/bin_trunc}
DB=$H/chirag_K/AccuracyDrift/databases/sample_targeted
W=/dev/shm/i4_$$
SRC=$H/chirag_K/results/per_pod5_fastq/pod5_0.fastq
mkdir -p $W/in $W/res
NP=0; NF=0; EXTRA=${EXTRA:-}
GROUPS_WANTED=${*:-"c multi sweep big control"}
want() { for g in $GROUPS_WANTED; do [ "$g" = "$1" ] && return 0; done; return 1; }

cat > $W/gen.pl <<'PERL'
use strict; use warnings;
my ($mode, $idx) = @ARGV; $idx //= 0;
my $i = 0;
while (defined(my $h = <STDIN>)) {
  my $s = <STDIN>; my $p = <STDIN>; my $q = <STDIN>; last unless defined $q; chomp($h,$s,$p,$q);
  if ($mode eq 'atq') { $q =~ s/^./@/ }
  elsif ($mode eq 'plq') { $q =~ s/^./+/ }
  elsif ($mode eq 'short' && $i == $idx) { $q = substr($q, 0, length($q) - 5) }
  elsif ($mode eq 'long' && $i == $idx) { $q .= "IIIII" }
  elsif ($mode eq 'junk' && $i == $idx) { print "junk junk\n" }
  print "$h\n$s\n$p\n$q\n"; $i++;
}
PERL

run_one() {   # bindir dir env threads opts inputs
  local B=$1 D=$2 E=$3 T=$4 OPTS=$5 INP=$6 O
  mkdir -p $D; O=$D/o
  OPTS=${OPTS//@O@/$O}
  ( env $EXTRA $E nice -n 10 $B/kraken2 --db $DB --threads $T --output $O.out --report $O.rep $OPTS $INP ) > $D/stdout 2> $D/stderr
  echo $? > $D/rc
  sed -i 's/processed in.*//;s/([0-9.]* [KMG]bp)//' $D/stderr
}
cmp_dirs() {  # ref new label ; sets BAD
  local A=$1 N=$2 L=$3 f; BAD=0
  [ "$(ls $A | tr '\n' ' ')" = "$(ls $N | tr '\n' ' ')" ] || { echo "FAIL $L: file set differs: [$(ls $A|tr '\n' ' ')] vs [$(ls $N|tr '\n' ' ')]"; BAD=1; }
  for f in $(ls $A); do
    [ -e $N/$f ] || continue
    case $f in
      o.rep) cmp -s <(sort $A/$f) <(sort $N/$f) || { echo "FAIL $L: report differs even sorted"; BAD=1; }
             cmp -s $A/$f $N/$f || { echo "FAIL $L: report differs in exact order"; BAD=1; } ;;
      *) cmp -s $A/$f $N/$f || { echo "FAIL $L: $f differs"; BAD=1; } ;;
    esac
  done
}
# case_ NAME 'opts' 'inputs' ['chunks'] ['threads']   stock runs once per thread count, new once per (chunk, thread count)
case_() {
  local ID=$1 OPTS=$2 INP=$3 CH=${4:-"4096 65536"} TS=${5:-"1 8"} R=$W/res/$1 t c ok=1 info=""
  rm -rf $R
  for t in $TS; do
    run_one $STOCK $R/stock_t$t "" $t "$OPTS" "$INP"
    for c in $CH; do
      run_one $NEW $R/new_t${t}_c$c "K2_PREAD_CHUNK=$c" $t "$OPTS" "$INP"
      cmp_dirs $R/stock_t$t $R/new_t${t}_c$c "$ID t=$t chunk=$c"
      if [ $BAD = 1 ]; then ok=0; NF=$((NF+1)); else NP=$((NP+1)); fi
    done
    info="$info rc=$(cat $R/stock_t$t/rc) lines=$(wc -l < $R/stock_t$t/o.out 2>/dev/null)"
  done
  [ $ok = 1 ] && echo "PASS $ID: identical to stock in all configs (chunks: $CH, threads: $TS;$info)"
}

# ---------------------------------------------------------------- inputs
I=$W/in
head -n 4000 $SRC > $I/base.fq                         # 1000 reads, 5.8 MB
head -n 1200 $SRC > $I/pre.fq                          # 300 reads, about 1.7 MB (damage at read 250 is after the first MiB)
head -n 400 $SRC > $I/m1.fq; sed -n 401,800p $SRC > $I/m2.fq; sed -n 801,1200p $SRC > $I/m3.fq
cut_midq()  { head -c -3 "$1"; }
cut_aplus() { head -n -1 "$1" | head -c -1; }
cut_aplus2(){ head -n -1 "$1"; }
cut_aseq()  { head -n -2 "$1"; }
cut_hdr()   { cat "$1"; printf '@h\n'; }
cut_hdr2()  { cat "$1"; printf '@h'; }
for k in midq aplus aplus2 aseq hdr hdr2; do
  cut_$k $I/base.fq > $I/eof_$k.in
  for m in m1 m2 m3; do cut_$k $I/$m.fq > $I/${m}_$k.fq; done
done
perl $W/gen.pl short 500 < $I/base.fq > $I/short.in
perl $W/gen.pl long 500 < $I/base.fq > $I/long.in
perl $W/gen.pl short 250 < $I/pre.fq > $I/short_big.in      # damage after the first MiB
perl $W/gen.pl long 250 < $I/pre.fq > $I/long_big.in
perl $W/gen.pl junk 250 < $I/pre.fq > $I/junk_big.in
perl $W/gen.pl atq < $I/base.fq > $I/atq.in
perl $W/gen.pl plq < $I/base.fq > $I/plq.in
perl $W/gen.pl short 500 < $I/atq.in > $I/atq_short.in       # resync lands on a quality line that starts with '@'
perl $W/gen.pl long 500 < $I/atq.in > $I/atq_long.in
perl $W/gen.pl short 500 < $I/plq.in > $I/plq_short.in
perl $W/gen.pl short 100 < $I/m1.fq > $I/m1_short.fq
perl $W/gen.pl short 50 < $I/m2.fq > $I/m2_short.fq
for v in short_big long_big atq_short; do cut_midq $I/$v.in > $I/${v}_tailcut.in; done   # two damages: mid-file plus a cut tail
cut_aseq $I/short.in > $I/short_aseq.in
perl $W/gen.pl atq < $I/pre.fq > $I/atq_pre.fq
perl $W/gen.pl short 250 < $I/atq_pre.fq > $I/atq_short_big.in
cut_midq $I/atq_pre.fq > $I/atq_pre_midq.in
echo "inputs ready in $W/in: $(ls $I | wc -l) files, base.fq $(stat -c %s $I/base.fq) bytes, pre.fq $(stat -c %s $I/pre.fq) bytes"

RP='--report-minimizer-data'; Z='--report-zero-counts'
CU='--classified-out @O@.cls.fq --unclassified-out @O@.unc.fq'

if want c; then
echo "=== c: the validate_matrix c_* cases (single file), 5 option sets"
for n in eof_midq eof_aplus eof_aplus2 eof_aseq eof_hdr eof_hdr2 short long atq_short atq_long plq_short atq plq; do
  case_ c_$n '' "$I/$n.in"
  case_ c_${n}_K "$RP $Z" "$I/$n.in"
  case_ c_${n}_names '--use-names' "$I/$n.in"
  case_ c_${n}_quick '--quick' "$I/$n.in"
  case_ c_${n}_CU "$CU" "$I/$n.in"
done
fi

if want multi; then
echo "=== multi: truncation in file 1 of 2, in the last file, in consecutive files, and mid-file damage in a multi-file run"
for k in midq aplus aplus2 aseq hdr; do
  case_ multi_trunc_file1_$k '' "$I/m1_$k.fq $I/m2.fq"
  case_ multi_trunc_lastfile_$k '' "$I/m1.fq $I/m2_$k.fq"
  case_ multi_trunc_two_$k '' "$I/m1_$k.fq $I/m2_$k.fq $I/m3.fq"
  case_ multi_trunc_two_last_$k '' "$I/m1.fq $I/m2_$k.fq $I/m3_$k.fq"
  case_ multi_trunc_file1_${k}_CU "$CU" "$I/m1_$k.fq $I/m2.fq"
done
case_ multi_trunc_mixed '' "$I/m1_midq.fq $I/m2_aseq.fq $I/m3_aplus.fq"
case_ multi_damage_file1_short '' "$I/m1_short.fq $I/m2.fq"
case_ multi_damage_lastfile_short '' "$I/m1.fq $I/m2_short.fq"
case_ multi_damage_both '' "$I/m1_short.fq $I/m2_short.fq $I/m3.fq"
case_ multi_damage_then_trunc '' "$I/m1_short.fq $I/m2_midq.fq"
case_ multi_big_trunc_file1 '' "$I/atq_pre_midq.in $I/m2.fq"
case_ multi_big_trunc_lastfile '' "$I/m2.fq $I/atq_pre_midq.in"
fi

if want big; then
echo "=== big: mid-file damage after the first MiB, two damages, '@' and '+' in quality lines"
for n in short_big long_big junk_big atq_short_big short_big_tailcut long_big_tailcut atq_short_tailcut short_aseq; do
  case_ big_$n '' "$I/$n.in"
done
case_ big_short_two_files '' "$I/short_big.in $I/m1.fq"
case_ big_short_lastfile '' "$I/m1.fq $I/short_big.in"
fi

if want sweep; then
echo "=== sweep: cut the last record at every byte offset (pre.fq first 250 reads plus a 120 base synthetic last record)"
head -n 1000 $SRC > $I/sw_pre.fq
P=$(stat -c %s $I/sw_pre.fq)
SEQL=$(sed -n 1001,1004p $SRC | awk 'NR==2{print substr($0,1,120)}'); QL=$(sed -n 1001,1004p $SRC | awk 'NR==4{print substr($0,1,120)}')
printf '@sweeprec runid=abc ch=5\n%s\n+\n%s\n' "$SEQL" "$QL" > $I/sw_last.fq
cat $I/sw_pre.fq $I/sw_last.fq > $I/sw_full.fq
LEN=$(stat -c %s $I/sw_last.fq)
echo "prefix $P bytes, last record $LEN bytes, first-MiB boundary is before the prefix end"
SWN=0; SWF=0; R=$W/res/sweep
for cut in $(seq 0 $LEN); do
  head -c $((P + cut)) $I/sw_full.fq > $I/sw_cut.fq
  rm -rf $R; mkdir -p $R
  for t in 1 8; do run_one $STOCK $R/stock_t$t "" $t "" "$I/sw_cut.fq"; done
  for cfg in "4096 8" "65536 1" "$((P + 100)) 8" "4096 1" "$((P + 7)) 1"; do
    set -- $cfg; c=$1; t=$2
    run_one $NEW $R/new_t${t}_c$c "K2_PREAD_CHUNK=$c" $t "" "$I/sw_cut.fq"
    cmp_dirs $R/stock_t$t $R/new_t${t}_c$c "sweep cut=$cut chunk=$c t=$t"
    if [ $BAD = 1 ]; then SWF=$((SWF+1)); else SWN=$((SWN+1)); fi
  done
done
NP=$((NP+SWN)); NF=$((NF+SWF))
echo "sweep: $SWN identical, $SWF different over $((LEN+1)) cut points x 5 configs"
fi

if want control; then
echo "=== control: K2_PREAD_PRESCAN=0 on mid-file damage after the first MiB must still abort with exit 3 (documented, not stock-equal)"
R=$W/res/control; rm -rf $R
run_one $NEW $R/new "K2_PREAD_PRESCAN=0 K2_PREAD_CHUNK=4096" 8 "" "$I/short_big.in"
echo "control rc=$(cat $R/new/rc) (expect 3); stderr: $(grep -i K2_PREAD $R/new/stderr | head -1)"
run_one $NEW $R/new_v "K2_PREAD_VERBOSE=1 K2_PREAD_CHUNK=4096" 8 "" "$I/short_big.in"
echo "verbose with prescan on: $(grep K2_PREAD $R/new_v/stderr | tr '\n' '|')"
run_one $NEW $R/new_v2 "K2_PREAD_VERBOSE=1 K2_PREAD_CHUNK=4096" 8 "" "$I/eof_midq.in"
echo "verbose on a truncated tail: $(grep K2_PREAD $R/new_v2/stderr | tr '\n' '|')"
fi
echo "TOTAL: $NP pass, $NF fail"
rm -rf $W
