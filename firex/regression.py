"""OLS with HAC standard errors plus month-FE + linear trend."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm
import xarray as xr

from firex.anomaly import build_design_matrix


@dataclass
class RegressionResult:
    params: pd.Series
    bse: pd.Series
    tvalues: pd.Series
    pvalues: pd.Series
    rsquared: float
    nobs: int

    def summary_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "coef": self.params,
                "std_err": self.bse,
                "t_stat": self.tvalues,
                "p_value": self.pvalues,
            }
        )


def fit_radiative_efficiency(
    ds: xr.Dataset,
    response: str,
    predictors: list[str],
    hac_lags: int = 6,
) -> RegressionResult:
    """Fit `response = α + Σ β_i · predictors_i + month_FE + trend + ε` via OLS+HAC."""
    if response not in ds:
        raise KeyError(f"Response variable {response!r} not in dataset")
    for p in predictors:
        if p not in ds:
            raise KeyError(f"Predictor {p!r} not in dataset")

    fe_trend = build_design_matrix(ds["time"])
    pred_df = pd.DataFrame({p: ds[p].values for p in predictors})
    X = pd.concat([pred_df, fe_trend.drop(columns=["intercept"])], axis=1)
    X = sm.add_constant(X, has_constant="add")

    y = pd.Series(ds[response].values, name=response)

    valid = X.notna().all(axis=1) & y.notna()
    X = X.loc[valid]
    y = y.loc[valid]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    return RegressionResult(
        params=model.params,
        bse=model.bse,
        tvalues=model.tvalues,
        pvalues=model.pvalues,
        rsquared=float(model.rsquared),
        nobs=int(model.nobs),
    )
