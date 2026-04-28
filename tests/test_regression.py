"""Tests for the OLS regression helper."""
import numpy as np
import pandas as pd
import xarray as xr

from firex.regression import fit_radiative_efficiency


def _make_synth(beta: float = -30.0, n: int = 240, seed: int = 0) -> xr.Dataset:
    rng = np.random.default_rng(seed)
    times = pd.date_range("2000-01", periods=n, freq="MS")
    smoke_aod = np.abs(0.10 + 0.05 * rng.standard_normal(n))
    cloud = 0.5 + 0.05 * rng.standard_normal(n)
    tqv = 18 + 4 * rng.standard_normal(n)
    seasonal = 5 * np.sin(2 * np.pi * times.month.values / 12)
    noise = 0.5 * rng.standard_normal(n)
    F = 100 + beta * smoke_aod + 2.0 * cloud + 0.1 * tqv + seasonal + noise
    return xr.Dataset(
        {
            "F_TOA_SW_clr": ("time", F),
            "smoke_aod": ("time", smoke_aod),
            "cloud_fraction": ("time", cloud),
            "tqv": ("time", tqv),
        },
        coords={"time": times},
    )


def test_recovers_known_beta():
    ds = _make_synth(beta=-30.0)
    result = fit_radiative_efficiency(
        ds, response="F_TOA_SW_clr",
        predictors=["smoke_aod", "cloud_fraction", "tqv"],
    )
    beta_hat = result.params["smoke_aod"]
    se = result.bse["smoke_aod"]
    assert abs(beta_hat - (-30.0)) < 2 * se


def test_hac_se_nonzero():
    ds = _make_synth()
    result = fit_radiative_efficiency(
        ds, response="F_TOA_SW_clr",
        predictors=["smoke_aod", "cloud_fraction", "tqv"],
    )
    assert result.bse["smoke_aod"] > 0


def test_summary_table_has_expected_columns():
    ds = _make_synth()
    result = fit_radiative_efficiency(
        ds, response="F_TOA_SW_clr",
        predictors=["smoke_aod", "cloud_fraction", "tqv"],
    )
    table = result.summary_frame()
    for col in ("coef", "std_err", "t_stat", "p_value"):
        assert col in table.columns
    assert "smoke_aod" in table.index
