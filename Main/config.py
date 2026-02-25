# config.py
"""
Global configuration and constants for Staklim package.
"""

import os


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
def _resolve_cache_dir():
    """Determine the static file cache directory."""
    if is_colab():
        return "/content/static_data"
    env_override = os.environ.get("CREATE_MAP_IDW_CACHE_DIR")
    if env_override:
        return env_override
    return os.path.join(os.path.expanduser("~"), ".create_map_idw", "static_data")

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
    'arial.zip': f"{GITHUB_BASE}/arial.zip",
    'template_doc.docx': f"{GITHUB_BASE}/template_doc.docx",
    'ID_GRID.csv': f"{GITHUB_BASE}/ID_GRID.csv",
}



