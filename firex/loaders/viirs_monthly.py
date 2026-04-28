"""Load VIIRS AERDB_M3 monthly L3 → regional means.

Real VIIRS AERDB_M3 granules are NetCDF4, one file per month, with no `time`
dimension and gridded on `Latitude_1D`×`Longitude_1D` axes (and 2D
`Latitude`/`Longitude` arrays as broadcast coords). The calendar month is
encoded in the filename (`AERDB_M3_VIIRS_{plat}.A{YYYY}{DOY}.002...nc`).
Synthetic fixtures use the simpler (time, lat, lon) layout for unit tests.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import pandas as pd
import xarray as xr

_AOD_VAR = "Aerosol_Optical_Thickness_550_Land_Ocean_Mean"


def _parse_viirs_time(name: str) -> pd.Timestamp:
    """`AERDB_M3_VIIRS_SNPP.A2020001.002.2023089190501.nc` → 2020-01-01."""
    parts = name.split(".")
    yyyydoy = parts[1].lstrip("A")
    yyyy, doy = int(yyyydoy[:4]), int(yyyydoy[4:])
    return pd.Timestamp(year=yyyy, month=1, day=1) + pd.Timedelta(days=doy - 1)


def _open_viirs(path: Path) -> xr.Dataset:
    src = xr.open_dataset(path).load()
    if _AOD_VAR not in src.data_vars:
        raise KeyError(f"VIIRS file missing variable: {_AOD_VAR}")
    if "Latitude_1D" in src.dims:
        # Real-data layout: rename dims and replace 2D Latitude/Longitude with 1D.
        lat_1d = src["Latitude"].isel(Longitude_1D=0).values
        lon_1d = src["Longitude"].isel(Latitude_1D=0).values
        src = src.rename({"Latitude_1D": "lat", "Longitude_1D": "lon"})
        # Drop the 2D coords; assign 1D ones.
        for c in ("Latitude", "Longitude"):
            if c in src.coords:
                src = src.reset_coords(c, drop=True)
        src = src.assign_coords(lat=lat_1d, lon=lon_1d)
    if "time" not in src.dims:
        t = _parse_viirs_time(path.name)
        src = src.expand_dims(time=[t])
    return src[[_AOD_VAR, *(c for c in () if False)]]  # carry only AOD var


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

    parts = [_open_viirs(p) for p in paths]
    src = xr.concat(parts, dim="time").sortby("time")

    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    aod = src[_AOD_VAR].weighted(weight).mean(dim=("lat", "lon"))
    return xr.Dataset({f"viirs_{platform}_aod": aod}).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        platform=platform,
    )
