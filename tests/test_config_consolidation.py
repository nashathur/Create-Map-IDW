"""Tests that config.py stays the single source for tunable values.

Guards the consolidation against quietly rotting back into scattered literals.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from Main import config as C

SRC = Path(__file__).resolve().parents[1] / "Main"


def source_of(name):
    return (SRC / name).read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# the two-table separation
# --------------------------------------------------------------------------

def test_levels_and_klasifikasi_are_deliberately_different():
    """Display bands are finer than narration categories. Not a bug."""
    levels = C.LEVELS[('Curah Hujan', 'Bulanan')]
    batas = C.KLASIFIKASI[('Curah Hujan', 'Bulanan')]['batas']
    assert len(levels) > len(batas)


def test_klasifikasi_entries_are_internally_consistent():
    for key, entry in C.KLASIFIKASI.items():
        assert len(entry['nama']) == len(entry['batas']), key
        assert len(entry['deskripsi']) == len(entry['nama']), key
        assert entry['batas'] == sorted(entry['batas']), key


def test_curah_hujan_and_normal_palettes_stay_distinct():
    """Similar but not identical in the original; must not be merged."""
    assert C.COLORS['Curah Hujan'] != C.COLORS['Normal']
    assert len(C.COLORS['Curah Hujan']) == len(C.COLORS['Normal'])


def test_levels_and_colors_line_up():
    """A BoundaryNorm over N levels needs N-1 colours."""
    for key, colors in [('Sifat Hujan', C.COLORS['Sifat Hujan']),
                        ('SPI', C.COLORS['SPI']),
                        ('Probabilistik', C.COLORS['Probabilistik']),
                        ('Normal', C.COLORS['Normal']),
                        ('Bias', C.COLORS['Bias'])]:
        assert len(C.LEVELS[key]) == len(colors) + 1, key
    for skala in ('Bulanan', 'Dasarian'):
        assert len(C.LEVELS[('Curah Hujan', skala)]) == len(C.COLORS['Curah Hujan']) + 1


def test_narasi_category_defs_derive_from_klasifikasi():
    from Main.narasi import CATEGORY_DEFS
    for key, entry in C.KLASIFIKASI.items():
        assert CATEGORY_DEFS[key] == dict(zip(entry['nama'], entry['deskripsi']))
    for key, text in C.KLASIFIKASI_TEKS.items():
        assert CATEGORY_DEFS[key] == text


def test_count_points_uses_klasifikasi_bins():
    from Main.config import cfg
    from Main.utils import count_points
    cfg.tipe, cfg.skala, cfg.peta = 'Curah Hujan', 'Bulanan', None
    entry = C.KLASIFIKASI[('Curah Hujan', 'Bulanan')]
    df = pd.DataFrame({'V': [50.0, 200.0, 400.0, 900.0]})
    counts = count_points(df, 'V', C.LEVELS[('Curah Hujan', 'Bulanan')])
    assert set(counts) == set(entry['nama']) | {'total'}
    assert counts['total'] == 4
    assert all(counts[n] == 1 for n in entry['nama'])


# --------------------------------------------------------------------------
# no regression back to scattered literals
# --------------------------------------------------------------------------

def test_no_hardcoded_cell_size_outside_config():
    assert '0.0021648361216' not in source_of('map_creation.py')
    assert C.GRID['cell_size'] == pytest.approx(0.0021648361216)


def test_panel_width_declared_once():
    """It used to be declared three times in template.py."""
    assert len(re.findall(r'PANEL_WIDTH\s*=\s*996', source_of('template.py'))) == 0
    assert C.TEMPLATE['panel_width'] == 996


def test_hex_palettes_live_only_in_config():
    """No stray hex colour lists left behind in the processors."""
    hexes = re.findall(r"#[0-9a-fA-F]{6}", source_of('processors.py'))
    assert hexes == [], f"hex colours still hardcoded in processors.py: {hexes}"


def test_interpolation_knob_is_declared():
    """The original bug: read via getattr(cfg, ...) but never declared."""
    assert 'method' in C.INTERP
    assert C.INTERP['method'] in ('auto', 'idw', 'regular', 'linear', 'nearest', 'cubic')
    for k in ('power', 'n_neighbors', 'discrete_threshold', 'spacing_tolerance'):
        assert k in C.INTERP


def test_interpolation_method_is_not_on_cfg():
    """Deliberately kept off cfg: it is data-determined, not a preference."""
    assert not hasattr(C.cfg, 'interpolation_method')


def test_arcgis_defaults_preserved():
    assert C.INTERP['power'] == 2
    assert C.INTERP['n_neighbors'] == 12


def test_resample_default_preserves_legacy_output():
    """BICUBIC is PIL's implicit default; LANCZOS is the upgrade but changes output."""
    from PIL import Image
    from Main.template import _RESAMPLE
    assert _RESAMPLE == getattr(Image.Resampling, C.TEMPLATE['resample'])


def test_cfg_gained_no_new_notebook_fields():
    """The Colab interface must be unchanged by the consolidation."""
    expected = {
        'jenis_peta', 'tipe_peta', 'skala_peta', 'year', 'year_ver', 'months',
        'month_ver', 'dasarian', 'dasarian_ver', 'wilayah', 'hgt', 'export_csv',
        'stress_test', 'skip_logging', 'file_prakiraan', 'file_analisis',
        'file_hth', 'peta', 'tipe', 'skala', 'month', 'png_only', 'create_word',
        'verif_mode', 'gemini_api_key',
    }
    public = {k for k in vars(C.cfg) if not k.startswith('_')}
    assert public - expected == set(), f"unexpected new cfg fields: {public - expected}"
