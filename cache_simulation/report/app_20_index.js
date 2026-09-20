/* ---------- experiment index (chronological) ---------- */
const INDEX = [
  { n: 1, d: "Sep 4", g: "setup", t: "Simulator choice: Sniper over TEJAS", x: "Chose Sniper, a cycle-level CPU simulator, for the cache study. A same-day reversal toward TEJAS was undone. No data; a decision recorded in the log.", a: "how" },
  { n: 2, d: "Sep 4", g: "setup", t: "Persistent tmux session and proxy on Luna", x: "Luna needs a logged-in tmux session and proxy variables for internet access. Set up once so long jobs survive disconnects.", a: null },
  { n: 3, d: "Sep 4", g: "setup", t: "Cloned, built and disk-checked Sniper", x: "Cloned Sniper, installed the missing build dependencies, built it, and checked free disk on the shared machine. Result: a working build.", a: "setup" },
  { n: 4, d: "Sep 4", g: "setup", t: "Smoke test on /bin/true (fast-forward and detailed)", x: "Ran a do-nothing program in both modes to prove the simulator itself works before touching a workload. Both exit cleanly; detailed mode gave 0.66 IPC and 0 memory-consistency errors. Every later result is detailed mode.", a: "how" },
  { n: 5, d: "Sep 4", g: "setup", t: "Read Luna's real cache geometry and clock", x: "Read sizes, ways, sets and line size from the machine's sysfs files: L1d 48 KB 12-way, L1i 32 KB 8-way, L2 2 MB 16-way, L3 105 MB 15-way. Clock is Intel's 2.1 GHz base spec, not measured.", a: "setup" },
  { n: 6, d: "Sep 4", g: "setup", t: "Wrote luna.cfg", x: "Encoded the real geometry as a Sniper overlay config, modeling the L3 as 96 per-core mesh slices of 1,125 KB. L3 speed, replacement policy and memory timing remain placeholders.", a: "setup" },
  { n: 7, d: "Sep 4 to 8", g: "setup", t: "Config debugging (four bugs)", x: "Wrong -c syntax, comma-joined flags, cache-size validation abort, and a crash from a non-power-of-2 set count. Fixed by using two separate -c flags and the plain mod hash.", a: "setup" },
  { n: 8, d: "Sep 8", g: "setup", t: "SSH access and crash root cause", x: "Direct SSH to Luna enabled running commands. The crash was traced to the xor_mod hash going out of range for 1,200 sets, by reading Sniper's source.", a: "setup" },
  { n: 9, d: "Sep 8", g: "setup", t: "Found kraken2 is a Perl wrapper", x: "Sniper showed near-zero work because it was instrumenting Perl. Using strace to find the real compiled classify binary and its raw arguments fixed it.", a: "setup" },
  { n: 10, d: "Sep 8", g: "setup", t: "First detailed kraken2 run (10 reads)", x: "25.1 M instructions, 14.3 M cycles, IPC 1.76, 51,558 unique cache lines, correct 7-of-10 classification, in 114 s.", a: "assoc10" },
  { n: 11, d: "Sep 8", g: "software", t: "Width sweep: 4 to 64-way, 10 reads, 50 MB", x: "More ways means more instructions, cycles and memory touched (64-way: +11% cycles, 4.3× cache lines vs 4-way). IPC flat. Reproduces the real-hardware trend without atomics.", a: "assoc10" },
  { n: 12, d: "Sep 8", g: "fix", t: "Found the true no-cache S0", x: "The earlier 'baseline' binary already contained an S2 cache. The real stock build is kraken2-src-baseline, with no S2 code.", a: "fixes" },
  { n: 13, d: "Sep 8", g: "setup", t: "Built and timed the 50-read workload", x: "Stock on 50 reads took 188 s versus about 115 s for 10 reads, showing most fixed cost is database load (about 96 s).", a: "workloads" },
  { n: 14, d: "Sep 8", g: "software", t: "Database-size comparison: 50 MB and 8 GB", x: "On 50 MB the 4-way cache costs about 10% more cycles; on 8 GB it uses 24% fewer instructions and runs 1.83× faster. The cache's value flips with database size.", a: "dbsize" },
  { n: 15, d: "Sep 8", g: "software", t: "Extended to 16 GB and 103 GB", x: "4-way is 2.05× (16 GB) and 1.97× (103 GB) faster than stock. The benefit rises then dips slightly at 103 GB.", a: "dbsize" },
  { n: 16, d: "Sep 8", g: "software", t: "Added 8-way; built 1-way from scratch", x: "No 1-way build existed. Built from the pristine source with a patch script; its classification output is identical to stock. Complete five-variant table across four databases.", a: "dbsize" },
  { n: 17, d: "Sep 8 to 9", g: "fix", t: "2,000/10,000-read and full-file jobs cancelled", x: "The head of the read file has unusually long reads (17.5 kbp vs a 3.4 kbp true mean), so read count is a poor size measure. The jobs were slow for that reason and were dropped, then 2,000 reads was re-queued alone.", a: "workloads" },
  { n: 18, d: "Sep 8", g: "fix", t: "Wall-clock contamination caught", x: "1-way took 454 s versus 8-way 341 s at nearly identical cycles because jobs overlapped. Wall-clock discarded; clean rerun.", a: "fixes" },
  { n: 19, d: "Sep 9", g: "fix", t: "Cross-batch drift and the fair batch", x: "Batches hours apart ran at 14 vs 8 s per million cycles. One fair batch of 20 runs (5 variants × 4 databases) ran together.", a: "dbsize" },
  { n: 20, d: "Sep 9", g: "fix", t: "Metric corrected from wall-clock to cycles", x: "Sniper's wall-clock is simulator time and tracks instruction count. Cycles ÷ clock is the real-time proxy. By cycles, 4-way wins or ties at every database size.", a: "dbsize" },
  { n: 21, d: "Sep 9", g: "software", t: "Figures 1 to 7", x: "Publication-style charts of the fair-batch data (widths, cycles by database, speedup, footprint, IPC, miss breakdown, machine comparison).", a: "data" },
  { n: 22, d: "Sep 9", g: "software", t: "Report 'The 4-Way Verdict' v1, then v2", x: "Published a report, then republished it with the cycles-based corrections after the metric error was found.", a: null },
  { n: 23, d: "Sep 9", g: "hardware", t: "Desktop and Orin-sized cache configs", x: "Reran stock and 4-way on 50 MB and 8 GB under a Ryzen 5 5600X and a Jetson Orin cache setup. 8 GB win: 1.83× (Luna), 1.94× (desktop), 1.65× (Orin). 50 MB about 0.9× on all.", a: "profiles" },
  { n: 24, d: "Sep 9", g: "hardware", t: "Real Orin / DynamoRIO route explored, paused", x: "Sniper's x86 front end cannot instrument ARM binaries; the ARM route needs recording on the board. Chose the config-only stand-in instead.", a: null },
  { n: 25, d: "Sep 9 to 12", g: "software", t: "2,000-read job on 50 MB", x: "All five variants took 12 to 15 hours each. Every width lost to stock (4-way 1.28× slower, 16-way 1.39×). The small-database loss is not a warm-up effect.", a: "r2000" },
  { n: 26, d: "Sep 11", g: "fix", t: "Correction: it was database size, not read count", x: "The first explanation of the 2,000-read result was withdrawn: that database was already losing at 50 reads.", a: "r2000" },
  { n: 27, d: "Sep 9 to 11", g: "software", t: "Figures 8 to 11", x: "Simulation-time table, 2,000-read charts, and the results table.", a: "timemodel" },
  { n: 28, d: "Sep 12 to 14", g: "hardware", t: "Hardware L3 associativity sweep, 50 MB", x: "1/4/8/15/16/30-way × 10/50/100/500 reads, no software cache, 24 runs. Under 1% spread at every size: no effect.", a: "hwassoc" },
  { n: 29, d: "Sep 9", g: "setup", t: "To-do list saved from the Q&A", x: "Queued two hardware questions (flat L3, isolated hardware associativity). Both were done later.", a: "hwnot" },
  { n: 30, d: "Sep 15", g: "hardware", t: "laptop.cfg (Ryzen 7 5800H)", x: "Read core count, clock, L2 and L3 size from your laptop; ways from AMD's spec. L3 split into 8 slices of 2,048 KB (a power-of-2 set count, so no hash override).", a: "setup" },
  { n: 31, d: "Sep 15 to 19", g: "software", t: "laptop_sweep: 32 runs", x: "Reads 10/50/100/500 × stock, 1, 4, 8-way × 8 GB and 16 GB. Cache wins small, loses large; 8 GB flips by 100 reads, 16 GB by 500.", a: "laptop" },
  { n: 32, d: "Sep 15", g: "analysis", t: "Cache-size research brief", x: "Wrote a multi-agent brief: five agents, three iterations, hypotheses H1 to H4, with a full file index.", a: "debate" },
  { n: 33, d: "Sep 15", g: "setup", t: "Step 0: where cache size is set", x: "The sizing formula (S3ComputeNumSets) and its limits are compile-time constants, so each size needs its own build. Pinning both limits to one value pins the size.", a: "internals" },
  { n: 34, d: "Sep 15", g: "setup", t: "Six size-pinned 4-way binaries", x: "Built for 2,048 to 1,048,576 sets; all classify identically to stock (7 of 10 reads, empty diff).", a: "size" },
  { n: 35, d: "Sep 15", g: "software", t: "Size sweep: 50 MB (10 reads)", x: "14.2 M cycles at five sizes, 15.1 M at 65,536 (+6.3%). Stock is 14.1 M, so no size beats stock. A tail run's results were recovered by hand.", a: "size" },
  { n: 36, d: "Sep 15", g: "fix", t: "50 MB pass redirected to 103 GB", x: "After four of six 50 MB sizes, the small-database pass was stopped (already known to lose) and the remaining effort moved to the big database.", a: "size" },
  { n: 37, d: "Sep 15", g: "software", t: "Size sweep: 103 GB (10 reads)", x: "Flat 15.1 M cycles except 16.0 M at 65,536 (+6.0%).", a: "size" },
  { n: 38, d: "Sep 15", g: "software", t: "Size sweep: 8 GB and 16 GB (50 reads)", x: "8 GB flat 27.9 M with 28.6 M at 65,536 (+2.5%); 16 GB flat 29.3 M with 29.6 M (+1.0%).", a: "size" },
  { n: 39, d: "Sep 15", g: "software", t: "True no-cache baseline for the size sweep", x: "Stock at the sweep's exact config: 14.1 M cycles on 50 MB. Every S2 size is at or above it.", a: "size" },
  { n: 40, d: "Sep 15", g: "analysis", t: "Five-agent debate, three iterations (H1 to H4)", x: "H1 confirmed, H2 refuted, H3 refuted on location (magnitude varies), H4 holds only at one thread. Iteration 2's mechanism was overturned by the 103 GB data. Figure 14.", a: "debate" },
  { n: 41, d: "Sep 15", g: "fix", t: "Size-65,536 anomaly and magnitude correction", x: "Quoted +4.4% / +10.2% were instruction deltas; the cycle figures are +2.5% / +6.0%. Best explanation: a hash-distribution artifact of the workload at that mask width.", a: "size" },
  { n: 42, d: "Sep 15", g: "hardware", t: "Hardware L3 associativity on 8 GB and 16 GB", x: "12 runs. 8 GB: 51.7 to 51.8 M cycles for all six settings; 16 GB exactly 60.7 M. Still no effect.", a: "hwassoc" },
  { n: 43, d: "Sep 15", g: "hardware", t: "Flat L3 versus mesh-slice L3", x: "Flat bank is 30.7% slower on 50 MB and 16.6% slower on 8 GB, with lower IPC. The mesh model matters.", a: "flat" },
  { n: 44, d: "Sep 19", g: "software", t: "laptop_sweep finished", x: "500-read tier: 8 GB 1.09× slower, 16 GB 1.02× slower than stock. The win is gone by 500 reads on both.", a: "laptop" },
  { n: 45, d: "Sep 19", g: "software", t: "Long-read scaling: 10/25/50 long reads", x: "Same-source long reads, 8 GB. 4-way speedup 1.42×, 1.20×, 1.05×, then 0.97× at 100 and 0.92× at 500. Crossover between 1.87 M and 4.7 M bases; read length is not the cause.", a: "longread" },
  { n: 46, d: "Sep 19", g: "fix", t: "Full audit of commits and data", x: "Found that figure 14 mixes workloads, the 'peer 8 GB' file is a copy of our data, the 16 GB ladder was unused, and the flat-L3 hit-rate column is wrong.", a: "fixes" },
  { n: 47, d: "Sep 19", g: "analysis", t: "S2 internals audit", x: "Measured per-thread memory from each binary (0 B, 96 KB to 1.5 MB, tiny for size builds), read both source variants, and found S0 and the S2 tree are different kraken2 snapshots.", a: "internals" },
  { n: 48, d: "Sep 19", g: "analysis", t: "FASTQ inventory of all of Luna", x: "86 files, 85 GB, one sequencing run basecalled three ways plus copies. All test workloads are the front of one file.", a: "workloads" },
  { n: 49, d: "Sep 20", g: "analysis", t: "Start-up constant found in the small-workload wins", x: "Stock minus 4-way instructions is +14.4 M at 10 long reads and +14.2 M at 25: a fixed offset, not a per-read saving. Suggests part of the small-workload win is a start-up difference.", a: "longread" },
  { n: 50, d: "Sep 20", g: "analysis", t: "This report", x: "Interactive page generated from the committed data files.", a: "top" },
];
const GROUPS = { all: "All", setup: "Setup", software: "Software cache", hardware: "Hardware", fix: "Corrections", analysis: "Analysis" };

function renderIndex() {
  const chips = $("#idxChips"), ul = $("#idxList");
  let g = "all";
  const draw = () => {
    chips.innerHTML = Object.entries(GROUPS).map(([k, l]) => `<button type="button" aria-pressed="${k === g}" data-k="${k}">${l}</button>`).join("");
    $$("button", chips).forEach(b => b.onclick = () => { g = b.dataset.k; draw(); });
    ul.innerHTML = INDEX.filter(e => g === "all" || e.g === g).map(e =>
      `<li><details><summary><span class="no">${e.n}</span><span class="nm">${e.t}</span><span class="dt">${e.d}</span></summary>` +
      `<div class="det"><p>${e.x}</p>${e.a && e.a !== "top" ? `<p><a href="#${e.a}">Jump to the section</a></p>` : ""}</div></details></li>`).join("");
  };
  draw();
}

/* ---------- committed figures and files ---------- */
const GH = "https://github.com/KathpaliaChirag/Nanopore-project/blob/main/cache_simulation/";
const FIGS = [
  ["fig1", "fig1_width_sweep_10reads.png", "Width sweep, 10 reads (simulator time)"],
  ["fig2", "fig2_cycles_by_db_5variant.png", "Cycles by variant, four databases"],
  ["fig3", "fig3_speedup_vs_nocache.png", "Speedup versus stock, by width and database"],
  ["fig4", "fig4_memory_footprint_by_db.png", "Unique cache lines touched"],
  ["fig5", "fig5_speedup_vs_ipc_dualaxis.png", "Speedup and IPC"],
  ["fig6", "fig6_miss_breakdown_103gb.png", "Where lookups are resolved, 103 GB"],
  ["fig7", "fig7_hardware_comparison.png", "Machine comparison with config table"],
  ["fig8", "fig8_readcount_time_estimate.png", "Simulation time by read count"],
  ["fig9", "fig9_2000reads_cycles_50mb.png", "2,000-read cycles, 50 MB"],
  ["fig10", "fig10_readcount_scaling_same_db.png", "50 vs 2,000 reads, same database"],
  ["fig11", "fig11_2000reads_results_table.png", "2,000-read results table"],
  ["fig12", "fig12_hw_assoc_sweep_null.png", "Hardware associativity, null result"],
  ["fig13", "fig13_hw_assoc_full_table.png", "Hardware associativity, all 24 runs"],
  ["fig14", "fig14_size_sweep_all_db.png", "Cache size sweep, three databases"],
];

function renderData() {
  $("#mRows").textContent = int(DATA.totalRows);
  $("#mFiles").textContent = DATA.inventory.length;
  table("tInv", [
    { h: "File", f: r => `<a href="${GH}measurements/${r.file}">${r.file}</a>`, v: r => r.file },
    { h: "Rows", n: 1, f: r => int(r.rows), v: r => r.rows },
  ], DATA.inventory);
  table("tFigs", [
    { h: "Figure", f: r => r[0], v: r => r[0] },
    { h: "What it shows", f: r => r[2] },
    { h: "File", f: r => `<a href="${GH}charts/${r[1]}">${r[1]}</a>` },
  ], FIGS, {});
}
