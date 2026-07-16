// bsjp.js — menu "Beli Sore, Jual Pagi" (overnight): mode Peluang Gap + 2 strategi backtested.
// Data: docs/data/screener.json (per emiten) & docs/data/backtest.json (agregasi backtest).
// Menampilkan PELUANG/HASIL HISTORIS, bukan jaminan. Menahan semalam berisiko gap-down.

import { cekSinyalLive } from "./signals.js";

const $ = (id) => document.getElementById(id);
const pct = (x) => (x != null && isFinite(x) ? (x * 100).toFixed(1) + "%" : "–");
const pct2 = (x) => (x != null && isFinite(x) ? (x * 100).toFixed(2) + "%" : "–");
const skor = (x) => (x != null && isFinite(x) ? x.toFixed(1) : "–");
const ribu = (x) => (x != null && isFinite(x) ? Math.round(x).toLocaleString("id-ID") : "–");

let DATA = null;       // screener.json
let BT = null;         // backtest.json
let onPilihEmiten = null;

const INFO_STRATEGI = {
  s1: "RSI(14) 25–50, volume ≥2× kemarin, return hari −5%…+1%, harga ≥100, market cap ≥Rp500 M, value ≥Rp1 M. " +
      "⚠️ Syarat asli 'Foreign Flow > 0' TIDAK tersedia dari sumber data, jadi backtest ini tanpa syarat itu.",
  s2: "Harga naik >5% dari kemarin, harga ≥ MA5, volume <1,2× kemarin, value ≥Rp5 M.",
  s_or: "Hari yang memenuhi Strategi 1 ATAU Strategi 2 (gabungan sinyal keduanya).",
  s_and: "Hari yang memenuhi Strategi 1 DAN Strategi 2 sekaligus. ⚠️ Keduanya BERTENTANGAN " +
         "(S1 minta hari turun/flat, S2 minta hari naik >5%), jadi hasilnya hampir selalu 0 sinyal.",
};
const FLAG_STRATEGI = { s1: "strat1_sinyal", s2: "strat2_sinyal", s_or: "strat_or_sinyal", s_and: "strat_and_sinyal" };

function bacaKriteriaGap() {
  const persen = (id) => { const v = parseFloat($(id).value); return isFinite(v) ? v / 100 : null; };
  return {
    peluangMin: persen("bs-peluang"),
    winMin: persen("bs-winrate"),
    volMin: parseFloat($("bs-volume").value) || 0,
    hanyaFundamental: $("bs-hanya-fundamental").checked,
  };
}

function lolosGap(r, k) {
  if (r.bsjp_peluang == null) return false;
  if (k.peluangMin != null && r.bsjp_peluang < k.peluangMin) return false;
  if (k.winMin != null && (r.bsjp_win_rate == null || r.bsjp_win_rate < k.winMin)) return false;
  if (k.volMin && (r.bsjp_volume == null || r.bsjp_volume < k.volMin)) return false;
  if (k.hanyaFundamental && (r.skor_akhir == null || r.skor_akhir < 5.5)) return false;
  return true;
}

// Aggregasi ulang win rate dari hitungan per-saham (subset yang difilter).
function agregasiSubset(emiten, key) {
  let sinyal = 0, menang = 0, hit3 = 0, ret = 0;
  for (const e of emiten) {
    sinyal += e[`bt_${key}_sinyal`] || 0;
    menang += e[`bt_${key}_menang`] || 0;
    hit3 += e[`bt_${key}_hit3`] || 0;
    ret += e[`bt_${key}_ret`] || 0;
  }
  return {
    total_sinyal: sinyal,
    win_rate: sinyal ? menang / sinyal : null,
    peluang_3persen: sinyal ? hit3 / sinyal : null,
    rata_overnight: sinyal ? ret / sinyal : null,
  };
}

function kartuBacktest(nama, pool, subset, adaFilter) {
  const warna = (x) => (x == null ? "" : x >= 0 ? "pos" : "neg");
  const s = adaFilter ? subset : pool;
  const menarik = s.win_rate != null && s.win_rate > 0.5 && (s.rata_overnight || 0) > 0;
  const bandingan = adaFilter
    ? `<p class="hint" style="margin:6px 0 0">Tanpa filter (semua IDX): win rate ${pct(pool.win_rate)}, rata ${pct2(pool.rata_overnight)}, ${ribu(pool.total_sinyal)} sinyal.</p>`
    : "";
  return `<div class="warnbox" style="border-left-color:var(--accent)">
    <b>Backtest ${nama}</b> (histori ~6 th${adaFilter ? ", <u>subset terfilter</u>" : ", seluruh IDX"}):
    <div class="kv" style="margin-top:6px">
      <div><span class="k">Total sinyal</span><span>${ribu(s.total_sinyal)}</span></div>
      <div><span class="k">Win rate (overnight+)</span><span class="${warna(s.win_rate - 0.5)}">${pct(s.win_rate)}</span></div>
      <div><span class="k">Rata-rata gain semalam</span><span class="${warna(s.rata_overnight)}">${pct2(s.rata_overnight)}</span></div>
      <div><span class="k">Peluang ≥3% semalam</span><span>${pct(s.peluang_3persen)}</span></div>
    </div>
    <p style="margin:8px 0 0">${menarik
      ? "Secara historis <b>rata-rata positif semalam</b> — tetap bukan jaminan; angka ini KOTOR (belum fee/spread/pajak)."
      : "⚠️ Secara historis <b>rata-rata TIDAK menguntungkan</b> semalam (win rate ≤50% atau rata gain negatif). Hati-hati."}</p>
    ${bandingan}
  </div>`;
}

function render() {
  if (!DATA) return;
  const mode = $("bs-strategi").value;
  const strategiMode = mode !== "gap";
  $("bs-strategi-info").textContent = strategiMode ? (INFO_STRATEGI[mode] || "") : "";
  $("bs-kriteria-gap").style.display = strategiMode ? "none" : "";
  // Filter subset hanya untuk mode strategi yang punya hitungan per-saham (s1/s2/s_or).
  const bisaSubset = strategiMode && mode !== "s_and";
  $("bs-filter-subset").hidden = !bisaSubset;

  const adaGap = DATA.emiten.some((r) => r.bsjp_peluang != null);
  if (!adaGap && mode === "gap") {
    $("bs-status").textContent =
      "Data overnight-gap belum tersedia (butuh riwayat harga harian). Akan terisi setelah pembaruan data.";
    $("bs-result").innerHTML = ""; $("bs-backtest").innerHTML = ""; return;
  }

  // Subset filter values.
  const skorMin = parseFloat($("bs-skor-min").value);
  const volMin = parseFloat($("bs-vol-subset").value);
  const sektor = ($("bs-sektor").value || "").trim().toLowerCase();
  const adaFilter = bisaSubset && (isFinite(skorMin) || isFinite(volMin) || !!sektor);
  const lolosSubset = (r) => {
    if (isFinite(skorMin) && (r.skor_akhir == null || r.skor_akhir < skorMin)) return false;
    if (isFinite(volMin) && (r.bsjp_volume == null || r.bsjp_volume < volMin)) return false;
    if (sektor && !(r.sektor || "").toLowerCase().includes(sektor)) return false;
    return true;
  };

  // Kartu backtest: live-recompute untuk subset.
  if (strategiMode) {
    const key = mode === "s_and" ? null : mode;
    if (mode === "s_and") {
      $("bs-backtest").innerHTML = BT ? kartuBacktest(BT.strategi.s_and.nama, BT.strategi.s_and, BT.strategi.s_and, false) : "";
    } else {
      const pool = agregasiSubset(DATA.emiten, key);
      const subset = agregasiSubset(DATA.emiten.filter(lolosSubset), key);
      const nama = (BT && BT.strategi[mode] && BT.strategi[mode].nama) || mode;
      $("bs-backtest").innerHTML = kartuBacktest(nama, pool, subset, adaFilter);
    }
  } else {
    $("bs-backtest").innerHTML = "";
  }

  let hasil, judul;
  if (mode === "gap") {
    const k = bacaKriteriaGap();
    hasil = DATA.emiten.filter((r) => lolosGap(r, k))
      .sort((a, b) => (b.bsjp_peluang || 0) - (a.bsjp_peluang || 0));
    judul = "peluang gap ≥3% tertinggi";
  } else {
    const flag = FLAG_STRATEGI[mode];
    hasil = DATA.emiten.filter((r) => r[flag] && (!adaFilter || lolosSubset(r)))
      .sort((a, b) => (b.bsjp_peluang || 0) - (a.bsjp_peluang || 0));
    judul = "yang memicu sinyal strategi pada data terakhir" + (adaFilter ? " (terfilter)" : "");
  }

  const adaSinyalData = mode === "gap" || DATA.emiten.some((r) => r[FLAG_STRATEGI[mode]] != null);
  if (!adaSinyalData) {
    $("bs-status").textContent = "Data sinyal strategi belum tersedia — akan terisi setelah pembaruan data harga.";
    $("bs-result").innerHTML = ""; return;
  }

  $("bs-status").innerHTML =
    `${hasil.length} saham (${judul}, data ${DATA.diperbarui}). <b>Ingat:</b> ini historis, bukan jaminan besok naik.`;
  if (!hasil.length) { $("bs-result").innerHTML = ""; return; }

  const rows = hasil.slice(0, 100).map((r) => `
    <tr data-kode="${r.kode}" class="sc-row">
      <td><b>${r.kode}</b></td>
      <td>${r.nama || ""}</td>
      <td><b class="bsjp-hero">${pct(r.bsjp_peluang)}</b></td>
      <td>${pct(r.bsjp_win_rate)}</td>
      <td>${pct2(r.bsjp_rata_gap)}</td>
      <td>${ribu(r.bsjp_volume)}</td>
      <td>${skor(r.skor_akhir)}</td>
    </tr>`).join("");

  $("bs-result").innerHTML = `
    <div style="overflow-x:auto">
    <table class="ratios sc-table">
      <thead><tr>
        <th>Kode</th><th>Nama</th><th>Peluang ≥3% pagi</th><th>Win rate (gap+)</th>
        <th>Rata gap</th><th>Volume/hari</th><th>Skor fund.</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <p class="hint">Klik baris untuk analisis fundamental emiten. Angka "peluang/win/rata gap" di atas
      adalah statistik overnight umum saham tsb (bukan khusus strategi). Pertimbangkan likuiditas,
      spread, biaya, dan risiko sentimen pasar memburuk.</p>`;

  for (const tr of $("bs-result").querySelectorAll(".sc-row")) {
    tr.addEventListener("click", () => onPilihEmiten && onPilihEmiten(tr.dataset.kode));
  }
}

async function cekLive() {
  const kode = ($("bs-live-kode").value || "").trim().toUpperCase();
  const out = $("bs-live-out");
  const btn = $("bs-live-btn");
  if (!kode) { out.textContent = "Isi kode emiten dulu."; return; }
  const row = DATA?.emiten?.find((e) => e.kode === kode);
  const shares = row?.saham || null;
  btn.disabled = true; out.textContent = `Mengambil harga live ${kode}…`;
  try {
    const r = await cekSinyalLive(kode, shares);
    const tag = (ok) => ok ? '<b class="pos">✅ SINYAL</b>' : '<span class="neg">tidak</span>';
    out.innerHTML =
      `<b>${r.kode}</b> per ${r.tanggal} · harga ${rp(r.harga)} · RSI ${r.rsi != null ? r.rsi.toFixed(0) : "–"} · ` +
      `return hari ${pct2(r.ret)} · value ${ribu(r.value)}<br>` +
      `Strategi 1 (RSI Pullback): ${tag(r.s1)}${r.mcapDilewati ? " <span class='hint'>(syarat market-cap dilewati: saham beredar tak diketahui)</span>" : ""} · ` +
      `Strategi 2 (Momentum): ${tag(r.s2)}<br>` +
      `<span class="hint">⚠️ Bar hari ini bisa <b>belum final</b> sampai bursa tutup (16:00 WIB). Sinyal bisa berubah. Bukan ajakan beli.</span>`;
  } catch (e) {
    out.innerHTML = `⚠️ Gagal ambil harga live (${e.message}). Proxy publik kadang diblokir — coba lagi, ` +
      `atau lihat sinyal harian yang di-refresh otomatis di tabel.`;
  } finally {
    btn.disabled = false;
  }
}

export async function initBSJP(onPilih) {
  onPilihEmiten = onPilih;
  $("view-bsjp").addEventListener("input", render);
  $("bs-strategi").addEventListener("change", render);
  $("bs-live-btn").addEventListener("click", cekLive);
  try {
    DATA = await (await fetch("data/screener.json", { cache: "no-cache" })).json();
  } catch (_) {
    $("bs-status").textContent = "Gagal memuat data (data/screener.json belum tersedia)."; return;
  }
  try { BT = await (await fetch("data/backtest.json", { cache: "no-cache" })).json(); } catch (_) { BT = null; }
  render();
}
