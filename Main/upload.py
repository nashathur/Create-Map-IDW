# Main/upload.py

def upload_files():
    """Explicitly reset and re-upload all files. Call this to force a fresh upload."""
    from google.colab import files
    from .config import cfg
    from .utils import clear_data_cache
    cfg.file_prakiraan = None
    cfg.file_analisis = None
    cfg.file_hth = None
    clear_data_cache()

    if cfg.jenis_peta == 'HTH':
        print("Upload file HTH (Excel/CSV):")
        uploaded = files.upload()
        cfg.file_hth = list(uploaded.keys())[0]
        return

    for peta in ([cfg.jenis_peta] if isinstance(cfg.jenis_peta, str) else cfg.jenis_peta):
        needs_prakiraan = peta in ['Prakiraan', 'Probabilistik', 'Verifikasi', 'Bias']
        needs_analisis = peta in ['Analisis', 'Verifikasi', 'Bias']

        if needs_prakiraan and cfg.file_prakiraan is None:
            print("Upload prakiraan file:")
            uploaded = files.upload()
            cfg.file_prakiraan = list(uploaded.keys())[0]

        if needs_analisis and cfg.file_analisis is None:
            print("Upload analisis file:")
            uploaded = files.upload()
            cfg.file_analisis = list(uploaded.keys())[0]


def ensure_files(peta):
    """Prompt for file upload only when required files are not yet set.

    Called automatically by execute(). Skips upload if file paths
    are already configured (e.g. set manually or from a previous upload).
    """
    from google.colab import files
    from .config import cfg

    if peta == 'HTH':
        if cfg.file_hth is None:
            print("Upload file HTH (Excel/CSV):")
            uploaded = files.upload()
            cfg.file_hth = list(uploaded.keys())[0]
        return

    needs_prakiraan = peta in ['Prakiraan', 'Probabilistik', 'Verifikasi', 'Bias']
    needs_analisis = peta in ['Analisis', 'Verifikasi', 'Bias']

    if needs_prakiraan and cfg.file_prakiraan is None:
        print("Upload prakiraan file:")
        uploaded = files.upload()
        cfg.file_prakiraan = list(uploaded.keys())[0]

    if needs_analisis and cfg.file_analisis is None:
        print("Upload analisis file:")
        uploaded = files.upload()
        cfg.file_analisis = list(uploaded.keys())[0]
