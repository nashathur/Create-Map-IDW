# config.py
"""
Global configuration and constants for Staklim package.
"""

import os
import tempfile
import warnings


def is_colab():
    """Return True if running inside Google Colab."""
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


class cfg:
    """Global configuration holder - set these before calling execute()"""
    # Map settings
    jenis_peta = None
    tipe_peta = None
    skala_peta = None
    
    # Time settings
    year = None
    year_ver = None
    months = None
    month_ver = None
    dasarian = None
    dasarian_ver = None
    
    # Region
    wilayah = None
    
    # Display options
    hgt = False
    export_csv = False

    # Stress test
    stress_test = False
    skip_logging = False
    
    # File paths (set after upload)
    file_prakiraan = None
    file_analisis = None
    file_hth = None
    
    # Runtime state (set by execute)
    peta = None
    tipe = None
    skala = None
    month = None

    png_only = False
    create_word = False
    verif_mode = 'kuantitatif'    #kuantitatif or kualitatif

    # Gemini API key (decoded at import time from obfuscated blob)
    gemini_api_key = None

def _decode(blob, key):
    import base64
    return bytes(b ^ key for b in base64.b64decode(blob)).decode()

cfg.gemini_api_key = _decode("GxMgOwkjG2s+DRQcMwg8FmMsbws4GxkdYggoNjAqLGoWFj1uY2of", 0x5A)

GITHUB_BASE = "https://github.com/nashathur/Create-Map-IDW/releases/download/v1.0"

def _is_writable_dir(path):
    """Check whether *path* can be used as a cache directory.

    If the directory exists, test writability directly.
    If it doesn't exist, walk up to the nearest existing ancestor
    and check that it is writable (so os.makedirs will succeed later).
    """
    try:
        if os.path.isdir(path):
            return os.access(path, os.W_OK)
        parent = path
        while parent and not os.path.exists(parent):
            prev = parent
            parent = os.path.dirname(parent)
            if parent == prev:
                return False
        return os.access(parent, os.W_OK) if parent else False
    except OSError:
        return False

def _resolve_cache_dir():
    """Determine the static file cache directory.

    Resolution order:
    1. Google Colab  -> /content/static_data
    2. Env var       -> CREATE_MAP_IDW_CACHE_DIR
    3. User home dir -> ~/.create_map_idw/static_data (if writable)
    4. Temp dir      -> <tempdir>/create_map_idw/static_data (fallback)
    """
    if is_colab():
        return "/content/static_data"
    env_override = os.environ.get("CREATE_MAP_IDW_CACHE_DIR")
    if env_override:
        return env_override
    primary = os.path.join(os.path.expanduser("~"), ".create_map_idw", "static_data")
    if _is_writable_dir(primary):
        return primary
    fallback = os.path.join(tempfile.gettempdir(), "create_map_idw", "static_data")
    warnings.warn(
        f"Default cache dir '{primary}' is not writable. "
        f"Falling back to '{fallback}'. "
        f"Set CREATE_MAP_IDW_CACHE_DIR to override.",
        stacklevel=2,
    )
    return fallback

CACHE_DIR = _resolve_cache_dir()

STATIC_FILES = {
    'idkab.feather': f"{GITHUB_BASE}/idkab.feather",
    'hgt1.tif': f"{GITHUB_BASE}/hgt1.tif",
    'DATA_CH_NORMAL_PAPBAR_1991_2020.xlsx': f"{GITHUB_BASE}/DATA_CH_NORMAL_PAPBAR_1991_2020.xlsx",
    'template_ch_bulanan.png': f"{GITHUB_BASE}/template_ch_bulanan.png",
    'template_ch_das.png': f"{GITHUB_BASE}/template_ch_das.png",
    'template_sh.png': f"{GITHUB_BASE}/template_sh.png",
    'template_verifikasi.png': f"{GITHUB_BASE}/template_verifikasi.png",
    'template_probabilistik.png': f"{GITHUB_BASE}/template_probabilistik.png",
    'template_hth.png': f"{GITHUB_BASE}/template_hth.png",
    'ARIAL.TTF': f"{GITHUB_BASE}/ARIAL.TTF",
    'ARIALBD.TTF': f"{GITHUB_BASE}/ARIALBD.TTF",
    'ArialMdm.ttf': f"{GITHUB_BASE}/ArialMdm.ttf",
    'arial.zip': f"{GITHUB_BASE}/arial.zip",
    'template_doc.docx': f"{GITHUB_BASE}/template_doc.docx",
    'ID_GRID.csv': f"{GITHUB_BASE}/ID_GRID.csv",
}



