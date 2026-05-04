"""Nearest-gridcell sampling of gridded fields at AERONET site locations.

Loaders use this to emit a per-site companion (`<var>_site` with dims
`(time, site)`) alongside the existing region-mean (`(time,)`) variable,
so plots can compare model/satellite AOD against AERONET at each site.
"""
from __future__ import annotations

import numpy as np
import xarray as xr


def sample_at_sites(
    da: xr.DataArray,
    sites: xr.Dataset,
    lat_dim: str = "lat",
    lon_dim: str = "lon",
) -> xr.DataArray:
    """Return *da* sampled at each (site_lat, site_lon) via nearest-neighbor.

    Parameters
    ----------
    da
        Gridded DataArray with a `time` dim plus the named spatial dims.
    sites
        Dataset with a `site` dim and `site_lat`, `site_lon` coords.
    lat_dim, lon_dim
        Names of the spatial dims on *da*.

    Returns
    -------
    DataArray
        Dims `(time, site)`, with `site_lat` / `site_lon` carried through.
    """
    site_lats = np.asarray(sites["site_lat"].values, dtype=float)
    site_lons = np.asarray(sites["site_lon"].values, dtype=float)
    cols = []
    for lat, lon in zip(site_lats, site_lons):
        cols.append(da.sel({lat_dim: lat, lon_dim: lon}, method="nearest"))
    out = xr.concat(cols, dim="site")
    out = out.assign_coords(
        site=("site", sites["site"].values),
        site_lat=("site", site_lats),
        site_lon=("site", site_lons),
    )
    # Drop the lat/lon scalar coords inherited from .sel (they vary per site).
    for c in (lat_dim, lon_dim):
        if c in out.coords:
            out = out.reset_coords(c, drop=True)
    return out
