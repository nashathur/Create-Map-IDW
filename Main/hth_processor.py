# hth_processor.py
"""
HTH (Hari Tanpa Hujan / Consecutive No Rain Days) Monitoring Map.
Scatter plot on basemap, overlaid onto template - same logic as map_creation + template.

Usage in Google Colab:
    from Main.hth_processor import execute_hth, load_hth, clear_hth_cache
    from Main.config import cfg

    cfg.wilayah = "Papua Barat Daya"
    cfg.hgt = True
    cfg.year = 2023
    cfg.month = 2
    cfg.file_hth = "HTH-2023_02C.xlsx"
    cfg.hth_update_date = "20 Februari 2023"

    map_data = execute_hth()
"""

import io
import gc
import os
from datetime import datetime

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import rasterio.plot
from PIL import Image, ImageDraw, ImageFont

from .config import cfg, CACHE_DIR
from .static import font_path, get_basemap, get_hgt_data
from .utils import load_image_to_memory, number_to_bulan
from .status import update as status_update


# =============================================================================
# HTH CLASSIFICATION COLORS (by INDEKS HTH value)
# =============================================================================

HTH_COLORS = {
    0: '#2E8B57',   # Masih Ada Hujan            - Dark green
    1: '#90EE90',   # Sangat Pendek (1-5 days)   - Light green
    2: '#FFD700',   # Pendek (6-10 days)          - Yellow
    3: '#FF8C00',   # Menengah (11-20 days)       - Orange
    4: '#8B4513',   # Panjang (21-30 days)        - Brown
    5: '#FFB6C1',   # Sangat Panjang (31-60 days) - Pink
    6: '#FF0000',   # Kekeringan Ekstrim (>60)    - Red
}

HTH_MARKER_SIZE = 120


# =============================================================================
# DATA LOADING
# =============================================================================

_df_hth_cache = None


def clear_hth_cache():
    global _df_hth_cache
    _df_hth_cache = None


def load_hth(copy=False):
    global _df_hth_cache

    if _df_hth_cache is not None:
        status_update("Using cached HTH data")
        return _df_hth_cache.copy() if copy else _df_hth_cache

    if cfg.file_hth is None:
        raise ValueError("cfg.file_hth not set. Set it to the uploaded file path.")

    filepath = cfg.file_hth
    status_update(f"Loading HTH file: {filepath}")

    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    elif filepath.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(filepath)
    else:
        raise FileNotFoundError(f"Unsupported file format: {filepath}")

    # Normalize column names
    col_map = {}
    for col in df.columns:
        cu = str(col).upper().strip()
        if cu in ('BUJUR', 'LON', 'LONGITUDE'):
            col_map[col] = 'LON'
        elif cu in ('LINTANG', 'LAT', 'LATITUDE'):
            col_map[col] = 'LAT'
        elif cu in ('INDEKS HTH', 'INDEKS_HTH', 'INDEX_HTH', 'INDEKS'):
            col_map[col] = 'INDEKS_HTH'
        elif cu == 'HTH':
            col_map[col] = 'HTH'

    df = df.rename(columns=col_map)

    if 'LON' not in df.columns or 'LAT' not in df.columns:
        raise ValueError(f"Cannot find LON/LAT columns. Available: {list(df.columns)}")
    if 'INDEKS_HTH' not in df.columns:
        raise ValueError(f"Cannot find INDEKS HTH column. Available: {list(df.columns)}")

    df[['LON', 'LAT']] = df[['LON', 'LAT']].apply(pd.to_numeric, errors='coerce')
    df['INDEKS_HTH'] = pd.to_numeric(df['INDEKS_HTH'], errors='coerce').fillna(0).astype(int)
    df = df.dropna(subset=['LON', 'LAT'])

    status_update(f"HTH file loaded: {len(df)} stations")
    _df_hth_cache = df
    return df.copy() if copy else df


# =============================================================================
# SCATTER PLOT CREATION
# =============================================================================

def create_hth_plot(df, info):
    """
    Create scatter plot of HTH stations on basemap.
    Same structure as create_map() but scatter instead of IDW.
    """
    year, month, dasarian, year_ver, month_ver, dasarian_ver, wilayah = info

    basemaps = get_basemap(wilayah)
    shp_main = basemaps['shp_main']
    shp_crs = basemaps['crs']
    others_shp = basemaps['others_shp']
    nama_wilayah = basemaps['nama_wilayah']
    status_update("Basemap loaded")

    # Create GeoDataFrame and clip
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.LON, df.LAT), crs=shp_crs
    )
    clipped = gpd.clip(gdf, shp_main)
    status_update(f"Clipped to {len(clipped)} stations")

    if len(clipped) == 0:
        status_update("Warning: No points within boundary, using all points")
        clipped = gdf

    # ---- Count points per region ----
    status_update("Counting points by region")
    joined = gpd.sjoin(clipped, shp_main[['PROVINSI', 'KABUPATEN', 'geometry']], predicate='within')
    province_counts = {}
    for prov_name, group in joined.groupby('PROVINSI'):
        province_counts[prov_name] = _count_hth(group)
    kabupaten_counts = {}
    for kab_name, group in joined.groupby('KABUPATEN'):
        kabupaten_counts[kab_name] = _count_hth(group)

    # ---- Create figure ----
    status_update("Creating plot")
    width_x, width_y = (20, 20)
    fig, ax = plt.subplots(figsize=(width_x, width_y))
    fig.set_frameon(False)
    ax.set_position([0, 0, 1, 1])

    minx, miny, maxx, maxy = shp_main.total_bounds

    # Ocean depth layer
    if cfg.hgt:
        try:
            hgt_data = get_hgt_data()
            rasterio.plot.show(hgt_data['data'], ax=ax, extent=hgt_data['extent'], cmap='Blues_r')
            status_update("Ocean depth layer loaded")
        except Exception as e:
            status_update(f"Could not load HGT: {e}")

    # Neighboring regions
    if others_shp is not None and len(others_shp) > 0:
        others_shp.plot(ax=ax, facecolor='0.8', edgecolor='k', zorder=1)

    # Main region with light fill
    shp_main.plot(ax=ax, facecolor='#FFFDE7', edgecolor='k', linewidth=1.0, zorder=2)

    # Province boundary (dashed red)
    if 'PROVINSI' in shp_main.columns:
        for prov_name, group in shp_main.groupby('PROVINSI'):
            dissolved = group.dissolve()
            dissolved.boundary.plot(ax=ax, color='red', linewidth=1.5, linestyle='--', zorder=3)

    # Kabupaten boundaries (dashed black)
    shp_main.boundary.plot(ax=ax, color='black', linewidth=0.5, linestyle='--', zorder=3)

    # ---- Scatter plot by INDEKS HTH ----
    status_update("Plotting scatter points")
    for idx_val in sorted(HTH_COLORS.keys()):
        subset = clipped[clipped['INDEKS_HTH'] == idx_val]
        if len(subset) > 0:
            ax.scatter(
                subset.geometry.x, subset.geometry.y,
                c=HTH_COLORS[idx_val], s=HTH_MARKER_SIZE,
                edgecolors='black', linewidths=0.5,
                zorder=5
            )

    # ---- Set extent ----
    x_center = (minx + maxx) / 2
    y_center = (miny + maxy) / 2
    x_range = maxx - minx
    y_range = maxy - miny
    max_range = max(x_range, y_range)
    buffer = 0.05 * max_range

    ax.set_xlim(x_center - (max_range + buffer) / 2, x_center + (max_range + buffer) / 2)
    ax.set_ylim(y_center - (max_range + buffer) / 2, y_center + (max_range + buffer) / 2)
    ax.set_aspect('equal', 'box')

    # ---- Kabupaten labels ----
    status_update("Adding labels")
    font_style = 'medium'
    fontprop = fm.FontProperties(fname=font_path(font_style), stretch=115)
    label_kab_fontsize = 26

    for idx_row, row in shp_main.iterrows():
        centroid = row.geometry.centroid
        kab_name = row['KABUPATEN']
        ax.annotate(
            kab_name, (centroid.x, centroid.y),
            fontsize=label_kab_fontsize, ha='center', va='center',
            zorder=4, fontproperties=fontprop
        )

    # ---- Tick labels and grid (same logic as map_creation.py) ----
    label_tick_fontsize = 25
    tick_width = 3
    tick_length = 10
    padding_label = 20
    ax.grid(c='k', alpha=0.1)

    ax.axis('on')
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    xr = xlim[1] - xlim[0]
    yr = ylim[1] - ylim[0]

    def calculate_step(range_val):
        if range_val <= 0.1:
            return 0.05
        elif range_val <= 1:
            return 0.1
        elif range_val <= 3:
            return 0.5
        elif range_val <= 8:
            return 1.0
        else:
            return 2.0

    x_step = calculate_step(xr)
    y_step = calculate_step(yr)

    xticks = np.arange(
        np.floor(xlim[0] / x_step) * x_step,
        np.ceil(xlim[1] / x_step) * x_step + x_step, x_step
    )
    yticks = np.arange(
        np.floor(ylim[0] / y_step) * y_step,
        np.ceil(ylim[1] / y_step) * y_step + y_step, y_step
    )
    ax.set_xticks(xticks)
    ax.set_yticks(yticks)

    def format_tick(x, pos):
        if x == 0:
            return "0°"
        elif x < 0:
            return f"{abs(x):.2f}°W" if x_step < 1 else f"{abs(x):.0f}°W"
        else:
            return f"{x:.2f}°E" if x_step < 1 else f"{x:.0f}°E"

    def format_tick_y(y, pos):
        if y == 0:
            return "0°"
        elif y < 0:
            return f"{abs(y):.2f}°S" if y_step < 1 else f"{abs(y):.0f}°S"
        else:
            return f"{y:.2f}°N" if y_step < 1 else f"{y:.0f}°N"

    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_tick))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(format_tick_y))

    ax.tick_params(
        which='both', direction='out', length=tick_length, width=tick_width,
        color='black', top=True, right=True, left=True, bottom=True,
        labeltop=True, labelright=True, labelleft=True, labelbottom=True,
        labelsize=label_tick_fontsize, pad=2
    )

    plt.setp(ax.get_yticklabels(), rotation=90, ha='center', va='center')

    yticklabels = ax.get_yticklabels()
    if yticklabels:
        ytickcoord = max([
            ytick.get_window_extent(renderer=plt.gcf().canvas.get_renderer()).width
            for ytick in yticklabels
        ])
        ax.yaxis.set_tick_params(pad=ytickcoord - padding_label)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xlabel('')
    ax.set_ylabel('')

    for spine in ax.spines.values():
        spine.set_linewidth(4)

    # ---- Save to buffer ----
    status_update("Saving plot to buffer")
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, transparent=True, bbox_inches='tight')
    buf.seek(0)
    img = load_image_to_memory(buf)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"plot_{timestamp}_HTH_{year}.{month:02d}.png"

    plot_data = {
        'fig': fig,
        'ax': ax,
        'peta': 'HTH',
        'tipe': 'HTH',
        'skala': getattr(cfg, 'skala', 'Dasarian') or 'Dasarian',
        'jenis': 'HTH',
        'year': year,
        'month': month,
        'dasarian': dasarian,
        'dasarian_ver': dasarian_ver,
        'month_ver': month_ver,
        'year_ver': year_ver,
        'value': 'INDEKS_HTH',
        'levels': list(HTH_COLORS.keys()),
        'province_data': province_counts,
        'kabupaten_data': kabupaten_counts,
        'image': img,
        'file_name': file_name,
        'nama_wilayah': nama_wilayah,
    }

    plt.close(fig)
    gc.collect()
    status_update("HTH plot creation complete")
    return plot_data


def _count_hth(group):
    """Count stations per HTH class within a group."""
    counts = group['INDEKS_HTH'].value_counts().to_dict()
    counts['total'] = len(group)
    return counts


# =============================================================================
# OVERLAY ONTO TEMPLATE (same logic as template.py overlay_image)
# =============================================================================

def overlay_hth(plot_data):
    """
    Overlay the scatter plot onto the HTH template image.
    Template is 3506 x 2481.
    Map area: ~(32, 35) to ~(2332, 2444) => 2300 x 2409.
    Title area: right panel top, centered around x~2897.
    """
    year = plot_data['year']
    month = plot_data['month']
    jenis = plot_data['jenis']
    nama_wilayah = plot_data['nama_wilayah']
    province_counts = plot_data['province_data']
    kabupaten_counts = plot_data['kabupaten_data']

    # ---- Load template ----
    status_update("Loading HTH template image")
    template_path = os.path.join(CACHE_DIR, 'template_hth.png')
    background_template = load_image_to_memory(template_path).convert("RGBA")
    status_update("Template loaded")

    # ---- Resize and paste plot ----
    dimension = (2300, 2409)
    location = (32, 35)

    status_update("Processing plot image")
    if 'fig' in plot_data and plot_data['fig'] is not None:
        plt.close(plot_data['fig'])

    result_image = plot_data['image'].convert("RGBA")
    result_image = result_image.resize(dimension)
    plot_data['image'].close()

    new_image = background_template.copy()
    new_image.paste(result_image, location, result_image)
    result_image.close()
    status_update("Image composite complete")

    # ---- Text overlays ----
    status_update("Rendering text overlays")

    update_date = getattr(cfg, 'hth_update_date', f"01 {number_to_bulan(month)} {year}")

    title_lines = [
        "MONITORING HARI TANPA HUJAN",
        "BERTURUT-TURUT",
        "MONITORING OF CONSECUTIVE NO RAIN DAYS",
        f"PROVINSI {nama_wilayah.upper()}",
    ]
    update_line = f"Update: {update_date}"

    font_title = ImageFont.truetype(font_path('bold'), size=32)
    font_update = ImageFont.truetype(font_path('bold_italic'), size=28)

    draw = ImageDraw.Draw(new_image)

    # Right panel center x: midpoint of (2332, 3462)
    text_x = (2332 + 3462) // 2
    text_y_start = 75
    spacing = 45

    def draw_centered(y, text, font, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((text_x - tw // 2, y - th // 2), text, fill=fill, font=font)

    for i, line in enumerate(title_lines):
        draw_centered(text_y_start + i * spacing, line, font_title)

    draw_centered(
        text_y_start + len(title_lines) * spacing + 15,
        update_line, font_update, fill='blue'
    )

    status_update("Text overlays complete")

    # ---- Display in notebook ----
    from IPython.display import display
    display(new_image)

    background_template.close()

    # ---- Build output ----
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"peta_{timestamp}_HTH_{year}.{month:02d}.png"

    map_data = {
        'peta': 'HTH',
        'tipe': 'HTH',
        'skala': plot_data['skala'],
        'jenis': jenis,
        'year': year,
        'month': month,
        'dasarian': plot_data['dasarian'],
        'dasarian_ver': plot_data['dasarian_ver'],
        'month_ver': plot_data['month_ver'],
        'year_ver': plot_data['year_ver'],
        'province_data': province_counts,
        'kabupaten_data': kabupaten_counts,
        'image': new_image,
        'file_name': file_name,
        'nama_wilayah': nama_wilayah,
        'plot_file': plot_data['file_name'],
    }

    status_update(f"HTH overlay complete: {file_name}")
    return map_data


# =============================================================================
# HIGH-LEVEL ENTRY POINTS
# =============================================================================

def get_hth():
    """Load data and create scatter plot. Expects cfg.file_hth, cfg.wilayah, cfg.year, cfg.month."""
    status_update("Processing HTH map")
    df = load_hth()
    info = (
        cfg.year,
        cfg.month,
        getattr(cfg, 'dasarian', None),
        getattr(cfg, 'year_ver', None),
        getattr(cfg, 'month_ver', None),
        getattr(cfg, 'dasarian_ver', None),
        cfg.wilayah,
    )
    plot_data = create_hth_plot(df, info)
    return plot_data


def execute_hth():
    """Full pipeline: load data -> scatter plot -> overlay template."""
    plot_data = get_hth()
    map_data = overlay_hth(plot_data)
    return map_data
