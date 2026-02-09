# map_creation.py
"""
Core map creation: raster interpolation and scatter plot visualization.
Shared plotting helpers + two public entry points: create_map, create_scatter_map.
"""

import io
import gc
from datetime import datetime

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
from scipy.interpolate import RegularGridInterpolator
import rioxarray
import xarray as xr
import rasterio.plot
from scipy.ndimage import gaussian_filter

from .config import cfg
from .static import font_path, get_basemap, get_hgt_data
from .utils import load_image_to_memory, count_points
from .status import update as status_update


# =============================================================================
# SHARED PLOTTING HELPERS
# =============================================================================

def _setup_figure(figsize=(20, 20)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.set_frameon(False)
    ax.set_position([0, 0, 1, 1])
    return fig, ax


def _setup_extent(ax, bounds, buffer_frac=0.05):
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


def _add_kabupaten_labels(ax, shp_main, fontsize=26, font_style='medium'):
    status_update("Adding labels")
    fontprop = fm.FontProperties(fname=font_path(font_style), stretch=115)
    for _, row in shp_main.iterrows():
        centroid = row.geometry.centroid
        ax.annotate(
            row['KABUPATEN'], (centroid.x, centroid.y),
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


def _add_lonlat_ticks(ax, label_tick_fontsize=25, tick_width=3, tick_length=10, padding_label=20):
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


def _save_plot_to_image(fig, dpi=200):
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
        ver_title = f"_ver_{year_ver}.{month_ver:02d}.{dasarian_ver_local}"
    else:
        ver_title = ""
        das_title = ""

    status_update("Basemap loaded")

    if not isinstance(df, gpd.GeoDataFrame):
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.LON, df.LAT), crs=shp_crs)
    else:
        gdf = df

    clipped_gdf = gpd.clip(gdf, shp_main)
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


def _finalize_map(fig, ax, ctx, levels, province_counts=None, kabupaten_counts=None):
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
            _add_lonlat_ticks(ax, label_tick_fontsize=45, tick_width=7, tick_length=20, padding_label=30)
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
    }

    if not cfg.png_only:
        plt.close(fig)
    gc.collect()
    status_update("Map creation complete")
    return plot_data


# =============================================================================
# GRID INTERPOLATION (raster-specific)
# =============================================================================

_grid_cache = {}


def _get_fine_grid(shp_main, shp_crs):
    bounds = tuple(shp_main.total_bounds)
    if bounds in _grid_cache:
        return _grid_cache[bounds]

    minx, miny, maxx, maxy = bounds
    output_cell_size = 0.0021648361216
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

    result = {
        'x_grid': x_grid, 'y_grid': y_grid,
        'template': template, 'bounds': bounds,
    }
    _grid_cache[bounds] = result
    return result


def _interpolate_regular_grid(lon_pts, lat_pts, values, x_grid, y_grid, method='linear'):
    from scipy.ndimage import distance_transform_edt

    unique_lon = np.sort(np.unique(lon_pts))
    unique_lat = np.sort(np.unique(lat_pts))

    grid_values = np.full((len(unique_lat), len(unique_lon)), np.nan, dtype=np.float32)
    lon_idx = np.searchsorted(unique_lon, lon_pts)
    lat_idx = np.searchsorted(unique_lat, lat_pts)
    grid_values[lat_idx, lon_idx] = values

    # Fill NaN cells (ocean/missing) with nearest valid value
    mask = np.isnan(grid_values)
    if mask.any():
        ind = distance_transform_edt(mask, return_distances=False, return_indices=True)
        grid_values = grid_values[tuple(ind)]

    interpolator = RegularGridInterpolator(
        (unique_lat, unique_lon), grid_values,
        method=method, bounds_error=False, fill_value=np.nan
    )

    grid_lat_fine, grid_lon_fine = np.meshgrid(y_grid, x_grid, indexing='ij')
    query = np.column_stack((grid_lat_fine.ravel(), grid_lon_fine.ravel()))
    return interpolator(query).reshape(grid_lat_fine.shape)

def clear_spatial_cache():
    global _grid_cache
    _grid_cache = {}


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
    ctx = _prepare_map_context(df, value, jenis, info)
    
    # ---- Interpolation ----
    lon_full = ctx['gdf'].geometry.x.to_numpy()
    lat_full = ctx['gdf'].geometry.y.to_numpy()
    values_full = ctx['gdf'][value].to_numpy()

    fine = _get_fine_grid(ctx['shp_main'], ctx['shp_crs'])

    unique_values = np.unique(values_full[~np.isnan(values_full)])
    is_discrete = len(unique_values) <= 10

    method = 'nearest' if is_discrete else getattr(cfg, 'interpolation_method', 'linear')
    status_update(f"Starting interpolation (method={method})")

    interpolated = _interpolate_regular_grid(
        lon_full, lat_full, values_full.astype(np.float32),
        fine['x_grid'], fine['y_grid'], method=method
    )
    
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
    clipped_data.plot(ax=ax, levels=levels, norm=norm, cmap=cmap, zorder=3, add_colorbar=False)
    ctx['shp_main'].plot(ax=ax, facecolor="none", edgecolor='k', zorder=4)

    if not cfg.png_only and cfg.peta == 'Probabilistik':
        ax.grid(c='k', alpha=0.4)
        for spine in ax.spines.values():
            spine.set_linewidth(7)

    plot_data = _finalize_map(fig, ax, ctx, levels, province_counts, kabupaten_counts)

    del clipped_data, interpolated
    return plot_data


# =============================================================================
# PUBLIC: SCATTER MAP (categorical points)
# =============================================================================

def create_scatter_map(df, value, jenis, colors, info):
    ctx = _prepare_map_context(df, value, jenis, info)
    scatter_sizes = {
        0: 300,
        1: 550,
        2: 600,
        3: 600,
        4: 600,
        5: 600,
    }
    # ---- Plot ----
    status_update("Creating scatter plot")
    fig, ax = _setup_figure()
    ax.axis('off')

    ctx['shp_main'].plot(ax=ax, facecolor='#FFFDE7', edgecolor='k', linewidth=1.0, zorder=2)
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

    return _finalize_map(fig, ax, ctx, levels=list(colors.keys()))












