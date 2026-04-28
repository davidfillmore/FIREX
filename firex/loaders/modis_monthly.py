"""Load MODIS C6.1 monthly L3 (MOD08_M3 / MYD08_M3) → regional means."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import xarray as xr

_AOD_VAR = "Aerosol_Optical_Depth_Land_Ocean_Mean_Mean"


def load_modis_monthly(
    paths: Iterable[Path],
    platform: Literal["terra", "aqua"],
    mask: xr.Dataset,
) -> xr.Dataset:
    if platform not in ("terra", "aqua"):
        raise ValueError(f"platform must be 'terra' or 'aqua', got {platform!r}")
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise FileNotFoundError("No MODIS files supplied")
    src = xr.open_mfdataset(paths, combine="by_coords")
    if _AOD_VAR not in src.data_vars:
        raise KeyError(f"MODIS file missing variable: {_AOD_VAR}")
    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    aod = src[_AOD_VAR].weighted(weight).mean(dim=("lat", "lon"))
    return xr.Dataset({f"modis_{platform}_aod": aod}).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        platform=platform,
    )
