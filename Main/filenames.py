# filenames.py
"""
Detect maps from uploaded file names and columns (for the Gradio Space).

Pure functions, no UI: parse_filename() reads one file, detect_maps() turns
several parsed files into the maps they offer, with Verifikasi/Bias pairing.
"""

import os
import re

from .utils import standard_column

_EXT = r'\.(?:csv|xlsx?)$'
_PRAKIRAAN = re.compile(
    r'^(pch|psh)_([a-z0-9]+)\.(\d{4})\.(\d{2})(?:\.das\.([1-3]))?'
    r'_ver_(\d{4})\.(\d{2})\.(\d{2})' + _EXT, re.I)
_ANALISIS = re.compile(r'^blendgsmap_pos\.(\d{4})(\d{2})(?:dec0?([1-3]))?' + _EXT, re.I)
_SPI = re.compile(r'^spi1_indo\.(\d{4})\.(\d{2})' + _EXT, re.I)
_COPY_SUFFIX = re.compile(r'\s*\(\d+\)(?=\.[^.]*$)')    # browser " (1)" before the extension

PROB_COLUMNS = ('b50', 'b100', 'b150', 'a50', 'a100', 'a150')

# map code -> (cfg.jenis_peta, tipe passed to execute())
MAPS = {
    'PCH': ('Prakiraan', 'Curah Hujan'),
    'PSH': ('Prakiraan', 'Sifat Hujan'),
    'PROB': ('Probabilistik', 'Curah Hujan'),
    'ACH': ('Analisis', 'Curah Hujan'),
    'ASH': ('Analisis', 'Sifat Hujan'),
    'SPI': ('Analisis', 'SPI'),
    'VER': ('Verifikasi', 'Curah Hujan'),
    'BIAS': ('Bias', 'Curah Hujan'),
    'HTH': ('HTH', 'Curah Hujan'),
}


def clean_name(name):
    """Base name with a browser copy suffix such as ' (1)' removed."""
    return _COPY_SUFFIX.sub('', os.path.basename(str(name)).strip())


def dasarian_of_day(day):
    """Dasarian of a day of the month: 1-10 -> 1, 11-20 -> 2, 21-31 -> 3."""
    return min((int(day) - 1) // 10 + 1, 3)


def _first(cols, *names):
    return next((n for n in names if n in cols), None)


def _offers(kind, dasarian, columns):
    """{map code: value column} a file offers; column None when columns are unknown."""
    if columns is None:
        default = {'pch': ['PCH'], 'psh': ['PSH'], 'prob': ['PROB'],
                   'analisis': ['ACH', 'ASH'], 'spi': ['SPI'], 'hth': ['HTH']}[kind]
        return {code: None for code in default}

    if kind == 'hth':
        return {'HTH': None}
    cols = {standard_column(c) for c in columns}
    if kind == 'prob':
        return {'PROB': None} if all(c in cols for c in PROB_COLUMNS) else {}

    das = dasarian is not None
    # Same preference order as get_pch() / get_psh()
    found = {
        'pch': {'PCH': _first(cols, 'CH', 'VAL') if das else _first(cols, 'VAL', 'CH'),
                'PSH': _first(cols, 'SH')},
        'psh': {'PSH': _first(cols, 'SH', 'VAL') if das else _first(cols, 'VAL', 'SH')},
        'analisis': {'ACH': _first(cols, 'CH'), 'ASH': _first(cols, 'SH%'), 'SPI': _first(cols, 'SPI')},
        'spi': {'SPI': _first(cols, 'SPI')},
    }[kind]
    return {code: col for code, col in found.items() if col}


def parse_filename(name, columns=None):
    """Detect what one uploaded file is from its name (and its column names, if given).

    Returns a dict with role ('prakiraan' | 'analisis' | 'hth'), kind, period
    (year, month, dasarian; dasarian None for Bulanan), version (year_ver,
    month_ver, dasarian_ver and the full date tuple 'version') and 'offers'
    ({map code: value column}); None when the name is not recognised.
    """
    base = clean_name(name)
    info = dict(file=name, role=None, kind=None, model=None,
                year=None, month=None, dasarian=None,
                year_ver=None, month_ver=None, dasarian_ver=None, version=None)

    m = _PRAKIRAAN.match(base)
    if m:
        prefix, model, y, mo, das, yv, mv, dv = m.groups()
        kind = 'prob' if model.lower() == 'prob' else prefix.lower()
        info.update(role='prakiraan', kind=kind, model=model,
                    year=int(y), month=int(mo), dasarian=int(das) if das else None,
                    year_ver=int(yv), month_ver=int(mv), dasarian_ver=dasarian_of_day(dv),
                    version=(int(yv), int(mv), int(dv)))
    elif _ANALISIS.match(base):
        y, mo, das = _ANALISIS.match(base).groups()
        info.update(role='analisis', kind='analisis', year=int(y), month=int(mo),
                    dasarian=int(das) if das else None)
    elif _SPI.match(base):
        y, mo = _SPI.match(base).groups()
        info.update(role='analisis', kind='spi', year=int(y), month=int(mo))
    elif 'hth' in base.lower():
        info.update(role='hth', kind='hth')
    else:
        return None

    info['offers'] = _offers(info['kind'], info['dasarian'], columns)
    return info


def map_stem(entry):
    """Short id of a map, e.g. 'PCHdas_2025.04.das3_ver_2025.04.3'."""
    code = entry['code']
    das = entry['dasarian']
    jenis = {'PROB': 'PCH_Prob'}.get(code, code)
    if code == 'HTH' or entry['year'] is None:
        return jenis
    if das is not None:
        jenis += '_das' if code == 'PROB' else 'das'
    stem = f"{jenis}_{entry['year']}.{entry['month']:02d}" + (f".das{das}" if das else '')
    if entry['year_ver'] is not None:
        stem += f"_ver_{entry['year_ver']}.{entry['month_ver']:02d}.{entry['dasarian_ver']}"
    return stem


def _entry(code, f, kolom, file_pembanding=None, kolom_pembanding=None):
    peta, tipe = MAPS[code]
    e = dict(code=code, peta=peta, tipe=tipe,
             skala='Dasarian' if f['dasarian'] else 'Bulanan',
             file=f['file'], kolom=kolom,
             file_pembanding=file_pembanding, kolom_pembanding=kolom_pembanding,
             cadangan=False,
             **{k: f[k] for k in ('year', 'month', 'dasarian', 'year_ver', 'month_ver', 'dasarian_ver')})
    # Ranking among maps of the same code and period: a psh file beats the
    # SH column of a pch file, then the newest version wins.
    e['_rank'] = (not (code == 'PSH' and f['kind'] == 'pch'), f['version'] or ())
    e['stem'] = map_stem(e)
    return e


def detect_maps(files):
    """Maps offered by parsed files (parse_filename() results; None entries are skipped).

    A prakiraan curah hujan and an analisis CH file with the same year, month
    and dasarian also offer VER and BIAS (version from the prakiraan). Where
    several maps share code and period, all but the best are marked cadangan.
    """
    files = [f for f in files if f]
    maps = [_entry(code, f, col) for f in files for code, col in f['offers'].items()]

    analisis_ch = [m for m in maps if m['code'] == 'ACH']
    for p in [m for m in maps if m['code'] == 'PCH']:
        for a in analisis_ch:
            if (p['year'], p['month'], p['dasarian']) == (a['year'], a['month'], a['dasarian']):
                src = next(f for f in files if f['file'] == p['file'])
                for code in ('VER', 'BIAS'):
                    maps.append(_entry(code, src, p['kolom'], a['file'], a['kolom']))

    best = {}
    for m in sorted(maps, key=lambda m: m['_rank'], reverse=True):
        key = (m['code'], m['year'], m['month'], m['dasarian'])
        if key in best:
            m['cadangan'] = True
        else:
            best[key] = m
    for m in maps:
        del m['_rank']
    return maps
