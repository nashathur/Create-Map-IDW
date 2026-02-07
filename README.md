#Map Creation

Weather Map Generation Package for BMKG Papua Barat Daya.

## Installation

```bash
pip install git+https://github.com/nashathur/Create-Map-IDW.git
```

## Usage in Google Colab

```python
from IPython.display import clear_output
try:
    from Main import cfg, execute, upload_files
except ImportError:
    !pip install git+https://github.com/nashathur/Create-Map-IDW.git -q
    clear_output()
    from Main import cfg, execute, upload_files

# SEKARANG BISA PROCESS HTH !!!
# step-stepnya:
#   1. atur settingan berikut
#   2. klik Run all atau tombol play
#   3. tunggu sebentar persiapan file dan script
#   4. upload file dengan klik 'Browse' di bawah (jika peta verifikasi: tunggu 'Browse' upload file kedua)
#   5. tunggu proses berjalan
#   *untuk HTH, upload file draft HTH ArcGIS (yang penting ada kolom bujur, lintang, indeks HTH)
# Configuration
cfg.jenis_peta = 'HTH'         # Pilihan: Prakiraan, Analisis, Verifikasi, Probabilistik, Normal, Bias, HTH (jangan lupa diberi tanda petik "")
cfg.tipe_peta  = ['Curah Hujan']     # 'Curah Hujan', 'Sifat Hujan'   (((bisa pilih dua-duanya, pisahkan dengan koma)))
cfg.skala_peta = "Bulanan"           # 'Bulanan', 'Dasarian'
cfg.wilayah    = "Papua Barat, Papua Barat Daya"
# > ((bisa kabupaten atau provinsi dan lebih dari satu, pisahkan dengan koma)) *diganti sesuai nama provinsi yang diinginkan (contoh jika dipilih lebih dari satu prov: Jawa Timur, Bali)

# settingan untuk judul dan waktu (title)
cfg.year     = 2026
cfg.month    = 2                     # bulan 1-12
cfg.dasarian = 3                     # dasarian 1-3

# settingan untuk versi / update date (subtitle)
cfg.year_ver     = 2026
cfg.month_ver    = 2
cfg.dasarian_ver = 2

# layer laut
cfg.hgt = True      # (True / False)

# cuma png (no laut, no legend, no background) HARUS DOWNLOAD ('Save Image As...') DULU, supaya background transparant
cfg.png_only = False  # (True / False)

# upload file (tunggu beberapa saat untuk upload file, klik 'Browse')
upload_files()

for tipe in cfg.tipe_peta:
    clear_output()
    execute(cfg.jenis_peta, tipe, cfg.skala_peta, cfg.month)
```
