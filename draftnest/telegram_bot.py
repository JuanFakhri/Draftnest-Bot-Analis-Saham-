"""Bot Telegram Draftnest — analisis saham IDX lewat chat.

Memakai ulang seluruh mesin Draftnest (skor 3 pilar deterministik, screener,
dividen, BSJP) dan data pra-ambil di `docs/data/`. Ringan: hanya butuh
`requests` (long-polling ke Telegram Bot API), tanpa framework.

Perintah:
  /start, /help                 — bantuan
  /analisis <KODE>              — analisis lengkap 1 emiten (skor + rekomendasi)
  <KODE>                        — sama seperti /analisis (ketik kode saja)
  /screener                     — saham tumbuh + dividen + prospek bagus
  /dividen                      — saham dividend yield tertinggi
  /bsjp                         — sinyal Beli Sore Jual Pagi + win rate backtest
  /cari <kata>                  — cari kode emiten

Jalankan:
  export TELEGRAM_BOT_TOKEN="123456:ABC-..."   # dari @BotFather
  python -m draftnest.telegram_bot
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
API = "https://api.telegram.org/bot{token}/{method}"

# File status bot (daftar pelanggan) — di luar git.
SUBS_FILE = Path(os.environ.get("DRAFTNEST_STATE_DIR", str(ROOT))) / ".draftnest_subs.json"
# Jam scan otomatis harian (WIB), format "HH:MM". Default 15:20.
SCAN_JAM = os.environ.get("DRAFTNEST_SCAN_TIME", "15:20")
# Selang auto-ambil data dari GitHub (menit). 0 = matikan. Default 60.
GIT_SYNC_MENIT = int(os.environ.get("DRAFTNEST_GIT_SYNC_MIN", "60") or 60)


def _wib():
    """Timezone Asia/Jakarta (fallback ke offset +7 bila zoneinfo tak ada)."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Asia/Jakarta")
    except Exception:
        from datetime import timezone
        return timezone(timedelta(hours=7))


# ============================ Format helpers ================================

def _esc(s: Any) -> str:
    """Escape untuk HTML parse_mode Telegram."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "–"


def _rp(x: Optional[float]) -> str:
    return f"Rp{x:,.0f}" if x is not None else "–"


def _skor(x: Optional[float]) -> str:
    return f"{x:.1f}/10" if x is not None else "–"


def _emoji_rek(rek: str) -> str:
    r = (rek or "").upper()
    if r.startswith("BELI"):
        return "🟢"
    if r.startswith("JUAL"):
        return "🔴"
    return "🟡"


# ============================ Message builders ==============================
# Semua fungsi ini MURNI (input data -> string), mudah diuji tanpa jaringan.

def pesan_start() -> str:
    return (
        "👋 <b>Draftnest Bot</b> — analis saham IDX di Telegram.\n\n"
        "Ketik <b>kode emiten</b> (mis. <code>BBCA</code>) untuk analisis cepat, "
        "atau pakai perintah:\n" + _daftar_perintah()
    )


def _daftar_perintah() -> str:
    return (
        "• /analisis <code>KODE</code> — skor 3 pilar + rekomendasi\n"
        "• /screener — tumbuh tiap tahun + dividen + prospek\n"
        "• /dividen — dividend yield tertinggi\n"
        "• /bsjp — sinyal Beli Sore Jual Pagi + win rate\n"
        "• /scan — pindai sinyal BSJP REALTIME sekarang\n"
        "• /update — ambil data terbaru dari GitHub sekarang\n"
        f"• /langganan — terima hasil scan otomatis tiap hari kerja {SCAN_JAM} WIB\n"
        "• /berhenti — berhenti berlangganan\n"
        "• /cari <code>kata</code> — cari kode emiten\n"
        "• /help — bantuan"
    )


def pesan_help() -> str:
    return (
        "<b>Bantuan Draftnest Bot</b>\n\n" + _daftar_perintah() +
        "\n\n⚠️ Semua analisis untuk edukasi/riset, <b>bukan</b> rekomendasi "
        "jual/beli. DYOR."
    )


def pesan_analisis(emiten) -> str:
    """Analisis lengkap 1 emiten (deterministik, tanpa AI)."""
    from .report import jalankan_analisis

    h = jalankan_analisis(emiten, None)
    p = emiten.profil
    sp = h.skor_pilar
    L = [
        f"📊 <b>{_esc(p.nama or p.kode)}</b> (<code>{_esc(p.kode)}</code>)",
        f"<i>{_esc(p.sektor)}</i>" if p.sektor else "",
        "",
        f"{_emoji_rek(h.rekomendasi)} <b>{_esc(h.rekomendasi)}</b> · Skor akhir <b>{_skor(h.skor_akhir)}</b>",
        f"• Kualitatif {_skor(sp.get('kualitatif'))} · Kuantitatif {_skor(sp.get('kuantitatif'))} · Valuasi {_skor(sp.get('valuasi'))}",
    ]

    r = h.kuantitatif_data.rasio_terbaru
    L.append(
        f"• ROE {_pct(r.roe)} · DER {_rp(None) if r.der is None else f'{r.der:.2f}x'} · "
        f"Net margin {_pct(r.net_profit_margin)}"
    )

    if h.valuasi_data:
        rel = h.valuasi_data.relative
        if rel.fair_value is not None:
            L.append(
                f"• Harga {_rp(h.valuasi_data.harga_saham)} · Nilai wajar {_rp(rel.fair_value)} "
                f"(MoS {_pct(rel.mos_fair_value)})"
            )
    if h.ramalan_harga and h.ramalan_harga.target:
        t = h.ramalan_harga.target[-1]
        L.append(f"• Target harga {t.tahun}: {_rp(t.target_harga)} ({_pct(t.potensi_pct)})")

    L.append("")
    L.append("<i>Deterministik dari data. Bukan rekomendasi — DYOR.</i>")
    return "\n".join(x for x in L if x != "" or True)


def pesan_screener(emiten: list[dict], n: int = 12) -> str:
    """Saham: pendapatan & laba naik tiap tahun + prospek bagus (dividen bila ada)."""
    kand = [e for e in emiten if e.get("naik_pendapatan") and e.get("naik_laba")
            and e.get("prospek_bagus")]
    dv = [e for e in kand if (e.get("dividend_yield") or 0) >= 0.03]
    pakai = dv if dv else kand
    pakai = sorted(pakai, key=lambda e: (e.get("skor_akhir") or 0), reverse=True)[:n]
    if not pakai:
        return "Tidak ada emiten yang lolos kriteria screener saat ini."
    L = ["🧭 <b>Screener</b> — tumbuh tiap tahun + prospek bagus"
         + (" + dividen" if dv else "") + ":\n"]
    for e in pakai:
        dyy = f" · div {_pct(e.get('dividend_yield'))}" if e.get("dividend_yield") else ""
        L.append(f"• <code>{_esc(e['kode'])}</code> {_esc((e.get('nama') or '')[:24])} — "
                 f"skor {_skor(e.get('skor_akhir'))}{dyy}")
    L.append("\n<i>Ketik kodenya untuk analisis detail.</i>")
    return "\n".join(L)


def pesan_dividen(emiten: list[dict], n: int = 12) -> str:
    dv = [e for e in emiten if e.get("dividend_yield")]
    dv = sorted(dv, key=lambda e: e["dividend_yield"], reverse=True)[:n]
    if not dv:
        return "Data dividen belum tersedia."
    L = ["💰 <b>Dividend yield tertinggi</b>:\n"]
    for e in dv:
        streak = e.get("dividen_beruntun") or 0
        s = f" ({streak}th beruntun)" if streak else ""
        L.append(f"• <code>{_esc(e['kode'])}</code> {_esc((e.get('nama') or '')[:22])} — "
                 f"<b>{_pct(e['dividend_yield'])}</b>{s}")
    L.append("\n<i>Yield tinggi belum tentu aman — cek keberlanjutan labanya.</i>")
    return "\n".join(L)


def pesan_bsjp(emiten: list[dict], backtest: dict, strategi: str = "s2") -> str:
    """Sinyal BSJP + ringkasan win rate backtest."""
    nama_str = {"s1": "Strategi 1 (RSI Pullback)", "s2": "Strategi 2 (Momentum Breakout)"}
    flag = {"s1": "strat1_sinyal", "s2": "strat2_sinyal"}[strategi]
    bt = (backtest or {}).get("strategi", {}).get(strategi, {})

    L = [f"🌙 <b>BSJP — {nama_str[strategi]}</b>"]
    if bt:
        L.append(
            f"Backtest ~6th: win rate <b>{_pct(bt.get('win_rate'))}</b>, "
            f"rata gain semalam {_pct(bt.get('rata_overnight'))}, "
            f"peluang ≥3% {_pct(bt.get('peluang_3persen'))}."
        )
    kand = [e for e in emiten if e.get(flag)]
    kand = sorted(kand, key=lambda e: (e.get("bsjp_peluang") or 0), reverse=True)
    L.append("")
    if kand:
        L.append(f"Kandidat sinyal terakhir ({len(kand)}):")
        for e in kand[:15]:
            L.append(f"• <code>{_esc(e['kode'])}</code> {_esc((e.get('nama') or '')[:22])}")
    else:
        L.append("Tidak ada kandidat pada data terakhir (sinyal memang jarang).")
    L.append("\n⚠️ <i>Menahan semalam berisiko gap-down. Historis, bukan jaminan.</i>")
    return "\n".join(L)


def pesan_cari(index_emiten: list[dict], kw: str) -> str:
    kw = (kw or "").strip().lower()
    if not kw:
        return "Ketik kata kunci, mis. <code>/cari bank</code>."
    hit = [e for e in index_emiten
           if kw in e.get("kode", "").lower() or kw in e.get("nama", "").lower()][:20]
    if not hit:
        return f"Tak ada emiten cocok '{_esc(kw)}'."
    L = [f"🔎 Hasil '<b>{_esc(kw)}</b>':\n"]
    for e in hit:
        L.append(f"• <code>{_esc(e['kode'])}</code> — {_esc(e.get('nama', ''))}")
    L.append("\n<i>Ketik kodenya untuk analisis.</i>")
    return "\n".join(L)


# ============================ Data loaders ==================================

def _baca_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def muat_screener() -> list[dict]:
    d = _baca_json(DATA_DIR / "screener.json") or {}
    return d.get("emiten", [])


def muat_backtest() -> dict:
    return _baca_json(DATA_DIR / "backtest.json") or {}


def muat_index() -> list[dict]:
    d = _baca_json(DATA_DIR / "index.json") or {}
    return d.get("emiten", [])


def muat_emiten_kode(kode: str):
    """Emiten dari data pra-ambil; None bila tak ada."""
    from .data_loader import muat_emiten

    f = DATA_DIR / f"{kode.lower()}.json"
    if not f.exists():
        return None
    try:
        return muat_emiten(f)
    except Exception:
        return None


# ============================ Pelanggan & Scan ==============================

_scan_lock = threading.Lock()


def muat_pelanggan() -> set[int]:
    d = _baca_json(SUBS_FILE) or []
    try:
        return set(int(x) for x in d)
    except Exception:
        return set()


def simpan_pelanggan(subs: set[int]) -> None:
    try:
        SUBS_FILE.write_text(json.dumps(sorted(subs)), encoding="utf-8")
    except Exception as e:
        print(f"[subs] gagal simpan: {e}")


def scan_realtime(delay: float = 0.3) -> tuple[bool, str]:
    """Pindai sinyal BSJP REALTIME: ambil harga live semua emiten (yfinance),
    hitung ulang sinyal, tulis ke docs/data. Kembalikan (sukses, ringkasan).

    Butuh koneksi internet + yfinance (requirements-data.txt) — cocok di VPS.
    Dilindungi lock agar tak jalan ganda; circuit-breaker menolak snapshot rusak.
    """
    if _scan_lock.locked():
        return False, "Scan lain sedang berjalan — coba lagi sebentar."
    with _scan_lock:
        try:
            from .pipeline import jalankan_sinyal
        except Exception as e:
            return False, f"Modul pipeline tak tersedia: {_esc(e)}"
        try:
            kode = jalankan_sinyal(DATA_DIR, delay=delay)
        except Exception as e:
            return False, f"Scan gagal: {_esc(e)}"
        if kode != 0:
            return False, ("Scan tak menghasilkan data valid (mungkin di luar jam "
                           "bursa / rate-limit). Data terakhir dipertahankan.")
        return True, ringkasan_scan()


def ringkasan_scan() -> str:
    """Ringkas kandidat BSJP dari screener.json terbaru (S2 & S1)."""
    em = muat_screener()
    diperbarui = (_baca_json(DATA_DIR / "screener.json") or {}).get("diperbarui", "?")
    s2 = [e for e in em if e.get("strat2_sinyal")]
    s1 = [e for e in em if e.get("strat1_sinyal")]
    s2 = sorted(s2, key=lambda e: (e.get("bsjp_peluang") or 0), reverse=True)
    L = [f"🌙 <b>Scan BSJP</b> (data {diperbarui}):", ""]
    L.append(f"<b>Strategi 2 — Momentum</b> ({len(s2)} sinyal):")
    L += [f"• <code>{_esc(e['kode'])}</code> {_esc((e.get('nama') or '')[:22])}" for e in s2[:15]] or ["  (tidak ada)"]
    L.append("")
    L.append(f"<b>Strategi 1 — RSI Pullback</b> ({len(s1)} sinyal):")
    L += [f"• <code>{_esc(e['kode'])}</code> {_esc((e.get('nama') or '')[:22])}" for e in s1[:15]] or ["  (tidak ada)"]
    L.append("\n⚠️ <i>Historis/best-effort, bukan jaminan. Risiko gap-down.</i>")
    return "\n".join(L)


# ============================ Auto-ambil data (git) =========================

_git_lock = threading.Lock()


def git_sync(repo_dir: Path = ROOT) -> tuple[bool, str]:
    """Ambil `docs/data/` terbaru dari GitHub (branch main) tanpa mengubah kode.

    Pipeline harian menulis data ke `main`; fungsi ini menariknya ke VPS agar
    bot menyajikan data segar tanpa `git pull` manual. Aman: hanya menimpa
    `docs/data` (bukan kode/`.draftnest_subs.json` yang di-gitignore).

    Kembalikan (sukses, ringkasan). Gagal dengan anggun bila `git` tak ada,
    folder bukan repo, atau tak ada jaringan — data lama tetap dipakai.
    """
    import subprocess

    if _git_lock.locked():
        return False, "Sinkronisasi git lain sedang berjalan."
    with _git_lock:
        if not (repo_dir / ".git").exists():
            return False, ("Folder ini bukan clone git (mis. dari ZIP). "
                           "Auto-update butuh `git clone`. Lihat PANDUAN-BOT.md.")

        def _git(*args: str) -> tuple[int, str]:
            try:
                p = subprocess.run(
                    ["git", "-C", str(repo_dir), *args],
                    capture_output=True, text=True, timeout=120,
                )
                return p.returncode, (p.stdout + p.stderr).strip()
            except FileNotFoundError:
                return 127, "git tidak terpasang"
            except Exception as e:  # timeout dll
                return 1, str(e)

        rc, out = _git("fetch", "origin", "main", "--quiet")
        if rc != 0:
            return False, f"Gagal fetch dari GitHub: {_esc(out) or 'error jaringan'}"
        # Timpa hanya docs/data dari origin/main (surgical, tak sentuh kode).
        rc, out = _git("checkout", "origin/main", "--", "docs/data")
        if rc != 0:
            return False, f"Gagal ambil data: {_esc(out)}"

        diperbarui = (_baca_json(DATA_DIR / "screener.json") or {}).get("diperbarui", "?")
        return True, f"Data ter-update dari GitHub (screener {diperbarui})."


def _penyelaras_git(interval_menit: int) -> None:
    """Thread latar: ambil data terbaru dari GitHub tiap `interval_menit`."""
    tidur = max(300, interval_menit * 60)   # minimal 5 menit
    while True:
        time.sleep(tidur)
        ok, msg = git_sync()
        print(f"[git-sync] {'ok' if ok else 'lewat'}: {msg}")


# ============================ Dispatcher ====================================

def tangani_pesan(teks: str) -> str:
    """Ubah teks pesan masuk -> teks balasan (memuat data dari disk)."""
    teks = (teks or "").strip()
    if not teks:
        return pesan_help()

    bagian = teks.split()
    perintah = bagian[0].lower().lstrip("/")
    # buang suffix @namabot pada perintah grup
    perintah = perintah.split("@", 1)[0]
    arg = " ".join(bagian[1:]).strip()

    if perintah in ("start",):
        return pesan_start()
    if perintah in ("help", "bantuan"):
        return pesan_help()
    if perintah in ("screener",):
        return pesan_screener(muat_screener())
    if perintah in ("dividen", "dividend"):
        return pesan_dividen(muat_screener())
    if perintah in ("bsjp",):
        strat = "s1" if arg.lower() in ("s1", "1", "rsi") else "s2"
        return pesan_bsjp(muat_screener(), muat_backtest(), strat)
    if perintah in ("cari", "search"):
        return pesan_cari(muat_index(), arg)
    if perintah in ("analisis", "analisa", "analyze"):
        kode = arg.upper().split()[0] if arg else ""
        return _analisis_kode(kode) if kode else "Format: <code>/analisis BBCA</code>"

    # Bukan perintah dikenal → anggap kode emiten bila 1 kata alfabet.
    if len(bagian) == 1 and teks.replace(".", "").isalnum() and len(teks) <= 6:
        return _analisis_kode(teks.upper())

    return "Perintah tak dikenal. /help untuk daftar perintah."


def _analisis_kode(kode: str) -> str:
    emiten = muat_emiten_kode(kode)
    if emiten is None:
        return (f"❓ <code>{_esc(kode)}</code> belum ada di data pra-ambil. "
                f"Coba /cari untuk temukan kodenya.")
    try:
        return pesan_analisis(emiten)
    except Exception as e:
        return f"Gagal menganalisis {_esc(kode)}: {_esc(e)}"


# ============================ Bot (long-polling) ============================

class TelegramBot:
    def __init__(self, token: str):
        import requests  # impor lazy

        self.token = token
        self.sesi = requests.Session()

    def _api(self, method: str, **params) -> Optional[dict]:
        url = API.format(token=self.token, method=method)
        try:
            resp = self.sesi.post(url, json=params, timeout=65)
            return resp.json()
        except Exception as e:
            print(f"[api] {method} gagal: {e}")
            return None

    def kirim(self, chat_id: int, teks: str) -> None:
        # Telegram batasi 4096 char; potong aman.
        for bagian in _potong(teks, 3800):
            self._api("sendMessage", chat_id=chat_id, text=bagian,
                      parse_mode="HTML", disable_web_page_preview=True)

    def siar(self, teks: str) -> None:
        """Kirim ke semua pelanggan."""
        for cid in muat_pelanggan():
            self.kirim(cid, teks)

    def _scan_dan_balas(self, chat_id: int, siar: bool = False) -> None:
        """Jalankan scan (thread) lalu kirim hasil ke chat / semua pelanggan."""
        ok, teks = scan_realtime()
        if siar and ok:
            self.siar(f"🔔 Scan otomatis {SCAN_JAM} WIB\n\n{teks}")
        else:
            self.kirim(chat_id, teks)

    def _tangani_khusus(self, chat_id: int, teks: str) -> bool:
        """Perintah yang butuh efek samping (scan/langganan). True bila ditangani."""
        kata = teks.strip().split()
        cmd = kata[0].lower().lstrip("/").split("@", 1)[0] if kata else ""
        if cmd == "scan":
            self.kirim(chat_id, "⏳ Memindai sinyal BSJP realtime… (bisa beberapa menit)")
            threading.Thread(target=self._scan_dan_balas, args=(chat_id,), daemon=True).start()
            return True
        if cmd in ("update", "sinkron", "sync"):
            ok, msg = git_sync()
            self.kirim(chat_id, ("✅ " if ok else "⚠️ ") + msg)
            return True
        if cmd in ("langganan", "subscribe"):
            subs = muat_pelanggan(); subs.add(chat_id); simpan_pelanggan(subs)
            self.kirim(chat_id, f"✅ Berlangganan. Anda akan menerima hasil scan otomatis "
                                f"tiap hari kerja {SCAN_JAM} WIB. /berhenti untuk stop.")
            return True
        if cmd in ("berhenti", "unsubscribe"):
            subs = muat_pelanggan(); subs.discard(chat_id); simpan_pelanggan(subs)
            self.kirim(chat_id, "🔕 Berhenti berlangganan.")
            return True
        return False

    def _penjadwal(self) -> None:
        """Thread latar: jalankan scan + siar pada SCAN_JAM WIB, Senin–Jumat."""
        try:
            jam, menit = (int(x) for x in SCAN_JAM.split(":"))
        except Exception:
            jam, menit = 15, 20
        tz = _wib()
        while True:
            now = datetime.now(tz)
            target = now.replace(hour=jam, minute=menit, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            while target.weekday() >= 5:      # lewati Sabtu/Minggu
                target += timedelta(days=1)
            tidur = (target - now).total_seconds()
            print(f"[jadwal] scan berikutnya: {target:%Y-%m-%d %H:%M} WIB "
                  f"({tidur/3600:.1f} jam lagi)")
            time.sleep(max(30, tidur))
            if not muat_pelanggan():
                continue                       # tak ada yang dikirimi
            # Ambil data terbaru dulu (kalau scan gagal, ringkasan tetap segar).
            gok, gmsg = git_sync()
            print(f"[jadwal] git-sync: {gmsg}")
            print("[jadwal] menjalankan scan otomatis…")
            ok, teks = scan_realtime()
            if ok:
                self.siar(f"🔔 Scan otomatis {SCAN_JAM} WIB\n\n{teks}")

    def jalan(self) -> None:
        me = self._api("getMe")
        nama = (me or {}).get("result", {}).get("username", "?")
        print(f"✅ Bot @{nama} jalan. Scan otomatis {SCAN_JAM} WIB (Sen–Jum). "
              f"Ctrl+C untuk berhenti.")
        # Ambil data terbaru saat mulai, lalu jadwalkan sinkronisasi berkala.
        if GIT_SYNC_MENIT > 0:
            ok, msg = git_sync()
            print(f"[git-sync] awal: {msg}")
            threading.Thread(target=_penyelaras_git, args=(GIT_SYNC_MENIT,),
                             daemon=True).start()
        threading.Thread(target=self._penjadwal, daemon=True).start()
        offset = None
        while True:
            data = self._api("getUpdates", offset=offset, timeout=50)
            if not data or not data.get("ok"):
                time.sleep(3)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg or "text" not in msg:
                    continue
                chat_id = msg["chat"]["id"]
                try:
                    if self._tangani_khusus(chat_id, msg["text"]):
                        continue
                    self.kirim(chat_id, tangani_pesan(msg["text"]))
                except Exception as e:
                    self.kirim(chat_id, f"⚠️ Terjadi kesalahan: {_esc(e)}")


def _potong(teks: str, maks: int) -> list[str]:
    if len(teks) <= maks:
        return [teks]
    keping, kini = [], ""
    for baris in teks.split("\n"):
        if len(kini) + len(baris) + 1 > maks:
            keping.append(kini)
            kini = ""
        kini += baris + "\n"
    if kini:
        keping.append(kini)
    return keping


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Set dulu TELEGRAM_BOT_TOKEN (dapat dari @BotFather di Telegram).")
        return 2
    TelegramBot(token).jalan()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
