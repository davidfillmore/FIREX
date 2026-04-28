"""Tests for monthly anomaly construction and regression-design helpers."""
import numpy as np
import pandas as pd
import xarray as xr

from firex.anomaly import compute_anomaly, build_design_matrix


def _seasonal(amp: float, n_years: int = 5) -> xr.DataArray:
    months = pd.date_range("2010-01", periods=12 * n_years, freq="MS")
    seasonal = amp * np.sin(2 * np.pi * months.month.values / 12)
    return xr.DataArray(seasonal, dims="time", coords={"time": months})


def test_pure_seasonal_has_zero_anomaly():
    da = _seasonal(amp=2.0)
    anom = compute_anomaly(da)
    np.testing.assert_allclose(anom.values, 0.0, atol=1e-12)


def test_anomaly_recovers_injected_trend():
    da = _seasonal(amp=1.0)
    t = np.arange(da.size, dtype=float)
    da = da + 0.05 * t
    anom = compute_anomaly(da)
    # Injected trend should remain (climatology subtraction removes seasonal only).
    # Per-month climatology absorbs a small fraction of the linear trend at short
    # record lengths, so the recovered slope sits a few % below 0.05.
    slope = np.polyfit(t, anom.values, 1)[0]
    np.testing.assert_allclose(slope, 0.05, atol=5e-3)


def test_design_matrix_shape_and_columns():
    months = pd.date_range("2010-01", periods=24, freq="MS")
    times = xr.DataArray(months, dims="time")
    X = build_design_matrix(times)
    # 11 month dummies + linear trend + intercept = 13 columns
    assert X.shape == (24, 13)
    assert "intercept" in X.columns
    assert "trend" in X.columns
    # Reference month dropped (should leave 11 month-FE columns)
    fe_cols = [c for c in X.columns if c.startswith("month_")]
    assert len(fe_cols) == 11
