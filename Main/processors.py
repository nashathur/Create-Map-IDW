# processors.py
"""
Map processing functions for different map types.
"""

import os
import io

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import rasterio.plot

from .config import cfg, CACHE_DIR
from .static import get_basemap, get_hgt_data
from .utils import (
    load_prakiraan, load_analisis, load_image_to_memory,
    arrange_table, calculate_metrics
)
from .map_creation import create_map
from .status import update as status_update


# =============================================================================
# PRAKIRAAN
# =============================================================================

def get_pch():
    status_update("Processing PCH")
    df_pch = load_prakiraan()
    if cfg.skala == 'Bulanan':
        levels = [0, 20, 50, 100, 150, 200, 300, 400, 500, 1000]
        color = ['#340900', '#8E2800', '#DC6200', '#EFA800', '#eae100', '#e0fe7c', '#8bd48b', '#369134', '#00450c']
    else:
        levels = [0, 10, 20, 50, 75, 100, 150, 200, 300, 1000]
        color = ['#340900', '#8E2800', '#DC6200', '#EFA800', '#eae100', '#e0fe7c', '#8bd48b', '#369134', '#00450c']
    
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    
    if cfg.skala == 'Bulanan':
        value = 'VAL'
        jenis = 'PCH'
        status_update(f"Creating {jenis} Map")
        plot_data = create_map(df_pch, value, jenis, color, levels, info)
        return plot_data
    else:
        if 'CH' in df_pch.columns:
            value = 'CH'
        elif 'VAL' in df_pch.columns:
            value = 'VAL'
        else:
            raise ValueError("Neither CH nor VAL found in the DataFrame")
        jenis = 'PCHdas'

    status_update(f"Creating {jenis} Map")
    plot_data = create_map(df_pch, value, jenis, color, levels, info)
    del df_pch
    return plot_data

def get_psh():
    status_update("Processing PSH")
    levels = [0, 30, 50, 85, 115, 150, 200, 500]
    df_psh = load_prakiraan()
    color = ['#4a1600', '#a85b00', '#f3c40f', '#ffff00', '#8bb700', '#238129', '#00460e']
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    
    if cfg.skala == 'Bulanan':
        value = 'VAL'
        jenis = 'PSH'
    else:
        value = 'SH'
        jenis = 'PSHdas'

    status_update(f"Creating {jenis} Map")
    plot_data = create_map(df_psh, value, jenis, color, levels, info)
    del df_psh
    return plot_data


# =============================================================================
# ANALISIS
# =============================================================================

def get_ach():
    status_update("Processing ACH")
    df_ach = load_analisis()
    if cfg.skala == 'Bulanan':
        levels = [0, 20, 50, 100, 150, 200, 300, 400, 500, 1000]
        color = ['#340900', '#8E2800', '#DC6200', '#EFA800', '#eae100', '#e0fe7c', '#8bd48b', '#369134', '#00450c']
    else:
        levels = [0, 10, 20, 50, 75, 100, 150, 200, 300, 1000]
        color = ['#340900', '#8E2800', '#DC6200', '#EFA800', '#eae100', '#e0fe7c', '#8bd48b', '#369134', '#00450c']
    
    value = 'CH'
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah

    if cfg.skala == 'Bulanan':
        jenis = 'ACH'
    else:
        jenis = 'ACHdas'

    status_update(f"Creating {jenis} Map")
    plot_data = create_map(df_ach, value, jenis, color, levels, info)
    del df_ach
    return plot_data


def get_ash():
    status_update("Processing ASH")
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    df_ash = load_analisis()
    levels = [0, 30, 50, 85, 115, 150, 200, 500]
    color = ['#4a1600', '#a85b00', '#f3c40f', '#ffff00', '#8bb700', '#238129', '#00460e']
    value = 'SH%'
    
    if cfg.skala == 'Bulanan':
        jenis = 'ASH'
    else:
        jenis = 'ASHdas'

    status_update(f"Creating {jenis} Map")
    plot_data = create_map(df_ash, value, jenis, color, levels, info)
    del df_ash
    return plot_data

# =============================================================================
# PROBABILISTIK
# =============================================================================

def get_pch_prob():
    status_update("Processing PCH Prob")
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    df_prob = load_prakiraan()
    
    if 'b50' not in df_prob.columns:
        raise ValueError("The column data for probabilistik is missing from the DataFrame.")
    
    levels = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    color = ['#ffffff', '#0000fe', '#007fff', '#01ffff', '#7eff80', '#fffe01', '#ffc800', '#ff7f00', '#ff3f01', '#b10101']

    if cfg.skala == 'Bulanan':
        jenis = 'PCH_Prob'
    else:
        jenis = 'PCH_Prob_das'

    status_update("Processing PCH Prob b50")
    result_b50 = create_map(df_prob, 'b50', jenis, color, levels, info)

    status_update("Processing PCH Prob b100")
    result_b100 = create_map(df_prob, 'b100', jenis, color, levels, info)

    status_update("Processing PCH Prob b150")
    result_b150 = create_map(df_prob, 'b150', jenis, color, levels, info)

    status_update("Processing PCH Prob a50")
    result_a50 = create_map(df_prob, 'a50', jenis, color, levels, info)

    status_update("Processing PCH Prob a100")
    result_a100 = create_map(df_prob, 'a100', jenis, color, levels, info)

    status_update("Processing PCH Prob a150")
    result_a150 = create_map(df_prob, 'a150', jenis, color, levels, info)

    status_update("Processing PCH Prob done")
    plot_data = {
        'result_b50': result_b50,
        'result_b100': result_b100,
        'result_b150': result_b150,
        'result_a50': result_a50,
        'result_a100': result_a100,
        'result_a150': result_a150,
        'peta': result_b50['peta'],
        'tipe': result_b50['tipe'],
        'skala': result_b50['skala'],
        'jenis': result_b50['jenis'],
        'year': result_b50['year'],
        'month_ver': result_b50['month_ver'],
        'year_ver': result_b50['year_ver'],
        'month': result_b50['month'],
        'dasarian': result_b50['dasarian'],
        'dasarian_ver': result_b50['dasarian_ver'],
        'nama_wilayah': result_b50['nama_wilayah'],
        'province_data': None,
        'kabupaten_data': None,
        'value': "PCHProb",
        'file_name': None
    }
    del df_prob, result_b50, result_b100, result_b150, result_a50, result_a100, result_a150
    return plot_data


# =============================================================================
# VERIFIKASI
# =============================================================================

def get_verif_quan():
    status_update("Processing Verifikasi Kuantitatif")
    df_prakiraan, df_analisis, merged_df = arrange_table()
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah

    basemaps = get_basemap(cfg.wilayah)
    shp_main = basemaps['shp_main']
    shp_crs = basemaps['crs']

    status_update("Basemap loaded")

    gdf_prakiraan = gpd.GeoDataFrame(df_prakiraan, geometry=gpd.points_from_xy(df_prakiraan.LON, df_prakiraan.LAT), crs=shp_crs)
    clipped_df_prakiraan = gpd.clip(gdf_prakiraan, shp_main)

    gdf_analisis = gpd.GeoDataFrame(df_analisis, geometry=gpd.points_from_xy(df_analisis.LON, df_analisis.LAT), crs=shp_crs)
    clipped_df_analisis = gpd.clip(gdf_analisis, shp_main)

    gdf_merged = gpd.GeoDataFrame(merged_df, geometry=gpd.points_from_xy(merged_df.LON, merged_df.LAT), crs=shp_crs)
    clipped_merged_df = gpd.clip(gdf_merged, shp_main)

    status_update("Building contingency table")
    all_categories = list(range(1, 10))
    contingency_quan = pd.crosstab(clipped_df_prakiraan['index'], clipped_df_analisis['index'], dropna=False, margins=True)
    contingency_quan = contingency_quan.reindex(index=all_categories + ['All'], columns=all_categories + ['All'], fill_value=0)
    
    color = ['white', 'dodgerblue']
    levels = [0, 1]
    value = 'exact_index'
    jenis = 'VERquan'

    status_update("Calculating metrics")
    accuracy, hss, pss = calculate_metrics(clipped_df_prakiraan['index'], clipped_df_analisis['index'], contingency_quan)

    status_update("Creating verification map")
    plot_data = create_map(clipped_merged_df, value, jenis, color, levels, info)

    del df_prakiraan, df_analisis, merged_df, gdf_prakiraan, gdf_analisis, gdf_merged, clipped_df_prakiraan, clipped_df_analisis, clipped_merged_df

    fig = plot_data['fig']
    ax = plot_data['ax']

    minx, maxx = ax.get_xlim()
    miny, maxy = ax.get_ylim()
    x_pos = maxx - (maxx - minx) * 0.95
    width = maxx - minx
    height = maxy - miny
    space = height * 0.027344

    bottom_space = miny + (height * 0.05)
    middle_space = bottom_space + space
    top_space = middle_space + space

    status_update("Adding metrics to plot")
    ax.text(x_pos, top_space, f"Akurasi (PC): {((accuracy)*100):.0f}%", fontsize=32, ha='left', va='center', fontweight='bold', zorder=11)
    ax.text(x_pos, middle_space, f"HSS: {((hss)*100):.0f}%", fontsize=32, ha='left', va='center', fontweight='normal', zorder=11)
    ax.text(x_pos, bottom_space, f"PSS: {((pss)*100):.0f}%", fontsize=32, ha='left', va='center', fontweight='normal', zorder=11)

    rect_x = x_pos - (space * 0.5)
    rect_y = bottom_space - (space * 0.75)
    ax.add_patch(Rectangle((rect_x, rect_y), width * 0.248582, height * 0.098, edgecolor='black', facecolor='white', fill=True, lw=4, zorder=10))

    status_update("Saving verification plot")
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, transparent=True, bbox_inches='tight')
    buf.seek(0)
    plot_data['image'] = load_image_to_memory(buf)
    plot_data['accuracy'] = accuracy
    plot_data['hss'] = hss
    plot_data['pss'] = pss
    plt.close(fig)

    return plot_data


def get_verif_qual():
    status_update("Processing Verifikasi Kualitatif")
    df_prakiraan, df_analisis, merged_df = arrange_table()
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    basemaps = get_basemap(cfg.wilayah)
    shp_main = basemaps['shp_main']
    shp_crs = basemaps['crs']
    status_update("Basemap loaded")

    gdf_prakiraan = gpd.GeoDataFrame(df_prakiraan, geometry=gpd.points_from_xy(df_prakiraan.LON, df_prakiraan.LAT), crs=shp_crs)
    clipped_df_prakiraan = gpd.clip(gdf_prakiraan, shp_main)

    gdf_analisis = gpd.GeoDataFrame(df_analisis, geometry=gpd.points_from_xy(df_analisis.LON, df_analisis.LAT), crs=shp_crs)
    clipped_df_analisis = gpd.clip(gdf_analisis, shp_main)

    gdf_merged = gpd.GeoDataFrame(merged_df, geometry=gpd.points_from_xy(merged_df.LON, merged_df.LAT), crs=shp_crs)
    clipped_merged_df = gpd.clip(gdf_merged, shp_main)

    status_update("Building contingency table")
    all_categories = list(range(1, 5))
    contingency_qual = pd.crosstab(clipped_df_prakiraan['CH_category'], clipped_df_analisis['CH_category'], margins=True)
    contingency_qual = contingency_qual.reindex(index=all_categories + ['All'], columns=all_categories + ['All'], fill_value=0)
    
    color = ['white', 'dodgerblue']
    levels = [0, 1]
    value = 'exact_match'
    jenis = 'VERqual'

    status_update("Calculating metrics")
    accuracy, hss, pss = calculate_metrics(clipped_df_prakiraan['CH_category'], clipped_df_analisis['CH_category'], contingency_qual)
    
    status_update("Creating verification map")
    plot_data = create_map(clipped_merged_df, value, jenis, color, levels, info)
    
    del df_prakiraan, df_analisis, merged_df, gdf_prakiraan, gdf_analisis, gdf_merged, clipped_df_prakiraan, clipped_df_analisis, clipped_merged_df
    
    fig = plot_data['fig']
    ax = plot_data['ax']

    minx, maxx = ax.get_xlim()
    miny, maxy = ax.get_ylim()
    x_pos = maxx - (maxx - minx) * 0.95
    width = maxx - minx
    height = maxy - miny
    space = height * 0.027344

    bottom_space = miny + (height * 0.05)
    middle_space = bottom_space + space
    top_space = middle_space + space

    status_update("Adding metrics to plot")
    ax.text(x_pos, top_space, f"Akurasi (PC): {((accuracy)*100):.0f}%", fontsize=32, ha='left', va='center', fontweight='bold', zorder=11)
    ax.text(x_pos, middle_space, f"HSS: {((hss)*100):.0f}%", fontsize=32, ha='left', va='center', fontweight='normal', zorder=11)
    ax.text(x_pos, bottom_space, f"PSS: {((pss)*100):.0f}%", fontsize=32, ha='left', va='center', fontweight='normal', zorder=11)

    rect_x = x_pos - (space * 0.5)
    rect_y = bottom_space - (space * 0.75)
    ax.add_patch(Rectangle((rect_x, rect_y), width * 0.248582, height * 0.098, edgecolor='black', facecolor='white', fill=True, lw=4, zorder=10))

    status_update("Saving verification plot")
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, transparent=True, bbox_inches='tight')
    buf.seek(0)
    plot_data['image'] = load_image_to_memory(buf)
    plot_data['accuracy'] = accuracy
    plot_data['hss'] = hss
    plot_data['pss'] = pss
    plt.close(fig)
    return plot_data


# =============================================================================
# NORMAL & BIAS
# =============================================================================

def get_normal():
    status_update("Processing Normal map")
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    normal_filename = "DATA_CH_NORMAL_PAPBAR_1991_2020.xlsx"
    status_update("Loading normal data")
    df_normal = pd.read_excel(os.path.join(CACHE_DIR, normal_filename))
    df_normal[['LON', 'LAT']] = df_normal[['LON', 'LAT']].round(2)
    levels = [0, 20, 50, 100, 150, 200, 300, 400, 500, 1000]
    color = ['#340A00', '#8E2800', '#DC6200', '#EFA800', '#EBE100', '#E0FD68', '#8AD58B', '#369135', '#00460C']
    value = cfg.month
    jenis = 'NORMAL'
    status_update("Creating normal map")
    plot_data = create_map(df_normal, value, jenis, color, levels, info)
    return plot_data


def bias_map():
    status_update("Processing Bias map")
    df_prakiraan, df_analisis, merged_df = arrange_table()
    info = cfg.year, cfg.month, cfg.dasarian, cfg.year_ver, cfg.month_ver, cfg.dasarian_ver, cfg.wilayah
    status_update("Calculating bias")
    merged_df['bias'] = merged_df['VAL'] - merged_df['CH']
    levels = [-1000, -500, -400, -300, -200, -100, -50, -25, 0, 25, 50, 100, 200, 300, 400, 500, 1000]
    color = ['#af3547', '#c74651', '#dc5b5e', '#ea7972', '#f19580', '#f5ae8a', '#f7c69a', '#ffffff', '#ffffff', '#bbe3f0', '#95d8ee', '#62cdef', '#34c0ec', '#0cafe4', '#0094d2', '#0074bc']
    value = 'bias'
    jenis = 'BIAS'
    status_update("Creating bias map")
    plot_data = create_map(merged_df, value, jenis, color, levels, info)
    ax = plot_data['ax']
    fig = plot_data['fig']
    status_update("Loading ocean depth layer")
    hgt_data = get_hgt_data()
    rasterio.plot.show(hgt_data['data'], ax=ax, extent=hgt_data['extent'], cmap='Blues_r')
    status_update("Ocean depth layer loaded")

    plot_data['ax'] = ax
    status_update("Saving bias map")
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=200, transparent=True, bbox_inches='tight')
    buf.seek(0)
    plot_data['image'] = load_image_to_memory(buf)
    return plot_data
