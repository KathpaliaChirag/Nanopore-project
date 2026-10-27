# cycle 3, round 2, a1_dsa

no new fetches. tags follow `00_context.md` section 6.

---

## 1. one line per new item

- **M75 (network / parallel fs rule): rider in M9 / M33.** a mapped table on nfs or lustre turns each lookup that misses the cache into a network round trip at queue depth 1. M30's batched `WILLNEED` would hide part of that. copying to node-local storage is simpler and needs no new code, so "stage the db" is the right default [guess].
- **M76 (page size at runtime): rider. add one more constant: the cache-line size.**
  - M8a/M26 assume 16 four-byte cells per 64 B line [arith].
  - if a cpu uses 128 B lines (my understanding of apple silicon, [guess], not fetched), a line holds 32 cells. the crossing rates then drop to about (2.17 - 1) / 32 = 3.7% for hits and (6.06 - 1) / 32 = 16% for misses [arith on the uniform-offset model].
  - M30's page formula (32 + 4 x idx) / page size and its bitmap size (one bit per page) must also take the runtime page size: 4x fewer pages at 16 KB [arith].
  - read the line size from sysfs or `sysconf` [guess on the exact file name].
- **M77 (input readahead outside the lock): rider in M9.** no data-structure effect.
- **M82 (`armv8.2-a` tier): revision of M21.** agree.
- **M86 (wsl2 / macOS probe backends): rider in M24.** agree. a vm that "drops its cache when idle" makes residency a per-run fact, not a per-boot fact [external: via a4].
- **M90 (channel-aware baseline, v2.1.3 column): rider in M1 / E2.** agree. data-structure note: v2.1.3 uses the same 32-bit linear-probing cell [external: the trie brief's v2.1.3 `compact_hash.h`]. so one db file serves all three versions and the byte compare is fair.
- **M91 (`ResolveTree` share): rider in the cpu gate.**
  - the repo's one count puts `ResolveTree` + `IsAAncestorOfB` at 0.08 s + 0.23 s of 105.87 s, 0.29% [arith on repo: WSL2 `gprof_report.txt` lines 16, 18]. that was a capped 8GB run, few taxa per read.
  - the cost grows with the square of the taxa per read: the repo's older estimate is ~80 x 80 x 5 ancestor-walk reads per long read [repo: `kraken2_get_optimizations_v2.md` S2]. #1063's 4.9x at 16 taxa vs 53x at 256 taxa [external: via a5] fits that.
  - so it can matter only on uncapped dbs with many hit taxa (103GB). measure it there first.
- **M70 (sorted vs random lookup benchmark): unranked measure.** it stays mine.
- **M71 (jetson gpu lookups): below the line.** it needs M85 first, because a gpu busy with dorado leaves no room for lookups [guess].
- **M72 (in-ram sweep): below the line.** it waits on M70.
- **M78 (cluster measurement): unranked.** agree.
- **M85 (orin co-run with dorado): campus visit.** agree. it also gates M71.
- **M88 (wsl2 cold-after-idle): unranked.** agree.
- **M89 (one apple silicon run): unranked.** agree. add one item to it: log the cache-line size, because it changes M8a/M26's crossing rates (see M76).

**the class splits** (H1-linux / wsl2 / mac, H4-dedicated / hpc, H2 "dorado idle"): agree. no rank moves follow.

---

## 2. wording fixes (section 2 of the brief)

1. **"the binary conda and brew users install":** confirm, as sourced by a5 [external: bioconda, homebrew, debian sid pages]. apt users on 2.1.3 are a separate population, so M90's column is the right fix.
2. **"its own" prefetch, load, parser, huge pages; aligners already prefetch:** confirm. one more piece of prior art from my area:
   - S9 is group prefetching and S16 is software-pipelined prefetching, both standard database techniques
   - AMAC calls them "existing techniques" that arrange lookups "into a group or pipeline" [external: cycle-2 a1 src 1]
   - so batched prefetch is not new for databases either. what may be new is applying it to kraken2's per-read loop before upstream did.
3. **"on an enterprise nvme":** confirm. the 0.106 ms latency at queue depth 1-16 is a kingston dcp1000 enterprise drive [external: a4 cycle-1 src 6]. consumer drives are [UNCLEAR].
4. **[UNCLEAR] back on orin's ~11.6x:** confirm. i flagged the same thing in cycle 2: it takes stock's 4.23 s of *sys* time as the load time [repo: `RESULTS.md` 1.4].
5. **drop "only" from "lost only 1.5x":** confirm. Coriolis has no in-ram point, so 1.5x is a slope across ratios 3.25-52, not a loss against fitting [external: via a5].

---

## 3. verdict

**list unchanged: agree.** both the build top 10 and the measure top 5.
- every item above is a rider, an unranked measure, or below the line
- the cache-line rider (M76 / M89) only rescales M8a/M26 cells on 128 B-line cpus
- M91 is a rider whose repo evidence (0.29% [arith]) gives no reason to rank it
