#!/bin/bash
# validate_matrix.sh - cycle 3 round 2 agent C. DO NOT RUN FROM THE REPO; run on luna later:
#   bash validate_matrix.sh 2>&1 | tee ~/e1/validate_matrix.log
# compares stock S19 against each stacked build (hll, hll+dedup, hll+dedup+serial, and serial with K2_KEEPQ=1
# as a control that isolates the quality-skip). per case it compares: exit code, normalised stderr, the
# per-read --output file, every other output file (classified/unclassified), and the report (sorted = must be
# identical; exact order = warn only, see round2_C_validation.md section 1 on tied siblings).
# result lines: PASS / FAIL / WARN. exit status is the number of FAIL lines. uses only /dev/shm for scratch.
set -u
HOME_=${HOME_:-$HOME}
STOCK=${STOCK:-$HOME_/chirag_K/tools/kraken2-fresh-bin-s19}
DBR=$HOME_/chirag_K/AccuracyDrift/databases
DB=${DB:-$DBR/sample_targeted}                 # small db for the full matrix
CORE_DBS=${CORE_DBS:-"$DBR/standard_8gb $DBR/standard_16gb"}   # short core subset (capped dbs: dedup skip path)
PROT_DB=${PROT_DB:-}                           # optional protein db (kraken2-build --protein) for translated search
T=${T:-8}
W=${W:-/dev/shm/vm_$$}
SRCFQ=${SRCFQ:-$(ls $HOME_/chirag_K/results/per_pod5_fastq/pod5_*.fastq | sort | head -1)}
NAMES=(final2 final2_keepq reader scanner_bulk hll_oldguard)
BINS=($HOME_/e1/bin_final2 $HOME_/e1/bin_final2 $HOME_/e1/bin_reader $HOME_/e1/bin_scanner $HOME_/e1/bin_hll)
ENVS=("" "K2_KEEPQ=1" "" "K2_BULK=1" "")
NPASS=0; NFAIL=0; NWARN=0
mkdir -p $W/in $W/res
G=$W/gen.pl

# ---------------------------------------------------------------- generators
cat > $G <<'PERL'
use strict; use warnings;
my $mode = shift @ARGV;
my @r;
while (defined(my $h = <STDIN>)) { my $s=<STDIN>; my $p=<STDIN>; my $q=<STDIN>; last unless defined $q; chomp($h,$s,$p,$q); push @r,[$h,$s,$p,$q]; }
sub fq { my($h,$s,$p,$q)=@_; return "$h\n$s\n$p\n$q\n"; }
sub wr { my($x,$w)=@_; my @c = $x =~ /(.{1,$w})/g; return join("\n",@c); }
sub rnd { my($n,$al)=@_; my @a=split //,$al; return join '', map { $a[int(rand(@a))] } 1..$n; }
my $i=0;
if ($mode eq 'fa_ml') { for my $x (@r) { print ">".substr($x->[0],1)."\n".wr($x->[1],60)."\n"; } }
elsif ($mode eq 'fa_1l') { for my $x (@r) { print ">".substr($x->[0],1)."\n$x->[1]\n"; } }
elsif ($mode eq 'empty') { print "\@e0\n\n+\n\n\@e0b\n\n+\n\n"; for my $x (@r) { print fq(@$x); print "\@e$i\n\n+\n\n" if $i%50==49; $i++ } print "\@eEND\n\n+\n\n"; }
elsif ($mode eq 'atq') { for my $x (@r) { $x->[3] =~ s/^./@/; print fq(@$x); } }
elsif ($mode eq 'atq_all') { for my $x (@r) { $x->[3] = '@' x length($x->[1]); print fq(@$x); } }
elsif ($mode eq 'plq') { for my $x (@r) { $x->[3] =~ s/^./+/; print fq(@$x); } }
elsif ($mode eq 'gtq') { for my $x (@r) { $x->[3] =~ s/^./>/; print fq(@$x); } }
elsif ($mode eq 'wrapfq') { for my $x (@r) { print "$x->[0]\n".wr($x->[1],70)."\n+\n".wr($x->[3],70)."\n"; } }
elsif ($mode eq 'plusname') { for my $x (@r) { $x->[2] = "+".substr($x->[0],1); print fq(@$x); } }
elsif ($mode eq 'blank') { for my $x (@r) { print fq(@$x)."\n"; } print "\n\n"; }
elsif ($mode eq 'blank2') { for my $x (@r) { print "$x->[0]\n$x->[1]\n\n+\n$x->[3]\n"; } }
elsif ($mode eq 'short') { for my $x (@r) { $x->[3] = substr($x->[3],0,length($x->[3])-5) if $i==500; print fq(@$x); $i++ } }
elsif ($mode eq 'long')  { for my $x (@r) { $x->[3] .= "IIIII" if $i==500; print fq(@$x); $i++ } }
elsif ($mode eq 'crcr')  { for my $x (@r) { $x->[3] .= "\r" if $i%7==0; print fq(@$x); $i++ } }
elsif ($mode eq 'tabs')  { for my $x (@r) { $x->[0] .= "\tcomment here\twith tabs"; print fq(@$x); } }
elsif ($mode eq 'special') {
  my $n=0;
  for my $x (@r) { last if $n>=150; my $s=$x->[1];
    if ($n%3==0) { $s=lc($s) } elsif ($n%3==1) { my @c=split //,$s; for (my $j=7;$j<@c;$j+=20){$c[$j]='N'} $s=join '',@c }
    else { my @c=split //,$s; my @iu=('R','Y','K','M'); for (my $j=3;$j<@c;$j+=11){$c[$j]=$iu[$j%4]} $s=join '',@c }
    print fq($x->[0],$s,$x->[2],$x->[3]); $n++ }
  my @syn = ('A' x 500, 'AC' x 250, 'N' x 200, 'ACGTACGTAC', 'ACGTTGCA' x 4, 'ACGT' x 8 . 'N' . 'ACGT' x 8, 'T' x 35, 'G' x 36, 'ACGTNNNNNNNNNNACGT' x 20);
  my $k=0; for my $s (@syn) { print "\@syn$k\n$s\n+\n".('I' x length($s))."\n"; $k++ }
  # every kth base ambiguous, run-length repeats of a real read, reverse-complement-like palindrome
  my $real = $r[0][1]; print "\@rep\n".($real x 3)."\n+\n".('I' x (3*length($real)))."\n";
}
elsif ($mode eq 'sweep') {
  srand(7);
  for my $len (1..600) { my $s=rnd($len,'ACGT'); my $q=rnd($len,'#$%&+-.0123456789:;<=>?@ABCDEFGHI'); $q =~ s/^./@/ if $len%5==0; print "\@sw$len\n$s\n+\n$q\n"; }
}
elsif ($mode eq 'big') {
  srand(3); my $L=200000; my $s=rnd($L,'ACGT'); my $q=rnd($L,'#$%&+-.0123456789:;<=>?@ABCDEFGHI');
  print "\@big1\n$s\n+\n$q\n"; $s=rnd(70000,'ACGT'); $q=rnd(70000,'#$%&@IIII'); print "\@big2\n$s\n+\n$q\n";
  for my $x (@r[0..199]) { print fq(@$x); }
}
elsif ($mode eq 'mixed') {
  for my $x (@r[0..99]) { print fq(@$x) } for my $x (@r[100..199]) { print ">".substr($x->[0],1)."\n".wr($x->[1],60)."\n" }
  for my $x (@r[200..299]) { print fq(@$x) } for my $x (@r[300..399]) { print ">".substr($x->[0],1)."\n$x->[1]\n" }
}
elsif ($mode eq 'boundary') {   # args: off crlf which(end|start)
  my ($off,$crlf,$which)=@ARGV; srand(11); my $L=150; my $P=16384+$off;
  my $s=rnd($L,'ACGT'); my $q=rnd($L,'#$%&+-.0123456789:;<=>?@ABCDEFGHI');
  my $e = $crlf ? 2 : 1; my $pad;
  if ($which eq 'end') { $pad = $crlf ? $P-11-2*$L : $P-7-2*$L; } else { $pad = $crlf ? $P-10-$L : $P-7-$L; }
  my $o = "\@b ".('x' x $pad)."\n$s\n+\n$q\n";
  for my $x (@r[0..19]) { $o .= fq(@$x) }
  $o =~ s/\n/\r\n/g if $crlf; print $o;
}
PERL

# ---------------------------------------------------------------- inputs
head -n 4000 "$SRCFQ" > $W/in/base.fq                       # 1000 real reads
head -n 80 $W/in/base.fq > $W/in/tiny20.fq                  # 20 reads: ties among siblings, -z
head -n 20 $W/in/base.fq > $W/in/tiny5.fq
head -n 400 $W/in/base.fq > $W/in/small100.fq               # 100 reads for chunked pipes
for m in fa_ml fa_1l empty atq atq_all plq gtq wrapfq plusname blank blank2 short long crcr tabs special mixed; do
  perl $G $m < $W/in/base.fq > $W/in/$m.in
done
perl $G sweep < /dev/null > $W/in/sweep.in
perl $G big < $W/in/base.fq > $W/in/big.in
sed 's/$/\r/' $W/in/base.fq > $W/in/crlf.in
head -c -1 $W/in/base.fq > $W/in/nonl.in                     # last record, no trailing newline
head -c -1 $W/in/crlf.in > $W/in/crlf_nonl.in                # ends with "\r" and no "\n"
head -c -2 $W/in/crlf.in > $W/in/crlf_nonl2.in               # ends without "\r\n"
sed 's/$/\r/' $W/in/wrapfq.in > $W/in/wrapfq_crlf.in
sed 's/$/\r/' $W/in/fa_ml.in > $W/in/fa_ml_crlf.in
head -c -1 $W/in/fa_ml.in > $W/in/fa_ml_nonl.in
head -c -3 $W/in/base.fq > $W/in/eof_mid_qual.in     # cut inside the last quality line
head -n 3999 $W/in/base.fq | head -c -1 > $W/in/eof_after_plus.in   # ends with the + and no newline
head -n 3999 $W/in/base.fq > $W/in/eof_after_plus2.in        # ends right after the + line (with newline)
head -n 3998 $W/in/base.fq > $W/in/eof_after_seq.in          # ends after the sequence line, no + line
for off in -3 -2 -1 0 1 2 3; do for crlf in 0 1; do for wh in end start; do
  perl $G boundary $off $crlf $wh < $W/in/base.fq > $W/in/bnd_${wh}_${crlf}_${off}.in
done; done; done
# pairs
sed -n 1,2000p $W/in/base.fq > $W/in/pA.fq
sed -n 2001,4000p $W/in/base.fq > $W/in/pB.fq
sed -n 2001,3600p $W/in/base.fq > $W/in/pB_short.fq
paste -d'\n' <(paste - - - - < $W/in/pA.fq) <(paste - - - - < $W/in/pB.fq) | tr '\t' '\n' > $W/in/inter.fq
head -n -4 $W/in/inter.fq > $W/in/inter_odd.fq
sed 's/$/\r/' $W/in/pA.fq > $W/in/pA_crlf.fq
sed 's/$/\r/' $W/in/pB.fq > $W/in/pB_crlf.fq
# compressed, multi-file
gzip -c $W/in/base.fq > $W/in/base.fq.gz
gzip -c $W/in/crlf.in > $W/in/crlf.fq.gz
bzip2 -c $W/in/base.fq > $W/in/base.fq.bz2
sed -n 1,1200p $W/in/base.fq > $W/in/m1.fq; head -c -1 $W/in/m1.fq > $W/in/m1_nonl.fq
sed -n 1201,2400p $W/in/base.fq | sed 's/$/\r/' > $W/in/m2_crlf.fq
sed -n 2401,3200p $W/in/base.fq > $W/in/m3.fq; : > $W/in/m_empty.fq
perl $G fa_1l < $W/in/m3.fq > $W/in/m3.fa
cat > $W/feed.pl <<'PERL'
$|=1; my $s=shift; binmode STDIN; binmode STDOUT; my $b;
while (read(STDIN,$b,$s)) { print $b; select(undef,undef,undef,0.0005); }
PERL

# ---------------------------------------------------------------- runner
run_one() {   # bindir dir env db opts inputs pre
  local B=$1 D=$2 E=$3 DBX=$4 OPTS=$5 INP=$6 PRE=${7:-} O
  mkdir -p $D; O=$D/o
  if [ -n "$PRE" ]; then
    ( eval "$PRE | env $E $B/kraken2 --db $DBX --threads $TT --output $O.out --report $O.rep $OPTS $INP" ) > $D/stdout 2> $D/stderr
  else
    ( eval "env $E $B/kraken2 --db $DBX --threads $TT --output $O.out --report $O.rep $OPTS $INP" ) > $D/stdout 2> $D/stderr
  fi
  echo $? > $D/rc
  sed -i 's/processed in.*//;s/([0-9.]* [KMG]bp)//' $D/stderr
}
run_cls() {   # direct classify (needed for -S interleaved, which the perl wrapper cannot pass)
  local B=$1 D=$2 E=$3 DBX=$4 OPTS=$5 INP=$6 O
  mkdir -p $D; O=$D/o
  ( eval "env $E $B/classify -H $DBX/hash.k2d -t $DBX/taxo.k2d -o $DBX/opts.k2d -p $TT -O $O.out -R $O.rep $OPTS $INP" ) > $D/stdout 2> $D/stderr
  echo $? > $D/rc
  sed -i 's/processed in.*//;s/([0-9.]* [KMG]bp)//' $D/stderr
}
cmp_dirs() {  # ref new label
  local A=$1 N=$2 L=$3 bad=0 warn=0 f
  [ "$(ls $A | tr '\n' ' ')" = "$(ls $N | tr '\n' ' ')" ] || { echo "FAIL $L: file set differs: [$(ls $A|tr '\n' ' ')] vs [$(ls $N|tr '\n' ' ')]"; bad=1; }
  for f in $(ls $A); do
    [ -e $N/$f ] || continue
    case $f in
      o.rep) cmp -s <(sort $A/$f) <(sort $N/$f) || { echo "FAIL $L: report differs even sorted"; bad=1; }
             cmp -s $A/$f $N/$f || warn=1 ;;
      *) cmp -s $A/$f $N/$f || { echo "FAIL $L: $f differs"; bad=1; } ;;
    esac
  done
  if [ $bad = 1 ]; then NFAIL=$((NFAIL+1)); return; fi
  local nl=$(wc -l < $A/o.out 2>/dev/null || echo 0) rcv=$(cat $A/rc)
  if [ $warn = 1 ]; then echo "WARN $L: IDENTICAL except report line order (sorted reports identical) lines=$nl rc=$rcv"; NWARN=$((NWARN+1))
  else echo "PASS $L: IDENTICAL lines=$nl rc=$rcv"; fi
  NPASS=$((NPASS+1))
}
# case ID 'opts' 'inputs' ['pre'] ['db'] ['threads'] ['mode: cls']
case_() {
  local ID=$1 OPTS=$2 INP=$3 PRE=${4:-} DBX=${5:-$DB} MODE=${7:-wrap} i
  TT=${6:-$T}
  local R=$W/res/$ID.$(basename $DBX); rm -rf $R
  if [ "$MODE" = cls ]; then run_cls $STOCK $R/stock "" $DBX "$OPTS" "$INP"; else run_one $STOCK $R/stock "" $DBX "$OPTS" "$INP" "$PRE"; fi
  for i in ${!NAMES[@]}; do
    if [ "$MODE" = cls ]; then run_cls ${BINS[$i]} $R/${NAMES[$i]} "${ENVS[$i]}" $DBX "$OPTS" "$INP"
    else run_one ${BINS[$i]} $R/${NAMES[$i]} "${ENVS[$i]}" $DBX "$OPTS" "$INP" "$PRE"; fi
    cmp_dirs $R/stock $R/${NAMES[$i]} "$ID [$(basename $DBX)] ${NAMES[$i]}"
  done
}
I=$W/in
RP='--report-minimizer-data'
Z='--report-zero-counts'

echo "=== A. plain options on real reads (patches 1,2 mostly)"
case_ a01_default      ''                                  "$I/base.fq"
case_ a02_names        '--use-names'                       "$I/base.fq"
case_ a03_z            "$Z"                                "$I/base.fq"
case_ a04_K            "$RP"                               "$I/base.fq"
case_ a05_K_z          "$RP $Z"                            "$I/base.fq"
case_ a06_mpa          '--use-mpa-style'                   "$I/base.fq"
case_ a07_mpa_z        "--use-mpa-style $Z"                "$I/base.fq"
case_ a08_conf         '--confidence 0.2'                  "$I/base.fq"
case_ a09_hitgroups    '--minimum-hit-groups 3'            "$I/base.fq"
case_ a10_quick        '--quick'                           "$I/base.fq"
case_ a11_quick_hg_K   "--quick --minimum-hit-groups 2 $RP" "$I/base.fq"
case_ a12_mmap         '--memory-mapping'                  "$I/base.fq"
case_ a13_names_conf_z "--use-names --confidence 0.1 $Z"   "$I/base.fq"
case_ a14_tiny20_z     "$Z"                                "$I/tiny20.fq"      # ties among siblings, patch 1 order risk
case_ a15_tiny5_z      "$Z"                                "$I/tiny5.fq"
case_ a16_tiny20       ''                                  "$I/tiny20.fq"
case_ a17_T1           ''                                  "$I/base.fq" '' "$DB" 1
case_ a18_T48          ''                                  "$I/base.fq" '' "$DB" 48
case_ a19_special      ''                                  "$I/special.in"     # N, lowercase, IUPAC, homopolymers: repeats + ambiguous (patch 2)
case_ a20_special_q    '--quick'                           "$I/special.in"
case_ a21_special_K    "$RP $Z"                            "$I/special.in"
echo "=== B. quality handling (patch 3): the skip is on only when no -Q, -C, -U"
case_ b01_Q10          '--minimum-base-quality 10'         "$I/base.fq"
case_ b02_Q10_fasta    '--minimum-base-quality 10'         "$I/fa_ml.in"
case_ b03_C            "--classified-out \$O.cls.fq"       "$I/base.fq"
case_ b04_U            "--unclassified-out \$O.unc.fq"     "$I/base.fq"
case_ b05_CU           "--classified-out \$O.cls.fq --unclassified-out \$O.unc.fq" "$I/base.fq"
case_ b06_CU_fasta     "--classified-out \$O.cls.fa --unclassified-out \$O.unc.fa" "$I/fa_ml.in"
case_ b07_CU_crlf      "--classified-out \$O.cls.fq --unclassified-out \$O.unc.fq" "$I/crlf.in"
case_ b08_Q10_atq      '--minimum-base-quality 10'         "$I/atq.in"
case_ b09_CU_empty     "--classified-out \$O.cls.fq --unclassified-out \$O.unc.fq" "$I/empty.in"
echo "=== C. input syntax (patch 3 reader)"
for n in fa_ml fa_1l fa_ml_crlf fa_ml_nonl crlf nonl crlf_nonl crlf_nonl2 empty atq atq_all plq gtq wrapfq wrapfq_crlf plusname blank blank2 \
         short long crcr tabs sweep big mixed eof_mid_qual eof_after_plus eof_after_plus2 eof_after_seq; do
  case_ c_$n '' "$I/$n.in"
  case_ c_${n}_K "$RP $Z" "$I/$n.in"
done
for f in $I/bnd_*.in; do b=$(basename $f .in); case_ c_$b '' "$f"; done
echo "=== D. paired, interleaved, multi-file, compressed, stdin"
case_ d01_paired        '--paired'                          "$I/pA.fq $I/pB.fq"
case_ d02_paired_CU     "--paired --classified-out \$O.c#.fq --unclassified-out \$O.u#.fq" "$I/pA.fq $I/pB.fq"
case_ d03_paired_Q      '--paired --minimum-base-quality 10' "$I/pA.fq $I/pB.fq"
case_ d04_paired_crlf   '--paired'                          "$I/pA_crlf.fq $I/pB_crlf.fq"
case_ d05_paired_short  '--paired'                          "$I/pA.fq $I/pB_short.fq"
case_ d06_paired_K_z    "--paired $RP $Z"                   "$I/pA.fq $I/pB.fq"
case_ d07_inter         '-S'                                "$I/inter.fq" '' "$DB" "$T" cls
case_ d08_inter_odd     '-S'                                "$I/inter_odd.fq" '' "$DB" "$T" cls
case_ d09_inter_CU      "-S -C \$O.c#.fq -U \$O.u#.fq"      "$I/inter.fq" '' "$DB" "$T" cls
case_ d10_inter_Q       '-S -Q 10'                          "$I/inter.fq" '' "$DB" "$T" cls
case_ d11_multi         ''                                  "$I/m1_nonl.fq $I/m2_crlf.fq $I/m_empty.fq $I/m3.fa"
case_ d12_multi_CU      "--classified-out \$O.cls.fq --unclassified-out \$O.unc.fq" "$I/m1_nonl.fq $I/m2_crlf.fq $I/m_empty.fq $I/m3.fa"
case_ d13_gz            '--gzip-compressed'                 "$I/base.fq.gz"
case_ d14_gz_crlf       '--gzip-compressed'                 "$I/crlf.fq.gz"
case_ d15_bz2           '--bzip2-compressed'                "$I/base.fq.bz2"
case_ d16_gz_paired     '--gzip-compressed --paired'        "$I/base.fq.gz $I/base.fq.gz"
case_ d17_stdin         ''                                  "/dev/stdin" "cat $I/base.fq"
case_ d18_stdin_crlf    ''                                  "/dev/stdin" "cat $I/crlf.in"
case_ d19_chunk37       ''                                  "/dev/stdin" "perl $W/feed.pl 37 < $I/small100.fq"
case_ d20_chunk1_crlf   ''                                  "/dev/stdin" "sed 's/\$/\r/' $I/small100.fq | perl $W/feed.pl 1"
case_ d21_chunk7_wrap   ''                                  "/dev/stdin" "perl $W/feed.pl 7 < $I/wrapfq.in"
case_ d22_chunk3_empty  ''                                  "/dev/stdin" "perl $W/feed.pl 3 < $I/empty.in"
echo "=== E. translated search (needs PROT_DB, a protein database)"
if [ -n "$PROT_DB" ]; then
  for n in base.fq special.in tiny20.fq; do
    case_ e_prot_$n ''           "$I/$n" '' "$PROT_DB"
    case_ e_prot_q_$n '--quick'  "$I/$n" '' "$PROT_DB"
    case_ e_prot_K_$n "$RP $Z"   "$I/$n" '' "$PROT_DB"
  done
  case_ e_prot_paired '--paired' "$I/pA.fq $I/pB.fq" '' "$PROT_DB"
else echo "SKIP translated search: set PROT_DB=/path/to/protein_db"; fi
echo "=== F. capped / large dbs, short core subset (dedup min-hash skip path, 3 builds x db)"
for DBX in $CORE_DBS; do
  [ -d $DBX ] || { echo "SKIP missing $DBX"; continue; }
  case_ f01_default  ''              "$I/base.fq"  '' $DBX
  case_ f02_K_z      "$RP $Z"        "$I/base.fq"  '' $DBX
  case_ f03_CU       "--classified-out \$O.cls.fq --unclassified-out \$O.unc.fq" "$I/base.fq" '' $DBX
  case_ f04_quick    '--quick'       "$I/base.fq"  '' $DBX
  case_ f05_special  ''              "$I/special.in" '' $DBX
  case_ f06_paired   '--paired'      "$I/pA.fq $I/pB.fq" '' $DBX
  case_ f07_mmap     '--memory-mapping' "$I/base.fq" '' $DBX
  case_ f08_T48      ''              "$I/base.fq" '' $DBX 48
done
echo "=== G. k-mer cap check: print minimum_acceptable_hash_value of each db (read-only; opts.k2d is 40+ bytes)"
for DBX in $DB $CORE_DBS; do echo "$DBX: $(od -An -t u8 -j 0 -N 64 $DBX/opts.k2d | tr -s ' ' | tr '\n' ' ')"; done
echo "=== SUMMARY pass=$NPASS warn=$NWARN fail=$NFAIL (expected: every line IDENTICAL; WARN only on report line order)"
rm -rf $W/in
exit $NFAIL
