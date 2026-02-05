# Staklim

Weather Map Generation Package for BMKG Papua Barat Daya.

## Installation

```bash
pip install git+https://github.com/nashathur/Staklim_Papbar.git
```

## Usage in Google Colab

```python
!pip install -q git+https://github.com/nashathur/Staklim_Papbar.git

from google.colab import files
from staklim import cfg, execute

# Configuration
cfg.jenis_peta = ['Prakiraan']
cfg.tipe_peta = ['Curah Hujan']
cfg.skala_peta = ['Dasarian']
cfg.year = 2026
cfg.months = [1]
cfg.wilayah = "Papua Barat Daya"
cfg.dasarian = 3
cfg.year_ver = 2025
cfg.month_ver = 12
cfg.dasarian_ver = 2
cfg.hgt = True

# Upload file
print("Upload prakiraan file:")
uploaded = files.upload()
cfg.file_prakiraan = list(uploaded.keys())[0]

# Execute
for peta in cfg.jenis_peta:
    for tipe in cfg.tipe_peta:
        for skala in cfg.skala_peta:
            for month in cfg.months:
                execute(peta, tipe, skala, month)
```

## Configuration Options

| Parameter | Description | Example |
|-----------|-------------|---------|
| `jenis_peta` | Map types | `['Prakiraan', 'Analisis', 'Verifikasi', 'Probabilistik']` |
| `tipe_peta` | Data types | `['Curah Hujan', 'Sifat Hujan']` |
| `skala_peta` | Time scale | `['Bulanan', 'Dasarian']` |
| `year` | Forecast year | `2026` |
| `months` | Months to process | `[1, 2, 3]` |
| `wilayah` | Region name | `"Papua Barat Daya"` |
| `dasarian` | Dasarian period (1-3) | `3` |
| `hgt` | Show ocean depth layer | `True` |
| `file_prakiraan` | Path to forecast data file | Set after upload |
| `file_analisis` | Path to analysis data file | Set after upload |
