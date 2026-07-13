// bsjp.js — menu "Beli Sore, Jual Pagi" (overnight gap).
// Memakai statistik overnight gap (close -> open besok) dari docs/data/screener.json.
// Menampilkan PELUANG HISTORIS, bukan jaminan. Menahan semalam berisiko gap-down.

const $ = (id) => document.getElementById(id);
const pct = (x) => (x != null && isFinite(x) ? (x * 100).toFixed(1) + "%" : "–");
const skor = (x) => (x != null && isFinite(x) ? x.toFixed(1) : "–");
const ribu = (x) => (x != null && isFinite(x) ? Math.round(x).toLocaleString("id-ID") : "–");

let DATA = null;
let onPilihEmiten = null;

function kriteria() {
  const persen = (id) => { const v = parseFloat($(id).value); return isFinite(v) ? v / 100 : null; };
  return {
    peluangMin: persen("bs-peluang"),
    winMin: persen("bs-winrate"),
    volMin: parseFloat($("bs-volume").value) || 0,
    hanyaFundamental: $("bs-hanya-fundamental").checked,
  };
}

function lolos(r, k) {
  if (r.bsjp_peluang == null) return false;
  if (k.peluangMin != null && r.bsjp_peluang < k.peluangMin) return false;
  if (k.winMin != null && (r.bsjp_win_rate == null || r.bsjp_win_rate < k.winMin)) return false;
  if (k.volMin && (r.bsjp_volume == null || r.bsjp_volume < k.volMin)) return false;
  if (k.hanyaFundamental && (r.skor_akhir == null || r.skor_akhir < 5.5)) return false;
  return true;
}

function render() {
  if (!DATA) return;
  const k = kriteria();
  const ada = DATA.emiten.some((r) => r.bsjp_peluang != null);
  if (!ada) {
    $("bs-status").innerHTML =
      "Data overnight-gap belum tersedia di dataset ini (butuh riwayat harga harian). " +
      "Akan terisi setelah pembaruan data harga. Sementara ini menu belum bisa memberi hasil.";
    $("bs-result").innerHTML = "";
    return;
  }

  const hasil = DATA.emiten.filter((r) => lolos(r, k))
    .sort((a, b) => (b.bsjp_peluang || 0) - (a.bsjp_peluang || 0));

  $("bs-status").innerHTML =
    `${hasil.length} saham cocok (data ${DATA.diperbarui}). Diurutkan dari peluang gap ≥3% tertinggi. ` +
    `<b>Ingat:</b> ini frekuensi historis, bukan jaminan besok naik.`;

  if (!hasil.length) { $("bs-result").innerHTML = ""; return; }

  const rows = hasil.slice(0, 100).map((r) => `
    <tr data-kode="${r.kode}" class="sc-row">
      <td><b>${r.kode}</b></td>
      <td>${r.nama || ""}</td>
      <td><b class="bsjp-hero">${pct(r.bsjp_peluang)}</b></td>
      <td>${pct(r.bsjp_win_rate)}</td>
      <td>${pct(r.bsjp_rata_gap)}</td>
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
    <p class="hint">
      <b>Peluang ≥3% pagi</b> = fraksi hari (±1 tahun) saat harga pembukaan ≥3% di atas penutupan sebelumnya.
      <b>Win rate</b> = fraksi hari gap positif. <b>Rata gap</b> = rata-rata selisih tutup→buka (sering mendekati 0).
      Klik baris untuk analisis fundamental emiten. Pertimbangkan likuiditas, spread, dan biaya transaksi —
      dan bahwa strategi ini rentan saat sentimen pasar memburuk.</p>`;

  for (const tr of $("bs-result").querySelectorAll(".sc-row")) {
    tr.addEventListener("click", () => onPilihEmiten && onPilihEmiten(tr.dataset.kode));
  }
}

export async function initBSJP(onPilih) {
  onPilihEmiten = onPilih;
  $("view-bsjp").addEventListener("input", render);
  try {
    DATA = await (await fetch("data/screener.json", { cache: "no-cache" })).json();
    render();
  } catch (_) {
    $("bs-status").textContent = "Gagal memuat data (data/screener.json belum tersedia).";
  }
}
