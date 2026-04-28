"""Tests for the plotting layer (light: existence + write-out only)."""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from firex.plots import (
    setup_style,
    save_figure,
    plot_aod_total_timeseries,
    plot_smoke_fraction_timeseries,
    plot_smoke_aod_timeseries,
    plot_ceres_toa_anomaly,
    plot_ceres_sfc_anomaly,
    plot_seasonal_climatology,
    plot_qfed_emissions_timeseries,
    plot_cloud_fraction_timeseries,
    plot_scatter_dF_TOA_vs_smoke,
    plot_scatter_dF_SFC_vs_smoke,
    plot_aeronet_vs_modis_scatter,
    plot_merra2_obs_scaling,
    plot_spatial_maps_peak_year,
)


def _synth_merged() -> xr.Dataset:
    times = pd.date_range("2000-03", periods=300, freq="MS")
    n = times.size
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "modis_terra_aod": ("time", 0.15 + 0.05 * rng.standard_normal(n)),
            "modis_aqua_aod": ("time", 0.16 + 0.05 * rng.standard_normal(n)),
            "viirs_snpp_aod": ("time", 0.14 + 0.04 * rng.standard_normal(n)),
            "viirs_noaa20_aod": ("time", 0.14 + 0.04 * rng.standard_normal(n)),
            "smoke_fraction": ("time", 0.20 + 0.05 * rng.standard_normal(n)),
            "smoke_aod_terra": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "smoke_aod_aqua": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "smoke_aod_snpp": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "smoke_aod_noaa20": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "ceres_toa_sw_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_sw_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_lw_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_lw_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_net_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_net_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_sw_down_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_sw_down_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_lw_down_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_lw_down_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_net_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_net_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_cloud_fraction": ("time", 0.5 + 0.05 * rng.standard_normal(n)),
            "qfed_bc": ("time", 1e-10 + 1e-11 * rng.standard_normal(n)),
            "qfed_oc": ("time", 5e-10 + 1e-10 * rng.standard_normal(n)),
            "qfed_co": ("time", 5e-9 + 1e-9 * rng.standard_normal(n)),
        },
        coords={"time": times},
        attrs={"region": "pacific-northwest", "bbox": "[42N–52N, 130W–110W]"},
    )


def test_setup_style_runs():
    setup_style()
    # spot-check a known NCAR-styled rcParam
    assert plt.rcParams["savefig.dpi"] == 300


def test_save_figure_writes_png(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 4])
    out = tmp_path / "fig.png"
    save_figure(fig, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_plot_aod_total_timeseries(tmp_path):
    setup_style()
    ds = _synth_merged()
    out = tmp_path / "p1.png"
    plot_aod_total_timeseries(ds, aeronet=None, output=out)
    assert out.exists()


def test_plot_smoke_fraction_timeseries(tmp_path):
    setup_style()
    plot_smoke_fraction_timeseries(_synth_merged(), tmp_path / "p2.png")
    assert (tmp_path / "p2.png").exists()


def test_plot_smoke_aod_timeseries(tmp_path):
    setup_style()
    plot_smoke_aod_timeseries(_synth_merged(), tmp_path / "p3.png")
    assert (tmp_path / "p3.png").exists()


def test_plot_ceres_toa_anomaly(tmp_path):
    setup_style()
    plot_ceres_toa_anomaly(_synth_merged(), tmp_path / "p4.png")
    assert (tmp_path / "p4.png").exists()


def test_plot_ceres_sfc_anomaly(tmp_path):
    setup_style()
    plot_ceres_sfc_anomaly(_synth_merged(), tmp_path / "p5.png")
    assert (tmp_path / "p5.png").exists()


def test_plot_seasonal_climatology(tmp_path):
    setup_style()
    plot_seasonal_climatology(_synth_merged(), tmp_path / "p8.png")
    assert (tmp_path / "p8.png").exists()


def test_plot_qfed_emissions(tmp_path):
    setup_style()
    plot_qfed_emissions_timeseries(_synth_merged(), tmp_path / "p10.png")
    assert (tmp_path / "p10.png").exists()


def test_plot_cloud_fraction(tmp_path):
    setup_style()
    plot_cloud_fraction_timeseries(_synth_merged(), tmp_path / "p12.png")
    assert (tmp_path / "p12.png").exists()


def test_plot_scatter_toa(tmp_path):
    setup_style()
    plot_scatter_dF_TOA_vs_smoke(_synth_merged(), tmp_path / "p6.png")
    assert (tmp_path / "p6.png").exists()


def test_plot_scatter_sfc(tmp_path):
    setup_style()
    plot_scatter_dF_SFC_vs_smoke(_synth_merged(), tmp_path / "p7.png")
    assert (tmp_path / "p7.png").exists()


def test_plot_aeronet_vs_modis(tmp_path):
    setup_style()
    times = pd.date_range("2000-03", periods=300, freq="MS")
    aeronet = xr.Dataset(
        {"aeronet_aod_550": (("time", "site"), np.full((times.size, 2), 0.1))},
        coords={"time": times, "site": ["Trinidad_Head", "Railroad_Valley"]},
    )
    plot_aeronet_vs_modis_scatter(_synth_merged(), aeronet, tmp_path / "p11.png")
    assert (tmp_path / "p11.png").exists()


def test_plot_merra2_obs_scaling(tmp_path):
    setup_style()
    ds = _synth_merged().assign(merra2_aer_TOTEXTTAU=("time", np.full(300, 0.18)))
    plot_merra2_obs_scaling(ds, tmp_path / "p13.png")
    assert (tmp_path / "p13.png").exists()


def test_plot_spatial_maps(tmp_path):
    setup_style()
    times = pd.date_range("2000-03", periods=300, freq="MS")
    lat = np.arange(40.5, 53)
    lon = np.arange(-130.5, -109)
    rng = np.random.default_rng(0)
    shape = (times.size, lat.size, lon.size)
    gridded = xr.Dataset(
        {
            "smoke_aod_terra": (("time", "lat", "lon"), 0.05 + 0.02 * rng.standard_normal(shape)),
            "ceres_toa_sw_clr_anom": (("time", "lat", "lon"), 1.0 * rng.standard_normal(shape)),
        },
        coords={"time": times, "lat": lat, "lon": lon},
    )
    out = tmp_path / "p9.png"
    plot_spatial_maps_peak_year(gridded, peak_year=2020, region_bbox=(-130, -110, 42, 52), output=out)
    assert out.exists()
