/* ---------- 9. hardware associativity ---------- */
function initHwa() {
  const st = { m: "pct" };
  const A = [1, 4, 8, 15, 16, 30];
  const S = [];
  [10, 50, 100, 500].forEach(rd => S.push({ key: "50 MB · " + rd + " reads", db: "50mb", rows: DATA.hwassoc50.filter(r => r.reads === rd) }));
  ["8gb", "16gb"].forEach(db => S.push({ key: DBL[db] + " · 50 reads", db, rows: DATA.hwassocBig.filter(r => r.db === db) }));
  const cols = ["--w1", "--w4", "--w8", "--w16", "--s0", "--ink2"];
  const shapes = ["circle", "triangle", "rect", "rectRot", "star", "crossRot"];
  const at = (s, a) => s.rows.find(r => r.associativity === a);
  const d = (s, a) => (at(s, a).cycles_M / at(s, 15).cycles_M - 1) * 100;
  seg("hwaMode", [["pct", "% vs Luna's real 15-way"], ["cyc", "Cycles (M)"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cHwa", () => ({
    type: "line",
    data: { labels: A.map(String), datasets: S.map((s, i) => ({
      label: s.key, data: A.map(a => st.m === "pct" ? d(s, a) : at(s, a).cycles_M),
      borderColor: css(cols[i]), backgroundColor: css(cols[i]), pointStyle: shapes[i], pointRadius: 6, pointHoverRadius: 8,
      borderWidth: 2, tension: 0, borderDash: s.db === "50mb" ? [] : [6, 4],
    })) },
    options: base({
      interaction: { mode: "nearest", intersect: true },
      plugins: {
        hline: st.m === "pct" ? { y: 0, label: "no change" } : {},
        tooltip: { callbacks: { label: c => c.dataset.label + ": " + (st.m === "pct" ? pct(c.parsed.y, 2) : fmt(c.parsed.y) + " M cycles") } },
      },
      scales: {
        x: ax("Hardware L3 associativity (ways). Luna's real value is 15"),
        y: st.m === "pct" ? ax("Cycles vs the same run at 15-way (%)", { min: -2, max: 2 }) : ax("Cycles (M, log scale)", { type: "logarithmic" }),
      },
    }),
  }));
  const rows = [];
  S.forEach(s => s.rows.forEach(r => rows.push({ s, r })));
  table("tHwa", [
    { h: "Workload", f: x => x.s.key, v: x => S.indexOf(x.s) },
    { h: "Ways", n: 1, f: x => x.r.associativity, v: x => x.r.associativity },
    { h: "Sets", n: 1, f: x => int(x.r.sets), v: x => x.r.sets },
    { h: "Cycles (M)", n: 1, f: x => fmt(x.r.cycles_M), v: x => x.r.cycles_M },
    { h: "vs 15-way", n: 1, f: x => pct(d(x.s, x.r.associativity), 2), v: x => d(x.s, x.r.associativity) },
    { h: "IPC", n: 1, f: x => fmt(x.r.ipc, 2), v: x => x.r.ipc },
    { h: "L2 hit %", n: 1, f: x => fmt(x.r.l2_hit_pct, 2), v: x => x.r.l2_hit_pct },
    { h: "LLC hit %", n: 1, f: x => fmt(x.r.nuca_hit_pct, 4), v: x => x.r.nuca_hit_pct },
    { h: "Sim wall (s)", n: 1, f: x => int(x.r.wallclock_s), v: x => x.r.wallclock_s },
  ], rows, { rowClass: x => x.r.associativity === 15 ? "hl" : "" });
}

/* ---------- 10. flat vs mesh L3 ---------- */
function initFlat() {
  const dbs = ["50mb", "8gb"];
  const g = (db, t) => DATA.flat.find(r => r.db === db && r.topology === t);
  chart("cFlat", () => ({
    type: "bar",
    data: { labels: dbs.map(d => DBL[d] + " database"), datasets: [
      { label: "Per-core mesh slices (used everywhere else)", data: dbs.map(d => g(d, "nuca").cycles_M), backgroundColor: css("--w4"), borderRadius: 3, borderSkipped: false },
      { label: "One flat bank", data: dbs.map(d => g(d, "flat").cycles_M), backgroundColor: css("--w1"), borderRadius: 3, borderSkipped: false },
    ] },
    options: base({
      interaction: { mode: "index", intersect: false },
      plugins: { tooltip: { callbacks: { afterLabel: c => c.datasetIndex === 1 ? pct((c.parsed.y / g(dbs[c.dataIndex], "nuca").cycles_M - 1) * 100) + " vs mesh" : "" } } },
      scales: { x: ax("Database (stock kraken2, 50 reads)"), y: ax("Cycles (M)", { beginAtZero: true }) },
    }),
  }));
  table("tFlat", [
    { h: "Database", f: r => DBL[r.db] },
    { h: "L3 model", f: r => r.topology === "nuca" ? "Mesh slices" : "Flat bank", v: r => r.topology },
    { h: "Instr. (M)", n: 1, f: r => fmt(r.instructions_M), v: r => r.instructions_M },
    { h: "Cycles (M)", n: 1, f: r => fmt(r.cycles_M), v: r => r.cycles_M },
    { h: "IPC", n: 1, f: r => fmt(r.ipc, 2), v: r => r.ipc },
    { h: "L2 hit %", n: 1, f: r => fmt(r.l2_hit_pct, 2), v: r => r.l2_hit_pct },
    { h: "Cycles vs mesh", n: 1, f: r => r.topology === "nuca" ? "baseline" : pct((r.cycles_M / g(r.db, "nuca").cycles_M - 1) * 100), v: r => r.cycles_M / g(r.db, "nuca").cycles_M, cls: r => r.topology === "flat" ? "loss" : "" },
  ], DATA.flat);
}

/* ---------- 11. workloads ---------- */
const WL = [
  { f: "tiny_10reads", reads: 10, bases: 7862, avg: 786, size: "18 KB", use: "Width sweep, hardware associativity (10 reads), size sweep (50 MB, 103 GB), laptop 10" },
  { f: "50reads", reads: 50, bases: 91372, avg: 1827, size: "191 KB", use: "Fair batch, machine comparison, laptop 50, size sweep (8, 16 GB), hardware associativity (8, 16 GB)" },
  { f: "long_10", reads: 10, bases: 346387, avg: 34639, size: "680 KB", use: "Long-read scaling" },
  { f: "long_25", reads: 25, bases: 900057, avg: 36002, size: "1.8 MB", use: "Long-read scaling" },
  { f: "long_50", reads: 50, bases: 1868769, avg: 37375, size: "3.6 MB", use: "Long-read scaling" },
  { f: "reads_100", reads: 100, bases: 4725953, avg: 47260, size: "9.1 MB", use: "Laptop 100, hardware associativity (100 reads)" },
  { f: "reads_500", reads: 500, bases: 25389294, avg: 50779, size: "49 MB", use: "Laptop 500, hardware associativity (500 reads)" },
  { f: "reads_fast_2000", reads: 2000, bases: 35051480, avg: 17526, size: "68 MB", use: "2,000-read job" },
  { f: "reads_fast_10000", reads: 10000, bases: 60185436, avg: 6019, size: "118 MB", use: "Built for the 10,000-read job; that job was cancelled" },
];
function initWl() {
  const st = { m: "avg" };
  const M = { avg: ["Average read length (bases, log scale)", w => w.avg], bases: ["Total bases (log scale)", w => w.bases], reads: ["Reads (log scale)", w => w.reads] };
  seg("wlMode", [["avg", "Read length"], ["bases", "Total bases"], ["reads", "Reads"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cWl", () => ({
    type: "bar",
    data: { labels: WL.map(w => w.f), datasets: [{ label: M[st.m][0], data: WL.map(M[st.m][1]), backgroundColor: WL.map(w => w.avg > 30000 ? css("--w1") : css("--w4")), borderRadius: 3, borderSkipped: false }] },
    options: base({
      plugins: { legend: { display: false }, hline: st.m === "avg" ? { y: 3411, label: "whole file: 3,411" } : {}, tooltip: { callbacks: { label: c => fmt(c.parsed.y, 0) } } },
      scales: { x: ax("Workload file (orange = long-read heavy, over 30 kbp per read)"), y: ax(M[st.m][0], { type: "logarithmic" }) },
    }),
  }));
  table("tWl", [
    { h: "File", f: w => "<code>" + w.f + ".fastq</code>", v: w => w.f },
    { h: "Reads", n: 1, f: w => int(w.reads), v: w => w.reads },
    { h: "Total bases", n: 1, f: w => int(w.bases), v: w => w.bases },
    { h: "Avg length", n: 1, f: w => int(w.avg), v: w => w.avg },
    { h: "File size", n: 1, f: w => w.size },
    { h: "Used in", f: w => w.use, cls: () => "wrap" },
  ], WL);
}

/* ---------- headline tiles ---------- */
function initTiles() {
  const f = (db, v) => DATA.fair.find(r => r.db === db && r.variant === v).cycles_M;
  const sps = ["8gb", "16gb", "103gb"].map(db => f(db, "S0") / f(db, "4way"));
  $("#tWin").textContent = fmt(Math.min(...sps), 1) + " to " + fmt(Math.max(...sps), 1) + "×";
  const L = (rd, db, v) => DATA.laptop.find(r => r.reads === rd && r.db === db && r.variant === v).cycles_M;
  $("#tWin2").textContent = times(L(10, "8gb", "S0") / L(10, "8gb", "4way"));
  $("#tLoss").textContent = times(L(500, "8gb", "S0") / L(500, "8gb", "4way"));
  $("#tLoss2").textContent = times(f("50mb", "S0") / f("50mb", "4way"));
  const g = (db, t) => DATA.flat.find(r => r.db === db && r.topology === t).cycles_M;
  $("#tFlat").textContent = pct((g("50mb", "flat") / g("50mb", "nuca") - 1) * 100, 0) + " / " + pct((g("8gb", "flat") / g("8gb", "nuca") - 1) * 100, 0);
}
