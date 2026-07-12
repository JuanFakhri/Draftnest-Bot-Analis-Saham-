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
  return {
    eps, bvps, per, pbv,
    per_sektor: p.per_sektor ?? null,
    pbv_sektor: p.pbv_sektor ?? null,
    harga_wajar_per: p.per_sektor && eps ? p.per_sektor * eps : null,
    harga_wajar_pbv: p.pbv_sektor && bvps ? p.pbv_sektor * bvps : null,
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
