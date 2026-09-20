"use strict";
/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmt = (v, d = 1) => v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const int = v => v == null ? "–" : Number(v).toLocaleString("en-US");
const times = v => fmt(v, 2) + "×";
const pct = (v, d = 1) => (v >= 0 ? "+" : "") + fmt(v, d) + "%";
const DBL = { "50mb": "50 MB", "8gb": "8 GB", "16gb": "16 GB", "103gb": "103 GB" };
const VAR = {
  S0: { label: "Stock (S0)", key: "--s0", pt: "rect" },
  "1way": { label: "1-way", key: "--w1", pt: "triangle" },
  "4way": { label: "4-way", key: "--w4", pt: "circle" },
  "8way": { label: "8-way", key: "--w8", pt: "rectRot" },
  "16way": { label: "16-way", key: "--w16", pt: "star" },
};
const VORDER = ["S0", "1way", "4way", "8way", "16way"];
const vcol = v => css(VAR[v].key);

/* ---------- chart plumbing ---------- */
const registry = [];
const HAS_CHART = typeof Chart !== "undefined" && typeof Chart.register === "function";
const hline = {
  id: "hline",
  afterDatasetsDraw(chart, args, o) {
    if (!o || o.y == null) return;
    const a = chart.chartArea, y = chart.scales.y;
    if (!y) return;
    const py = y.getPixelForValue(o.y);
    if (py < a.top || py > a.bottom) return;
    const c = chart.ctx;
    c.save();
    c.strokeStyle = o.color || css("--muted");
    c.setLineDash([5, 4]);
    c.lineWidth = 1.25;
    c.beginPath(); c.moveTo(a.left, py); c.lineTo(a.right, py); c.stroke();
    if (o.label) {
      c.setLineDash([]);
      c.fillStyle = css("--muted");
      c.font = '11px "IBM Plex Sans", sans-serif';
      c.textAlign = "right";
      c.fillText(o.label, a.right - 4, py - 5);
    }
    c.restore();
  },
};
if (HAS_CHART) Chart.register(hline);

function themeDefaults() {
  if (!HAS_CHART) return;
  Chart.defaults.color = css("--ink2");
  Chart.defaults.font.family = '"IBM Plex Sans", system-ui, sans-serif';
  Chart.defaults.font.size = 12;
}
function merge(a, b) {
  for (const k in b) {
    if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] && typeof a[k] === "object" && !Array.isArray(a[k])) merge(a[k], b[k]);
    else a[k] = b[k];
  }
  return a;
}
function base(extra = {}) {
  const o = {
    responsive: true, maintainAspectRatio: false, animation: { duration: 220 },
    interaction: { mode: "nearest", intersect: true },
    plugins: {
      legend: { labels: { color: css("--ink2"), usePointStyle: true, boxWidth: 8, boxHeight: 8 } },
      tooltip: {
        backgroundColor: css("--surface"), titleColor: css("--ink"), bodyColor: css("--ink2"),
        borderColor: css("--line2"), borderWidth: 1, padding: 10, boxPadding: 4,
      },
    },
    scales: {},
  };
  return merge(o, extra);
}
function ax(title, extra = {}) {
  return Object.assign({
    title: { display: !!title, text: title, color: css("--muted") },
    grid: { color: css("--grid") }, border: { color: css("--axis") },
    ticks: { color: css("--muted") },
  }, extra);
}
function chart(id, build) {
  if (!HAS_CHART) {
    const cv = document.getElementById(id);
    if (cv && cv.parentNode) cv.parentNode.innerHTML = '<p class="figcap">The chart library did not load. The table below holds the same data.</p>';
    return { draw() {} };
  }
  const e = { id, build, chart: null };
  e.draw = () => {
    if (e.chart) e.chart.destroy();
    const cv = document.getElementById(id);
    if (!cv) return;
    e.chart = new Chart(cv, build());
  };
  registry.push(e);
  e.draw();
  return e;
}
function redrawAll() { themeDefaults(); registry.forEach(e => e.draw()); }

/* ---------- controls ---------- */
function seg(id, items, get, set) {
  const el = document.getElementById(id);
  if (!el) return;
  const draw = () => {
    el.innerHTML = items.map(([k, l]) => `<button type="button" aria-pressed="${k === get()}" data-k="${k}">${l}</button>`).join("");
    $$("button", el).forEach(b => b.onclick = () => { set(b.dataset.k); draw(); });
  };
  draw();
}
function checks(id, items, sel, onChange) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = items.map(v => `<label class="chk" for="${id}_${v}"><input type="checkbox" id="${id}_${v}" ${sel.has(v) ? "checked" : ""}><i style="background:var(${VAR[v].key})"></i>${VAR[v].label}</label>`).join(" ");
  items.forEach(v => {
    document.getElementById(`${id}_${v}`).onchange = ev => {
      if (ev.target.checked) sel.add(v); else sel.delete(v);
      onChange();
    };
  });
}

/* ---------- tables ---------- */
function table(id, cols, rows, opt = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  const st = { k: opt.sortBy == null ? null : opt.sortBy, dir: opt.dir || 1 };
  const draw = () => {
    let rs = rows.slice();
    if (st.k != null) {
      const c = cols[st.k];
      rs.sort((a, b) => {
        const va = c.v ? c.v(a) : c.f(a), vb = c.v ? c.v(b) : c.f(b);
        return (va > vb ? 1 : va < vb ? -1 : 0) * st.dir;
      });
    }
    el.innerHTML = "<thead><tr>" + cols.map((c, i) => `<th class="${c.n ? "n " : ""}sortable" data-i="${i}">${c.h}${st.k === i ? (st.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("") + "</tr></thead><tbody>" +
      rs.map(r => `<tr class="${opt.rowClass ? opt.rowClass(r) : ""}">` + cols.map(c => `<td class="${[c.n ? "n" : "", c.cls ? c.cls(r) : ""].join(" ").trim()}">${c.f(r)}</td>`).join("") + "</tr>").join("") + "</tbody>";
    $$("th", el).forEach(th => th.onclick = () => {
      const i = +th.dataset.i;
      if (st.k === i) st.dir *= -1; else { st.k = i; st.dir = 1; }
      draw();
    });
  };
  draw();
}
const winCls = sp => (sp > 1.005 ? "win" : sp < 0.995 ? "loss" : "");
const spTxt = sp => times(sp) + (sp > 1.005 ? " ▲" : sp < 0.995 ? " ▼" : "");

/* ---------- theme, nav ---------- */
function effectiveDark() {
  const t = document.documentElement.getAttribute("data-theme");
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
function initTheme() {
  $("#themeBtn").onclick = () => {
    document.documentElement.setAttribute("data-theme", effectiveDark() ? "light" : "dark");
  };
  new MutationObserver(() => redrawAll()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => redrawAll());
}
function initNav() {
  const secs = $$("main section[data-nav]");
  const rail = $("#rail"), jump = $("#jump");
  let html = "", last = "";
  jump.innerHTML = '<option value="top">Jump to…</option>';
  secs.forEach(s => {
    const g = s.dataset.group;
    if (g !== last) { html += `<div class="grp">${g}</div>`; last = g; }
    html += `<a href="#${s.id}" data-id="${s.id}">${s.dataset.nav}</a>`;
    jump.insertAdjacentHTML("beforeend", `<option value="${s.id}">${s.dataset.nav}</option>`);
  });
  rail.innerHTML = html;
  jump.onchange = () => { const t = document.getElementById(jump.value); if (t) t.scrollIntoView({ behavior: "smooth" }); };
  const links = $$("a", rail);
  const io = new IntersectionObserver(es => {
    es.forEach(e => {
      if (e.isIntersecting) links.forEach(a => a.classList.toggle("on", a.dataset.id === e.target.id));
    });
  }, { rootMargin: "-20% 0px -70% 0px" });
  secs.forEach(s => io.observe(s));
}
