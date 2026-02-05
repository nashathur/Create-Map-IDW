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
from sklearn.metrics import cohen_kappa_score

from .config import cfg, CACHE_DIR


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
    print("Data cache cleared")


def load_prakiraan(copy=False):
    global _df_prakiraan_cache

    if _df_prakiraan_cache is not None:
        print(f"\rUsing cached prakiraan data", end="", flush=True)
        return _df_prakiraan_cache.copy() if copy else _df_prakiraan_cache

    if cfg.file_prakiraan is None:
        raise ValueError("cfg.file_prakiraan not set. Set it to the uploaded file path.")

    filepath = cfg.file_prakiraan
    if filepath.endswith('.csv'):
        df_prakiraan = pd.read_csv(filepath)
    elif filepath.endswith('.xlsx') or filepath.endswith('.xls'):
        df_prakiraan = pd.read_excel(filepath)
    else:
        raise FileNotFoundError(f"Unsupported file format: {filepath}")

    df_prakiraan[['LON', 'LAT']] = df_prakiraan[['LON', 'LAT']].round(2)
    print(f"\rFile {filepath} loaded successfully", end="", flush=True)

    _df_prakiraan_cache = df_prakiraan
    return df_prakiraan.copy() if copy else df_prakiraan


def load_analisis(copy=False):
    global _df_analisis_cache

    if _df_analisis_cache is not None:
        print(f"\rUsing cached analisis data", end="", flush=True)
        return _df_analisis_cache.copy() if copy else _df_analisis_cache

    if cfg.file_analisis is None:
        raise ValueError("cfg.file_analisis not set. Set it to the uploaded file path.")

    filepath = cfg.file_analisis
    if filepath.endswith('.csv'):
        df_analisis = pd.read_csv(filepath)
    elif filepath.endswith('.xlsx') or filepath.endswith('.xls'):
        df_analisis = pd.read_excel(filepath)
    else:
        raise FileNotFoundError(f"Unsupported file format: {filepath}")

    df_analisis[['LON', 'LAT']] = df_analisis[['LON', 'LAT']].round(2)
    print(f"\rFile {filepath} loaded successfully", end="", flush=True)

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


# =============================================================================
# METRICS
# =============================================================================

def calculate_metrics(forecast_series, actual_series, contingency_table):
    total = contingency_table.loc['All', 'All']

    correct = sum(contingency_table.loc[i, i] for i in contingency_table.index if i != 'All' and i in contingency_table.columns)
    accuracy = correct / total

    hss = cohen_kappa_score(actual_series, forecast_series)

    contingency_table_probabilistic = contingency_table.apply(lambda x: x / total, axis=0)
    n_categories = len(contingency_table.index) - 1

    pixoi = sum(contingency_table_probabilistic.iloc[i, -1] * contingency_table_probabilistic.iloc[-1, i] for i in range(n_categories))
    hits = sum(contingency_table_probabilistic.iloc[i, i] for i in range(n_categories))
    oi2 = sum(contingency_table_probabilistic.iloc[-1, i]**2 for i in range(n_categories))
    pss = (hits - pixoi) / (1 - oi2)
    return accuracy, hss, pss


def count_points(data, value, levels):
    arr = data[value].values

    if cfg.tipe == 'Curah Hujan':
        if cfg.skala == 'Bulanan':
            bins = [0, 100, 300, 500, np.inf]
            labels = ['Rendah', 'Menengah', 'Tinggi', 'Sangat Tinggi']
        else:
            bins = [0, 50, 150, 300, np.inf]
            labels = ['Rendah', 'Menengah', 'Tinggi', 'Sangat Tinggi']
    elif cfg.tipe == 'Sifat Hujan':
        bins = [0, 85, 115, np.inf]
        labels = ['Bawah Normal', 'Normal', 'Atas Normal']
    else:
        bins = levels + [np.inf]
        labels = [f"{levels[i]}-{levels[i+1]}" for i in range(len(levels)-1)] + [f">={levels[-1]}"]

    counts_arr, _ = np.histogram(arr, bins=bins)
    counts = dict(zip(labels, counts_arr.astype(int).tolist()))
    counts['total'] = len(arr)

    return counts


# =============================================================================
# ARRANGE TABLE (for verification)
# =============================================================================

def arrange_table():
    print("\rLoading data", end="", flush=True)
    df_prakiraan = load_prakiraan(copy=True)
    df_analisis = load_analisis(copy=True)

    if 'CH' in df_prakiraan.columns:
        value = 'CH'
        print("found CH")
    elif 'VAL' in df_prakiraan.columns:
        value = 'VAL'
        print("found VAL")
    else:
        raise ValueError("Neither CH nor VAL found in the DataFrame")
    
    print("\rProcessing dataframe", end="", flush=True)
    df_prakiraan['CH_category'] = df_prakiraan[value].apply(categorize_ch)
    df_analisis['CH_category'] = df_analisis['CH'].apply(categorize_ch)
    df_prakiraan['index'] = df_prakiraan[value].apply(categorize_index)
    df_analisis['index'] = df_analisis['CH'].apply(categorize_index)

    merged_df = pd.merge(df_prakiraan, df_analisis, on=['LON', 'LAT'], suffixes=('_forecast', '_analysis'))

    merged_df['exact_match'] = (merged_df['CH_category_forecast'] == merged_df['CH_category_analysis']).astype(int)
    merged_df['exact_index'] = (merged_df['index_forecast'] == merged_df['index_analysis']).astype(int)
    merged_df['relaxed_index'] = ((merged_df['index_forecast'] - merged_df['index_analysis']).abs() <= 1).astype(int)
    print("\rDataframe done", end="", flush=True)

    return df_prakiraan, df_analisis, merged_df
