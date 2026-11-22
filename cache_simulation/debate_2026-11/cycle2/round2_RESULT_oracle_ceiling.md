# cycle 2 result: oracle ceiling kills the static hot-set front table (luna, 2026-11-23)

experiment: a time-only upper bound, the prosecutor's cheapest falsifier. in a copy of the guarded S19 (e1/src_ceil), for a fixed fraction of keys (chosen by hash bits, so repeated minimizers always get the same decision, like a hot set) skip both PrefetchIndex and GetAt and reuse the previous looked-up taxon. a real front table cannot be cheaper than this, because a real front probe costs time and a real hit still needs the value. output is wrong by design (time only). T=32, all 1,872,777 reads, plain --report, 3 interleaved repetitions. raw: data/ceil.csv.

wall seconds (3 reps each):

| variant | 103 GB | 8 GB |
|---|---|---|
| guarded S19 (reference) | 12.53 12.08 12.16 | 7.50 7.51 7.48 |
| hook, skip 0% (control) | 12.54 12.35 12.30 | 7.57 7.65 7.56 |
| skip 25% of keys | 12.49 12.46 12.29 | 7.90 7.97 7.91 |
| skip 45% | 12.19 12.34 12.16 | 8.11 8.11 8.10 |
| skip 60% | 11.74 11.69 11.67 | 7.96 7.93 7.97 |
| skip 80% | 10.84 10.80 10.69 | 7.57 7.61 7.58 |

medians vs the skip-0 control: 103 GB: 25% -> +0.9%, 45% -> -1.3%, 60% -> -5.3%, 80% -> -12.5%. 8 GB: 25% -> +4.5%, 45% -> +7.1%, 60% -> +5.1%, 80% -> +0.3%. the hook itself costs about 1.6% at 103 GB and 1% at 8 GB.

## reading

- the 262,144 hottest slots cover 56% of lookups in the 8 GB trace and 1M slots cover 90%. a front table small enough to stay in L2 (a few MB, 262K entries) therefore covers about 45% to 56%. at that coverage the oracle gains about 0% at 103 GB and LOSES about 7% at 8 GB.
- the loss at 8 GB is most likely branch misprediction plus holes in the 16-lookup batches (the skip decision is data dependent and close to 50/50). a real front probe has the same branch and the same holes, plus its own probe latency.
- only at 80% coverage does 103 GB gain a real 12%, and 8 GB only breaks even. 80% coverage needs about 600K to 1M entries (10 to 16 MB with 5 entries per 64-byte line), which will not stay L2-resident and whose probe cost is not in this bound.
- both kill criteria agreed in round 2 fire: gain under 3% at 103 GB for the reachable hit rates, and a loss at 8 GB.

## verdict

the static hot-set front table is falsified as a wall-clock win at the table sizes that fit in cache, before writing any of it. this saved the 2 to 4 days of building it. the prosecutor's pessimism (about 0 to +2% at 103 GB, about 0% at 8 GB) was right and the defender's 5 to 9% at 103 GB was not supported. a 1M-entry table is the only untested corner (oracle says up to about 10% at 103 GB if it were free, 0% at 8 GB) and is not worth building given its probe cost.

lesson recorded for the next cycles: any idea that changes which lookups hit memory must first pass an oracle ceiling, because S19 already overlaps most of the miss latency and a data-dependent branch in the batch loop is itself costly.
