# Plan: Hugging Face Space (Gradio) for Create-Map-IDW

Status (2026-10-26): design settled; build step 1 (`Main/` changes) done but **uncommitted**; steps 2-4 not started. This file is the full handoff for a fresh session: read it, then `## Handoff` at the end.

## Goal

A web page that the office staff (about 5 people) use instead of the Colab notebook. They upload files, check the maps detected from them, pick the wilayah, and download the results. The admin is the user alone.

Decisions already made:

- Host: a Hugging Face Space, Gradio SDK, free CPU tier (2 vCPU, 16 GB RAM, sleeps after 48 h idle, disk wiped on restart).
- The Space is public with no password. Data privacy and key exposure were weighed and accepted: Gemini narration has its own fallback, and only about 5 people use it.
- The Colab notebook keeps working unchanged. Every `Main/` change below is opt-in and defaults to today's behaviour.

## Repository changes in `Main/`

| File | Change |
|---|---|
| `config.py` | New fields `cfg.ask_upload = True`, `cfg.output_dir = None`, `cfg.kolom = None`, `cfg.kolom_pembanding = None`. Gemini key: `os.environ.get('GEMINI_API_KEY') or _decode(...)` at line 68. |
| `upload.py` | `upload_files()` starts with `if not cfg.ask_upload: return` (it is called unconditionally at `__init__.py:85`). |
| `word.py:275` | `output_dir = cfg.output_dir or ('/content' if is_colab() else os.getcwd())` |
| `map_creation.py:563` | Same `output_dir` line as `word.py`. |
| `logger.py:40` | `_get_token()` returns `os.environ.get('GITHUB_TOKEN')` first, then the obfuscated token. Do not touch or expose the existing blob. |
| `processors.py` | About 10 processors pick their value column with fallback logic (for example `get_pch` dasarian: CH, then VAL). Each one first uses `cfg.kolom` when it is set; Verifikasi and Bias use `cfg.kolom_pembanding` for the analisis file. Fallback stays as it is. |
| `pyproject.toml` | Add `google-genai` (today `narasi.py` installs it at runtime). |
| new `Main/filenames.py` | File-name and column detection (rules below), pure functions, no Gradio import. |
| new `tests/test_filenames.py` | Self-check on the 8 real file names listed below. |

Then tag a release (for example `v1.1`) so the Space installs a fixed version.

`IPython.display` calls at `template.py:359` and `__init__.py:165` already fall back on `ImportError`; nothing to change there.

## Space files (separate HF repo)

- `README.md` front matter: `sdk: gradio`, `app_file: app.py`.
- `requirements.txt`: `git+https://github.com/nashathur/Create-Map-IDW.git@v1.1`, `google-genai`.
- `app.py`:
  - Calls `download_static_files()` once at start-up. Reads the wilayah choices from `idkab.feather` (`PROVINSI` and `KABUPATEN` unique values) at the same time.
  - `demo.queue(default_concurrency_limit=1)`, because `cfg` is a global class shared by every visitor.
  - Per run: a temp dir set as `cfg.output_dir`; `cfg.ask_upload = False`; `cfg.file_*` set from the uploads; `status.set_callback()` drives each map's progress bar.
  - After each `execute()`: saves `map_data['image']` to PNG, collects Word/CSV from `cfg.output_dir`, renames everything to the readable names (below).
  - `delete_cache` so results are removed after 1 hour.
- Secrets (Space settings): `GEMINI_API_KEY`, `GITHUB_TOKEN`. No auth.

## File-name detection (`Main/filenames.py`)

Matching is case-insensitive; browser suffixes like ` (1)` are stripped first.

| Pattern | Meaning |
|---|---|
| `(pch\|psh)_<model>.YYYY.MM[.das.D]_ver_YYYY.MM.DD.(csv\|xls\|xlsx)` | Prakiraan. `pch` gives Curah Hujan, `psh` Sifat Hujan. Model `prob` gives Probabilistik; any other model (det, ensMean, ...) is ordinary prakiraan. |
| `BlendGSMAP_POS.YYYYMM[decDD].(xls\|xlsx\|csv)` | Analisis. `decDD` sets the dasarian. No version. |
| `SPI1_Indo.YYYY.MM.csv` | Analisis SPI, always Bulanan. |
| any name containing `HTH` | HTH. No period in the name, so staff fill in the month. |

- Version day sets `dasarian_ver`: days 1-10 give 1, 11-20 give 2, 21-31 give 3.
- Columns decide which maps a file offers: `VAL` gives CH, `SH` gives SH dasarian, `CH` / `SH%` give ACH / ASH, `VALSPI` gives SPI, `b50`..`a150` give PROB.
- Pairing: a prakiraan and an analisis file with the same year, month and dasarian offer Verifikasi and Bias. The version comes from the prakiraan file.
- Several files for the same map and period: the newest version is used, the others are marked cadangan.
- A `psh` file wins over the `SH` column of a `pch` file for the same period.
- Unconfirmed: dasarian Probabilistik is assumed to be `pch_prob.YYYY.MM.das.D_ver_...`; no real example exists yet.

Test names, with expected results to write in the test:

- `pch_det.2025.04.das.3_ver_2025.04.21.csv` gives 2025 / 4 / das 3 / ver 2025 / 4 / 3, output `PCHdas_2025.04.das3_ver_2025.04.3`
- `pch_ensMean.2026.01_ver_2025.12.01.csv`
- `pch_prob.2026.02_ver_2026.01.01.csv`
- `BlendGSMAP_POS.202503dec02.xls`
- `BlendGSMAP_POS.202601.xls`
- `SPI1_Indo.2026.04.csv`
- `HTH.csv`
- `Draft.Argis.HTH.TR.csv`

Sample copies live in `_localrun/rel/` (git-excluded) and in the GitHub release `test_data`.

## Page design

One column of four numbered cards. Backgrounds: card `surface-2`, rows `surface-1`, dropdowns, checkboxes and buttons `surface-3`. Sizes in rem, `ch` and em so the browser font setting scales the page.

### 1. File data

- Upload area first, because the files decide everything below it. CSV, XLS, XLSX; several at once.
- One row per file: icon by detected jenis (colours as the code badges), file name cut at 18 characters plus "…", status pill: Siap, Mengunggah n% with a bar, "… perlu diisi", or Tidak dikenali.
- Header count: "n file · m siap".

### 2. Daftar peta

Built from the detection; one accordion row per map (`@gr.render`, since a Gradio Dataframe cannot hold dropdowns per cell).

Code badges: colour gives the source, icon gives what is mapped.

| Colour | Source | | Icon | Map |
|---|---|---|---|---|
| violet | Prakiraan | | rain cloud | CH |
| aqua | Analisis | | percent | SH |
| magenta | VER / BIAS | | line chart | SPI |
| yellow | NOR | | bar chart | PROB |
| orange | HTH | | check marks | VER (kuantitatif or kualitatif) |
| | | | difference arrows | BIAS |
| | | | calendar | NOR |
| | | | sun | HTH |

Row header, left to right: tick box, code badge, full title in words (for example "Prakiraan Sifat Hujan April Dasarian III 2025", no file name or version), status pill (Siap, or what is missing), chevron.

Open row, groups split by thin hairlines. Group titles 13 px medium; field labels 11 px muted with a small "otomatis" (aqua) or "diubah" (amber) tag. Dropdowns content-sized, 26 px tall.

| Group | Fields (width) |
|---|---|
| Peta | Jenis (190), Skala (100) |
| Data | File (330) + Kolom (90); for VER and BIAS also File pembanding (analisis) + Kolom |
| Periode | Tahun (80), Bulan (110), Dasarian (80) |
| Versi | Tahun, Bulan, Dasarian; hidden for ACH, ASH, SPI, NOR, HTH |
| Opsi | checkboxes: Layer laut, Dokumen Word, Ekspor CSV, PNG saja |

- Buttons: Kembalikan ke otomatis, Duplikat, Hapus.
- PNG saja greys out and unticks Layer laut and Dokumen Word. Bias greys out Dokumen Word.
- No global Opsi card; a "Terapkan opsi ke semua peta" button copies one row's Opsi to all.
- Below the list: "Tambah peta dari [file ▾]", including "Tanpa file" for Normal.
- Header count: "n peta · m siap".

### 3. Wilayah

- Tingkat: segmented switch, Provinsi | Kabupaten/kota. One level per batch, because `load_basemap()` (`static.py:199`) uses provinces only as soon as one name matches a province and silently drops kabupaten names.
- Pilihan: chosen wilayah as chips above a search box; × on a chip removes it. Typing shows up to 6 suggestions; Enter takes the top one. Names come from `idkab.feather`, so they always match exactly and fuzzy matching never decides.
- Default: Papua Barat, Papua Barat Daya. Nothing chosen: red "Pilih minimal satu wilayah" and the run is blocked.
- One wilayah for the whole batch. Passed to the package as the names joined with commas in `cfg.wilayah`.
- Gradio: a plain `gr.Dropdown(filterable=True)` for search plus a `gr.HTML` chip row (the built-in multiselect puts chips inside the box).

### 4. Hasil

- One row per ticked map: thumbnail (click opens the full map), code badge, title, a 22 px progress bar with the status written inside it, then one Proses/Ulangi button and an Unduh button.
- Bar states: Belum diproses and Menunggu (no fill), current step with percentage (blue; steps from `status_update()`: Memuat data, Interpolasi IDW, Menggambar peta, Menempel template, Narasi Gemini, Word), "Selesai · n dtk" (green), "Gagal: <one-line reason>" (red).
- Row button reads Proses before the map has run and Ulangi after; it re-runs only that map. Unduh gives the PNG, or a small ZIP when Word or CSV was ticked. Both are disabled while waiting or running; a failed map has only Ulangi.
- A failed map does not stop the batch.
- No overall bar; the header shows "x dari n selesai · y gagal".
- Queue: when another person's run is going, rows show "Antre: menunggu 1 proses lain".
- Bottom row: Proses semua peta on the left (becomes "Proses ulang semua" after a run, "Sedang memproses…" while running), then Unduh semua (ZIP) on the right with "Tersimpan 1 jam".

### Output names

| What | Name |
|---|---|
| PNG | `Peta Prakiraan Curah Hujan Bulan November Dasarian I 2026.png` |
| Word | `Laporan ... .docx` (already `report_filename()`, `word.py:177`) |
| CSV | `Data ... .csv` |
| One map's ZIP | `Prakiraan Curah Hujan Bulan November Dasarian I 2026.zip` |
| All results | `Hasil Peta 26 Oktober 2026 (5 peta).zip` |

When two files would get the same name, append the version: `... 2026 (versi 21 Oktober 2026).png`. Strip characters Windows cannot store, as `report_filename()` does. Renaming happens in `app.py`; the package's own names stay.

## Build order

1. ~~`Main/` changes and `Main/filenames.py` with its test; run `python -m pytest tests`.~~ Done, see Handoff.
2. Tag the release.
3. Space repo: `README.md`, `requirements.txt`, `app.py`; set the two secrets.
4. Try it with the real files in the Space, then with a second person queued at the same time.

## Handoff

### What step 1 built (all uncommitted on branch `claude/doc-narration-table`)

The same working tree also holds earlier, separate uncommitted work (narration table / Word table merging in `narasi.py`, `utils.py`, `word.py`, `map_creation.py`, `tests/test_narasi_word.py`, `CLAUDE.md`). Decide with the user how to split commits before committing; commit or push only when asked.

| File | What is there now |
|---|---|
| `Main/config.py` | `ask_upload = True`, `output_dir = None` (line 63), `kolom = None`, `kolom_pembanding = None`; Gemini key from `GEMINI_API_KEY` env first, then the existing decoded blob. `skip_logging = False` already existed (line 44). |
| `Main/logger.py` | `_get_token()` returns `os.environ["GITHUB_TOKEN"]` when set, else the existing decode. `log_execution` returns early when `cfg.skip_logging`. |
| `Main/upload.py` | `if not cfg.ask_upload: return` at the top of `upload_files()`. |
| `Main/word.py:275`, `Main/map_creation.py:563` | `output_dir = cfg.output_dir or ('/content' if is_colab() else os.getcwd())`. |
| `Main/utils.py:111` | `pick_column(df, kolom, *fallback)`: with `kolom` set, uses `standard_column(kolom)` or `kolom`, else raises an Indonesian `ValueError`; without it, first fallback present. Used by `arrange_table` (lines 497, 506). |
| `Main/processors.py` | `get_pch/psh/ach/ash/spi` call `pick_column(df, cfg.kolom, ...)` with the old fallback order; `bias_map` (~line 483) handles `cfg.kolom` / `cfg.kolom_pembanding` with the `_forecast` / `_analysis` merge suffixes. |
| `pyproject.toml` | Added `google-genai` and `docxcompose>=1.3.0` (word.py already imports it). |
| `Main/filenames.py` (new) | See API below. No Gradio import. |
| `tests/test_filenames.py` (new) | The 8 real names plus pairing/cadangan cases. |

Tests: 33 pass with `conda run -n work python -m pytest tests` (conda env **work**; the user already chose it for this project).

### `Main/filenames.py` API (for `app.py`)

- `MAPS`: map code → `(cfg.jenis_peta, tipe)`. Codes: PCH, PSH, PROB, ACH, ASH, SPI, VER, BIAS, HTH. (NOR / Normal has no file; the GUI adds it via "Tanpa file".)
- `parse_filename(name, columns=None)` → dict `file, role ('prakiraan'|'analisis'|'hth'), kind ('pch'|'psh'|'prob'|'analisis'|'spi'|'hth'), model, year, month, dasarian (None = Bulanan), year_ver, month_ver, dasarian_ver, version (y, m, day), offers {code: column}`; `None` when unrecognised. Pass the file's column names so `offers` is real; without them it guesses from the name.
- `detect_maps(parsed_files)` → list of map entries: `code, peta, tipe, skala, file, kolom, file_pembanding, kolom_pembanding, cadangan, year, month, dasarian, year_ver, month_ver, dasarian_ver, stem`. VER/BIAS appear when a PCH and an ACH share year/month/dasarian. Non-best duplicates have `cadangan=True`.
- `map_stem(entry)` → e.g. `PCHdas_2025.04.das3_ver_2025.04.3`. `clean_name`, `dasarian_of_day` are helpers.

How an entry becomes a run (for `app.py`): set `cfg.jenis_peta=peta`, `cfg.tipe_peta=[tipe]`, `cfg.skala_peta=skala`, period and version fields, `cfg.file_prakiraan` / `file_analisis` / `file_hth` by role (VER/BIAS: `file` is prakiraan, `file_pembanding` analisis), `cfg.kolom`, `cfg.kolom_pembanding`, `cfg.ask_upload=False`, `cfg.output_dir=<temp dir>`, `cfg.wilayah=', '.join(names)`; then `execute(peta, tipe, skala, month)` (`Main/__init__.py:66`) returns `map_data` with `image` (PIL). Progress via `Main.status.set_callback(fn)`.

### Useful things already in the repo

- `_localrun/run_local.py` (git-excluded): local end-to-end run on synthetic data, no upload dialog, `cfg.skip_logging = True`, writes `.docx` + `report.md`. Good model for driving the package without Colab. `--no-llm` skips Gemini.
- `_localrun/rel/`: copies of the 8 real sample files (also in GitHub release `test_data`).
- `Main/stress.py` also toggles `skip_logging`; use `skip_logging=True` for any local test so nothing is committed to `execution_log.csv` on GitHub.

### Knowledge and gotchas

- `load_basemap()` (`static.py:199-211`): if any wilayah name matches a province, only provinces are used and kabupaten names are silently dropped. Hence the one-Tingkat-per-batch rule in the Wilayah card.
- `cfg` is global class state: never run two maps at once (`default_concurrency_limit=1`); set every field before each `execute()`, and reset `kolom`/`kolom_pembanding` between maps.
- `upload_files()` is called unconditionally inside `execute()` (`__init__.py:85`), so `cfg.ask_upload=False` is mandatory in the Space.
- `word.py` calls `google.colab.files.download` only inside a `try/except ImportError`; harmless outside Colab.
- Probabilistik returns 6 sub-maps (`result_b50`..`result_a150`): Hasil card must show/zip all six for one PROB row.
- `png_only=True` disables hgt and Word; Bias has no Word document.
- The design mockups were inline chat widgets and were not saved; this file's "Page design" section is the authoritative spec. The user said visual placement can be fixed during the build.

### Open questions (ask the user, together, before step 3)

1. Dasarian Probabilistik file name is assumed `pch_prob.YYYY.MM.das.D_ver_...`; no real example yet.
2. Release tag name (`v1.1` suggested) and whether the `Main/` work is merged to `main` first.
3. Space name / HF account, and who sets the two secrets.

### Standing rules for this project (from the user's CLAUDE.md files)

- Python runs in conda env `work`: `conda run -n work python ...`; install with `conda install -n work` and update `C:\Users\thurs\conda-envs\work.yml`.
- Never replace or expose the obfuscated GitHub token or Gemini key.
- Ask before sending BMKG data or documents to OpenAI (Codex).
- Commit or push only when asked; edit files with Edit/Write, not sed.
- New logic with a branch/loop/parser leaves a small test.
