"""Load VIIRS AERDB_M3 monthly L3 → regional means."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import xarray as xr

_AOD_VAR = "Aerosol_Optical_Thickness_550_Land_Ocean_Mean"


def load_viirs_monthly(
    paths: Iterable[Path],
    platform: Literal["snpp", "noaa20"],
    mask: xr.Dataset,
) -> xr.Dataset:
    if platform not in ("snpp", "noaa20"):
        raise ValueError(f"platform must be 'snpp' or 'noaa20', got {platform!r}")
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise FileNotFoundError("No VIIRS files supplied")
    src = xr.open_mfdataset(paths, combine="by_coords")
    if _AOD_VAR not in src.data_vars:
        raise KeyError(f"VIIRS file missing variable: {_AOD_VAR}")
    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    aod = src[_AOD_VAR].weighted(weight).mean(dim=("lat", "lon"))
    return xr.Dataset({f"viirs_{platform}_aod": aod}).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        platform=platform,
    )
