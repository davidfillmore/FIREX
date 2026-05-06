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


_QFED_BAD_YEARS = (2017,)


def _mask_bad_qfed(ds: xr.Dataset) -> xr.Dataset:
    """Mask QFED variables to NaN in known-bad years (Y2017 ships byte-
    identical daily files in the local archive). MERRA-2-derived smoke
    fields are unaffected and stay intact. See CLAUDE.md §Datasets."""
    qfed_vars = [v for v in ds.data_vars if v.startswith("qfed_")]
    if not qfed_vars:
        return ds
    years = ds["time"].dt.year
    bad = years.isin(list(_QFED_BAD_YEARS))
    return ds.assign({
        v: ds[v].where(~bad) for v in qfed_vars
    })


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
    fig.suptitle(f"Total AOD at AERONET Sites — {_region_label(ds)}")
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
    ax.set_title(f"Total AOD — {_region_label(ds)} Monthly (Regional Mean)")
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
    ax.set_ylabel("Smoke Fraction (–)")
    ax.set_title(f"MERRA-2-Derived Smoke Fraction — {_region_label(ds)}")
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
    ax.set_title(f"Smoke AOD — {_region_label(ds)} Monthly")
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
        (f"{label} SW Anomaly (W m⁻²)", f"{label} LW Anomaly (W m⁻²)", f"{label} Net Anomaly (W m⁻²)"),
    ):
        all_var = f"{prefix}_{comp}_all_anom" if "sfc" not in prefix else f"{prefix}_{comp}_down_all_anom"
        clr_var = f"{prefix}_{comp}_clr_anom" if "sfc" not in prefix else f"{prefix}_{comp}_down_clr_anom"
        # Net at sfc lacks "_down" suffix in CERES
        if "sfc" in prefix and comp == "net":
            all_var = f"{prefix}_net_all_anom"
            clr_var = f"{prefix}_net_clr_anom"
        if clr_var in ds:
            _plot_anomaly_fill(ax, ds["time"].values, ds[clr_var].values, pos_color, neg_color)
            ax.plot(ds["time"], ds[clr_var], label="Clear-Sky", lw=1.2, color=clr_color, zorder=3)
        if all_var in ds:
            ax.plot(ds["time"], ds[all_var], label="All-Sky", lw=0.8, color=all_color, alpha=0.8, zorder=2)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=9)
    axes[-1].set_xlabel("Year")
    _apply_date_range(axes[-1])
    fig.suptitle(f"CERES {label} Radiative-Flux Anomalies — {_region_label(ds)}")
    _annotate_caption(fig, ds, methods="anomaly = monthly value − month-of-year climatology")
    save_figure(fig, output)


def _sw_anom_series(
    ds: xr.Dataset, kind: str, sky: str, flux_source: str,
) -> tuple[xr.DataArray | None, str]:
    """Return the SW anomaly series and a short flux-source label.

    `flux_source="ceres"` reads `ceres_*_anom`. `flux_source="merra2"` reads
    `merra2_rad_SW*_anom`; for `kind="toa"` the MERRA-2 series is *negated*
    (SWTNT is net-down at TOA whereas CERES TOA SW is upward outgoing) so
    the two read with the same convention: positive ΔF = more outgoing SW.
    """
    if flux_source == "ceres":
        if kind == "sfc":
            name = f"ceres_sfc_sw_down_{sky}_anom"
        else:
            name = f"ceres_toa_sw_{sky}_anom"
        return (ds[name] if name in ds else None), "CERES"
    if flux_source == "merra2":
        if kind == "sfc":
            name = "merra2_rad_SWGDN_anom" if sky == "all" else "merra2_rad_SWGDNCLR_anom"
            da = ds[name] if name in ds else None
        else:
            name = "merra2_rad_SWTNT_anom" if sky == "all" else "merra2_rad_SWTNTCLR_anom"
            da = -ds[name] if name in ds else None
        return da, "MERRA-2"
    raise ValueError(f"flux_source must be 'ceres' or 'merra2', got {flux_source!r}")


def _smoke_series(
    ds: xr.Dataset, smoke_source: str,
) -> tuple[xr.DataArray | None, str]:
    """Return the smoke-AOD series and its legend label."""
    if smoke_source == "platform_ensemble":
        cols = [c for c in
                ("smoke_aod_terra","smoke_aod_aqua","smoke_aod_snpp","smoke_aod_noaa20")
                if c in ds]
        if not cols:
            return None, "Smoke AOD"
        return (xr.concat([ds[c] for c in cols], dim="src").mean("src"),
                "Smoke AOD (obs ensemble)")
    if smoke_source == "merra2":
        return (ds["smoke_aod_merra2"] if "smoke_aod_merra2" in ds else None,
                "Smoke AOD (MERRA-2)")
    raise ValueError(f"smoke_source must be 'platform_ensemble' or 'merra2', got {smoke_source!r}")


def _render_smoke_twinx(
    ax_a, ds: xr.Dataset, smoke: xr.DataArray, smoke_label: str,
    sw_for_peaks: xr.DataArray | None,
    pos_color: str, neg_color: str,
) -> object:
    """Twin axis with smoke AOD + top-N smoke-peak markers + month labels.

    `sw_for_peaks` is the ΔF series whose value at each peak month gets a
    color-coded marker (blue if positive, orange if negative). Pass the
    primary CERES line in compare plots so peak markers track the
    observational reference.
    """
    ax_s = ax_a.twinx()
    smoke_color = "black"
    ax_s.plot(ds["time"], smoke, lw=1.2, color=smoke_color, alpha=0.9,
              label=smoke_label)
    ax_s.set_ylabel("Smoke AOD 550 nm", color=smoke_color)
    ax_s.tick_params(axis="y", colors=smoke_color)
    # Layer smoke beneath the SW anomaly: drop the twin axis below the
    # primary, then make the primary's face transparent so smoke shows
    # through. (matplotlib draws twinx on top by default — zorder alone
    # isn't enough.)
    ax_s.set_zorder(ax_a.get_zorder() - 1)
    ax_a.patch.set_alpha(0.0)

    # Mark the four highest-smoke-AOD months in the record. Label each
    # smoke marker with the year; mirror the marker on the SW-anomaly
    # trace in orange/blue depending on sign.
    smoke_vals = smoke.values
    years = pd.DatetimeIndex(smoke["time"].values).year
    sw_vals = (sw_for_peaks.values if sw_for_peaks is not None
               else np.full_like(smoke_vals, np.nan))
    df = pd.DataFrame({"time": smoke["time"].values, "smoke": smoke_vals,
                       "sw": sw_vals, "year": years})
    # EAU's Black Summer (Dec 2019 + Jan 2020) takes two of the top slots,
    # so bump to 5 there to keep four distinct fire events labeled.
    top_n = 5 if ds.attrs.get("region") == "eastern-australia" else 4
    peaks = df.dropna(subset=["smoke"]).nlargest(top_n, "smoke").sort_values("time")
    if not peaks.empty:
        import matplotlib.dates as mdates
        from matplotlib.transforms import blended_transform_factory
        trans_smoke = blended_transform_factory(ax_a.transData, ax_s.transData)
        peak_xnum = mdates.date2num(peaks["time"].values)
        ax_a.scatter(peak_xnum, peaks["smoke"], s=42, facecolor="black",
                     edgecolor="white", linewidths=0.6,
                     transform=trans_smoke, zorder=20, clip_on=False)
        for x_num, row in zip(peak_xnum, peaks.itertuples(index=False)):
            label = pd.Timestamp(row.time).strftime("%b %Y")
            ax_a.annotate(
                label, xy=(x_num, row.smoke),
                xycoords=trans_smoke,
                xytext=(6, 0), textcoords="offset points",
                ha="left", va="center", fontsize=8, color="black",
                zorder=21, clip_on=False,
            )
        valid_sw = peaks.dropna(subset=["sw"])
        if not valid_sw.empty:
            sw_colors = [pos_color if v >= 0 else neg_color for v in valid_sw["sw"]]
            ax_a.scatter(valid_sw["time"], valid_sw["sw"], s=42,
                         facecolor=sw_colors,
                         edgecolor="white", linewidths=0.6, zorder=20)
    return ax_s


def _plot_aod_sw_pair(
    ds: xr.Dataset, kind: str, output, sky: str = "clr",
    flux_source: str = "ceres", smoke_source: str = "platform_ensemble",
    show_aod_panel: bool = True,
) -> None:
    """SW (clear- or all-sky) anomaly + smoke AOD on twinx, optionally with
    a top total-AOD panel.

    `flux_source` selects the SW anomaly dataset (CERES or MERRA-2 rad);
    `smoke_source` selects the smoke-AOD trace (per-platform ensemble or
    MERRA-2-internal smoke_aod_merra2). When `show_aod_panel=False`, the
    figure collapses to a single panel — useful when an AOD timeseries is
    already shown elsewhere.
    """
    if sky not in ("clr", "all"):
        raise ValueError(f"sky must be 'clr' or 'all', got {sky!r}")
    sky_label = "Clear-Sky" if sky == "clr" else "All-Sky"
    sw_series, flux_label = _sw_anom_series(ds, kind, sky, flux_source)
    if kind == "sfc":
        ylabel_anom = f"ΔF$_{{SFC,SW↓}}$ {sky_label} ({flux_label}, W m⁻²)"
        title_tag = "Surface"
    elif kind == "toa":
        ylabel_anom = f"ΔF$_{{TOA,SW}}$ {sky_label} ({flux_label}, W m⁻²)"
        title_tag = "TOA"
    else:
        raise ValueError(f"kind must be 'sfc' or 'toa', got {kind!r}")

    if show_aod_panel:
        fig, axes = plt.subplots(
            2, 1, figsize=(11, 9), sharex=True,
            gridspec_kw={"height_ratios": [1, 1.6]},
        )
        ax = axes[0]
        sat_series = [
            ("modis_terra_aod", "MODIS Terra", NCAR_COLORS["ncar_blue"]),
            ("modis_aqua_aod", "MODIS Aqua", NCAR_COLORS["aqua"]),
            ("viirs_snpp_aod", "VIIRS-SNPP", NCAR_COLORS["orange"]),
            ("viirs_noaa20_aod", "VIIRS-NOAA20", NCAR_COLORS["purple"]),
        ]
        present = [(v, lbl, c) for v, lbl, c in sat_series if v in ds]
        if present:
            ensemble = xr.concat([ds[v] for v, _, _ in present], dim="src").mean("src")
            _plot_annual_bars(ax, ensemble, NCAR_COLORS["gray"])
            for var, label, color in present:
                ax.plot(ds["time"], ds[var], label=label, lw=1.0, color=color, zorder=2)
        if "merra2_aer_TOTEXTTAU" in ds:
            ax.plot(ds["time"], ds["merra2_aer_TOTEXTTAU"], label="MERRA-2 TOT",
                    lw=1.4, color=NCAR_COLORS["red"], zorder=3)
        ax.set_ylabel("Total AOD 550 nm")
        ax.legend(fontsize=8, loc="upper left", ncol=2)
        ax_a = axes[1]
        last_ax = axes[-1]
    else:
        fig, ax_a = plt.subplots(1, 1, figsize=(11, 5))
        last_ax = ax_a

    # Positive ΔF in blue, negative in orange — orange marks dimming/cooling
    # so it visually pairs with the smoke peaks.
    pos_color = NCAR_COLORS["ncar_blue"]
    neg_color = NCAR_COLORS["orange"]
    if sw_series is not None:
        _plot_anomaly_fill(ax_a, ds["time"].values, sw_series.values,
                           pos_color, neg_color)
        ax_a.plot(ds["time"], sw_series, lw=1.2,
                  color=NCAR_COLORS["red"], zorder=3,
                  label=f"ΔF {sky_label} ({flux_label})")
    ax_a.set_ylabel(ylabel_anom)
    if kind == "sfc":
        # Invert so dimming (negative ΔF) reads "up" — visually aligns with
        # the AOD spikes in the panel above (or in the AOD plot pair when
        # the top panel is suppressed).
        ax_a.invert_yaxis()

    smoke, smoke_label = _smoke_series(ds, smoke_source)
    if smoke is not None:
        ax_s = _render_smoke_twinx(ax_a, ds, smoke, smoke_label,
                                   sw_for_peaks=sw_series,
                                   pos_color=pos_color, neg_color=neg_color)
        handles, labels = ax_a.get_legend_handles_labels()
        h2, l2 = ax_s.get_legend_handles_labels()
        ax_a.legend(handles + h2, labels + l2, fontsize=8, loc="upper left")
    else:
        ax_a.legend(fontsize=8, loc="upper left")

    last_ax.set_xlabel("Year")
    _apply_date_range(last_ax)
    fig.suptitle(
        f"{flux_label} SW {title_tag} {sky_label} Anomaly — {_region_label(ds)}"
        if not show_aod_panel else
        f"AOD and {flux_label} SW {title_tag} {sky_label} Anomaly — {_region_label(ds)}"
    )
    fig.tight_layout()
    save_figure(fig, output)


def _plot_dF_compare(
    ds: xr.Dataset, kind: str, output, sky: str = "clr",
    smoke_source: str = "merra2",
) -> None:
    """Single panel: CERES and MERRA-2 SW anomalies overlaid + smoke AOD twinx.

    Both series share the W m⁻² axis. CERES is the observational reference
    (red, with anomaly fill); MERRA-2 is overlaid as a dashed line in
    purple to read as "the model's claim" against the observation. SWTNT
    is already negated by `_sw_anom_series` so the two share sign
    convention (positive ΔF = more outgoing SW at TOA / more incoming SW
    at SFC).
    """
    if sky not in ("clr", "all"):
        raise ValueError(f"sky must be 'clr' or 'all', got {sky!r}")
    sky_label = "Clear-Sky" if sky == "clr" else "All-Sky"
    ceres_sw, _ = _sw_anom_series(ds, kind, sky, "ceres")
    merra2_sw, _ = _sw_anom_series(ds, kind, sky, "merra2")
    if kind == "sfc":
        ylabel_anom = f"ΔF$_{{SFC,SW↓}}$ {sky_label} (W m⁻²)"
        title_tag = "Surface"
    elif kind == "toa":
        ylabel_anom = f"ΔF$_{{TOA,SW}}$ {sky_label} (W m⁻²)"
        title_tag = "TOA"
    else:
        raise ValueError(f"kind must be 'sfc' or 'toa', got {kind!r}")

    fig, ax_a = plt.subplots(1, 1, figsize=(11, 5))
    pos_color = NCAR_COLORS["ncar_blue"]
    neg_color = NCAR_COLORS["orange"]
    ceres_color = NCAR_COLORS["red"]
    merra2_color = "0.25"  # dark gray — clean against the blue/orange fills

    # Both records get an anomaly fill in the same blue/orange palette at
    # low alpha. Where they agree on sign at a given month the two fills
    # stack and alpha-composite to a darker shade — that darker overlap
    # *is* the agreement signal, no extra annotation needed. Where they
    # disagree, you get a light orange below zero alongside light blue
    # above (or vice versa) and the eye reads the divergence directly.
    fill_alpha = 0.30
    ax_a.axhline(0, color=NCAR_COLORS["gray"], lw=0.8, zorder=1)
    times = ds["time"].values
    for series, lbl_prefix, line_color, line_lw, line_z in [
        (ceres_sw,  "CERES",   ceres_color,  1.4, 4),
        (merra2_sw, "MERRA-2", merra2_color, 1.0, 3),
    ]:
        if series is None:
            continue
        vals = series.values
        ax_a.fill_between(times, 0, vals, where=vals >= 0,
                          color=pos_color, alpha=fill_alpha,
                          zorder=1, interpolate=True)
        ax_a.fill_between(times, 0, vals, where=vals < 0,
                          color=neg_color, alpha=fill_alpha,
                          zorder=1, interpolate=True)
        ax_a.plot(times, vals, lw=line_lw, color=line_color,
                  zorder=line_z, label=f"{lbl_prefix} ΔF {sky_label}")
    ax_a.set_ylabel(ylabel_anom)
    if kind == "sfc":
        ax_a.invert_yaxis()

    smoke, smoke_label = _smoke_series(ds, smoke_source)
    if smoke is not None:
        # Use CERES for peak markers when present; fall back to MERRA-2.
        sw_for_peaks = ceres_sw if ceres_sw is not None else merra2_sw
        ax_s = _render_smoke_twinx(ax_a, ds, smoke, smoke_label,
                                   sw_for_peaks=sw_for_peaks,
                                   pos_color=pos_color, neg_color=neg_color)
        handles, labels = ax_a.get_legend_handles_labels()
        h2, l2 = ax_s.get_legend_handles_labels()
        ax_a.legend(handles + h2, labels + l2, fontsize=8, loc="upper left")
    else:
        ax_a.legend(fontsize=8, loc="upper left")

    ax_a.set_xlabel("Year")
    _apply_date_range(ax_a)
    fig.suptitle(
        f"CERES vs MERRA-2 SW {title_tag} {sky_label} Anomaly — {_region_label(ds)}"
    )
    fig.tight_layout()
    save_figure(fig, output)


def plot_region_map(output, regions=None) -> None:
    """Global PlateCarree map with all FIREX region boxes.

    Featured regions (the story arc) are filled semi-transparent orange
    with a label; the rest are drawn as thin dark-grey outlines with a
    smaller label, marking them as future-analysis candidates.
    """
    from firex.regions import REGIONS
    if regions is None:
        regions = REGIONS

    fig = plt.figure(figsize=(14, 6.8))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_global()
    ax.coastlines(linewidth=0.4, color="0.4")
    ax.add_feature(cfeature.LAND, facecolor="0.96", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="white", zorder=0)
    ax.gridlines(draw_labels=False, linewidth=0.3, color="0.85", zorder=1)

    featured_color = NCAR_COLORS["orange"]
    for r in regions.values():
        lons = [r.lon_min, r.lon_max, r.lon_max, r.lon_min, r.lon_min]
        lats = [r.lat_min, r.lat_min, r.lat_max, r.lat_max, r.lat_min]
        if r.featured:
            ax.fill(lons, lats, color=featured_color, alpha=0.35,
                    transform=ccrs.PlateCarree(), zorder=3)
            ax.plot(lons, lats, color=featured_color, lw=1.5,
                    transform=ccrs.PlateCarree(), zorder=4)
            ax.text(
                (r.lon_min + r.lon_max) / 2, (r.lat_min + r.lat_max) / 2,
                r.name.replace("-", " ").title(),
                transform=ccrs.PlateCarree(),
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="0.1", zorder=5,
            )
        else:
            ax.plot(lons, lats, color="0.35", lw=0.9, linestyle="-",
                    transform=ccrs.PlateCarree(), zorder=2)
            label = r.name.replace("-", " ").title().replace(" Se ", " SE ")
            ax.text(
                (r.lon_min + r.lon_max) / 2, (r.lat_min + r.lat_max) / 2,
                label,
                transform=ccrs.PlateCarree(),
                ha="center", va="center", fontsize=7, color="0.25", zorder=2,
            )

    fig.suptitle("FIREX Regions")
    fig.tight_layout()
    save_figure(fig, output)


def plot_smoke_radiative_efficiency(ds: xr.Dataset, output) -> None:
    """1×2 clear-sky scatter: smoke AOD vs ΔF at SFC SW↓ and TOA SW.

    Each panel shows OLS slope β (W m⁻² per AOD), standard error, n, R².
    The same top-N peak smoke months from the timeseries plots are
    labeled (4 for PNW, 5 for EAU)."""
    smoke_cols = [c for c in
                  ("smoke_aod_terra","smoke_aod_aqua",
                   "smoke_aod_snpp","smoke_aod_noaa20") if c in ds]
    if not smoke_cols:
        return
    smoke_da = xr.concat([ds[c] for c in smoke_cols], dim="src").mean("src")
    smoke = smoke_da.values.astype(float)
    times = pd.DatetimeIndex(smoke_da["time"].values)

    panels = [
        ("ceres_sfc_sw_down_clr_anom", "ΔF$_{SFC,SW↓}$ Clear-Sky"),
        ("ceres_toa_sw_clr_anom",      "ΔF$_{TOA,SW}$ Clear-Sky"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))

    top_n = 5 if ds.attrs.get("region") == "eastern-australia" else 4
    peak_idx = (
        pd.DataFrame({"time": times, "smoke": smoke})
        .dropna(subset=["smoke"]).nlargest(top_n, "smoke").index.tolist()
    )

    for ax, (y_var, label) in zip(axes, panels):
        if y_var not in ds:
            ax.set_visible(False)
            continue
        y = ds[y_var].values.astype(float)
        valid = np.isfinite(smoke) & np.isfinite(y)
        x_v, y_v = smoke[valid], y[valid]
        ax.scatter(x_v, y_v, s=14, alpha=0.5, color="black", zorder=2)
        if x_v.size >= 3 and x_v.var() > 0:
            slope, intercept = np.polyfit(x_v, y_v, 1)
            yhat = slope * x_v + intercept
            resid = y_v - yhat
            sxx = ((x_v - x_v.mean()) ** 2).sum()
            se = float(np.sqrt((resid ** 2).sum() / (x_v.size - 2) / sxx))
            r2 = float(1 - (resid ** 2).sum() / ((y_v - y_v.mean()) ** 2).sum())
            xs = np.linspace(0, x_v.max(), 50)
            ax.plot(xs, slope * xs + intercept, color="black", lw=1.4, zorder=3)
            ax.text(
                0.05, 0.05,
                f"β = {slope:.1f} ± {se:.1f} W m⁻²/AOD\nR² = {r2:.2f}\nn = {x_v.size}",
                transform=ax.transAxes, va="bottom", fontsize=9,
                bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
            )
        # Label peak months. When two peaks share a similar y, stagger
        # the labels above/below so they don't stack on the same line.
        peak_xy = [(i, smoke[i], y[i]) for i in peak_idx
                   if np.isfinite(smoke[i]) and np.isfinite(y[i])]
        if peak_xy:
            ymin, ymax = ax.get_ylim()
            yrange = ymax - ymin if ymax > ymin else 1.0
            threshold = 0.06 * yrange
            order = sorted(range(len(peak_xy)), key=lambda k: peak_xy[k][2])
            dy = [0] * len(peak_xy)
            for rank in range(1, len(order)):
                prev = order[rank - 1]
                cur = order[rank]
                if abs(peak_xy[cur][2] - peak_xy[prev][2]) < threshold:
                    dy[cur] = -dy[prev] if dy[prev] != 0 else 9
                else:
                    dy[cur] = 0
            for k, (i, xi, yi) in enumerate(peak_xy):
                ax.annotate(
                    pd.Timestamp(times[i]).strftime("%b %Y"),
                    xy=(xi, yi),
                    xytext=(7, dy[k]), textcoords="offset points",
                    ha="left", va="center", fontsize=9, color="black",
                    zorder=5,
                )
        ax.axhline(0, color="0.6", lw=0.5, zorder=1)
        ax.set_xlabel("Smoke AOD 550 nm")
        ax.set_ylabel(f"{label} (W m⁻²)")

    fig.suptitle(f"Smoke Radiative Efficiency — {_region_label(ds)}")
    fig.tight_layout()
    save_figure(fig, output)


def plot_smoke_radiative_efficiency_tertiles(ds: xr.Dataset, output) -> None:
    """1×2 clear-sky scatter (SFC, TOA) of smoke AOD vs ΔF, with points
    color-coded by QFED-OC tertile and separate OLS slopes per tertile.

    Visualizes the within-record variation of β with fire intensity:
    saturation would flatten the slope at high QFED; "cleaner smoke
    fraction" steepens it. PNW shows the latter (β_high ≈ −44 vs all-
    record −39); EAU's low/mid slopes are unstable due to narrow AOD
    range and should be read as cautionary, not interpretive.
    """
    ds = _mask_bad_qfed(ds)
    smoke_cols = [c for c in
                  ("smoke_aod_terra","smoke_aod_aqua",
                   "smoke_aod_snpp","smoke_aod_noaa20") if c in ds]
    if not smoke_cols or "qfed_oc" not in ds:
        return
    smoke_da = xr.concat([ds[c] for c in smoke_cols], dim="src").mean("src")
    smoke = smoke_da.values.astype(float)
    qfed = ds["qfed_oc"].values.astype(float)

    panels = [
        ("ceres_sfc_sw_down_clr_anom", "ΔF$_{SFC,SW↓}$ Clear-Sky"),
        ("ceres_toa_sw_clr_anom",      "ΔF$_{TOA,SW}$ Clear-Sky"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))

    tertiles = [
        ("Low",  NCAR_COLORS["aqua"],      "--", 1.1),
        ("Mid",  NCAR_COLORS["ncar_blue"], "-",  1.4),
        ("High", NCAR_COLORS["red"],       "-",  2.0),
    ]

    for ax, (y_var, label) in zip(axes, panels):
        if y_var not in ds:
            ax.set_visible(False)
            continue
        y = ds[y_var].values.astype(float)
        valid = np.isfinite(smoke) & np.isfinite(y) & np.isfinite(qfed)
        s, yy, q = smoke[valid], y[valid], qfed[valid]
        if s.size < 30:
            continue
        q_lo, q_hi = np.percentile(q, [33.33, 66.67])
        bins = [
            ("Low",  q < q_lo),
            ("Mid",  (q >= q_lo) & (q < q_hi)),
            ("High", q >= q_hi),
        ]
        legend_lines = []
        for (name, color, linestyle, lw), (_, mask) in zip(tertiles, bins):
            xs, ys = s[mask], yy[mask]
            ax.scatter(xs, ys, s=14, alpha=0.55, color=color, zorder=2)
            if xs.size < 5 or xs.var() < 1e-12:
                continue
            slope, intercept = np.polyfit(xs, ys, 1)
            yhat = slope * xs + intercept
            r2 = float(1 - ((ys - yhat) ** 2).sum() /
                       ((ys - ys.mean()) ** 2).sum()) if ys.var() > 0 else 0.0
            xline = np.linspace(0, xs.max(), 50)
            ax.plot(xline, slope * xline + intercept,
                    color=color, lw=lw, linestyle=linestyle, zorder=3,
                    label=f"{name}: β={slope:.0f}, R²={r2:.2f}, n={xs.size}")
        ax.axhline(0, color="0.6", lw=0.5, zorder=1)
        ax.set_xlabel("Smoke AOD 550 nm")
        ax.set_ylabel(f"{label} (W m⁻²)")
        ax.legend(fontsize=8, loc="lower left", title="QFED OC tertile",
                  title_fontsize=8)

    fig.suptitle(f"Smoke Radiative Efficiency by QFED Tertile — {_region_label(ds)}")
    fig.tight_layout()
    save_figure(fig, output)


def plot_qfed_daily_bursts(ds: xr.Dataset, output) -> None:
    """Daily QFED OC time series within each top fire month; reads the
    raw daily QFED NetCDFs from `~/Data/QFED/Y{YYYY}/M{MM}/`.

    Shows the within-month concentration that motivates the duty-cycle
    correction in §"Caveat" of FIREX.md. Annotates each panel with
    f_eff = (1/Σpᵢ²) / n_days.
    """
    smoke_cols = [c for c in
                  ("smoke_aod_terra","smoke_aod_aqua",
                   "smoke_aod_snpp","smoke_aod_noaa20") if c in ds]
    if not smoke_cols:
        return
    smoke_da = xr.concat([ds[c] for c in smoke_cols], dim="src").mean("src")
    times = pd.DatetimeIndex(smoke_da["time"].values)
    smoke = smoke_da.values.astype(float)
    top_n = 5 if ds.attrs.get("region") == "eastern-australia" else 4
    # Skip top fire months in Y2017 — local QFED 2017 archive is corrupt
    # (see CLAUDE.md). Keeps the burst panel from rendering empty bars.
    candidates = pd.DataFrame({"time": times, "smoke": smoke}).dropna(subset=["smoke"])
    candidates = candidates[~candidates["time"].dt.year.isin(_QFED_BAD_YEARS)]
    df = candidates.nlargest(top_n, "smoke").sort_values("time")
    if df.empty:
        return

    bbox = ds.attrs.get("bbox", "")
    # Parse bbox attr "lon[a,b] lat[c,d]"
    import re
    m = re.match(r"lon\[([-\d.]+),([-\d.]+)\] lat\[([-\d.]+),([-\d.]+)\]", bbox)
    if not m:
        return
    lon_min, lon_max, lat_min, lat_max = map(float, m.groups())

    qfed_root = Path.home() / "Data" / "QFED"

    n = len(df)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.6), sharey=True)
    if n == 1:
        axes = [axes]
    for ax, (_, row) in zip(axes, df.iterrows()):
        t = pd.Timestamp(row.time)
        files = sorted(
            (qfed_root / f"Y{t.year}" / f"M{t.month:02d}").glob(
                f"qfed2.emis_oc.061.{t.year}{t.month:02d}*.nc4"))
        if not files:
            ax.text(0.5, 0.5, "no QFED daily", ha="center", va="center",
                    transform=ax.transAxes)
            continue
        days, vals = [], []
        for f in files:
            sds = xr.open_dataset(f)
            sub = sds["biomass"].sel(
                lat=slice(lat_min, lat_max), lon=slice(lon_min, lon_max))
            mean = float(sub.weighted(np.cos(np.deg2rad(sub.lat)))
                            .mean(("lat", "lon")).values[0])
            days.append(pd.Timestamp(sds.time.values[0]).floor("D"))
            vals.append(mean)
        s = pd.Series(vals, index=days)
        # f_eff
        total = s.sum()
        if total > 0:
            p = s / total
            H = (p ** 2).sum()
            f_eff = (1 / H) / len(s)
        else:
            f_eff = float("nan")
        ax.bar(s.index, s.values, color=NCAR_COLORS["orange"],
               edgecolor="0.3", lw=0.4, width=0.85)
        ax.set_title(t.strftime("%b %Y"), fontsize=10)
        ax.set_xlabel("Day")
        ax.text(0.97, 0.95, f"f_eff = {f_eff:.2f}",
                transform=ax.transAxes, ha="right", va="top", fontsize=9,
                bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"))
        ax.tick_params(axis="x", rotation=30, labelsize=7)
    axes[0].set_ylabel("Daily QFED OC (kg m⁻² s⁻¹)")
    fig.suptitle(f"Daily QFED OC Bursts in Top Fire Months — {_region_label(ds)}")
    fig.tight_layout()
    save_figure(fig, output)


def plot_qfed_vs_smoke_aod_scatter(ds: xr.Dataset, output) -> None:
    """Monthly scatter of QFED OC emission flux vs ensemble-mean smoke AOD.

    Uses black dots/line (instead of the NCAR palette) and labels the
    same top-N peak smoke months as the timeseries plots.
    """
    ds = _mask_bad_qfed(ds)
    smoke_cols = [c for c in
                  ("smoke_aod_terra","smoke_aod_aqua",
                   "smoke_aod_snpp","smoke_aod_noaa20") if c in ds]
    if "qfed_oc" not in ds or not smoke_cols:
        return
    smoke = xr.concat([ds[c] for c in smoke_cols], dim="src").mean("src")
    times = pd.DatetimeIndex(smoke["time"].values)
    x_all = ds["qfed_oc"].values.astype(float)
    y_all = smoke.values.astype(float)
    valid = np.isfinite(x_all) & np.isfinite(y_all)
    x, y = x_all[valid], y_all[valid]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(x, y, s=14, alpha=0.55, color="black", zorder=2)
    if x.size >= 3 and x.var() > 0:
        slope, intercept = np.polyfit(x, y, 1)
        yhat = slope * x + intercept
        resid = y - yhat
        sxx = ((x - x.mean()) ** 2).sum()
        se = float(np.sqrt((resid ** 2).sum() / (x.size - 2) / sxx))
        r2 = float(1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum())
        xs = np.linspace(0, x.max(), 100)
        ax.plot(xs, slope * xs + intercept, color="black", lw=1.4, zorder=3)
        ax.text(
            0.05, 0.95,
            f"β = {slope:.2e} ± {se:.2e}\nn = {x.size}\nR² = {r2:.2f}",
            transform=ax.transAxes, va="top", fontsize=10,
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
        )

    # Mark + label the same peak months as the timeseries plots (top-N
    # smoke-AOD ensemble means; N=5 for EAU, 4 elsewhere).
    top_n = 5 if ds.attrs.get("region") == "eastern-australia" else 4
    peaks = (
        pd.DataFrame({"time": times, "qfed": x_all, "smoke": y_all})
        .dropna(subset=["smoke"])
        .nlargest(top_n, "smoke")
        .sort_values("time")
    )
    if not peaks.empty:
        for _, row in peaks.iterrows():
            label = pd.Timestamp(row.time).strftime("%b %Y")
            ax.annotate(
                label, xy=(row.qfed, row.smoke),
                xytext=(7, 0), textcoords="offset points",
                ha="left", va="center", fontsize=9, color="black", zorder=6,
            )

    ax.set_xlabel("QFED OC (kg m⁻² s⁻¹)")
    ax.set_ylabel("Smoke AOD 550 nm (Ensemble Mean)")
    ax.set_title(f"QFED OC vs Smoke AOD — {_region_label(ds)}")
    fig.tight_layout()
    save_figure(fig, output)


def plot_qfed_smoke_aod(ds: xr.Dataset, output) -> None:
    """2-panel: QFED OC + BC (twinx) on top; total AOD + smoke AOD spreads below."""
    ds = _mask_bad_qfed(ds)
    fig, axes = plt.subplots(
        2, 1, figsize=(11, 8), sharex=True,
        gridspec_kw={"height_ratios": [1, 1.3]},
    )

    # Top: QFED OC. (BC is omitted because QFED's biome-fixed emission
    # factors yield a near-constant OC/BC ratio — BC plots on top of OC
    # under any dual-axis scaling and adds no information.)
    ax_oc = axes[0]
    oc_color = NCAR_COLORS["orange"]
    if "qfed_oc" in ds:
        _plot_annual_bars(ax_oc, ds["qfed_oc"], oc_color)
        ax_oc.plot(ds["time"], ds["qfed_oc"], lw=1.2, color=oc_color,
                   label="QFED OC", zorder=2)
    ax_oc.set_ylabel("QFED OC (kg m⁻² s⁻¹)")
    ax_oc.legend(fontsize=9, loc="upper left")

    # Bottom: total AOD ensemble + spread, smoke AOD ensemble + spread.
    ax = axes[1]
    total_cols = [c for c in
                  ("modis_terra_aod","modis_aqua_aod","viirs_snpp_aod",
                   "viirs_noaa20_aod","merra2_aer_TOTEXTTAU") if c in ds]
    if total_cols:
        total = xr.concat([ds[c] for c in total_cols], dim="src")
        ax.fill_between(ds["time"], total.min("src"), total.max("src"),
                        color=NCAR_COLORS["aqua"], alpha=0.25, zorder=1,
                        label="Total AOD Spread")
        ax.plot(ds["time"], total.mean("src"), lw=1.4,
                color=NCAR_COLORS["ncar_blue"], zorder=3,
                label="Total AOD Ensemble")
    smoke_cols = [c for c in
                  ("smoke_aod_terra","smoke_aod_aqua",
                   "smoke_aod_snpp","smoke_aod_noaa20") if c in ds]
    if smoke_cols:
        smoke = xr.concat([ds[c] for c in smoke_cols], dim="src")
        ax.fill_between(ds["time"], smoke.min("src"), smoke.max("src"),
                        color="0.65", alpha=0.4, zorder=2,
                        label="Smoke AOD Spread")
        ax.plot(ds["time"], smoke.mean("src"), lw=1.4, color="black",
                zorder=4, label="Smoke AOD Ensemble")
    ax.set_ylabel("AOD 550 nm")
    ax.legend(fontsize=9, loc="upper left", ncol=2)
    ax.set_xlabel("Year")
    _apply_date_range(ax)

    fig.suptitle(f"QFED Emissions and Total / Smoke AOD — {_region_label(ds)}")
    fig.tight_layout()
    save_figure(fig, output)


def plot_aod_sfc(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="sfc", output=output, sky="clr")


def plot_aod_toa(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="toa", output=output, sky="clr")


def plot_aod_sfc_all(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="sfc", output=output, sky="all")


def plot_aod_toa_all(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="toa", output=output, sky="all")


# MERRA-2 analogues. Single-panel: SW anomaly + MERRA-2-internal smoke AOD
# on twinx. Reads the MERRA-2 rad fluxes (SWGDN[CLR] at SFC, −SWTNT[CLR]
# at TOA — sign-aligned with CERES outgoing convention by `_sw_anom_series`)
# and pairs them with smoke_aod_merra2, so flux and smoke come from the
# same model. The total-AOD timeseries is omitted; refer to the dedicated
# AOD plots for that view.
def plot_aod_sfc_merra2(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="sfc", output=output, sky="clr",
                      flux_source="merra2", smoke_source="merra2",
                      show_aod_panel=False)


def plot_aod_toa_merra2(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="toa", output=output, sky="clr",
                      flux_source="merra2", smoke_source="merra2",
                      show_aod_panel=False)


def plot_aod_sfc_all_merra2(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="sfc", output=output, sky="all",
                      flux_source="merra2", smoke_source="merra2",
                      show_aod_panel=False)


def plot_aod_toa_all_merra2(ds: xr.Dataset, output) -> None:
    _plot_aod_sw_pair(ds, kind="toa", output=output, sky="all",
                      flux_source="merra2", smoke_source="merra2",
                      show_aod_panel=False)


# CERES vs MERRA-2 ΔF on a single panel. Useful as an obs-vs-model
# diagnostic — same units, same sign convention; gaps between the two
# lines flag radiative-transfer disagreements (clouds, surface albedo,
# aerosol mix). Smoke AOD on the twin axis is MERRA-2-internal so the
# model's "what should happen" reading is self-consistent.
def plot_dF_sfc_compare(ds: xr.Dataset, output) -> None:
    _plot_dF_compare(ds, kind="sfc", output=output, sky="clr")


def plot_dF_toa_compare(ds: xr.Dataset, output) -> None:
    _plot_dF_compare(ds, kind="toa", output=output, sky="clr")


def plot_dF_sfc_all_compare(ds: xr.Dataset, output) -> None:
    _plot_dF_compare(ds, kind="sfc", output=output, sky="all")


def plot_dF_toa_all_compare(ds: xr.Dataset, output) -> None:
    _plot_dF_compare(ds, kind="toa", output=output, sky="all")


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
    ax.set_title(f"Seasonal Climatology — {_region_label(ds)}")
    ax.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_qfed_emissions_timeseries(ds: xr.Dataset, output) -> None:
    ds = _mask_bad_qfed(ds)
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
            ax2.set_ylabel("Smoke AOD", color=aod_color)
        ax.legend(loc="upper left", fontsize=9)
    axes[-1].set_xlabel("Year")
    _apply_date_range(axes[-1])
    fig.suptitle(f"QFED Biomass-Burning Emissions — {_region_label(ds)}")
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_cloud_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    color = NCAR_COLORS["ncar_blue"]
    _plot_annual_bars(ax, ds["ceres_cloud_fraction"], color)
    ax.plot(ds["time"], ds["ceres_cloud_fraction"], lw=1.2, color=color, zorder=2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Cloud Fraction")
    ax.set_title(f"CERES Total-Column Cloud Fraction — {_region_label(ds)}")
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
    _scatter_with_ols(axes[0], smoke, ds[clr_var].values, "Clear-Sky")
    _scatter_with_ols(axes[1], smoke, ds[all_var].values, "All-Sky")
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
        ax.set_ylabel("MODIS Terra (Site Gridcell)")
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
    axes[0].set_title("Magnitude Comparison")
    ratio = ds["merra2_aer_TOTEXTTAU"] / ds["modis_terra_aod"]
    axes[1].plot(ds["time"], ratio, lw=1.0)
    axes[1].set_xlabel("Year")
    axes[1].set_ylabel("MERRA-2 / MODIS")
    axes[1].set_title("Scaling-Factor Time Series")
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
    fig.suptitle(f"Spatial Fields: Climatology vs. {peak_year} Anomaly")
    save_figure(fig, output)
