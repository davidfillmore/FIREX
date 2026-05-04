"""Plot module: NCAR styling hook plus 13 figure-builder functions.

Plot builders are added incrementally across tasks 15a..15c. This file
holds the shared style hook and `save_figure` helper.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

# DAVINCI-MONET lives outside the sarb env on this Mac. Path differs by host.
for _cand in (Path.home() / "DAVINCI", Path.home() / "EarthSystem" / "DAVINCI-MONET"):
    if (_cand / "davinci_monet" / "__init__.py").is_file():
        sys.path.insert(0, str(_cand))
        break
from davinci_monet.plots.style import NCAR_COLORS, apply_ncar_style  # noqa: E402


# Study window: CERES record start (Mar 2000) through Feb 2026 = 26 full years.
DATE_MIN = pd.Timestamp("2000-03-01")
DATE_MAX = pd.Timestamp("2026-03-01")  # right edge, exclusive — Feb 2026 sits inside
DATE_LABEL = ("2000-03", "2026-02")


def _apply_date_range(ax) -> None:
    """Clamp time-axis to 2000-03..2026-02 with one tick per year, slanted.

    Ticks are placed at mid-year (Jul 1) so each label sits centered under
    the year's data span, rather than at the Jan-1 boundary between years.
    """
    import matplotlib.dates as mdates
    ax.set_xlim(DATE_MIN, DATE_MAX)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=7))
    ax.xaxis.set_minor_locator(mdates.YearLocator())  # faint Jan-1 ticks
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha("center")


_STYLE_APPLIED = False


def setup_style() -> None:
    """Apply NCAR brand styling once per process. Idempotent."""
    global _STYLE_APPLIED
    if _STYLE_APPLIED:
        return
    apply_ncar_style(context="publication")
    _STYLE_APPLIED = True


def save_figure(fig, path: Path) -> None:
    """Write `fig` atomically as both `path` (PNG @ 300 DPI from NCAR style)
    and `path.pdf` (vector). Each format goes through a `.tmp.<ext>` rename
    so partial writes never appear under the final name."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write the requested format plus PDF alongside (deduped if path is already pdf).
    suffixes = list(dict.fromkeys([path.suffix, ".pdf"]))
    for ext in suffixes:
        target = path.with_suffix(ext)
        # matplotlib infers format from extension, so keep the original extension
        # on the temp path (e.g. fig.png → fig.tmp.png, not fig.png.tmp).
        tmp = target.with_name(target.stem + ".tmp" + target.suffix)
        fig.savefig(tmp)
        tmp.rename(target)
    plt.close(fig)


def _annual_mean_complete(da: xr.DataArray) -> xr.DataArray:
    """Annual means, restricted to years with all 12 months present."""
    counts = da.groupby("time.year").count()
    means = da.groupby("time.year").mean()
    return means.where(counts == 12, drop=True)


def _plot_annual_bars(
    ax, da: xr.DataArray, color: str, y_floor: float | None = None,
) -> float:
    """Faint wide bars at the annual mean for each complete year.

    Returns the y_floor used, so callers can share an anchor across series
    plotted on the same axis.
    """
    annual = _annual_mean_complete(da)
    if annual.size == 0:
        return float("nan") if y_floor is None else y_floor
    if y_floor is None:
        lo = float(annual.min())
        hi = float(annual.max())
        pad = 0.05 * (hi - lo) if hi > lo else 0.0
        y_floor = lo - pad
    bar_dates = pd.to_datetime([f"{int(y)}-07-01" for y in annual.year.values])
    ax.bar(
        bar_dates,
        annual.values - y_floor,
        bottom=y_floor,
        width=np.timedelta64(300, "D"),
        color=color,
        alpha=0.15,
        zorder=1,
    )
    return y_floor


def _plot_anomaly_fill(
    ax, time, values, pos_color: str, neg_color: str,
) -> None:
    """Shade between zero and *values*: pos_color above, neg_color below."""
    values = np.asarray(values, dtype=float)
    ax.axhline(0, color=NCAR_COLORS["gray"], lw=0.8, zorder=1)
    ax.fill_between(
        time, 0, values, where=values >= 0,
        color=pos_color, alpha=0.2, zorder=1, interpolate=True,
    )
    ax.fill_between(
        time, 0, values, where=values < 0,
        color=neg_color, alpha=0.2, zorder=1, interpolate=True,
    )


def _region_label(ds: xr.Dataset) -> str:
    """Humanize the region slug stored in ds.attrs (e.g. eastern-australia → Eastern Australia)."""
    raw = ds.attrs.get("region", "")
    return raw.replace("-", " ").title() if raw else "?"


def _annotate_caption(fig, ds: xr.Dataset, methods: str = "") -> None:
    """Footer was redundant with title + axes; keep tight_layout only."""
    fig.tight_layout()


def plot_aod_total_timeseries(ds: xr.Dataset, aeronet, output) -> None:
    """Per-AERONET-site panel grid: satellite AODs sampled at the site
    (nearest gridcell) overlaid with AERONET observations at that site.

    Falls back to a single-panel region-mean view when no AERONET sites
    are present or the per-site companion vars aren't in the dataset.
    """
    series = [
        ("modis_terra_aod", "MODIS Terra", NCAR_COLORS["ncar_blue"]),
        ("modis_aqua_aod", "MODIS Aqua", NCAR_COLORS["aqua"]),
        ("viirs_snpp_aod", "VIIRS-SNPP", NCAR_COLORS["orange"]),
        ("viirs_noaa20_aod", "VIIRS-NOAA20", NCAR_COLORS["purple"]),
    ]
    have_sites = (
        aeronet is not None
        and "aeronet_aod_550" in aeronet
        and aeronet.sizes.get("site", 0) > 0
        and any(f"{v}_site" in ds for v, _, _ in series)
    )
    if not have_sites:
        # Legacy region-mean view (no AERONET in bbox).
        _plot_aod_total_region_mean(ds, aeronet, series, output)
        return

    sites = list(aeronet["site"].values)
    n = len(sites)
    fig, axes = plt.subplots(n, 1, figsize=(10, 3.0 * n),
                             sharex=True, squeeze=False)
    handles: dict[str, object] = {}
    for i, site in enumerate(sites):
        ax = axes[i][0]
        site_present = [(v, lbl, c) for v, lbl, c in series if f"{v}_site" in ds]
        if site_present:
            ensemble = xr.concat(
                [ds[f"{v}_site"].sel(site=site) for v, _, _ in site_present], dim="src",
            ).mean("src")
            _plot_annual_bars(ax, ensemble, NCAR_COLORS["gray"])
            for var, label, color in site_present:
                line, = ax.plot(
                    ds["time"], ds[f"{var}_site"].sel(site=site),
                    label=label, lw=1.2, color=color, zorder=2,
                )
                handles[label] = line
        # AERONET points at this site.
        ae = aeronet["aeronet_aod_550"].sel(site=site)
        sc = ax.scatter(
            aeronet["time"], ae,
            s=8, alpha=0.6, color=NCAR_COLORS["red"], zorder=3,
        )
        handles["AERONET"] = sc
        ax.set_title(str(site))
        ax.set_ylabel("AOD 550 nm")
        _apply_date_range(ax)
    axes[-1][0].set_xlabel("Year")
    fig.suptitle(f"Total AOD at AERONET sites — {_region_label(ds)}")
    fig.legend(handles.values(), handles.keys(), loc="lower center",
               ncol=min(5, len(handles)), fontsize=9, frameon=False)
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 0.97))
    save_figure(fig, output)


def _plot_aod_total_region_mean(ds, aeronet, series, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    present = [(v, lbl, c) for v, lbl, c in series if v in ds]
    if present:
        ensemble = xr.concat([ds[v] for v, _, _ in present], dim="src").mean("src")
        _plot_annual_bars(ax, ensemble, NCAR_COLORS["gray"])
        for var, label, color in present:
            ax.plot(ds["time"], ds[var], label=label, lw=1.2, color=color, zorder=2)
    if aeronet is not None and "aeronet_aod_550" in aeronet:
        for site in aeronet["site"].values:
            ax.scatter(
                aeronet["time"], aeronet["aeronet_aod_550"].sel(site=site),
                s=8, alpha=0.6, label=f"AERONET {site}", zorder=3,
            )
    ax.set_xlabel("Year")
    ax.set_ylabel("AOD 550 nm")
    ax.set_title(f"Total AOD — {_region_label(ds)} monthly (regional mean)")
    ax.legend(fontsize=8, loc="upper left")
    _apply_date_range(ax)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_smoke_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    color = NCAR_COLORS["ncar_blue"]
    _plot_annual_bars(ax, ds["smoke_fraction"], color)
    ax.plot(ds["time"], ds["smoke_fraction"], lw=1.2, color=color, zorder=2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Smoke fraction (–)")
    ax.set_title(f"MERRA-2-derived smoke fraction — {_region_label(ds)}")
    _apply_date_range(ax)
    _annotate_caption(fig, ds, methods="smoke_fraction = (BC + OC_bb) / TOTAL")
    save_figure(fig, output)


def plot_smoke_aod_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    cols = ["smoke_aod_terra", "smoke_aod_aqua", "smoke_aod_snpp", "smoke_aod_noaa20"]
    arr = xr.concat([ds[c] for c in cols if c in ds], dim="src")
    mean = arr.mean("src")
    color = NCAR_COLORS["ncar_blue"]
    spread_color = NCAR_COLORS["aqua"]
    _plot_annual_bars(ax, mean, color)
    ax.fill_between(
        ds["time"], arr.min("src"), arr.max("src"),
        color=spread_color, alpha=0.3, label="inter-platform spread", zorder=2,
    )
    ax.plot(ds["time"], mean, lw=1.2, color=color, label="ensemble mean", zorder=3)
    ax.set_xlabel("Year")
    ax.set_ylabel("Smoke AOD 550 nm")
    ax.set_title(f"Smoke AOD — {_region_label(ds)} monthly")
    ax.legend(fontsize=9)
    _apply_date_range(ax)
    _annotate_caption(fig, ds, methods="smoke_AOD = smoke_fraction × observed AOD")
    save_figure(fig, output)


def _three_panel_anomaly(ds, prefix: str, label: str, output) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    pos_color = NCAR_COLORS["orange"]
    neg_color = NCAR_COLORS["ncar_blue"]
    all_color = NCAR_COLORS["gray"]
    clr_color = NCAR_COLORS["red"]
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
        if clr_var in ds:
            _plot_anomaly_fill(ax, ds["time"].values, ds[clr_var].values, pos_color, neg_color)
            ax.plot(ds["time"], ds[clr_var], label="clear-sky", lw=1.2, color=clr_color, zorder=3)
        if all_var in ds:
            ax.plot(ds["time"], ds[all_var], label="all-sky", lw=0.8, color=all_color, alpha=0.8, zorder=2)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=9)
    axes[-1].set_xlabel("Year")
    _apply_date_range(axes[-1])
    fig.suptitle(f"CERES {label} radiative-flux anomalies — {_region_label(ds)}")
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
    ax.set_title(f"Seasonal climatology — {_region_label(ds)}")
    ax.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_qfed_emissions_timeseries(ds: xr.Dataset, output) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    main_color = NCAR_COLORS["ncar_blue"]
    aod_color = NCAR_COLORS["aqua"]
    for ax, var, label in zip(axes, ("qfed_bc", "qfed_oc", "qfed_co"), ("BC", "OC", "CO")):
        _plot_annual_bars(ax, ds[var], main_color)
        ax.plot(ds["time"], ds[var], lw=1.2, color=main_color, label=label, zorder=2)
        ax.set_ylabel(f"{label} (kg m⁻² s⁻¹)")
        if "smoke_aod_terra" in ds:
            ax2 = ax.twinx()
            ax2.plot(ds["time"], ds["smoke_aod_terra"], color=aod_color, lw=0.8, alpha=0.6)
            ax2.set_ylabel("smoke AOD", color=aod_color)
        ax.legend(loc="upper left", fontsize=9)
    axes[-1].set_xlabel("Year")
    _apply_date_range(axes[-1])
    fig.suptitle(f"QFED biomass-burning emissions — {_region_label(ds)}")
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_cloud_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    color = NCAR_COLORS["ncar_blue"]
    _plot_annual_bars(ax, ds["ceres_cloud_fraction"], color)
    ax.plot(ds["time"], ds["ceres_cloud_fraction"], lw=1.2, color=color, zorder=2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Cloud fraction")
    ax.set_title(f"CERES total-column cloud fraction — {_region_label(ds)}")
    _apply_date_range(ax)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def _scatter_with_ols(ax, x: np.ndarray, y: np.ndarray, label: str) -> None:
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    ax.scatter(x, y, s=10, alpha=0.5)
    if x.size >= 3:
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 50)
        ax.plot(xs, slope * xs + intercept, color="C3", lw=1.5)
        # SE estimate from residuals
        yhat = slope * x + intercept
        resid = y - yhat
        sxx = ((x - x.mean()) ** 2).sum()
        se = np.sqrt((resid ** 2).sum() / (x.size - 2) / sxx) if x.size > 2 else float("nan")
        r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum() if y.var() > 0 else 0
        ax.text(
            0.05, 0.95,
            f"β = {slope:.1f} ± {se:.1f}\nn = {x.size}\nR² = {r2:.2f}",
            transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"),
        )
    ax.set_title(label)


def _scatter_pair(ds, smoke_var: str, all_var: str, clr_var: str, ylabel: str, output) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    smoke = ds[smoke_var].values
    _scatter_with_ols(axes[0], smoke, ds[clr_var].values, "clear-sky")
    _scatter_with_ols(axes[1], smoke, ds[all_var].values, "all-sky")
    axes[0].set_ylabel(ylabel)
    for ax in axes:
        ax.set_xlabel("Smoke AOD (MODIS Terra)")
    _annotate_caption(fig, ds, methods="OLS regression on monthly anomalies")
    save_figure(fig, output)


def plot_scatter_dF_TOA_vs_smoke(ds, output) -> None:
    _scatter_pair(
        ds, smoke_var="smoke_aod_terra",
        all_var="ceres_toa_sw_all_anom", clr_var="ceres_toa_sw_clr_anom",
        ylabel="ΔF_TOA_SW (W m⁻²)", output=output,
    )


def plot_scatter_dF_SFC_vs_smoke(ds, output) -> None:
    _scatter_pair(
        ds, smoke_var="smoke_aod_terra",
        all_var="ceres_sfc_sw_down_all_anom", clr_var="ceres_sfc_sw_down_clr_anom",
        ylabel="ΔF_SFC_SW↓ (W m⁻²)", output=output,
    )


def plot_aeronet_vs_modis_scatter(ds, aeronet, output) -> None:
    """Per-site scatter of AERONET vs MODIS Terra at the same gridcell.

    Uses `modis_terra_aod_site` (nearest gridcell at the AERONET site) when
    present; falls back to the region-mean `modis_terra_aod` otherwise.
    """
    n_sites = aeronet.sizes.get("site", 0) if aeronet is not None else 0
    if aeronet is None or "aeronet_aod_550" not in aeronet or n_sites == 0:
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.text(0.5, 0.5, "no AERONET sites inside region bbox",
                ha="center", va="center", transform=ax.transAxes, fontsize=11)
        ax.set_xlabel("AERONET AOD 550 nm")
        ax.set_ylabel("MODIS Terra gridcell AOD")
        ax.set_title("AERONET vs. MODIS")
        save_figure(fig, output)
        return

    sites = list(aeronet["site"].values)
    use_site_var = "modis_terra_aod_site" in ds
    ncols = min(n_sites, 2)
    nrows = (n_sites + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 5 * nrows), squeeze=False)
    for i, site in enumerate(sites):
        ax = axes[i // ncols][i % ncols]
        site_aod = aeronet["aeronet_aod_550"].sel(site=site)
        if use_site_var:
            modis = ds["modis_terra_aod_site"].sel(site=site).interp(time=aeronet["time"])
        else:
            modis = ds["modis_terra_aod"].interp(time=aeronet["time"])
        x = site_aod.values
        y = modis.values
        valid = np.isfinite(x) & np.isfinite(y)
        ax.scatter(x[valid], y[valid], s=12, alpha=0.6, color=NCAR_COLORS["ncar_blue"])
        if valid.sum() >= 3:
            xv, yv = x[valid], y[valid]
            slope, intercept = np.polyfit(xv, yv, 1)
            r2 = 1 - ((yv - (slope * xv + intercept)) ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
            xs = np.linspace(0, np.nanmax(xv), 50)
            ax.plot(xs, slope * xs + intercept, color=NCAR_COLORS["red"], lw=1.2)
            ax.text(0.05, 0.95, f"n = {valid.sum()}\nβ = {slope:.2f}\nR² = {r2:.2f}",
                    transform=ax.transAxes, va="top", fontsize=9,
                    bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"))
        lim = float(np.nanmax(np.concatenate([x[valid], y[valid]]))) if valid.any() else 1.0
        ax.plot([0, lim], [0, lim], "k--", lw=0.6)
        ax.set_xlim(0, lim); ax.set_ylim(0, lim)
        ax.set_xlabel("AERONET AOD 550 nm")
        ax.set_ylabel("MODIS Terra (site gridcell)")
        ax.set_title(str(site))
    for j in range(n_sites, nrows * ncols):
        axes[j // ncols][j % ncols].set_visible(False)
    fig.suptitle(f"AERONET vs MODIS Terra — {_region_label(ds)}")
    fig.tight_layout()
    save_figure(fig, output)


def plot_merra2_obs_scaling(ds, output) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].scatter(ds["modis_terra_aod"], ds["merra2_aer_TOTEXTTAU"], s=10, alpha=0.5)
    lim = float(max(ds["modis_terra_aod"].max(), ds["merra2_aer_TOTEXTTAU"].max()))
    axes[0].plot([0, lim], [0, lim], "k--", lw=0.8)
    axes[0].set_xlabel("MODIS Terra AOD")
    axes[0].set_ylabel("MERRA-2 TOTEXTTAU")
    axes[0].set_title("Magnitude comparison")
    ratio = ds["merra2_aer_TOTEXTTAU"] / ds["modis_terra_aod"]
    axes[1].plot(ds["time"], ratio, lw=1.0)
    axes[1].set_xlabel("Year")
    axes[1].set_ylabel("MERRA-2 / MODIS")
    axes[1].set_title("Scaling-factor time series")
    _apply_date_range(axes[1])
    _annotate_caption(fig, ds, methods="ratio used to validate MERRA-2 fractional split, not magnitude")
    save_figure(fig, output)


def plot_spatial_maps_peak_year(
    gridded: xr.Dataset,
    peak_year: int,
    region_bbox: tuple[float, float, float, float],
    output,
) -> None:
    """2x2 cartopy grid: rows = climatology / peak-year anomaly, cols = smoke AOD / ΔF_TOA_SW_clr."""
    smoke = gridded["smoke_aod_terra"]
    dF = gridded["ceres_toa_sw_clr_anom"]

    smoke_clim = smoke.mean("time")
    dF_clim = dF.mean("time")
    smoke_peak = smoke.sel(time=str(peak_year)).mean("time") - smoke_clim
    dF_peak = dF.sel(time=str(peak_year)).mean("time") - dF_clim

    fig = plt.figure(figsize=(11, 8))
    panels = [
        ("Climatology — smoke AOD", smoke_clim, "viridis", None),
        ("Climatology — ΔF_TOA_SW_clr", dF_clim, "RdBu_r", (-5, 5)),
        (f"{peak_year} anomaly — smoke AOD", smoke_peak, "viridis", None),
        (f"{peak_year} anomaly — ΔF_TOA_SW_clr", dF_peak, "RdBu_r", (-10, 10)),
    ]
    for i, (title, data, cmap, vrange) in enumerate(panels, start=1):
        ax = fig.add_subplot(2, 2, i, projection=ccrs.PlateCarree())
        kwargs = {"cmap": cmap}
        if vrange is not None:
            kwargs["vmin"], kwargs["vmax"] = vrange
        m = ax.pcolormesh(data["lon"], data["lat"], data, transform=ccrs.PlateCarree(), **kwargs)
        ax.coastlines(lw=0.5)
        ax.add_feature(cfeature.STATES.with_scale("50m"), lw=0.3)
        lon_min, lon_max, lat_min, lat_max = region_bbox
        ax.plot(
            [lon_min, lon_max, lon_max, lon_min, lon_min],
            [lat_min, lat_min, lat_max, lat_max, lat_min],
            "k", lw=1.0, transform=ccrs.PlateCarree(),
        )
        ax.set_extent([lon_min - 5, lon_max + 5, lat_min - 5, lat_max + 5])
        ax.set_title(title, fontsize=10)
        plt.colorbar(m, ax=ax, shrink=0.7)
    fig.suptitle(f"Spatial fields: climatology vs. {peak_year} anomaly")
    save_figure(fig, output)
