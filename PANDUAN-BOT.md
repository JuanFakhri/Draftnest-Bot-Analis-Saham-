# Panduan Menjalankan Bot Telegram Draftnest di VPS Windows

Langkah demi langkah dari nol sampai bot jalan 24 jam + scan BSJP otomatis 15:20 WIB.

> Ringkasnya: install Python → **git clone** kode → install dependensi → buat
> bot di @BotFather → set token → jalankan → (opsional) pasang sebagai service
> biar jalan terus. Data saham ter-update sendiri dari GitHub (butuh git clone).

---

## 1. Masuk ke VPS Windows

Buka **Remote Desktop Connection** (bawaan Windows: tekan `Win`, ketik "Remote
Desktop"), masukkan **IP VPS**, **username**, **password** dari penyedia VPS Anda.

---

## 2. Install Python

1. Buka browser di VPS → https://www.python.org/downloads/windows/
2. Unduh **Python 3.12** (Windows installer 64-bit).
3. Jalankan installer → **CENTANG "Add python.exe to PATH"** (penting!) → klik
   **Install Now**.
4. Verifikasi: buka **PowerShell** (tekan `Win`, ketik "PowerShell", Enter) lalu:

   ```powershell
   python --version
   ```
   Harus muncul `Python 3.12.x`.

---

## 3. Ambil kode Draftnest (pakai Git — disarankan)

> **Penting:** ambil kode dengan **`git clone`**, bukan ZIP. Bot mengambil data
> saham terbaru otomatis lewat `git` (lihat langkah 10), dan itu **hanya jalan
> kalau folder ini adalah clone git**. ZIP tidak bisa auto-update.

```powershell
winget install --id Git.Git -e --source winget
# Tutup lalu buka lagi PowerShell agar `git` terbaca, lalu:
cd C:\
git clone https://github.com/JuanFakhri/Draftnest-Bot-Analis-Saham-.git draftnest
```

Sesudah clone, pastikan file `requirements-bot.txt` ada di `C:\draftnest\`.

**Alternatif tanpa Git (ZIP):** buka repo di GitHub → tombol hijau **Code** →
**Download ZIP** → ekstrak ke `C:\draftnest`. Cara ini jalan, tapi **data tidak
ter-update otomatis** — Anda harus unduh ZIP baru tiap kali ingin data segar.

---

## 4. Install dependensi

Di PowerShell, masuk ke folder proyek lalu install:

```powershell
cd C:\draftnest
python -m pip install --upgrade pip
python -m pip install -r requirements-bot.txt      # untuk analisis
python -m pip install -r requirements-data.txt     # + yfinance (untuk /scan realtime)
python -m pip install tzdata                        # zona waktu Asia/Jakarta di Windows
```

---

## 5. Buat bot Telegram & ambil TOKEN

1. Di HP/PC, buka Telegram → cari **@BotFather** → mulai chat.
2. Kirim `/newbot`.
3. Beri **nama** bot (bebas, mis. `Draftnest Saham`).
4. Beri **username** bot, harus diakhiri `bot` (mis. `draftnest_saham_bot`).
5. BotFather membalas dengan **TOKEN**, bentuknya seperti:
   `123456789:AAE...panjang...xyz`
6. **Salin token itu.** (Jangan dibagikan ke siapa pun.)

---

## 6. Set token & jam scan (variabel lingkungan)

Di PowerShell di VPS, jalankan (ganti token dengan milik Anda):

```powershell
setx TELEGRAM_BOT_TOKEN "123456789:AAE...token-anda...xyz"
setx DRAFTNEST_SCAN_TIME "15:20"
```

> `setx` menyimpan permanen. **Tutup lalu buka lagi** jendela PowerShell agar
> nilainya terbaca (setx tidak berlaku di jendela yang sedang terbuka).

---

## 7. Jalankan bot (uji dulu)

```powershell
cd C:\draftnest
python -m draftnest.telegram_bot
```

Kalau berhasil muncul:

```
✅ Bot @draftnest_saham_bot jalan. Scan otomatis 15:20 WIB (Sen–Jum). Ctrl+C untuk berhenti.
[jadwal] scan berikutnya: 2026-07-21 15:20 WIB (...jam lagi)
```

Biarkan jendela ini terbuka selama menguji.

---

## 8. Uji dari Telegram

Buka Telegram → cari **username bot** Anda → mulai chat → coba:

| Ketik | Hasil |
|---|---|
| `/start` | Sapaan + daftar perintah |
| `BBCA` | Analisis cepat (skor + rekomendasi) |
| `/analisis ICBP` | Skor 3 pilar + nilai wajar + target harga |
| `/screener` | Saham tumbuh + dividen + prospek |
| `/dividen` | Dividend yield tertinggi |
| `/bsjp` | Sinyal + win rate backtest |
| **`/scan`** | **Pindai sinyal BSJP realtime sekarang** (agak lama, ambil harga live) |
| **`/update`** | **Ambil data saham terbaru dari GitHub sekarang** |
| **`/langganan`** | Daftar untuk terima scan otomatis 15:20 WIB |
| `/cari bank` | Cari kode emiten |

Kalau semua membalas → bot **sudah jadi**. 🎉

Untuk berhenti sementara: kembali ke PowerShell, tekan `Ctrl + C`.

---

## 9. Jalan 24 jam (auto-start + auto-restart)

Kalau hanya dijalankan lewat PowerShell, bot **mati saat Anda logout RDP atau
VPS restart**. Agar jalan terus, pasang sebagai **service** memakai **NSSM**.

1. Unduh **NSSM**: https://nssm.cc/download → ekstrak, ambil
   `win64\nssm.exe`, taruh di `C:\draftnest\nssm.exe`.
2. Cari path Python: di PowerShell ketik `where.exe python` → catat, mis.
   `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`.
3. Install service (jalankan PowerShell **sebagai Administrator**):

   ```powershell
   cd C:\draftnest
   .\nssm.exe install DraftnestBot "C:\...\python.exe" "-m draftnest.telegram_bot"
   .\nssm.exe set DraftnestBot AppDirectory "C:\draftnest"
   .\nssm.exe set DraftnestBot AppEnvironmentExtra TELEGRAM_BOT_TOKEN=123456789:AAE...token... DRAFTNEST_SCAN_TIME=15:20
   .\nssm.exe start DraftnestBot
   ```

4. Cek status: `.\nssm.exe status DraftnestBot` (harus `SERVICE_RUNNING`).

Sekarang bot **jalan otomatis** saat VPS menyala, restart sendiri kalau crash,
dan **tetap hidup meski Anda logout RDP**.

Perintah berguna:
```powershell
.\nssm.exe restart DraftnestBot     # restart (mis. setelah update kode)
.\nssm.exe stop DraftnestBot        # hentikan
.\nssm.exe remove DraftnestBot confirm   # hapus service
```

---

## 10. Data ter-update otomatis dari GitHub

Pipeline harian Draftnest menulis data saham terbaru ke GitHub. Bot di VPS
**menariknya sendiri lewat `git`** — Anda tidak perlu `git pull` manual:

- **Saat bot mulai** → langsung ambil data terbaru.
- **Setiap 60 menit** → ambil ulang data terbaru (hanya folder `docs/data`,
  kode & daftar pelanggan tidak tersentuh).
- **Menjelang scan sore** → ambil data terbaru dulu sebelum kirim ke pelanggan.
- Kapan saja bisa paksa lewat perintah **`/update`** di Telegram.

Atur selang auto-update (menit) lewat variabel `DRAFTNEST_GIT_SYNC_MIN`
(default `60`, isi `0` untuk mematikan):

```powershell
setx DRAFTNEST_GIT_SYNC_MIN "60"
```

> Syarat: kode diambil via **`git clone`** (langkah 3), bukan ZIP. Kalau dari
> ZIP, perintah `/update` akan memberi tahu bahwa folder bukan clone git.

---

## 11. Scan otomatis 15:20 WIB

- Kirim **`/langganan`** ke bot dari akun Telegram Anda (boleh beberapa orang).
- Tiap hari kerja **15:20 WIB**, bot otomatis: ambil data terbaru dari GitHub →
  ambil harga live semua emiten → hitung sinyal BSJP → **kirim hasilnya** ke
  semua pelanggan.
- Mau ganti jam? ubah `DRAFTNEST_SCAN_TIME` (mis. `15:30`) lalu restart service.
- `/berhenti` untuk stop langganan.

---

## 12. Update kode nanti

**Data saham** ter-update sendiri (langkah 10). Bagian ini untuk update **kode
program** (perbaikan/fitur baru):

```powershell
cd C:\draftnest
git pull                      # kalau pakai Git (atau unduh ZIP terbaru)
python -m pip install -r requirements-bot.txt
.\nssm.exe restart DraftnestBot
```

---

## Masalah umum

| Gejala | Solusi |
|---|---|
| `python : tidak dikenal` | Python belum masuk PATH → install ulang, centang "Add to PATH", buka PowerShell baru |
| `Set dulu TELEGRAM_BOT_TOKEN` | Token belum ke-set / PowerShell belum dibuka ulang setelah `setx` |
| `/scan` error / kosong | Butuh `yfinance` (`requirements-data.txt`); di luar jam bursa hasil bisa ditolak circuit-breaker (wajar) |
| Jam scan meleset | Install `tzdata` (`python -m pip install tzdata`) |
| `/update`: "bukan clone git" | Kode diambil dari ZIP → ambil ulang via `git clone` (langkah 3) agar bisa auto-update data |
| Data tidak ter-update | Pastikan `git` terpasang & folder hasil `git clone`; cek log bot ada baris `[git-sync]` |
| Bot mati saat logout RDP | Pasang sebagai service dengan NSSM (langkah 9) |

---

⚠️ **Disclaimer:** Semua analisis & sinyal untuk edukasi/riset, **bukan**
rekomendasi jual/beli. BSJP menahan saham semalam — berisiko *gap-down*. Hasil
backtest historis, **bukan jaminan**. DYOR (do your own research).
