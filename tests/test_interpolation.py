"""Tests for interpolation method selection and the IDW backend.

Run with:  pytest tests/
These are pure-numeric tests: no static files, no network, no Gemini/GitHub.
"""

import numpy as np
import pytest

from Main.config import INTERP
from Main.map_creation import (
    _interpolate_idw,
    _interpolate_regular_grid,
    _is_regular_lattice,
    _resolve_interp_method,
)


def make_fine(x_grid, y_grid):
    """Build the minimal fine-grid dict the interpolators consume."""
    gl, go = np.meshgrid(y_grid, x_grid, indexing='ij')
    return {
        'x_grid': x_grid, 'y_grid': y_grid,
        'query': np.column_stack((gl.ravel(), go.ravel())),
        'shape': gl.shape,
    }


@pytest.fixture
def gridded():
    lons = np.round(np.arange(130, 134, 0.25), 2)
    lats = np.round(np.arange(-4, -1, 0.25), 2)
    LO, LA = np.meshgrid(lons, lats, indexing='ij')
    return LO.ravel(), LA.ravel()


@pytest.fixture
def fine():
    return make_fine(np.linspace(130, 134, 60), np.linspace(-4, -1, 45))


@pytest.fixture
def restore_interp():
    """INTERP is module-level mutable state; restore it after each test."""
    saved = dict(INTERP)
    yield
    INTERP.clear()
    INTERP.update(saved)


# --------------------------------------------------------------------------
# lattice detection
# --------------------------------------------------------------------------

def test_uniform_lattice_is_regular(gridded):
    lon, lat = gridded
    assert _is_regular_lattice(lon)
    assert _is_regular_lattice(lat)


def test_jittered_points_are_irregular(gridded):
    lon, lat = gridded
    rng = np.random.default_rng(0)
    assert not (
        _is_regular_lattice(lon + rng.uniform(-0.07, 0.07, lon.size))
        and _is_regular_lattice(lat + rng.uniform(-0.07, 0.07, lat.size))
    )


def test_lattice_with_ocean_holes_still_regular(gridded):
    """Gridded model output legitimately has gaps over ocean."""
    lon, lat = gridded
    keep = np.random.default_rng(1).random(lon.size) > 0.3
    assert _is_regular_lattice(lon[keep])
    assert _is_regular_lattice(lat[keep])


# --------------------------------------------------------------------------
# method resolution
# --------------------------------------------------------------------------

def test_gridded_resolves_to_linear(gridded, restore_interp):
    lon, lat = gridded
    assert _resolve_interp_method(lon, lat, False)[0] == 'linear'


def test_scattered_resolves_to_idw(gridded, restore_interp):
    lon, lat = gridded
    rng = np.random.default_rng(2)
    lon = lon + rng.uniform(-0.07, 0.07, lon.size)
    lat = lat + rng.uniform(-0.07, 0.07, lat.size)
    assert _resolve_interp_method(lon, lat, False)[0] == 'idw'


def test_discrete_always_forces_nearest(gridded, restore_interp):
    """get_verif() passes 0/1; smoothing them would invent categories."""
    lon, lat = gridded
    assert _resolve_interp_method(lon, lat, True)[0] == 'nearest'
    INTERP['method'] = 'idw'
    assert _resolve_interp_method(lon, lat, True)[0] == 'nearest'


def test_explicit_override_beats_autodetect(gridded, restore_interp):
    lon, lat = gridded
    INTERP['method'] = 'idw'
    assert _resolve_interp_method(lon, lat, False)[0] == 'idw'


# --------------------------------------------------------------------------
# IDW numerics
# --------------------------------------------------------------------------

def test_idw_of_constant_field_is_that_constant(gridded, fine):
    lon, lat = gridded
    out = _interpolate_idw(lon, lat, np.full(lon.size, 42.0, np.float32), fine)
    assert np.allclose(out, 42.0, atol=1e-4)


def test_idw_at_station_returns_station_value():
    lon = np.array([131.0, 132.0, 133.0])
    lat = np.array([-3.0, -2.0, -2.5])
    val = np.array([10.0, 50.0, 90.0], dtype=np.float32)
    out = _interpolate_idw(lon, lat, val, make_fine(np.array([131.0]), np.array([-3.0])))
    assert out[0, 0] == pytest.approx(10.0, abs=1e-3)


def test_idw_ignores_nan_stations(gridded, fine):
    """One NaN neighbour must not poison every cell that references it."""
    lon, lat = gridded
    vals = np.full(lon.size, 7.0, dtype=np.float32)
    vals[np.random.default_rng(3).integers(0, vals.size, 20)] = np.nan
    out = _interpolate_idw(lon, lat, vals, fine)
    assert np.isfinite(out).all()
    assert np.allclose(out, 7.0, atol=1e-4)


def test_idw_all_nan_raises(gridded, fine):
    lon, lat = gridded
    with pytest.raises(ValueError):
        _interpolate_idw(lon, lat, np.full(lon.size, np.nan, np.float32), fine)


def test_idw_output_stays_within_data_range(gridded, fine):
    """A weighted mean cannot exceed the range of its inputs."""
    lon, lat = gridded
    v = np.random.default_rng(4).uniform(0, 500, lon.size).astype(np.float32)
    out = _interpolate_idw(lon, lat, v, fine)
    assert out.min() >= v.min() - 1e-3
    assert out.max() <= v.max() + 1e-3


# --------------------------------------------------------------------------
# regression: gridded input must keep producing what it produced before
# --------------------------------------------------------------------------

@pytest.mark.parametrize("discrete", [False, True])
def test_gridded_path_unchanged_from_legacy_behaviour(gridded, fine, discrete, restore_interp):
    """Legacy behaviour was: 'nearest' if discrete else 'linear'.

    Auto-detect must reproduce that for gridded input, so existing production
    maps are untouched by the IDW work.
    """
    lon, lat = gridded
    rng = np.random.default_rng(5)
    v = (rng.integers(0, 2, lon.size) if discrete else rng.uniform(0, 500, lon.size)).astype(np.float32)

    legacy_method = 'nearest' if discrete else 'linear'
    resolved, _ = _resolve_interp_method(lon, lat, discrete)
    assert resolved == legacy_method

    a = _interpolate_regular_grid(lon, lat, v, fine, method=legacy_method)
    b = _interpolate_regular_grid(lon, lat, v, fine, method=resolved)
    assert np.array_equal(a, b, equal_nan=True)
