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
from .narasi import get_analysis
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

download_static_files()

__version__ = "1.0.0"


def execute(peta, tipe, skala, month):
    """Execute map generation based on configuration."""
    start_time = time.time()

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
    'arrange_word',
]






