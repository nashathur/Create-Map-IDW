# map_creation.py
"""
Core map creation with IDW interpolation and visualization.
"""

import io
import gc
from datetime import datetime

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
from scipy.interpolate import griddata
from scipy.spatial import cKDTree
import rioxarray
import xarray as xr
import rasterio.plot

from .config import cfg
from .static import font_path, get_basemap, get_hgt_data
from .utils import load_image_to_memory, idw_numba, count_points

_spatial_cache = {}

def _get_spatial(shp_main, shp_crs, lon, lat, n_neighbors=6):
    """Cache grid, tree, query results, and clip geometry for a given spatial extent + point set."""
    bounds = tuple(shp_main.total_bounds)
    pts_hash = (lon.tobytes(), lat.tobytes())  # identity of point locations
    cache_key = (bounds, pts_hash)

    if cache_key in _spatial_cache:
        return _spatial_cache[cache_key]

    minx, miny, maxx, maxy = bounds
    output_cell_size = 0.0021648361216
    ncols = int(np.ceil((maxx - minx) / output_cell_size))
    nrows = int(np.ceil((maxy - miny) / output_cell_size))
    x_grid = np.linspace(minx, minx + ncols * output_cell_size, ncols + 1)
    y_grid = np.linspace(miny, miny + nrows * output_cell_size, nrows + 1)
    grid_lon, grid_lat = np.meshgrid(x_grid, y_grid)

    xy = np.column_stack((lon.astype(np.float32), lat.astype(np.float32)))
    tree = cKDTree(xy)
    query_points = np.column_stack((grid_lon.ravel().astype(np.float32), grid_lat.ravel().astype(np.float32)))
    dists, idx = tree.query(query_points, k=n_neighbors)
    dists = dists.astype(np.float32)

    # Pre-build the xarray template and clip mask once
    template = xr.DataArray(
        np.empty(grid_lon.shape, dtype=np.float32),
        coords={'lat': y_grid, 'lon': x_grid},
        dims=['lat', 'lon']
    )
    template = template.rio.set_spatial_dims("lon", "lat", inplace=True)
    template = template.rio.write_crs(shp_crs)

    result = {
        'x_grid': x_grid,
        'y_grid': y_grid,
        'grid_lon': grid_lon,
        'grid_lat': grid_lat,
        'dists': dists,
        'idx': idx,
        'query_shape': grid_lon.shape,
        'template': template,
        'bounds': bounds,
    }

    _spatial_cache[cache_key] = result
    return result

def clear_spatial_cache():
    global _spatial_cache
    _spatial_cache = {}
    
def create_map(df, value, jenis, color, levels, info):
    print(f"\rProcessing {value}", end="", flush=True)
    year, month, dasarian, year_ver, month_ver, dasarian_ver, wilayah = info
    custom_colors = color
    custom_levels = levels
    basemaps = get_basemap(wilayah)
    shp_main = basemaps['shp_main']
    shp_crs = basemaps['crs']
    others_shp = basemaps['others_shp']
    nama_wilayah = basemaps['nama_wilayah']

    if cfg.peta == 'Prakiraan' or cfg.peta == 'Verifikasi':
        if cfg.skala == "Bulanan":
            das_title = ""
            das_ver_title = ""
            dasarian_local = ""
            dasarian_ver_local = ""
        else:
            dasarian_local = dasarian
            dasarian_ver_local = dasarian_ver
            das_title = f".das{dasarian}"
            das_ver_title = f".das{dasarian_ver}"
        ver_title = f"_ver_{year_ver}.{month_ver:02d}.{dasarian_ver_local}"
    else:
        ver_title = ""
        das_title = ""
        das_ver_title = ""

    print("\rBasemap loaded", end="", flush=True)

    if not isinstance(df, gpd.GeoDataFrame):
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.LON, df.LAT), crs=shp_crs)
    else:
        gdf = df

    clipped_gdf = gpd.clip(gdf, shp_main)

    lon = clipped_gdf.geometry.x.to_numpy()
    lat = clipped_gdf.geometry.y.to_numpy()
    values = clipped_gdf[value].to_numpy()
    print(f"\rClipping data done", end="", flush=True)

    # ---- Cached spatial computation ----
    spatial = _get_spatial(shp_main, shp_crs, lon, lat)

    print("\rStarting IDW", end="", flush=True)
    unique_values = np.unique(values[~np.isnan(values)])
    is_discrete = len(unique_values) <= 10
    power = 2

    if not is_discrete:
        vals = values.astype(np.float32)
        zi = idw_numba(vals, spatial['dists'], spatial['idx'], power)
        idw = zi.reshape(spatial['query_shape'])
    else:
        points = np.column_stack((lon, lat))
        idw = griddata(points, values, (spatial['grid_lon'], spatial['grid_lat']), method='nearest', fill_value=np.nan)

    # Reuse template, just swap data
    data_array = spatial['template'].copy(data=idw)
    clipped_data = data_array.rio.clip(shp_main.geometry)
    print("\rIDW Done", end="", flush=True)

    # ---- Colormap (unchanged logic) ----
    print("\rApplying Colormap", end="", flush=True)
    if custom_colors is not None:
        if isinstance(custom_colors, list):
            cmap = mcolors.ListedColormap(custom_colors)
        else:
            cmap = custom_colors
    else:
        cmap = plt.cm.get_cmap('viridis' if not is_discrete else 'Set1', len(unique_values))

    if custom_levels is None:
        if not is_discrete:
            vmin, vmax = np.nanmin(clipped_data), np.nanmax(clipped_data)
            levels = np.linspace(vmin, vmax, 10)
        else:
            levels = unique_values
    else:
        levels = custom_levels

    norm = mcolors.BoundaryNorm(levels, cmap.N)
    print("\rColormap applied", end="", flush=True)

    # ---- Point counts ----
    print("\rStarting point count", end="", flush=True)
    joined = gpd.sjoin(clipped_gdf, shp_main[['PROVINSI', 'KABUPATEN', 'geometry']], predicate='within')
    province_counts = {}
    for prov_name, group in joined.groupby('PROVINSI'):
        province_counts[prov_name] = count_points(group, value, levels)
    kabupaten_counts = {}
    for kab_name, group in joined.groupby('KABUPATEN'):
        kabupaten_counts[kab_name] = count_points(group, value, levels)
    print(f"\rCounting data done", end="", flush=True)

    # ---- Plot ----
    width_x, width_y = (20, 20)
    fig, ax = plt.subplots(figsize=(width_x, width_y))
    fig.set_frameon(False)
    print("\rSetting up fig,ax", end="", flush=True)

    if 'spatial_ref' in clipped_data.coords:
        clipped_data = clipped_data.drop_vars('spatial_ref')

    ax.axis('off')
    ax.set_position([0, 0, 1, 1])

    minx, miny, maxx, maxy = spatial['bounds']

    im = clipped_data.plot(ax=ax, levels=levels, norm=norm, cmap=cmap, zorder=3, add_colorbar=False)
    shp_main.plot(ax=ax, facecolor="none", edgecolor='k', zorder=4)

    x_center = (minx + maxx) / 2
    y_center = (miny + maxy) / 2
    x_range = maxx - minx
    y_range = maxy - miny
    max_range = max(x_range, y_range)
    buffer = 0.05 * max_range

    ax.set_xlim(x_center - (max_range + buffer) / 2, x_center + (max_range + buffer) / 2)
    ax.set_ylim(y_center - (max_range + buffer) / 2, y_center + (max_range + buffer) / 2)
    print("\rAdding up labels", end="", flush=True)
    ax.set_aspect('equal', 'box')

    if cfg.peta == 'Probabilistik':
        label_kab_fontsize = 25
        label_tick_fontsize = 45
        tick_width = 7
        tick_length = 20
        padding_label = 30
        ax.grid(c='k', alpha=0.4)
        for spine in ax.spines.values():
            spine.set_linewidth(tick_width)
    else:
        label_kab_fontsize = 18
        label_tick_fontsize = 25
        tick_width = 3
        tick_length = 10
        padding_label = 20
        ax.grid(c='k', alpha=0.1)

    # Font created once outside loop
    font_style = 'medium'
    fontprop = fm.FontProperties(fname=font_path(font_style), stretch=115)
    label_kab_fontsize = 26

    for idx_row, row in shp_main.iterrows():
        centroid = row.geometry.centroid
        kab_name = row['KABUPATEN']
        ax.annotate(kab_name, (centroid.x, centroid.y), fontsize=label_kab_fontsize, ha='center', va='center', zorder=4, fontproperties=fontprop)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\rMap: {timestamp}_{jenis}_{year}.{month:02d}{das_title}{ver_title} ({value})", end="", flush=True)
    file_name = f"plot_{timestamp}_{jenis}_{year}.{month:02d}{das_title}{ver_title}.png"

    if others_shp is not None and len(others_shp) > 0:
        others_shp.plot(ax=ax, facecolor='0.8', edgecolor='k', zorder=1)

    if cfg.hgt:
        hgt_data = get_hgt_data()
        rasterio.plot.show(hgt_data['data'], ax=ax, extent=hgt_data['extent'], cmap='Blues_r')
        print("\rhgt ocean depth loaded", end="", flush=True)

    lonlat_label = True
    if lonlat_label:
        ax.axis('on')
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]

        def calculate_step(range_val):
            if range_val <= 0.1:
                return 0.05
            elif range_val <= 1:
                return 0.1
            elif range_val <= 5:
                return 0.5
            else:
                return 1

        x_step = calculate_step(x_range)
        y_step = calculate_step(y_range)

        xticks = np.arange(np.floor(xlim[0] / x_step) * x_step, np.ceil(xlim[1] / x_step) * x_step + x_step, x_step)
        yticks = np.arange(np.floor(ylim[0] / y_step) * y_step, np.ceil(ylim[1] / y_step) * y_step + y_step, y_step)

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

        ax.tick_params(which='both', direction='out', length=tick_length, width=tick_width, color='black',
                       top=True, right=True, left=True, bottom=True,
                       labeltop=True, labelright=True, labelleft=True, labelbottom=True,
                       labelsize=label_tick_fontsize, pad=2)

        plt.setp(ax.get_yticklabels(), rotation=90, ha='center', va='center')

        yticklabels = ax.get_yticklabels()
        if yticklabels:
            ytickcoord = max([ytick.get_window_extent(renderer=plt.gcf().canvas.get_renderer()).width for ytick in yticklabels])
            ax.yaxis.set_tick_params(pad=ytickcoord - padding_label)
        else:
            print("\rNo y-tick labels generated.", end="", flush=True)

        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_xlabel('')
        ax.set_ylabel('')

        for spine in ax.spines.values():
            spine.set_linewidth(4)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, transparent=True, bbox_inches='tight')
    buf.seek(0)
    img = load_image_to_memory(buf)

    plot_data = {
        'fig': fig,
        'ax': ax,
        'peta': cfg.peta,
        'tipe': cfg.tipe,
        'skala': cfg.skala,
        'jenis': jenis,
        'year': year,
        'month': month,
        'dasarian': dasarian,
        'dasarian_ver': dasarian_ver,
        'month_ver': month_ver,
        'year_ver': year_ver,
        'value': value,
        'levels': levels,
        'province_data': province_counts,
        'kabupaten_data': kabupaten_counts,
        'image': img,
        'file_name': file_name,
        'nama_wilayah': nama_wilayah,
    }

    plt.close(fig)
    gc.collect()
    del clipped_data, idw
    return plot_data
