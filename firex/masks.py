"""Build and persist regional masks on the 1° CERES EBAF grid."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from firex.regions import Region


def build_mask(region: Region, resolution_deg: float = 1.0) -> xr.Dataset:
    """Build a global 1° boolean mask + cosine-latitude area weight."""
    if resolution_deg <= 0:
        raise ValueError(f"resolution_deg must be positive, got {resolution_deg}")
    lat_centers = np.arange(-90 + resolution_deg / 2, 90, resolution_deg)
    lon_centers = np.arange(-180 + resolution_deg / 2, 180, resolution_deg)

    lat2d, lon2d = np.meshgrid(lat_centers, lon_centers, indexing="ij")
    inside = (
        (lat2d >= region.lat_min)
        & (lat2d <= region.lat_max)
        & (lon2d >= region.lon_min)
        & (lon2d <= region.lon_max)
    )

    cos_lat = np.cos(np.deg2rad(lat2d))
    weight = np.where(inside, cos_lat, 0.0)

    return xr.Dataset(
        {
            "mask": (("lat", "lon"), inside),
            "weight": (("lat", "lon"), weight),
        },
        coords={"lat": lat_centers, "lon": lon_centers},
        attrs={
            "region": region.name,
            "lon_min": region.lon_min,
            "lon_max": region.lon_max,
            "lat_min": region.lat_min,
            "lat_max": region.lat_max,
            "resolution_deg": resolution_deg,
        },
    )


def save_mask(mask: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    mask.to_netcdf(tmp)
    tmp.rename(path)


def load_mask(path: Path) -> xr.Dataset:
    return xr.open_dataset(path).load()
