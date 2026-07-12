// idx-price.js — ambil harga saham IDX real-time dari browser (best-effort).
//
// Halaman statis tak bisa mengakses idx.co.id langsung (CORS + proteksi bot),
// jadi kita pakai Yahoo Finance (ticker "<KODE>.JK") lewat CORS-proxy publik.
// Ini best-effort: bila semua proxy gagal, isi harga manual.

const PROXIES = [
  (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
  (u) => `https://corsproxy.io/?url=${encodeURIComponent(u)}`,
  (u) => `https://thingproxy.freeboard.io/fetch/${u}`,
];

function yahooUrl(kode) {
  const tkr = `${kode.toUpperCase()}.JK`;
  return `https://query1.finance.yahoo.com/v8/finance/chart/${tkr}?interval=1d&range=1d`;
}

/**
 * Ambil harga penutupan terakhir untuk kode emiten IDX.
 * @returns {Promise<{harga:number, mata_uang:string, sumber:string}>}
 */
export async function ambilHargaIDX(kode) {
  if (!kode) throw new Error("Isi kode emiten dulu.");
  const target = yahooUrl(kode);
  let lastErr = null;

  for (const proxy of PROXIES) {
    try {
      const resp = await fetch(proxy(target), { headers: { accept: "application/json" } });
      if (!resp.ok) { lastErr = new Error(`proxy HTTP ${resp.status}`); continue; }
      const teks = await resp.text();
      const data = JSON.parse(teks);
      const meta = data?.chart?.result?.[0]?.meta;
      const harga = meta?.regularMarketPrice;
      if (harga == null) { lastErr = new Error("harga tidak ada di respons"); continue; }
      return {
        harga: Number(harga),
        mata_uang: meta.currency || "IDR",
        sumber: "Yahoo Finance (.JK)",
      };
    } catch (e) {
      lastErr = e; // coba proxy berikutnya
    }
  }
  throw new Error(
    `Gagal ambil harga ${kode.toUpperCase()} (${lastErr?.message || "semua proxy gagal"}). ` +
    "Isi harga manual atau coba lagi."
  );
}
