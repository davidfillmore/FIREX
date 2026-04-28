"""Load CERES EBAF Ed4.2.1 monthly file → masked, area-weighted regional means."""
from __future__ import annotations

from pathlib import Path

import xarray as xr


_VAR_MAP: dict[str, str] = {
    "toa_sw_all_mon": "ceres_toa_sw_all",
    "toa_sw_clr_t_mon": "ceres_toa_sw_clr",
    "toa_lw_all_mon": "ceres_toa_lw_all",
    "toa_lw_clr_t_mon": "ceres_toa_lw_clr",
    "toa_net_all_mon": "ceres_toa_net_all",
    "toa_net_clr_t_mon": "ceres_toa_net_clr",
    "sfc_sw_down_all_mon": "ceres_sfc_sw_down_all",
    "sfc_sw_down_clr_t_mon": "ceres_sfc_sw_down_clr",
    "sfc_lw_down_all_mon": "ceres_sfc_lw_down_all",
    "sfc_lw_down_clr_t_mon": "ceres_sfc_lw_down_clr",
    "sfc_net_tot_all_mon": "ceres_sfc_net_all",
    "sfc_net_tot_clr_t_mon": "ceres_sfc_net_clr",
    "cldarea_total_daynight_mon": "ceres_cloud_fraction",
}


def load_ceres_ebaf(path: Path, mask: xr.Dataset) -> xr.Dataset:
    """Open CERES EBAF, regrid mask if needed, area-weighted mean per month."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CERES EBAF file not found: {path}")

    src = xr.open_dataset(path)
    missing = [k for k in _VAR_MAP if k not in src.data_vars]
    if missing:
        raise KeyError(f"CERES EBAF file missing variables: {missing}")

    # CERES EBAF ships with lon ∈ [0, 360); the mask is on [-180, 180].
    # Wrap to the same convention so the nearest-neighbor interp can match.
    if float(src["lon"].max()) > 180:
        src = src.assign_coords(lon=(((src["lon"] + 180) % 360) - 180)).sortby("lon")

    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)

    out = {}
    for src_name, out_name in _VAR_MAP.items():
        weighted = src[src_name].weighted(weight)
        out[out_name] = weighted.mean(dim=("lat", "lon"))

    ds = xr.Dataset(out)
    ds = ds.assign_attrs(
        source_file=str(path),
        region=mask.attrs.get("region", "unknown"),
    )
    return ds
