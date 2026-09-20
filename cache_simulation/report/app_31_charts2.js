/* ---------- 6. laptop sweep ---------- */
function initLaptop() {
  const st = { db: "8gb", m: "speedup" };
  const sel = new Set(["1way", "4way", "8way"]);
  const READS = [10, 50, 100, 500];
  const get = (rd, db, v) => DATA.laptop.find(r => r.reads === rd && r.db === db && r.variant === v);
  const sp = (rd, db, v) => get(rd, db, "S0").cycles_M / get(rd, db, v).cycles_M;
  seg("lapDb", [["8gb", "8 GB"], ["16gb", "16 GB"], ["both", "Both"]], () => st.db, v => { st.db = v; e.draw(); });
  seg("lapMetric", [["speedup", "Speedup"], ["cycles", "Cycles"], ["ipc", "IPC"]], () => st.m, v => { st.m = v; e.draw(); });
  checks("lapVars", VORDER.filter(v => v !== "16way"), sel, () => e.draw());
  const e = chart("cLap", () => {
    const dbs = st.db === "both" ? ["8gb", "16gb"] : [st.db];
    const ds = [];
    VORDER.filter(v => sel.has(v) && !(st.m === "speedup" && v === "S0")).forEach(v => dbs.forEach(db => {
      ds.push({
        label: VAR[v].label + (dbs.length > 1 ? " · " + DBL[db] : ""),
        data: READS.map(rd => st.m === "speedup" ? sp(rd, db, v) : st.m === "cycles" ? get(rd, db, v).cycles_M : get(rd, db, v).ipc),
        borderColor: vcol(v), backgroundColor: vcol(v), pointStyle: VAR[v].pt, pointRadius: 6, pointHoverRadius: 8,
        borderWidth: 2.4, tension: 0, borderDash: db === "16gb" && dbs.length > 1 ? [6, 4] : [],
      });
    }));
    const yl = { speedup: "Speedup vs stock (above 1 is faster)", cycles: "Cycles (M, log scale)", ipc: "IPC" }[st.m];
    return {
      type: "line",
      data: { labels: READS.map(String), datasets: ds },
      options: base({
        interaction: { mode: "index", intersect: false },
        plugins: {
          hline: st.m === "speedup" ? { y: 1, label: "stock = 1.0" } : {},
          tooltip: { callbacks: { label: c => c.dataset.label + ": " + (st.m === "speedup" ? times(c.parsed.y) + " (" + pct((1 / c.parsed.y - 1) * 100) + " cycles)" : fmt(c.parsed.y, st.m === "ipc" ? 2 : 1)) } },
        },
        scales: { x: ax("Reads in the workload (10 and 50 are short reads; 100 and 500 are long reads)"), y: st.m === "cycles" ? ax(yl, { type: "logarithmic" }) : ax(yl, { beginAtZero: st.m === "speedup" }) },
      }),
    };
  });
  const rows = [];
  ["8gb", "16gb"].forEach(db => READS.forEach(rd => rows.push({ rd, db })));
  const cell = v => ({ h: VAR[v].label, n: 1, f: r => spTxt(sp(r.rd, r.db, v)), v: r => sp(r.rd, r.db, v), cls: r => winCls(sp(r.rd, r.db, v)) });
  table("tLapMatrix", [
    { h: "Database", f: r => DBL[r.db] }, { h: "Reads", n: 1, f: r => r.rd, v: r => r.rd },
    { h: "Stock cycles (M)", n: 1, f: r => fmt(get(r.rd, r.db, "S0").cycles_M), v: r => get(r.rd, r.db, "S0").cycles_M },
    cell("1way"), cell("4way"), cell("8way"),
  ], rows);
  table("tLap", [
    { h: "Reads", n: 1, f: r => r.reads, v: r => r.reads }, { h: "Database", f: r => DBL[r.db] },
    { h: "Variant", f: r => VAR[r.variant].label, v: r => VORDER.indexOf(r.variant) },
    { h: "Instr. (M)", n: 1, f: r => fmt(r.instructions_M), v: r => r.instructions_M },
    { h: "Cycles (M)", n: 1, f: r => fmt(r.cycles_M), v: r => r.cycles_M },
    { h: "IPC", n: 1, f: r => fmt(r.ipc, 2), v: r => r.ipc },
    { h: "Cache lines", n: 1, f: r => int(r.unique_cache_lines), v: r => r.unique_cache_lines },
    { h: "L2 hit %", n: 1, f: r => fmt(r.l2_hit_pct, 2), v: r => r.l2_hit_pct },
    { h: "Sim wall (s)", n: 1, f: r => int(r.wallclock_s), v: r => r.wallclock_s },
    { h: "Speedup", n: 1, f: r => r.variant === "S0" ? "1.00×" : spTxt(sp(r.reads, r.db, r.variant)), v: r => sp(r.reads, r.db, r.variant), cls: r => r.variant === "S0" ? "" : winCls(sp(r.reads, r.db, r.variant)) },
  ], DATA.laptop, { rowClass: r => r.variant === "4way" ? "hl" : "" });
}

/* ---------- 7. long-read scaling ---------- */
function initLong() {
  const st = { m: "speedup" };
  const P = [];
  [10, 25, 50].forEach(n => {
    const a = DATA.longS0.find(r => r.reads === n), b = DATA.long4.find(r => r.reads === n);
    P.push({ reads: n, kind: "long-read run", bases: a.total_bases, s0c: a.cycles_M, w4c: b.cycles_M, s0i: a.instructions_M, w4i: b.instructions_M });
  });
  [100, 500].forEach(n => {
    const a = DATA.laptop.find(r => r.reads === n && r.db === "8gb" && r.variant === "S0"), b = DATA.laptop.find(r => r.reads === n && r.db === "8gb" && r.variant === "4way");
    P.push({ reads: n, kind: "laptop sweep", bases: BASES[n], s0c: a.cycles_M, w4c: b.cycles_M, s0i: a.instructions_M, w4i: b.instructions_M });
  });
  P.forEach(p => { p.sp = p.s0c / p.w4c; p.gap = p.s0i - p.w4i; });
  const lab = p => p.reads + " reads · " + fmt(p.bases / 1e6, 2) + " M bases";
  seg("lrMode", [["speedup", "Speedup vs total bases"], ["gap", "Instruction gap"], ["cycles", "Cycles"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cLong", () => {
    if (st.m === "speedup") {
      return {
        type: "scatter",
        data: { datasets: [{
          label: "4-way speedup vs stock", showLine: true, data: P.map(p => ({ x: p.bases, y: p.sp, p })),
          borderColor: css("--w4"), backgroundColor: css("--w4"), borderWidth: 2.4,
          pointStyle: P.map(p => p.kind === "laptop sweep" ? "rect" : "circle"), pointRadius: 7, pointHoverRadius: 9,
        }] },
        options: base({
          plugins: { legend: { display: false }, hline: { y: 1, label: "stock = 1.0" }, tooltip: { callbacks: { label: c => { const p = c.raw.p; return [lab(p) + " (" + p.kind + ")", times(p.sp) + " · " + pct((1 / p.sp - 1) * 100) + " cycles"]; } } } },
          scales: { x: ax("Total bases in the workload (log scale)", { type: "logarithmic", min: 2e5, max: 4e7, ticks: { color: css("--muted"), callback: v => [3e5, 1e6, 3e6, 1e7, 3e7].includes(v) ? fmt(v / 1e6, 1) + " M" : "" } }), y: ax("Speedup vs stock (above 1 is faster)", { beginAtZero: true }) },
        }),
      };
    }
    if (st.m === "gap") {
      return {
        type: "bar",
        data: { labels: P.map(lab), datasets: [{ label: "Stock minus 4-way instructions (M)", data: P.map(p => p.gap), backgroundColor: P.map(p => p.gap > 0 ? css("--win") : css("--loss")), borderRadius: 3, borderSkipped: false }] },
        options: base({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => (c.parsed.y >= 0 ? "4-way ran " + fmt(c.parsed.y) + " M FEWER instructions" : "4-way ran " + fmt(-c.parsed.y) + " M MORE instructions") } } }, scales: { x: ax("Workload"), y: ax("Stock minus 4-way instructions (M). Positive: 4-way ran fewer") } }),
      };
    }
    return {
      type: "bar",
      data: { labels: P.map(lab), datasets: [
        { label: "Stock", data: P.map(p => p.s0c), backgroundColor: css("--s0"), borderRadius: 3, borderSkipped: false },
        { label: "4-way", data: P.map(p => p.w4c), backgroundColor: css("--w4"), borderRadius: 3, borderSkipped: false },
      ] },
      options: base({ interaction: { mode: "index", intersect: false }, scales: { x: ax("Workload"), y: ax("Cycles (M, log scale)", { type: "logarithmic", min: 10 }) } }),
    };
  });
  table("tLong", [
    { h: "Reads", n: 1, f: r => r.reads, v: r => r.reads }, { h: "Source", f: r => r.kind },
    { h: "Total bases", n: 1, f: r => int(r.bases), v: r => r.bases },
    { h: "Stock cycles (M)", n: 1, f: r => fmt(r.s0c), v: r => r.s0c },
    { h: "4-way cycles (M)", n: 1, f: r => fmt(r.w4c), v: r => r.w4c },
    { h: "Speedup", n: 1, f: r => spTxt(r.sp), v: r => r.sp, cls: r => winCls(r.sp) },
    { h: "Stock instr. (M)", n: 1, f: r => fmt(r.s0i), v: r => r.s0i },
    { h: "4-way instr. (M)", n: 1, f: r => fmt(r.w4i), v: r => r.w4i },
    { h: "Instr. gap (M)", n: 1, f: r => (r.gap >= 0 ? "+" : "") + fmt(r.gap), v: r => r.gap, cls: r => r.gap > 0 ? "win" : "loss" },
  ], P);
}

/* ---------- 8. cache size sweep ---------- */
const SIZES = [2048, 4096, 16384, 65536, 262144, 1048576];
const TRUE_S0_50MB = 14.1; /* stock kraken2, 50 MB, 10 reads, same config: measured in the size research (command log), not in a CSV */
function initSize() {
  const st = { db: "all", m: "dev" };
  const order = ["50mb", "8gb", "16gb", "103gb"];
  const colr = { "50mb": "--w1", "8gb": "--w4", "16gb": "--w8", "103gb": "--w16" };
  const med = {};
  order.forEach(db => { const c = DATA.sizes.filter(r => r.db === db).map(r => r.cycles_M).sort((a, b) => a - b); med[db] = (c[2] + c[3]) / 2; });
  const dev = r => (r.cycles_M / med[r.db] - 1) * 100;
  seg("szDb", [["all", "All"], ["50mb", "50 MB"], ["8gb", "8 GB"], ["16gb", "16 GB"], ["103gb", "103 GB"]], () => st.db, v => { st.db = v; e.draw(); });
  seg("szMode", [["dev", "% vs database median"], ["cyc", "Cycles (M)"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cSize", () => {
    const dbs = st.db === "all" ? order : [st.db];
    return {
      type: "line",
      data: { datasets: dbs.map(db => ({
        label: DBL[db] + " (" + DATA.sizes.find(r => r.db === db).reads + " reads)",
        data: DATA.sizes.filter(r => r.db === db).map(r => ({ x: r.size, y: st.m === "dev" ? dev(r) : r.cycles_M })),
        borderColor: css(colr[db]), backgroundColor: css(colr[db]), pointRadius: 6, pointHoverRadius: 8, borderWidth: 2.4, tension: 0,
      })) },
      options: base({
        interaction: { mode: "nearest", intersect: true },
        plugins: {
          hline: st.m === "cyc" && st.db === "50mb" ? { y: TRUE_S0_50MB, label: "stock: 14.1 M cycles" } : (st.m === "dev" ? { y: 0, label: "median" } : {}),
          tooltip: { callbacks: { label: c => c.dataset.label + ": " + (st.m === "dev" ? pct(c.parsed.y, 2) : fmt(c.parsed.y) + " M cycles") + " at " + int(c.parsed.x) + " sets" } },
        },
        scales: {
          x: ax("Software cache size (sets, 4 ways each, log scale)", { type: "logarithmic", afterBuildTicks: sc => { sc.ticks = SIZES.map(v => ({ value: v })); }, ticks: { color: css("--muted"), callback: v => int(v) } }),
          y: ax(st.m === "dev" ? "Cycles vs the database's own median (%)" : "Cycles (M)"),
        },
      }),
    };
  });
  table("tSize", [
    { h: "Database", f: r => DBL[r.db], v: r => order.indexOf(r.db) },
    { h: "Reads", n: 1, f: r => r.reads, v: r => r.reads },
    { h: "Sets", n: 1, f: r => int(r.size), v: r => r.size },
    { h: "Cache (4 ways × 16 B)", n: 1, f: r => r.size * 64 >= 1048576 ? fmt(r.size * 64 / 1048576, 0) + " MiB" : fmt(r.size * 64 / 1024, 0) + " KiB", v: r => r.size },
    { h: "Cycles (M)", n: 1, f: r => fmt(r.cycles_M), v: r => r.cycles_M },
    { h: "vs median", n: 1, f: r => pct(dev(r), 2), v: r => dev(r), cls: r => Math.abs(dev(r)) > 0.9 ? "loss" : "" },
    { h: "Instr. (M)", n: 1, f: r => fmt(r.instructions_M), v: r => r.instructions_M },
    { h: "IPC", n: 1, f: r => fmt(r.ipc, 2), v: r => r.ipc },
    { h: "Cache lines", n: 1, f: r => int(r.unique_cache_lines), v: r => r.unique_cache_lines },
    { h: "L2 hit %", n: 1, f: r => fmt(r.l2_hit_pct, 2), v: r => r.l2_hit_pct },
  ], DATA.sizes, { rowClass: r => r.size === 65536 ? "hl" : "" });
}
