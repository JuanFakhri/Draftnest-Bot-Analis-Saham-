// app.js — logika UI Draftnest.
import { analisisKuantitatif, analisisValuasi, proyeksiTahunDepan } from "./finance.js";
import {
  DEFAULT_MODEL, analisisKualitatif, analisisKuantitatifLLM, analisisValuasiLLM,
} from "./claude.js";
import { renderTrendChart } from "./chart.js";
import { ambilHargaIDX } from "./idx-price.js";
import { muatPraAmbil, fetchFMP } from "./data-fetch.js";

const $ = (id) => document.getElementById(id);
const BOBOT = { kualitatif: 0.35, kuantitatif: 0.35, valuasi: 0.30 };

// Field numerik per tahun laporan, dikelompokkan seperti 3 laporan keuangan.
const FIELD_LAPORAN = {
  "Neraca": [
    ["total_aset", "Total Aset"], ["aset_lancar", "Aset Lancar"],
    ["total_liabilitas", "Total Liabilitas"], ["liabilitas_lancar", "Liabilitas Lancar"],
    ["total_ekuitas", "Total Ekuitas"],
  ],
  "Laba Rugi": [
    ["pendapatan", "Pendapatan"], ["laba_kotor", "Laba Kotor"],
    ["laba_operasi", "Laba Operasi"], ["laba_bersih", "Laba Bersih"],
  ],
  "Arus Kas": [
    ["arus_kas_operasi", "Arus Kas Operasi"], ["arus_kas_investasi", "Arus Kas Investasi"],
    ["arus_kas_pendanaan", "Arus Kas Pendanaan"],
  ],
};

// ---------- Format ----------
const pct = (x) => (x != null ? (x * 100).toFixed(1) + "%" : "n/a");
const numx = (x) => (x != null ? x.toFixed(2) + "x" : "n/a");
const rp = (x) => (x != null ? "Rp" + Math.round(x).toLocaleString("id-ID") : "n/a");
const skorTxt = (x) => (x != null ? x.toFixed(1) + "/10" : "n/a");
const skorKelas = (s) => (s >= 7 ? "g" : s >= 5 ? "m" : "b");

// ---------- Tema ----------
function initTema() {
  const simpan = localStorage.getItem("draftnest-theme") || "dark";
  document.documentElement.setAttribute("data-theme", simpan);
  $("btn-theme").textContent = simpan === "dark" ? "🌙" : "☀️";
}
$("btn-theme").addEventListener("click", () => {
  const kini = document.documentElement.getAttribute("data-theme");
  const baru = kini === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", baru);
  localStorage.setItem("draftnest-theme", baru);
  $("btn-theme").textContent = baru === "dark" ? "🌙" : "☀️";
});

// ---------- Pengaturan API ----------
function initSettings() {
  $("api-key").value = localStorage.getItem("draftnest-key") || "";
  $("model").value = localStorage.getItem("draftnest-model") || DEFAULT_MODEL;
  $("fmp-key").value = localStorage.getItem("draftnest-fmp") || "";
}
$("btn-settings").addEventListener("click", () => $("settings").showModal());
$("settings").addEventListener("close", () => {
  if ($("settings").returnValue === "save") {
    localStorage.setItem("draftnest-key", $("api-key").value.trim());
    localStorage.setItem("draftnest-model", $("model").value.trim() || DEFAULT_MODEL);
    localStorage.setItem("draftnest-fmp", $("fmp-key").value.trim());
    setStatus("Pengaturan tersimpan.", "ok");
  }
});

// ---------- Kartu tahun ----------
function tambahKartuTahun(data = {}) {
  const wrap = document.createElement("div");
  wrap.className = "year-card";
  let html = `<div class="year-head">
      <input type="number" class="y-tahun" placeholder="Tahun" value="${data.tahun ?? ""}" />
      <button type="button" class="del">Hapus</button>
    </div>`;
  for (const [grup, fields] of Object.entries(FIELD_LAPORAN)) {
    html += `<div class="sub">${grup}</div><div class="grid grid-3">`;
    for (const [key, label] of fields) {
      html += `<label>${label}<input type="number" step="any" data-key="${key}" value="${data[key] ?? ""}" /></label>`;
    }
    html += `</div>`;
  }
  wrap.innerHTML = html;
  wrap.querySelector(".del").addEventListener("click", () => wrap.remove());
  $("years").appendChild(wrap);
}
$("btn-add-year").addEventListener("click", () => tambahKartuTahun());

// ---------- Kumpulkan / Isi form ----------
function bacaEmiten() {
  const laporan = [];
  for (const card of document.querySelectorAll(".year-card")) {
    const tahun = parseInt(card.querySelector(".y-tahun").value, 10);
    if (!tahun) continue;
    const l = { tahun };
    for (const inp of card.querySelectorAll("input[data-key]")) {
      l[inp.dataset.key] = parseFloat(inp.value) || 0;
    }
    laporan.push(l);
  }
  const harga = parseFloat($("m-harga").value);
  const saham = parseFloat($("m-saham").value);
  const pasar = (harga && saham) ? {
    harga_saham: harga, saham_beredar: saham,
    per_sektor: parseFloat($("m-per").value) || null,
    pbv_sektor: parseFloat($("m-pbv").value) || null,
    growth_rate: parseFloat($("m-growth").value) || 0.08,
    discount_rate: parseFloat($("m-discount").value) || 0.11,
    terminal_growth: parseFloat($("m-terminal").value) || 0.03,
    tahun_proyeksi: parseInt($("m-tahun").value, 10) || 5,
  } : null;

  return {
    profil: {
      kode: $("p-kode").value.trim() || "N/A",
      nama: $("p-nama").value.trim(),
      sektor: $("p-sektor").value.trim(),
      sub_sektor: $("p-subsektor").value.trim(),
      deskripsi_bisnis: $("p-bisnis").value.trim(),
      manajemen: $("p-manajemen").value.trim(),
      keunggulan_kompetitif: $("p-moat").value.trim(),
      prospek_industri: $("p-prospek").value.trim(),
      berita_terkini: $("p-berita").value.trim(),
    },
    laporan, pasar,
  };
}

function isiForm(e) {
  const p = e.profil || {};
  $("p-kode").value = p.kode || "";
  $("p-nama").value = p.nama || "";
  $("p-sektor").value = p.sektor || "";
  $("p-subsektor").value = p.sub_sektor || "";
  $("p-bisnis").value = p.deskripsi_bisnis || "";
  $("p-manajemen").value = p.manajemen || "";
  $("p-moat").value = p.keunggulan_kompetitif || "";
  $("p-prospek").value = p.prospek_industri || "";
  $("p-berita").value = p.berita_terkini || "";

  $("years").innerHTML = "";
  (e.laporan || []).forEach((l) => tambahKartuTahun(l));
  if (!e.laporan?.length) tambahKartuTahun();

  const m = e.pasar || {};
  $("m-harga").value = m.harga_saham ?? "";
  $("m-saham").value = m.saham_beredar ?? "";
  $("m-per").value = m.per_sektor ?? "";
  $("m-pbv").value = m.pbv_sektor ?? "";
  $("m-growth").value = m.growth_rate ?? 0.08;
  $("m-discount").value = m.discount_rate ?? 0.11;
  $("m-terminal").value = m.terminal_growth ?? 0.03;
  $("m-tahun").value = m.tahun_proyeksi ?? 5;
}

// ---------- Toolbar data ----------
$("btn-sample").addEventListener("click", async () => {
  try {
    const e = await (await fetch("data/icbp.json")).json();
    isiForm(e);
    setStatus("Contoh ICBP dimuat (data ilustratif).", "ok");
  } catch (_) { setStatus("Gagal memuat contoh.", "err"); }
});
$("btn-export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(bacaEmiten(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${bacaEmiten().profil.kode || "emiten"}.json`;
  a.click();
});
$("btn-import").addEventListener("click", () => $("file-import").click());
$("file-import").addEventListener("change", async (ev) => {
  const file = ev.target.files[0];
  if (!file) return;
  try {
    isiForm(JSON.parse(await file.text()));
    setStatus("JSON diimpor.", "ok");
  } catch (_) { setStatus("File JSON tidak valid.", "err"); }
});

// ---------- Ambil Data Otomatis (pra-ambil -> fallback FMP) ----------
$("btn-autofetch").addEventListener("click", async () => {
  const kode = ($("fetch-kode").value || $("p-kode").value).trim().toUpperCase();
  const note = $("fetch-note");
  const btn = $("btn-autofetch");
  if (!kode) { note.textContent = "Ketik kode emiten dulu."; return; }
  btn.disabled = true; note.textContent = `Mengambil data ${kode}…`;
  try {
    let data = await muatPraAmbil(kode);
    let sumber = "data pra-ambil (pipeline)";
    if (!data || !(data.laporan && data.laporan.length)) {
      // Fallback live via FMP (butuh key).
      const fmpKey = localStorage.getItem("draftnest-fmp");
      note.textContent = `Tidak ada di data pra-ambil. Mencoba FMP live…`;
      data = await fetchFMP(kode, fmpKey);
      sumber = "FMP (live)";
    }
    isiForm(data);
    const nTahun = (data.laporan || []).length;
    note.textContent = `✓ ${data.profil?.nama || kode} — ${nTahun} tahun laporan (${sumber}). ` +
      (data.pasar ? "" : "Lengkapi harga & saham beredar. ") +
      "Lengkapi PER/PBV sektor untuk harga wajar relatif.";
    // Auto-analisa.
    if (nTahun >= 1) {
      const autoAI = $("auto-ai").checked && localStorage.getItem("draftnest-key");
      await jalankan(Boolean(autoAI));
    }
  } catch (e) {
    note.textContent = "⚠️ " + e.message + " Anda tetap bisa isi manual atau Muat Contoh.";
  } finally {
    btn.disabled = false;
  }
});

// ---------- Ambil harga IDX (real-time via proxy) ----------
$("btn-fetch-price").addEventListener("click", async () => {
  const kode = $("p-kode").value.trim();
  const note = $("price-note");
  const btn = $("btn-fetch-price");
  if (!kode) { note.textContent = "Isi kode emiten dulu."; return; }
  btn.disabled = true; note.textContent = "Mengambil harga…";
  try {
    const { harga, mata_uang, sumber } = await ambilHargaIDX(kode);
    $("m-harga").value = harga;
    note.textContent = `✓ ${mata_uang} ${harga.toLocaleString("id-ID")} — ${sumber}. Lengkapi jumlah saham beredar.`;
  } catch (e) {
    note.textContent = e.message;
  } finally {
    btn.disabled = false;
  }
});

// ---------- Status ----------
function setStatus(msg, kelas = "") {
  const el = $("status");
  el.textContent = msg;
  el.className = "status " + kelas;
}

// ---------- Agregasi ----------
function rataSkor(hasil, fields) {
  if (!hasil) return null;
  const s = fields.filter((f) => hasil[f]?.skor != null).map((f) => hasil[f].skor);
  return s.length ? s.reduce((a, b) => a + b, 0) / s.length : null;
}
function rekomendasi(skor, status) {
  if (skor == null) return { teks: "TAHAN", kelas: "tahan" };
  let teks = skor >= 7.5 ? "BELI" : skor >= 5.5 ? "TAHAN" : "JUAL";
  let kelas = teks.toLowerCase();
  if (teks === "BELI" && status === "overvalued") { teks = "TAHAN"; kelas = "tahan"; }
  return { teks, kelas };
}

// ---------- Analisis ----------
async function jalankan(pakaiAI) {
  const emiten = bacaEmiten();
  if (!emiten.laporan.length) { setStatus("Isi minimal 1 tahun laporan keuangan.", "err"); return; }

  const kuant = analisisKuantitatif(emiten);
  const valu = analisisValuasi(emiten);
  const proyeksi = proyeksiTahunDepan(emiten);

  let kualLLM = null, kuantLLM = null, valuLLM = null;
  if (pakaiAI) {
    const key = localStorage.getItem("draftnest-key");
    const model = localStorage.getItem("draftnest-model") || DEFAULT_MODEL;
    if (!key) { setStatus("Set API key dulu lewat ⚙️ Pengaturan.", "err"); $("settings").showModal(); return; }

    disableBtns(true);
    try {
      setStatus("Menganalisis pilar Kualitatif…");
      kualLLM = await analisisKualitatif(key, model, emiten);
      setStatus("Menganalisis pilar Kuantitatif…");
      kuantLLM = await analisisKuantitatifLLM(key, model, emiten.profil.kode, kuant);
      if (valu) {
        setStatus("Menganalisis pilar Valuasi & outlook…");
        valuLLM = await analisisValuasiLLM(key, model, emiten.profil.kode, valu, proyeksi);
      }
      setStatus("Selesai.", "ok");
    } catch (err) {
      setStatus(err.message, "err");
      disableBtns(false);
      return;
    }
    disableBtns(false);
  } else {
    setStatus("Rasio & valuasi dihitung (offline).", "ok");
  }

  render(emiten, kuant, valu, proyeksi, kualLLM, kuantLLM, valuLLM);
}
$("btn-offline").addEventListener("click", () => jalankan(false));
$("btn-ai").addEventListener("click", () => jalankan(true));

function disableBtns(v) {
  $("btn-ai").disabled = v; $("btn-offline").disabled = v;
  $("btn-ai").textContent = v ? "⏳ Menganalisis…" : "✨ Analisis Lengkap dengan AI";
}

// ---------- Render ----------
let laporanMd = "";
function render(emiten, kuant, valu, proyeksi, kualLLM, kuantLLM, valuLLM) {
  const skorPilar = {
    kualitatif: rataSkor(kualLLM, ["model_bisnis", "manajemen", "keunggulan_kompetitif", "prospek_industri"]),
    kuantitatif: rataSkor(kuantLLM, ["profitabilitas", "solvabilitas", "likuiditas", "pertumbuhan"]),
    valuasi: rataSkor(valuLLM, ["relative_valuation", "absolute_valuation"]),
  };
  const tersedia = Object.entries(skorPilar).filter(([, v]) => v != null);
  let skorAkhir = null;
  if (tersedia.length) {
    const tb = tersedia.reduce((a, [k]) => a + BOBOT[k], 0);
    skorAkhir = tersedia.reduce((a, [k, v]) => a + BOBOT[k] * v, 0) / tb;
  }
  const rec = rekomendasi(skorAkhir, valuLLM?.status);

  // Verdict
  $("result-title").textContent = `Hasil Analisis — ${emiten.profil.nama || emiten.profil.kode} (${emiten.profil.kode})`;
  const badge = $("rec-badge");
  badge.textContent = rec.teks; badge.className = "rec-badge " + rec.kelas;
  $("score-final").textContent = skorAkhir != null ? skorAkhir.toFixed(1) : "–";
  const setBar = (barId, numId, v) => {
    $(barId).style.width = v != null ? (v * 10) + "%" : "0";
    $(numId).textContent = v != null ? v.toFixed(1) : "–";
  };
  setBar("bar-kual", "num-kual", skorPilar.kualitatif);
  setBar("bar-kuant", "num-kuant", skorPilar.kuantitatif);
  setBar("bar-val", "num-val", skorPilar.valuasi);

  // Detail
  const D = $("detail");
  D.innerHTML = "";
  D.appendChild(pilarKualitatif(kualLLM));
  D.appendChild(pilarKuantitatif(kuant, kuantLLM));
  if (valu) D.appendChild(pilarValuasi(valu, valuLLM));
  const proj = pilarProyeksi(proyeksi, valuLLM);
  if (proj) D.appendChild(proj);

  laporanMd = buatMarkdown(emiten, kuant, valu, proyeksi, kualLLM, kuantLLM, valuLLM, skorPilar, skorAkhir, rec);
  $("results").hidden = false;
  $("results").scrollIntoView({ behavior: "smooth" });
}

function poinEl(hasil, key, judul) {
  const div = document.createElement("div");
  div.className = "point";
  if (!hasil || !hasil[key]) {
    div.innerHTML = `<span class="chip">–</span><div class="txt"><strong>${judul}</strong><span>Analisis AI belum dijalankan.</span></div>`;
    return div;
  }
  const p = hasil[key];
  div.innerHTML = `<span class="chip ${skorKelas(p.skor)}">${p.skor}</span>
    <div class="txt"><strong>${judul}</strong><span>${p.justifikasi}</span></div>`;
  return div;
}

function pilarKualitatif(llm) {
  const s = document.createElement("div");
  s.className = "pillar";
  s.innerHTML = "<h3>1. Analisis Kualitatif</h3>";
  s.appendChild(poinEl(llm, "model_bisnis", "Model Bisnis"));
  s.appendChild(poinEl(llm, "manajemen", "Manajemen"));
  s.appendChild(poinEl(llm, "keunggulan_kompetitif", "Keunggulan Kompetitif"));
  s.appendChild(poinEl(llm, "prospek_industri", "Prospek Industri"));
  if (llm?.ringkasan) s.insertAdjacentHTML("beforeend", `<div class="summary">${llm.ringkasan}</div>`);
  return s;
}

function pilarKuantitatif(kuant, llm) {
  const s = document.createElement("div");
  s.className = "pillar";
  let rows = kuant.rasio_historis.map((r) =>
    `<tr><td>${r.tahun}</td><td>${pct(r.roe)}</td><td>${pct(r.roa)}</td><td>${numx(r.der)}</td>
     <td>${numx(r.current_ratio)}</td><td>${pct(r.net_profit_margin)}</td></tr>`).join("");
  s.innerHTML = `<h3>2. Analisis Kuantitatif</h3>
    <table class="ratios"><thead><tr><th>Tahun</th><th>ROE</th><th>ROA</th><th>DER</th><th>Current Ratio</th><th>Net Margin</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <div class="kv">
      <div><span class="k">Growth Pendapatan (CAGR)</span><span>${pct(kuant.growth_pendapatan)}</span></div>
      <div><span class="k">Growth Laba Bersih (CAGR)</span><span>${pct(kuant.growth_laba_bersih)}</span></div>
    </div>`;
  const chart = renderTrendChart(kuant.rasio_historis);
  if (chart) s.appendChild(chart);
  s.appendChild(poinEl(llm, "profitabilitas", "Profitabilitas"));
  s.appendChild(poinEl(llm, "solvabilitas", "Solvabilitas"));
  s.appendChild(poinEl(llm, "likuiditas", "Likuiditas"));
  s.appendChild(poinEl(llm, "pertumbuhan", "Pertumbuhan"));
  if (llm?.ringkasan) s.insertAdjacentHTML("beforeend", `<div class="summary">${llm.ringkasan}</div>`);
  return s;
}

function pilarValuasi(valu, llm) {
  const s = document.createElement("div");
  s.className = "pillar";
  const r = valu.relative, a = valu.absolute;
  const statusTag = llm?.status ? `<span class="tag ${llm.status}">${llm.status}</span>` : "";
  s.innerHTML = `<h3>3. Analisis Valuasi ${statusTag}</h3>
    <div class="kv">
      <div><span class="k">Harga Pasar</span><span>${rp(valu.harga_saham)}</span></div>
      <div><span class="k">EPS</span><span>${rp(r.eps)}</span></div>
      <div><span class="k">PER (sektor)</span><span>${numx(r.per)} (${numx(r.per_sektor)})</span></div>
      <div><span class="k">PBV (sektor)</span><span>${numx(r.pbv)} (${numx(r.pbv_sektor)})</span></div>
      <div><span class="k">Harga Wajar (PER)</span><span>${rp(r.harga_wajar_per)}</span></div>
      <div><span class="k">Harga Wajar (PBV)</span><span>${rp(r.harga_wajar_pbv)}</span></div>
      <div><span class="k">Nilai Intrinsik (DCF)</span><span>${rp(a.nilai_intrinsik_per_saham)}</span></div>
      <div><span class="k">Margin of Safety</span><span>${pct(valu.margin_of_safety)}</span></div>
    </div>`;
  s.appendChild(poinEl(llm, "relative_valuation", "Relative Valuation"));
  s.appendChild(poinEl(llm, "absolute_valuation", "Absolute Valuation"));
  if (llm?.kesimpulan_valuasi) s.insertAdjacentHTML("beforeend", `<div class="summary">${llm.kesimpulan_valuasi}</div>`);
  return s;
}

function pilarProyeksi(proyeksi, valuLLM) {
  if (!proyeksi || !proyeksi.proyeksi.length) return null;
  const s = document.createElement("div");
  s.className = "pillar";
  const rows = proyeksi.proyeksi.map((p) =>
    `<tr><td>${p.tahun}</td><td>${Math.round(p.pendapatan).toLocaleString("id-ID")}</td>
     <td>${Math.round(p.laba_bersih).toLocaleString("id-ID")}</td><td>${pct(p.net_margin)}</td></tr>`).join("");
  s.innerHTML = `<h3>4. Proyeksi Tahun Mendatang</h3>
    <p class="hint">Ekstrapolasi tren — CAGR pendapatan ${pct(proyeksi.cagr_pendapatan)},
      laba ${pct(proyeksi.cagr_laba)}. Bukan ramalan pasti.</p>
    <table class="ratios"><thead><tr><th>Tahun</th><th>Pendapatan (proy.)</th><th>Laba Bersih (proy.)</th><th>Net Margin</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  if (valuLLM?.outlook_tahun_depan)
    s.insertAdjacentHTML("beforeend", `<div class="summary">${valuLLM.outlook_tahun_depan}</div>`);
  return s;
}

// ---------- Markdown untuk unduhan ----------
function buatMarkdown(e, kuant, valu, proyeksi, kualLLM, kuantLLM, valuLLM, skorPilar, skorAkhir, rec) {
  const L = [];
  L.push(`# Analisis Saham — ${e.profil.nama || e.profil.kode} (${e.profil.kode})`);
  L.push(`_Sektor: ${e.profil.sektor} · ${new Date().toISOString().slice(0, 10)}_\n`);
  L.push(`## Kesimpulan`);
  L.push(`- **Rekomendasi:** ${rec.teks}`);
  L.push(`- **Skor akhir:** ${skorTxt(skorAkhir)}`);
  L.push(`- Kualitatif ${skorTxt(skorPilar.kualitatif)} · Kuantitatif ${skorTxt(skorPilar.kuantitatif)} · Valuasi ${skorTxt(skorPilar.valuasi)}`);
  if (valuLLM?.status) L.push(`- **Status valuasi:** ${valuLLM.status}`);
  const poin = (h, k, j) => h?.[k] ? `- **${j} — ${h[k].skor}/10:** ${h[k].justifikasi}` : `- **${j}:** _(AI belum dijalankan)_`;
  L.push(`\n## 1. Analisis Kualitatif`);
  L.push(poin(kualLLM, "model_bisnis", "Model Bisnis"));
  L.push(poin(kualLLM, "manajemen", "Manajemen"));
  L.push(poin(kualLLM, "keunggulan_kompetitif", "Keunggulan Kompetitif"));
  L.push(poin(kualLLM, "prospek_industri", "Prospek Industri"));
  L.push(`\n## 2. Analisis Kuantitatif`);
  L.push(`| Tahun | ROE | ROA | DER | Current Ratio | Net Margin |`);
  L.push(`|---|---|---|---|---|---|`);
  kuant.rasio_historis.forEach((r) =>
    L.push(`| ${r.tahun} | ${pct(r.roe)} | ${pct(r.roa)} | ${numx(r.der)} | ${numx(r.current_ratio)} | ${pct(r.net_profit_margin)} |`));
  L.push(`\n- Growth pendapatan (CAGR): ${pct(kuant.growth_pendapatan)}`);
  L.push(`- Growth laba bersih (CAGR): ${pct(kuant.growth_laba_bersih)}`);
  L.push(poin(kuantLLM, "profitabilitas", "Profitabilitas"));
  L.push(poin(kuantLLM, "solvabilitas", "Solvabilitas"));
  L.push(poin(kuantLLM, "likuiditas", "Likuiditas"));
  L.push(poin(kuantLLM, "pertumbuhan", "Pertumbuhan"));
  if (valu) {
    const r = valu.relative, a = valu.absolute;
    L.push(`\n## 3. Analisis Valuasi`);
    L.push(`- Harga pasar ${rp(valu.harga_saham)} · EPS ${rp(r.eps)}`);
    L.push(`- PER ${numx(r.per)} (sektor ${numx(r.per_sektor)}) · PBV ${numx(r.pbv)} (sektor ${numx(r.pbv_sektor)})`);
    L.push(`- Nilai intrinsik (DCF) ${rp(a.nilai_intrinsik_per_saham)} · Margin of safety ${pct(valu.margin_of_safety)}`);
    L.push(poin(valuLLM, "relative_valuation", "Relative Valuation"));
    L.push(poin(valuLLM, "absolute_valuation", "Absolute Valuation"));
  }
  if (proyeksi && proyeksi.proyeksi.length) {
    L.push(`\n## 4. Proyeksi Tahun Mendatang`);
    L.push(`_CAGR pendapatan ${pct(proyeksi.cagr_pendapatan)}, laba ${pct(proyeksi.cagr_laba)}._`);
    L.push(`| Tahun | Pendapatan (proy.) | Laba Bersih (proy.) | Net Margin |`);
    L.push(`|---|---|---|---|`);
    proyeksi.proyeksi.forEach((p) =>
      L.push(`| ${p.tahun} | ${Math.round(p.pendapatan).toLocaleString("id-ID")} | ${Math.round(p.laba_bersih).toLocaleString("id-ID")} | ${pct(p.net_margin)} |`));
    if (valuLLM?.outlook_tahun_depan) L.push(`\n> ${valuLLM.outlook_tahun_depan}`);
  }
  L.push(`\n---\n_Disclaimer: analisis otomatis untuk edukasi/riset, bukan rekomendasi jual/beli. DYOR._`);
  return L.join("\n");
}

$("btn-download").addEventListener("click", () => {
  const blob = new Blob([laporanMd], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `laporan_${bacaEmiten().profil.kode || "emiten"}.md`;
  a.click();
});
$("btn-print").addEventListener("click", () => window.print());

// ---------- Datalist emiten pra-ambil ----------
async function initDatalist() {
  try {
    const idx = await (await fetch("data/index.json", { cache: "no-cache" })).json();
    const dl = $("kode-list");
    dl.innerHTML = (idx.emiten || [])
      .map((e) => `<option value="${e.kode}">${e.nama}</option>`).join("");
  } catch (_) { /* index belum ada — abaikan */ }
}

// ---------- Init ----------
initTema();
initSettings();
initDatalist();
tambahKartuTahun();
