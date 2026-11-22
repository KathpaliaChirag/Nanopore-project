# cycle 2 round 3, agent C: memory system and modelling

read: round2 result (oracle ceiling), round2 A and B, p32_summary.txt, S9/S14/S16/S19 explanations, compact_hash.cc on luna (read-only ssh: lscpu, perf list, sed). nothing run. tags: [L] measured by us, [S] source code, [P] published fact, [A] my arithmetic, [G] guess.

luna facts [L from lscpu]: Xeon Platinum 8468 (Sapphire Rapids, Golden Cove cores), 2 sockets x 48 cores x 2 SMT = 192 cpus, L2 2 MB per core, L3 105 MB per socket, THP mode madvise, 2 MB hugetlb pool empty, 1 GB hugetlb pool empty (0 pages, needs root to fill). perf list on luna has every event I name below (dtlb_load_misses.walk_active, walk_completed_2m_4m, stlb_hit, l1d_pend_miss.fb_full, mem_load_retired.l3_miss, offcore_requests_outstanding.demand_data_rd, memory_activity.stalls_l3_miss, sw_prefetch_access.t0).

## 0. what the oracle result already pins down

the skip oracle is the best number we have, so use it as the budget [L, A]:

- at 103 GB, T=32, skipping 80% of keys (both PrefetchIndex and GetAt) gains 12.5%. linear extrapolation to 100% skip gives about 15.6%. perf says lookups are 10.6 + 8.0 = 18.6% of samples. so the whole lookup path is worth at most 15 to 19% of wall time at 103 GB, and "free memory" cannot give more.
- at 8 GB the skip oracle lost because of a data-dependent branch and holes in the 16-batch. so any later oracle must NOT use a data-dependent skip. the ladder in section 1.4 has no branch.
- K2_B 64 vs 16 is a null on luna (s20, s9_103.log) [L, from next_steps_plan]. that is the first MLP data point: going from 16 to 64 lookups in flight changes nothing, so the machine is already past the knee of the MLP curve. more prefetch depth is dead, which is also why S16 gave only -10%.

so the real question is not "how do we hide more latency" but "what is the 10% in PrefetchIndex, and is any of it removable".

## 1. what PrefetchIndex really costs

### 1.1 the code [S]

```
size_t idx = FastMod(hc);            // 64x64->128 multiply by cap_recip_, then one more multiply and a correction
__builtin_prefetch(&table_[idx],0,3);
return idx;
```

FastMod is about 2 multiplies, roughly 6 to 8 cycles latency, throughput near 2 cycles. that is 2 to 3 ns. it cannot be 10% of a run that spends 100+ ns per lookup elsewhere. so if perf puts 10 to 12% on this symbol, the samples are the prefetch instruction (or its skid) waiting, not the arithmetic.

### 1.2 why a prefetch can be slow [P, G]

three mechanisms, in the order I believe them:

1. address translation is not free for a prefetch. on Intel a software prefetch needs its physical address before it can retire (it does a TLB lookup and, on a miss, a page walk). it does not wait for the data, but it does wait for the walk. the table is 103 GB. with 2 MB pages that is 51,500 pages against a 2048-entry shared STLB (reach 4 GB), so about 96% of lookups miss the STLB at 103 GB [A: 1 - 2048/51500]. at 8 GB (4096 pages) about 50% miss. at 16 GB (8192 pages) about 75%. a 4 KB page walk reads a PTE that itself lives in a 206 MB page table (103 GB / 4 KB x 8 B), larger than L2 and about equal to one socket's L3, so with 4 KB pages the walk is a second DRAM round trip. with 2 MB pages the PDE array is 412 KB (51,500 x 8 B), which mostly stays in L2/L3, so a walk costs maybe 20 to 70 cycles [G]. this explains why S14 mattered so much and says the remaining walk cost is real but small per lookup.
2. line fill buffer exhaustion. Golden Cove has 16 L1D fill buffers per core, shared by both SMT threads [P: Intel optimization manual, L1D miss handling; I could not fetch the manual text, treat 16 as the commonly cited figure]. a batch of 16 prefetches issued back to back, with the previous batch still in flight (S16 keeps two batches), asks for up to 32 outstanding lines. the 17th prefetch cannot allocate a buffer, sits in the load pipeline, and blocks later loads (including NextMinimizer's table reads) until the oldest fill returns, one DRAM latency (about 110 to 130 ns local on SPR [G]). by Little's law the steady rate is 16 lines per 120 ns = 133 M lines/s per core, and luna needs about 0.6 M lookups/s per thread [A: 218M lookups / 32 threads / 12 s]. so the buffers are almost never the average limit (0.4% utilisation), but a burst of 16 prefetches can stall for one latency per batch. that is about 120 ns / 16 = 7.5 ns per lookup [A]. small but visible.
3. sampling skid. perf samples with cycles are attributed to the instruction that is waiting to retire. a stalled prefetch (walk or buffer) is charged to PrefetchIndex. anything stalled in the batch loop after the prefetch gets charged to the next instruction. so the symbol share is an upper bound on the true prefetch stall.

sizes tell us what scales. [A from p32_summary x walls]: PrefetchIndex is 11.8% of 7.5 s at 8 GB, 10.6% of 12.3 s at 103 GB. absolute weight grows by about 1.5x with a 13x bigger table. GetAt grows 1.5% to 8.0% share, about 9x in absolute weight. so most of PrefetchIndex is a size-insensitive floor (hash, FastMod, issuing, buffer bursts) plus a 1.5x size-dependent part (walks). GetAt carries the real exposed miss growth (lines not yet arrived when GetAt reads them, plus second-line probes, see 3.1).

caveat: share x wall x 32 threads / 218M lookups gives 110 to 190 ns per lookup for PrefetchIndex, which is too big to be real. the denominator includes the load phase and idle threads. do not quote the ns, only the ratios.

### 1.3 perf stat measurements (all exist on luna)

run on stock-vs-S19 at 8 GB and 103 GB, T=32, same reads, `perf stat -e` with the events below, count in the classification phase only if possible (otherwise subtract a load-only run with 0 reads, which E1 already uses):

| event | what it says | prediction if page walks matter | if buffers matter |
|---|---|---|---|
| cycles, instructions | baseline IPC | IPC below 1 at 103 GB | same |
| dtlb_load_misses.walk_completed_2m_4m and .walk_completed_4k | walks per lookup by page size | about 0.96 per lookup at 103 GB, about 0.5 at 8 GB, near 0 for 4K if THP works | no signal |
| dtlb_load_misses.walk_active (cycles) / cycles | share of time a walker is busy | 3 to 10% of cycles at 103 GB | low |
| dtlb_load_misses.stlb_hit | L1 dTLB miss that STLB catches | big at 8 GB | none |
| mem_inst_retired.stlb_miss_loads | retired loads with true STLB miss | about 1 per lookup at 103 GB | none |
| l1d_pend_miss.fb_full (and fb_full_periods) | cycles a load wanted a fill buffer and found none | small | clear spikes, scales with K2_B |
| l1d_pend_miss.pending / pending_cycles | average outstanding L1 misses (that ratio is the measured MLP) | the key number: if it is 10 to 14 we are at the buffer ceiling, if 2 to 5 we are latency bound by a lack of parallelism | |
| offcore_requests_outstanding.demand_data_rd / cycles_with_demand_data_rd | outstanding L2 misses, uncore view of MLP | same | |
| mem_load_retired.l3_miss, l3_hit, fb_hit | where the GetAt loads land | l3_miss per lookup near 1.0-1.3 at 103 GB, fb_hit high means GetAt arrives while the prefetch is still in flight (prefetch too late) | |
| sw_prefetch_access.t0 | count of prefetches executed | equals lookups, sanity check | |
| memory_activity.stalls_l3_miss / cycles | fraction of cycles stalled on L3 misses | at most about 15% at 103 GB if the oracle is right | |

decision rules [A]: (a) walk_active / cycles above 5% at 103 GB means TLB reach is worth chasing (section 1.4 step B). (b) fb_full above 2% of cycles or average MLP above 12 means cap the in-flight lines (try K2_B 8) and the idea of more prefetching is dead. (c) fb_hit near 30% of GetAt loads means the prefetch lead is too short, which contradicts the K2_B 64 null, so expect it low. (d) l3_miss per lookup well above 1.3 means second-line probes (3.1) matter.

### 1.4 the ladder oracle (run FIRST, time only, wrong output by design)

nothing data dependent, so no branch or batch-hole artifact (the flaw that wrecked the skip oracle at 8 GB). in a copy of guarded S19 (like e1/src_ceil), change `FastMod(hc)` to `FastMod(hc) & mask` or fold idx into a region of R bytes, keep everything else. rungs at T=32, full 1.87M reads, 3 interleaved reps, classification time:

| rung | region | what it removes | reads as |
|---|---|---|---|
| R0 | whole 103 GB | nothing | reference |
| R1 | 4 GB (fits STLB reach with 2 MB pages) | page walks, DRAM stays | R0 - R1 = TLB cost |
| R2 | 128 MB (fits L3, still per-socket) | most DRAM misses too, no walks | R1 - R2 = DRAM latency/bandwidth cost |
| R3 | 8 MB (fits L2 mostly) | L3 latency | R2 - R3 = L3 cost |

the sum R0 - R3 is the real ceiling for any layout change that only moves lines (aligned buckets, compact cells, locality ordering). I predict R0 - R3 is about 12 to 16% of wall at 103 GB [A from the skip oracle], R0 - R1 about 2 to 5% [G], and nearly flat at 8 GB. kill rule: if R0 - R2 is under 5% at 103 GB, no layout idea can beat noise and section 3 is closed. run the same ladder with 1 thread to separate latency from contention.

## 2. a model that can rank ideas (replacing uncalibrated Sniper)

### 2.1 why not a full simulator

Sniper reported numbers we cannot trust (uncalibrated). a full-system simulator also cannot see page-walk caching or the real SPR fill-buffer policy. what we actually need is a ranking among a handful of layouts, and the oracle says the total headroom is about 15%. a 40-line analytic model fitted to real timings is the right tool.

### 2.2 the model (per thread, steady state)

per lookup, `t = c + e`, c = non-memory work (scan, hash, classify), e = exposed memory time.

- lookups in flight `m = min(B_eff, F)`, B_eff = lookups with a prefetch outstanding (about 1.5 B with two batches), F = fill buffers per thread (16 per core, 8 each if both SMT threads on the core run).
- memory latency per line `L = L_dram` for a miss, `L_l3` for an LLC hit, with a hit probability `h_l3` from the footprint (touched lines / L3) and the key skew from the trace (the real E1 hot-slot trace gives the hit curve, 56% for 262K slots).
- translation `W = p_walk x w`, p_walk from the STLB reach table (4 GB, 2 MB pages: 1 - 2048 x 2MB / size), w about 25 cycles for 2 MB, 25 + L for 4 KB, about 8 for a 1 GB PDPTE-cached walk. page walkers: 4 per core on Golden Cove [P], so concurrent walks are bounded at 4 per core.
- lines per lookup `n` (1 + the cross-line probability, section 3.1).
- exposed time per lookup `e = max(0, n(L + W) / m_eff - c_slack)` where `c_slack` is the compute that runs between the prefetch and the use (about B x c, one batch). when B x c exceeds L + W the exposed time is zero and extra batch size does nothing, exactly the K2_B null.
- throughput cap: lines/s per core <= F / L; per socket bandwidth = lines/s x 64 B x active cores (check against about 300 GB/s per socket SPR DDR5 peak [G]).

free parameters: c, L, w, m_eff. four numbers.

### 2.3 how to fit it to luna's real timings

the project already has four independent series that identify these: S9 (batch 1 vs 16, 103 GB: ~87 to ~76 s on the old base, a 12% change), S14 (4 KB vs 2 MB pages: 103 GB 35 s to 13-20 s, 8 GB 10.36 to 8.29 s, 16 GB 11.9 to 9.15 s), S16 (single vs double batch: 19.18 to 17.21 s, -10%), the T sweep (contention), the K2_B 16 vs 64 null, and the ladder (section 1.4) which directly gives R0 - R3. step 1: a stand-alone microbenchmark (200 lines, the A4 "k in flight" probe) that reads random lines of a 100 GB hugepage buffer with k = 1, 2, 4 ... 64 independent loads in flight, per page size (4 KB madvise off, 2 MB), per T (1, 8, 32, 64 with SMT). that curve is L, F, and w without any kraken2 code. step 2: take c from a run of 1.87M reads on the 50 MB DB (everything in L2), where e is about zero. step 3: check the model against S9, S14, S16 and the ladder without refitting. accept only if it predicts four of five within 10%.

### 2.4 what it should predict (before fitting, [G])

- batch size: knee at B x c about L + W. with c about 20 to 40 ns per lookup [G] that is B of 4 to 8. B above F/1.5 (about 10) gives nothing and 64 is harmless. matches the null.
- 2 MB vs 1 GB pages at 103 GB: p_walk goes 0.96 to about 0.84 with 1 GB (103 pages vs 16 STLB 1G entries [P, G]) but w drops from about 25 to about 8 cycles, so the saving is about 17 cycles x 0.9 = 15 cycles = 5 ns per lookup, which is 2 to 4% of a lookup that costs 100+ ns of overlapped time. predicted gain under 3% at 103 GB, about 0 at 8 GB (8 pages, fits TLB). cannot be tested on luna now (1 GB pool is empty, needs root), and the ladder R1 gives the upper bound without root.
- SMT (64 threads on 32 cores): F halves per thread, c is shared, so the model predicts a 5 to 10% gain at 103 GB only if e is large and a loss if c is large. the repo already has T=64 data, fit it.
- design ideas, per model, [G] numbers as relative lookup-path time at 103 GB:
  - aligned 64 B buckets (3.1): n from about 1.2 to about 1.05, lookup time -12 to -14%. since lookup path is under 19% of wall, wall gain 1 to 3%.
  - 24-bit cells: n unchanged, size -25%, p_walk unchanged, L unchanged, h_l3 unchanged. wall gain only through the load phase (3.2).
  - 8 keys per line bucketed with a fingerprint (3.3): n about 1.0, but a bigger line-aligned bucket needs a 32-bit key plus 32-bit value per entry, 2x the table. net loss.
  - locality ordering (3.4): n_eff 1.0 to about 0.5 per lookup in the best case, predicts the largest lookup-path drop (up to -40%), wall gain at most 5 to 7% from the skip table (45% fewer lines gave 1.3% on the skip oracle, 60% gave 5.3%).
- ranking: locality ordering > aligned buckets > 6/24-bit cells (lookup path only) = load-phase win. every one below the 15% ceiling, each probably under noise on a single wall-clock number. the model's real use is to say which to build first and which fail the kill rule.

## 3. layouts that cut lines or TLB reach without a front table

### 3.1 aligned buckets or prefetch-both-lines (cheap, build and rebuild-free variants)

in S19 the cell is 4 bytes, 16 per 64 B line, table is linear probing with a load of about 0.7 [S, G: compact_hash.cc, GetAt]. probe length at load a: hit (1 + 1/(1-a))/2 = 2.2 cells, miss (1 + 1/(1-a)^2)/2 = 6.1 cells [A, Knuth]. a run starting at a uniform cell crosses the next 64 B line with probability (L-1)/16: 7.5% for a hit, 32% for a miss. if half the lookups miss (reads from non-matching organisms, plausible, unmeasured) the average is about 0.2 extra lines per lookup, and that second line is NOT prefetched, so GetAt takes a full exposed miss on it. 20% of lookups x one DRAM latency is plausibly a large part of why GetAt is 8% at 103 GB but 1.5% at 8 GB. note the +1 line is adjacent so the hardware adjacent-line pair prefetcher may catch some, which the measurement will show.
- cheapest oracle (no rebuild): in PrefetchIndex also prefetch the next line when `idx & 15 >= 10` (adds about 37% extra prefetches, covering most crossings). a gain at 103 GB means crossings matter. measure mem_load_retired.l3_miss per lookup to confirm the 1.2.
- real fix: choose the bucket as hash to a 16-cell line, probe within the bucket and spill to the next line only when it is full. bucket overflow at load 0.7 with mean 11.2 per bucket: P(>16) about 7% (Poisson) [A], so the typical lookup reads 1.07 lines instead of 1.2. requires a rebuild but no change to key/value bits or table size.
- double hashing: the code is compiled out (-DLINEAR_PROBING); with it each probe is a new random line, so n goes up, not down. keep linear.

### 3.2 more compact value encoding, smaller cells (the 6-bit/bitmask thesis item)

a smaller table does three things, and only one matters here [A]:
1. fewer pages: 103 GB at 24-bit cells is 77 GB, 51,500 to 38,600 pages. p_walk goes 0.96 to 0.95. no change. TLB reach is 4 GB, we would need a 25x shrink.
2. higher LLC hit: L3 is 105 MB per socket (210 MB total) against 77 GB, hit chance from 0.2% to 0.27%. no change for random lookups. only the skewed hot slots hit, and those already hit (the trace says 1M hot slots cover 90% = 64 MB of lines).
3. less data to load and to fault in. at 103 GB perf shows 14.2% + 10.6% = 24.8% of samples in two kernel addresses (0xffffffffb3247ff8 and 0xffffffffb3ba2be7) for the guarded build, 11.4 + 9.7 = 21% for stock. those are the pread/page-zeroing/fault costs of loading the table. they scale linearly with bytes. 25% fewer bytes would take 5 to 6% off the run at 103 GB, a bigger gain than any lookup-side idea. cannot be confirmed because the two kernel symbols were never resolved (perf report without kallsyms access); with sudo-free `perf report --sort dso` we only see [k]. unresolved: that 21 to 25% could also be the memory zeroing for THP, which a smaller table also shrinks.

so cell shrinking is a LOAD-PHASE and index-size win (and with -M mmap a page-cache win), not a lookup win. the lookup ceiling in 1.4 will not move. note the 16-bit cell false-positive law from the report still binds accuracy, and 24 bits is the sweet spot for the model only because it keeps a byte boundary (3 B cells straddle lines; 21 cells per line with 1 B waste, needs unaligned loads: cost small).

### 3.3 bucketed table with 8 keys per line

8 entries x (key 4 B + value 4 B) = 64 B. the current 32-bit cell packs key and value together (key_bits + value_bits = 32 [S: populate()]). a separate 8-key line has 2x the bytes per entry, doubling pages and load. only worth it when a fingerprint SIMD compare removes the second line, but 3.1 already gets n to 1.07 at the same size. drop it.

### 3.4 locality-preserving build order (kache-hash style)

kache-hash [P: Khan, Patro, Pandey preprint, jamshed/kache-hash, 1.58 to 2.62x insertion, up to 6.1x query, 7.39x fewer cache misses, bound O(1/r) misses per op with r the minimizer run length] exploits consecutive k-mers sharing a minimizer, so they land in the same bucket. kraken2 is different in a useful way: it looks up the minimizer itself, not the k-mer, and consecutive lookups of a read are the 31-mers chosen as window minimizers, with a new one about every 2 to 3 bases in a 35-mer window [A]. consecutive minimizers overlap by about 28 of their 31 bases. so a sub-minimizer (say the smallest 15-mer inside the 31-mer) is shared by consecutive minimizers with probability roughly 1 - shift/17 = 0.8 [A, G].
- idea: line index = hash(inner 15-mer minimizer) for the high bits of the position, with the low bits from the full hash, so consecutive lookups hit the same line or the same 2 MB page. the table stays a pure function of the key, so classification output is unchanged (key semantics identical, only placement). cost: inner minimizers cluster: 4^15 = 1G inner values, 25G cells, mean 25 entries per inner value but with skew (low-complexity k-mers, repeats). a 64 B line holds only 16, so the group must span 2 to 4 consecutive lines with a spill rule, and a skewed bucket overflows into neighbours.
- what it saves: n_eff per lookup goes from 1.0 to about 0.5 to 0.6 lines when consecutive lookups share a line within the 16-batch (an L1/fill-buffer hit instead of a DRAM line), and page reuse makes p_walk drop sharply (the same 2 MB page covers consecutive lookups, p_walk about 0.96 to about 0.5). the skip oracle bounds it: 45% fewer lines gave 1.3% and 60% gave 5.3% at 103 GB, but that skipped GetAt as well, and a share-the-line trick still pays the GetAt compare. so expect 1 to 3% wall at 103 GB, near 0 at 8 GB. honest verdict: the biggest lookup-side win but still under 5%, and it needs a complete rebuild and key-bit changes at build time. the S19 dedup (`skip_lookup` for consecutive equal minimizers) already takes the cheapest form of this.
- cheap evidence before building: from the E1 trace (hash `hc` per lookup, 116.6 lookups per read at 8 GB) compute offline, per read, the fraction of consecutive lookups whose inner-15-mer minimizer (or whose idx >> 4 under the proposed mapping) is equal. if it is under 40% give it up. this is a one-hour awk or C check on a trace we already have.

### 3.5 lower load factor

lowering the load from 0.7 to 0.5 shortens a miss from 6.1 to 2.5 cells (crossing 32% to 9%), but costs 1.4x memory (103 to 144 GB), more load time and more pages. gain at most the same 0.2 line as 3.1, paid for with 40% more bytes. 3.1 dominates it.

## 4. do this in this order

1. ladder oracle R0 to R3 (1.4), 3 reps each, T=32 and T=1. half a day. it fixes the ceiling for everything below and needs no rebuild.
2. perf stat events (1.3) on the same two binaries. decides TLB vs buffers vs second line.
3. prefetch-next-line oracle (3.1). 1 hour, one line of code.
4. offline trace check for 3.4 (shared inner minimizer fraction) and crossing probability from the real table and trace.
5. fit the analytic model (2.3) to the microbenchmark plus S9/S14/S16, then use it to rank. only then build aligned buckets (3.1) or the load-phase work for 3.2.

## 5. caveats

- fill-buffer count (16), STLB 2048 entries and 4 page walkers are published values for Golden Cove from memory of the Intel optimization manual and common microarchitecture write-ups, not fetched this session (web search returned no Intel manual text); confirm the numbers with the microbenchmark.
- Little's law arithmetic uses 110 to 130 ns local DRAM, a guess for SPR.
- the miss fraction of lookups (reads from absent organisms) is unmeasured; it drives the crossing estimate.
- AMAC [P: asynchronous memory access chaining] and group prefetching (Chen et al. ICDE 2004, 2.0 to 2.9x on join) solve the same latency problem S9/S16 already solve; I found nothing in them that adds beyond S16 for a single dependent-free lookup per slot.

## summary

1. the whole lookup path is under about 19% of wall at 103 GB, so any pure memory idea is capped near 15%, and K2_B 16 to 64 being null shows MLP is already saturated.
2. PrefetchIndex is mostly a size-insensitive floor (hash, issue, buffer bursts) plus walk latency; FastMod itself is about 2 to 3 ns; GetAt carries the size-dependent exposed misses.
3. first test is a no-branch region-shrink ladder oracle (103 GB / 4 GB / 128 MB / 8 MB), which separates TLB, DRAM and L3 costs and sets the true ceiling; second is perf stat with walk_active, fb_full and l1d_pend_miss.pending (measured MLP).
4. a four-parameter analytic MLP model (c, L, w, buffers) fitted to a k-in-flight microbenchmark plus S9/S14/S16 is the right replacement for Sniper; it predicts the batch knee near 4 to 8 and under 3% for 1 GB pages.
5. smaller cells do not help lookups (no change in pages or LLC hit) but cut load-phase kernel time (21 to 25% of samples at 103 GB), worth about 5 to 6% at 24-bit.
6. best lookup-side idea is aligned buckets (about 0.2 fewer lines per lookup, cross-line second probe is unprefetched), then minimizer-locality placement (needs a trace check first); expected wall gains are 1 to 3% each, not 10%.
