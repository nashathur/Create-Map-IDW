# Main/upload.py

def upload_files():
    """Prompt for fresh file upload. Resets existing file paths and always
    asks the user to upload, regardless of whether files were previously set.

    Called automatically at the start of execute().
    """
    from google.colab import files
    from .config import cfg
    from .utils import clear_data_cache

    cfg.file_prakiraan = None
    cfg.file_analisis = None
    cfg.file_hth = None
    clear_data_cache()

    jenis = cfg.jenis_peta
    if jenis == 'HTH':
        print("Upload file HTH (Excel/CSV):")
        uploaded = files.upload()
        cfg.file_hth = list(uploaded.keys())[0]
        return

    peta_list = [jenis] if isinstance(jenis, str) else jenis
    needs_prakiraan = any(
        p in ['Prakiraan', 'Probabilistik', 'Verifikasi', 'Bias'] for p in peta_list
    )
    needs_analisis = any(
        p in ['Analisis', 'Verifikasi', 'Bias'] for p in peta_list
    )

    if needs_prakiraan:
        print("Upload prakiraan file:")
        uploaded = files.upload()
        cfg.file_prakiraan = list(uploaded.keys())[0]

    if needs_analisis:
        print("Upload analisis file:")
        uploaded = files.upload()
        cfg.file_analisis = list(uploaded.keys())[0]
