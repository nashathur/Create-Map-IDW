# __init__.py
"""
Weather Map Generation Package for BMKG
"""

from .config import cfg, CACHE_DIR
from .static import download_static_files, clear_basemap_cache
from .utils import load_prakiraan, load_analisis, clear_data_cache
from .map_creation import create_map
from .template import overlay_image
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

# Auto-download static files on import
download_static_files()

__version__ = "1.0.0"
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

