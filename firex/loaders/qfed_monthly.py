"""Aggregate QFED v2.6r1 daily files into monthly regional emission totals."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)


def load_qfed_monthly(
    base_dir: Path,
    species: Iterable[str],
    mask: xr.Dataset,
) -> xr.Dataset:
    """Walk ``base_dir/Y{yyyy}/M{mm}/`` summing daily files into monthly means.

    Y2016 is hard-skipped per CLAUDE.md (NCCS reprocess anomaly).
    """
    base = Path(base_dir)
    species = list(species)
    monthly_arrays: dict[str, list] = {sp: [] for sp in species}
    months: list[pd.Timestamp] = []

    for year_dir in sorted(p for p in base.glob("Y*") if p.is_dir()):
        year = int(year_dir.name[1:])
        if year == 2016:
            logger.info("Skipping Y2016 per CLAUDE.md note (NCCS reprocess anomaly)")
            continue
        for month_dir in sorted(p for p in year_dir.glob("M*") if p.is_dir()):
            month = int(month_dir.name[1:])
            month_start = pd.Timestamp(year=year, month=month, day=1)
            for sp in species:
                # Glob is collection-agnostic — real data uses .061., synthetic
                # fixtures use .005. Both formats are otherwise identical.
                files = sorted(month_dir.glob(f"qfed2.emis_{sp}.*.nc4"))
                if not files:
                    continue
                src = xr.open_mfdataset(files, combine="by_coords")["biomass"]
                weight = mask["weight"].interp(
                    lat=src["lat"], lon=src["lon"], method="nearest"
                ).fillna(0.0)
                regional = src.weighted(weight).mean(dim=("lat", "lon"))
                monthly_arrays[sp].append((month_start, float(regional.sum(dim="time").compute())))
            months.append(month_start)

    months = sorted(set(months))
    out = {}
    for sp in species:
        records = dict(monthly_arrays[sp])
        values = [records.get(m, float("nan")) for m in months]
        out[f"qfed_{sp}"] = xr.DataArray(values, dims=("time",), coords={"time": months})
    return xr.Dataset(out, coords={"time": months})
