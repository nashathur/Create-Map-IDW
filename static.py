# static.py
"""
Static file management: downloads, fonts, basemap, elevation data.
"""

import os
import urllib.request
import zipfile

import numpy as np
import geopandas as gpd
import rasterio
import rasterio.plot
from fuzzywuzzy import process

from .config import CACHE_DIR, STATIC_FILES


# =============================================================================
# DOWNLOAD
# =============================================================================

def download_static_files():
    os.makedirs(CACHE_DIR, exist_ok=True)
    for filename, url in STATIC_FILES.items():
        filepath = os.path.join(CACHE_DIR, filename)
        if not os.path.exists(filepath):
            print(f"Downloading {filename}...")
            urllib.request.urlretrieve(url, filepath)
    # Extract fonts
    fonts_dir = os.path.join(CACHE_DIR, "fonts")
    if not os.path.exists(fonts_dir):
        with zipfile.ZipFile(os.path.join(CACHE_DIR, "arial.zip"), 'r') as z:
            z.extractall(CACHE_DIR)
    print("All static files ready.")


# =============================================================================
# FONT
# =============================================================================

def font_path(font_style):
    font_files = {
        'regular': 'ARIAL.TTF',
        'bold': 'ARIALBD.TTF',
        'italic': 'ARIALI.TTF',
        'bold_italic': 'ARIALBI.TTF',
        'narrow': 'ARIALN.TTF',
        'narrow_bold': 'ARIALNB.TTF',
        'narrow_italic': 'ARIALNI.TTF',
        'narrow_bold_italic': 'ARIALNBI.TTF',
        'black': 'ARIBLK.TTF',
        'light': 'ARIALLGT.TTF',
        'medium': 'ArialMdm.ttf',
        'medium_italic': 'ArialMdmItl.ttf'
    }
    return os.path.join(CACHE_DIR, font_files[font_style])


# =============================================================================
# BASEMAP
# =============================================================================

_basemap_cache = {}
_idkab_cache = None
_hgt_cache = None


def load_idkab():
    global _idkab_cache
    if _idkab_cache is None:
        filepath = os.path.join(CACHE_DIR, "idkab.feather")
        _idkab_cache = gpd.read_feather(filepath)
        print(f"\rfeather loaded", end="", flush=True)
    return _idkab_cache


def flexible_match(query, choices, threshold=80):
    if query in choices:
        return query

    prefixes = ["Kota", "Kabupaten"]
    for prefix in prefixes:
        if not query.startswith(prefix):
            prefixed_query = f"{prefix} {query}"
            if prefixed_query in choices:
                return prefixed_query

    matches = process.extractBests(query, choices, score_cutoff=threshold, limit=1)
    if matches:
        return matches[0][0]

    for prefix in prefixes:
        if not query.startswith(prefix):
            prefixed_query = f"{prefix} {query}"
            matches = process.extractBests(prefixed_query, choices, score_cutoff=threshold, limit=1)
            if matches:
                return matches[0][0]
    return None


def load_basemap(wilayah, include_others=True, others_buffer_deg=2.0, simplify_others=True):
    idkab = load_idkab()

    if isinstance(wilayah, str):
        wilayah_list = [w.strip() for w in wilayah.split(',')]
    elif isinstance(wilayah, list):
        wilayah_list = [w.strip() for w in wilayah]
    else:
        raise ValueError("wilayah must be a string (comma-separated) or a list")

    found_wilayah = []
    kolom_types = []

    for kolom in ['PROVINSI', 'KABUPATEN']:
        unique_values = set(idkab[kolom].unique())
        for query in wilayah_list:
            match = flexible_match(query, unique_values)
            if match:
                found_wilayah.append(match)
                kolom_types.append(kolom)

        if not found_wilayah:
            continue

        shp_main = idkab[idkab[kolom].isin(found_wilayah)].copy()
        shp_crs = idkab.crs

        if include_others:
            minx, miny, maxx, maxy = shp_main.total_bounds
            bounds = idkab.geometry.bounds
            bbox_filter = (
                (bounds['minx'] <= maxx + others_buffer_deg) &
                (bounds['maxx'] >= minx - others_buffer_deg) &
                (bounds['miny'] <= maxy + others_buffer_deg) &
                (bounds['maxy'] >= miny - others_buffer_deg)
            )
            nearby = idkab[bbox_filter]
            others_shp = nearby[~nearby[kolom].isin(found_wilayah)].copy()

            if simplify_others and len(others_shp) > 0:
                others_shp = others_shp.copy()
                others_shp['geometry'] = others_shp.geometry.simplify(0.01, preserve_topology=True)
        else:
            others_shp = None

        print(f"\rBasemap loaded for {kolom}: {', '.join(found_wilayah)}", end="", flush=True)

        if len(set(kolom_types)) == 1:
            prefix = 'Provinsi' if kolom_types[0] == 'PROVINSI' else 'Kabupaten'
            if len(found_wilayah) == 1:
                formatted_title = f"{prefix} {found_wilayah[0]}"
            elif len(found_wilayah) == 2:
                formatted_title = f"{prefix} {found_wilayah[0]} DAN {found_wilayah[1]}"
            else:
                formatted_title = f"{prefix} " + ', '.join(found_wilayah[:-1]) + f", DAN {found_wilayah[-1]}"
        else:
            formatted_titles = []
            for wil, kol in zip(found_wilayah, kolom_types):
                prefix = 'Provinsi' if kol == 'PROVINSI' else 'Kabupaten'
                formatted_titles.append(f"{prefix} {wil}")

            if len(formatted_titles) == 2:
                formatted_title = f"{formatted_titles[0]} DAN {formatted_titles[1]}"
            else:
                formatted_title = ', '.join(formatted_titles[:-1]) + f", DAN {formatted_titles[-1]}"

        return {
            'shp_main': shp_main,
            'others_shp': others_shp,
            'crs': shp_crs,
            'nama_wilayah': formatted_title
        }

    raise ValueError(f"None of the specified wilayah {wilayah_list} found in PROVINSI or KABUPATEN")


def get_basemap(wilayah, include_others=True, others_buffer_deg=2.0, simplify_others=True):
    cache_key = (wilayah, include_others, others_buffer_deg, simplify_others)
    if cache_key not in _basemap_cache:
        _basemap_cache[cache_key] = load_basemap(wilayah, include_others, others_buffer_deg, simplify_others)
    return _basemap_cache[cache_key]


def clear_basemap_cache():
    global _basemap_cache
    _basemap_cache = {}
    print("Basemap cache cleared")


def get_hgt_data():
    global _hgt_cache
    if _hgt_cache is None:
        filepath = os.path.join(CACHE_DIR, 'hgt1.tif')
        with rasterio.open(filepath) as src:
            _hgt_cache = {
                'data': src.read(1),
                'extent': rasterio.plot.plotting_extent(src)
            }
        print("\rhgt cached to memory", end="", flush=True)
    return _hgt_cache