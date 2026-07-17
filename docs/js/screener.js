// screener.js — Screener saham (port ringan dari draftnest/screener.py).
// Memuat docs/data/screener.json lalu menyaring di sisi browser.

const $ = (id) => document.getElementById(id);
const pct = (x) => (x != null && isFinite(x) ? (x * 100).toFixed(1) + "%" : "–");
const num = (x) => (x != null && isFinite(x) ? x.toFixed(2) + "x" : "–");
const skor = (x) => (x != null && isFinite(x) ? x.toFixed(1) : "–");

let DATA = null;          // {emiten:[...], diperbarui}
let onPilihEmiten = null; // callback saat baris dipilih

function bacaKriteria() {
  const persen = (id) => {
    const v = parseFloat($(id).value);
    return isFinite(v) ? v / 100 : null;
  };
  const skorMinRaw = parseFloat($("sc-skor-min").value);
  return {
    naikPend: $("sc-naik-pend").checked,
    naikLaba: $("sc-naik-laba").checked,
    prospek: $("sc-prospek").checked,
    abaikanDividen: $("sc-abaikan-dividen").checked,
    dyMin: persen("sc-dy-min"),
    dyMaks: persen("sc-dy-maks"),
    streakMin: parseInt($("sc-dy-streak").value, 10) || 0,
    skorMin: isFinite(skorMinRaw) ? skorMinRaw : null,
  };
}

function lolos(r, k) {
  if (k.naikPend && !r.naik_pendapatan) return false;
  if (k.naikLaba && !r.naik_laba) return false;
  if (!k.abaikanDividen) {
    const dy = r.dividend_yield;
    if (k.dyMin != null && (dy == null || dy < k.dyMin)) return false;
    if (k.dyMaks != null && dy != null && dy > k.dyMaks) return false;
    if (k.streakMin && (r.dividen_beruntun || 0) < k.streakMin) return false;
  }
  if (k.prospek && !r.prospek_bagus) return false;
  if (k.skorMin != null && (r.skor_akhir == null || r.skor_akhir < k.skorMin)) return false;
  return true;
}

function badgeRek(rek) {
  if (!rek) return "–";
  const t = rek.split(" ")[0];
  const kelas = t === "BELI" ? "beli" : t === "JUAL" ? "jual" : "tahan";
  return `<span class="rec-badge ${kelas}" style="font-size:11px;padding:3px 8px">${t}</span>`;
}

function render() {
  if (!DATA) return;
  const k = bacaKriteria();
  const hasil = DATA.emiten.filter((r) => lolos(r, k))
    .sort((a, b) => (b.skor_akhir || 0) - (a.skor_akhir || 0));

  const adaDividen = DATA.emiten.some((r) => r.dividend_yield != null);
  const catatanDiv = (!adaDividen && !k.abaikanDividen)
    ? ` <b>Catatan:</b> data dividen belum tersedia di dataset ini, jadi filter dividen menyaring semua. Centang “Abaikan filter dividen” untuk melihat hasil pertumbuhan+prospek, atau tunggu pembaruan data.`
    : "";
  $("sc-status").innerHTML =
    `${hasil.length} emiten cocok dari ${DATA.emiten.length} (data ${DATA.diperbarui}).${catatanDiv}`;

  if (!hasil.length) { $("sc-result").innerHTML = ""; return; }

  const rows = hasil.map((r) => `
    <tr data-kode="${r.kode}" class="sc-row">
      <td><b>${r.kode}</b></td>
      <td>${r.nama || ""}</td>
      <td>${r.sektor || "–"}</td>
      <td>${pct(r.cagr_laba)}</td>
      <td>${pct(r.roe)}</td>
      <td>${pct(r.dividend_yield)}${r.dividen_beruntun ? ` <span class="hint">(${r.dividen_beruntun}th)</span>` : ""}</td>
      <td>${skor(r.skor_akhir)}</td>
      <td>${badgeRek(r.rekomendasi)}</td>
    </tr>`).join("");

  $("sc-result").innerHTML = `
    <div style="overflow-x:auto">
    <table class="ratios sc-table">
      <thead><tr>
        <th>Kode</th><th>Nama</th><th>Sektor</th><th>CAGR Laba</th><th>ROE</th>
        <th>Div Yield</th><th>Skor</th><th>Rekom.</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <p class="hint">Klik baris untuk memuat emiten ke tab Analisis. Dividend Yield “(Nth)” = jumlah tahun beruntun membagi dividen.</p>`;

  for (const tr of $("sc-result").querySelectorAll(".sc-row")) {
    tr.addEventListener("click", () => onPilihEmiten && onPilihEmiten(tr.dataset.kode));
  }
}

export async function initScreener(onPilih) {
  onPilihEmiten = onPilih;
  $("view-screener").addEventListener("input", render);
  try {
    DATA = await (await fetch(`data/screener.json?t=${Date.now()}`, { cache: "no-store" })).json();
    render();
  } catch (_) {
    $("sc-status").textContent = "Gagal memuat data screener (data/screener.json belum tersedia).";
  }
}
