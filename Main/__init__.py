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
from .processors import (
    get_pch,
    get_psh,
    get_ach,
    get_ash,
    get_pch_prob,
    get_verif_quan,
    get_verif_qual,
    get_normal,
    bias_map,
)

download_static_files()

__version__ = "1.0.0"


def execute(peta, tipe, skala, month):
    """Execute map generation based on configuration."""
    cfg.peta = peta
    cfg.tipe = tipe
    cfg.skala = skala
    cfg.month = month

    if cfg.png_only:
        cfg.hgt = False
        
    clear_data_cache()
    
    print(f"\n{'='*60}")
    print(f"Processing: {peta} - {tipe} - {skala} - Month {month}")
    print(f"{'='*60}")
    
    if peta == 'Prakiraan':
        if tipe == 'Curah Hujan':
            plot_data = get_pch()
        elif tipe == 'Sifat Hujan':
            plot_data = get_psh()
        else:
            raise ValueError(f"Unknown tipe: {tipe}")
            
    elif peta == 'Analisis':
        if tipe == 'Curah Hujan':
            plot_data = get_ach()
        elif tipe == 'Sifat Hujan':
            plot_data = get_ash()
        else:
            raise ValueError(f"Unknown tipe: {tipe}")
            
    elif peta == 'Probabilistik':
        plot_data = get_pch_prob()
        
    elif peta == 'Verifikasi':
        if skala == 'Bulanan':
            plot_data = get_verif_qual()
        else:
            plot_data = get_verif_quan()
            
    elif peta == 'Normal':
        plot_data = get_normal()
        
    elif peta == 'Bias':
        plot_data = bias_map()
        
    else:
        raise ValueError(f"Unknown peta type: {peta}")
    
    if cfg.png_only:
        from IPython.display import display
        if peta == 'Probabilistik':
            for key in ['result_b50','result_b100','result_b150','result_a50','result_a100','result_a150']:
                display(plot_data[key]['image'])
        else:
            display(plot_data['image'])
        print(f"\nCompleted: {plot_data.get('file_name','png_only')}")
        return plot_data
    
    map_data = overlay_image(plot_data)
    
    print(f"\nCompleted: {map_data['file_name']}")
    return map_data


__all__ = [
    'cfg',
    'CACHE_DIR',
    'download_static_files',
    'clear_basemap_cache',
    'clear_data_cache',
    'load_prakiraan',
    'load_analisis',
    'create_map',
    'overlay_image',
    'execute',
    'get_pch',
    'get_psh',
    'get_ach',
    'get_ash',
    'get_pch_prob',
    'get_verif_quan',
    'get_verif_qual',
    'get_normal',
    'bias_map',
]





