# __init__.py
"""
Create-Map-IDW - Weather Map Generation Package for BMKG
"""

import time
import importlib as _importlib

# ── Eager imports (lightweight, no heavy deps) ───────────────────────────────
from .config import cfg, CACHE_DIR, is_colab
from .upload import upload_files
from .status import update as status_update

__version__ = "1.0.0"


# ── Lazy attribute access (PEP 562) ──────────────────────────────────────────
# Heavy modules are only loaded when their names are first accessed, e.g.
#   from Main import get_pch   →  triggers import of processors.py
#   from Main import create_map →  triggers import of map_creation.py

_LAZY_MAP = {
    'download_static_files':      ('.static', 'download_static_files'),
    'download_required_files':    ('.static', 'download_required_files'),
    'clear_basemap_cache':        ('.static', 'clear_basemap_cache'),
    'clear_data_cache':           ('.utils', 'clear_data_cache'),
    'load_prakiraan':             ('.utils', 'load_prakiraan'),
    'load_analisis':              ('.utils', 'load_analisis'),
    'create_map':                 ('.map_creation', 'create_map'),
    'clear_spatial_cache':        ('.map_creation', 'clear_spatial_cache'),
    'overlay_image':              ('.template', 'overlay_image'),
    'get_analysis':               ('.narasi', 'get_analysis'),
    'get_full_narration':         ('.narasi', 'get_full_narration'),
    'get_visual_interpretation':  ('.narasi', 'get_visual_interpretation'),
    'build_table_data':           ('.narasi', 'build_table_data'),
    'arrange_word':               ('.word', 'arrange_word'),
    'log_execution':              ('.logger', 'log_execution'),
    'get_pch':                    ('.processors', 'get_pch'),
    'get_psh':                    ('.processors', 'get_psh'),
    'get_ach':                    ('.processors', 'get_ach'),
    'get_ash':                    ('.processors', 'get_ash'),
    'get_pch_prob':               ('.processors', 'get_pch_prob'),
    'get_verif':                  ('.processors', 'get_verif'),
    'get_normal':                 ('.processors', 'get_normal'),
    'bias_map':                   ('.processors', 'bias_map'),
    'get_hth':                    ('.processors', 'get_hth'),
    'load_hth':                   ('.processors', 'load_hth'),
    'run_stress_test':            ('.stress', 'run_stress_test'),
    'random_config':              ('.stress', 'random_config'),
}


def __getattr__(name):
    if name in _LAZY_MAP:
        module_path, attr_name = _LAZY_MAP[name]
        mod = _importlib.import_module(module_path, __package__)
        val = getattr(mod, attr_name)
        globals()[name] = val          # cache so next access is instant
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── Main entry point ─────────────────────────────────────────────────────────

def execute(peta, tipe, skala, month):
    """Execute map generation based on configuration."""
    # Lazy imports — heavy deps load here on first call, not at package import
    from .static import download_static_files, download_required_files
    from .utils import clear_data_cache
    from .map_creation import _export_csv
    from .template import overlay_image
    from .logger import log_execution
    from .processors import (
        get_pch, get_psh, get_ach, get_ash, get_pch_prob,
        get_verif, get_normal, bias_map, get_hth,
    )
    from .stress import run_stress_test
    from .word import arrange_word

    if cfg.stress_test:
        download_static_files()
        return run_stress_test()

    upload_files()
    download_required_files(peta, tipe, skala)

    start_time = time.time()

    cfg.peta = peta
    cfg.tipe = tipe
    cfg.skala = skala
    cfg.month = month

    if not isinstance(month, int) or month < 1 or month > 12:
        raise ValueError(
            f"Nilai bulan tidak valid: {month}. Bulan harus berupa angka 1-12."
        )

    if cfg.dasarian is not None and cfg.dasarian not in (1, 2, 3):
        raise ValueError(
            f"Nilai dasarian tidak valid: {cfg.dasarian}. Dasarian harus bernilai 1, 2, atau 3."
        )

    if cfg.png_only:
        cfg.hgt = False

    if peta != 'HTH':
        clear_data_cache()

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

    if cfg.png_only or peta == 'Bias':
        if peta == 'Bias':
            try:
                from IPython.display import display
                display(plot_data['image'])
            except ImportError:
                pass
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
    'is_colab',
    'download_static_files',
    'download_required_files',
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
    'run_stress_test',
    'random_config',
]
