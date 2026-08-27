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
    'template_spi.png': f"{GITHUB_BASE}/template_spi.png",
    'ARIAL.TTF': f"{GITHUB_BASE}/ARIAL.TTF",
    'ARIALBD.TTF': f"{GITHUB_BASE}/ARIALBD.TTF",
    'ArialMdm.ttf': f"{GITHUB_BASE}/ArialMdm.ttf",
    'template_doc.docx': f"{GITHUB_BASE}/template_doc.docx",
    'ID_GRID.csv': f"{GITHUB_BASE}/ID_GRID.csv",
}


# =============================================================================
# INTERPOLASI
# =============================================================================
# Semua parameter interpolasi ada di sini -- tidak perlu membuka map_creation.py.
# Sengaja TIDAK diletakkan di cfg: metode yang benar ditentukan oleh bentuk data
# di dalam file, bukan oleh preferensi operator. 'auto' mendeteksi sendiri;
# override di bawah hanya untuk memaksa satu metode atau membandingkan dua.

INTERP = {
    'method':             'auto',  # 'auto' | 'idw' | 'regular' | 'nearest'
    'power':              2,       # eksponen jarak IDW (default ArcGIS: 2)
    'n_neighbors':        12,      # jumlah tetangga IDW (default ArcGIS: 12)
    'smoothing':          0.0,     # peredam puncak di titik stasiun
    'gaussian_sigma':     0.0,     # filter halus setelah interpolasi; 0 = mati
    'render_mode':        'pcolormesh',  # 'pcolormesh' | 'contourf'
    'discrete_threshold': 10,      # <= n nilai unik -> paksa 'nearest'
    'spacing_tolerance':  1e-3,    # toleransi deteksi grid teratur
}

# Ukuran sel grid keluaran dalam derajat (~240 m di ekuator).
GRID = {'cell_size': 0.0021648361216}


# =============================================================================
# RENDER (ukuran figure, font, garis)
# =============================================================================

RENDER = {
    'figsize':              (20, 20),
    'dpi':                  200,
    'buffer_frac':          0.05,
    'kabupaten_fontsize':   26,
    'label_tick_fontsize':  25,
    'tick_width':           3,
    'tick_length':          10,
    'padding_label':        20,
    'spine_linewidth':      4,
    'metrics_fontsize':     32,
}

# Peta Probabilistik memakai panel kecil, jadi font/garis diperbesar.
RENDER_PROB = {
    'label_tick_fontsize':  45,
    'tick_width':           7,
    'tick_length':          20,
    'padding_label':        30,
    'spine_linewidth':      7,
}


# =============================================================================
# PITA WARNA PETA (display)
# =============================================================================
# Sengaja lebih halus daripada KLASIFIKASI di bawah: ini gradasi warna peta,
# bukan kategori narasi. Kunci ('Curah Hujan', skala) karena levelnya berbeda
# per skala; jenis peta lain memakai kunci string tunggal.

LEVELS = {
    ('Curah Hujan', 'Bulanan'):  [0, 20, 50, 100, 150, 200, 300, 400, 500, 1000],
    ('Curah Hujan', 'Dasarian'): [0, 10, 20, 50, 75, 100, 150, 200, 300, 1000],
    'Sifat Hujan':   [0, 30, 50, 85, 115, 150, 200, 500],
    'SPI':           [-10, -2, -1.5, -1, 1, 1.5, 2, 10],
    'Probabilistik': [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    'Verifikasi':    [0, 1],
    'Normal':        [0, 20, 50, 100, 150, 200, 300, 400, 500, 1000],
    'Bias':          [-1000, -500, -400, -300, -200, -100, -50, -25, 0,
                      25, 50, 100, 200, 300, 400, 500, 1000],
}

# CATATAN: 'Curah Hujan' dan 'Normal' MIRIP tapi TIDAK identik (mis. #340900 vs
# #340A00). Perbedaan ini ada di kode asli dan sengaja dipertahankan.
COLORS = {
    'Curah Hujan': ['#340900', '#8E2800', '#DC6200', '#EFA800', '#eae100',
                    '#e0fe7c', '#8bd48b', '#369134', '#00450c'],
    'Sifat Hujan': ['#4a1600', '#a85b00', '#f3c40f', '#ffff00', '#8bb700',
                    '#238129', '#00460e'],
    'SPI': [
        '#730000',  # Sangat Kering  (<= -2)
        '#FF0000',  # Kering         (-2 .. -1.5)
        '#E69800',  # Agak Kering    (-1.5 .. -1)
        '#FFFFBE',  # Normal         (-1 .. 1)
        '#7FCC00',  # Agak Basah     (1 .. 1.5)
        '#267300',  # Basah          (1.5 .. 2)
        '#00B0F0',  # Sangat Basah   (>= 2)
    ],
    'Probabilistik': ['#ffffff', '#0000fe', '#007fff', '#01ffff', '#7eff80',
                      '#fffe01', '#ffc800', '#ff7f00', '#ff3f01', '#b10101'],
    'Verifikasi': ['white', 'dodgerblue'],
    'Normal': ['#340A00', '#8E2800', '#DC6200', '#EFA800', '#EBE100',
               '#E0FD68', '#8AD58B', '#369135', '#00460C'],
    'Bias': ['#af3547', '#c74651', '#dc5b5e', '#ea7972', '#f19580', '#f5ae8a',
             '#f7c69a', '#ffffff', '#ffffff', '#bbe3f0', '#95d8ee', '#62cdef',
             '#34c0ec', '#0cafe4', '#0094d2', '#0074bc'],
    'basemap_fill': '#FFFDE7',
}


# =============================================================================
# KATEGORI UNTUK PERHITUNGAN & NARASI
# =============================================================================
# Sengaja lebih kasar daripada LEVELS di atas: 9 pita warna enak dibaca di peta,
# 4 kategori enak dibaca di kalimat. Pemisahan ini disengaja.
#
# 'batas'     -> tepi bin untuk count_points(); bin terakhir terbuka (np.inf).
# 'nama'      -> label kategori.
# 'deskripsi' -> kata-kata untuk prompt AI, ditulis tangan agar bisa diatur
#                bebas -- tapi sekarang duduk tepat di sebelah angkanya, jadi
#                mengubah satu tanpa yang lain sulit terlewat.

KLASIFIKASI = {
    ('Curah Hujan', 'Bulanan'): {
        'batas':     [0, 100, 300, 500],
        'nama':      ['Rendah', 'Menengah', 'Tinggi', 'Sangat Tinggi'],
        'deskripsi': ['0-100 mm', '100-300 mm', '300-500 mm', '>500 mm'],
    },
    ('Curah Hujan', 'Dasarian'): {
        'batas':     [0, 50, 150, 300],
        'nama':      ['Rendah', 'Menengah', 'Tinggi', 'Sangat Tinggi'],
        'deskripsi': ['0-50 mm/das', '50-150 mm/das', '150-300 mm/das', '>300 mm/das'],
    },
    ('Sifat Hujan', 'Bulanan'): {
        'batas':     [0, 85, 115],
        'nama':      ['Bawah Normal', 'Normal', 'Atas Normal'],
        'deskripsi': ['0%-84%', '85%-115%', '>116%'],
    },
    ('Sifat Hujan', 'Dasarian'): {
        'batas':     [0, 85, 115],
        'nama':      ['Bawah Normal', 'Normal', 'Atas Normal'],
        'deskripsi': ['0%-84%', '85%-115%', '>116%'],
    },
    ('Verifikasi', 'Bulanan'): {
        'batas':     [0, 1],
        'nama':      ['Tidak Sesuai', 'Sesuai'],
        'deskripsi': ['0', '1'],
    },
    ('Verifikasi', 'Dasarian'): {
        'batas':     [0, 1],
        'nama':      ['Tidak Sesuai', 'Sesuai'],
        'deskripsi': ['0', '1'],
    },
    ('Normal', 'Bulanan'): {
        'batas':     [0, 100, 300, 500],
        'nama':      ['Rendah', 'Menengah', 'Tinggi', 'Sangat Tinggi'],
        'deskripsi': ['0-100 mm', '100-300 mm', '300-500 mm', '>500 mm'],
    },
}

# Peta yang tidak punya kategori diskrit: narasi memakai satu kalimat penjelas.
KLASIFIKASI_TEKS = {
    ('Bias', 'Bulanan'):  "Selisih antara prakiraan dan analisis curah hujan (mm)",
    ('Bias', 'Dasarian'): "Selisih antara prakiraan dan analisis curah hujan (mm)",
    ('Probabilistik', 'Bulanan'): "Peluang curah hujan per kategori ambang batas (50mm, 100mm, 150mm)",
    ('HTH', 'Dasarian'): "Jumlah hari tanpa hujan berturut-turut",
}


# =============================================================================
# HTH (scatter map)
# =============================================================================

HTH_KLASIFIKASI = {
    1: 'Sangat Pendek',
    2: 'Pendek',
    3: 'Menengah',
    4: 'Panjang',
    5: 'Sangat Panjang',
    6: 'Kekeringan Ekstrim',
}

HTH_COLORS = {
    0: '#2E8B57',
    1: '#90EE90',
    2: '#FFD700',
    3: '#FF8C00',
    4: '#8B4513',
    5: '#FFB6C1',
    6: '#FF0000',
}

SCATTER_SIZES = {
    0: 300,
    1: 550,
    2: 600,
    3: 600,
    4: 600,
    5: 600,
}


# =============================================================================
# TEMPLATE (komposisi PNG)
# =============================================================================
# PANEL_WIDTH/TEXT_PADDING sebelumnya dideklarasikan tiga kali di template.py.

TEMPLATE = {
    'panel_width':  996,
    'text_padding': 40,          # 40px kiri-kanan
    'paste_dimension': (2379, 2392),
    'paste_location':  (40, 42),
    # Filter downscale PIL. BICUBIC adalah perilaku lama (nilai bawaan PIL saat
    # argumen resample tidak diberikan) dan beraliasing saat gambar diperkecil
    # dari ~4000px ke 2379px. LANCZOS jauh lebih bersih untuk reduksi -- tapi
    # mengubahnya MENGUBAH OUTPUT, jadi defaultnya masih BICUBIC di sini.
    # Ganti ke 'LANCZOS' saat tahap perbandingan visual.
    'resample': 'BICUBIC',
    'fonts': {
        'title':       52,
        'subtitle':    46,
        'line1':       46,
        'line2':       46,
        'line3':       40,
        'skala':       46,
        'periode':     46,
        'update':      36,
        'versi':       32,
        'scaled_min':  24,
        'scaled_max':  40,
        'scaled_max_line4': 36,
        'scaled_max_spi':   44,
    },
}


# =============================================================================
# NARASI / GEMINI
# =============================================================================

GEMINI = {
    'models': {
        'analysis': [
            'gemini-3-flash-preview',
            'gemini-2.5-flash',
            'gemini-2.5-flash-lite',
        ],
        'visual': [
            'gemini-3-flash-preview',
            'gemini-2.5-flash',
            'gemini-2.5-flash-lite',
        ],
    },
    'retry': {
        'max_retries':   3,
        'initial_delay': 2.0,
    },
}

NARASI = {
    'high_priority_threshold':  5.0,
    'close_category_threshold': 10.0,   # selisih dalam poin persen
}


# =============================================================================
# WORD & DOWNLOAD
# =============================================================================

WORD = {
    'font_name': 'Times New Roman',
    'font_size_pt': 12,
}

DOWNLOAD = {'retries': 4}



