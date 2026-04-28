"""Plot module: NCAR styling hook plus 13 figure-builder functions.

Plot builders are added incrementally across tasks 15a..15c. This file
holds the shared style hook and `save_figure` helper.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import xarray as xr
from davinci_monet.plots.style import apply_ncar_style


_STYLE_APPLIED = False


def setup_style() -> None:
    """Apply NCAR brand styling once per process. Idempotent."""
    global _STYLE_APPLIED
    if _STYLE_APPLIED:
        return
    apply_ncar_style(context="publication")
    _STYLE_APPLIED = True


def save_figure(fig, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # matplotlib infers format from extension, so keep the original extension
    # on the temp path (e.g. fig.png → fig.tmp.png, not fig.png.tmp).
    tmp = path.with_name(path.stem + ".tmp" + path.suffix)
    fig.savefig(tmp)
    tmp.rename(path)
    plt.close(fig)


def _annotate_caption(fig, ds: xr.Dataset, methods: str = "") -> None:
    region = ds.attrs.get("region", "?")
    bbox = ds.attrs.get("bbox", "")
    t0 = str(xr.DataArray(ds["time"].values[0]).dt.strftime("%Y-%m").item())
    t1 = str(xr.DataArray(ds["time"].values[-1]).dt.strftime("%Y-%m").item())
    caption = f"region={region} {bbox} | {t0}–{t1}"
    if methods:
        caption += f" | {methods}"
    fig.text(0.5, -0.02, caption, ha="center", fontsize=8)


def plot_aod_total_timeseries(ds: xr.Dataset, aeronet, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    for var, label in [
        ("modis_terra_aod", "MODIS Terra"),
        ("modis_aqua_aod", "MODIS Aqua"),
        ("viirs_snpp_aod", "VIIRS-SNPP"),
        ("viirs_noaa20_aod", "VIIRS-NOAA20"),
    ]:
        if var in ds:
            ax.plot(ds["time"], ds[var], label=label, lw=1.0)
    if aeronet is not None and "aeronet_aod_550" in aeronet:
        for site in aeronet["site"].values:
            ax.scatter(
                aeronet["time"], aeronet["aeronet_aod_550"].sel(site=site),
                s=8, alpha=0.6, label=f"AERONET {site}",
            )
    ax.set_xlabel("Year")
    ax.set_ylabel("AOD 550 nm")
    ax.set_title("Total AOD — Pacific Northwest monthly")
    ax.legend(fontsize=8, loc="upper left")
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_smoke_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(ds["time"], ds["smoke_fraction"], lw=1.0)
    ax.set_xlabel("Year")
    ax.set_ylabel("Smoke fraction (–)")
    ax.set_title("MERRA-2-derived smoke fraction — Pacific Northwest")
    _annotate_caption(fig, ds, methods="smoke_fraction = (BC + OC_bb) / TOTAL")
    save_figure(fig, output)


def plot_smoke_aod_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    cols = ["smoke_aod_terra", "smoke_aod_aqua", "smoke_aod_snpp", "smoke_aod_noaa20"]
    arr = xr.concat([ds[c] for c in cols if c in ds], dim="src")
    ax.fill_between(ds["time"], arr.min("src"), arr.max("src"), alpha=0.3, label="inter-platform spread")
    ax.plot(ds["time"], arr.mean("src"), lw=1.0, label="ensemble mean")
    ax.set_xlabel("Year")
    ax.set_ylabel("Smoke AOD 550 nm")
    ax.set_title("Smoke AOD — Pacific Northwest monthly")
    ax.legend(fontsize=9)
    _annotate_caption(fig, ds, methods="smoke_AOD = smoke_fraction × observed AOD")
    save_figure(fig, output)


def _three_panel_anomaly(ds, prefix: str, label: str, output) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for ax, comp, ylabel in zip(
        axes, ("sw", "lw", "net"),
        (f"{label} SW anomaly (W m⁻²)", f"{label} LW anomaly (W m⁻²)", f"{label} Net anomaly (W m⁻²)"),
    ):
        all_var = f"{prefix}_{comp}_all_anom" if "sfc" not in prefix else f"{prefix}_{comp}_down_all_anom"
        clr_var = f"{prefix}_{comp}_clr_anom" if "sfc" not in prefix else f"{prefix}_{comp}_down_clr_anom"
        # Net at sfc lacks "_down" suffix in CERES
        if "sfc" in prefix and comp == "net":
            all_var = f"{prefix}_net_all_anom"
            clr_var = f"{prefix}_net_clr_anom"
        if all_var in ds:
            ax.plot(ds["time"], ds[all_var], label="all-sky", lw=1.0)
        if clr_var in ds:
            ax.plot(ds["time"], ds[clr_var], label="clear-sky", lw=1.0)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=9)
    axes[-1].set_xlabel("Year")
    fig.suptitle(f"CERES {label} radiative-flux anomalies — Pacific Northwest")
    _annotate_caption(fig, ds, methods="anomaly = monthly value − month-of-year climatology")
    save_figure(fig, output)


def plot_ceres_toa_anomaly(ds: xr.Dataset, output) -> None:
    _three_panel_anomaly(ds, prefix="ceres_toa", label="TOA", output=output)


def plot_ceres_sfc_anomaly(ds: xr.Dataset, output) -> None:
    _three_panel_anomaly(ds, prefix="ceres_sfc", label="SFC", output=output)


def plot_seasonal_climatology(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    smoke_clim = ds["smoke_aod_terra"].groupby("time.month").mean()
    dF_clim = ds["ceres_toa_sw_clr_anom"].groupby("time.month").mean()
    width = 0.4
    months = smoke_clim["month"].values
    ax.bar(months - width / 2, smoke_clim, width=width, label="smoke AOD")
    ax2 = ax.twinx()
    ax2.bar(months + width / 2, dF_clim, width=width, color="C1", label="ΔF_TOA_SW (clear-sky)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Smoke AOD")
    ax2.set_ylabel("ΔF_TOA_SW (W m⁻²)")
    ax.set_title("Seasonal climatology — Pacific Northwest")
    ax.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_qfed_emissions_timeseries(ds: xr.Dataset, output) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for ax, var, label in zip(axes, ("qfed_bc", "qfed_oc", "qfed_co"), ("BC", "OC", "CO")):
        ax.plot(ds["time"], ds[var], lw=1.0, label=label)
        ax.set_ylabel(f"{label} (kg m⁻² s⁻¹)")
        if "smoke_aod_terra" in ds:
            ax2 = ax.twinx()
            ax2.plot(ds["time"], ds["smoke_aod_terra"], color="C1", lw=0.8, alpha=0.6)
            ax2.set_ylabel("smoke AOD", color="C1")
        ax.legend(loc="upper left", fontsize=9)
    axes[-1].set_xlabel("Year")
    fig.suptitle("QFED biomass-burning emissions — Pacific Northwest")
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_cloud_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(ds["time"], ds["ceres_cloud_fraction"], lw=1.0)
    ax.set_xlabel("Year")
    ax.set_ylabel("Cloud fraction")
    ax.set_title("CERES total-column cloud fraction — Pacific Northwest")
    _annotate_caption(fig, ds)
    save_figure(fig, output)
