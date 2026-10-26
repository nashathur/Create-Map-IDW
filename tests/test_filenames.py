"""File-name detection, column choice and the opt-in cfg flags for the Space."""

import pandas as pd
import pytest

from Main.config import cfg
from Main.filenames import clean_name, dasarian_of_day, detect_maps, parse_filename
from Main.utils import pick_column

PERIOD = ('role', 'kind', 'year', 'month', 'dasarian', 'year_ver', 'month_ver', 'dasarian_ver')


def _period(info):
    return tuple(info[k] for k in PERIOD)


def _only(maps, code, cadangan=False):
    found = [m for m in maps if m['code'] == code and m['cadangan'] == cadangan]
    assert len(found) == 1, found
    return found[0]


# ---- the 8 real file names -------------------------------------------------

@pytest.mark.parametrize('name, columns, period, offers, stem', [
    ('pch_det.2025.04.das.3_ver_2025.04.21.csv', None,
     ('prakiraan', 'pch', 2025, 4, 3, 2025, 4, 3), {'PCH': None},
     'PCHdas_2025.04.das3_ver_2025.04.3'),
    ('pch_ensMean.2026.01_ver_2025.12.01.csv', ['NOGRID', 'LON', 'LAT', 'VAL', 'MIN', 'MAX'],
     ('prakiraan', 'pch', 2026, 1, None, 2025, 12, 1), {'PCH': 'VAL'},
     'PCH_2026.01_ver_2025.12.1'),
    ('pch_prob.2026.02_ver_2026.01.01.csv',
     ['NOGRID', 'LON', 'LAT', 'b20', 'b50', 'b100', 'b150', 'a50', 'a100', 'a150', 'a200'],
     ('prakiraan', 'prob', 2026, 2, None, 2026, 1, 1), {'PROB': None},
     'PCH_Prob_2026.02_ver_2026.01.1'),
    ('BlendGSMAP_POS.202503dec02.xls', ['LON', 'LAT', 'CH', 'SH%', 'SHpercentil'],
     ('analisis', 'analisis', 2025, 3, 2, None, None, None), {'ACH': 'CH', 'ASH': 'SH%'},
     'ACHdas_2025.03.das2'),
    ('BlendGSMAP_POS.202601.xls', ['LON', 'LAT', 'CH', 'SH%', 'SHpercentil'],
     ('analisis', 'analisis', 2026, 1, None, None, None, None), {'ACH': 'CH', 'ASH': 'SH%'},
     'ACH_2026.01'),
    ('SPI1_Indo.2026.04.csv', ['NOGRID', 'LON', 'LAT', 'VALSPI'],
     ('analisis', 'spi', 2026, 4, None, None, None, None), {'SPI': 'SPI'},
     'SPI_2026.04'),
    ('HTH.csv', ['No.', 'POS', 'LON', 'LAT', 'HTH', 'INDEKS_HTH'],
     ('hth', 'hth', None, None, None, None, None, None), {'HTH': None}, 'HTH'),
    ('Draft.Argis.HTH.TR.csv', None,
     ('hth', 'hth', None, None, None, None, None, None), {'HTH': None}, 'HTH'),
])
def test_real_file_names(name, columns, period, offers, stem):
    info = parse_filename(name, columns)
    assert _period(info) == period
    assert info['offers'] == offers
    maps = detect_maps([info])
    assert [m['stem'] for m in maps if m['code'] == next(iter(offers))] == [stem]


def test_name_rules():
    assert clean_name('/tmp/gradio/abc/PCH_DET.2025.04.das.3_ver_2025.04.21 (2).CSV') == \
        'PCH_DET.2025.04.das.3_ver_2025.04.21.CSV'
    info = parse_filename('PCH_DET.2025.04.das.3_ver_2025.04.21 (2).CSV')
    assert _period(info) == ('prakiraan', 'pch', 2025, 4, 3, 2025, 4, 3)
    assert parse_filename('hth (1).xlsx')['role'] == 'hth'
    assert parse_filename('data_stasiun.csv') is None
    assert parse_filename('pch_det.2025.04_ver_2025.04.21.pdf') is None
    assert [dasarian_of_day(d) for d in (1, 10, 11, 20, 21, 31)] == [1, 1, 2, 2, 3, 3]


def test_pch_sh_column_offers_psh():
    info = parse_filename('pch_det.2025.04.das.3_ver_2025.04.21.csv', ['LON', 'LAT', 'ch', 'sh'])
    assert info['offers'] == {'PCH': 'CH', 'PSH': 'SH'}


# ---- pairing and cadangan ---------------------------------------------------

def test_pairing_newest_version_wins():
    cols_p, cols_a = ['LON', 'LAT', 'CH'], ['LON', 'LAT', 'CH', 'SH%']
    maps = detect_maps([
        parse_filename('pch_det.2025.04.das.3_ver_2025.04.11.csv', cols_p),
        parse_filename('pch_det.2025.04.das.3_ver_2025.04.21.csv', cols_p),
        parse_filename('BlendGSMAP_POS.202504dec03.xls', cols_a),
        parse_filename('BlendGSMAP_POS.202503dec02.xls', cols_a),   # other period: no pair
        parse_filename('notes.txt'),
    ])
    for code in ('PCH', 'VER', 'BIAS'):
        main = _only(maps, code)
        assert main['file'] == 'pch_det.2025.04.das.3_ver_2025.04.21.csv'
        assert main['dasarian_ver'] == 3
        assert _only(maps, code, cadangan=True)['dasarian_ver'] == 2
    ver = _only(maps, 'VER')
    assert (ver['peta'], ver['skala'], ver['file_pembanding']) == \
        ('Verifikasi', 'Dasarian', 'BlendGSMAP_POS.202504dec03.xls')
    assert (ver['kolom'], ver['kolom_pembanding']) == ('CH', 'CH')
    assert ver['stem'] == 'VERdas_2025.04.das3_ver_2025.04.3'
    assert len([m for m in maps if m['code'] == 'ACH']) == 2
    assert not any(m['cadangan'] for m in maps if m['code'] in ('ACH', 'ASH'))


def test_psh_file_beats_pch_sh_column():
    maps = detect_maps([
        parse_filename('pch_det.2025.04.das.3_ver_2025.04.21.csv', ['LON', 'LAT', 'CH', 'SH']),
        parse_filename('psh_det.2025.04.das.3_ver_2025.04.01.csv', ['LON', 'LAT', 'SH']),
    ])
    assert _only(maps, 'PSH')['file'].startswith('psh_')
    assert _only(maps, 'PSH', cadangan=True)['file'].startswith('pch_')


# ---- column choice ----------------------------------------------------------

def test_pick_column():
    df = pd.DataFrame(columns=['LON', 'LAT', 'CH', 'VAL', 'SPI'])
    assert pick_column(df, None, 'VAL', 'CH') == 'VAL'
    assert pick_column(df, None, 'SH', 'CH') == 'CH'
    assert pick_column(df, None, 'SH') is None
    assert pick_column(df, 'CH', 'VAL', 'CH') == 'CH'
    assert pick_column(df, 'valspi', 'SPI') == 'SPI'
    with pytest.raises(ValueError, match='SH%'):
        pick_column(df, 'SH%', 'CH')


# ---- opt-in cfg flags -------------------------------------------------------

@pytest.fixture
def restore_cfg():
    names = ('ask_upload', 'output_dir', 'file_prakiraan', 'file_analisis', 'file_hth')
    saved = {n: getattr(cfg, n) for n in names}
    yield
    for n, v in saved.items():
        setattr(cfg, n, v)


def test_ask_upload_false_keeps_files(restore_cfg):
    from Main.upload import upload_files
    cfg.ask_upload = False
    cfg.file_prakiraan, cfg.file_analisis = 'p.csv', 'a.xls'
    upload_files()
    assert (cfg.file_prakiraan, cfg.file_analisis) == ('p.csv', 'a.xls')


def test_output_dir_used_for_csv(restore_cfg, tmp_path):
    from Main.map_creation import _export_csv
    cfg.output_dir = str(tmp_path)
    df = pd.DataFrame({'LON': [131.0], 'LAT': [-1.0], 'CH': [120.0]})
    _export_csv({'joined_gdf': df, 'value': 'CH', 'file_name': 'peta.png'})
    assert list(pd.read_csv(tmp_path / 'peta.csv').columns) == ['LON', 'LAT', 'CH']


def test_github_token_env_first(monkeypatch):
    from Main.logger import _get_token
    monkeypatch.setenv('GITHUB_TOKEN', 'env-token')
    assert _get_token() == 'env-token'
