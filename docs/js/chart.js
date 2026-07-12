// chart.js — grafik tren rasio (SVG inline, tanpa dependensi, tema-aware).
// Tiga seri persentase satu-sumbu: ROE, ROA, Net Margin.
// Warna dari palet tervalidasi (dataviz): blue / aqua / yellow.
// Identitas lewat legend (swatch), angka & label memakai tinta teks — bukan warna seri.

const SERIES = [
  { key: "roe", nama: "ROE", varc: "--series-1" },
  { key: "roa", nama: "ROA", varc: "--series-2" },
  { key: "net_profit_margin", nama: "Net Margin", varc: "--series-3" },
];

const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};
const pctLabel = (x) => (x * 100).toFixed(1) + "%";

/** Bangun grafik tren dari rasio_historis. Kembalikan <figure> atau null. */
export function renderTrendChart(rasioHistoris) {
  const data = [...rasioHistoris].sort((a, b) => a.tahun - b.tahun);
  if (data.length < 2) return null; // tren butuh >= 2 titik

  const W = 540, H = 260;
  const m = { t: 18, r: 54, b: 30, l: 46 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;

  // Domain nilai (semua seri terdefinisi).
  const semua = [];
  for (const s of SERIES) for (const d of data) if (d[s.key] != null) semua.push(d[s.key]);
  if (!semua.length) return null;
  let ymin = Math.min(0, ...semua);
  let ymax = Math.max(...semua);
  const pad = (ymax - ymin) * 0.12 || 0.01;
  ymax += pad;
  if (ymin < 0) ymin -= pad;

  const years = data.map((d) => d.tahun);
  const x = (i) => m.l + (data.length === 1 ? iw / 2 : (i / (data.length - 1)) * iw);
  const y = (v) => m.t + ih - ((v - ymin) / (ymax - ymin)) * ih;

  const svg = el("svg", {
    viewBox: `0 0 ${W} ${H}`, width: "100%", role: "img",
    "aria-label": "Grafik tren ROE, ROA, dan Net Margin per tahun",
  });

  // Gridlines horizontal + label sumbu-y (5 tick).
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const v = ymin + ((ymax - ymin) * i) / ticks;
    const gy = y(v);
    svg.appendChild(el("line", {
      x1: m.l, y1: gy, x2: m.l + iw, y2: gy,
      stroke: "var(--viz-grid)", "stroke-width": 1,
    }));
    const t = el("text", {
      x: m.l - 8, y: gy + 3, "text-anchor": "end",
      fill: "var(--viz-muted)", "font-size": 10, "font-variant-numeric": "tabular-nums",
    });
    t.textContent = (v * 100).toFixed(0) + "%";
    svg.appendChild(t);
  }

  // Baseline nol bila domain melewati nol.
  if (ymin < 0 && ymax > 0) {
    svg.appendChild(el("line", {
      x1: m.l, y1: y(0), x2: m.l + iw, y2: y(0),
      stroke: "var(--viz-axis)", "stroke-width": 1.5,
    }));
  }

  // Label sumbu-x (tahun).
  data.forEach((d, i) => {
    const t = el("text", {
      x: x(i), y: H - 10, "text-anchor": "middle",
      fill: "var(--viz-muted)", "font-size": 10, "font-variant-numeric": "tabular-nums",
    });
    t.textContent = d.tahun;
    svg.appendChild(t);
  });

  // Garis + marker tiap seri. Kumpulkan label ujung untuk anti-tabrakan.
  const endLabels = [];
  for (const s of SERIES) {
    const titik = data.map((d, i) => ({ i, v: d[s.key] })).filter((p) => p.v != null);
    if (titik.length < 2) continue;
    const dpath = titik.map((p, k) => `${k ? "L" : "M"}${x(p.i)},${y(p.v)}`).join(" ");
    svg.appendChild(el("path", {
      d: dpath, fill: "none", stroke: `var(${s.varc})`,
      "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
    }));
    for (const p of titik) {
      svg.appendChild(el("circle", {
        cx: x(p.i), cy: y(p.v), r: 4,
        fill: `var(${s.varc})`, stroke: "var(--viz-surface)", "stroke-width": 2,
      }));
    }
    const last = titik.at(-1);
    endLabels.push({ x: x(last.i) + 8, y: y(last.v), text: pctLabel(last.v) });
  }
  // Anti-tabrakan label ujung: geser vertikal bila terlalu rapat (min 12px).
  endLabels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < endLabels.length; i++) {
    if (endLabels[i].y - endLabels[i - 1].y < 12) endLabels[i].y = endLabels[i - 1].y + 12;
  }
  for (const lab of endLabels) {
    const tl = el("text", {
      x: lab.x, y: lab.y + 3, "text-anchor": "start",
      fill: "var(--viz-ink)", "font-size": 10, "font-variant-numeric": "tabular-nums",
    });
    tl.textContent = lab.text;
    svg.appendChild(tl);
  }

  // ---- Crosshair + tooltip (hover) ----
  const fig = document.createElement("figure");
  fig.className = "chart-fig viz-root";
  const cap = document.createElement("figcaption");
  cap.className = "chart-legend";
  cap.innerHTML = SERIES.map(
    (s) => `<span><i class="sw" style="background:var(${s.varc})"></i>${s.nama}</span>`
  ).join("");
  fig.appendChild(cap);
  fig.appendChild(svg);

  const tip = document.createElement("div");
  tip.className = "chart-tip";
  tip.hidden = true;
  fig.appendChild(tip);

  const crosshair = el("line", {
    y1: m.t, y2: m.t + ih, stroke: "var(--viz-axis)", "stroke-width": 1, "stroke-dasharray": "3 3",
  });
  crosshair.style.display = "none";
  svg.appendChild(crosshair);

  const overlay = el("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" });
  svg.appendChild(overlay);

  function hover(ev) {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    let i = Math.round(((px - m.l) / iw) * (data.length - 1));
    i = Math.max(0, Math.min(data.length - 1, i));
    crosshair.setAttribute("x1", x(i));
    crosshair.setAttribute("x2", x(i));
    crosshair.style.display = "block";
    const d = data[i];
    tip.innerHTML =
      `<b>${d.tahun}</b>` +
      SERIES.map((s) => d[s.key] != null
        ? `<span><i class="sw" style="background:var(${s.varc})"></i>${s.nama}: ${pctLabel(d[s.key])}</span>`
        : "").join("");
    tip.hidden = false;
    const leftPct = (x(i) / W) * 100;
    tip.style.left = leftPct + "%";
    tip.style.transform = leftPct > 60 ? "translate(-105%, 0)" : "translate(8px, 0)";
  }
  overlay.addEventListener("mousemove", hover);
  overlay.addEventListener("mouseleave", () => {
    tip.hidden = true;
    crosshair.style.display = "none";
  });

  return fig;
}
