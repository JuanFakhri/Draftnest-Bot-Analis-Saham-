// avgdown.js — Kalkulator Average Down (port dari draftnest/average_down.py).
const SAHAM_PER_LOT = 100;
const $ = (id) => document.getElementById(id);

const rp = (x) => (x != null && isFinite(x) ? "Rp" + Math.round(x).toLocaleString("id-ID") : "–");
const pct = (x) => (x != null && isFinite(x) ? (x * 100).toFixed(2) + "%" : "–");
const numLot = (x) => (x != null && isFinite(x) ? (Math.round(x * 100) / 100).toLocaleString("id-ID") : "–");

export function hitung(pembelian, hargaSekarang, cash) {
  const totalLot = pembelian.reduce((a, p) => a + p.lot, 0);
  const totalSaham = totalLot * SAHAM_PER_LOT;
  const totalModal = pembelian.reduce((a, p) => a + p.lot * SAHAM_PER_LOT * p.harga, 0);
  const hargaRata = totalSaham ? totalModal / totalSaham : null;
  const nilaiSekarang = totalSaham * hargaSekarang;
  const untungRugi = nilaiSekarang - totalModal;
  const untungRugiPct = totalModal ? untungRugi / totalModal : null;
  const diBawahRata = hargaRata != null && hargaSekarang < hargaRata;
  const kenaikanBep = hargaRata != null && hargaSekarang ? (hargaRata - hargaSekarang) / hargaSekarang : null;

  let persenInvestasi = null, risiko = null;
  if (cash && cash > 0) {
    persenInvestasi = totalModal / cash;
    risiko = persenInvestasi >= 0.7 ? "HIGH RISK" : persenInvestasi >= 0.4 ? "MEDIUM RISK" : "LOW RISK";
  }
  return { totalLot, totalSaham, totalModal, hargaRata, hargaSekarang, nilaiSekarang,
    untungRugi, untungRugiPct, diBawahRata, kenaikanBep, persenInvestasi, risiko };
}

export function lotUntukTarget(totalLotAwal, hargaRataAwal, hargaBeli, targetRata) {
  if (!(hargaBeli < targetRata && targetRata < hargaRataAwal)) return null;
  const s0 = totalLotAwal * SAHAM_PER_LOT;
  const c0 = s0 * hargaRataAwal;
  const penyebut = hargaBeli - targetRata;
  if (penyebut === 0) return null;
  const lot = ((targetRata * s0 - c0) / penyebut) / SAHAM_PER_LOT;
  return lot > 0 ? lot : null;
}

function tambahBaris(data = {}, awal = false) {
  const div = document.createElement("div");
  div.className = "ad-row";
  div.innerHTML = `
    <span class="ad-tag">${awal ? "Posisi Awal" : "Avg Down"}</span>
    <label>Jumlah Lot<input type="number" step="any" class="ad-lot" value="${data.lot ?? ""}" placeholder="mis. 34" /></label>
    <label>Harga Beli<input type="number" step="any" class="ad-harga-beli" value="${data.harga ?? ""}" placeholder="Rp/lembar" /></label>
    <button type="button" class="ad-del" title="Hapus baris" ${awal ? "disabled" : ""}>✕</button>`;
  div.querySelector(".ad-del").addEventListener("click", () => { div.remove(); render(); });
  $("ad-rows").appendChild(div);
}

function bacaPembelian() {
  const out = [];
  for (const row of document.querySelectorAll("#ad-rows .ad-row")) {
    const lot = parseFloat(row.querySelector(".ad-lot").value);
    const harga = parseFloat(row.querySelector(".ad-harga-beli").value);
    if (lot > 0 && harga > 0) out.push({ lot, harga });
  }
  return out;
}

function badgeRisiko(r) {
  if (!r) return "";
  const kelas = r.startsWith("HIGH") ? "jual" : r.startsWith("MEDIUM") ? "tahan" : "beli";
  return `<span class="rec-badge ${kelas}" style="font-size:12px;padding:4px 10px">${r}</span>`;
}

function render() {
  const beli = bacaPembelian();
  const harga = parseFloat($("ad-harga").value);
  const cash = parseFloat($("ad-cash").value) || null;
  const box = $("ad-result");

  if (!beli.length || !(harga > 0)) {
    box.innerHTML = `<p class="hint">Isi minimal satu baris (lot & harga beli) dan Harga Saat Ini untuk melihat hasil.</p>`;
    $("ad-sim-out").textContent = "";
    return;
  }

  const h = hitung(beli, harga, cash);
  const plKelas = h.untungRugi >= 0 ? "pos" : "neg";
  box.innerHTML = `
    <div class="ad-hero">
      <div><span class="ad-hero-num">${rp(h.hargaRata)}</span><small>Harga Rata-rata</small></div>
      <div><span class="ad-hero-num ${plKelas}">${rp(h.untungRugi)}</span><small>Untung/Rugi (${pct(h.untungRugiPct)})</small></div>
    </div>
    <div class="kv">
      <div><span class="k">Total Lot</span><span>${numLot(h.totalLot)} lot (${h.totalSaham.toLocaleString("id-ID")} lembar)</span></div>
      <div><span class="k">Total Modal</span><span>${rp(h.totalModal)}</span></div>
      <div><span class="k">Harga Saat Ini</span><span>${rp(h.hargaSekarang)}</span></div>
      <div><span class="k">Nilai Sekarang</span><span>${rp(h.nilaiSekarang)}</span></div>
      <div><span class="k">Status</span><span>${h.diBawahRata ? "⬇️ Masih di bawah rata-rata (nyangkut)" : "⬆️ Di atas/di harga rata-rata"}</span></div>
      <div><span class="k">Kenaikan ke BEP</span><span>${h.kenaikanBep != null && h.kenaikanBep > 0 ? "+" + pct(h.kenaikanBep) + " dari harga kini" : "sudah balik modal"}</span></div>
      ${h.risiko ? `<div><span class="k">% Investasi</span><span>${pct(h.persenInvestasi)}</span></div>
      <div><span class="k">Risiko</span><span>${badgeRisiko(h.risiko)}</span></div>` : ""}
    </div>`;

  // Simulator: berapa lot untuk turunkan average ke target.
  const target = parseFloat($("ad-sim-target").value);
  const hargaBeli = parseFloat($("ad-sim-harga").value) || harga;
  const out = $("ad-sim-out");
  if (target > 0 && h.hargaRata != null) {
    const lot = lotUntukTarget(h.totalLot, h.hargaRata, hargaBeli, target);
    if (lot != null) {
      const tambahanModal = lot * SAHAM_PER_LOT * hargaBeli;
      out.className = "summary";
      out.innerHTML = `Untuk menurunkan rata-rata ke <b>${rp(target)}</b>, beli <b>${numLot(lot)} lot</b> di harga <b>${rp(hargaBeli)}</b> (modal tambahan ${rp(tambahanModal)}).`;
    } else {
      out.className = "hint";
      out.textContent = `Target ${rp(target)} tak tercapai: target harus di antara harga beli (${rp(hargaBeli)}) dan rata-rata saat ini (${rp(h.hargaRata)}).`;
    }
  } else {
    out.textContent = "";
  }
}

export function initAvgDown() {
  tambahBaris({}, true);
  $("ad-add").addEventListener("click", () => tambahBaris());
  // Recompute live pada input apa pun di view average down.
  $("view-avgdown").addEventListener("input", render);
  render();
}
