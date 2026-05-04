"""Load MERRA-2 monthly tavgM_2d_{aer,slv,flx,lnd}_Nx → regional means."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import xarray as xr

_COLLECTION_VARS: dict[str, list[str]] = {
    "aer": ["TOTEXTTAU", "BCEXTTAU", "OCEXTTAU", "SUEXTTAU", "DUEXTTAU", "SSEXTTAU"],
    "slv": ["T2M", "TQV", "PBLH"],
    "flx": ["HFLUX", "EFLUX", "USTAR"],
    "lnd": ["GWETROOT", "RUNOFF"],
}


def load_merra2_monthly(
    paths: Iterable[Path],
    collection: str,
    mask: xr.Dataset,
    sites: xr.Dataset | None = None,
) -> xr.Dataset:
    if collection not in _COLLECTION_VARS:
        raise ValueError(
            f"Unknown collection {collection!r}; expected one of {list(_COLLECTION_VARS)}"
        )
    wanted = _COLLECTION_VARS[collection]
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise FileNotFoundError("No MERRA-2 files supplied")
    src = xr.open_mfdataset(paths, combine="by_coords")
    missing = [v for v in wanted if v not in src.data_vars]
    if missing:
        raise KeyError(f"MERRA-2 {collection} file missing variables: {missing}")
    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    out = {}
    have_sites = sites is not None and sites.sizes.get("site", 0) > 0
    if have_sites:
        from firex.loaders.site_sample import sample_at_sites
    for v in wanted:
        out[f"merra2_{collection}_{v}"] = src[v].weighted(weight).mean(dim=("lat", "lon"))
        if have_sites:
            out[f"merra2_{collection}_{v}_site"] = sample_at_sites(src[v], sites)
    return xr.Dataset(out).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        collection=collection,
    )
