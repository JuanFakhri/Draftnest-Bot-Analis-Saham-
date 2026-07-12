// scoring.js — skoring deterministik (tanpa AI) untuk pilar Kuantitatif & Valuasi.
// Port dari draftnest/scoring.py. Output menyerupai bentuk keluaran analyzer LLM
// sehingga bisa dipakai langsung oleh render()/rataSkor() di app.js.

const pct = (x) => (x != null && isFinite(x) ? (x * 100).toFixed(1) + "%" : "n/a");
const numx = (x) => (x != null && isFinite(x) ? x.toFixed(2) + "x" : "n/a");
const rp = (x) => (x != null && isFinite(x) ? "Rp" + Math.round(x).toLocaleString("id-ID") : "n/a");

// Petakan nilai ke skor via daftar [batas, skor] urut menurun; None -> null.
function skorDariAmbang(nilai, ambang, bawah) {
  if (nilai == null || !isFinite(nilai)) return null;
  for (const [batas, skor] of ambang) {
    if (nilai >= batas) return skor;
  }
  return bawah;
}

// ----------------------------- Kuantitatif ----------------------------------

function skorProfitabilitas(r) {
  const skor = skorDariAmbang(r.roe,
    [[0.20, 10], [0.15, 8], [0.10, 7], [0.05, 5], [0.0, 3]], 1);
  if (skor == null) return [null, "ROE tidak tersedia — profitabilitas tak bisa dinilai."];
  let just = `ROE ${pct(r.roe)}, ROA ${pct(r.roa)}, NPM ${pct(r.net_profit_margin)}. `;
  if (r.roe >= 0.15) just += "Profitabilitas kuat, imbal hasil ekuitas di atas rata-rata pasar.";
  else if (r.roe >= 0.05) just += "Profitabilitas moderat, masih menghasilkan laba yang sehat.";
  else just += "Profitabilitas lemah/negatif, perlu perhatian pada kemampuan mencetak laba.";
  return [skor, just];
}

function skorSolvabilitas(r) {
  const skor = skorDariAmbang(r.der == null ? null : -r.der,
    [[-0.3, 10], [-0.5, 9], [-1.0, 7], [-2.0, 5], [-3.0, 3]], 1);
  if (skor == null) return [null, "DER tidak tersedia — solvabilitas tak bisa dinilai."];
  let just = `DER ${numx(r.der)}. `;
  if (r.der <= 0.5) just += "Struktur modal konservatif, leverage rendah — risiko solvabilitas kecil.";
  else if (r.der <= 1.0) just += "Leverage moderat, utang masih dalam batas wajar terhadap ekuitas.";
  else if (r.der <= 2.0) just += "Leverage cukup tinggi, beban utang perlu dipantau.";
  else just += "Leverage sangat tinggi — risiko solvabilitas signifikan.";
  return [skor, just];
}

function skorLikuiditas(r) {
  const skor = skorDariAmbang(r.current_ratio,
    [[2.0, 9], [1.5, 7], [1.0, 5], [0.75, 3]], 2);
  if (skor == null) return [null, "Current Ratio tidak tersedia — likuiditas tak bisa dinilai."];
  let just = `Current Ratio ${numx(r.current_ratio)}. `;
  const cr = r.current_ratio;
  if (cr >= 2.0) just += "Likuiditas sangat sehat, aset lancar jauh menutupi kewajiban jangka pendek.";
  else if (cr >= 1.0) just += "Likuiditas memadai, kewajiban jangka pendek tertutupi aset lancar.";
  else just += "Likuiditas ketat — aset lancar belum menutupi kewajiban jangka pendek.";
  return [skor, just];
}

function skorPertumbuhan(kuant) {
  const komponen = [kuant.growth_pendapatan, kuant.growth_laba_bersih].filter((g) => g != null);
  if (!komponen.length) return [null, "Butuh ≥ 2 tahun data untuk menilai pertumbuhan."];
  const rata = komponen.reduce((a, b) => a + b, 0) / komponen.length;
  const skor = skorDariAmbang(rata, [[0.20, 10], [0.10, 8], [0.05, 6], [0.0, 4]], 2);
  let just = `CAGR pendapatan ${pct(kuant.growth_pendapatan)}, CAGR laba ${pct(kuant.growth_laba_bersih)}. `;
  if (rata >= 0.10) just += "Pertumbuhan kuat dan konsisten di atas inflasi.";
  else if (rata >= 0.0) just += "Pertumbuhan positif namun moderat.";
  else just += "Pertumbuhan negatif — kinerja menurun dibanding awal periode.";
  return [skor, just];
}

export function skorKuantitatif(kuant) {
  const r = kuant.rasio_terbaru;
  const [profS, profJ] = skorProfitabilitas(r);
  const [solvS, solvJ] = skorSolvabilitas(r);
  const [likS, likJ] = skorLikuiditas(r);
  const [tumS, tumJ] = skorPertumbuhan(kuant);

  const hasil = {};
  if (profS != null) hasil.profitabilitas = { skor: profS, justifikasi: profJ };
  if (solvS != null) hasil.solvabilitas = { skor: solvS, justifikasi: solvJ };
  if (likS != null) hasil.likuiditas = { skor: likS, justifikasi: likJ };
  if (tumS != null) hasil.pertumbuhan = { skor: tumS, justifikasi: tumJ };

  const skorAda = Object.values(hasil).map((d) => d.skor);
  if (skorAda.length) {
    const rata = skorAda.reduce((a, b) => a + b, 0) / skorAda.length;
    hasil.ringkasan =
      `Skor kuantitatif rata-rata ${rata.toFixed(1)}/10 berdasarkan rasio tahun ` +
      `${r.tahun} (dihitung dari data, tanpa AI). ` + profJ;
  }
  return hasil;
}

// ------------------------------- Valuasi ------------------------------------

function skorRelative(v) {
  const rel = v.relative;
  const mos = rel.mos_fair_value;
  if (mos != null) {
    const skor = skorDariAmbang(mos,
      [[0.30, 10], [0.15, 9], [0.05, 8], [0.0, 6], [-0.15, 4]], 2);
    const status = mos >= 0.05 ? "undervalued" : mos <= -0.05 ? "overvalued" : "fairvalued";
    let just = `Fair Value (Mean PER&PBV) ${rp(rel.fair_value)} vs harga ${rp(v.harga_saham)} → Margin of Safety ${pct(mos)}. `;
    just += mos >= 0.05 ? "Harga di bawah nilai wajar (diskon)."
      : mos <= -0.05 ? "Harga di atas nilai wajar (premium)." : "Harga mendekati nilai wajar.";
    return [skor, just, status];
  }
  // Fallback: PER & PBV vs sektor (rasio < sektor = lebih murah).
  const poin = [];
  const detail = [];
  if (rel.per != null && rel.per_sektor) {
    poin.push(skorDariAmbang(-(rel.per / rel.per_sektor), [[-0.7, 9], [-1.0, 7], [-1.3, 5]], 3));
    detail.push(`PER ${numx(rel.per)} vs sektor ${numx(rel.per_sektor)}`);
  }
  if (rel.pbv != null && rel.pbv_sektor) {
    poin.push(skorDariAmbang(-(rel.pbv / rel.pbv_sektor), [[-0.7, 9], [-1.0, 7], [-1.3, 5]], 3));
    detail.push(`PBV ${numx(rel.pbv)} vs sektor ${numx(rel.pbv_sektor)}`);
  }
  if (!poin.length) return [null, "Data PER/PBV sektor atau Fair Value tak tersedia.", null];
  const skor = Math.round(poin.reduce((a, b) => a + b, 0) / poin.length);
  const status = skor >= 7 ? "undervalued" : skor <= 4 ? "overvalued" : "fairvalued";
  return [skor, detail.join("; ") + ".", status];
}

function skorAbsolute(v) {
  const mos = v.margin_of_safety;
  if (mos == null) return [null, "Nilai intrinsik DCF tak tersedia — asumsi/FCF tidak lengkap."];
  const skor = skorDariAmbang(mos,
    [[0.30, 10], [0.15, 9], [0.05, 7], [0.0, 6], [-0.20, 4]], 2);
  const ni = v.absolute.nilai_intrinsik_per_saham;
  let just = `Nilai intrinsik DCF ${rp(ni)} vs harga ${rp(v.harga_saham)} → Margin of Safety ${pct(mos)}. `;
  if (mos >= 0.15) just += "Diskon signifikan terhadap nilai intrinsik (menarik, namun sensitif asumsi).";
  else if (mos >= 0.0) just += "Harga sedikit di bawah nilai intrinsik.";
  else just += "Harga di atas nilai intrinsik DCF (premium).";
  return [skor, just];
}

export function skorValuasi(v, proyeksi = null) {
  if (!v) return null;
  const [relS, relJ, relStatus] = skorRelative(v);
  const [absS, absJ] = skorAbsolute(v);

  const hasil = {};
  if (relS != null) hasil.relative_valuation = { skor: relS, justifikasi: relJ };
  if (absS != null) hasil.absolute_valuation = { skor: absS, justifikasi: absJ };

  let status = null;
  const mos = v.margin_of_safety;
  if (mos != null) status = mos >= 0.05 ? "undervalued" : mos <= -0.05 ? "overvalued" : "fairvalued";
  else if (relStatus != null) status = relStatus;
  if (status != null) hasil.status = status;

  const skorAda = Object.values(hasil).filter((d) => d && d.skor != null).map((d) => d.skor);
  if (skorAda.length) {
    const rata = skorAda.reduce((a, b) => a + b, 0) / skorAda.length;
    const label = { undervalued: "cenderung undervalued", overvalued: "cenderung overvalued",
      fairvalued: "mendekati wajar" }[status] || "belum simpul";
    hasil.kesimpulan_valuasi =
      `Berdasar hitung data (tanpa AI), harga ${label} dengan skor valuasi rata-rata ${rata.toFixed(1)}/10. ` + relJ;
    if (proyeksi && proyeksi.proyeksi && proyeksi.proyeksi.length) {
      hasil.outlook_tahun_depan =
        `Proyeksi ekstrapolasi CAGR: pendapatan ${pct(proyeksi.cagr_pendapatan)}, ` +
        `laba ${pct(proyeksi.cagr_laba)} per tahun. Angka proyeksi sangat sensitif terhadap asumsi pertumbuhan.`;
    }
  }
  return Object.keys(hasil).length ? hasil : null;
}
