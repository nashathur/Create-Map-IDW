# utils.py
"""
Utility functions: data loading, categorization, metrics, helpers.
"""

import os
import io
from io import BytesIO

import numpy as np
import pandas as pd
import geopandas as gpd
from PIL import Image
from numba import njit, prange

from .config import cfg, CACHE_DIR
from .status import update as status_update


# =============================================================================
# IMAGE HELPERS
# =============================================================================

def load_image_to_memory(source):
    """Load image fully into memory and close source."""
    if isinstance(source, (str, bytes, os.PathLike)):
        with Image.open(source) as img:
            return img.copy()
    elif isinstance(source, io.BytesIO):
        img = Image.open(source)
        img.load()
        img_copy = img.copy()
        img.close()
        source.close()
        return img_copy
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")


def get_cached_file(folder_id, filename):
    filepath = os.path.join(CACHE_DIR, filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Static file not found: {filename}")
    with open(filepath, 'rb') as f:
        return BytesIO(f.read())


# =============================================================================
# IDW INTERPOLATION
# =============================================================================

@njit(parallel=True)
def idw_numba(values, dists, idx, power):
    n = dists.shape[0]
    k = dists.shape[1]
    result = np.empty(n, dtype=np.float32)
    for i in prange(n):
        w_sum = 0.0
        val_sum = 0.0
        for j in range(k):
            w = 1.0 / (dists[i, j]**power + 1e-10)
            w_sum += w
            val_sum += w * values[idx[i, j]]
        result[i] = val_sum / w_sum
    return result


# =============================================================================
# DATA LOADING
# =============================================================================

_df_prakiraan_cache = None
_df_analisis_cache = None


def clear_data_cache():
    global _df_prakiraan_cache, _df_analisis_cache
    _df_prakiraan_cache = None
    _df_analisis_cache = None
    


_COLUMN_VARIANTS = {
    'LON': ('BUJUR', 'LON', 'LONGITUDE'),
    'LAT': ('LINTANG', 'LAT', 'LATITUDE'),
    'CH': ('CH', 'CURAH HUJAN', 'CURAH_HUJAN'),
    'VAL': ('VAL', 'VALUE', 'NILAI'),
    'SH': ('SH', 'SIFAT HUJAN', 'SIFAT_HUJAN'),
    'SH%': ('SH%', 'SH_PERSEN', 'SIFAT_HUJAN_PERSEN'),
    'SPI': ('SPI', 'VALSPI', 'VAL_SPI', 'NILAI_SPI'),
}


def standard_column(col):
    """Standard name for a column-name variant (e.g. 'valspi' -> 'SPI'), else the name unchanged."""
    cu = str(col).upper().strip()
    for std, variants in _COLUMN_VARIANTS.items():
        if cu in variants:
            return std
    return col


def _normalize_columns(df):
    """Normalize common column name variants to standard names."""
    col_map = {col: standard_column(col) for col in df.columns if standard_column(col) != col}
    if col_map:
        df = df.rename(columns=col_map)
    return df


def pick_column(df, kolom, *fallback):
    """Value column to map: *kolom* (cfg.kolom) when set, else the first *fallback* present.

    Returns None when nothing in *fallback* is present; raises when *kolom* is set but missing.
    """
    if kolom:
        for name in (standard_column(kolom), kolom):
            if name in df.columns:
                return name
        raise ValueError(
            f"Kolom '{kolom}' yang dipilih tidak ditemukan pada file. "
            f"Kolom yang tersedia: {list(df.columns)}."
        )
    return next((c for c in fallback if c in df.columns), None)


def _validate_lonlat(df, source_name):
    """Validate that LON and LAT columns exist in the DataFrame."""
    missing = [c for c in ('LON', 'LAT') if c not in df.columns]
    if missing:
        raise ValueError(
            f"Kolom {', '.join(missing)} tidak ditemukan pada file {source_name}. "
            f"Kolom yang tersedia: {list(df.columns)}. "
            f"Pastikan file memiliki kolom LON/BUJUR/LONGITUDE dan LAT/LINTANG/LATITUDE."
        )


def load_prakiraan(copy=False):
    global _df_prakiraan_cache

    if _df_prakiraan_cache is not None:
        status_update("Using cached prakiraan data")
        return _df_prakiraan_cache.copy() if copy else _df_prakiraan_cache

    if cfg.file_prakiraan is None:
        raise ValueError("cfg.file_prakiraan not set. Set it to the uploaded file path.")

    filepath = cfg.file_prakiraan
    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"File tidak ditemukan: {filepath}. "
            f"Pastikan path file sudah benar dan file sudah diupload."
        )

    status_update(f"Loading prakiraan file: {filepath}")
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.csv':
        df_prakiraan = pd.read_csv(filepath)
    elif ext in ('.xlsx', '.xls'):
        df_prakiraan = pd.read_excel(filepath)
    else:
        raise FileNotFoundError(f"Format file tidak didukung: {filepath}. Gunakan file .csv, .xlsx, atau .xls.")

    df_prakiraan = _normalize_columns(df_prakiraan)
    _validate_lonlat(df_prakiraan, filepath)

    df_prakiraan[['LON', 'LAT']] = df_prakiraan[['LON', 'LAT']].round(2)
    status_update(f"File {filepath} loaded successfully")

    _df_prakiraan_cache = df_prakiraan
    return df_prakiraan.copy() if copy else df_prakiraan


def load_analisis(copy=False):
    global _df_analisis_cache

    if _df_analisis_cache is not None:
        status_update("Using cached analisis data")
        return _df_analisis_cache.copy() if copy else _df_analisis_cache

    if cfg.file_analisis is None:
        raise ValueError("cfg.file_analisis not set. Set it to the uploaded file path.")

    filepath = cfg.file_analisis
    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"File tidak ditemukan: {filepath}. "
            f"Pastikan path file sudah benar dan file sudah diupload."
        )

    status_update(f"Loading analisis file: {filepath}")
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.csv':
        df_analisis = pd.read_csv(filepath)
    elif ext in ('.xlsx', '.xls'):
        df_analisis = pd.read_excel(filepath)
    else:
        raise FileNotFoundError(f"Format file tidak didukung: {filepath}. Gunakan file .csv, .xlsx, atau .xls.")

    df_analisis = _normalize_columns(df_analisis)
    _validate_lonlat(df_analisis, filepath)

    df_analisis[['LON', 'LAT']] = df_analisis[['LON', 'LAT']].round(2)
    status_update(f"File {filepath} loaded successfully")

    _df_analisis_cache = df_analisis
    return df_analisis.copy() if copy else df_analisis


# =============================================================================
# CATEGORIZATION
# =============================================================================

def categorize_ch(value):
    fallback_strategy = 'lowest'
    ranges = {
        1: (0, 100),
        2: (101, 300),
        3: (301, 500),
        4: (501, float('inf'))
    }

    if pd.isna(value) or value is None:
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 4
        elif fallback_strategy == 'middle':
            return 2
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    try:
        if np.isnan(value):
            if fallback_strategy == 'lowest':
                return 1
            elif fallback_strategy == 'highest':
                return 4
            elif fallback_strategy == 'middle':
                return 2
            elif fallback_strategy == 'zero_as_lowest':
                return 1
    except (TypeError, ValueError):
        pass

    if not isinstance(value, (int, float, np.integer, np.floating)):
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 4
        elif fallback_strategy == 'middle':
            return 2
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    if value < 0:
        return 1

    for category, (min_val, max_val) in ranges.items():
        if min_val <= value <= max_val:
            return category

    return 4


def categorize_index(value):
    fallback_strategy = 'lowest'
    ranges = {
        1: (0, 20),
        2: (21, 50),
        3: (51, 100),
        4: (101, 150),
        5: (151, 200),
        6: (201, 300),
        7: (301, 400),
        8: (401, 500),
        9: (501, float('inf'))
    }

    if pd.isna(value) or value is None:
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 9
        elif fallback_strategy == 'middle':
            return 5
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    try:
        if np.isnan(value):
            if fallback_strategy == 'lowest':
                return 1
            elif fallback_strategy == 'highest':
                return 9
            elif fallback_strategy == 'middle':
                return 5
            elif fallback_strategy == 'zero_as_lowest':
                return 1
    except (TypeError, ValueError):
        pass

    if not isinstance(value, (int, float, np.integer, np.floating)):
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 9
        elif fallback_strategy == 'middle':
            return 5
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    if value < 0:
        return 1

    for category, (min_val, max_val) in ranges.items():
        if min_val <= value <= max_val:
            return category

    return 9


# =============================================================================
# FORMATTING
# =============================================================================

def number_to_bulan(month):
    bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    return bulan[month]


def dasarian_romawi(number):
    das_romawi = {1: 'I', 2: 'II', 3: 'III'}
    return das_romawi[number]

def dasarian_to_date(dasarian):
    dasarian_date = {1: '11', 2: '21', 3: '1'}
    return dasarian_date[dasarian]
# =============================================================================
# METRICS
# =============================================================================

def cohen_kappa(y1, y2):
    y1 = np.asarray(y1)
    y2 = np.asarray(y2)
    n = len(y1)
    labels = np.unique(np.concatenate([y1, y2]))
    po = np.sum(y1 == y2) / n
    pe = sum((np.sum(y1 == c) * np.sum(y2 == c)) for c in labels) / (n * n)
    return (po - pe) / (1 - pe) if pe != 1 else 0.0

def calculate_metrics(forecast_series, actual_series, contingency_table):
    status_update("Calculating verification metrics")
    total = contingency_table.loc['All', 'All']

    correct = sum(contingency_table.loc[i, i] for i in contingency_table.index if i != 'All' and i in contingency_table.columns)
    accuracy = correct / total

    hss = cohen_kappa(actual_series, forecast_series)

    contingency_table_probabilistic = contingency_table.apply(lambda x: x / total, axis=0)
    n_categories = len(contingency_table.index) - 1

    pixoi = sum(contingency_table_probabilistic.iloc[i, -1] * contingency_table_probabilistic.iloc[-1, i] for i in range(n_categories))
    hits = sum(contingency_table_probabilistic.iloc[i, i] for i in range(n_categories))
    oi2 = sum(contingency_table_probabilistic.iloc[-1, i]**2 for i in range(n_categories))
    pss = (hits - pixoi) / (1 - oi2)
    status_update("Metrics calculation complete")
    return accuracy, hss, pss


# =============================================================================
# CATEGORY SCHEMES (shared by count_points, narasi and the Word table)
# =============================================================================
# Each scheme: (edges, [(label, range_text, extreme), ...]).
# Bin i holds edges[i-1] <= x < edges[i]; len(categories) == len(edges) + 1.
# 'extreme' categories are named in the narration/table whenever a kabupaten
# has a notable share of them, even if they are not dominant there.

CATEGORY_SCHEMES = {
    'CH_Bulanan': ([100, 300, 500], [
        ('Rendah', '0-100 mm', True),
        ('Menengah', '100-300 mm', False),
        ('Tinggi', '300-500 mm', False),
        ('Sangat Tinggi', '>500 mm', True),
    ]),
    'CH_Dasarian': ([50, 150, 300], [
        ('Rendah', '0-50 mm/das', True),
        ('Menengah', '50-150 mm/das', False),
        ('Tinggi', '150-300 mm/das', False),
        ('Sangat Tinggi', '>300 mm/das', True),
    ]),
    'SH': ([85, 115], [
        ('Bawah Normal', '<85%', True),
        ('Normal', '85%-115%', False),
        ('Atas Normal', '>115%', True),
    ]),
    'VERIF': ([1], [
        ('Tidak Sesuai', '', False),
        ('Sesuai', '', False),
    ]),
    'SPI': ([-2, -1.5, -1, 1, 1.5, 2], [
        ('Sangat Kering', '≤-2,0', True),
        ('Kering', '-2,0 s.d. -1,5', True),
        ('Agak Kering', '-1,5 s.d. -1,0', False),
        ('Normal', '-1,0 s.d. 1,0', False),
        ('Agak Basah', '1,0 s.d. 1,5', False),
        ('Basah', '1,5 s.d. 2,0', True),
        ('Sangat Basah', '≥2,0', True),
    ]),
    'BIAS': ([-100, -25, 25, 100], [
        ('Negatif Tinggi', '<-100 mm', True),
        ('Negatif', '-100 s.d. -25 mm', False),
        ('Netral', '-25 s.d. 25 mm', False),
        ('Positif', '25 s.d. 100 mm', False),
        ('Positif Tinggi', '>100 mm', True),
    ]),
    'HTH': ([1, 2, 3, 4, 5, 6], [
        ('Masih Ada Hujan', '', False),
        ('Sangat Pendek', '1-5 hari', False),
        ('Pendek', '6-10 hari', False),
        ('Menengah', '11-20 hari', False),
        ('Panjang', '21-30 hari', True),
        ('Sangat Panjang', '31-60 hari', True),
        ('Kekeringan Ekstrim', '>60 hari', True),
    ]),
}


def category_scheme(peta, tipe, skala):
    """Return (edges, categories) for a map, or None if it has no fixed scheme."""
    if peta == 'Verifikasi':
        key = 'VERIF'
    elif peta == 'Bias':
        key = 'BIAS'
    elif peta == 'HTH':
        key = 'HTH'
    elif peta == 'Probabilistik':
        return None
    elif tipe == 'SPI':
        key = 'SPI'
    elif tipe == 'Curah Hujan':
        key = 'CH_Dasarian' if skala == 'Dasarian' else 'CH_Bulanan'
    elif tipe == 'Sifat Hujan':
        key = 'SH'
    else:
        return None
    return CATEGORY_SCHEMES[key]


def count_points(data, value, levels):
    if value not in data.columns:
        raise ValueError(
            f"Kolom '{value}' tidak ditemukan saat menghitung titik per wilayah. "
            f"Kolom yang tersedia: {list(data.columns)}."
        )
    arr = pd.to_numeric(pd.Series(data[value].values), errors='coerce').dropna().values

    scheme = category_scheme(cfg.peta, cfg.tipe, cfg.skala)
    if scheme is not None:
        edges, categories = scheme
        labels = [c[0] for c in categories]
        idx = np.digitize(arr, edges, right=False)
        if scheme is CATEGORY_SCHEMES['SPI']:
            # SPI dry classes include their upper bound (-2,0 is Sangat Kering)
            idx = np.where(arr < 0, np.digitize(arr, edges, right=True), idx)
        counts_arr = np.bincount(idx, minlength=len(labels))
    else:
        bins = list(levels) + [np.inf]
        labels = [f"{levels[i]}-{levels[i+1]}" for i in range(len(levels)-1)] + [f">={levels[-1]}"]
        counts_arr, _ = np.histogram(arr, bins=bins)

    counts = dict(zip(labels, counts_arr.astype(int).tolist()))
    counts['total'] = int(sum(counts.values()))

    return counts


# =============================================================================
# ARRANGE TABLE (for verification)
# =============================================================================

def categorize_ch_vec(s):
    s = pd.to_numeric(s, errors='coerce').fillna(0).clip(lower=0)
    return np.digitize(s, bins=[0, 101, 301, 501], right=False)

def categorize_index_vec(s):
    s = pd.to_numeric(s, errors='coerce').fillna(0).clip(lower=0)
    return np.digitize(s, bins=[0, 21, 51, 101, 151, 201, 301, 401, 501], right=False)
    
def arrange_table():
    status_update("Loading data for verification")
    df_prakiraan = load_prakiraan(copy=True)
    df_analisis = load_analisis(copy=True)

    value = pick_column(df_prakiraan, cfg.kolom, 'CH', 'VAL')
    if value is None:
        raise ValueError(
            f"Kolom 'CH' atau 'VAL' tidak ditemukan pada file prakiraan. "
            f"Kolom yang tersedia: {list(df_prakiraan.columns)}. "
            f"Untuk verifikasi, file prakiraan harus memiliki kolom CH atau VAL."
        )
    status_update(f"Found {value} column in prakiraan")

    actual = pick_column(df_analisis, cfg.kolom_pembanding, 'CH')
    if actual is None:
        raise ValueError(
            f"Kolom 'CH' tidak ditemukan pada file analisis. "
            f"Kolom yang tersedia: {list(df_analisis.columns)}. "
            f"Untuk verifikasi, file analisis harus memiliki kolom CH (Curah Hujan)."
        )

    status_update("Processing dataframe categories")
    df_prakiraan['CH_category'] = categorize_ch_vec(df_prakiraan[value])
    df_analisis['CH_category'] = categorize_ch_vec(df_analisis[actual])
    df_prakiraan['index'] = categorize_index_vec(df_prakiraan[value])
    df_analisis['index'] = categorize_index_vec(df_analisis[actual])

    status_update("Merging forecast and analysis data")
    merged_df = pd.merge(df_prakiraan, df_analisis, on=['LON', 'LAT'], suffixes=('_forecast', '_analysis'))
    if merged_df.empty:
        raise ValueError(
            f"Tidak ada koordinat yang cocok antara file prakiraan dan analisis. "
            f"Prakiraan memiliki {len(df_prakiraan)} titik, analisis memiliki {len(df_analisis)} titik, "
            f"tetapi tidak ada pasangan LON/LAT yang sama. "
            f"Pastikan kedua file menggunakan koordinat stasiun yang sama."
        )

    merged_df['exact_match'] = (merged_df['CH_category_forecast'] == merged_df['CH_category_analysis']).astype(int)
    merged_df['exact_index'] = (merged_df['index_forecast'] == merged_df['index_analysis']).astype(int)
    merged_df['relaxed_index'] = ((merged_df['index_forecast'] - merged_df['index_analysis']).abs() <= 1).astype(int)
    status_update("Dataframe processing complete")

    return df_prakiraan, df_analisis, merged_df



