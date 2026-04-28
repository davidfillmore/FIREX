"""Load AERONET monthly site file and filter to a region."""
from __future__ import annotations

from pathlib import Path

import xarray as xr

from firex.regions import Region


def load_aeronet(path: Path, region: Region) -> xr.Dataset:
    src = xr.open_dataset(Path(path)).load()
    if "site_lat" not in src or "site_lon" not in src:
        raise KeyError("AERONET file must contain site_lat and site_lon coordinates")
    inside = (
        (src["site_lat"] >= region.lat_min)
        & (src["site_lat"] <= region.lat_max)
        & (src["site_lon"] >= region.lon_min)
        & (src["site_lon"] <= region.lon_max)
    )
    return src.where(inside, drop=True).rename({"AOD_550nm": "aeronet_aod_550"})
