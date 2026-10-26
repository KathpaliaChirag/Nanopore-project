#!/bin/bash
# usage: grid.sh LOGNAME "VARIANTS"
#   VARIANT = label=bindir[=flags[=env]]   flags and env are comma-separated lists, env uses ':' instead of '='
#     "s19=kraken2-fresh-bin-s19 s19M=kraken2-fresh-bin-s19=--memory-mapping"     (-M vs copy-load)
#     "L1=kraken2-fresh-bin-s19==OMP_NUM_THREADS:1 L32=kraken2-fresh-bin-s19==OMP_NUM_THREADS:32"  (loader threads)
#   the FIRST variant is the reference: in rep 1, every other variant's kraken output and report are
#   byte-compared to it (sorted, same as check.sh). put s0 first when you want "identical to stock".
# env knobs, defaults = the standard grid (4 dbs x 4 read counts, 32 threads, 3 interleaved reps):
#   DBS="50MB 8GB 16GB 103GB"  RCS="10 1000 104918 1872777"  THREADS="32"  REPS=3
#   DBROOT=~/AccuracyDrift/databases   R10 R1000 R104918 R1872777 = input file(s) per read count
#   OUT=~/chirag_K/results/s6plus   PIN="" (prefix, e.g. "numactl --cpunodebind=0 --membind=0")
#   NOOUT=1 sends kraken output to /dev/null (removes the serial in-order output write; no byte compare then)
# writes OUT/LOGNAME.log (one line per run) and OUT/LOGNAME.md (full 4x4 table per thread count, medians).
# CHIRAG 21-10-26 :: one runner for every experiment in next_steps_plan_2026-10-21.md, so all of them log the
#                    same columns: wall/user/sys, max rss, major and minor faults (minor faults count how many
#                    pages -M really touched), the load/classify/exit split from timestamped stderr, and the
#                    peak huge-page coverage (explains the 13-21s thp spread on 103GB).
OUT=${OUT:-$HOME/chirag_K/results/s6plus}
LOGF=$OUT/$1.log; MDF=$OUT/$1.md; VARS=$2
DBS=${DBS:-50MB 8GB 16GB 103GB}; RCS=${RCS:-10 1000 104918 1872777}; THREADS=${THREADS:-32}; REPS=${REPS:-3}
DBROOT=${DBROOT:-$HOME/AccuracyDrift/databases}
TIME_BIN=${TIME_BIN:-/usr/bin/time}
declare -A DB=([50MB]=$DBROOT/sample_targeted [8GB]=$DBROOT/standard_8gb [16GB]=$DBROOT/standard_16gb [103GB]=$DBROOT/pluspf_103gb)
declare -A RF=([10]=${R10:-$HOME/chirag_K/results/readcount_bench/reads_10.fastq}
               [1000]=${R1000:-$HOME/chirag_K/results/readcount_bench/reads_1000.fastq}
               [104918]=${R104918:-$HOME/chirag_K/results/basecalling/reads_hac.fastq}
               [1872777]=${R1872777:-$(ls $HOME/chirag_K/results/per_pod5_fastq/pod5_*.fastq 2>/dev/null | sort | tr "\n" " ")})
W=$OUT/grid_$1; mkdir -p "$W"; : > "$LOGF"
REF=${VARS%% *}; REF=${REF%%=*}

sample_mem() {
  # CHIRAG 21-10-26 :: nobody else on luna used thp (AnonHugePages 0 kB on 2026-10-21), so the system-wide peak
  #                    minus the pre-run value is our table's huge-page coverage. FilePmdMapped > 0 would mean -M
  #                    got 2MB mappings of the page cache (expected 0 on ext4 + kernel 6.8).
  local a=0 f=0 x y
  while [ ! -e "$W/stop" ]; do
    read -r x y < <(awk '/^AnonHugePages:/{a=$2} /^FilePmdMapped:/{f=$2} END{print a+0, f+0}' /proc/meminfo)
    [ "$x" -gt "$a" ] && a=$x; [ "$y" -gt "$f" ] && f=$y
    sleep 0.2
  done
  echo "$a $f" > "$W/mem"
}

for r in $(seq 1 "$REPS"); do for t in $THREADS; do for d in $DBS; do for rc in $RCS; do
  for v in $VARS; do
    IFS='=' read -r label bin flags envs <<< "$v"
    flags=${flags//,/ }; envs=${envs//,/ }; envs=${envs//:/=}
    rm -f "$W/stop" "$W/mem" "$W/time" "$W/err"
    base=$(awk '/^AnonHugePages:/{print $2+0}' /proc/meminfo)
    sample_mem & sp=$!
    S=$(date +%s.%N)
    # CHIRAG 21-10-26 :: a pipeline instead of 2> >(...) so bash waits for the timestamper by itself; stdout goes
    #                    to /dev/null, stderr (the only lines we need) goes through the pipe.
    ko=$W/$label.out; [ "$NOOUT" = 1 ] && ko=/dev/null
    env $envs $PIN "$TIME_BIN" -f "%e %U %S %M %F %R %x" -o "$W/time" "$HOME/tools/$bin/kraken2" --db "${DB[$d]}" \
        --threads "$t" $flags --output "$ko" --report "$W/$label.rep" ${RF[$rc]} 2>&1 >/dev/null \
      | while IFS= read -r l; do echo "$(date +%s.%N) $l"; done > "$W/err"
    touch "$W/stop"; wait "$sp"
    read -r wall usr sys rss majf minf xs < <(tail -1 "$W/time")
    read -r thp fpmd < "$W/mem"
    split=$(awk -v s="$S" -v w="$wall" '
      /Loading database information/ && /done\./ { td = $1 }
      / processed in / { tp = $1 }
      END { if (td == "" || tp == "") print "load=NA classify=NA exit=NA";
            else printf "load=%.2f classify=%.2f exit=%.2f", td - s, tp - td, s + w - tp }' "$W/err")
    verdict="-"
    if [ "$xs" != "0" ]; then verdict="EXIT$xs"
    elif [ "$NOOUT" = 1 ]; then verdict="-"
    elif [ ! -s "$W/$label.out" ]; then verdict="EMPTY"
    elif [ "$r" = 1 ]; then
      if [ "$label" = "$REF" ]; then verdict="ref"
      elif cmp -s <(sort "$W/$REF.out") <(sort "$W/$label.out") && cmp -s <(sort "$W/$REF.rep") <(sort "$W/$label.rep"); then verdict="IDENTICAL"
      else verdict="MISMATCH"; fi
    fi
    printf "%s reads=%s threads=%s %s rep%s wall=%s user=%s sys=%s maxrss_kb=%s majflt=%s minflt=%s %s thp_gb=%.1f filepmd_gb=%.1f %s\n" \
      "$d" "$rc" "$t" "$label" "$r" "$wall" "$usr" "$sys" "$rss" "$majf" "$minf" "$split" \
      "$(awk -v a="$thp" -v b="$base" 'BEGIN{x=(a-b)/1048576; print (x<0?0:x)}')" \
      "$(awk -v a="$fpmd" 'BEGIN{print a/1048576}')" "$verdict" >> "$LOGF"
  done
done; done; done; done
echo DONE >> "$LOGF"

# CHIRAG 21-10-26 :: the summary always prints the full 4 dbs x 4 read counts grid (ck's rule), and says "not run"
#                    for any cell this machine or this run did not cover, instead of dropping the row.
awk -v vars="$VARS" -v ths="$THREADS" '
  function med(k,   n, i, j, a, tmp) { n = split(W[k], a, " "); for (i = 2; i <= n; i++) for (j = i; j > 1 && a[j-1]+0 > a[j]+0; j--) { tmp = a[j]; a[j] = a[j-1]; a[j-1] = tmp }
                                       return n ? (n % 2 ? a[(n+1)/2] : (a[n/2] + a[n/2+1]) / 2) : "" }
  $1 == "DONE" { next }
  { sub(/^reads=/, "", $2); sub(/^threads=/, "", $3); w = $6; sub(/^wall=/, "", w)
    k = $1 SUBSEP $2 SUBSEP $3 SUBSEP $4; W[k] = W[k] (W[k] == "" ? "" : " ") w; N[k]++
    if ($5 == "rep1") V[k] = $NF }
  END {
    nv = split(vars, vv, " "); for (i = 1; i <= nv; i++) { split(vv[i], p, "="); L[i] = p[1] }
    nt = split(ths, tt, " "); nd = split("50MB 8GB 16GB 103GB", dd, " "); nr = split("10 1000 104918 1872777", rr, " ")
    for (x = 1; x <= nt; x++) {
      printf "\n### threads = %s (median of reps, seconds)\n\n| db | reads |", tt[x]
      for (i = 1; i <= nv; i++) printf " %s |", L[i]
      for (i = 2; i <= nv; i++) printf " %s speedup (%s/%s) |", L[i], L[1], L[i]
      printf " output vs %s |\n|---|---|", L[1]; for (i = 1; i <= 2 * nv; i++) printf "---|"; printf "\n"
      for (a = 1; a <= nd; a++) for (b = 1; b <= nr; b++) {
        printf "| %s | %s |", dd[a], rr[b]; out = ""
        for (i = 1; i <= nv; i++) { k = dd[a] SUBSEP rr[b] SUBSEP tt[x] SUBSEP L[i]; m[i] = med(k)
          printf " %s |", (m[i] == "" ? "not run" : sprintf("%.2f (n=%d)", m[i], N[k]))
          if (i > 1 && V[k] != "") out = out " " L[i] ":" V[k] }
        for (i = 2; i <= nv; i++) printf " %s |", (m[1] == "" || m[i] == "" || m[i] + 0 == 0 ? "n/a" : sprintf("%.2fx", m[1] / m[i]))
        printf " %s |\n", (out == "" ? "n/a" : out)
      }
    }
  }' "$LOGF" > "$MDF"
echo "wrote $LOGF and $MDF"
