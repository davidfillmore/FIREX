"""Generate small synthetic NetCDF fixtures for loader tests.

Run this once to populate `tests/fixtures/*.nc`. Re-run if schemas change.

    python tests/fixtures/build_fixtures.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).parent
RNG = np.random.default_rng(seed=20260428)


def _months(n: int = 24, start: str = "2020-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="MS")


def _grid(lat_min: float = 40.0, lat_max: float = 50.0,
          lon_min: float = -130.0, lon_max: float = -110.0,
          step: float = 1.0):
    lat = np.arange(lat_min + step / 2, lat_max, step)
    lon = np.arange(lon_min + step / 2, lon_max, step)
    return lat, lon


def build_ceres_ebaf() -> None:
    """CERES EBAF Ed4.2.1 — TOA + SFC SW/LW/Net, both clear-sky and all-sky."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "toa_sw_all_mon": (("time", "lat", "lon"), 100 + 5 * RNG.standard_normal(shape)),
            "toa_sw_clr_t_mon": (("time", "lat", "lon"), 95 + 4 * RNG.standard_normal(shape)),
            "toa_lw_all_mon": (("time", "lat", "lon"), 230 + 5 * RNG.standard_normal(shape)),
            "toa_lw_clr_t_mon": (("time", "lat", "lon"), 250 + 4 * RNG.standard_normal(shape)),
            "toa_net_all_mon": (("time", "lat", "lon"), 20 + 3 * RNG.standard_normal(shape)),
            "toa_net_clr_t_mon": (("time", "lat", "lon"), 18 + 2 * RNG.standard_normal(shape)),
            "sfc_sw_down_all_mon": (("time", "lat", "lon"), 180 + 10 * RNG.standard_normal(shape)),
            "sfc_sw_down_clr_t_mon": (("time", "lat", "lon"), 220 + 8 * RNG.standard_normal(shape)),
            "sfc_lw_down_all_mon": (("time", "lat", "lon"), 320 + 5 * RNG.standard_normal(shape)),
            "sfc_lw_down_clr_t_mon": (("time", "lat", "lon"), 310 + 5 * RNG.standard_normal(shape)),
            "sfc_net_tot_all_mon": (("time", "lat", "lon"), 90 + 5 * RNG.standard_normal(shape)),
            "sfc_net_tot_clr_t_mon": (("time", "lat", "lon"), 110 + 5 * RNG.standard_normal(shape)),
            "cldarea_total_daynight_mon": (("time", "lat", "lon"), 0.5 + 0.1 * RNG.standard_normal(shape)),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / "ceres_ebaf_synth.nc")


def build_modis(short: str) -> None:
    """MODIS MOD08_M3 / MYD08_M3 — monthly L3 AOD."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "Aerosol_Optical_Depth_Land_Ocean_Mean_Mean": (
                ("time", "lat", "lon"),
                0.15 + 0.05 * RNG.standard_normal(shape),
            ),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / f"{short}_synth.nc")


def build_viirs(short: str, start: str) -> None:
    """VIIRS AERDB monthly L3."""
    months = _months(start=start)
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "Aerosol_Optical_Thickness_550_Land_Ocean_Mean": (
                ("time", "lat", "lon"),
                0.13 + 0.04 * RNG.standard_normal(shape),
            ),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / f"{short}_synth.nc")


def build_merra2_aer() -> None:
    """MERRA-2 monthly aer_Nx species AOD (no OCEXTTAU_bb -> exercises fallback)."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "TOTEXTTAU": (("time", "lat", "lon"), 0.20 + 0.05 * RNG.standard_normal(shape)),
            "BCEXTTAU": (("time", "lat", "lon"), 0.02 + 0.005 * RNG.standard_normal(shape)),
            "OCEXTTAU": (("time", "lat", "lon"), 0.06 + 0.01 * RNG.standard_normal(shape)),
            "SUEXTTAU": (("time", "lat", "lon"), 0.05 + 0.01 * RNG.standard_normal(shape)),
            "DUEXTTAU": (("time", "lat", "lon"), 0.04 + 0.01 * RNG.standard_normal(shape)),
            "SSEXTTAU": (("time", "lat", "lon"), 0.03 + 0.01 * RNG.standard_normal(shape)),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / "merra2_aer_synth.nc")


def build_merra2_slv() -> None:
    """MERRA-2 monthly slv_Nx covariates."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "T2M": (("time", "lat", "lon"), 285 + 5 * RNG.standard_normal(shape)),
            "TQV": (("time", "lat", "lon"), 18 + 4 * RNG.standard_normal(shape)),
            "PBLH": (("time", "lat", "lon"), 1500 + 200 * RNG.standard_normal(shape)),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / "merra2_slv_synth.nc")


def build_qfed() -> None:
    """A handful of QFED daily files in the Y{YYYY}/M{MM}/ layout."""
    base = HERE / "qfed_synth"
    days = pd.date_range("2020-07-01", "2020-07-03", freq="D")
    lat, lon = _grid(step=0.5)
    for sp in ("oc", "bc", "co"):
        for d in days:
            d_dir = base / f"Y{d.year}" / f"M{d.month:02d}"
            d_dir.mkdir(parents=True, exist_ok=True)
            arr = 1e-10 + 1e-11 * RNG.standard_normal((1, len(lat), len(lon)))
            ds = xr.Dataset(
                {"biomass": (("time", "lat", "lon"), arr)},
                coords={"time": [d], "lat": lat, "lon": lon},
            )
            ds.to_netcdf(d_dir / f"qfed2.emis_{sp}.005.{d:%Y%m%d}.nc4")


def build_aeronet() -> None:
    """AERONET monthly site file (~3 PNW sites)."""
    months = _months()
    sites = ["Trinidad_Head", "Railroad_Valley", "Bondville"]
    # Trinidad_Head fudged 2° north (real 41.05°N is just south of PNW
    # lat_min=42°) so the fixture has at least one site inside the bbox.
    site_lat = np.array([43.0, 38.5, 40.05])
    site_lon = np.array([-124.15, -115.7, -88.4])
    ds = xr.Dataset(
        {
            "AOD_550nm": (
                ("time", "site"),
                0.10 + 0.04 * RNG.standard_normal((len(months), len(sites))),
            ),
            "site_lat": (("site",), site_lat),
            "site_lon": (("site",), site_lon),
        },
        coords={"time": months, "site": sites},
    )
    ds.to_netcdf(HERE / "aeronet_synth.nc")


if __name__ == "__main__":
    build_ceres_ebaf()
    build_modis("modis_terra")
    build_modis("modis_aqua")
    build_viirs("viirs_snpp", start="2020-01")
    build_viirs("viirs_noaa20", start="2020-01")
    build_merra2_aer()
    build_merra2_slv()
    build_qfed()
    build_aeronet()
    print("Synthetic fixtures written to", HERE)
