# Main/upload.py

def upload_files():
    from google.colab import files
    from .config import cfg
    from .utils import clear_data_cache
    cfg.file_prakiraan = None
    cfg.file_analisis = None
    clear_data_cache()
    for peta in cfg.jenis_peta:
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
            
