# config.py
"""
Global configuration and constants for Staklim package.
"""

import os
import sys
import tempfile


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


def _is_suspicious_home(home_path):
    """Check if a home directory path looks like a system/program directory (Windows)."""
    if sys.platform != "win32":
        return False
    normalized = os.path.normcase(os.path.normpath(home_path))
    suspicious_fragments = [
        os.path.normcase("\\Program Files"),
        os.path.normcase("\\Program Files (x86)"),
        os.path.normcase("\\AppData\\Local\\Programs"),
        os.path.normcase("\\Windows\\"),
        os.path.normcase("\\ProgramData"),
    ]
    return any(fragment in normalized for fragment in suspicious_fragments)


def _get_windows_home_candidates():
    """Return candidate home directories on Windows, ordered by preference."""
    candidates = []
    userprofile = os.environ.get("USERPROFILE")
    if userprofile and not _is_suspicious_home(userprofile):
        candidates.append(userprofile)
    homedrive = os.environ.get("HOMEDRIVE", "")
    homepath = os.environ.get("HOMEPATH", "")
    if homedrive and homepath:
        combined = os.path.join(homedrive, homepath)
        if not _is_suspicious_home(combined) and combined not in candidates:
            candidates.append(combined)
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(localappdata)
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(appdata)
    candidates.append(tempfile.gettempdir())
    return candidates


def _resolve_cache_dir():
    """Determine the static file cache directory."""
    if is_colab():
        return "/content/static_data"
    env_override = os.environ.get("CREATE_MAP_IDW_CACHE_DIR")
    if env_override:
        return env_override

    home = os.path.expanduser("~")

    # On Windows, expanduser("~") can return unexpected paths (e.g. VS Code
    # install directory) when HOME env var is overridden by IDE terminals.
    if sys.platform == "win32" and (home == "~" or _is_suspicious_home(home)):
        for candidate in _get_windows_home_candidates():
            return os.path.join(candidate, ".create_map_idw", "static_data")
        return os.path.join(tempfile.gettempdir(), ".create_map_idw", "static_data")

    # Guard against expanduser returning "~" unchanged (no home configured)
    if home == "~":
        return os.path.join(tempfile.gettempdir(), ".create_map_idw", "static_data")

    return os.path.join(home, ".create_map_idw", "static_data")


def _test_directory_writable(path):
    """Test if a directory can be created and written to."""
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".write_test")
        with open(test_file, "wb") as f:
            f.write(b"test")
        os.remove(test_file)
        return True
    except OSError:
        return False


def validate_cache_dir():
    """
    Validate that CACHE_DIR is writable. If not, try fallback directories.
    Updates the module-level CACHE_DIR. Call before first file I/O.
    """
    global CACHE_DIR

    if _test_directory_writable(CACHE_DIR):
        return CACHE_DIR

    import warnings
    warnings.warn(
        f"Cache directory is not writable: {CACHE_DIR}. Trying fallback locations.",
        RuntimeWarning,
        stacklevel=2,
    )

    if sys.platform == "win32":
        candidates = _get_windows_home_candidates()
    else:
        candidates = [tempfile.gettempdir()]

    for base in candidates:
        candidate = os.path.join(base, ".create_map_idw", "static_data")
        if candidate == CACHE_DIR:
            continue
        if _test_directory_writable(candidate):
            CACHE_DIR = candidate
            return CACHE_DIR

    raise OSError(
        f"Cannot find a writable cache directory. "
        f"Tried: {CACHE_DIR} and fallbacks. "
        f"Set the CREATE_MAP_IDW_CACHE_DIR environment variable to a writable path."
    )


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



