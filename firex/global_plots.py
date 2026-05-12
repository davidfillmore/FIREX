"""Global spatial-pattern plots for the FIREX presentation set.

Three figure builders:

- `plot_smoke_aod_seasonal`     — 2×2 DJF/MAM/JJA/SON climatology of
                                  MERRA-2 smoke AOD (BCEXTTAU + OCEXTTAU).
- `plot_smoke_radiative_effect` — 1×2 TOA/SFC mean radiative effect from
                                  smoke, per-cell regression slope × the
                                  climatological smoke AOD.
- `plot_event_anomaly`          — 2×2 panels (smoke AOD, total AOD,
                                  ΔF_TOA, ΔF_SFC) for one event year/
                                  season vs. the rest-of-record climatology.

All three use the cached on-disk dataset from `build_global_dataset()`:
MERRA-2 aer_Nx interpolated to the CERES 1° grid + CERES EBAF clear-sky
fluxes, aligned on the inner time range.
"""
from __future__ import annotations

from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from firex.plots import NCAR_COLORS, save_figure
from firex.regions import REGIONS


# ── Paths ─────────────────────────────────────────────────────────────
MERRA2_AER_DIR = Path.home() / "Data" / "MERRA2_tavgM" / "aer_Nx"
CERES_FILE = Path.home() / "Data" / "CERES_EBAF" / "ceres" / \
    "CERES_EBAF_Edition4.2.1_200003-202512.nc"
CACHE_FILE = Path.home() / "FIREX" / "output" / "global" / "data" / \
    "global_monthly.nc"


# ── Dataset assembly ──────────────────────────────────────────────────

def _open_merra2_smoke_total(time_range: tuple[str, str]) -> xr.Dataset:
    """Open all aer_Nx monthly files in `time_range` (inclusive YYYY-MM).

    Returns Dataset with `smoke_aod` and `total_aod` on the native MERRA-2
    grid. Uses dask chunking so the full record fits comfortably in memory.
    """
    files = sorted(MERRA2_AER_DIR.glob("MERRA2_*.tavgM_2d_aer_Nx.*.nc4"))
    if not files:
        raise FileNotFoundError(f"no MERRA-2 aer_Nx files under {MERRA2_AER_DIR}")
    ds = xr.open_mfdataset(
        files,
        combine="by_coords",
        data_vars=["BCEXTTAU", "OCEXTTAU", "TOTEXTTAU"],
        chunks={"time": 12},
    )
    ds = ds.sel(time=slice(*time_range))
    smoke = (ds["BCEXTTAU"] + ds["OCEXTTAU"]).rename("smoke_aod")
    total = ds["TOTEXTTAU"].rename("total_aod")
    return xr.merge([smoke, total])


def _open_ceres_clr(time_range: tuple[str, str]) -> xr.Dataset:
    """Open CERES EBAF and return clear-sky TOA SW + SFC SW-down."""
    src = xr.open_dataset(CERES_FILE)
    src = src.sel(time=slice(*time_range))
    out = xr.Dataset(
        {
            "toa_sw_clr": src["toa_sw_clr_t_mon"],
            "sfc_sw_down_clr": src["sfc_sw_down_clr_t_mon"],
        }
    )
    # CERES ships lon ∈ [0, 360); MERRA-2 is [-180, 180].
    if float(out["lon"].max()) > 180:
        out = out.assign_coords(
            lon=(((out["lon"] + 180) % 360) - 180)
        ).sortby("lon")
    return out


def build_global_dataset(rebuild: bool = False) -> xr.Dataset:
    """Assemble + cache the aligned monthly dataset on the CERES 1° grid.

    First call writes `CACHE_FILE` (~600 MB). Subsequent calls just open
    it. Pass `rebuild=True` to overwrite the cache.
    """
    if CACHE_FILE.exists() and not rebuild:
        return xr.open_dataset(CACHE_FILE).load()

    # CERES anchors the time + space grid; align MERRA-2 to it.
    ceres_full = xr.open_dataset(CERES_FILE)
    t0 = str(ceres_full.time.values[0])[:7]
    t1 = str(ceres_full.time.values[-1])[:7]

    ceres = _open_ceres_clr((t0, t1))
    merra = _open_merra2_smoke_total((t0, t1))

    # Interpolate MERRA-2 to the CERES grid; nearest-neighbor on time
    # (both monthly, the date-of-month differs: CERES uses mid-month
    # 15th, MERRA-2 uses month-end).
    merra_on_ceres = merra.interp(
        lat=ceres["lat"], lon=ceres["lon"], method="linear"
    )
    # Align by month/year regardless of day-of-month.
    merra_monthly = merra_on_ceres.assign_coords(
        time=merra_on_ceres["time"].dt.strftime("%Y-%m")
    )
    ceres_monthly = ceres.assign_coords(
        time=ceres["time"].dt.strftime("%Y-%m")
    )
    common = sorted(set(merra_monthly["time"].values) &
                    set(ceres_monthly["time"].values))
    merra_monthly = merra_monthly.sel(time=common)
    ceres_monthly = ceres_monthly.sel(time=common)
    # Restore a proper datetime axis for downstream groupby("time.season").
    time_dt = xr.DataArray(
        np.array(common, dtype="datetime64[M]").astype("datetime64[ns]"),
        dims="time",
    )
    out = xr.merge([merra_monthly, ceres_monthly]).assign_coords(time=time_dt)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp.nc")
    out.load().to_netcdf(tmp)
    tmp.rename(CACHE_FILE)
    return xr.open_dataset(CACHE_FILE).load()


# ── Map helpers ───────────────────────────────────────────────────────

def _add_base_features(ax, gridlines: bool = True) -> None:
    ax.coastlines(linewidth=0.4, color="0.3")
    ax.add_feature(cfeature.BORDERS.with_scale("110m"),
                   linewidth=0.2, color="0.5")
    if gridlines:
        ax.gridlines(draw_labels=False, linewidth=0.25, color="0.85")


def _draw_featured_boxes(ax, color: str | None = None,
                         linewidth: float = 1.2) -> None:
    """Outline the four featured-region bboxes on a map."""
    c = color or NCAR_COLORS["orange"]
    for r in REGIONS.values():
        if not r.featured:
            continue
        lons = [r.lon_min, r.lon_max, r.lon_max, r.lon_min, r.lon_min]
        lats = [r.lat_min, r.lat_min, r.lat_max, r.lat_max, r.lat_min]
        ax.plot(lons, lats, color=c, lw=linewidth,
                transform=ccrs.PlateCarree(), zorder=5)


# ── Generic seasonal-panel helpers ─────────────────────────────────────

SEASONS = ("DJF", "MAM", "JJA", "SON")

# Discrete log-spaced bin boundaries for smoke-AOD climatology maps.
# Resolves both central-African burning peak (~0.3–0.5) and the global
# background (~0.005–0.02) on the same colorbar.
SMOKE_AOD_LEVELS = [
    0.002, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.06,
    0.08, 0.10, 0.15, 0.20, 0.30, 0.50, 0.70, 1.0,
]


def smoke_aod_norm():
    """BoundaryNorm matching `SMOKE_AOD_LEVELS`, both ends extended."""
    from matplotlib.colors import BoundaryNorm
    return BoundaryNorm(SMOKE_AOD_LEVELS, ncolors=256, extend="both")


def _seasonal_mean(da: xr.DataArray, period: tuple[str, str] | None
                   ) -> xr.DataArray:
    """Mean by climatological season, restricted to `period` if given.

    `period` is (start, end) in `YYYY-MM` form, inclusive of both ends.
    Returns DataArray with `season` dim ordered DJF, MAM, JJA, SON.
    """
    if period is not None:
        da = da.sel(time=slice(*period))
    out = da.groupby("time.season").mean("time")
    return out.sel(season=list(SEASONS))


def _seasonal_panel_figure(
    field: xr.DataArray, title: str, cmap: str,
    vmin: float, vmax: float, cbar_label: str, output: Path,
    diverging: bool = False, gridlines: bool = True,
    region_boxes: bool = True,
    seasons: tuple[str, ...] = SEASONS,
    invert_cbar: bool = False,
    norm=None,
) -> None:
    """Render a Robinson panel grid of seasonal fields.

    `seasons` controls which seasons appear. Default is all four (2×2);
    pass e.g. ("JJA",) for a single-panel figure.
    """
    proj = ccrs.Robinson(central_longitude=0)
    if len(seasons) == 1:
        fig, ax = plt.subplots(figsize=(12, 6),
                               subplot_kw={"projection": proj})
        axes = np.array([ax])
    else:
        fig, axes = plt.subplots(
            2, 2, figsize=(14, 7.5), subplot_kw={"projection": proj},
        )
        axes = axes.flat

    mesh = None
    pcm_kwargs = (
        {"norm": norm} if norm is not None
        else {"vmin": vmin, "vmax": vmax}
    )
    for ax, season in zip(axes, seasons):
        f = field.sel(season=season)
        ax.set_global()
        _add_base_features(ax, gridlines=gridlines)
        mesh = ax.pcolormesh(
            f["lon"], f["lat"], f,
            cmap=cmap, **pcm_kwargs,
            shading="auto", transform=ccrs.PlateCarree(),
            rasterized=True,
        )
        if region_boxes:
            box_color = "black" if diverging else NCAR_COLORS["orange"]
            _draw_featured_boxes(ax, color=box_color, linewidth=1.0)
        if len(seasons) > 1:
            ax.set_title(season, fontsize=12)

    if len(seasons) == 1:
        fig.subplots_adjust(right=0.88)
        cax = fig.add_axes([0.90, 0.18, 0.018, 0.64])
    else:
        fig.subplots_adjust(right=0.92, wspace=0.05, hspace=0.05)
        cax = fig.add_axes([0.94, 0.18, 0.014, 0.64])
    cbar = fig.colorbar(mesh, cax=cax)
    cbar.set_label(cbar_label)
    if invert_cbar:
        cbar.ax.invert_yaxis()

    fig.suptitle(title, fontsize=14, color=NCAR_COLORS["space"])
    save_figure(fig, output)


def plot_seasonal_climatology(
    ds: xr.Dataset, var: str, output: Path,
    *, period: tuple[str, str] | None = None,
    cmap: str = "YlOrRd", vmin: float = 0.0, vmax: float = 0.30,
    cbar_label: str = "", title: str | None = None,
    gridlines: bool = True, region_boxes: bool = True,
    seasons: tuple[str, ...] = SEASONS,
    norm=None,
) -> None:
    """Seasonal-climatology of a single field, optionally restricted to `period`.

    `seasons` picks which to render (single-panel if length 1).
    `norm` (matplotlib Normalize, e.g. BoundaryNorm or LogNorm) overrides
    vmin/vmax for non-uniform scales.
    """
    field = _seasonal_mean(ds[var], period)
    if title is None:
        suffix = f", {period[0][:4]}–{period[1][:4]}" if period else ""
        title = f"{var} — Seasonal Climatology{suffix}"
    _seasonal_panel_figure(field, title, cmap, vmin, vmax, cbar_label, output,
                           gridlines=gridlines, region_boxes=region_boxes,
                           seasons=seasons, norm=norm)


def plot_seasonal_anomaly(
    ds: xr.Dataset, var: str, output: Path,
    *, baseline: tuple[str, str], target: tuple[str, str],
    cmap: str = "RdBu_r", lim: float = 1.0,
    cbar_label: str = "", title: str | None = None,
    gridlines: bool = True, region_boxes: bool = True,
    seasons: tuple[str, ...] = SEASONS,
    sign: float = 1.0,
    invert_cbar: bool = False,
) -> None:
    """Seasonal-mean anomaly: target − baseline.

    `seasons` picks which to render (single-panel if length 1).
    `sign` multiplies the anomaly — set to -1 to flip direction (e.g.
    plot surface SW dimming as positive so warm colours mark fire-impact
    cells, matching the smoke-AOD anomaly convention).
    """
    base = _seasonal_mean(ds[var], baseline)
    targ = _seasonal_mean(ds[var], target)
    field = sign * (targ - base)
    if title is None:
        title = (f"{var} — Seasonal Anomaly "
                 f"({target[0][:4]}–{target[1][:4]} minus "
                 f"{baseline[0][:4]}–{baseline[1][:4]})")
    _seasonal_panel_figure(field, title, cmap, -lim, lim, cbar_label, output,
                           diverging=True,
                           gridlines=gridlines, region_boxes=region_boxes,
                           seasons=seasons, invert_cbar=invert_cbar)


# ── Figure 1: seasonal smoke-AOD climatology (2×2) ─────────────────────


def plot_smoke_aod_seasonal(ds: xr.Dataset, output: Path,
                            vmax: float = 0.30) -> None:
    """2×2 Robinson panels: DJF / MAM / JJA / SON smoke-AOD climatology.

    Featured-region boxes overlaid. cmap YlOrRd, vmin 0, vmax `vmax`
    (default 0.30 — chosen so persistent biomass-burning regions saturate
    but the global background remains readable).
    """
    smoke = ds["smoke_aod"]
    seasonal = smoke.groupby("time.season").mean("time")

    proj = ccrs.Robinson(central_longitude=0)
    fig, axes = plt.subplots(
        2, 2, figsize=(14, 7.5), subplot_kw={"projection": proj},
    )

    mesh = None
    for ax, season in zip(axes.flat, SEASONS):
        field = seasonal.sel(season=season)
        ax.set_global()
        _add_base_features(ax)
        mesh = ax.pcolormesh(
            field["lon"], field["lat"], field,
            cmap="YlOrRd", vmin=0, vmax=vmax,
            shading="auto", transform=ccrs.PlateCarree(),
            rasterized=True,
        )
        _draw_featured_boxes(ax)
        ax.set_title(season, fontsize=12)

    fig.subplots_adjust(right=0.92, wspace=0.05, hspace=0.05)
    cax = fig.add_axes([0.94, 0.18, 0.014, 0.64])
    cbar = fig.colorbar(mesh, cax=cax)
    cbar.set_label("Smoke AOD (BC + OC, 550 nm)")

    yr0 = int(ds["time"].dt.year.values[0])
    yr1 = int(ds["time"].dt.year.values[-1])
    fig.suptitle(
        f"MERRA-2 Smoke AOD — Seasonal Climatology, {yr0}–{yr1}",
        fontsize=14, color=NCAR_COLORS["space"],
    )
    save_figure(fig, output)


# ── Figure 2: mean smoke radiative effect (1×2) ────────────────────────

def _per_cell_slope(y: xr.DataArray, x: xr.DataArray) -> xr.DataArray:
    """β = cov(y, x) / var(x) along the time dimension (already de-meaned)."""
    cov = (x * y).mean("time")
    var = (x * x).mean("time")
    return (cov / var).where(var > 0)


def _per_cell_corr(y: xr.DataArray, x: xr.DataArray) -> xr.DataArray:
    """Pearson r along time (assumes both inputs already de-meaned)."""
    cov = (x * y).mean("time")
    var_x = (x * x).mean("time")
    var_y = (y * y).mean("time")
    denom = np.sqrt(var_x * var_y)
    return (cov / denom).where(denom > 0)


def _seasonal_anomaly(da: xr.DataArray) -> xr.DataArray:
    """Anomaly relative to per-month climatology."""
    clim = da.groupby("time.month").mean("time")
    return da.groupby("time.month") - clim


def plot_smoke_radiative_effect(ds: xr.Dataset, output: Path) -> None:
    """1×2 Robinson panels: TOA and SFC mean radiative effect from smoke.

    Method (per grid cell, monthly anomalies over the CERES record):
      1. smoke_anom = smoke_aod − monthly climatology
         flux_anom  = flux       − monthly climatology
      2. β = slope of flux_anom on smoke_anom  (cov/var)
      3. ΔF = β × <smoke_aod>      (annual-mean climatology of smoke AOD)

    TOA sign convention is flipped so both panels read as "energy added
    to surface / Earth-atmosphere column": negative (blue) ⇒ cooling.
    """
    smoke_anom = _seasonal_anomaly(ds["smoke_aod"])
    toa_anom = _seasonal_anomaly(ds["toa_sw_clr"])   # +outgoing
    sfc_anom = _seasonal_anomaly(ds["sfc_sw_down_clr"])  # +downward

    beta_toa = _per_cell_slope(toa_anom, smoke_anom)
    beta_sfc = _per_cell_slope(sfc_anom, smoke_anom)
    r_toa = _per_cell_corr(toa_anom, smoke_anom)
    r_sfc = _per_cell_corr(sfc_anom, smoke_anom)

    smoke_clim = ds["smoke_aod"].mean("time")
    # Mask cells where the smoke-flux relationship is too weak to trust.
    # |r| < 0.15 catches polar/clean-ocean cells where the slope is
    # dominated by other-aerosol or cloud noise.
    weak_toa = abs(r_toa) < 0.15
    weak_sfc = abs(r_sfc) < 0.15
    dF_toa = (-beta_toa * smoke_clim).where(~weak_toa)  # forcing-sign at TOA
    dF_sfc = (beta_sfc * smoke_clim).where(~weak_sfc)   # surface effect

    proj = ccrs.Robinson(central_longitude=0)
    fig, axes = plt.subplots(
        1, 2, figsize=(15, 5.5), subplot_kw={"projection": proj},
    )

    panels = [
        (axes[0], dF_toa, "TOA SW Clear-Sky", 5.0),
        (axes[1], dF_sfc, "Surface SW Clear-Sky", 10.0),
    ]
    for ax, field, title, lim in panels:
        ax.set_global()
        _add_base_features(ax)
        mesh = ax.pcolormesh(
            field["lon"], field["lat"], field,
            cmap="RdBu_r", vmin=-lim, vmax=lim,
            shading="auto", transform=ccrs.PlateCarree(),
            rasterized=True,
        )
        _draw_featured_boxes(ax, color="black", linewidth=0.9)
        ax.set_title(f"ΔF — {title}", fontsize=12)
        fig.colorbar(mesh, ax=ax, orientation="horizontal",
                     shrink=0.75, pad=0.04, label=r"W m$^{-2}$")

    yr0 = int(ds["time"].dt.year.values[0])
    yr1 = int(ds["time"].dt.year.values[-1])
    fig.suptitle(
        "Smoke-Attributable Mean Radiative Effect "
        f"(slope × mean smoke AOD, {yr0}–{yr1})",
        fontsize=14, color=NCAR_COLORS["space"],
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_figure(fig, output)


# ── Figure 3: event-year anomaly (2×2) ─────────────────────────────────

EVENT_CATALOG: dict[str, dict] = {
    "pnw-2017": {
        "year": 2017, "season": "JJA",
        "region": "pacific-northwest",
        "label": "Pacific Northwest 2017 (JJA)",
    },
    "australia-2019-20": {
        "year": 2019, "season": "DJF",   # DJF 2019-20 lands in CERES Dec-2019/Jan-Feb-2020; we'll handle below
        "region": "eastern-australia",
        "label": "Eastern Australia — Black Summer (Dec 2019 – Feb 2020)",
    },
    "canada-2023": {
        "year": 2023, "season": "JJA",
        "region": "eastern-canada",
        "label": "Eastern Canada 2023 (JJA)",
    },
    "siberia-2019": {
        "year": 2019, "season": "JJA",
        "region": "eastern-siberia",
        "label": "Eastern Siberia 2019 (JJA)",
    },
}


def _event_season_mask(time: xr.DataArray, year: int, season: str) -> xr.DataArray:
    """Boolean mask for one event-year season; DJF spans (year-Dec, year+1-Jan,Feb)."""
    t = time.values.astype("datetime64[M]")
    months = t.astype("datetime64[M]").astype(int) % 12 + 1
    years = t.astype("datetime64[Y]").astype(int) + 1970

    if season == "DJF":
        mask = ((years == year) & (months == 12)) | \
               ((years == year + 1) & ((months == 1) | (months == 2)))
    elif season == "MAM":
        mask = (years == year) & np.isin(months, [3, 4, 5])
    elif season == "JJA":
        mask = (years == year) & np.isin(months, [6, 7, 8])
    elif season == "SON":
        mask = (years == year) & np.isin(months, [9, 10, 11])
    else:
        raise ValueError(f"unknown season {season!r}")
    return xr.DataArray(mask, dims="time", coords={"time": time})


def plot_event_anomaly(ds: xr.Dataset, event_key: str, output: Path) -> None:
    """2×2 PlateCarree panels for one fire-season event.

    Panels (all anomalies vs. same-season rest-of-record climatology):
      smoke AOD | total AOD
      ΔF_TOA SW clear-sky (radiative-forcing sign) | ΔF_SFC SW-down clear-sky
    """
    cfg = EVENT_CATALOG[event_key]
    year, season = cfg["year"], cfg["season"]
    region = REGIONS[cfg["region"]]

    event_mask = _event_season_mask(ds["time"], year, season)
    season_mask = ds["time"].dt.season == season
    if season == "DJF":
        # `time.season=='DJF'` puts Dec/Jan/Feb together regardless of year;
        # OK for the climatology denominator since we exclude event months.
        pass
    baseline_mask = season_mask & ~event_mask
    if int(event_mask.sum()) == 0:
        raise ValueError(f"no months matched event {event_key}")

    def field(var: str) -> xr.DataArray:
        event_mean = ds[var].where(event_mask, drop=True).mean("time")
        clim = ds[var].where(baseline_mask, drop=True).mean("time")
        return event_mean - clim

    smoke_a = field("smoke_aod")
    total_a = field("total_aod")
    # TOA anomaly: outgoing SW. Smoke reflects ⇒ positive anomaly ⇒ cooling.
    # Flip sign so the panel reads as energy added to the column.
    toa_a = -field("toa_sw_clr")
    sfc_a = field("sfc_sw_down_clr")

    proj = ccrs.PlateCarree()
    fig, axes = plt.subplots(
        2, 2, figsize=(14, 8.5), subplot_kw={"projection": proj},
    )

    panels = [
        (axes[0, 0], smoke_a, "Smoke AOD anomaly",
         "PuOr_r", 0.5, r"$\Delta$AOD"),
        (axes[0, 1], total_a, "Total AOD anomaly",
         "PuOr_r", 0.5, r"$\Delta$AOD"),
        (axes[1, 0], toa_a, r"$\Delta F_{TOA,SW}$ clear-sky (forcing sign)",
         "RdBu_r", 30.0, r"W m$^{-2}$"),
        (axes[1, 1], sfc_a, r"$\Delta F_{SFC,SW\downarrow}$ clear-sky",
         "RdBu_r", 30.0, r"W m$^{-2}$"),
    ]
    for ax, field_da, title, cmap, lim, cbar_label in panels:
        ax.set_global()
        _add_base_features(ax)
        mesh = ax.pcolormesh(
            field_da["lon"], field_da["lat"], field_da,
            cmap=cmap, vmin=-lim, vmax=lim,
            shading="auto", transform=ccrs.PlateCarree(),
            rasterized=True,
        )
        # Highlight the event region box in heavy orange.
        lons = [region.lon_min, region.lon_max,
                region.lon_max, region.lon_min, region.lon_min]
        lats = [region.lat_min, region.lat_min,
                region.lat_max, region.lat_max, region.lat_min]
        ax.plot(lons, lats, color=NCAR_COLORS["orange"], lw=1.6,
                transform=ccrs.PlateCarree(), zorder=5)
        ax.set_title(title, fontsize=11)
        fig.colorbar(mesh, ax=ax, orientation="horizontal",
                     shrink=0.75, pad=0.05, label=cbar_label)

    fig.suptitle(
        f"{cfg['label']} — anomaly vs. rest-of-record {season} climatology",
        fontsize=13, color=NCAR_COLORS["space"],
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_figure(fig, output)
