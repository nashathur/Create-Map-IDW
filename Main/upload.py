# Main/upload.py

def upload_files():
    """Prompt for file upload. Uses Colab widget in Colab, native file picker locally.

    Resets existing file paths and always asks the user to upload,
    regardless of whether files were previously set.
    Called automatically at the start of execute().
    """
    from .config import cfg, is_colab
    from .status import update as status_update

    cfg.file_prakiraan = None
    cfg.file_analisis = None
    cfg.file_hth = None

    if is_colab():
        _upload_colab(cfg, status_update)
    else:
        _upload_local(cfg, status_update)


def _upload_colab(cfg, status_update):
    """Upload files via Google Colab widget."""
    from google.colab import files

    jenis = cfg.jenis_peta
    if jenis == 'HTH':
        status_update("Upload file HTH (Excel/CSV):")
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
        status_update("Upload prakiraan file:")
        uploaded = files.upload()
        cfg.file_prakiraan = list(uploaded.keys())[0]

    if needs_analisis:
        status_update("Upload analisis file:")
        uploaded = files.upload()
        cfg.file_analisis = list(uploaded.keys())[0]


def _upload_local(cfg, status_update):
    """Open native OS file picker dialogs for local (non-Colab) environments."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    jenis = cfg.jenis_peta
    filetypes = [("Excel/CSV files", "*.xlsx *.xls *.csv"), ("All files", "*.*")]

    if jenis == 'HTH':
        status_update("Select HTH file (Excel/CSV):")
        path = filedialog.askopenfilename(parent=root, title="Select HTH file", filetypes=filetypes)
        if not path:
            raise FileNotFoundError("No HTH file selected.")
        cfg.file_hth = path
        root.destroy()
        return

    peta_list = [jenis] if isinstance(jenis, str) else jenis
    needs_prakiraan = any(
        p in ['Prakiraan', 'Probabilistik', 'Verifikasi', 'Bias'] for p in peta_list
    )
    needs_analisis = any(
        p in ['Analisis', 'Verifikasi', 'Bias'] for p in peta_list
    )

    if needs_prakiraan:
        status_update("Select prakiraan file:")
        path = filedialog.askopenfilename(parent=root, title="Select prakiraan file", filetypes=filetypes)
        if not path:
            raise FileNotFoundError("No prakiraan file selected.")
        cfg.file_prakiraan = path

    if needs_analisis:
        status_update("Select analisis file:")
        path = filedialog.askopenfilename(parent=root, title="Select analisis file", filetypes=filetypes)
        if not path:
            raise FileNotFoundError("No analisis file selected.")
        cfg.file_analisis = path

    root.destroy()
