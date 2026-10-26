# runner.py
"""
Run one map of the Space with the Create-Map-IDW package; no Gradio here.

A map entry is a dict from Main.filenames.detect_maps() plus the Space's own
keys (uid, opsi, verif_mode). run_map() sets cfg from it, calls execute() and
returns the output files under readable names.
"""

import os
import re
import shutil
import time
import zipfile

from Main import cfg, execute
from Main.filenames import MAPS
from Main.utils import number_to_bulan, dasarian_romawi

# Codes whose title carries a version line (and whose rows show Versi fields);
# HTH prints it as "Update: <date>" (template._draw_hth_text)
WITH_VERSION = ('PCH', 'PSH', 'PROB', 'VER', 'BIAS', 'HTH')
MAPS_ALL = dict(MAPS, NOR=('Normal', 'Curah Hujan'))
PROB_KEYS = ('b50', 'b100', 'b150', 'a50', 'a100', 'a150')

# Progress steps: (keywords in a status_update() message, label, percent)
STEPS = [
    (('word',), 'Word', 92),
    (('narration', 'gemini', 'interpretation', 'models exhausted'), 'Narasi Gemini', 80),
    (('template', 'overlay', 'text', 'final output', 'probabilistik images'), 'Menempel template', 68),
    (('colormap', 'counting', 'creating plot', 'scatter', 'labels', 'ocean', 'saving plot',
      'map creation'), 'Menggambar peta', 50),
    (('interpolation',), 'Interpolasi IDW', 30),
]
FIRST_STEP = ('Memuat data', 8)


_PROB_SUB = re.compile(r'processing pch prob (\w+)', re.I)


def step_of(message, previous=FIRST_STEP):
    """(label, percent) for a status message; never moves back from *previous*.

    Probabilistik draws six sub-maps, each repeating the drawing steps, so
    those count as 'Peta n/6' until the template step.
    """
    low = message.lower()
    sub = _PROB_SUB.search(low)
    if sub and sub.group(1) in PROB_KEYS:
        i = PROB_KEYS.index(sub.group(1))
        return (f'Peta {i + 1}/6', 10 + i * 9)
    for keys, label, pct in STEPS:
        if previous[0].startswith('Peta ') and pct < 68:
            continue
        if any(k in low for k in keys):
            return (label, pct) if pct >= previous[1] else previous
    return previous


def needs_version(code):
    return code in WITH_VERSION


def title(e):
    """'Prakiraan Curah Hujan Bulan November Dasarian I 2026' (as word.report_filename)."""
    peta, tipe = MAPS_ALL[e['code']]
    if e['code'] == 'HTH':
        head = 'Hari Tanpa Hujan'
    elif e['code'] == 'NOR':
        head = 'Normal Curah Hujan'
    else:
        head = f'{peta} {tipe}'
    if not e.get('month') or not e.get('year'):
        return head
    when = f"Bulan {number_to_bulan(e['month'])}"
    if e.get('skala') == 'Dasarian' and e.get('dasarian'):
        when += f" Dasarian {dasarian_romawi(e['dasarian'])}"
    return f"{head} {when} {e['year']}"


def version_text(e):
    """'versi 21 Oktober 2026' from the version date, or dasarian when the day is unknown."""
    if not needs_version(e['code']) or not e.get('year_ver'):
        return ''
    day = e.get('version_day')
    if day:
        return f"versi {day} {number_to_bulan(e['month_ver'])} {e['year_ver']}"
    return (f"versi {number_to_bulan(e['month_ver'])} Dasarian "
            f"{dasarian_romawi(e['dasarian_ver'])} {e['year_ver']}")


def safe_name(name):
    """Strip characters Windows cannot store, as word.report_filename() does."""
    return re.sub(r'[\\/:*?"<>|]', '', ' '.join(name.split()))


def missing(e, wilayah):
    """What still has to be filled in before the map can run; [] when ready."""
    out = []
    if e['code'] != 'NOR' and not e.get('file'):
        out.append('file')
    if e['code'] in ('VER', 'BIAS') and not e.get('file_pembanding'):
        out.append('file pembanding')
    if not e.get('year') or not e.get('month'):
        out.append('periode')
    elif e.get('skala') == 'Dasarian' and not e.get('dasarian'):
        out.append('dasarian')
    if needs_version(e['code']) and not (e.get('year_ver') and e.get('month_ver')
                                         and e.get('dasarian_ver')):
        out.append('versi')
    if not wilayah:
        out.append('wilayah')
    return out


def _set_cfg(e, paths, wilayah, out_dir):
    """Every cfg field execute() reads, so nothing leaks from the previous map."""
    peta, tipe = MAPS_ALL[e['code']]
    opsi = e['opsi']
    cfg.ask_upload = False
    cfg.output_dir = out_dir
    cfg.wilayah = ', '.join(wilayah)
    cfg.jenis_peta, cfg.tipe_peta, cfg.skala_peta = peta, [tipe], e['skala']
    cfg.year = int(e['year'])
    cfg.dasarian = int(e['dasarian']) if e['skala'] == 'Dasarian' and e.get('dasarian') else None
    if needs_version(e['code']):
        cfg.year_ver, cfg.month_ver = int(e['year_ver']), int(e['month_ver'])
        cfg.dasarian_ver = int(e['dasarian_ver'])
    else:
        cfg.year_ver, cfg.month_ver, cfg.dasarian_ver = cfg.year, int(e['month']), cfg.dasarian
    cfg.png_only = bool(opsi['png'])
    cfg.hgt = bool(opsi['laut']) and not cfg.png_only
    cfg.create_word = bool(opsi['word']) and not cfg.png_only and e['code'] != 'BIAS'
    cfg.export_csv = bool(opsi['csv'])
    cfg.verif_mode = e.get('verif_mode') or 'kuantitatif'
    cfg.kolom = e.get('kolom') or None
    cfg.kolom_pembanding = e.get('kolom_pembanding') or None
    cfg.stress_test = False

    cfg.file_prakiraan = cfg.file_analisis = cfg.file_hth = None
    main = paths.get(e.get('file'))
    role = e.get('role')
    if e['code'] in ('VER', 'BIAS'):
        cfg.file_prakiraan = main
        cfg.file_analisis = paths.get(e.get('file_pembanding'))
    elif role == 'hth':
        cfg.file_hth = main
    elif role == 'analisis':
        cfg.file_analisis = main
    else:
        cfg.file_prakiraan = main
    return peta, tipe


def run_map(e, paths, wilayah, work_dir, taken=()):
    """Run one map entry; returns (readable name, list of output paths, seconds).

    *paths* maps an uploaded file name to its path on disk. Outputs are written
    to a fresh folder under *work_dir* and renamed to readable names; *taken*
    holds names already used in this batch, so a duplicate gets its version.
    """
    out_dir = os.path.join(work_dir, f"{e['uid']}_{int(time.time() * 1000)}")
    raw_dir = os.path.join(out_dir, 'raw')
    os.makedirs(raw_dir)
    peta, tipe = _set_cfg(e, paths, wilayah, raw_dir)

    start = time.time()
    data = execute(peta, tipe, e['skala'], int(e['month']))

    name = title(e)
    if name in taken and version_text(e):
        name += f' ({version_text(e)})'
    base, n = name, 2
    while name in taken:                # still a duplicate: number it
        name, n = f'{base} ({n})', n + 1
    name = safe_name(name)

    outputs = []
    if data.get('image') is not None:
        outputs.append(_save_png(data['image'], os.path.join(out_dir, f'Peta {name}.png')))
    else:      # Probabilistik with PNG saja: six separate maps
        for k in PROB_KEYS:
            sub = data.get(f'result_{k}')
            if sub and sub.get('image') is not None:
                outputs.append(_save_png(sub['image'], os.path.join(out_dir, f'Peta {name} ({k}).png')))
    _release(data)
    for f in sorted(os.listdir(raw_dir)):
        src = os.path.join(raw_dir, f)
        if f.lower().endswith('.docx'):
            outputs.append(_move(src, os.path.join(out_dir, f'Laporan {name}.docx')))
        elif f.lower().endswith('.csv'):
            suffix = next((f' ({k})' for k in PROB_KEYS if f'_{k}' in f.lower()), '')
            outputs.append(_move(src, os.path.join(out_dir, f'Data {name}{suffix}.csv')))
    return name, outputs, time.time() - start


def _release(data):
    """Close the matplotlib figures and PIL images of a finished run (the worker is long-lived)."""
    import matplotlib.pyplot as plt
    parts = [data] + [data.get(f'result_{k}') for k in PROB_KEYS]
    for d in parts:
        if not isinstance(d, dict):
            continue
        if d.get('fig') is not None:
            plt.close(d['fig'])
        try:
            if d.get('image') is not None:
                d['image'].close()
        except Exception:
            pass


def _save_png(image, path):
    image.save(path, format='PNG')
    return path


def _move(src, dst):
    base, ext = os.path.splitext(dst)
    n = 2
    while os.path.exists(dst):
        dst, n = f'{base} {n}{ext}', n + 1
    shutil.move(src, dst)
    return dst


def make_zip(files, path):
    """ZIP *files* flat into *path*; returns *path*."""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if os.path.exists(f):       # results may have been cleaned up
                z.write(f, os.path.basename(f))
    return path


def clean_old(work_dir, max_age=3600):
    """Delete run folders older than *max_age* seconds (results are kept 1 hour)."""
    if not os.path.isdir(work_dir):
        return
    now = time.time()
    for d in os.listdir(work_dir):
        p = os.path.join(work_dir, d)
        if os.path.isdir(p) and now - os.path.getmtime(p) > max_age:
            shutil.rmtree(p, ignore_errors=True)
