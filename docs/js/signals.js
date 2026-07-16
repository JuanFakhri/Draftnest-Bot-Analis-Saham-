// signals.js — cek sinyal strategi BSJP secara LIVE dari browser.
// Port indikator/strategi dari draftnest/backtest.py + ambil bar harian via CORS-proxy.
// Realtime best-effort: memakai bar hari ini (bisa masih terbentuk) dari Yahoo.

const PROXIES = [
  (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
  (u) => `https://corsproxy.io/?url=${encodeURIComponent(u)}`,
  (u) => `https://thingproxy.freeboard.io/fetch/${u}`,
];

function rsi(closes, period = 14) {
  const n = closes.length, out = new Array(n).fill(null);
  if (n < period + 1) return out;
  const gains = [], losses = [];
  for (let i = 1; i < n; i++) {
    const ch = closes[i] - closes[i - 1];
    gains.push(Math.max(ch, 0)); losses.push(Math.max(-ch, 0));
  }
  const rs = (ag, al) => (al === 0 ? 100 : 100 - 100 / (1 + ag / al));
  let ag = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
  let al = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out[period] = rs(ag, al);
  for (let i = period + 1; i < n; i++) {
    ag = (ag * (period - 1) + gains[i - 1]) / period;
    al = (al * (period - 1) + losses[i - 1]) / period;
    out[i] = rs(ag, al);
  }
  return out;
}

function sma(closes, period = 5) {
  const n = closes.length, out = new Array(n).fill(null);
  for (let i = period - 1; i < n; i++) {
    let s = 0; for (let j = i - period + 1; j <= i; j++) s += closes[j];
    out[i] = s / period;
  }
  return out;
}

// Evaluasi S1 & S2 pada indeks i (default: bar terakhir).
export function evalSinyal(opens, closes, vols, shares, i) {
  const n = closes.length;
  if (i == null) i = n - 1;
  if (i < 1) return { s1: false, s2: false };
  const rsis = rsi(closes, 14), sma5 = sma(closes, 5);
  const ret = closes[i - 1] > 0 ? (closes[i] - closes[i - 1]) / closes[i - 1] : null;
  const value = closes[i] * vols[i];
  const mcap = shares ? closes[i] * shares : null;

  const s1 = rsis[i] != null && rsis[i] >= 25 && rsis[i] <= 50 &&
    vols[i - 1] > 0 && vols[i] >= 2 * vols[i - 1] &&
    ret != null && ret >= -0.05 && ret <= 0.01 &&
    closes[i] >= 100 && (mcap == null || mcap >= 5e11) && value >= 1e9;

  const s2 = closes[i - 1] > 0 && closes[i] > 1.05 * closes[i - 1] &&
    sma5[i] != null && closes[i] >= sma5[i] &&
    vols[i - 1] > 0 && vols[i] < 1.2 * vols[i - 1] && value >= 5e9;

  return {
    s1, s2, ret, rsi: rsis[i], value, mcap,
    mcapDilewati: mcap == null,   // bila shares tak diketahui, syarat mcap S1 dilewati
  };
}

async function ambilBar(kode) {
  const tkr = `${kode.toUpperCase()}.JK`;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${tkr}?interval=1d&range=1y`;
  let lastErr = null;
  for (const proxy of PROXIES) {
    try {
      const resp = await fetch(proxy(url), { headers: { accept: "application/json" } });
      if (!resp.ok) { lastErr = new Error(`proxy HTTP ${resp.status}`); continue; }
      const data = JSON.parse(await resp.text());
      const res = data?.chart?.result?.[0];
      const q = res?.indicators?.quote?.[0];
      if (!q || !res?.timestamp) { lastErr = new Error("data bar kosong"); continue; }
      const ts = res.timestamp, o = q.open, c = q.close, v = q.volume;
      const opens = [], closes = [], vols = [], tanggal = [];
      for (let i = 0; i < ts.length; i++) {
        if (c[i] == null || o[i] == null) continue;
        opens.push(o[i]); closes.push(c[i]); vols.push(v[i] || 0);
        tanggal.push(new Date(ts[i] * 1000).toISOString().slice(0, 10));
      }
      return { opens, closes, vols, tanggal };
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error("gagal ambil bar harian");
}

// Cek sinyal LIVE satu emiten sekarang. `shares` opsional (utk syarat market cap S1).
export async function cekSinyalLive(kode, shares) {
  const bars = await ambilBar(kode);
  if (bars.closes.length < 16) throw new Error("data harga terlalu sedikit.");
  const ev = evalSinyal(bars.opens, bars.closes, bars.vols, shares);
  return {
    kode: kode.toUpperCase(),
    tanggal: bars.tanggal.at(-1),
    harga: bars.closes.at(-1),
    ...ev,
  };
}
