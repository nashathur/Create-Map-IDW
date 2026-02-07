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
        'HTH': 'template_hth.png',
        'default': {
            'Bulanan': {'Curah Hujan': 'template_ch_bulanan.png', 'Sifat Hujan': 'template_sh.png'},
            'Dasarian': {'Curah Hujan': 'template_ch_das.png', 'Sifat Hujan': 'template_sh.png'}
        }
    }
    try:
        if cfg.peta in templates:
            template_filename = templates[cfg.peta]
        elif cfg.peta in ['Analisis', 'Prakiraan']:
            template_filename = templates['default'][cfg.skala][cfg.tipe]
        else:
            raise ValueError("Invalid peta.")
        status_update("Retrieving background template")
        filepath = os.path.join(CACHE_DIR, template_filename)
        background_template = load_image_to_memory(filepath).convert("RGBA")
        return background_template
    except KeyError:
        raise ValueError("Invalid combination of peta, skala, and tipe")

def _get_scaled_font(text, font_path_str, max_width, min_size=24, max_size=40):
    """Continuously scale font size to fit text within max_width."""
    size = max_size
    font = ImageFont.truetype(font_path_str, size=size)
    text_width = font.getbbox(text)[2] - font.getbbox(text)[0]
    
    if text_width <= max_width:
        return font
    
    # Linear estimate then clamp
    size = int(size * max_width / text_width)
    size = max(min_size, min(size, max_size))
    font = ImageFont.truetype(font_path_str, size=size)
    
    # Fine-tune downward if still too wide
    while font.getbbox(text)[2] - font.getbbox(text)[0] > max_width and size > min_size:
        size -= 1
        font = ImageFont.truetype(font_path_str, size=size)
    
    return font

def _draw_hth_text(draw, plot_data, text_x):
    """Draw HTH-specific title text on the right panel."""
    month = plot_data['month']
    year = plot_data['year']
    dasarian_ver = plot_data['dasarian_ver']
    month_ver = plot_data['month_ver']
    year_ver = plot_data['year_ver']
    nama_wilayah = plot_data['nama_wilayah']

    title_lines = [
        "MONITORING HARI TANPA HUJAN",
        "BERTURUT-TURUT",
        "MONITORING OF CONSECUTIVE NO RAIN DAYS",
        f"PROVINSI {nama_wilayah.upper()}",
    ]
    update_line = f"Update: {dasarian_romawi(dasarian_ver)} {number_to_bulan(month_ver)} {year_ver}"

    PANEL_WIDTH = 996
    TEXT_PADDING = 40

    font_line1 = ImageFont.truetype(font_path('bold'), size=40)
    font_line2 = ImageFont.truetype(font_path('bold'), size=40)
    font_line3 = ImageFont.truetype(font_path('bold'), size=36)
    font_line4 = _get_scaled_font(title_lines[3], font_path('bold'), max_width=PANEL_WIDTH - TEXT_PADDING, min_size=24, max_size=36)
    font_update = ImageFont.truetype(font_path('bold_italic'), size=28)

    fonts_title = [font_line1, font_line2, font_line3, font_line4]

    text_y_start = 200
    spacing = 50

    def draw_centered(y, text, font, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((text_x - tw // 2, y - th // 2), text, fill=fill, font=font)

    for i, line in enumerate(title_lines):
        draw_centered(text_y_start + i * spacing, line, fonts_title[i])

    draw_centered(
        text_y_start + len(title_lines) * spacing + 15,
        update_line, font_update, fill='blue'
    )

def _draw_default_text(draw, plot_data, text_x, text_y, spacing):
    """Draw standard map title text (Prakiraan, Analisis, etc.)."""
    peta = plot_data['peta']
    tipe = plot_data['tipe']
    skala = plot_data['skala']
    year = plot_data['year']
    month = plot_data['month']
    dasarian = plot_data['dasarian']
    dasarian_ver = plot_data['dasarian_ver']
    month_ver = plot_data['month_ver']
    year_ver = plot_data['year_ver']
    nama_wilayah = plot_data['nama_wilayah']

    if peta in ['Prakiraan', 'Verifikasi', 'Probabilistik']:
        if skala == "Bulanan":
            subtitle_versi = f"Versi: 01 {number_to_bulan(month_ver)} {year_ver}"
        else:
            subtitle_versi = f"Versi: {dasarian_romawi(dasarian_ver)} {number_to_bulan(month_ver)} {year_ver}"
    else:
        subtitle_versi = ""

    if skala == 'Bulanan':
        subtitle = f"BULAN {number_to_bulan(month)} {year}"
    else:
        subtitle = f"DASARIAN {dasarian_romawi(dasarian)} {number_to_bulan(month)} {year}"

    subtitle_wilayah = nama_wilayah.upper()

    if peta == 'Probabilistik':
        title = f"PETA PRAKIRAAN {peta} {tipe}"
    else:
        title = f"PETA {peta} {tipe}"

    font_title = ImageFont.truetype(font_path('bold'), size=52)
    font_subtitle = ImageFont.truetype(font_path('bold'), size=46)
    font_versi = ImageFont.truetype(font_path('regular'), size=32)
    
    PANEL_WIDTH = 996
    TEXT_PADDING = 40  # 40px each side
    font_wilayah = _get_scaled_font(
        subtitle_wilayah, font_path('bold'),
        max_width=PANEL_WIDTH - TEXT_PADDING,
        min_size=24, max_size=40)

    def draw_centered(y, text, font, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((text_x - tw // 2, y - (bbox[3] - bbox[1]) // 2), text, fill=fill, font=font)

    draw_centered(text_y, title.upper(), font_title)
    draw_centered(text_y + spacing, subtitle.upper(), font_subtitle)
    draw_centered(text_y + spacing * 2, subtitle_wilayah, font_wilayah)
    draw_centered(text_y + int(spacing * 2.8), subtitle_versi, font_versi, fill='blue')


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
        result_image = None

    else:
        # Same paste dimensions for all non-Probabilistik maps (including HTH)
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

    del plot_data

    # ---- Build filename strings ----
    if peta in ['Prakiraan', 'Verifikasi', 'Probabilistik']:
        if skala == "Bulanan":
            das_title = ""
            dasarian_ver_local = ""
        else:
            das_title = f".das{dasarian}"
            dasarian_ver_local = dasarian_ver
        ver_title = f"_ver_{year_ver}.{month_ver:02d}{dasarian_ver_local}"
    else:
        das_title = ""
        ver_title = ""

    # ---- Text rendering ----
    status_update("Rendering text overlays")
    draw = ImageDraw.Draw(new_image)

    if peta == 'HTH':
        text_x = 2940
        _draw_hth_text(draw, {
            'year': year, 'month': month,
            'dasarian_ver': dasarian_ver, 'month_ver': month_ver, 'year_ver': year_ver,
            'nama_wilayah': nama_wilayah,
        }, text_x)
    elif peta == 'Probabilistik':
        _draw_default_text(draw, {
            'peta': peta, 'tipe': tipe, 'skala': skala, 'year': year, 'month': month,
            'dasarian': dasarian, 'dasarian_ver': dasarian_ver,
            'month_ver': month_ver, 'year_ver': year_ver, 'nama_wilayah': nama_wilayah,
        }, text_x=822, text_y=1916, spacing=55)
    else:
        _draw_default_text(draw, {
            'peta': peta, 'tipe': tipe, 'skala': skala, 'year': year, 'month': month,
            'dasarian': dasarian, 'dasarian_ver': dasarian_ver,
            'month_ver': month_ver, 'year_ver': year_ver, 'nama_wilayah': nama_wilayah,
        }, text_x=2940, text_y=172, spacing=60)

    status_update("Text overlays complete")

    # ---- Display in notebook ----
    status_update("Preparing final output")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    status_update(f"Map: {jenis}_{year}.{month:02d}{das_title}{ver_title} ({value})")
    file_name = f"peta_{timestamp}_{jenis}_{year}.{month:02d}{das_title}{ver_title}.png"

    from IPython.display import display
    display(new_image)

    background_template.close()
    if result_image is not None:
        result_image.close()

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








