/* ---------- 1. width sweep, 10 reads ---------- */
function initAssoc10() {
  const st = { m: "cycles" };
  const M = { cycles: ["Cycles (M)", "cycles"], instr: ["Instructions (M)", "instructions"], lines: ["Unique cache lines", "unique_cache_lines"], ipc: ["IPC", "ipc"] };
  const rows = DATA.assoc10;
  const lab = r => r.variant === "baseline" ? "early S2 build" : r.variant.replace("lru-noatomics-", "").replace("way", "-way");
  seg("assocMetric", [["cycles", "Cycles"], ["instr", "Instructions"], ["lines", "Cache lines"], ["ipc", "IPC"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cAssoc10", () => {
    const [yl, k] = M[st.m];
    return {
      type: "line",
      data: { labels: rows.map(lab), datasets: [{ label: yl, data: rows.map(r => r[k]), borderColor: css("--w4"), backgroundColor: css("--w4"), pointRadius: 6, pointHoverRadius: 8, borderWidth: 2.5, tension: 0 }] },
      options: base({ plugins: { legend: { display: false } }, scales: { x: ax("Software cache width (baseline = an early S2 build)"), y: ax(yl) } }),
    };
  });
  const four = rows.find(r => r.variant.includes("4way"));
  table("tAssoc10", [
    { h: "Variant", f: lab },
    { h: "Instructions (M)", n: 1, f: r => fmt(r.instructions, 1), v: r => r.instructions },
    { h: "Cycles (M)", n: 1, f: r => fmt(r.cycles, 1), v: r => r.cycles },
    { h: "IPC", n: 1, f: r => fmt(r.ipc, 2), v: r => r.ipc },
    { h: "Cache lines", n: 1, f: r => int(r.unique_cache_lines), v: r => r.unique_cache_lines },
    { h: "Cycles vs 4-way", n: 1, f: r => pct((r.cycles / four.cycles - 1) * 100), v: r => r.cycles },
  ], rows, { rowClass: r => r === four ? "hl" : "" });
}

/* ---------- 2. fair batch across databases ---------- */
function initFair() {
  const st = { m: "speedup" };
  const sel = new Set(["1way", "4way", "8way", "16way"]);
  const dbs = ["50mb", "8gb", "16gb", "103gb"];
  const get = (db, v) => DATA.fair.find(r => r.db === db && r.variant === v);
  const M = {
    speedup: ["Speedup vs stock (above 1 is faster)", (r, s0) => s0.cycles_M / r.cycles_M, 2],
    cycles: ["Cycles (M)", r => r.cycles_M, 1],
    instr: ["Instructions (M)", r => r.instructions_M, 1],
    ipc: ["IPC", r => r.ipc, 2],
    lines: ["Unique cache lines", r => r.unique_cache_lines, 0],
    l2: ["L2 hit rate (% of loads)", r => r.l2_hit_pct, 2],
    wall: ["Sniper wall-clock (s), NOT program speed", r => r.sim_wallclock_s, 0],
  };
  seg("fairMetric", [["speedup", "Speedup"], ["cycles", "Cycles"], ["instr", "Instructions"], ["ipc", "IPC"], ["lines", "Cache lines"], ["l2", "L2 hit %"], ["wall", "Simulator wall-clock"]], () => st.m, v => { st.m = v; e.draw(); });
  checks("fairVars", VORDER, sel, () => e.draw());
  const e = chart("cFair", () => {
    const [yl, fn] = M[st.m];
    const vars = VORDER.filter(v => sel.has(v) && !(st.m === "speedup" && v === "S0"));
    return {
      type: "bar",
      data: {
        labels: dbs.map(d => DBL[d]),
        datasets: vars.map(v => ({
          label: VAR[v].label, backgroundColor: vcol(v), borderRadius: 3, borderSkipped: false,
          data: dbs.map(d => fn(get(d, v), get(d, "S0"))),
        })),
      },
      options: base({
        interaction: { mode: "index", intersect: false },
        plugins: { hline: st.m === "speedup" ? { y: 1, label: "stock = 1.0" } : {} },
        scales: { x: ax("Database"), y: ax(yl, { beginAtZero: true }) },
      }),
    };
  });
  table("tFair", [
    { h: "Database", f: r => DBL[r.db], v: r => dbs.indexOf(r.db) },
    { h: "Variant", f: r => VAR[r.variant].label, v: r => VORDER.indexOf(r.variant) },
    { h: "Instr. (M)", n: 1, f: r => fmt(r.instructions_M), v: r => r.instructions_M },
    { h: "Cycles (M)", n: 1, f: r => fmt(r.cycles_M), v: r => r.cycles_M },
    { h: "IPC", n: 1, f: r => fmt(r.ipc, 2), v: r => r.ipc },
    { h: "Cache lines", n: 1, f: r => int(r.unique_cache_lines), v: r => r.unique_cache_lines },
    { h: "L2 hit %", n: 1, f: r => fmt(r.l2_hit_pct, 2), v: r => r.l2_hit_pct },
    { h: "LLC hit %", n: 1, f: r => fmt(r.nuca_hit_pct, 3), v: r => r.nuca_hit_pct },
    { h: "Sim wall (s)", n: 1, f: r => int(r.sim_wallclock_s), v: r => r.sim_wallclock_s },
    { h: "Speedup", n: 1, f: r => r.variant === "S0" ? "1.00×" : spTxt(get(r.db, "S0").cycles_M / r.cycles_M), v: r => get(r.db, "S0").cycles_M / r.cycles_M, cls: r => r.variant === "S0" ? "" : winCls(get(r.db, "S0").cycles_M / r.cycles_M) },
  ], DATA.fair, { rowClass: r => r.variant === "4way" ? "hl" : "" });
}

/* ---------- 3. other machines ---------- */
function initProfiles() {
  const st = { m: "speedup" };
  const MACH = [["Luna", 2.1], ["Desktop", 3.7], ["Orin-sized", 2.2], ["Laptop", 3.2]];
  const cyc = {};
  const put = (m, db, v, c) => { (cyc[m] = cyc[m] || {}); (cyc[m][db] = cyc[m][db] || {})[v] = c; };
  DATA.fair.filter(r => (r.variant === "S0" || r.variant === "4way") && (r.db === "50mb" || r.db === "8gb")).forEach(r => put("Luna", r.db, r.variant, r.cycles_M));
  DATA.hwsize.forEach(r => put(r.hw === "desktop" ? "Desktop" : "Orin-sized", r.db, r.variant, r.cycles_M));
  DATA.laptop.filter(r => r.reads === 50 && r.db === "8gb" && (r.variant === "S0" || r.variant === "4way")).forEach(r => put("Laptop", "8gb", r.variant, r.cycles_M));
  const ghz = Object.fromEntries(MACH);
  const val = (m, db) => {
    const c = cyc[m] && cyc[m][db];
    if (!c || c.S0 == null || c["4way"] == null) return null;
    if (st.m === "speedup") return c.S0 / c["4way"];
    if (st.m === "stock") return c.S0;
    if (st.m === "four") return c["4way"];
    return c.S0 / ghz[m];
  };
  const YL = { speedup: "4-way speedup vs stock (above 1 is faster)", stock: "Stock cycles (M)", four: "4-way cycles (M)", ms: "Stock time = cycles ÷ clock (ms)" };
  seg("profMetric", [["speedup", "Speedup"], ["stock", "Stock cycles"], ["four", "4-way cycles"], ["ms", "Stock time (ms)"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cProf", () => ({
    type: "bar",
    data: {
      labels: MACH.map(m => m[0] + " (" + m[1] + " GHz)"),
      datasets: [["50mb", "50 MB database", "--w1"], ["8gb", "8 GB database", "--w4"]].map(([db, l, c]) => ({
        label: l, backgroundColor: css(c), borderRadius: 3, borderSkipped: false, data: MACH.map(m => val(m[0], db)),
      })),
    },
    options: base({
      interaction: { mode: "index", intersect: false },
      plugins: { hline: st.m === "speedup" ? { y: 1, label: "stock = 1.0" } : {} },
      scales: { x: ax("Simulated machine (clock speed)"), y: ax(YL[st.m], { beginAtZero: true }) },
    }),
  }));
  const rows = [];
  MACH.forEach(([m]) => ["50mb", "8gb"].forEach(db => { const c = cyc[m] && cyc[m][db]; if (c) rows.push({ m, db, s0: c.S0, w4: c["4way"], sp: c.S0 / c["4way"], ms: c.S0 / ghz[m] }); }));
  table("tProf", [
    { h: "Machine", f: r => r.m }, { h: "Database", f: r => DBL[r.db] },
    { h: "Stock cycles (M)", n: 1, f: r => fmt(r.s0), v: r => r.s0 },
    { h: "4-way cycles (M)", n: 1, f: r => fmt(r.w4), v: r => r.w4 },
    { h: "Speedup", n: 1, f: r => spTxt(r.sp), v: r => r.sp, cls: r => winCls(r.sp) },
    { h: "Stock time (ms)", n: 1, f: r => fmt(r.ms), v: r => r.ms },
  ], rows);
}

/* ---------- 4. 2,000 reads ---------- */
function initR2000() {
  const st = { m: "speedup" };
  const V = ["1way", "4way", "8way", "16way"];
  const f50 = v => DATA.fair.find(r => r.db === "50mb" && r.variant === v);
  const f2k = v => DATA.r2000.find(r => r.variant === v);
  seg("r2000Mode", [["speedup", "Speedup: 50 vs 2,000 reads"], ["cycles", "Cycles at 2,000 reads"]], () => st.m, v => { st.m = v; e.draw(); });
  const e = chart("cR2000", () => {
    if (st.m === "speedup") {
      return {
        type: "bar",
        data: { labels: V.map(v => VAR[v].label), datasets: [
          { label: "50 reads (fair batch)", backgroundColor: css("--s0"), borderRadius: 3, borderSkipped: false, data: V.map(v => f50("S0").cycles_M / f50(v).cycles_M) },
          { label: "2,000 reads", backgroundColor: css("--accent"), borderRadius: 3, borderSkipped: false, data: V.map(v => f2k("S0").cycles_M / f2k(v).cycles_M) },
        ] },
        options: base({ interaction: { mode: "index", intersect: false }, plugins: { hline: { y: 1, label: "stock = 1.0" } }, scales: { x: ax("S2 cache width"), y: ax("Speedup vs stock (below 1 is slower)", { beginAtZero: true }) } }),
      };
    }
    return {
      type: "bar",
      data: { labels: VORDER.map(v => VAR[v].label), datasets: [{ label: "Cycles (M)", backgroundColor: VORDER.map(v => vcol(v)), borderRadius: 3, borderSkipped: false, data: VORDER.map(v => v === "S0" ? f2k("S0").cycles_M : f2k(v).cycles_M) }] },
      options: base({ plugins: { legend: { display: false }, hline: { y: f2k("S0").cycles_M, label: "stock" } }, scales: { x: ax("Variant"), y: ax("Cycles (M)", { beginAtZero: true }) } }),
    };
  });
  const s0 = f2k("S0");
  table("tR2000", [
    { h: "Variant", f: r => VAR[r.variant].label, v: r => VORDER.indexOf(r.variant) },
    { h: "Instr. (M)", n: 1, f: r => fmt(r.instructions_M), v: r => r.instructions_M },
    { h: "Cycles (M)", n: 1, f: r => fmt(r.cycles_M), v: r => r.cycles_M },
    { h: "IPC", n: 1, f: r => fmt(r.ipc, 2), v: r => r.ipc },
    { h: "Cache lines", n: 1, f: r => int(r.unique_cache_lines), v: r => r.unique_cache_lines },
    { h: "L2 hit %", n: 1, f: r => fmt(r.l2_hit_pct, 2), v: r => r.l2_hit_pct },
    { h: "Sim wall (h)", n: 1, f: r => fmt(r.wallclock_s / 3600, 2), v: r => r.wallclock_s },
    { h: "Speedup vs stock", n: 1, f: r => r.variant === "S0" ? "1.00×" : spTxt(s0.cycles_M / r.cycles_M), v: r => s0.cycles_M / r.cycles_M, cls: r => r.variant === "S0" ? "" : winCls(s0.cycles_M / r.cycles_M) },
  ], DATA.r2000, { rowClass: r => r.variant === "4way" ? "hl" : "" });
}

/* ---------- 5. simulation time model ---------- */
const BASES = { 10: 7862, 50: 91372, 100: 4725953, 500: 25389294, 2000: 35051480 };
function humanTime(s) {
  if (s < 120) return fmt(s, 0) + " s";
  if (s < 7200) return fmt(s / 60, 0) + " min";
  if (s < 172800) return fmt(s / 3600, 1) + " hours";
  return fmt(s / 86400, 1) + " days";
}
function initTime() {
  const s50 = DATA.fair.find(r => r.db === "50mb" && r.variant === "S0").sim_wallclock_s;
  const s2k = DATA.r2000.find(r => r.variant === "S0").wallclock_s;
  const slope = (s2k - s50) / (BASES[2000] - BASES[50]);
  const fixed = s50 - slope * BASES[50];
  const est = b => fixed + slope * b;
  const pts = [];
  DATA.hwassoc50.filter(r => r.associativity === 15).forEach(r => pts.push({ x: BASES[r.reads], y: r.wallclock_s, l: r.reads + " reads" }));
  pts.push({ x: BASES[2000], y: s2k, l: "2,000 reads" });
  const slider = $("#tmBases"), out = $("#tmOut");
  const e = chart("cTime", () => {
    const line = [];
    for (let i = 0; i <= 40; i++) { const x = Math.pow(10, 3.6 + (i / 40) * 5.1); line.push({ x, y: est(x) }); }
    const b = +slider.value * 1e6;
    return {
      type: "scatter",
      data: { datasets: [
        { label: "Measured (Luna, stock, 50 MB)", data: pts, backgroundColor: css("--w4"), pointRadius: 6, pointHoverRadius: 8 },
        { label: "Fit: " + fmt(fixed, 0) + " s + " + fmt(slope * 1000, 2) + " ms per base", type: "line", data: line, borderColor: css("--muted"), borderDash: [6, 4], pointRadius: 0, borderWidth: 1.5 },
        { label: "Your estimate", data: [{ x: b, y: est(b), l: "estimate" }], backgroundColor: css("--w1"), pointRadius: 8, pointStyle: "rectRot" },
      ] },
      options: base({
        plugins: { tooltip: { callbacks: { label: c => (c.raw.l ? c.raw.l + ": " : "") + humanTime(c.raw.y) + " at " + fmt(c.raw.x / 1e6, 2) + " M bases" } } },
        scales: { x: ax("Total bases in the workload", { type: "logarithmic", ticks: { color: css("--muted"), callback: v => [1e4, 1e5, 1e6, 1e7, 1e8].includes(v) ? fmt(v / 1e6, v < 1e6 ? 2 : 0) + " M" : "" } }), y: ax("Sniper wall-clock (s)", { type: "logarithmic", ticks: { color: css("--muted"), callback: v => [10, 100, 1e3, 1e4, 1e5, 1e6].includes(v) ? int(v) : "" } }) },
      }),
    };
  });
  const upd = () => {
    const b = +slider.value * 1e6;
    out.textContent = fmt(+slider.value, 2) + " M bases: about " + humanTime(est(b));
    e.draw();
  };
  slider.oninput = upd;
  upd();
}
