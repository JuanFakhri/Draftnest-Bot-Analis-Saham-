"""Fixtures bersama untuk pengujian."""

from draftnest.models import DataPasar, Emiten, LaporanTahunan, ProfilEmiten


def laporan(tahun, **over):
    dasar = dict(
        total_aset=130000, aset_lancar=46000,
        total_liabilitas=59000, liabilitas_lancar=22000, total_ekuitas=71000,
        pendapatan=72000, laba_kotor=26000, laba_operasi=15500, laba_bersih=9200,
        arus_kas_operasi=12500, arus_kas_investasi=-6000, arus_kas_pendanaan=-3500,
    )
    dasar.update(over)
    return LaporanTahunan(tahun=tahun, **dasar)


def emiten_contoh():
    return Emiten(
        profil=ProfilEmiten(kode="ICBP", nama="Indofood CBP", sektor="Consumer"),
        laporan=[
            laporan(2023, pendapatan=67000, laba_bersih=8000, total_ekuitas=61000),
            laporan(2024),
        ],
        pasar=DataPasar(
            harga_saham=11500, saham_beredar=11.66,
            per_sektor=15.0, pbv_sektor=3.0,
        ),
    )
