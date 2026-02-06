# template.py
"""
Image template loading and overlay composition.
"""

import os
import io
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

from .config import cfg, CACHE_DIR
from .static import font_path
from .utils import load_image_to_memory, number_to_bulan, dasarian_romawi
from .status import update as status_update


def image_template():
    templates = {
        'Verifikasi': 'template_verifikasi.png',
        'Probabilistik': 'template_probabilistik.png',
        'Bias': 'bias.png',
        'Normal': 'template_ch_bulanan.png',
        'default': {
            'Bulanan': {'Curah Hujan': 'template_ch_bulanan.png', 'Sifat Hujan': 'template_sh.png'},
            'Dasarian': {'Curah Hujan': 'template_ch_das.png', 'Sifat Hujan': 'template_sh.png'}
        }
    }
    try:
        if cfg.peta in templates:
            template_filename = templates[cfg.peta]
        elif cfg.peta in ['Analisis', 'Prakiraan', 'Normal']:
            template_filename = templates['default'][cfg.skala][cfg.tipe]
        else:
            raise ValueError("Invalid peta.")
        status_update("Retrieving background template")
        filepath = os.path.join(CACHE_DIR, template_filename)
        background_template = load_image_to_memory(filepath).convert("RGBA")
        return background_template
    except KeyError:
        raise ValueError("Invalid combination of peta, skala, and tipe")


def overlay_image(plot_data):
    peta = plot_data['peta']
    tipe = plot_data['tipe']
    skala = plot_data['skala']
    year = plot_data['year']
    month = plot_data['month']
    jenis = plot_data['jenis']
    dasarian = plot_data['dasarian']
    dasarian_ver = plot_data['dasarian_ver']
    month_ver = plot_data['month_ver']
    year_ver = plot_data['year_ver']
    province_counts = plot_data['province_data']
    kabupaten_counts = plot_data['kabupaten_data']
    nama_wilayah = plot_data['nama_wilayah']
    value = plot_data['value']
    plot_file = plot_data['file_name']

    if peta == 'Verifikasi':
        accuracy = plot_data['accuracy']
        hss = plot_data['hss']
        pss = plot_data['pss']
    else:
        accuracy = None
        hss = None
        pss = None

    status_update("Loading template image")
    background_template = image_template()
    status_update("Template image loaded")

    if peta == 'Probabilistik':
        status_update("Loading Probabilistik images")
        result_b50 = plot_data['result_b50']
        result_b100 = plot_data['result_b100']
        result_b150 = plot_data['result_b150']
        result_a50 = plot_data['result_a50']
        result_a100 = plot_data['result_a100']
        result_a150 = plot_data['result_a150']
        status_update("Probabilistik images loaded")
        x_dim, y_dim = 854, 777
        x_loc, y_loc = 171, 140
        dimension = (x_dim, y_dim)
        locations = [
            (x_loc, y_loc),
            (x_loc + x_dim + 300, y_loc),
            (x_loc + x_dim * 2 + 300 * 2, y_loc),
            (x_loc, y_loc + 900),
            (x_loc + x_dim + 300, y_loc + 900),
            (x_loc + x_dim * 2 + 300 * 2, y_loc + 900)
        ]

        results = [result_b50, result_b100, result_b150, result_a50, result_a100, result_a150]
        new_image = background_template.copy()

        status_update("Overlaying Probabilistik images")
        for result, location in zip(results, locations):
            img = result['image']
            img = img.resize(dimension)
            new_image.paste(img, location, img)

        for result in results:
            if 'fig' in result and result['fig'] is not None:
                plt.close(result['fig'])
            if 'image' in result and result['image'] is not None:
                result['image'].close()

        status_update("Probabilistik overlay complete")
        title = f"PETA PRAKIRAAN {peta} {tipe}"
        result_image = None

    else:
        dimension = (2379, 2392)
        location = (40, 42)
        status_update("Processing plot image")

        if 'fig' in plot_data and plot_data['fig'] is not None:
            plt.close(plot_data['fig'])

        result_image = plot_data['image'].convert("RGBA")
        result_image = result_image.resize(dimension)
        plot_data['image'].close()
        status_update("Plot image processed")
        new_image = background_template.copy()
        new_image.paste(result_image, location, result_image)
        status_update("Image composite complete")
        title = f"PETA {peta} {tipe}"

    del plot_data

    # ---- Build text strings ----
    if peta in ['Prakiraan', 'Verifikasi', 'Probabilistik']:
        if skala == "Bulanan":
            das_title = ""
            das_ver_title = ""
            dasarian_local = ""
            dasarian_ver_local = ""
            subtitle_versi = f"Versi: 01 {number_to_bulan(month_ver)} {year_ver}"
        else:
            das_title = f".das{dasarian}"
            das_ver_title = f".das{dasarian_ver}"
            dasarian_local = dasarian
            dasarian_ver_local = dasarian_ver
            subtitle_versi = f"Versi: {dasarian_romawi(dasarian_ver)} {number_to_bulan(month_ver)} {year_ver}"
        ver_title = f"_ver_{year_ver}.{month_ver:02d}{dasarian_ver_local}"
    else:
        das_title = ""
        das_ver_title = ""
        ver_title = ""
        subtitle_versi = ""

    if skala == 'Bulanan':
        subtitle = f"BULAN {number_to_bulan(month)} {year}"
    else:
        subtitle = f"DASARIAN {dasarian_romawi(dasarian)} {number_to_bulan(month)} {year}"

    subtitle_wilayah = nama_wilayah.upper()

    if peta == 'Probabilistik':
        title = f"PETA PRAKIRAAN {peta} {tipe}"
        text_x = 822
        text_y = 1916
        spacing = 55
    else:
        title = f"PETA {peta} {tipe}"
        text_x = 2940
        text_y = 172
        spacing = 60

    status_update("Rendering text overlays")
    # ---- PIL text rendering ----
    font_title = ImageFont.truetype(font_path('bold'), size=52)
    font_subtitle = ImageFont.truetype(font_path('bold'), size=46)
    font_wilayah_large = ImageFont.truetype(font_path('bold'), size=40)
    font_wilayah_small = ImageFont.truetype(font_path('bold'), size=36)
    font_versi = ImageFont.truetype(font_path('regular'), size=32)

    font_wilayah = font_wilayah_small if len(subtitle_wilayah) > 41 else font_wilayah_large

    draw = ImageDraw.Draw(new_image)

    def draw_centered(y, text, font, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((text_x - tw // 2, y - (bbox[3] - bbox[1]) // 2), text, fill=fill, font=font)

    draw_centered(text_y, title.upper(), font_title)
    draw_centered(text_y + spacing, subtitle.upper(), font_subtitle)
    draw_centered(text_y + spacing * 2, subtitle_wilayah, font_wilayah)
    draw_centered(text_y + int(spacing * 2.8), subtitle_versi, font_versi, fill='blue')

    status_update("Text overlays complete")
    # ---- Save directly from PIL ----
    status_update("Preparing final output")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    status_update(f"Map: {jenis}_{year}.{month:02d}{das_title}{ver_title} ({value})")
    file_name = f"peta_{timestamp}_{jenis}_{year}.{month:02d}{das_title}{ver_title}.png"

    # ---- Display in notebook ----
    from IPython.display import display
    display(new_image)

    background_template.close()

    map_data = {
        'peta': peta,
        'tipe': tipe,
        'skala': skala,
        'jenis': jenis,
        'year': year,
        'month_ver': month_ver,
        'year_ver': year_ver,
        'month': month,
        'dasarian': dasarian,
        'dasarian_ver': dasarian_ver,
        'province_data': province_counts,
        'kabupaten_data': kabupaten_counts,
        'image': new_image,
        'file_name': file_name,
        'nama_wilayah': nama_wilayah,
        'plot_file': plot_file
    }
    if peta == 'Verifikasi':
        map_data['accuracy'] = accuracy
        map_data['hss'] = hss
        map_data['pss'] = pss
    status_update("Overlay complete")
    return map_data
