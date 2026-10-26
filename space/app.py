# app.py
"""
Gradio Space for Create-Map-IDW: upload files, check the detected maps,
pick the wilayah, run and download. Design: docs/hf-space-plan.md.

cfg in the package is one global class, so map runs share one queue slot
(concurrency_id 'peta'); every other event only touches the session state.
"""

import os
os.environ.setdefault('MPLBACKEND', 'Agg')      # maps are drawn in a worker thread

import html
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime

import gradio as gr
import pandas as pd

from Main import cfg
from Main.filenames import parse_filename, detect_maps, dasarian_of_day
from Main.static import download_static_files, load_idkab
from Main.status import set_callback
from Main.utils import number_to_bulan

import runner

WORK = os.path.join(tempfile.gettempdir(), 'peta_space')
os.makedirs(WORK, exist_ok=True)
if os.environ.get('SPACE_SKIP_LOG'):            # local testing: no commit to execution_log.csv
    cfg.skip_logging = True

download_static_files()
_idkab = load_idkab()
WILAYAH = {
    'Provinsi': sorted(_idkab['PROVINSI'].dropna().unique()),
    'Kabupaten/kota': sorted(_idkab['KABUPATEN'].dropna().unique()),
}
DEFAULT_WILAYAH = [w for w in ('Papua Barat', 'Papua Barat Daya') if w in WILAYAH['Provinsi']]

BUSY = {'n': 0}            # map runs in progress across all sessions


def _clean_loop():
    while True:
        try:
            runner.clean_old(WORK)
        except Exception:
            traceback.print_exc()
        time.sleep(600)


threading.Thread(target=_clean_loop, daemon=True).start()

# ---------------------------------------------------------------------------
# Look of codes: colour by source, icon by what is mapped
# ---------------------------------------------------------------------------

SOURCE = {'PCH': 'violet', 'PSH': 'violet', 'PROB': 'violet', 'ACH': 'aqua', 'ASH': 'aqua',
          'SPI': 'aqua', 'VER': 'magenta', 'BIAS': 'magenta', 'NOR': 'yellow', 'HTH': 'orange'}
ICON = {'PCH': '🌧', 'ACH': '🌧', 'PSH': '%', 'ASH': '%', 'SPI': '📈', 'PROB': '📊',
        'VER': '✔✔', 'BIAS': '⇅', 'NOR': '📅', 'HTH': '☀'}
JENIS_CHOICES = [
    ('PCH · Prakiraan Curah Hujan', 'PCH'), ('PSH · Prakiraan Sifat Hujan', 'PSH'),
    ('PROB · Probabilistik', 'PROB'), ('ACH · Analisis Curah Hujan', 'ACH'),
    ('ASH · Analisis Sifat Hujan', 'ASH'), ('SPI · Analisis SPI', 'SPI'),
    ('VER · Verifikasi', 'VER'), ('BIAS · Bias', 'BIAS'), ('NOR · Normal', 'NOR'),
    ('HTH · Hari Tanpa Hujan', 'HTH'),
]
ROLE_OF = {'PCH': 'prakiraan', 'PSH': 'prakiraan', 'PROB': 'prakiraan', 'VER': 'prakiraan',
           'BIAS': 'prakiraan', 'ACH': 'analisis', 'ASH': 'analisis', 'SPI': 'analisis',
           'HTH': 'hth', 'NOR': None}
BULAN = [(number_to_bulan(m), m) for m in range(1, 13)]
DASARIAN = [('I', 1), ('II', 2), ('III', 3)]
AUTO_FIELDS = ('code', 'skala', 'file', 'kolom', 'file_pembanding', 'kolom_pembanding',
               'year', 'month', 'dasarian', 'year_ver', 'month_ver', 'dasarian_ver',
               'role', 'version_day')

CSS = """
:root { --violet:#7c5cff; --aqua:#13a8a8; --magenta:#c2389a; --yellow:#c99a06; --orange:#e06c1f; }
.card { background: var(--background-fill-secondary) !important; border-radius: .75rem; padding: .75rem 1rem !important; }
.card h3 { margin: 0 0 .25rem; font-size: 1.05rem; }
.count { color: var(--body-text-color-subdued); font-weight: 400; font-size: .85rem; margin-left: .5em; }
.rowbox { background: var(--background-fill-primary) !important; border-radius: .5rem; padding: .35rem .6rem !important; margin: .25rem 0; }
.badge { display: inline-flex; gap: .3em; align-items: center; color: #fff; border-radius: .35rem;
         padding: .1em .45em; font: 600 .78rem/1.4 ui-monospace, monospace; white-space: nowrap; }
.b-violet{background:var(--violet)} .b-aqua{background:var(--aqua)} .b-magenta{background:var(--magenta)}
.b-yellow{background:var(--yellow)} .b-orange{background:var(--orange)} .b-grey{background:#888}
.pill { border-radius: 1em; padding: .05em .6em; font-size: .78rem; white-space: nowrap; }
.p-ok { background: #1f9d5522; color: #1f9d55; } .p-need { background: #d9770622; color: #d97706; }
.p-bad { background: #dc262622; color: #dc2626; }
.maprow { display: flex; gap: .6em; align-items: center; min-height: 2rem; }
.maprow .t { flex: 1; } .muted { color: var(--body-text-color-subdued); font-size: .78rem; }
.bar { position: relative; height: 22px; border-radius: .35rem; background: var(--block-background-fill);
       border: 1px solid var(--border-color-primary); overflow: hidden; flex: 1; min-width: 10ch; }
.bar > i { position: absolute; inset: 0 auto 0 0; }
.bar > span { position: relative; padding: 0 .5em; font-size: .78rem; line-height: 22px; white-space: nowrap; }
.f-run { background: #3b82f655; } .f-done { background: #1f9d5555; } .f-fail { background: #dc262655; }
.thumb { width: 5.5rem; height: 3.6rem; object-fit: cover; border-radius: .3rem; display: block;
         background: var(--block-background-fill); }
.err { color: #dc2626; font-size: .85rem; }
.grp { border-top: 1px solid var(--border-color-primary); padding-top: .4rem !important; margin-top: .3rem; }
.grp-title { font-size: .82rem; font-weight: 500; margin: 0; }
.chips button { border-radius: 1em !important; }
.fields > .form { flex: 1 1 100% !important; }
.hrow { align-items: center !important; flex-wrap: nowrap !important; }
.hrow button { align-self: center; }
.maprow .t { min-width: 14ch; }
.form:has(> .tick) { flex: 0 0 auto !important; min-width: 0 !important; border: 0 !important;
                      background: none !important; }
.tick { flex: 0 0 2.2rem !important; min-width: 0 !important; width: 2.2rem !important; padding: 0 !important;
        background: none !important; border: 0 !important; }
.tick span { display: none; }
"""


def esc(s):
    return html.escape(str(s))


def badge(code):
    return (f'<span class="badge b-{SOURCE.get(code, "grey")}">{ICON.get(code, "")} '
            f'{esc(code)}</span>')


def file_url(path):
    return f'/gradio_api/file={path}'


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def new_state():
    return {'files': [], 'maps': [], 'tingkat': 'Provinsi', 'wilayah': list(DEFAULT_WILAYAH),
            'zip': None}


def read_columns(path):
    try:
        if path.lower().endswith('.csv'):
            return list(pd.read_csv(path, nrows=5, sep=None, engine='python').columns)
        return list(pd.read_excel(path, nrows=0).columns)
    except Exception:
        return None


def make_entry(m, files):
    """A detect_maps() entry plus the Space's own keys."""
    f = next((x for x in files if x['name'] == m['file']), None)
    p = f['parsed'] if f else None
    e = dict(m)
    e.update(uid=uuid.uuid4().hex[:8], role=p['role'] if p else ROLE_OF[m['code']],
             version_day=p['version'][2] if p and p.get('version') else None,
             opsi={'laut': True, 'word': False, 'csv': False, 'png': False},
             verif_mode='kuantitatif', ticked=not m.get('cadangan'), open=False,
             status={'state': 'idle'}, outputs=[], download=None, thumb=None, full=None)
    if e['code'] == 'HTH' and not e.get('year_ver'):      # update date: today's dasarian
        now = datetime.now()
        e.update(year_ver=now.year, month_ver=now.month, dasarian_ver=dasarian_of_day(now.day))
    e['auto'] = {k: e.get(k) for k in AUTO_FIELDS}
    return e


def invalidate(e):
    """Forget a map's results; its settings changed."""
    e['status'] = {'state': 'idle'}
    e['outputs'] = []
    e['download'] = e['thumb'] = e['full'] = None
    e['name'] = None


def invalidate_done(S):
    """The wilayah changed: finished and failed maps no longer match it."""
    for x in S['maps']:
        if x['status']['state'] in ('done', 'fail'):
            invalidate(x)
    S['zip'] = None


def find(S, uid):
    return next(e for e in S['maps'] if e['uid'] == uid)


def files_of(S, role=None):
    return [f for f in S['files'] if f['parsed'] and (role is None or f['parsed']['role'] == role)]


# ---------------------------------------------------------------------------
# Card 1: files
# ---------------------------------------------------------------------------

def on_upload(paths, S, dv, hv):
    if any_running(S):
        gr.Warning('Tunggu sampai proses selesai')
        return S, files_html(S), dv, hv, add_choices(S)
    paths = paths or []
    S['files'] = []
    for p in paths:
        name = os.path.basename(p)
        cols = read_columns(p)
        S['files'].append({'name': name, 'path': p, 'columns': cols,
                           'parsed': parse_filename(name, cols)})
    parsed = [dict(f['parsed'], file=f['name']) for f in S['files'] if f['parsed']]
    S['maps'] = [make_entry(m, S['files']) for m in detect_maps(parsed)]
    S['zip'] = None
    return S, files_html(S), dv + 1, hv + 1, add_choices(S)


def files_html(S):
    if not S['files']:
        return '<div class="muted">Belum ada file.</div>'
    rows, ready = [], 0
    for f in S['files']:
        p = f['parsed']
        short = f['name'] if len(f['name']) <= 18 else f['name'][:18] + '…'
        if not p:
            code, pill = '?', '<span class="pill p-bad">Tidak dikenali</span>'
        else:
            code = {'pch': 'PCH', 'psh': 'PSH', 'prob': 'PROB', 'analisis': 'ACH',
                    'spi': 'SPI', 'hth': 'HTH'}[p['kind']]
            if p['year'] is None:
                pill = '<span class="pill p-need">Periode perlu diisi</span>'
            elif not p['offers'] and f['columns'] is not None:
                pill = '<span class="pill p-need">Kolom perlu diisi</span>'
            else:
                pill, ready = '<span class="pill p-ok">Siap</span>', ready + 1
        rows.append(f'<div class="maprow rowbox">{badge(code) if p else ""}'
                    f'<span class="t" title="{esc(f["name"])}">{esc(short)}</span>{pill}</div>')
    head = f'<div class="count">{len(S["files"])} file · {ready} siap</div>'
    return head + ''.join(rows)


# ---------------------------------------------------------------------------
# Card 2: maps
# ---------------------------------------------------------------------------

def add_choices(S):
    choices = [(f['name'], f['name']) for f in files_of(S)] + [('Tanpa file (Normal)', '')]
    return gr.update(choices=choices, value=choices[0][1])


def on_add(src, S, dv, hv):
    now = datetime.now()
    if src:
        f = next(x for x in S['files'] if x['name'] == src)
        p = f['parsed']
        code = next(iter(p['offers']), None) or {'pch': 'PCH', 'psh': 'PSH', 'prob': 'PROB',
                                                 'analisis': 'ACH', 'spi': 'SPI',
                                                 'hth': 'HTH'}[p['kind']]
        m = detect_maps([dict(p, file=src, offers={code: p['offers'].get(code)})])[0]
    else:
        m = dict(code='NOR', peta='Normal', tipe='Curah Hujan', skala='Bulanan', file=None,
                 kolom=None, file_pembanding=None, kolom_pembanding=None, cadangan=False,
                 year=now.year, month=now.month, dasarian=None, year_ver=None,
                 month_ver=None, dasarian_ver=None)
    e = make_entry(m, S['files'])
    e['ticked'], e['open'] = True, True
    S['maps'].append(e)
    return S, dv + 1, hv + 1


def set_code(e, S, code):
    e['code'] = code
    e['peta'], e['tipe'] = runner.MAPS_ALL[code]
    if code in ('SPI', 'HTH', 'NOR'):
        e['skala'] = 'Bulanan'
    if code == 'NOR':
        e['file'] = None
    want = ROLE_OF[code]
    f = next((x for x in S['files'] if x['name'] == e.get('file')), None)
    if want and (not f or not f['parsed'] or f['parsed']['role'] != want):
        f = next(iter(files_of(S, want)), None)
        e['file'] = f['name'] if f else None
    set_file(e, S, e.get('file'))
    if code in ('VER', 'BIAS') and not e.get('file_pembanding'):
        a = next((x for x in files_of(S, 'analisis')
                  if (x['parsed']['year'], x['parsed']['month']) == (e['year'], e['month'])),
                 next(iter(files_of(S, 'analisis')), None))
        e['file_pembanding'] = a['name'] if a else None
        e['kolom_pembanding'] = None


def set_file(e, S, name):
    e['file'] = name or None
    f = next((x for x in S['files'] if x['name'] == name), None)
    e['kolom'] = (f['parsed']['offers'].get(e['code']) if f and f['parsed'] else None)
    if f and f['parsed']:
        e['role'] = f['parsed']['role']
        if f['parsed']['version']:
            e['version_day'] = f['parsed']['version'][2]


def map_status(e, S):
    miss = runner.missing(e, S['wilayah'])
    if not miss:
        return '<span class="pill p-ok">Siap</span>', True
    return f'<span class="pill p-need">{esc(", ".join(miss))} perlu diisi</span>', False


def tag(e, field):
    return 'diubah' if e.get(field) != e['auto'].get(field) else 'otomatis'


def columns_of(S, name):
    f = next((x for x in S['files'] if x['name'] == name), None)
    cols = (f['columns'] or []) if f else []
    return [('otomatis', '')] + [(str(c), str(c)) for c in cols]


def any_running(S):
    return any(e['status']['state'] in ('wait', 'queue', 'run') for e in S['maps'])


# ---------------------------------------------------------------------------
# Card 3: wilayah
# ---------------------------------------------------------------------------

def on_tingkat(t, S, wv, dv, hv):
    if any_running(S):
        gr.Warning('Tunggu sampai proses selesai')
        return S, gr.update(), wv, dv, hv
    if t != S['tingkat']:
        S['tingkat'], S['wilayah'] = t, []
        invalidate_done(S)
    return S, gr.update(choices=WILAYAH[t], value=None), wv + 1, dv + 1, hv + 1


def on_pick(name, S, wv, dv, hv):
    if any_running(S):
        gr.Warning('Tunggu sampai proses selesai')
        return S, gr.update(value=None), wv, dv, hv
    if name and name not in S['wilayah']:
        S['wilayah'].append(name)
        invalidate_done(S)
    return S, gr.update(value=None), wv + 1, dv + 1, hv + 1


# ---------------------------------------------------------------------------
# Card 4: run
# ---------------------------------------------------------------------------

def bar_html(e):
    st = e['status']
    s = st['state']
    if s == 'idle':
        fill, pct, text = '', 0, 'Belum diproses'
    elif s == 'wait':
        fill, pct, text = '', 0, 'Menunggu'
    elif s == 'queue':
        fill, pct, text = '', 0, 'Antre: menunggu 1 proses lain'
    elif s == 'run':
        fill, pct, text = 'f-run', st['pct'], f"{st['label']} · {st['pct']}%"
    elif s == 'done':
        fill, pct, text = 'f-done', 100, f"Selesai · {st['secs']:.0f} dtk"
    else:
        fill, pct, text = 'f-fail', 100, f"Gagal: {st['error']}"
    return (f'<div class="bar"><i class="{fill}" style="width:{pct}%"></i>'
            f'<span title="{esc(text)}">{esc(text)}</span></div>')


def mark(S, uids):
    """Queue the given maps; 'Antre' when another session's run holds the slot."""
    state = 'queue' if BUSY['n'] else 'wait'
    for e in S['maps']:
        if e['uid'] in uids:
            e['status'] = {'state': state}


def on_run_all(S, hv, rt):
    if not S['wilayah']:
        gr.Warning('Pilih minimal satu wilayah')
        return S, hv, rt
    uids = [e['uid'] for e in S['maps'] if e['ticked'] and map_status(e, S)[1]]
    if not uids:
        gr.Warning('Tidak ada peta yang siap diproses')
        return S, hv, rt
    mark(S, uids)
    return S, hv + 1, rt + 1


def run_batch(S, hv, dv):
    BUSY['n'] += 1
    S['zip'] = None
    try:
        runner.clean_old(WORK)
        for e in S['maps']:             # results the hourly cleanup deleted
            if e['status']['state'] == 'done' and (
                    not e['outputs'] or not all(os.path.exists(p) for p in e['outputs'])):
                invalidate(e)
        wilayah = list(S['wilayah'])    # snapshot: edits are frozen, but run_one must not read S
        paths = {f['name']: f['path'] for f in S['files']}
        todo = [e for e in S['maps'] if e['status']['state'] in ('wait', 'queue')]
        for e in todo:
            e['status'] = {'state': 'wait'}
        dv += 1
        yield S, hv + 1, dv
        for e in todo:
            for hv in run_one(e, S, hv, wilayah, paths):
                yield S, hv, dv
        done = [e for e in S['maps'] if e['status']['state'] == 'done']
        if done:
            now = datetime.now()
            zname = (f"Hasil Peta {now.day} {number_to_bulan(now.month)} {now.year} "
                     f"({len(done)} peta).zip")
            zdir = os.path.join(WORK, 'zip_' + uuid.uuid4().hex[:8])
            os.makedirs(zdir)
            S['zip'] = runner.make_zip([p for e in done for p in e['outputs']
                                        if os.path.exists(p)],
                                       os.path.join(zdir, zname))
        yield S, hv + 1, dv + 1
    finally:
        BUSY['n'] -= 1


def run_one(e, S, hv, wilayah, paths):
    """Generator: runs one map in a thread, yields a new hasil version per progress tick."""
    msgs = []
    e['status'] = {'state': 'run', 'label': runner.FIRST_STEP[0], 'pct': runner.FIRST_STEP[1]}
    yield hv + 1
    hv += 1
    taken = {x['name'] for x in S['maps']
             if x is not e and x['status']['state'] == 'done' and x.get('name')}
    box = {}

    def work():
        try:
            box['result'] = runner.run_map(e, paths, wilayah, WORK, taken)
        except Exception as ex:     # one map's failure must not stop the batch
            traceback.print_exc()
            box['error'] = ex

    set_callback(msgs.append)
    t = threading.Thread(target=work, daemon=True)
    t.start()
    seen = 0
    try:
        while t.is_alive():
            t.join(0.5)
            if len(msgs) > seen:
                step = (e['status']['label'], e['status']['pct'])
                for m in msgs[seen:]:
                    step = runner.step_of(m, step)
                seen = len(msgs)
                e['status'].update(label=step[0], pct=step[1])
                hv += 1
                yield hv
    finally:
        set_callback(None)

    if 'error' in box:
        ex = box['error']
        lines = str(ex).strip().splitlines()
        msg = lines[0] if lines else ''
        if not isinstance(ex, (ValueError, FileNotFoundError)) or not msg:
            msg = f'{type(ex).__name__}: {msg}'       # the package's own errors are Indonesian ValueErrors
        e['status'] = {'state': 'fail', 'error': msg[:160]}
    else:
        name, outputs, secs = box['result']
        e.update(name=name, outputs=outputs)
        pngs = [p for p in outputs if p.endswith('.png')]
        e['full'] = pngs[0] if pngs else None
        e['thumb'] = make_thumb(e['full']) if e['full'] else None
        if len(outputs) == 1:
            e['download'] = outputs[0]
        else:
            e['download'] = runner.make_zip(outputs, os.path.join(os.path.dirname(outputs[0]),
                                                                  f'{name}.zip'))
        e['status'] = {'state': 'done', 'secs': secs}
    yield hv + 1


def make_thumb(path):
    from PIL import Image
    out = os.path.splitext(path)[0] + '.thumb.jpg'
    with Image.open(path) as im:
        im = im.convert('RGB')
        im.thumbnail((360, 360))
        im.save(out, quality=80)
    return out


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

with gr.Blocks(title='Peta IDW BMKG', delete_cache=(3600, 3600)) as demo:
    S = gr.State(new_state())
    dv = gr.State(0)        # bump to redraw Daftar peta
    hv = gr.State(0)        # bump to redraw Hasil
    wv = gr.State(0)        # bump to redraw Wilayah chips
    rt = gr.State(0)        # bump to start a run

    gr.Markdown('## Peta IDW · Stasiun Klimatologi Papua Barat')

    with gr.Column(elem_classes='card'):
        gr.HTML('<h3>1. File data</h3>')
        up = gr.File(file_count='multiple', file_types=['.csv', '.xls', '.xlsx'],
                     label='Unggah file (CSV, XLS, XLSX)')
        files_box = gr.HTML(files_html(new_state()))

    with gr.Column(elem_classes='card'):
        @gr.render(inputs=[S], triggers=[dv.change, demo.load])
        def daftar(state):
            locked = any_running(state)
            ready = sum(1 for e in state['maps'] if map_status(e, state)[1])
            gr.HTML(f'<h3>2. Daftar peta<span class="count">{len(state["maps"])} peta · '
                    f'{ready} siap</span></h3>')
            if not state['maps']:
                gr.HTML('<div class="muted">Unggah file untuk melihat peta yang bisa dibuat.</div>')
            for e in state['maps']:
                draw_map_row(e, state, locked)

        with gr.Row(elem_classes='fields'):
            add_src = gr.Dropdown(choices=[('Tanpa file (Normal)', '')], value='',
                                  label='Tambah peta dari', scale=0, min_width=280)
            add_btn = gr.Button('Tambah peta', scale=0, size='sm')

    with gr.Column(elem_classes='card'):
        gr.HTML('<h3>3. Wilayah</h3>')
        tingkat = gr.Radio(['Provinsi', 'Kabupaten/kota'], value='Provinsi', label='Tingkat')

        @gr.render(inputs=[S], triggers=[wv.change, demo.load])
        def chips(state):
            if not state['wilayah']:
                gr.HTML('<div class="err">Pilih minimal satu wilayah</div>')
                return
            with gr.Row(elem_classes='chips'):
                for name in state['wilayah']:
                    b = gr.Button(f'{name}  ×', size='sm', scale=0)

                    def drop(st, w, d, h, name=name):
                        if any_running(st):
                            gr.Warning('Tunggu sampai proses selesai')
                            return st, w, d, h
                        invalidate_done(st)
                        st['wilayah'] = [x for x in st['wilayah'] if x != name]
                        return st, w + 1, d + 1, h + 1
                    b.click(drop, [S, wv, dv, hv], [S, wv, dv, hv])

        pick = gr.Dropdown(choices=WILAYAH['Provinsi'], value=None, filterable=True,
                           label='Cari wilayah', allow_custom_value=False)

    with gr.Column(elem_classes='card'):
        @gr.render(inputs=[S], triggers=[hv.change, demo.load])
        def hasil(state):
            rows = [e for e in state['maps'] if e['ticked']]
            n_done = sum(e['status']['state'] == 'done' for e in rows)
            n_fail = sum(e['status']['state'] == 'fail' for e in rows)
            gr.HTML(f'<h3>4. Hasil<span class="count">{n_done} dari {len(rows)} selesai · '
                    f'{n_fail} gagal</span></h3>')
            busy = any_running(state)
            for e in rows:
                s = e['status']['state']
                with gr.Row(elem_classes='rowbox hrow'):
                    thumb = (f'<a href="{file_url(e["full"])}" target="_blank">'
                             f'<img class="thumb" src="{file_url(e["thumb"])}"></a>'
                             if e.get('thumb') else '<div class="thumb"></div>')
                    gr.HTML(f'<div class="maprow">{thumb}{badge(e["code"])}'
                            f'<span class="t">{esc(runner.title(e))}</span>{bar_html(e)}</div>',
                            scale=1)
                    again = s in ('done', 'fail')
                    b = gr.Button('Ulangi' if again else 'Proses', size='sm', scale=0,
                                  min_width=90, interactive=not busy)

                    def one(st, h, r, uid=e['uid']):
                        if not st['wilayah']:
                            gr.Warning('Pilih minimal satu wilayah')
                            return st, h, r
                        miss = runner.missing(find(st, uid), st['wilayah'])
                        if miss:
                            gr.Warning('Peta ini belum siap: ' + ', '.join(miss))
                            return st, h, r
                        mark(st, [uid])
                        return st, h + 1, r + 1
                    b.click(one, [S, hv, rt], [S, hv, rt])
                    gr.DownloadButton('Unduh', value=e.get('download'), size='sm', scale=0,
                                      min_width=90, interactive=s == 'done' and not busy)
            with gr.Row(elem_classes='fields'):
                label = ('Sedang memproses…' if busy else
                         'Proses ulang semua' if any(e['status']['state'] in ('done', 'fail')
                                                     for e in rows) else 'Proses semua peta')
                run_all = gr.Button(label, variant='primary', interactive=not busy and bool(rows))
                run_all.click(on_run_all, [S, hv, rt], [S, hv, rt])
                gr.DownloadButton('Unduh semua (ZIP)', value=state.get('zip'),
                                  interactive=bool(state.get('zip')) and not busy)
                gr.HTML('<span class="muted">Tersimpan 1 jam</span>')

    def draw_map_row(e, state, locked):
        uid = e['uid']
        status, _ = map_status(e, state)
        cad = ' <span class="muted">(cadangan)</span>' if e.get('cadangan') else ''
        with gr.Column(elem_classes='rowbox'):
            with gr.Row(equal_height=True):
                tick = gr.Checkbox(value=e['ticked'], label='Pilih', container=False,
                                   scale=0, min_width=30, interactive=not locked, elem_classes='tick')
                gr.HTML(f'<div class="maprow">{badge(e["code"])}<span class="t">'
                        f'{esc(runner.title(e))}{cad}</span>{status}</div>', scale=1)
                chev = gr.Button('▴' if e['open'] else '▾', size='sm', scale=0, min_width=40)
            tick.input(edit(uid, lambda e, S, v: e.update(ticked=bool(v)), keeps_results=True),
                       [tick, S, dv, hv], [S, dv, hv])
            chev.click(edit(uid, lambda e, S, v: e.update(open=not e['open']), keeps_results=True),
                       [chev, S, dv, hv], [S, dv, hv])
            if not e['open']:
                return
            draw_fields(e, state, locked)

    def edit(uid, apply, keeps_results=False):
        """Event handler: apply(entry, state, value) then redraw Daftar and Hasil.

        Unless keeps_results, the edit changes the map's settings, so its results are dropped.
        """
        def fn(value, st, d, h):
            e = find(st, uid)
            apply(e, st, value)
            if not keeps_results:
                invalidate(e)
                st['zip'] = None
            return st, d + 1, h + 1
        return fn

    def draw_fields(e, state, locked):
        uid, code = e['uid'], e['code']
        io = lambda comp: ([comp, S, dv, hv], [S, dv, hv])
        on = not locked

        gr.HTML('<p class="grp-title">Peta</p>', elem_classes='grp')
        with gr.Row(elem_classes='fields'):
            jenis = gr.Dropdown(JENIS_CHOICES, value=code, label=f'Jenis · {tag(e, "code")}',
                                scale=0, min_width=190, interactive=on)
            jenis.input(edit(uid, lambda e, S, v: set_code(e, S, v)), *io(jenis))
            fixed = code in ('SPI', 'HTH', 'NOR')
            skala = gr.Dropdown(['Bulanan', 'Dasarian'], value=e['skala'],
                                label=f'Skala · {tag(e, "skala")}', scale=0, min_width=110,
                                interactive=on and not fixed)
            skala.input(edit(uid, lambda e, S, v: e.update(skala=v)), *io(skala))
            if code == 'VER':
                vm = gr.Dropdown(['kuantitatif', 'kualitatif'], value=e['verif_mode'],
                                 label='Mode verifikasi', scale=0, min_width=130, interactive=on)
                vm.input(edit(uid, lambda e, S, v: e.update(verif_mode=v)), *io(vm))

        if code != 'NOR':
            gr.HTML('<p class="grp-title">Data</p>', elem_classes='grp')
            with gr.Row(elem_classes='fields'):
                role = ROLE_OF[code]
                names = [f['name'] for f in files_of(state, role)]
                fl = gr.Dropdown(names, value=e.get('file') if e.get('file') in names else None,
                                 label=f'File · {tag(e, "file")}', scale=0, min_width=330,
                                 interactive=on)
                fl.input(edit(uid, lambda e, S, v: set_file(e, S, v)), *io(fl))
                kl = gr.Dropdown(columns_of(state, e.get('file')), value=e.get('kolom') or '',
                                 label=f'Kolom · {tag(e, "kolom")}', scale=0, min_width=110,
                                 interactive=on)
                kl.input(edit(uid, lambda e, S, v: e.update(kolom=v or None)), *io(kl))
            if code in ('VER', 'BIAS'):
                with gr.Row(elem_classes='fields'):
                    anames = [f['name'] for f in files_of(state, 'analisis')]
                    fp = gr.Dropdown(anames, value=e.get('file_pembanding') if e.get('file_pembanding') in anames else None,
                                     label=f'File pembanding (analisis) · {tag(e, "file_pembanding")}',
                                     scale=0, min_width=330, interactive=on)
                    fp.input(edit(uid, lambda e, S, v: e.update(file_pembanding=v, kolom_pembanding=None)), *io(fp))
                    kp = gr.Dropdown(columns_of(state, e.get('file_pembanding')),
                                     value=e.get('kolom_pembanding') or '',
                                     label=f'Kolom · {tag(e, "kolom_pembanding")}', scale=0,
                                     min_width=110, interactive=on)
                    kp.input(edit(uid, lambda e, S, v: e.update(kolom_pembanding=v or None)), *io(kp))

        def period(prefix, title):
            gr.HTML(f'<p class="grp-title">{title}</p>', elem_classes='grp')
            with gr.Row(elem_classes='fields'):
                y = gr.Number(value=e.get(f'year{prefix}'), precision=0, label=f'Tahun · {tag(e, "year" + prefix)}',
                              scale=0, min_width=90, interactive=on)
                for ev in (y.blur, y.submit):
                    ev(edit(uid, lambda e, S, v, k='year' + prefix: e.update({k: int(v) if v else None})), *io(y))
                m = gr.Dropdown(BULAN, value=e.get(f'month{prefix}'), label=f'Bulan · {tag(e, "month" + prefix)}',
                                scale=0, min_width=120, interactive=on)
                m.input(edit(uid, lambda e, S, v, k='month' + prefix: e.update({k: v})), *io(m))
                if prefix or e['skala'] == 'Dasarian':
                    d = gr.Dropdown(DASARIAN, value=e.get(f'dasarian{prefix}'),
                                    label=f'Dasarian · {tag(e, "dasarian" + prefix)}',
                                    scale=0, min_width=90, interactive=on)
                    d.input(edit(uid, lambda e, S, v, k='dasarian' + prefix: e.update({k: v})), *io(d))

        period('', 'Periode')
        if runner.needs_version(code):
            period('_ver', 'Versi')

        gr.HTML('<p class="grp-title">Opsi</p>', elem_classes='grp')
        o = e['opsi']
        with gr.Row(elem_classes='fields'):
            boxes = {}
            for k, lab in (('laut', 'Layer laut'), ('word', 'Dokumen Word'), ('csv', 'Ekspor CSV'),
                           ('png', 'PNG saja')):
                grey = (k in ('laut', 'word') and o['png']) or (k == 'word' and code == 'BIAS')
                boxes[k] = gr.Checkbox(value=o[k] and not grey, label=lab, scale=0, min_width=130,
                                       interactive=on and not grey)

                def set_opt(e, S, v, k=k):
                    e['opsi'][k] = bool(v)
                    if k == 'png' and v:
                        e['opsi'].update(laut=False, word=False)
                boxes[k].input(edit(uid, set_opt), *io(boxes[k]))

        with gr.Row(elem_classes='fields'):
            reset = gr.Button('Kembalikan ke otomatis', size='sm', scale=0, interactive=on)
            dup = gr.Button('Duplikat', size='sm', scale=0, interactive=on)
            rm = gr.Button('Hapus', size='sm', scale=0, variant='stop', interactive=on)
            allopt = gr.Button('Terapkan opsi ke semua peta', size='sm', scale=0, interactive=on)

        def do_reset(e, S, v):
            e.update(e['auto'])
            e['peta'], e['tipe'] = runner.MAPS_ALL[e['code']]

        def do_dup(e, S, v):
            c = dict(e, uid=uuid.uuid4().hex[:8], opsi=dict(e['opsi']), auto=dict(e['auto']),
                     status={'state': 'idle'}, outputs=[], download=None, thumb=None, full=None, name=None)
            S['maps'].insert(S['maps'].index(e) + 1, c)

        def do_rm(e, S, v):
            S['maps'].remove(e)

        def do_all(e, S, v):
            for x in S['maps']:
                if x['opsi'] != e['opsi']:
                    x['opsi'] = dict(e['opsi'])
                    invalidate(x)
                    S['zip'] = None

        for b, f in ((reset, do_reset), (dup, do_dup), (rm, do_rm), (allopt, do_all)):
            b.click(edit(uid, f, keeps_results=f is not do_reset), *io(b))

    # -- events outside the renders --
    up.change(on_upload, [up, S, dv, hv], [S, files_box, dv, hv, add_src])
    add_btn.click(on_add, [add_src, S, dv, hv], [S, dv, hv])
    tingkat.input(on_tingkat, [tingkat, S, wv, dv, hv], [S, pick, wv, dv, hv])
    pick.input(on_pick, [pick, S, wv, dv, hv], [S, pick, wv, dv, hv])
    rt.change(run_batch, [S, hv, dv], [S, hv, dv], concurrency_limit=1, concurrency_id='peta',
              show_progress='hidden')


demo.queue(default_concurrency_limit=None)

if __name__ == '__main__':
    demo.launch(css=CSS, allowed_paths=[WORK])
