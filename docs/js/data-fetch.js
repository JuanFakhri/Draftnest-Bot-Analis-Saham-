// data-fetch.js — auto-isi data emiten dari kode.
//
// Dua sumber:
// 1. Pra-ambil (pipeline GitHub Actions): docs/data/<kode>.json — instan & andal.
// 2. Fallback live: Financial Modeling Prep (FMP) memakai API key gratis pengguna
//    untuk emiten di luar watchlist. Kuota harian terbatas; cakupan IDX bervariasi.

const FMP = "https://financialmodelingprep.com/api/v3";

/** Coba muat data pra-ambil dari repo. Kembalikan objek emiten atau null. */
export async function muatPraAmbil(kode) {
  try {
    const resp = await fetch(`data/${kode.toLowerCase()}.json`, { cache: "no-cache" });
    if (!resp.ok) return null;
    return await resp.json();
  } catch (_) {
    return null;
  }
}

function num(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

/** Ambil data live dari FMP (butuh apiKey). Kembalikan objek emiten. */
export async function fetchFMP(kode, apiKey) {
  if (!apiKey) throw new Error("API key FMP belum diisi (⚙️ Pengaturan).");
  const t = `${kode.toUpperCase()}.JK`;
  const q = `apikey=${encodeURIComponent(apiKey)}`;
  const url = (path) => `${FMP}/${path}/${t}?${path === "profile" ? "" : "period=annual&limit=5&"}${q}`;

  const [profRes, incRes, balRes, cfRes] = await Promise.all([
    fetch(url("profile")), fetch(url("income-statement")),
    fetch(url("balance-sheet-statement")), fetch(url("cash-flow-statement")),
  ]);
  for (const r of [profRes, incRes, balRes, cfRes]) {
    if (!r.ok) {
      if (r.status === 401 || r.status === 403)
        throw new Error("API key FMP tidak valid / tidak berhak (cek key & paket).");
      throw new Error(`FMP error HTTP ${r.status}.`);
    }
  }
  const [profArr, inc, bal, cf] = await Promise.all([
    profRes.json(), incRes.json(), balRes.json(), cfRes.json(),
  ]);
  const prof = Array.isArray(profArr) ? profArr[0] : null;
  if ((!inc || !inc.length) && !prof) throw new Error(`FMP tak punya data untuk ${t}.`);

  const byYear = (arr) => Object.fromEntries((arr || []).map((x) => [x.calendarYear, x]));
  const I = byYear(inc), B = byYear(bal), C = byYear(cf);
  const years = [...new Set([...Object.keys(I), ...Object.keys(B), ...Object.keys(C)])]
    .map(Number).filter(Boolean).sort((a, b) => a - b);

  const laporan = years.map((y) => {
    const i = I[y] || {}, b = B[y] || {}, c = C[y] || {};
    return {
      tahun: y,
      total_aset: num(b.totalAssets), aset_lancar: num(b.totalCurrentAssets),
      total_liabilitas: num(b.totalLiabilities), liabilitas_lancar: num(b.totalCurrentLiabilities),
      total_ekuitas: num(b.totalStockholdersEquity),
      pendapatan: num(i.revenue), laba_kotor: num(i.grossProfit),
      laba_operasi: num(i.operatingIncome), laba_bersih: num(i.netIncome),
      arus_kas_operasi: num(c.netCashProvidedByOperatingActivities),
      arus_kas_investasi: num(c.netCashUsedForInvestingActivites),
      arus_kas_pendanaan: num(c.netCashUsedProvidedByFinancingActivities),
      free_cash_flow: c.freeCashFlow != null ? num(c.freeCashFlow) : null,
    };
  });

  let pasar = null;
  if (prof && prof.price) {
    // Saham beredar ~ market cap / harga (FMP profil tak selalu punya field shares).
    const saham = prof.mktCap && prof.price ? prof.mktCap / prof.price : null;
    if (saham) pasar = { harga_saham: num(prof.price), saham_beredar: saham,
      growth_rate: 0.08, discount_rate: 0.11, terminal_growth: 0.03, tahun_proyeksi: 5 };
  }

  return {
    profil: {
      kode: kode.toUpperCase(),
      nama: prof?.companyName || kode.toUpperCase(),
      sektor: prof?.sector || "", sub_sektor: prof?.industry || "",
      deskripsi_bisnis: prof?.description || "",
      manajemen: "", keunggulan_kompetitif: "", prospek_industri: "", berita_terkini: "",
    },
    laporan, pasar,
  };
}
