# stress.py
"""
Stress test module — randomizes cfg and generates synthetic data
to exercise the full map generation pipeline.
"""

import os
import traceback

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

from .config import cfg, CACHE_DIR
from .status import update as status_update

# ── Hardcoded config space ──────────────────────────────────────────────────

PROVINCES = [
    'Papua Barat', 'Papua Barat Daya', 'Papua', 'Papua Selatan',
    'Papua Tengah', 'Papua Pegunungan', 'Maluku', 'Maluku Utara',
    'Sulawesi Utara', 'Sulawesi Tengah', 'Sulawesi Selatan',
    'Sulawesi Tenggara', 'Sulawesi Barat', 'Gorontalo',
    'Kalimantan Barat', 'Kalimantan Tengah', 'Kalimantan Selatan',
    'Kalimantan Timur', 'Kalimantan Utara',
    'Jawa Barat', 'Jawa Tengah', 'Jawa Timur',
    'Banten', 'DKI Jakarta', 'DI Yogyakarta',
    'Bali', 'Nusa Tenggara Barat', 'Nusa Tenggara Timur',
    'Sumatera Utara', 'Sumatera Barat', 'Sumatera Selatan',
    'Riau', 'Jambi', 'Bengkulu', 'Lampung',
    'Kepulauan Bangka Belitung', 'Kepulauan Riau', 'Aceh',
]

JENIS_OPTIONS = [
    'Prakiraan', 'Analisis', 'Probabilistik',
    'Verifikasi', 'Normal', 'Bias', 'HTH',
]

STRESS_DIR = '/content/stress_test'


# ── Data generation ─────────────────────────────────────────────────────────

def _load_grid():
    """Load the ID_GRID.csv coordinate file from cache."""
    grid_path = os.path.join(CACHE_DIR, 'ID_GRID.csv')
    if not os.path.exists(grid_path):
        raise FileNotFoundError(
            f"ID_GRID.csv not found at {grid_path}. "
            "Make sure download_static_files() has been called and "
            "ID_GRID.csv is uploaded to the GitHub release."
        )
    return pd.read_csv(grid_path)


def _clip_grid_to_wilayah():
    """Load ID_GRID.csv, clip to cfg.wilayah basemap, return clipped coords.

    Returns a DataFrame with LON, LAT columns containing only points
    that fall within the chosen wilayah boundary.
    """
    from .static import get_basemap

    grid = _load_grid()
    basemaps = get_basemap(cfg.wilayah)
    shp_main = basemaps['shp_main']
    shp_crs = basemaps['crs']

    gdf = gpd.GeoDataFrame(
        grid,
        geometry=gpd.points_from_xy(grid.LON, grid.LAT),
        crs=shp_crs,
    )
    clipped = gpd.clip(gdf, shp_main)

    if clipped.empty:
        raise ValueError(
            f"No points from ID_GRID.csv fall within wilayah '{cfg.wilayah}'. "
            f"Total grid points: {len(grid)}, clipped: 0. "
            "Check that ID_GRID.csv has sufficient coverage for this region."
        )

    coords = clipped[['LON', 'LAT']].reset_index(drop=True)
    status_update(f"Clipped grid: {len(coords)} points in {cfg.wilayah}")
    return coords


def _generate_random_data(jenis, tipe, skala, rng):
    """Generate synthetic CSV data files for the given map type.

    1. Clips ID_GRID.csv to cfg.wilayah basemap
    2. Uses ALL clipped points
    3. Adds random value columns matching the expected schema
    4. Saves as CSV and sets cfg.file_prakiraan / cfg.file_analisis / cfg.file_hth
    """
    os.makedirs(STRESS_DIR, exist_ok=True)

    cfg.file_prakiraan = None
    cfg.file_analisis = None
    cfg.file_hth = None

    # Normal uses built-in data, no file needed
    if jenis == 'Normal':
        return

    coords = _clip_grid_to_wilayah()
    n = len(coords)

    # ── HTH ──
    if jenis == 'HTH':
        df = coords.copy()
        df['INDEKS_HTH'] = rng.randint(0, 7, size=n)
        path = os.path.join(STRESS_DIR, 'stress_hth.csv')
        df.to_csv(path, index=False)
        cfg.file_hth = path
        return

    # ── Prakiraan ──
    if jenis == 'Prakiraan':
        df = coords.copy()
        if tipe == 'Curah Hujan':
            if skala == 'Bulanan':
                df['VAL'] = rng.uniform(0, 1000, size=n).round(1)
            else:
                df['CH'] = rng.uniform(0, 300, size=n).round(1)
        else:  # Sifat Hujan
            if skala == 'Bulanan':
                df['VAL'] = rng.uniform(0, 500, size=n).round(1)
            else:
                df['SH'] = rng.uniform(0, 200, size=n).round(1)
        path = os.path.join(STRESS_DIR, 'stress_prakiraan.csv')
        df.to_csv(path, index=False)
        cfg.file_prakiraan = path
        return

    # ── Analisis ──
    if jenis == 'Analisis':
        df = coords.copy()
        if tipe == 'Curah Hujan':
            if skala == 'Bulanan':
                df['CH'] = rng.uniform(0, 1000, size=n).round(1)
            else:
                df['CH'] = rng.uniform(0, 300, size=n).round(1)
        else:  # Sifat Hujan
            if skala == 'Bulanan':
                df['SH%'] = rng.uniform(0, 500, size=n).round(1)
            else:
                df['SH%'] = rng.uniform(0, 200, size=n).round(1)
        path = os.path.join(STRESS_DIR, 'stress_analisis.csv')
        df.to_csv(path, index=False)
        cfg.file_analisis = path
        return

    # ── Probabilistik ──
    if jenis == 'Probabilistik':
        df = coords.copy()
        for col in ('b50', 'b100', 'b150', 'a50', 'a100', 'a150'):
            df[col] = rng.uniform(0, 100, size=n).round(1)
        path = os.path.join(STRESS_DIR, 'stress_prakiraan.csv')
        df.to_csv(path, index=False)
        cfg.file_prakiraan = path
        return

    # ── Verifikasi / Bias — need both prakiraan and analisis ──
    if jenis in ('Verifikasi', 'Bias'):
        df_p = coords.copy()
        df_p['VAL'] = rng.uniform(0, 1000, size=n).round(1)
        path_p = os.path.join(STRESS_DIR, 'stress_prakiraan.csv')
        df_p.to_csv(path_p, index=False)
        cfg.file_prakiraan = path_p

        df_a = coords.copy()
        df_a['CH'] = rng.uniform(0, 1000, size=n).round(1)
        path_a = os.path.join(STRESS_DIR, 'stress_analisis.csv')
        df_a.to_csv(path_a, index=False)
        cfg.file_analisis = path_a
        return


# ── Config randomizer ───────────────────────────────────────────────────────

def random_config(seed=None):
    """Randomize all cfg fields and generate matching synthetic data.

    Returns a dict summarizing the chosen configuration.
    """
    rng = np.random.RandomState(seed)

    jenis = rng.choice(JENIS_OPTIONS)

    # tipe_peta — valid per jenis
    if jenis in ('Prakiraan', 'Analisis'):
        tipe = rng.choice(['Curah Hujan', 'Sifat Hujan'])
    else:
        tipe = 'Curah Hujan'

    # skala_peta — Normal is always Bulanan
    if jenis == 'Normal':
        skala = 'Bulanan'
    else:
        skala = rng.choice(['Bulanan', 'Dasarian'])

    # wilayah
    wilayah = rng.choice(PROVINCES)

    # time settings
    year = int(rng.randint(2020, 2027))
    month = int(rng.randint(1, 13))
    dasarian = int(rng.randint(1, 4)) if skala == 'Dasarian' else None
    year_ver = int(rng.randint(2020, 2027))
    month_ver = int(rng.randint(1, 13))
    dasarian_ver = int(rng.randint(1, 4)) if skala == 'Dasarian' else None

    # boolean flags
    hgt = bool(rng.choice([True, False]))
    png_only = bool(rng.choice([True, False]))
    export_csv = bool(rng.choice([True, False]))
    create_word = bool(rng.choice([True, False]))
    verif_mode = rng.choice(['kuantitatif', 'kualitatif'])

    # Apply to cfg
    cfg.jenis_peta = jenis
    cfg.tipe_peta = [tipe]
    cfg.skala_peta = skala
    cfg.wilayah = wilayah
    cfg.year = year
    cfg.months = [month]
    cfg.month_ver = month_ver
    cfg.year_ver = year_ver
    cfg.dasarian = dasarian
    cfg.dasarian_ver = dasarian_ver
    cfg.hgt = hgt
    cfg.png_only = png_only
    cfg.export_csv = export_csv
    cfg.create_word = create_word
    cfg.verif_mode = verif_mode

    # Generate random data files (clips ID_GRID to wilayah first)
    _generate_random_data(jenis, tipe, skala, rng)

    config_summary = {
        'jenis': jenis,
        'tipe': tipe,
        'skala': skala,
        'wilayah': wilayah,
        'year': year,
        'month': month,
        'dasarian': dasarian,
        'year_ver': year_ver,
        'month_ver': month_ver,
        'dasarian_ver': dasarian_ver,
        'hgt': hgt,
        'png_only': png_only,
        'export_csv': export_csv,
        'create_word': create_word,
        'verif_mode': verif_mode,
    }
    return config_summary


# ── Stress test runner ──────────────────────────────────────────────────────

def run_stress_test():
    """Run N random iterations of the pipeline. Stops on first failure.

    Called by execute() when cfg.stress_test is True.
    Dispatches to processor functions directly (same logic as execute).
    """
    import time as _time
    from .utils import clear_data_cache
    from .map_creation import _export_csv
    from .template import overlay_image
    from .logger import log_execution
    from .word import arrange_word
    from .processors import (
        get_pch, get_psh, get_ach, get_ash,
        get_pch_prob, get_verif, get_normal, bias_map, get_hth,
    )

    n = 10
    cfg.skip_logging = True
    status_update(f"Starting stress test ({n} iterations)")

    for i in range(n):
        config = random_config(seed=i)
        jenis = config['jenis']
        tipe = config['tipe']
        skala = config['skala']
        month = config['month']

        status_update(
            f"[{i + 1}/{n}] {jenis} | {tipe} | {skala} | {config['wilayah']}"
        )

        try:
            start_time = _time.time()

            # Set runtime state
            cfg.peta = jenis
            cfg.tipe = tipe
            cfg.skala = skala
            cfg.month = month

            if cfg.png_only:
                cfg.hgt = False

            if jenis != 'HTH':
                clear_data_cache()

            # Dispatch to processor
            if jenis == 'Prakiraan':
                if tipe == 'Curah Hujan':
                    plot_data = get_pch()
                elif tipe == 'Sifat Hujan':
                    plot_data = get_psh()
            elif jenis == 'Analisis':
                if tipe == 'Curah Hujan':
                    plot_data = get_ach()
                elif tipe == 'Sifat Hujan':
                    plot_data = get_ash()
            elif jenis == 'Probabilistik':
                plot_data = get_pch_prob()
            elif jenis == 'Verifikasi':
                plot_data = get_verif()
            elif jenis == 'Normal':
                plot_data = get_normal()
            elif jenis == 'Bias':
                plot_data = bias_map()
            elif jenis == 'HTH':
                plot_data = get_hth()

            # Export CSV if enabled
            if cfg.export_csv:
                if jenis == 'Probabilistik':
                    for key in ('result_b50', 'result_b100', 'result_b150',
                                'result_a50', 'result_a100', 'result_a150'):
                        sub = plot_data.get(key)
                        if sub:
                            _export_csv(sub)
                else:
                    _export_csv(plot_data)

            # Overlay template (unless png_only)
            if not cfg.png_only:
                map_data = overlay_image(plot_data)
                if cfg.create_word:
                    arrange_word(map_data)

            plt.close('all')
            duration = _time.time() - start_time
            status_update(f"  [{i + 1}/{n}] OK ({duration:.1f}s)")

        except Exception as e:
            status_update(f"  [{i + 1}/{n}] FAILED: {e}")
            status_update(f"  Config: {config}")
            traceback.print_exc()
            plt.close('all')
            cfg.skip_logging = False
            return {
                'completed': i,
                'total': n,
                'failed_config': config,
                'error': str(e),
            }

    cfg.skip_logging = False
    status_update(f"Stress test complete: {n}/{n} passed")
    return {'completed': n, 'total': n, 'failed_config': None, 'error': None}
