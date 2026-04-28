"""Climatology subtraction and regression design-matrix construction."""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr


def compute_anomaly(da: xr.DataArray) -> xr.DataArray:
    """Subtract month-of-year climatology computed over the full record."""
    if "time" not in da.dims:
        raise ValueError("DataArray must have a `time` dimension")
    climatology = da.groupby("time.month").mean()
    return da.groupby("time.month") - climatology


def build_design_matrix(times: xr.DataArray) -> pd.DataFrame:
    """Construct intercept + linear trend + month-of-year fixed effects."""
    if times.dtype.kind != "M":
        raise ValueError(f"`times` must be datetime, got {times.dtype}")
    n = times.size
    df = pd.DataFrame(index=range(n))
    df["intercept"] = 1.0
    df["trend"] = np.arange(n, dtype=float)
    months = pd.DatetimeIndex(times.values).month
    # Reference month = 1 (January). Add month_2..month_12 dummies.
    for m in range(2, 13):
        df[f"month_{m}"] = (months == m).astype(float)
    return df
