# cycle 1, R3 vote, a1_dsa

## 1. verdict

- **build list (section 2): AGREE.** it differs from my R2 list only in M9's rank and M15's place, and the reasons given for both are fair.
- **measure-first list (section 3): DISSENT.** one change, below.

## 2. change

1. **move M22 (lookup census) to rank 1, and M1 to rank 2.**
   - M22 costs 15-30 min. M1 costs 1.5-2 h.
   - M1 has to split its results into capped and uncapped dbs, and that needs f for each db first. E1 and M12 also need d x f for their predictions.
   - if luna's 8GB turns out to have a threshold of 0, section 1.2's capped rows and section 1.3 change before M1 is read.

## 3. factual errors

1. **section 1.2, "about 1 lookup per 30 positions".** the counts give 1 per 36: 9,871,933 / 354,164,193 = 1 / 35.9 [repo: `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`, arith].
2. **section 1.2, "at 1/36 that would be ~3.9 µs per lookup".** 162.6 ns x 36 = 5.85 µs [arith]. either correct it to ~5.9 µs, or state what cpu share was subtracted first.
3. **section 1.2, "our 8GB and 16GB are capped standard builds", with f ≈ 0.088.** that f was measured on the WSL2 prebuilt `~/eskape_db` [repo: `dorado-kraken-research/docs/knowledge_base.md` 18.1], not on luna's files.
   - luna's 8GB f is [UNCLEAR] until M22 reads `opts.k2d`
   - the 16GB f has never been measured
   - tag both as [UNCLEAR], not as fact
