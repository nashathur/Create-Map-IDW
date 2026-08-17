# map_creation.py
"""
Core map creation: raster interpolation and scatter plot visualization.
Shared plotting helpers + two public entry points: create_map, create_scatter_map.
"""

import io
import gc
import os
import hashlib
from datetime import datetime

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
from scipy.interpolate import RegularGridInterpolator
import rioxarray
import xarray as xr
import rasterio.plot
from scipy.ndimage import gaussian_filter

from .config import (
    cfg, is_colab, GRID, INTERP, RENDER, RENDER_PROB, COLORS,
    HTH_KLASIFIKASI, SCATTER_SIZES,
)
from .static import font_path, get_basemap, get_hgt_data
from .utils import load_image_to_memory, count_points
from .status import update as status_update


# =============================================================================
# SHARED PLOTTING HELPERS
# =============================================================================

def _setup_figure(figsize=None):
    figsize = RENDER['figsize'] if figsize is None else figsize
    fig, ax = plt.subplots(figsize=figsize)
    fig.set_frameon(False)
    ax.set_position([0, 0, 1, 1])
    return fig, ax


def _setup_extent(ax, bounds, buffer_frac=None):
    buffer_frac = RENDER['buffer_frac'] if buffer_frac is None else buffer_frac
    minx, miny, maxx, maxy = bounds
    x_center = (minx + maxx) / 2
    y_center = (miny + maxy) / 2
    x_range = maxx - minx
    y_range = maxy - miny
    max_range = max(x_range, y_range)
    buffer = buffer_frac * max_range
    ax.set_xlim(x_center - (max_range + buffer) / 2, x_center + (max_range + buffer) / 2)
    ax.set_ylim(y_center - (max_range + buffer) / 2, y_center + (max_range + buffer) / 2)
    ax.set_aspect('equal', 'box')


def _add_kabupaten_labels(ax, shp_main, fontsize=None, font_style='medium'):
    fontsize = RENDER['kabupaten_fontsize'] if fontsize is None else fontsize
    status_update("Adding labels")
    fontprop = fm.FontProperties(fname=font_path(font_style), stretch=115)
    # One vectorized centroid pass instead of recomputing per row.
    centroids = shp_main.geometry.centroid
    for name, cx, cy in zip(shp_main['KABUPATEN'].to_numpy(),
                            centroids.x.to_numpy(), centroids.y.to_numpy()):
        ax.annotate(
            name, (cx, cy),
            fontsize=fontsize, ha='center', va='center',
            zorder=4, fontproperties=fontprop
        )


def _calculate_step(range_val):
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


def _add_lonlat_ticks(ax, label_tick_fontsize=None, tick_width=None, tick_length=None, padding_label=None):
    label_tick_fontsize = RENDER['label_tick_fontsize'] if label_tick_fontsize is None else label_tick_fontsize
    tick_width = RENDER['tick_width'] if tick_width is None else tick_width
    tick_length = RENDER['tick_length'] if tick_length is None else tick_length
    padding_label = RENDER['padding_label'] if padding_label is None else padding_label
    ax.grid(c='k', alpha=0.1)
    ax.axis('on')

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    xr_ = xlim[1] - xlim[0]
    yr_ = ylim[1] - ylim[0]

    x_step = _calculate_step(xr_)
    y_step = _calculate_step(yr_)

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


def _save_plot_to_image(fig, dpi=None):
    dpi = RENDER['dpi'] if dpi is None else dpi
    status_update("Saving plot to buffer")
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi, transparent=True, bbox_inches='tight')
    buf.seek(0)
    return load_image_to_memory(buf)


# =============================================================================
# SHARED CONTEXT: PREPARE & FINALIZE
# =============================================================================

def _prepare_map_context(df, value, jenis, info):
    """Load basemap, build GeoDataFrame, clip, resolve filename."""
    status_update(f"Processing {value}")
    year, month, dasarian, year_ver, month_ver, dasarian_ver, wilayah = info

    basemaps = get_basemap(wilayah)
    shp_main = basemaps['shp_main']
    shp_crs = basemaps['crs']
    others_shp = basemaps['others_shp']
    nama_wilayah = basemaps['nama_wilayah']

    if cfg.peta in ('Prakiraan', 'Verifikasi'):
        if cfg.skala == "Bulanan":
            das_title = ""
            dasarian_ver_local = ""
        else:
            das_title = f".das{dasarian}"
            dasarian_ver_local = dasarian_ver
        ver_title = f"_ver_{year_ver}.{month_ver:02d}" + (f".{dasarian_ver_local}" if dasarian_ver_local else "")
    else:
        ver_title = ""
        das_title = ""

    status_update("Basemap loaded")

    if not isinstance(df, gpd.GeoDataFrame):
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.LON, df.LAT), crs=shp_crs)
    else:
        gdf = df

    clipped_gdf = gpd.clip(gdf, shp_main)
    if clipped_gdf.empty:
        raise ValueError(
            f"Tidak ada titik data yang berada dalam wilayah '{nama_wilayah}'. "
            f"Periksa apakah koordinat LON/LAT pada file sesuai dengan wilayah yang dipilih. "
            f"Data memiliki {len(gdf)} titik, tetapi tidak ada yang berada dalam batas wilayah."
        )
    status_update("Clipping data done")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"plot_{timestamp}_{jenis}_{year}.{month:02d}{das_title}{ver_title}.png"

    return {
        'year': year, 'month': month, 'dasarian': dasarian,
        'year_ver': year_ver, 'month_ver': month_ver, 'dasarian_ver': dasarian_ver,
        'shp_main': shp_main, 'shp_crs': shp_crs, 'others_shp': others_shp,
        'nama_wilayah': nama_wilayah,
        'gdf': gdf, 'clipped_gdf': clipped_gdf,
        'jenis': jenis, 'value': value, 'file_name': file_name,
        'bounds': tuple(shp_main.total_bounds),
    }


def _finalize_map(fig, ax, ctx, levels, province_counts=None, kabupaten_counts=None, joined_gdf=None, hth_table_data=None):
    """Add overlays, ticks, save image, build plot_data dict, cleanup."""
    _setup_extent(ax, ctx['bounds'])
    _add_kabupaten_labels(ax, ctx['shp_main'])

    if ctx['others_shp'] is not None and len(ctx['others_shp']) > 0 and not cfg.png_only:
        ctx['others_shp'].plot(ax=ax, facecolor='0.8', edgecolor='k', zorder=1)

    if cfg.hgt:
        hgt_data = get_hgt_data()
        rasterio.plot.show(hgt_data['data'], ax=ax, extent=hgt_data['extent'], cmap='Blues_r')
        status_update("Ocean depth layer loaded")

    if not cfg.png_only:
        if cfg.peta == 'Probabilistik':
            _add_lonlat_ticks(
                ax,
                label_tick_fontsize=RENDER_PROB['label_tick_fontsize'],
                tick_width=RENDER_PROB['tick_width'],
                tick_length=RENDER_PROB['tick_length'],
                padding_label=RENDER_PROB['padding_label'],
            )
        else:
            _add_lonlat_ticks(ax)

    img = _save_plot_to_image(fig)

    plot_data = {
        'fig': fig, 'ax': ax,
        'peta': cfg.peta, 'tipe': cfg.tipe, 'skala': cfg.skala,
        'jenis': ctx['jenis'], 'year': ctx['year'], 'month': ctx['month'],
        'dasarian': ctx['dasarian'], 'dasarian_ver': ctx['dasarian_ver'],
        'month_ver': ctx['month_ver'], 'year_ver': ctx['year_ver'],
        'value': ctx['value'], 'levels': levels,
        'province_data': province_counts, 'kabupaten_data': kabupaten_counts,
        'image': img, 'file_name': ctx['file_name'],
        'nama_wilayah': ctx['nama_wilayah'],
        'joined_gdf': joined_gdf,
        'hth_table_data': hth_table_data,
    }

    if not cfg.png_only and cfg.peta != 'Bias':
        plt.close(fig)
    gc.collect()
    status_update("Map creation complete")
    return plot_data


# =============================================================================
# GRID INTERPOLATION (raster-specific)
# =============================================================================

_grid_cache = {}


def _get_fine_grid(shp_main, shp_crs):
    # Key includes cell_size: it is configurable now, so bounds alone would
    # collide across two runs with different resolutions.
    bounds = tuple(shp_main.total_bounds)
    output_cell_size = GRID['cell_size']
    cache_key = (bounds, output_cell_size)
    if cache_key in _grid_cache:
        return _grid_cache[cache_key]

    minx, miny, maxx, maxy = bounds
    ncols = int(np.ceil((maxx - minx) / output_cell_size))
    nrows = int(np.ceil((maxy - miny) / output_cell_size))
    x_grid = np.linspace(minx, minx + ncols * output_cell_size, ncols + 1)
    y_grid = np.linspace(miny, miny + nrows * output_cell_size, nrows + 1)

    template = xr.DataArray(
        np.empty((len(y_grid), len(x_grid)), dtype=np.float32),
        coords={'lat': y_grid, 'lon': x_grid},
        dims=['lat', 'lon']
    )
    template = template.rio.set_spatial_dims("lon", "lat", inplace=True)
    template = template.rio.write_crs(shp_crs)

    # Query points depend only on the grid, not on the values being
    # interpolated. Probabilistik interpolates six columns over identical
    # coordinates, so building this once instead of six times matters.
    grid_lat_fine, grid_lon_fine = np.meshgrid(y_grid, x_grid, indexing='ij')
    query = np.column_stack((grid_lat_fine.ravel(), grid_lon_fine.ravel()))

    result = {
        'x_grid': x_grid, 'y_grid': y_grid,
        'template': template, 'bounds': bounds,
        'query': query, 'shape': grid_lat_fine.shape,
    }
    _grid_cache[cache_key] = result
    return result


# Station lattice (unique coords + searchsorted indices) reused across columns
# that share coordinates -- again, the Probabilistik six-column case.
_lattice_cache = {}


def _get_station_lattice(lon_pts, lat_pts):
    key = (
        hashlib.blake2b(np.ascontiguousarray(lon_pts).tobytes(), digest_size=16).digest(),
        hashlib.blake2b(np.ascontiguousarray(lat_pts).tobytes(), digest_size=16).digest(),
    )
    cached = _lattice_cache.get(key)
    if cached is not None:
        return cached

    unique_lon = np.sort(np.unique(lon_pts))
    unique_lat = np.sort(np.unique(lat_pts))
    entry = {
        'unique_lon': unique_lon,
        'unique_lat': unique_lat,
        'lon_idx': np.searchsorted(unique_lon, lon_pts),
        'lat_idx': np.searchsorted(unique_lat, lat_pts),
        'edt': {},   # nearest-fill indices, keyed by NaN pattern
    }
    _lattice_cache[key] = entry
    return entry


def _interpolate_regular_grid(lon_pts, lat_pts, values, fine, method='linear'):
    from scipy.ndimage import distance_transform_edt

    lat = _get_station_lattice(lon_pts, lat_pts)
    unique_lon, unique_lat = lat['unique_lon'], lat['unique_lat']

    grid_values = np.full((len(unique_lat), len(unique_lon)), np.nan, dtype=np.float32)
    grid_values[lat['lat_idx'], lat['lon_idx']] = values

    # Fill NaN cells (ocean/missing) with nearest valid value. The result
    # depends only on WHICH cells are NaN, so cache it per NaN pattern -- the
    # six Probabilistik columns normally share one pattern.
    mask = np.isnan(grid_values)
    if mask.any():
        mkey = hashlib.blake2b(np.packbits(mask).tobytes(), digest_size=16).digest()
        ind = lat['edt'].get(mkey)
        if ind is None:
            ind = distance_transform_edt(mask, return_distances=False, return_indices=True)
            lat['edt'][mkey] = ind
        grid_values = grid_values[tuple(ind)]

    interpolator = RegularGridInterpolator(
        (unique_lat, unique_lon), grid_values,
        method=method, bounds_error=False, fill_value=np.nan
    )
    return interpolator(fine['query']).reshape(fine['shape'])


def _is_regular_lattice(coords, tolerance=None):
    """True if sorted distinct coords are evenly spaced.

    Keys on spacing regularity rather than on the lattice being fully populated:
    gridded model output legitimately has holes over ocean, and the regular-grid
    path already handles those via nearest-fill.
    """
    tolerance = INTERP['spacing_tolerance'] if tolerance is None else tolerance
    uniq = np.sort(np.unique(coords[~np.isnan(coords)]))
    if uniq.size < 3:
        return True   # too few distinct values to call it irregular
    diffs = np.diff(uniq)
    step = np.median(diffs)
    if step <= 0:
        return False
    return bool(np.all(np.abs(diffs - step) <= tolerance * step))


def _resolve_interp_method(lon_pts, lat_pts, is_discrete):
    """Decide which interpolator to run, and say why.

    Returns (method, reason). Discrete fields always force 'nearest' -- verif
    maps pass 0/1 and must not be smoothed into intermediate values.
    """
    if is_discrete:
        return 'nearest', 'data diskrit'

    configured = INTERP.get('method', 'auto')
    if configured != 'auto':
        return configured, 'diatur di INTERP'

    regular = _is_regular_lattice(lon_pts) and _is_regular_lattice(lat_pts)
    if regular:
        return 'linear', 'grid teratur terdeteksi'
    return 'idw', 'titik tidak teratur (stasiun)'


def _interpolate_idw(lon_pts, lat_pts, values, fine):
    """IDW over the k nearest stations, matching ArcGIS Spatial Analyst defaults.

    power=2 and n_neighbors=12 are the ArcGIS defaults. NaN stations are dropped
    before the tree is built -- otherwise a single NaN neighbour poisons every
    output cell that references it.
    """
    from scipy.spatial import cKDTree
    from .utils import idw_numba

    valid = ~np.isnan(values)
    if not valid.any():
        raise ValueError("Semua nilai kosong (NaN); interpolasi IDW tidak bisa dijalankan.")
    lon_v = lon_pts[valid]
    lat_v = lat_pts[valid]
    val_v = np.ascontiguousarray(values[valid], dtype=np.float32)

    power = float(INTERP['power'])
    k = min(int(INTERP['n_neighbors']), val_v.size)

    tree = cKDTree(np.column_stack((lon_v, lat_v)))
    # fine['query'] is (lat, lon); the tree is (lon, lat)
    query_lonlat = fine['query'][:, ::-1]
    dists, idx = tree.query(query_lonlat, k=k, workers=-1)
    if k == 1:
        dists = dists[:, None]
        idx = idx[:, None]

    smoothing = float(INTERP.get('smoothing', 0.0))
    if smoothing:
        dists = dists + smoothing

    flat = idw_numba(val_v, np.ascontiguousarray(dists, dtype=np.float64),
                     np.ascontiguousarray(idx, dtype=np.int64), power)
    return flat.reshape(fine['shape']).astype(np.float64)


def clear_spatial_cache():
    global _grid_cache, _lattice_cache
    _grid_cache = {}
    _lattice_cache = {}


# =============================================================================
# PUBLIC: RASTER MAP (interpolated)
# =============================================================================

def create_map(df, value, jenis, color, levels, info):
    """
    Create an interpolated raster map from ECMWF regular-grid data.

    Interpolation method from cfg.interpolation_method.
    Supported: 'linear' (default), 'cubic', 'nearest'.
    Discrete fields (<=10 unique values) always use 'nearest'.
    """
    if value not in df.columns:
        raise ValueError(
            f"Kolom '{value}' tidak ditemukan pada DataFrame. "
            f"Kolom yang tersedia: {list(df.columns)}. "
            f"Pastikan file yang diupload memiliki kolom '{value}'."
        )

    ctx = _prepare_map_context(df, value, jenis, info)

    # ---- Interpolation ----
    lon_full = ctx['gdf'].geometry.x.to_numpy()
    lat_full = ctx['gdf'].geometry.y.to_numpy()
    values_full = ctx['gdf'][value].to_numpy()

    fine = _get_fine_grid(ctx['shp_main'], ctx['shp_crs'])

    unique_values = np.unique(values_full[~np.isnan(values_full)])
    is_discrete = len(unique_values) <= INTERP['discrete_threshold']

    method, reason = _resolve_interp_method(lon_full, lat_full, is_discrete)
    status_update(f"Starting interpolation (method={method}; {reason})")

    if method == 'idw':
        interpolated = _interpolate_idw(
            lon_full, lat_full, values_full.astype(np.float32), fine
        )
    else:
        interpolated = _interpolate_regular_grid(
            lon_full, lat_full, values_full.astype(np.float32),
            fine, method=method
        )

    sigma = float(INTERP.get('gaussian_sigma', 0.0))
    if sigma:
        nanmask = np.isnan(interpolated)
        if nanmask.any():
            filled = np.where(nanmask, np.nanmean(interpolated), interpolated)
            interpolated = gaussian_filter(filled, sigma=sigma)
            interpolated[nanmask] = np.nan
        else:
            interpolated = gaussian_filter(interpolated, sigma=sigma)

    data_array = fine['template'].copy(data=interpolated)
    data_array = data_array.rio.set_spatial_dims("lon", "lat", inplace=True)
    clipped_data = data_array.rio.clip(ctx['shp_main'].geometry)
    status_update("Interpolation complete")

    # ---- Colormap ----
    status_update("Applying colormap")
    if color is not None:
        cmap = mcolors.ListedColormap(color) if isinstance(color, list) else color
    else:
        cmap = plt.cm.get_cmap('viridis' if not is_discrete else 'Set1', len(unique_values))

    if levels is None:
        if not is_discrete:
            vmin, vmax = np.nanmin(clipped_data), np.nanmax(clipped_data)
            levels = np.linspace(vmin, vmax, 10)
        else:
            levels = unique_values

    norm = mcolors.BoundaryNorm(levels, cmap.N)
    status_update("Colormap applied")

    # ---- Count points by region ----
    status_update("Counting points by region")
    clipped_gdf = ctx['clipped_gdf']
    joined = gpd.sjoin(clipped_gdf, ctx['shp_main'][['PROVINSI', 'KABUPATEN', 'geometry']], predicate='within')
    province_counts = {}
    for prov_name, group in joined.groupby('PROVINSI'):
        province_counts[prov_name] = count_points(group, value, levels)
    kabupaten_counts = {}
    for kab_name, group in joined.groupby('KABUPATEN'):
        kabupaten_counts[kab_name] = count_points(group, value, levels)
    status_update("Point counting complete")

    # ---- Plot ----
    status_update("Creating plot")
    fig, ax = _setup_figure()
    ax.axis('off')

    if 'spatial_ref' in clipped_data.coords:
        clipped_data = clipped_data.drop_vars('spatial_ref')
    # pcolormesh (default) draws one rectangle per grid cell, so class
    # boundaries follow cell edges as a staircase. contourf traces the level
    # crossing between cell centres and fills smooth polygons instead.
    if INTERP.get('render_mode') == 'contourf':
        clipped_data.plot.contourf(
            ax=ax, levels=levels, norm=norm, cmap=cmap, zorder=3, add_colorbar=False
        )
    else:
        clipped_data.plot(ax=ax, levels=levels, norm=norm, cmap=cmap, zorder=3, add_colorbar=False)
    ctx['shp_main'].plot(ax=ax, facecolor="none", edgecolor='k', zorder=4)

    if not cfg.png_only and cfg.peta == 'Probabilistik':
        ax.grid(c='k', alpha=0.4)
        for spine in ax.spines.values():
            spine.set_linewidth(7)

    if jenis == 'BIAS':
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(
            sm, ax=ax, orientation='horizontal',
            fraction=0.046, pad=0.04, shrink=0.8,
            ticks=levels,
        )
        cbar.set_label('Bias (mm)', fontsize=20, fontweight='bold')
        cbar.ax.tick_params(labelsize=14, rotation=45)

    plot_data = _finalize_map(fig, ax, ctx, levels, province_counts, kabupaten_counts, joined_gdf=joined)
    # Which interpolator actually ran, and why. This replaces a notebook toggle:
    # the operator does not choose the method, but can always see what was chosen.
    plot_data['interp_method'] = method
    plot_data['interp_reason'] = reason

    del clipped_data, interpolated
    return plot_data


# =============================================================================
# HTH TABLE HELPER
# =============================================================================

_HTH_KLASIFIKASI = HTH_KLASIFIKASI


def _build_hth_rows(joined):
    """Build lightweight HTH table data from the spatial-joined GeoDataFrame.

    Filters out index 0 (Masih Ada Hujan), maps indices to klasifikasi names,
    and detects optional KECAMATAN/POS columns.

    Returns:
        dict with 'columns' and 'rows', or None if no data after filtering.
    """
    df = joined[joined['INDEKS_HTH'] != 0].copy()
    if len(df) == 0:
        return None

    df['KLASIFIKASI'] = df['INDEKS_HTH'].map(_HTH_KLASIFIKASI)

    columns = ['Provinsi', 'Kabupaten']
    col_keys = ['PROVINSI', 'KABUPATEN']

    if 'KECAMATAN' in df.columns and df['KECAMATAN'].notna().any():
        columns.append('Kecamatan')
        col_keys.append('KECAMATAN')
    if 'POS' in df.columns and df['POS'].notna().any():
        columns.append('Pos Hujan')
        col_keys.append('POS')

    columns.append('Indeks HTH')

    df = df.sort_values(['PROVINSI', 'KABUPATEN', 'INDEKS_HTH'])

    # Column-wise str() instead of .iterrows(): iterrows builds a Series per
    # row, which dominates the cost here. Semantics are kept EXACTLY as before,
    # including str(NaN) -> 'nan' for blank cells; a missing column still
    # yields '' as row.get(ck, '') did.
    out_keys = col_keys + ['KLASIFIKASI']
    cols_str = [
        df[k].map(str).tolist() if k in df.columns else [''] * len(df)
        for k in out_keys
    ]
    rows = [list(r) for r in zip(*cols_str)]

    return {'columns': columns, 'rows': rows}


# =============================================================================
# PUBLIC: SCATTER MAP (categorical points)
# =============================================================================

def create_scatter_map(df, value, jenis, colors, info):
    if value not in df.columns:
        raise ValueError(
            f"Kolom '{value}' tidak ditemukan pada DataFrame. "
            f"Kolom yang tersedia: {list(df.columns)}. "
            f"Pastikan file yang diupload memiliki kolom '{value}'."
        )

    ctx = _prepare_map_context(df, value, jenis, info)
    scatter_sizes = SCATTER_SIZES
    # ---- Plot ----
    status_update("Creating scatter plot")
    fig, ax = _setup_figure()
    ax.axis('off')

    ctx['shp_main'].plot(ax=ax, facecolor=COLORS['basemap_fill'], edgecolor='k', linewidth=1.0, zorder=2)
    ctx['shp_main'].plot(ax=ax, facecolor="none", edgecolor='k', zorder=4)

    clipped_gdf = ctx['clipped_gdf']
    for cat_val, cat_color in colors.items():
        subset = clipped_gdf[clipped_gdf[value] == cat_val]
        if len(subset) > 0:
            ax.scatter(
                subset.geometry.x, subset.geometry.y,
                c=cat_color, s=scatter_sizes.get(cat_val, 300),
                edgecolors='black', linewidths=0.5, zorder=5
            )

    joined = gpd.sjoin(clipped_gdf, ctx['shp_main'][['PROVINSI', 'KABUPATEN', 'geometry']], predicate='within')

    # Pre-compute HTH table data if Word output is requested
    hth_table = None
    if cfg.create_word and cfg.peta == 'HTH':
        hth_table = _build_hth_rows(joined)

    return _finalize_map(fig, ax, ctx, levels=list(colors.keys()), joined_gdf=joined,
                         hth_table_data=hth_table)


# =============================================================================
# CSV EXPORT
# =============================================================================

def _export_csv(plot_data):
    """Export station-level data from plot_data as CSV and auto-download in Colab."""

    joined_gdf = plot_data.get('joined_gdf')
    if joined_gdf is None or len(joined_gdf) == 0:
        print("No data available for CSV export.")
        return

    value_col = plot_data.get('value')
    keep_cols = ['LON', 'LAT']
    if value_col and value_col in joined_gdf.columns:
        keep_cols.append(value_col)
    if 'PROVINSI' in joined_gdf.columns:
        keep_cols.append('PROVINSI')
    if 'KABUPATEN' in joined_gdf.columns:
        keep_cols.append('KABUPATEN')

    # Include any other numeric data columns present (but not index columns from sjoin)
    skip = {'index_right', 'index_left', 'geometry'}
    for col in joined_gdf.columns:
        if col not in keep_cols and col not in skip:
            if joined_gdf[col].dtype.kind in ('f', 'i'):
                keep_cols.append(col)

    export_df = joined_gdf[[c for c in keep_cols if c in joined_gdf.columns]].copy()
    export_df = export_df.reset_index(drop=True)


    png_name = plot_data.get('file_name', 'export')
    csv_name = os.path.splitext(png_name)[0] + '.csv'
    output_dir = '/content' if is_colab() else os.getcwd()
    csv_path = os.path.join(output_dir, csv_name)

    export_df.to_csv(csv_path, index=False)
    status_update(f"CSV exported: {csv_name} ({len(export_df)} rows)")

    try:
        from google.colab import files
        files.download(csv_path)
    except ImportError:
        print(f"CSV saved to: {csv_path}")











