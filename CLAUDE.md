# CLAUDE.md — Create-Map-IDW

This file describes the codebase structure, conventions, and development workflows for AI assistants working on this project.

## Project Overview

**Create-Map-IDW** is a Python package for automated weather map generation, developed for BMKG (Badan Meteorologi, Klimatologi, dan Geofisika) — specifically the Papua Barat and Papua Barat Daya regional offices. It is designed to run in **Google Colab** and produces publication-ready weather maps using IDW (Inverse Distance Weighting) spatial interpolation.

- **Package name:** `create-map-idw`
- **Version:** 1.0.0
- **Python requirement:** >=3.9
- **Primary language:** Python
- **Deployment target:** Google Colab notebooks

---

## Repository Structure

```
Create-Map-IDW/
├── Main/                          # Core package
│   ├── __init__.py                # Public API, execute() entry point
│   ├── config.py                  # Global cfg class + static file URLs
│   ├── logger.py                  # GitHub API execution logging
│   ├── map_creation.py            # Core map rendering (IDW raster, scatter)
│   ├── narasi.py                  # AI-generated captions via Gemini API
│   ├── processors.py              # Per-map-type data processors
│   ├── static.py                  # Static file downloads and basemap caching
│   ├── status.py                  # Status callback system (for Colab output)
│   ├── template.py                # Image template overlay composition
│   ├── upload.py                  # Google Colab file upload handler
│   ├── utils.py                   # IDW math, data loaders, metrics, helpers
│   ├── word.py                    # Word document generation (.docx)
│   └── unused.py                  # Archived/deprecated code
├── Prakiraan.ipynb                # Google Colab notebook for end users
├── execution_log.csv              # Auto-committed execution history log
├── pyproject.toml                 # Build config and dependencies
├── README.md                      # User-facing installation/usage guide
└── .gitignore                     # Ignores __pycache__/
```

---

## Module Responsibilities

| Module | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~150 | Package exports; `execute()` orchestration |
| `config.py` | ~70 | Global `cfg` class, static file URLs, Gemini key |
| `processors.py` | ~416 | Map-type-specific data prep (`get_pch`, `get_psh`, etc.) |
| `map_creation.py` | ~549 | Core map rendering: IDW raster + scatter plot variants |
| `narasi.py` | ~852 | Gemini API captions, percentage computations, retries |
| `utils.py` | ~371 | IDW Numba kernel, data loaders, categorization, metrics |
| `template.py` | ~350 | PNG template overlay composition with PIL |
| `word.py` | ~245 | Jinja2 Word doc rendering via `docxtpl` |
| `static.py` | ~258 | Download static files from GitHub releases, basemap cache |
| `logger.py` | ~111 | Log execution metadata to `execution_log.csv` via GitHub API |
| `status.py` | ~12 | `update()` callback for Colab display |
| `upload.py` | ~30 | Colab file upload widget handler |

---

## Configuration System

All settings live on the `cfg` class in `config.py`. **Set all fields before calling `execute()`.**

```python
from Main import cfg, execute, upload_files

# Map type
cfg.jenis_peta = 'Prakiraan'          # Prakiraan | Analisis | Verifikasi |
                                       # Probabilistik | Normal | Bias | HTH
cfg.tipe_peta  = ['Curah Hujan']      # 'Curah Hujan' | 'Sifat Hujan' (list)
cfg.skala_peta = 'Bulanan'            # 'Bulanan' | 'Dasarian'
cfg.wilayah    = 'Papua Barat, Papua Barat Daya'  # Province/district names

# Time settings
cfg.year        = 2026
cfg.month       = 2           # 1–12
cfg.dasarian    = 3           # 1–3

# Verification period settings
cfg.year_ver     = 2026
cfg.month_ver    = 2
cfg.dasarian_ver = 2

# Feature flags
cfg.hgt         = True        # Ocean depth layer (True/False)
cfg.png_only    = False       # Skip template overlay (True/False)
cfg.export_csv  = False       # Export interpolated data to CSV
cfg.create_word = False       # Generate Word document output
cfg.verif_mode  = 'kuantitatif'  # 'kuantitatif' | 'kualitatif'

# File paths (set by upload_files() or manually)
cfg.file_prakiraan = None     # Path to uploaded forecast file
cfg.file_analisis  = None     # Path to uploaded analysis file
cfg.file_hth       = None     # Path to uploaded HTH file
```

`cfg` uses class-level attributes (no instantiation needed). Fields `peta`, `tipe`, `skala`, and `month` are set internally by `execute()` — do not set these directly.

---

## Execution Flow

```
execute(peta, tipe, skala, month)
    │
    ├── download_static_files()        # Ensure basemap/template files exist
    ├── clear_data_cache()             # Reset in-memory data (except HTH)
    │
    ├── Processor dispatch:
    │   ├── get_pch()    → PCH, PCHdas
    │   ├── get_psh()    → PSH, PSHdas
    │   ├── get_ach()    → ACH, ACHdas
    │   ├── get_ash()    → ASH, ASHdas
    │   ├── get_spi()    → SPI
    │   ├── get_pch_prob() → PCH_Prob, PCH_Prob_das (6 sub-maps)
    │   ├── get_verif()  → VERquan | VERqual
    │   ├── get_normal() → NORMAL
    │   ├── bias_map()   → BIAS
    │   └── get_hth()    → HTH
    │
    ├── [Optional] _export_csv(plot_data)
    │
    ├── overlay_image(plot_data)       # Composite PNG template
    │
    ├── log_execution(cfg, filename, duration)
    │
    └── [Optional] arrange_word(map_data)
```

Each processor function calls `create_map()` or `create_scatter_map()` and returns a `plot_data` dict containing: `fig`, `ax`, `image`, `file_name`, `peta`, `tipe`, `skala`, `jenis`, `year`, `month`, `dasarian`, `month_ver`, `year_ver`, `dasarian_ver`, `nama_wilayah`, `province_data`, `kabupaten_data`, `value`.

---

## Map Types Reference

| `jenis_peta` | `tipe_peta` | `skala_peta` | Internal `jenis` |
|---|---|---|---|
| Prakiraan | Curah Hujan | Bulanan | PCH |
| Prakiraan | Curah Hujan | Dasarian | PCHdas |
| Prakiraan | Sifat Hujan | Bulanan | PSH |
| Prakiraan | Sifat Hujan | Dasarian | PSHdas |
| Analisis | Curah Hujan | Bulanan | ACH |
| Analisis | Curah Hujan | Dasarian | ACHdas |
| Analisis | Sifat Hujan | Bulanan | ASH |
| Analisis | Sifat Hujan | Dasarian | ASHdas |
| Prakiraan / Analisis | SPI | — (always 1-monthly) | SPI |
| Probabilistik | Curah Hujan | Bulanan/Dasarian | PCH_Prob / PCH_Prob_das |
| Verifikasi | — | — | VERquan / VERqual |
| Normal | — | — | NORMAL |
| Bias | — | — | BIAS |
| HTH | — | — | HTH |

---

## Input Data Conventions

### Expected Column Names

All input DataFrames must use these normalized column names after loading:

| Column | Variants accepted | Notes |
|---|---|---|
| `LON` | BUJUR, LON, LONGITUDE | Longitude, rounded to 2 decimal places |
| `LAT` | LINTANG, LAT, LATITUDE | Latitude, rounded to 2 decimal places |
| `CH` | — | Curah Hujan (rainfall mm) in analisis |
| `VAL` | — | Forecast value (prakiraan bulanan) |
| `SH` | — | Sifat Hujan percentage (dasarian) |
| `SH%` | — | Sifat Hujan percentage (bulanan ASH) |
| `b50`, `b100`, `b150`, `a50`, `a100`, `a150` | — | Probabilistic columns |
| `INDEKS_HTH` | INDEKS HTH, INDEKS_HTH, INDEX_HTH | HTH index |
| `SPI` | SPI, VALSPI, VAL_SPI, NILAI_SPI | Standardized Precipitation Index (continuous) |

### Data Categorization

**Curah Hujan (4-level):**
- 1: 0–100 mm
- 2: 101–300 mm
- 3: 301–500 mm
- 4: >500 mm

**Index (9-level, quantitative verification):**
- 1: 0–20 | 2: 21–50 | 3: 51–100 | 4: 101–150 | 5: 151–200 | 6: 201–300 | 7: 301–400 | 8: 401–500 | 9: >500

**Missing value fallback:** Always returns category `1` (lowest). The scalar `categorize_ch()` / `categorize_index()` are archived in `unused.py` (no callers); the live implementations are the vectorized `categorize_ch_vec()` / `categorize_index_vec()` in `utils.py`, used by `arrange_table()`.

---

## Static Files and Caching

Static files are downloaded from GitHub releases. The cache directory is resolved by `_resolve_cache_dir()` in `config.py`:

1. **Google Colab:** `/content/static_data`
2. **Environment variable:** `CREATE_MAP_IDW_CACHE_DIR` (if set)
3. **Default (local):** `~/.create_map_idw/static_data`

| File | Purpose |
|---|---|
| `idkab.feather` | Indonesian district shapefile (GeoDataFrame) |
| `hgt1.tif` | Ocean depth/elevation raster |
| `DATA_CH_NORMAL_PAPBAR_1991_2020.xlsx` | 1991–2020 climate normals |
| `template_ch_bulanan.png` | Map template (monthly CH) |
| `template_ch_das.png` | Map template (dasarian CH) |
| `template_sh.png` | Map template (SH) |
| `template_verifikasi.png` | Map template (verification) |
| `template_probabilistik.png` | Map template (probabilistic) |
| `template_hth.png` | Map template (HTH) |
| `arial.zip` | Arial font family |
| `template_doc.docx` | Word document base template |

**Cache behavior:**
- Basemap and HGT data are held in module-level global variables after first load
- Call `clear_basemap_cache()` or `clear_spatial_cache()` to force reload
- Data (prakiraan/analisis) is cached per session and cleared at the start of each `execute()` call (except for HTH maps)

---

## IDW Interpolation

The core spatial interpolation is in `utils.py:idw_numba()`:

- Uses `@njit(parallel=True)` from Numba for JIT-compiled parallel execution
- Distance weighting: `w = 1 / (dist^power + 1e-10)` (epsilon prevents division by zero)
- `power` parameter controls interpolation smoothness
- Uses `scipy.spatial.KDTree` for efficient nearest-neighbor lookup before IDW

When modifying IDW logic, **test with actual station data** — Numba compilation happens on first call, which can be slow.

---

## Verification Metrics

Implemented in `utils.py:calculate_metrics()`:

- **Accuracy (PC):** `correct / total` — proportion of exact category matches
- **HSS:** Heidke Skill Score via Cohen's Kappa (`cohen_kappa()`)
- **PSS:** Peirce Skill Score — `(hits - pixoi) / (1 - oi2)`

Displayed on the verification map as overlaid text. `kuantitatif` mode uses 9 categories; `kualitatif` uses 4.

---

## Key Design Patterns

### Global cfg Pattern
The `cfg` class uses class attributes as a simple global state container. There is no instantiation — all reads and writes use `cfg.field_name` directly. This is intentional for simplicity in Colab notebooks.

### Status Callback
`status_update(msg)` (from `status.py`) is a thin wrapper that forwards messages to a global callable. In Colab, this prints progress. When adding new processing steps, call `status_update()` at meaningful checkpoints.

### In-Memory Image Handling
Images are loaded into memory via `load_image_to_memory()` in `utils.py` to avoid PIL file-handle leaks. Always use this function when opening images that must outlive their source file handle.

### Processor Return Dictionary
All processor functions return a `plot_data` dict. The `overlay_image()` function in `template.py` expects specific keys. When adding a new map type, ensure the return dict matches the structure:

```python
plot_data = {
    'fig': matplotlib_figure,
    'ax': matplotlib_axes,
    'image': PIL_Image,         # In-memory PNG of the raw map
    'file_name': 'output.png',
    'peta': cfg.peta,
    'tipe': cfg.tipe,
    'skala': cfg.skala,
    'jenis': 'PCH',             # Internal map type identifier
    'year': ..., 'month': ..., 'dasarian': ...,
    'year_ver': ..., 'month_ver': ..., 'dasarian_ver': ...,
    'nama_wilayah': ...,
    'province_data': ...,       # Dict of province-level statistics
    'kabupaten_data': ...,      # Dict of district-level statistics
    'value': 'CH',              # Source column name
}
```

### Fuzzy Region Matching
`thefuzz` is used in `static.py` and related code for flexible region name matching. Indonesian province/district names may have spelling variants; fuzzy matching prevents failures on minor differences.

---

## Execution Logging

Every `execute()` call appends a record to `execution_log.csv` via the GitHub API (`logger.py`). The log captures:

- Timestamp, map type, scale, region
- Year/month/dasarian settings (title and version)
- Feature flags (`hgt`, `export_csv`, `png_only`, `create_word`, `verif_mode`)
- Output filename and execution duration (seconds)

The GitHub token is XOR-obfuscated in `logger.py` with key `0x5A` and decoded at runtime using base64. **Do not replace or expose the raw token.**

Similarly, the Gemini API key in `config.py` is decoded at import time from an obfuscated blob — it is assigned to `cfg.gemini_api_key` and should not be hardcoded elsewhere.

---

## Narasi (AI Caption) System

`narasi.py` uses the Google Gemini API to generate Indonesian-language map captions. Key functions:

- `get_analysis(plot_data)` — province/district level percentage analysis
- `get_full_narration(plot_data)` — full narrative text for the map
- `get_visual_interpretation(plot_data)` — visual analysis paragraph
- `build_table_data(plot_data)` — structured data for Word tables

Gemini calls use exponential backoff retry logic. The API key comes from `cfg.gemini_api_key`.

---

## Word Document Generation

`word.py:arrange_word(map_data)` uses `docxtpl` (Jinja2 templates for Word) with `python-docx` to produce `.docx` output. The base template is `template_doc.docx` from static files. Enable with `cfg.create_word = True`.

---

## Dependencies

```toml
[project.dependencies]
pandas >= 1.5.0        # DataFrame operations
numpy >= 1.21.0        # Numerical arrays
geopandas >= 0.12.0    # Geospatial shapefiles
matplotlib >= 3.5.0    # Map visualization
scipy >= 1.9.0         # KDTree, interpolation
rioxarray >= 0.13.0    # GeoTIFF raster handling
thefuzz >= 0.22.0      # Fuzzy string matching
numba >= 0.56.0        # JIT-compiled IDW kernel
Pillow >= 9.0.0        # Image composition
openpyxl >= 3.0.0      # Excel file I/O
pyarrow >= 10.0.0      # Feather file I/O
docxtpl >= 0.16.0      # Word template rendering
python-docx >= 0.8.11  # Word document model

[project.optional-dependencies]
dev = ["pytest >= 7.0.0"]
```

---

## Testing

There is currently **no formal test suite**. `pytest` is declared as a dev dependency but no test files or test directories exist. The package is validated through the `execution_log.csv` history and manual notebook runs.

When adding tests, place them in a `tests/` directory. Use `pytest` as the test runner. Test data should mock `cfg` settings and stub out Gemini/GitHub API calls.

---

## Installation

```bash
# Install from GitHub (typical Colab usage)
pip install git+https://github.com/nashathur/Create-Map-IDW.git

# Local development
pip install -e .
```

---

## Git Conventions

- Branch for AI/Claude sessions: `claude/<session-id>`
- Execution log commits follow the format: `log: <MapType> - <Tipe> - <Skala> (YYYY-MM-DD HH:MM)`
- Feature/fix branches merged to `main` via pull requests
- `main` is the default branch and the one `pip install git+https://...` resolves to

---

## Common Gotchas

1. **Numba JIT warm-up:** `idw_numba()` is currently NOT on the active code path — `create_map()` interpolates via `scipy.interpolate.RegularGridInterpolator` plus a `distance_transform_edt` nearest-fill. When IDW is restored, expect a compile delay on its first call per session.

2. **`cfg.png_only = True`** disables `cfg.hgt` automatically, skips template overlay, and skips Word generation.

3. **Probabilistik maps** return a nested dict with 6 sub-maps (`result_b50` through `result_a150`). The `overlay_image()` and `_export_csv()` functions handle this case differently from other map types.

4. **Region name in `cfg.wilayah`** can be a comma-separated list of provinces and/or districts. Fuzzy matching handles minor name variants. Use exact or near-exact Indonesian geographic names.

5. **`cfg.tipe_peta`** is a list (not a string). The calling notebook loops over this list and calls `execute()` once per type.

6. **Static files** are cached to `/content/static_data`. On a fresh Colab runtime, `download_static_files()` re-downloads everything. If a file is corrupted, `redownload()` in `static.py` handles it.

7. **Data column flexibility:** Prakiraan data may use either `CH` or `VAL` for forecast values. Always check for both columns in order (`CH` first, then `VAL`).

---

## Configuration Constants (config.py)

Everything tunable lives in `Main/config.py`. The dividing rule:

> **`cfg` = what changes between runs. Module-level constants = what changes between deployments.**

`cfg` keeps exactly the fields it always had — nothing was added to it, so the
notebook interface is unchanged. Values that used to be hardcoded across modules
now sit in named tables:

| Table | Covers |
|---|---|
| `INTERP` | Interpolation method, IDW `power`/`n_neighbors`, smoothing, render mode, detection thresholds |
| `GRID` | Output cell size (degrees) |
| `RENDER`, `RENDER_PROB` | figsize, dpi, font sizes, tick/spine widths; Probabilistik overrides |
| `LEVELS`, `COLORS` | Map colour bands (display) |
| `KLASIFIKASI`, `KLASIFIKASI_TEKS` | Narration categories: `batas` + `nama` + `deskripsi` in one place |
| `HTH_KLASIFIKASI`, `HTH_COLORS`, `SCATTER_SIZES` | HTH scatter map |
| `TEMPLATE` | Panel geometry, paste dimensions, fonts, downscale `resample` filter |
| `GEMINI`, `NARASI` | Model fallback chains, retry policy, narration thresholds |
| `WORD`, `DOWNLOAD` | Word font, download retries |

### Two concepts, deliberately separate

`LEVELS` (display bands) is intentionally **finer** than `KLASIFIKASI`
(narration categories) — a 9-band gradient reads well on a map, a 4-category
summary reads well in a sentence. Do not merge them.

What *was* wrong is now fixed: the narration thresholds and the wording that
describes them used to live in two different files (`utils.py` bins vs
`narasi.py` prompt text), so changing one left the other stale. Both now come
from `KLASIFIKASI`, and `narasi.CATEGORY_DEFS` is derived from it.

### Interpolation method is not on `cfg`

Deliberate. Unlike `hgt` or `png_only`, the correct method is determined by the
shape of the data in the file, and an operator generally cannot tell which by
looking. A notebook toggle invites a wrong or stale setting and a silently
wrong map. `INTERP['method']` defaults to `'auto'`; the override exists for
forcing a method or comparing two, and lives in `config.py` where it is reached
deliberately.

### Note on `COLORS['Curah Hujan']` vs `COLORS['Normal']`

These two palettes are similar but **not identical** (`#340900` vs `#340A00`,
and five other channels). The difference exists in the original code and is
preserved intentionally — do not "tidy" them into one entry.

---

## Testing

There is a `tests/` directory now, run with `pytest tests/`. The tests are
pure-numeric — no static files, no network, no Gemini/GitHub calls — so they run
in a bare checkout with only the runtime dependencies installed.

| File | Covers |
|---|---|
| `tests/test_interpolation.py` | Lattice detection, method resolution, IDW numerics, and a regression test that gridded input still produces exactly what it did before |
| `tests/test_config_consolidation.py` | The two-table separation, `LEVELS`/`COLORS` alignment, and guards against literals creeping back out of `config.py` |

`INTERP` is module-level mutable state; tests that change it use the
`restore_interp` fixture so they do not leak into other tests.
