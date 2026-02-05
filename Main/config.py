# config.py
"""
Global configuration and constants for Staklim package.
"""

class cfg:
    """Global configuration holder - set these before calling execute()"""
    # Map settings
    jenis_peta = ['Prakiraan']
    tipe_peta = ['Curah Hujan']
    skala_peta = ['Dasarian']
    
    # Time settings
    year = 2026
    year_ver = 2026
    months = [1]
    month_ver = 1
    dasarian = 3
    dasarian_ver = 2
    
    # Region
    wilayah = "Papua Barat Daya"
    
    # Display options
    hgt = True
    
    # File paths (set after upload)
    file_prakiraan = None
    file_analisis = None
    
    # Runtime state (set by execute)
    peta = None
    tipe = None
    skala = None
    month = None


GITHUB_BASE = "https://github.com/nashathur/Create-Map-IDW/releases/download/v1.0"
CACHE_DIR = "/content/static_data"

STATIC_FILES = {
    'idkab.feather': f"{GITHUB_BASE}/idkab.feather",
    'hgt1.tif': f"{GITHUB_BASE}/hgt1.tif",
    'DATA_CH_NORMAL_PAPBAR_1991_2020.xlsx': f"{GITHUB_BASE}/DATA_CH_NORMAL_PAPBAR_1991_2020.xlsx",
    'template_ch_bulanan.png': f"{GITHUB_BASE}/template_ch_bulanan.png",
    'template_ch_das.png': f"{GITHUB_BASE}/template_ch_das.png",
    'template_sh.png': f"{GITHUB_BASE}/template_sh.png",
    'template_verifikasi.png': f"{GITHUB_BASE}/template_verifikasi.png",
    'template_probabilistik.png': f"{GITHUB_BASE}/template_probabilistik.png",
    'arial.zip': f"{GITHUB_BASE}/arial.zip",

}
