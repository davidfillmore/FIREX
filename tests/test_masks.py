"""Tests for regional mask construction."""
import numpy as np
import xarray as xr

from firex.masks import build_mask, save_mask, load_mask
from firex.regions import REGIONS


def test_build_mask_shape_and_dtype():
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    assert isinstance(mask, xr.Dataset)
    assert mask["mask"].dtype == bool
    assert "weight" in mask
    assert mask.sizes["lat"] == 180
    assert mask.sizes["lon"] == 360


def test_build_mask_pnw_inside_outside():
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    inside = mask["mask"].sel(lat=46.5, lon=-120.5).item()
    outside = mask["mask"].sel(lat=46.5, lon=-90.5).item()
    assert inside is True or inside == 1
    assert outside is False or outside == 0


def test_weight_positive_inside_zero_outside():
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    weight = mask["weight"].values
    inside = mask["mask"].values
    assert (weight[inside] > 0).all()
    assert (weight[~inside] == 0).all()


def test_weight_uses_cosine_latitude():
    """Higher latitudes should have smaller area-weight."""
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    inside = mask["weight"].where(mask["mask"], drop=True)
    w_low = inside.sel(lat=42.5, lon=-120.5).item()
    w_high = inside.sel(lat=51.5, lon=-120.5).item()
    assert w_low > w_high  # cos(42°) > cos(51°)


def test_save_load_roundtrip(tmp_path):
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    path = tmp_path / "mask.nc"
    save_mask(mask, path)
    reloaded = load_mask(path)
    np.testing.assert_array_equal(mask["mask"].values, reloaded["mask"].values)
    np.testing.assert_allclose(mask["weight"].values, reloaded["weight"].values)
