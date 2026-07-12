// finance.js — mesin keuangan di sisi browser.
// Port persis dari draftnest/ratios.py & valuation.py agar hasil konsisten.

export function bagi(a, b) {
  return b === 0 ? null : a / b;
}

export function cagr(awal, akhir, periode) {
  if (periode <= 0 || awal <= 0 || akhir <= 0) return null;
  return Math.pow(akhir / awal, 1 / periode) - 1;
}

export function fcf(lap) {
  if (lap.free_cash_flow != null) return lap.free_cash_flow;
  // Proxy: CFO + CFI (CFI biasanya negatif = capex)
  return lap.arus_kas_operasi + lap.arus_kas_investasi;
}

export function hitungRasio(lap) {
  return {
    tahun: lap.tahun,
    roe: bagi(lap.laba_bersih, lap.total_ekuitas),
    roa: bagi(lap.laba_bersih, lap.total_aset),
    der: bagi(lap.total_liabilitas, lap.total_ekuitas),
    current_ratio: bagi(lap.aset_lancar, lap.liabilitas_lancar),
    net_profit_margin: bagi(lap.laba_bersih, lap.pendapatan),
    gross_profit_margin: bagi(lap.laba_kotor, lap.pendapatan),
    operating_margin: bagi(lap.laba_operasi, lap.pendapatan),
  };
}

export function analisisKuantitatif(emiten) {
  const laporan = [...emiten.laporan].sort((a, b) => a.tahun - b.tahun);
  const rasio = laporan.map(hitungRasio);

  let growthPendapatan = null;
  let growthLaba = null;
  if (laporan.length >= 2) {
    const periode = laporan[laporan.length - 1].tahun - laporan[0].tahun;
    growthPendapatan = cagr(laporan[0].pendapatan, laporan[laporan.length - 1].pendapatan, periode);
    growthLaba = cagr(laporan[0].laba_bersih, laporan[laporan.length - 1].laba_bersih, periode);
  }

  return {
    rasio_terbaru: rasio[rasio.length - 1],
    rasio_historis: rasio,
    growth_pendapatan: growthPendapatan,
    growth_laba_bersih: growthLaba,
    tahun_data: laporan.map((l) => l.tahun),
  };
}

function laporanTerbaru(emiten) {
  return [...emiten.laporan].sort((a, b) => a.tahun - b.tahun).at(-1);
}

function relativeValuation(emiten) {
  const lap = laporanTerbaru(emiten);
  const p = emiten.pasar;
  const eps = bagi(lap.laba_bersih, p.saham_beredar);
  const bvps = bagi(lap.total_ekuitas, p.saham_beredar);
  const per = eps ? bagi(p.harga_saham, eps) : null;
  const pbv = bvps ? bagi(p.harga_saham, bvps) : null;

  // Fair Value (Mean PER & PBV) — metode rata-rata historis emiten sendiri.
  const fvPer = p.mean_per_3y && eps ? p.mean_per_3y * eps : null;
  const fvPbv = p.mean_pbv_3y && bvps ? p.mean_pbv_3y * bvps : null;
  const tersedia = [fvPer, fvPbv].filter((x) => x != null);
  const fairValue = tersedia.length ? tersedia.reduce((a, b) => a + b, 0) / tersedia.length : null;
  const mosFair = fairValue ? (fairValue - p.harga_saham) / fairValue : null;

  return {
    eps, bvps, per, pbv,
    per_sektor: p.per_sektor ?? null,
    pbv_sektor: p.pbv_sektor ?? null,
    harga_wajar_per: p.per_sektor && eps ? p.per_sektor * eps : null,
    harga_wajar_pbv: p.pbv_sektor && bvps ? p.pbv_sektor * bvps : null,
    mean_per: p.mean_per_3y ?? null,
    mean_pbv: p.mean_pbv_3y ?? null,
    fair_value_per: fvPer,
    fair_value_pbv: fvPbv,
    fair_value: fairValue,
    mos_fair_value: mosFair,
  };
}

function absoluteValuation(emiten) {
  const lap = laporanTerbaru(emiten);
  const p = emiten.pasar;
  const fcf0 = fcf(lap);
  const g = p.growth_rate ?? 0.08;
  const r = p.discount_rate ?? 0.11;
  const gt = p.terminal_growth ?? 0.03;
  const n = p.tahun_proyeksi ?? 5;

  const fcfProyeksi = [];
  const pvFcf = [];
  let f = fcf0;
  for (let t = 1; t <= n; t++) {
    f = f * (1 + g);
    fcfProyeksi.push(f);
    pvFcf.push(f / Math.pow(1 + r, t));
  }
  const terminalValue = r > gt
    ? (fcfProyeksi.at(-1) * (1 + gt)) / (r - gt)
    : fcfProyeksi.at(-1) * 10;
  const pvTerminal = terminalValue / Math.pow(1 + r, n);
  const enterpriseValue = pvFcf.reduce((a, b) => a + b, 0) + pvTerminal;
  const nilaiIntrinsik = bagi(enterpriseValue, p.saham_beredar);

  return {
    fcf_dasar: fcf0, growth_rate: g, discount_rate: r, terminal_growth: gt,
    tahun_proyeksi: n, fcf_proyeksi: fcfProyeksi, pv_fcf: pvFcf,
    terminal_value: terminalValue, pv_terminal: pvTerminal,
    enterprise_value: enterpriseValue, nilai_intrinsik_per_saham: nilaiIntrinsik,
  };
}

// Proyeksi tahun mendatang berbasis CAGR (port dari draftnest/forecast.py).
export function proyeksiTahunDepan(emiten, nTahun = 3) {
  const lap = [...emiten.laporan].sort((a, b) => a.tahun - b.tahun);
  if (lap.length < 2) return { cagr_pendapatan: null, cagr_laba: null, proyeksi: [] };
  const periode = lap.at(-1).tahun - lap[0].tahun;
  const gPend = cagr(lap[0].pendapatan, lap.at(-1).pendapatan, periode);
  const gLaba = cagr(lap[0].laba_bersih, lap.at(-1).laba_bersih, periode);
  const t = lap.at(-1);
  let pend = t.pendapatan, laba = t.laba_bersih;
  const proyeksi = [];
  for (let i = 1; i <= nTahun; i++) {
    if (gPend != null) pend *= 1 + gPend;
    if (gLaba != null) laba *= 1 + gLaba;
    proyeksi.push({
      tahun: t.tahun + i, pendapatan: pend, laba_bersih: laba,
      net_margin: pend ? laba / pend : null,
    });
  }
  return { cagr_pendapatan: gPend, cagr_laba: gLaba, proyeksi };
}

export function analisisValuasi(emiten) {
  if (!emiten.pasar) return null;
  const rel = relativeValuation(emiten);
  const abs = absoluteValuation(emiten);
  let mos = null;
  if (abs.nilai_intrinsik_per_saham) {
    mos = (abs.nilai_intrinsik_per_saham - emiten.pasar.harga_saham) / abs.nilai_intrinsik_per_saham;
  }
  return {
    harga_saham: emiten.pasar.harga_saham,
    relative: rel,
    absolute: abs,
    margin_of_safety: mos,
  };
}
