# __init__.py
"""
Create-Map-IDW - Weather Map Generation Package for BMKG
"""

from .config import cfg, CACHE_DIR
from .static import download_static_files, clear_basemap_cache
from .utils import load_prakiraan, load_analisis, clear_data_cache
from .map_creation import create_map, clear_spatial_cache
from .template import overlay_image
from .upload import upload_files
from .status import update as status_update
from .narasi import get_analysis, get_full_narration, get_visual_interpretation, build_table_data
from .word import arrange_word
import time
from .logger import log_execution
from .processors import (
    get_pch,
    get_psh,
    get_ach,
    get_ash,
    get_pch_prob,
    get_verif,
    get_normal,
    bias_map,
    get_hth,
    load_hth,
)

__version__ = "1.0.0"


def _export_csv(plot_data):
    """Export station-level data from plot_data as CSV and auto-download in Colab."""
    import os
    import pandas as pd

    joined_gdf = plot_data.get('joined_gdf')
    if joined_gdf is None or len(joined_gdf) == 0:
        print("No data available for CSV export.")
        return

    value_col = plot_data.get('value')
    keep_cols = ['LON', 'LAT']
    if value_col and value_col in joined_gdf.columns:
        keep_cols.append(value_col)
    if 'PROVINSI' in joined_gdf.columns:
        keep_cols.append('PROVINSI')
    if 'KABUPATEN' in joined_gdf.columns:
        keep_cols.append('KABUPATEN')

    # Include any other numeric data columns present (but not index columns from sjoin)
    skip = {'index_right', 'index_left', 'geometry'}
    for col in joined_gdf.columns:
        if col not in keep_cols and col not in skip:
            if joined_gdf[col].dtype.kind in ('f', 'i'):
                keep_cols.append(col)

    export_df = joined_gdf[[c for c in keep_cols if c in joined_gdf.columns]].copy()
    export_df = export_df.reset_index(drop=True)

    png_name = plot_data.get('file_name', 'export')
    csv_name = os.path.splitext(png_name)[0] + '.csv'
    csv_path = os.path.join('/content', csv_name)

    export_df.to_csv(csv_path, index=False)
    print(f"CSV exported: {csv_name} ({len(export_df)} rows)")

    try:
        from google.colab import files
        files.download(csv_path)
    except ImportError:
        print(f"Not running in Google Colab. CSV saved to: {csv_path}")


def execute(peta, tipe, skala, month):
    """Execute map generation based on configuration."""
    start_time = time.time()
    download_static_files()

    cfg.peta = peta
    cfg.tipe = tipe
    cfg.skala = skala
    cfg.month = month

    if cfg.png_only:
        cfg.hgt = False
        
    if peta != 'HTH':
        clear_data_cache()
    
    print(f"Processing: {peta} - {tipe} - {skala} - Month {month}")
    
    if peta == 'Prakiraan':
        if tipe == 'Curah Hujan':
            status_update("Getting PCH data...")
            plot_data = get_pch()
        elif tipe == 'Sifat Hujan':
            status_update("Getting PSH data...")
            plot_data = get_psh()
        else:
            raise ValueError(f"Unknown tipe: {tipe}")
    elif peta == 'Analisis':
        if tipe == 'Curah Hujan':
            status_update("Getting ACH data...")
            plot_data = get_ach()
        elif tipe == 'Sifat Hujan':
            status_update("Getting ASH data...")
            plot_data = get_ash()
        else:
            raise ValueError(f"Unknown tipe: {tipe}")
    elif peta == 'Probabilistik':
        status_update("Getting probabilistic data...")
        plot_data = get_pch_prob()
    elif peta == 'Verifikasi':
        status_update("Getting verifikasi data...")
        plot_data = get_verif()
    elif peta == 'Normal':
        status_update("Getting normal data...")
        plot_data = get_normal()
    elif peta == 'Bias':
        status_update("Creating bias map...")
        plot_data = bias_map()
    elif peta == 'HTH':
        status_update("Getting HTH data...")
        plot_data = get_hth()
    else:
        raise ValueError(f"Unknown peta type: {peta}")
        
    if cfg.export_csv:
        if peta == 'Probabilistik':
            for key in ('result_b50', 'result_b100', 'result_b150', 'result_a50', 'result_a100', 'result_a150'):
                sub = plot_data.get(key)
                if sub:
                    _export_csv(sub)
        else:
            _export_csv(plot_data)

    if cfg.png_only:
        output_filename = plot_data.get('file_name', 'png_only')
        status_update(f"Completed: {output_filename}")
        duration = time.time() - start_time
        log_execution(cfg, output_filename, duration)
        return plot_data

    status_update("Overlaying image template...")
    map_data = overlay_image(plot_data)
    output_filename = map_data['file_name']

    status_update(f"Completed: {output_filename}")
    duration = time.time() - start_time
    log_execution(cfg, output_filename, duration)

    if cfg.create_word:
        arrange_word(map_data)

    return map_data
    


__all__ = [
    'cfg',
    'CACHE_DIR',
    'download_static_files',
    'clear_basemap_cache',
    'clear_data_cache',
    'load_prakiraan',
    'load_analisis',
    'load_hth',
    'create_map',
    'overlay_image',
    'execute',
    'get_pch',
    'get_psh',
    'get_ach',
    'get_ash',
    'get_pch_prob',
    'get_verif',
    'get_normal',
    'bias_map',
    'get_hth',
    'status_update',
    'get_analysis',
    'get_full_narration',
    'get_visual_interpretation',
    'build_table_data',
    'arrange_word',
]






