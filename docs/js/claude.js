// claude.js — panggilan langsung ke Claude API dari browser.
// Memakai header 'anthropic-dangerous-direct-browser-access' (didukung resmi).
// API key milik pengguna, disimpan hanya di localStorage browser mereka.

const API_URL = "https://api.anthropic.com/v1/messages";
export const DEFAULT_MODEL = "claude-opus-4-8";

function poinSkor(deskripsi) {
  return {
    type: "object",
    properties: {
      skor: { type: "integer", description: `Skor 1-10 untuk ${deskripsi}` },
      justifikasi: { type: "string", description: `Justifikasi singkat untuk ${deskripsi}` },
    },
    required: ["skor", "justifikasi"],
    additionalProperties: false,
  };
}

function skemaPilar(poin, extra) {
  const props = {};
  const required = [];
  for (const [k, v] of Object.entries(poin)) {
    props[k] = poinSkor(v);
    required.push(k);
  }
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      props[k] = v;
      required.push(k);
    }
  }
  return { type: "object", properties: props, required, additionalProperties: false };
}

async function panggilClaude(apiKey, model, system, prompt, schema) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model,
      max_tokens: 8000,
      thinking: { type: "adaptive" },
      system,
      output_config: { format: { type: "json_schema", schema } },
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!resp.ok) {
    let detail = "";
    try { detail = (await resp.json())?.error?.message || ""; } catch (_) { /* noop */ }
    if (resp.status === 401) throw new Error("API key tidak valid (401). Periksa key Anda.");
    if (resp.status === 429) throw new Error("Rate limit (429). Coba lagi sebentar.");
    throw new Error(`Claude API error ${resp.status}. ${detail}`);
  }

  const data = await resp.json();
  const teks = (data.content || []).find((b) => b.type === "text")?.text || "";
  return JSON.parse(teks);
}

// ---- Pilar 1: Kualitatif ----
const SYS_KUAL =
  "Anda analis fundamental saham Bursa Efek Indonesia (IDX) yang objektif, kritis, " +
  "dan berbasis bukti. Beri skor jujur; hindari optimisme berlebihan. Jawab dalam Bahasa Indonesia.";

const SKEMA_KUAL = skemaPilar(
  {
    model_bisnis: "kualitas & daya tahan model bisnis",
    manajemen: "kompetensi & rekam jejak manajemen",
    keunggulan_kompetitif: "moat / keunggulan kompetitif & pangsa pasar",
    prospek_industri: "prospek pertumbuhan industri/sektor",
  },
  { ringkasan: { type: "string", description: "Ringkasan naratif 2-4 kalimat." } }
);

export function analisisKualitatif(apiKey, model, emiten) {
  const p = emiten.profil;
  const prompt =
`Analisis kualitatif emiten berikut berdasarkan 4 poin.

Emiten : ${p.nama} (${p.kode})
Sektor : ${p.sektor} ${p.sub_sektor ? "- " + p.sub_sektor : ""}

1. Model Bisnis:
${p.deskripsi_bisnis || "(tidak ada data — nilai konservatif dan sebutkan keterbatasan data)"}

2. Manajemen:
${p.manajemen || "(tidak ada data)"}

3. Keunggulan Kompetitif:
${p.keunggulan_kompetitif || "(tidak ada data)"}

4. Prospek Industri:
${p.prospek_industri || "(tidak ada data)"}

Berita terkini:
${p.berita_terkini || "(tidak ada data)"}

Untuk tiap poin beri skor 1-10 (10 terbaik) dan justifikasi singkat.
Bila data tidak memadai, beri skor konservatif dan nyatakan keterbatasannya.`;
  return panggilClaude(apiKey, model, SYS_KUAL, prompt, SKEMA_KUAL);
}

// ---- Pilar 2: Kuantitatif ----
const SYS_KUANT =
  "Anda analis keuangan kuantitatif untuk saham IDX. Interpretasikan rasio keuangan " +
  "secara ketat dan berbasis angka. Jawab dalam Bahasa Indonesia.";

const SKEMA_KUANT = skemaPilar(
  {
    profitabilitas: "profitabilitas (ROE, ROA, margin)",
    solvabilitas: "solvabilitas/leverage (DER)",
    likuiditas: "likuiditas (Current Ratio)",
    pertumbuhan: "pertumbuhan pendapatan & laba",
  },
  { ringkasan: { type: "string", description: "Ringkasan naratif 2-4 kalimat." } }
);

const pct = (x) => (x != null ? (x * 100).toFixed(1) + "%" : "n/a");
const numx = (x) => (x != null ? x.toFixed(2) + "x" : "n/a");

export function analisisKuantitatifLLM(apiKey, model, kode, ringkasan) {
  const historis = ringkasan.rasio_historis
    .map((r) =>
      `  ${r.tahun}: ROE ${pct(r.roe)}, ROA ${pct(r.roa)}, DER ${numx(r.der)}, ` +
      `CR ${numx(r.current_ratio)}, NPM ${pct(r.net_profit_margin)}, ` +
      `GPM ${pct(r.gross_profit_margin)}, OPM ${pct(r.operating_margin)}`)
    .join("\n");
  const prompt =
`Interpretasikan rasio keuangan emiten ${kode} berikut (olahan dari Neraca, Laba Rugi,
dan Arus Kas). Tahun data: ${ringkasan.tahun_data.join(", ")}.

Rasio historis:
${historis}

Pertumbuhan (CAGR):
  Pendapatan : ${pct(ringkasan.growth_pendapatan)}
  Laba bersih: ${pct(ringkasan.growth_laba_bersih)}

Beri skor 1-10 (10 terbaik) + justifikasi untuk tiap dimensi: profitabilitas,
solvabilitas, likuiditas, dan pertumbuhan. Kaitkan skor dengan angka konkret.`;
  return panggilClaude(apiKey, model, SYS_KUANT, prompt, SKEMA_KUANT);
}

// ---- Pilar 3: Valuasi ----
const SYS_VAL =
  "Anda analis valuasi saham IDX. Nilai kewajaran harga berdasarkan valuasi relatif " +
  "(PER/PBV vs sektor) dan valuasi absolut (DCF). Bersikap konservatif dan sadar " +
  "keterbatasan asumsi. Jawab dalam Bahasa Indonesia.";

const SKEMA_VAL = skemaPilar(
  {
    relative_valuation: "kewajaran harga via PER/PBV dibanding sektor",
    absolute_valuation: "kewajaran harga via DCF (nilai intrinsik)",
  },
  {
    status: {
      type: "string",
      enum: ["undervalued", "fairvalued", "overvalued"],
      description: "Kesimpulan status harga terhadap nilai wajar.",
    },
    kesimpulan_valuasi: { type: "string", description: "Ringkasan 2-4 kalimat." },
    outlook_tahun_depan: {
      type: "string",
      description: "Outlook 2-4 kalimat untuk tahun mendatang berdasar proyeksi tren + risiko utamanya.",
    },
  }
);

function teksProyeksi(proyeksi) {
  if (!proyeksi || !proyeksi.proyeksi.length) return "(proyeksi tak tersedia)";
  const baris = proyeksi.proyeksi.map((p) =>
    `  ${p.tahun}: pendapatan ~${Math.round(p.pendapatan).toLocaleString("id-ID")}, ` +
    `laba bersih ~${Math.round(p.laba_bersih).toLocaleString("id-ID")}` +
    (p.net_margin != null ? `, margin ~${(p.net_margin * 100).toFixed(1)}%` : "")).join("\n");
  return `CAGR pendapatan ${pct(proyeksi.cagr_pendapatan)}, CAGR laba ${pct(proyeksi.cagr_laba)}\n${baris}`;
}

const rp = (x) => (x != null ? "Rp" + Math.round(x).toLocaleString("id-ID") : "n/a");

export function analisisValuasiLLM(apiKey, model, kode, v, proyeksi) {
  const r = v.relative;
  const a = v.absolute;
  const prompt =
`Nilai kewajaran harga saham ${kode}.
Harga pasar saat ini: ${rp(v.harga_saham)} per lembar.

== Relative Valuation ==
EPS : ${rp(r.eps)} | BVPS : ${rp(r.bvps)}
PER emiten : ${numx(r.per)} | PER sektor: ${numx(r.per_sektor)}
PBV emiten : ${numx(r.pbv)} | PBV sektor: ${numx(r.pbv_sektor)}
Harga wajar (PER sektor): ${rp(r.harga_wajar_per)} | (PBV sektor): ${rp(r.harga_wajar_pbv)}
Fair Value (Mean PER&PBV): Mean PER ${numx(r.mean_per)} x EPS -> ${rp(r.fair_value_per)}; Mean PBV ${numx(r.mean_pbv)} x BVPS -> ${rp(r.fair_value_pbv)}; Fair Value ${rp(r.fair_value)} (MoS ${pct(r.mos_fair_value)})

== Absolute Valuation (DCF) ==
FCF dasar : ${Math.round(a.fcf_dasar).toLocaleString("id-ID")}
Asumsi : growth ${pct(a.growth_rate)}, discount ${pct(a.discount_rate)}, terminal ${pct(a.terminal_growth)}, ${a.tahun_proyeksi} thn
Nilai intrinsik : ${rp(a.nilai_intrinsik_per_saham)} per lembar
Margin of safety : ${pct(v.margin_of_safety)} (positif = harga di bawah nilai intrinsik)

== Proyeksi Tahun Mendatang (ekstrapolasi CAGR) ==
${teksProyeksi(proyeksi)}

Beri skor 1-10 (10 = paling menarik/undervalued) + justifikasi untuk relative_valuation
dan absolute_valuation. Tentukan status: undervalued/fairvalued/overvalued. Isi
'outlook_tahun_depan' dengan pandangan ke depan berdasar proyeksi di atas plus risiko
utamanya. Ingatkan bila DCF/proyeksi sangat sensitif terhadap asumsi.`;
  return panggilClaude(apiKey, model, SYS_VAL, prompt, SKEMA_VAL);
}
