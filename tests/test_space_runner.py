"""Self-check for space/runner.py: titles, readiness, progress steps, cfg routing."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'space'))

import runner                        # noqa: E402
from Main import cfg                 # noqa: E402


def entry(**kw):
    e = dict(uid='u1', code='PCH', skala='Dasarian', file='p.csv', role='prakiraan',
             kolom=None, file_pembanding=None, kolom_pembanding=None,
             year=2026, month=11, dasarian=1, year_ver=2026, month_ver=10, dasarian_ver=3,
             version_day=21, verif_mode='kuantitatif',
             opsi={'laut': True, 'word': True, 'csv': False, 'png': False})
    e.update(kw)
    return e


def test_title_and_version():
    e = entry()
    assert runner.title(e) == 'Prakiraan Curah Hujan Bulan November Dasarian I 2026'
    assert runner.title(entry(skala='Bulanan')) == 'Prakiraan Curah Hujan Bulan November 2026'
    assert runner.version_text(e) == 'versi 21 Oktober 2026'
    assert runner.version_text(entry(code='ACH')) == ''
    assert runner.safe_name('a/b: c?') == 'ab c'


def test_missing():
    assert runner.missing(entry(), ['Papua Barat']) == []
    assert runner.missing(entry(), []) == ['wilayah']
    assert runner.missing(entry(code='HTH', role='hth', year=None, month=None), ['X']) == ['periode']
    assert runner.missing(entry(code='VER'), ['X']) == ['file pembanding']
    assert runner.missing(entry(code='NOR', file=None, skala='Bulanan'), ['X']) == []


def test_step_never_goes_back():
    s = runner.step_of('Starting interpolation (method=idw)')
    assert s == ('Interpolasi IDW', 30)
    s = runner.step_of('Overlaying image template...', s)
    assert s[0] == 'Menempel template'
    assert runner.step_of('Loading prakiraan file: x', s) == s
    p = runner.step_of('Processing PCH Prob b100')
    assert p == ('Peta 2/6', 19)
    assert runner.step_of('Applying colormap', p) == p          # sub-map steps don't jump ahead
    assert runner.step_of('Overlaying Probabilistik images', p)[0] == 'Menempel template'


@pytest.fixture(autouse=True)
def keep_cfg():
    saved = dict(vars(cfg))
    yield
    for k, v in saved.items():
        if not k.startswith('__'):
            setattr(cfg, k, v)


def test_load_hth_reads_semicolon_csv(tmp_path):
    from Main.processors import load_hth
    p = tmp_path / 'HTH.csv'
    p.write_text('No.;POS;LON;LAT;HTH;INDEKS_HTH\n1;Wasior;134.5;-2.7;12;3\n')
    cfg.file_hth = str(p)
    df = load_hth()
    assert list(df[['LON', 'LAT', 'INDEKS_HTH']].iloc[0]) == [134.5, -2.7, 3]


def test_run_map_unique_name_and_closes_figure(tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    fig = plt.figure()
    monkeypatch.setattr(runner, 'execute',
                        lambda *a: {'image': Image.new('RGB', (4, 4)), 'fig': fig})
    base = 'Prakiraan Curah Hujan Bulan November Dasarian I 2026'
    name, outputs, _ = runner.run_map(entry(), {'p.csv': '/p'}, ['A'], str(tmp_path),
                                      taken={base, f'{base} (versi 21 Oktober 2026)'})
    assert name == f'{base} (versi 21 Oktober 2026) (2)'
    assert [os.path.basename(p) for p in outputs] == [f'Peta {name}.png']
    assert os.path.exists(outputs[0])
    assert not plt.fignum_exists(fig.number)


def test_make_zip_skips_missing(tmp_path):
    import zipfile
    a = tmp_path / 'a.txt'
    a.write_text('x')
    z = runner.make_zip([str(a), str(tmp_path / 'gone.txt')], str(tmp_path / 'o.zip'))
    assert zipfile.ZipFile(z).namelist() == ['a.txt']


def test_cfg_routing():
    runner._set_cfg(entry(code='VER', file_pembanding='a.xls', opsi={'laut': True, 'word': True,
                    'csv': False, 'png': True}), {'p.csv': '/p', 'a.xls': '/a'}, ['A', 'B'], '/out')
    assert (cfg.file_prakiraan, cfg.file_analisis, cfg.file_hth) == ('/p', '/a', None)
    assert cfg.wilayah == 'A, B' and cfg.ask_upload is False and cfg.output_dir == '/out'
    assert cfg.png_only and not cfg.hgt and not cfg.create_word
    runner._set_cfg(entry(code='ACH', role='analisis', skala='Bulanan'), {'p.csv': '/p'}, ['A'], '/o')
    assert (cfg.file_prakiraan, cfg.file_analisis) == (None, '/p')
    assert cfg.dasarian is None and cfg.month_ver == 11       # no version: title period
    runner._set_cfg(entry(code='BIAS', file_pembanding='a.xls'), {'p.csv': '/p'}, ['A'], '/o')
    assert not cfg.create_word
