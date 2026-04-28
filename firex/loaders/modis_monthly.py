"""Load MODIS C6.1 monthly L3 (MOD08_M3 / MYD08_M3) → regional means.

Real MODIS L3 monthly granules ship as HDF4 (.hdf), one file per month, with
no `time` dimension in the SDS — the calendar month is encoded in the
filename (`MOD08_M3.A{YYYY}{DOY}.061...hdf`). Synthetic test fixtures use
NetCDF (.nc) with the same single-month + filename-encoded-time convention.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd
import xarray as xr

_AOD_VAR = "Aerosol_Optical_Depth_Land_Ocean_Mean_Mean"


def _parse_modis_time(name: str) -> pd.Timestamp:
    """`MOD08_M3.A2020001.061.2020032093438.hdf` → 2020-01-01."""
    yyyydoy = name.split(".")[1].lstrip("A")
    yyyy, doy = int(yyyydoy[:4]), int(yyyydoy[4:])
    return pd.Timestamp(year=yyyy, month=1, day=1) + pd.Timedelta(days=doy - 1)


def _open_modis_hdf4(path: Path) -> xr.Dataset:
    from pyhdf.SD import SD, SDC

    sd = SD(str(path), SDC.READ)
    try:
        sds = sd.select(_AOD_VAR)
        attrs = sds.attributes()
        raw = sds.get()
        fill = attrs.get("_FillValue", -9999)
        sf = attrs.get("scale_factor", 1.0)
        off = attrs.get("add_offset", 0.0)
        aod = np.where(raw == fill, np.nan, raw * sf + off).astype(np.float32)
        lat = sd.select("YDim").get().astype(np.float64)
        lon = sd.select("XDim").get().astype(np.float64)
    finally:
        sd.end()

    # MODIS HDF4 ships YDim descending (90 → -90); flip to ascending.
    if lat[0] > lat[-1]:
        lat = lat[::-1].copy()
        aod = aod[::-1, :].copy()

    t = _parse_modis_time(path.name)
    return xr.Dataset(
        {_AOD_VAR: (("time", "lat", "lon"), aod[None, :, :])},
        coords={"time": [t], "lat": lat, "lon": lon},
    )


def _open_modis_netcdf(path: Path) -> xr.Dataset:
    """Open a single-month synthetic MODIS NetCDF and add a `time` axis from the filename."""
    src = xr.open_dataset(path).load()
    if _AOD_VAR not in src.data_vars:
        raise KeyError(f"MODIS file missing variable: {_AOD_VAR}")
    if "time" in src.dims:
        return src  # multi-month synthetic fixture (legacy)
    t = _parse_modis_time(path.name)
    return src.expand_dims(time=[t])


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

    parts = []
    for p in paths:
        if p.suffix == ".hdf":
            parts.append(_open_modis_hdf4(p))
        else:
            parts.append(_open_modis_netcdf(p))
    src = xr.concat(parts, dim="time").sortby("time")

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
