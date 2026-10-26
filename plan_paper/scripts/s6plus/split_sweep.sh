#!/bin/bash
# usage: split_sweep.sh LOGNAME [DIR]   -> tab-separated, one row per run: threads, bin, wall, load, classify, exit
# reads DIR/LOGNAME.log (written by threads_sweep.sh) and the matching DIR/LOGNAME.<bin>.t<threads>.err files.
# CHIRAG 21-10-26 :: wall minus kraken2's "processed in" is load PLUS exit teardown, not load alone (exit was
#                    4.8-8.1s on 103GB in the first sweep runs). the timestamped .err lines split all three:
#                    load = "done." stamp - start, classify = "processed in" stamp - "done." stamp,
#                    exit = start + wall - "processed in" stamp. processed_in_s is kraken2's own number, a cross-check.
D=${2:-$HOME/chirag_K/results/s6plus}
printf "threads\tbin\twall_s\tload_s\tclassify_s\texit_s\tprocessed_in_s\n"
grep '^threads=' "$D/$1.log" | while read -r th db bin st wl; do
  t=${th#threads=}; s=${st#start=}; w=${wl#wall=}
  e=$D/$1.$bin.t$t.err
  if [ ! -f "$e" ]; then printf "%s\t%s\t%s\tmissing_err\n" "$t" "$bin" "$w"; continue; fi
  awk -v t="$t" -v b="$bin" -v s="$s" -v w="$w" '
    /Loading database information/ && /done\./ { td = $1 }
    / processed in / { tp = $1; for (i = 1; i < NF; i++) if ($i == "in") { pi = $(i + 1); sub(/s$/, "", pi) } }
    END {
      if (td == "" || tp == "") { printf "%s\t%s\t%s\tincomplete\n", t, b, w; exit }
      printf "%s\t%s\t%.2f\t%.2f\t%.2f\t%.2f\t%s\n", t, b, w, td - s, tp - td, s + w - tp, pi
    }' "$e"
done
