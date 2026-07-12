# Draftnest — Bot Analisis Saham IDX

Bot analisis fundamental saham Bursa Efek Indonesia (IDX) berbasis **3 pilar**,
memakai [Claude API](https://www.anthropic.com/) (model `claude-opus-4-8`) untuk
menilai dan menyimpulkan.

| Pilar | Isi (sesuai desain) |
|---|---|
| 🧠 **Analisis Kualitatif** | Model Bisnis · Manajemen · Keunggulan Kompetitif · Prospek Industri |
| 📊 **Analisis Kuantitatif** | Laporan Neraca · Laba Rugi · Arus Kas → **Data Olahannya** (ROE, ROA, DER, Current Ratio, growth) |
| 💰 **Analisis Valuasi** | **Relative** (PER, PBV vs sektor) · **Absolute** (DCF sederhana) |

Setiap pilar diberi skor 1–10 + justifikasi, lalu digabung menjadi satu laporan
dengan **skor akhir** dan **rekomendasi** (Beli / Tahan / Jual).

Tersedia dalam **dua bentuk**:
- 🌐 **Website** (`docs/`) — SPA statis di GitHub Pages, analisis real-time di browser
  (UI elegan, mode siang/malam, form input, impor/ekspor JSON, unduh laporan).
- 🖥️ **CLI Python** (`draftnest/`) — untuk otomasi, plus **scraper IDX** (profil,
  harga, parser XBRL laporan keuangan).

---

## 🌐 Website (GitHub Pages)

Situs statis di folder [`docs/`](docs/). Berjalan penuh di browser:
matematika keuangan dihitung di JavaScript, dan interpretasi 3 pilar memanggil
**Claude API langsung dari browser** memakai API key milik Anda sendiri
(disimpan hanya di `localStorage`, tidak ada server perantara).

**Fitur:**
- Mode **siang & malam** (elegan, responsif)
- Form input ramah + kartu laporan per tahun (Neraca / Laba Rugi / Arus Kas)
- **Muat Contoh**, **Impor JSON**, **Ekspor JSON**
- **Hitung Rasio & Valuasi** (offline, tanpa API key) — instan
- **Analisis Lengkap dengan AI** (3 pilar via Claude)
- Kartu skor per pilar, tabel rasio, rincian DCF, badge rekomendasi
- **Unduh laporan .md** & cetak

**Aktifkan Pages:** Settings → Pages → Source: **GitHub Actions**. Workflow
[`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)
menerbitkan `docs/` otomatis setiap push ke `main`. Coba lokal:

```bash
cd docs && python -m http.server 8000   # buka http://localhost:8000
```

---

## Pengambilan Data Otomatis dari IDX

Modul [`draftnest/idx_scraper.py`](draftnest/idx_scraper.py):

- **Profil & harga** — endpoint JSON IDX (best-effort; IDX memakai proteksi bot
  sehingga bisa terblokir/rate-limit).
- **Laporan keuangan** — **parser XBRL** (paling andal). Unduh file
  `instance.xbrl` laporan keuangan dari idx.co.id, lalu parse offline.

```bash
# Rakit data emiten dari IDX (profil/harga) + XBRL, simpan ke JSON, lalu analisis
python -m draftnest --fetch ICBP --xbrl 2023.xbrl --xbrl 2024.xbrl \
  --save-json data/ICBP.json

# Hanya XBRL (lewati harga IDX), tentukan tahun manual
python -m draftnest --fetch ICBP --xbrl instance.xbrl --year 2024 --no-market --offline
```

Parser XBRL memetakan konsep taksonomi IDX/IFRS (`Assets`, `Equity`,
`SalesAndRevenue`, `ProfitLoss`, `NetCashFlowsReceivedFromUsedInOperatingActivities`,
dst.) ke field laporan. Bagian yang gagal diambil dibiarkan kosong untuk
dilengkapi manual.

---

## Alur Bot

```
1. User input kode saham (file JSON emiten)
2. Muat & validasi data (Neraca, Laba Rugi, Arus Kas, harga, pembanding)
3. Olah data keuangan  -> rasio & valuasi (deterministik, di Python)
4. Kirim ke Claude API dengan 3 prompt terpisah (kualitatif, kuantitatif, valuasi)
5. Gabungkan output -> laporan skor + kesimpulan rekomendasi (Markdown)
```

Matematika keuangan (rasio, PER/PBV, DCF) dihitung **deterministik di Python**,
bukan diserahkan ke LLM. Claude bertugas **menginterpretasi & memberi skor** atas
angka-angka tersebut — sehingga hasil konsisten dan bisa diaudit.

## Instalasi

```bash
pip install -r requirements.txt
cp .env.example .env      # lalu isi ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY=sk-ant-...   # atau muat dari .env
```

## Pemakaian

```bash
# Analisis penuh (3 pilar + LLM)
python -m draftnest data/ICBP.json

# Simpan ke file
python -m draftnest data/ICBP.json --output laporan_ICBP.md

# Tanpa panggilan LLM — hanya olah rasio & valuasi (tidak butuh API key)
python -m draftnest data/ICBP.json --offline
```

Contoh output (mode offline, data ilustratif ICBP):

```
## 2. Analisis Kuantitatif
| Tahun | ROE | ROA | DER | Current Ratio | Net Margin |
| 2024 | 13.0% | 7.1% | 0.83x | 2.09x | 12.8% |
...
### Relative Valuation
- PER: 14.57x (sektor 15.00x) · PBV: 1.89x (sektor 3.00x)
### Absolute Valuation (DCF)
- Nilai intrinsik: Rp8,828 per lembar · Margin of safety: -30.3%
```

## Format Data Emiten

Satu file JSON per emiten (lihat [`data/ICBP.json`](data/ICBP.json) sebagai
templat). Angka keuangan memakai satuan konsisten (mis. **miliar Rupiah**),
`saham_beredar` dalam satuan lembar yang konsisten (mis. **miliar lembar**).

```jsonc
{
  "profil": {
    "kode": "ICBP", "nama": "...", "sektor": "...",
    "deskripsi_bisnis": "...", "manajemen": "...",
    "keunggulan_kompetitif": "...", "prospek_industri": "...",
    "berita_terkini": "..."
  },
  "laporan": [
    { "tahun": 2024,
      "total_aset": 130000, "aset_lancar": 46000,
      "total_liabilitas": 59000, "liabilitas_lancar": 22000, "total_ekuitas": 71000,
      "pendapatan": 72000, "laba_kotor": 26000, "laba_operasi": 15500, "laba_bersih": 9200,
      "arus_kas_operasi": 12500, "arus_kas_investasi": -6000, "arus_kas_pendanaan": -3500 }
  ],
  "pasar": {
    "harga_saham": 11500, "saham_beredar": 11.66,
    "per_sektor": 15.0, "pbv_sektor": 3.0,
    "growth_rate": 0.08, "discount_rate": 0.11, "terminal_growth": 0.03, "tahun_proyeksi": 5
  }
}
```

Sertakan minimal 2–3 tahun `laporan` agar CAGR pertumbuhan bisa dihitung.

## Sumber Data untuk Indonesia

Data untuk mengisi JSON bisa diambil dari:

- **IDX** (idx.co.id) — laporan keuangan resmi
- **RTI Business / Stockbit / Sahamidx** — rasio & harga real-time
- **laporankeuangan.web.id** — arsip laporan keuangan
- API sekuritas bila tersedia

Ingin otomatisasi? Tulis modul _fetch/scraping_ tersendiri yang menghasilkan
objek `Emiten` (lihat `draftnest/models.py`), lalu teruskan ke
`draftnest.report.jalankan_analisis`. `data_loader.py` adalah contoh "port" data
dari JSON.

## Struktur Proyek

```
draftnest/
  models.py        # dataclass input (profil, laporan, data pasar)
  data_loader.py   # muat emiten dari JSON
  idx_scraper.py   # ambil data IDX (profil/harga) + parser XBRL laporan keuangan
  ratios.py        # Pilar 2: hitung rasio (data olahan) — deterministik
  valuation.py     # Pilar 3: PER/PBV (relative) + DCF (absolute) — deterministik
  client.py        # pembungkus Anthropic Claude API (structured output)
  analyzers/
    kualitatif.py  # Pilar 1: prompt 4 poin kualitatif
    kuantitatif.py # Pilar 2: prompt interpretasi rasio
    valuasi.py     # Pilar 3: prompt interpretasi valuasi
  report.py        # gabung 3 pilar -> skor akhir + rekomendasi
  formatter.py     # render laporan Markdown
  cli.py           # antarmuka baris perintah
data/ICBP.json     # contoh emiten (ilustratif)
docs/              # website statis (GitHub Pages)
  index.html
  css/styles.css   # tema elegan + mode siang/malam
  js/finance.js    # port matematika keuangan ke browser
  js/claude.js     # panggilan Claude API dari browser (3 pilar)
  js/app.js        # logika UI
.github/workflows/deploy-pages.yml   # deploy otomatis ke Pages
```

## Sebagai Library

```python
from draftnest.data_loader import muat_emiten
from draftnest.client import ClaudeClient
from draftnest.report import jalankan_analisis
from draftnest.formatter import format_markdown

emiten = muat_emiten("data/ICBP.json")
hasil = jalankan_analisis(emiten, ClaudeClient())   # atau None untuk offline
print(format_markdown(hasil))
print(hasil.skor_akhir, hasil.rekomendasi)
```

## Catatan

- **Bukan rekomendasi investasi.** Output untuk edukasi/riset. Selalu DYOR.
- Data contoh ICBP bersifat **ilustratif** — ganti dengan data resmi sebelum dipakai.
- Hasil DCF sangat **sensitif terhadap asumsi** (growth, discount, terminal).
