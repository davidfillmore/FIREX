"""Load AERONET monthly site files and aggregate to a region.

Real `~/Data/AeroNet/AeroNet_{YYYYMM}.nc` files contain hourly site-level
observations (~744 timesteps for a 31-day month) for ~340 global sites along
the `x` dimension, with `siteid`, `latitude`, `longitude` coords. AOD is
reported at many wavelengths but **not at 550 nm** — closest channel is
`aod_500nm`, which we use as the regional smoke proxy and rename
`aeronet_aod_550` for downstream consistency. (The 50 nm offset is small
relative to the other uncertainties in the smoke-AOD attribution chain.)

Synthetic fixtures use a simplified (time, site) monthly layout; loader
detects format and routes accordingly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

from firex.regions import Region


def _load_real_aeronet_files(paths: list[Path], region: Region) -> xr.Dataset:
    """Open real AeroNet_{YYYYMM}.nc files, resample to monthly, filter to bbox."""
    parts = []
    for p in paths:
        ds = xr.open_dataset(p).load()
        # `siteid`, `latitude`, `longitude` are coords on dim `x`; pick aod_500nm.
        if "aod_500nm" not in ds.data_vars:
            continue
        sub = ds[["aod_500nm"]].copy()
        # AERONET uses -1.0 as the missing-value convention (no _FillValue attr).
        sub["aod_500nm"] = sub["aod_500nm"].where(sub["aod_500nm"] >= 0)
        # Squeeze stray length-1 dims (real files carry a `y=1` axis).
        sub = sub.squeeze(drop=True)
        # Keep site-level coords for filtering.
        for c in ("siteid", "latitude", "longitude"):
            if c in ds.coords:
                sub = sub.assign_coords({c: ds[c].squeeze(drop=True)})
        parts.append(sub)
    if not parts:
        raise KeyError("No AeroNet_*.nc files contained aod_500nm")
    src = xr.concat(parts, dim="time").sortby("time")

    # Across-month concat broadcasts site coords to (time, x) where some files
    # have fewer sites (padded with NaN). Collapse to 1D per site by taking the
    # first non-NaN value along time using numpy (avoids bottleneck dependency).
    def _per_site(coord_name):
        c = src[coord_name]
        if "time" not in c.dims:
            return c.values
        arr = c.values  # shape (time, x)
        if np.issubdtype(arr.dtype, np.floating):
            valid = ~np.isnan(arr)
        else:
            # siteid is string; treat empty/None as missing.
            valid = arr.astype(bool)
        first_valid_idx = valid.argmax(axis=0)  # 0 if no valid, else first valid row
        cols = np.arange(arr.shape[1])
        return arr[first_valid_idx, cols]

    site_lat = _per_site("latitude")
    site_lon = _per_site("longitude")
    siteid = _per_site("siteid")

    # Resample hourly → monthly mean.
    monthly = src["aod_500nm"].resample(time="MS").mean()
    out = xr.Dataset({"aeronet_aod_550": monthly}).assign_coords(
        site_lat=("x", site_lat),
        site_lon=("x", site_lon),
        site=("x", siteid.astype(str)),
    )
    out = out.swap_dims({"x": "site"}).reset_coords("x", drop=True)

    has_id = np.array([s not in ("nan", "", "None") for s in out["site"].values])
    inside = (
        (out["site_lat"] >= region.lat_min)
        & (out["site_lat"] <= region.lat_max)
        & (out["site_lon"] >= region.lon_min)
        & (out["site_lon"] <= region.lon_max)
    )
    out = out.where(inside & xr.DataArray(has_id, dims="site"), drop=True)
    out.attrs["source_channel"] = "aod_500nm"
    out.attrs["source_files"] = ";".join(str(p) for p in paths)
    return out


def _load_synth_aeronet(path: Path, region: Region) -> xr.Dataset:
    """Synthetic single-file fixture path."""
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


def load_aeronet(path_or_paths, region: Region) -> xr.Dataset:
    """Accepts either a single fixture file path or a directory/list of monthly files.

    - `Path` to a directory  → glob `AeroNet_*.nc` (real-data layout)
    - `Path` to a single .nc → synthetic-fixture layout (legacy)
    - iterable of paths      → treated as real-data files
    """
    if isinstance(path_or_paths, (str, Path)):
        p = Path(path_or_paths)
        if p.is_dir():
            files = sorted(p.glob("AeroNet_*.nc"))
            if not files:
                raise FileNotFoundError(f"No AeroNet_*.nc files in {p}")
            return _load_real_aeronet_files(files, region)
        return _load_synth_aeronet(p, region)
    paths = sorted(Path(x) for x in path_or_paths)
    return _load_real_aeronet_files(paths, region)
