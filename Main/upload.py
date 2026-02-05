# Main/upload.py

def upload_files():
    from google.colab import files
    from .config import cfg

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
