"""Compute smoke-fraction and smoke-AOD per observed source."""
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


def _djf_baseline_oc(merra2: xr.Dataset) -> float:
    """Per-record DJF mean of OCEXTTAU as anthropogenic+biogenic baseline."""
    oc = merra2["merra2_aer_OCEXTTAU"]
    djf = oc.where(oc["time"].dt.month.isin([12, 1, 2]), drop=True)
    if djf.size == 0:
        raise ValueError("No DJF months available for fallback baseline")
    return float(djf.mean().item())


def compute_smoke_attribution(
    *,
    merra2: xr.Dataset,
    obs: dict[str, xr.DataArray],
    qfed: xr.Dataset,
) -> xr.Dataset:
    """Smoke fraction (MERRA-2-based) and smoke AOD per observation source."""
    bc = merra2["merra2_aer_BCEXTTAU"]
    oc = merra2["merra2_aer_OCEXTTAU"]
    total = merra2["merra2_aer_TOTEXTTAU"]

    if "merra2_aer_OCEXTTAU_bb" in merra2:
        oc_bb = merra2["merra2_aer_OCEXTTAU_bb"]
        oc_split_method = "explicit"
    else:
        baseline = _djf_baseline_oc(merra2)
        share = qfed["qfed_oc"] / (qfed["qfed_oc"] + baseline)
        oc_bb = oc * share.clip(0.0, 1.0)
        oc_split_method = "fallback"
        logger.warning(
            "MERRA-2 lacks OCEXTTAU_bb; using QFED-ratio fallback with DJF baseline %.3e",
            baseline,
        )

    smoke_fraction = ((bc + oc_bb) / total).clip(0.0, 1.0)

    out_vars: dict[str, xr.DataArray] = {"smoke_fraction": smoke_fraction}
    for obs_name, obs_da in obs.items():
        if obs_name not in _OBS_TO_SLUG:
            raise KeyError(f"Unknown observation source: {obs_name}")
        slug = _OBS_TO_SLUG[obs_name]
        out_vars[f"smoke_aod_{slug}"] = smoke_fraction * obs_da

    ds = xr.Dataset(out_vars)
    ds.attrs["oc_split_method"] = oc_split_method
    return ds
