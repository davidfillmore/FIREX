"""Compute smoke-fraction and smoke-AOD per observed source.

MERRA-2 aer_Nx exposes only species totals (BCEXTTAU, OCEXTTAU, ...) — no
biomass-burning split. We approximate the smoke contribution to BC and OC
by subtracting a per-month-of-year background climatology (the 10th
percentile across the record), which captures non-fire anthropogenic +
biogenic levels in each season:

    smoke_BC[t] = max(0, BCEXTTAU[t] − BCEXTTAU_bg[month_of(t)])
    smoke_OC[t] = max(0, OCEXTTAU[t] − OCEXTTAU_bg[month_of(t)])
    smoke_AOD_merra2[t] = smoke_BC[t] + smoke_OC[t]
    smoke_fraction[t] = smoke_AOD_merra2[t] / TOTEXTTAU[t]

The 10th-percentile baseline assumes that for any calendar month the record
contains at least a few clean (no-fire) realizations. With ~26 years of data
this puts the baseline at roughly the 3rd-lowest year per month — robust to
elevated fire years while staying dimensionally honest (AOD minus AOD).
"""
from __future__ import annotations

import logging

import xarray as xr

logger = logging.getLogger(__name__)

_OBS_TO_SLUG = {
    "modis_terra_aod": "terra",
    "modis_aqua_aod": "aqua",
    "viirs_snpp_aod": "snpp",
    "viirs_noaa20_aod": "noaa20",
}

_BASELINE_PERCENTILE = 0.10


def _per_month_baseline(da: xr.DataArray, q: float = _BASELINE_PERCENTILE) -> xr.DataArray:
    """Per-month-of-year low-percentile baseline (broadcast back along time).

    Returns a DataArray on the same time axis as *da*, with each timestep
    replaced by its calendar-month baseline value.
    """
    by_month = da.groupby("time.month").quantile(q, dim="time")
    return by_month.sel(month=da["time.month"]).drop_vars(("month", "quantile"))


def compute_smoke_attribution(
    *,
    merra2: xr.Dataset,
    obs: dict[str, xr.DataArray],
    qfed: xr.Dataset,
) -> xr.Dataset:
    """Smoke fraction (MERRA-2-based) and smoke AOD per observation source.

    Parameters
    ----------
    merra2
        Region-averaged MERRA-2 aer monthly dataset; required vars are
        ``merra2_aer_BCEXTTAU``, ``merra2_aer_OCEXTTAU``, ``merra2_aer_TOTEXTTAU``.
    obs
        Mapping of observation-AOD variables (`modis_terra_aod`,
        `modis_aqua_aod`, `viirs_snpp_aod`, `viirs_noaa20_aod`) to their
        DataArrays.
    qfed
        Region-averaged QFED dataset (carried for provenance only — not
        used in the baseline-subtraction method).
    """
    bc = merra2["merra2_aer_BCEXTTAU"]
    oc = merra2["merra2_aer_OCEXTTAU"]
    total = merra2["merra2_aer_TOTEXTTAU"]

    bc_bg = _per_month_baseline(bc)
    oc_bg = _per_month_baseline(oc)
    smoke_bc = (bc - bc_bg).clip(min=0.0)
    smoke_oc = (oc - oc_bg).clip(min=0.0)
    smoke_aod_merra2 = smoke_bc + smoke_oc
    smoke_fraction = (smoke_aod_merra2 / total).clip(0.0, 1.0)

    out_vars: dict[str, xr.DataArray] = {
        "smoke_fraction": smoke_fraction,
        "smoke_aod_merra2": smoke_aod_merra2,
        "merra2_bc_baseline": bc_bg,
        "merra2_oc_baseline": oc_bg,
    }
    for obs_name, obs_da in obs.items():
        if obs_name not in _OBS_TO_SLUG:
            raise KeyError(f"Unknown observation source: {obs_name}")
        slug = _OBS_TO_SLUG[obs_name]
        out_vars[f"smoke_aod_{slug}"] = smoke_fraction * obs_da

    ds = xr.Dataset(out_vars)
    ds.attrs["oc_split_method"] = f"baseline_subtraction_q{_BASELINE_PERCENTILE:.2f}"
    return ds
