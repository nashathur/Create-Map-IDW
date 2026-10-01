# Create-Map-IDW

Automated weather map generation using IDW (Inverse Distance Weighting) spatial interpolation, built for [BMKG](https://www.bmkg.go.id/) regional offices in Papua Barat and Papua Barat Daya.

## Overview

Create-Map-IDW is a Python package designed to run in **Google Colab**. It produces publication-ready weather maps from station observation and forecast data, with support for multiple map types, template overlays, AI-generated captions, and Word document reports.

## Features

- **7 map types** — Prakiraan (forecast), Analisis (analysis), Verifikasi (verification), Probabilistik, Normal, Bias, and HTH
- **IDW interpolation** — Numba JIT-accelerated spatial interpolation with KDTree neighbor lookup
- **Template overlays** — Composites raw maps onto publication-ready templates with legends and backgrounds
- **Ocean depth layer** — Optional bathymetry/elevation raster overlay
- **Flexible regions** — Province or district-level maps with fuzzy name matching
- **AI captions** — Auto-generated Indonesian-language narratives via Google Gemini API
- **Word reports** — `.docx` output with official letterhead, maps, and AI analysis
- **CSV export** — Export the station points used for interpolation
- **Verification metrics** — Accuracy, HSS (Heidke Skill Score), and PSS (Peirce Skill Score)
- **Execution logging** — Automatic logging of every run to `execution_log.csv`

## Installation

```bash
pip install git+https://github.com/nashathur/Create-Map-IDW.git
```

Requires Python >= 3.9.

## Quick Start (Google Colab)

```python
from IPython.display import clear_output
try:
    from Main import cfg, execute
except ImportError:
    !pip install git+https://github.com/nashathur/Create-Map-IDW.git -q
    from Main import cfg, execute

# Map type
cfg.jenis_peta = "Analisis"            # Prakiraan | Analisis | Verifikasi | Probabilistik | Normal | Bias | HTH
cfg.tipe_peta  = ['Sifat Hujan']       # 'Curah Hujan' (rainfall) | 'Sifat Hujan' (rainfall characteristics)
cfg.skala_peta = 'Dasarian'            # 'Bulanan' (monthly) | 'Dasarian' (10-day period)
cfg.wilayah    = "Papua Barat,Papua Barat Daya"  # Province/district names, comma-separated

# Title date
cfg.year     = 2026
cfg.month    = 2                        # 1–12
cfg.dasarian = 2                        # 1–3

# Subtitle / version date
cfg.year_ver     = 2026
cfg.month_ver    = 2
cfg.dasarian_ver = 3

# Options
cfg.hgt         = True                  # Ocean depth layer
cfg.png_only    = False                 # Raw PNG only (no template, no legend)
cfg.create_word = True                  # Generate Word document report
cfg.export_csv  = False                 # Export interpolated data to CSV
cfg.verif_mode  = 'kuantitatif'         # 'kuantitatif' (9 classes) | 'kualitatif' (4 classes)

# Run
for tipe in cfg.tipe_peta:
    clear_output()
    map_data = execute(cfg.jenis_peta, tipe, cfg.skala_peta, cfg.month)
```

## Configuration Reference

### Map Settings

| Option | Type | Values | Description |
|---|---|---|---|
| `cfg.jenis_peta` | `str` | `Prakiraan`, `Analisis`, `Verifikasi`, `Probabilistik`, `Normal`, `Bias`, `HTH` | Map category |
| `cfg.tipe_peta` | `list[str]` | `['Curah Hujan']`, `['Sifat Hujan']`, or both | Rainfall metric(s) to map |
| `cfg.skala_peta` | `str` | `Bulanan`, `Dasarian` | Time scale (monthly or 10-day) |
| `cfg.wilayah` | `str` | Province/district names | Target region(s), comma-separated |

### Date Settings

| Option | Type | Description |
|---|---|---|
| `cfg.year` | `int` | Map title year |
| `cfg.month` | `int` | Map title month (1–12) |
| `cfg.dasarian` | `int` | Map title dasarian (1–3) |
| `cfg.year_ver` | `int` | Subtitle / version year |
| `cfg.month_ver` | `int` | Subtitle / version month |
| `cfg.dasarian_ver` | `int` | Subtitle / version dasarian |

### Feature Flags

| Option | Type | Default | Description |
|---|---|---|---|
| `cfg.hgt` | `bool` | `True` | Enable ocean depth / elevation layer |
| `cfg.png_only` | `bool` | `False` | Output raw PNG only — disables template overlay, HGT layer, and Word generation |
| `cfg.create_word` | `bool` | `False` | Generate a `.docx` report with maps and AI-generated analysis |
| `cfg.export_csv` | `bool` | `False` | Export the station points used for interpolation to CSV |
| `cfg.verif_mode` | `str` | `kuantitatif` | Verification method: `kuantitatif` (9 rainfall classes) or `kualitatif` (4 classes) |

## Supported Map Types

| `jenis_peta` | `tipe_peta` | `skala_peta` | Description |
|---|---|---|---|
| Prakiraan | Curah Hujan / Sifat Hujan | Bulanan / Dasarian | Rainfall forecast maps |
| Analisis | Curah Hujan / Sifat Hujan | Bulanan / Dasarian | Observation analysis maps |
| Verifikasi | — | — | Forecast verification with accuracy metrics |
| Probabilistik | Curah Hujan | Bulanan / Dasarian | Probabilistic forecast (6 threshold sub-maps) |
| Normal | — | — | 1991–2020 climate normal reference |
| Bias | — | — | Forecast bias map |
| HTH | — | — | Hari Tanpa Hujan (consecutive dry days) index |

## Dependencies

pandas, numpy, geopandas, matplotlib, scipy, rioxarray, thefuzz, numba, Pillow, openpyxl, pyarrow, docxtpl, python-docx
