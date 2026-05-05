"""Annotated region map with per-region key statistics.

For each region, compute from `output/<region>/data/merged.nc`:
  - η_SFC: OLS slope of `ceres_sfc_sw_down_clr_anom` on mean smoke AOD
    (W m⁻² per AOD), with 1σ standard error
  - peak smoke AOD and the year it occurred
  - count of months with smoke AOD ≥ 50% of peak

Render a global PlateCarree map with all region boxes drawn equally
(no orange highlight) and a 3-line stats block placed near each box.
Per-region placement nudges live in `LAYOUT` below — edit there when
the region set or layout changes. Output:
`output/region_map_stats.{png,pdf}`.

Invoke from the davinci-monet env (sarb also works — only needs
xarray + cartopy + the davinci_monet style hook):

    conda run -n davinci-monet python scripts/region_map_stats.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Make `firex` importable when launched from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firex import plots  # noqa: E402
from firex.regions import REGIONS  # noqa: E402


SMOKE_SRCS = ("smoke_aod_terra", "smoke_aod_aqua",
              "smoke_aod_snpp", "smoke_aod_noaa20")

# Per-region placement overrides for the stats block. Edit when the
# region set or layout drifts. Default: anchor to the left of the box
# (lon_min − 1.5°, vertical box centre), right-aligned.
LAYOUT = {
    "above": {"alaska", "eastern-canada"},
    "below": {"california"},
    # Extra leftward shift in degrees of longitude (positive = further west).
    "extra_left_shift": {
        "pacific-northwest": 4.0,
        "eastern-australia": 8.0,
        "northern-australia": 8.0,
    },
    # Fine nudges (Δlon, Δlat) from default anchor for left-side blocks.
    "left_nudge": {"pacific-northwest": (0.0, -3.5)},
    # Fine nudges (Δlon, Δlat) from default anchor for below blocks.
    "below_nudge": {"california": (6.0, -3.0)},
}


def compute_stats(ds: xr.Dataset) -> dict | None:
    smoke_cols = [c for c in SMOKE_SRCS if c in ds]
    if not smoke_cols:
        return None
    smoke_da = xr.concat([ds[c] for c in smoke_cols], dim="src").mean("src")
    smoke = smoke_da.values.astype(float)
    times = pd.DatetimeIndex(smoke_da["time"].values)
    valid = np.isfinite(smoke)
    if not valid.any():
        return None

    peak_aod = float(np.nanmax(smoke))
    peak_idx = int(np.nanargmax(smoke))
    peak_year = int(times[peak_idx].year)
    n_near_peak = int(np.sum(smoke[valid] >= 0.5 * peak_aod))

    eta = eta_se = None
    y_var = "ceres_sfc_sw_down_clr_anom"
    if y_var in ds:
        y = ds[y_var].values.astype(float)
        v2 = valid & np.isfinite(y)
        x_v, y_v = smoke[v2], y[v2]
        if x_v.size >= 3 and x_v.var() > 0:
            slope, intercept = np.polyfit(x_v, y_v, 1)
            yhat = slope * x_v + intercept
            resid = y_v - yhat
            sxx = ((x_v - x_v.mean()) ** 2).sum()
            se = float(np.sqrt((resid ** 2).sum() / (x_v.size - 2) / sxx))
            eta, eta_se = float(slope), se
    return {
        "eta": eta, "eta_se": eta_se,
        "peak_aod": peak_aod, "peak_year": peak_year,
        "n_near_peak": n_near_peak,
    }


def fmt_block(stats: dict | None) -> str:
    if stats is None:
        return "no data"
    if stats["eta"] is None:
        eta_line = "η$_{SFC}$: n/a"
    else:
        eta_line = (f"η$_{{SFC}}$ = {stats['eta']:.1f} ± "
                    f"{stats['eta_se']:.1f} W m⁻²/τ")
    return (
        f"{eta_line}\n"
        f"peak τ$_{{smoke}}$ = {stats['peak_aod']:.2f} ({stats['peak_year']})\n"
        f"n ≥ 50% peak: {stats['n_near_peak']}"
    )


def main() -> int:
    plots.setup_style()
    output_root = Path.home() / "FIREX" / "output"

    region_stats: dict[str, dict | None] = {}
    for name in REGIONS:
        merged_path = output_root / name / "data" / "merged.nc"
        if not merged_path.exists():
            region_stats[name] = None
            continue
        with xr.open_dataset(merged_path) as ds:
            ds = ds.load()
        region_stats[name] = compute_stats(ds)

    fig = plt.figure(figsize=(16, 8.5))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_global()
    ax.coastlines(linewidth=0.4, color="0.4")
    ax.add_feature(cfeature.LAND, facecolor="0.96", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="white", zorder=0)
    ax.gridlines(draw_labels=False, linewidth=0.3, color="0.85", zorder=1)

    box_color = "0.25"
    above = LAYOUT["above"]
    below = LAYOUT["below"]
    extra_left_shift = LAYOUT["extra_left_shift"]
    left_nudge = LAYOUT["left_nudge"]
    below_nudge = LAYOUT["below_nudge"]

    for r in REGIONS.values():
        lons = [r.lon_min, r.lon_max, r.lon_max, r.lon_min, r.lon_min]
        lats = [r.lat_min, r.lat_min, r.lat_max, r.lat_max, r.lat_min]
        ax.plot(lons, lats, color=box_color, lw=1.0,
                transform=ccrs.PlateCarree(), zorder=2)

        cx = (r.lon_min + r.lon_max) / 2
        cy = (r.lat_min + r.lat_max) / 2
        ax.text(cx, cy, r.name.replace("-", " ").title(),
                transform=ccrs.PlateCarree(),
                ha="center", va="center",
                fontsize=10, color="0.1", fontweight="bold", zorder=3)

        block = fmt_block(region_stats.get(r.name))
        if r.name in above:
            anchor_x, anchor_y = cx, r.lat_max + 1.5
            ha, va = "center", "bottom"
        elif r.name in below:
            dx, dy = below_nudge.get(r.name, (0.0, 0.0))
            anchor_x = cx + dx
            anchor_y = r.lat_min - 1.5 + dy
            ha, va = "center", "top"
        else:
            shift = 1.5 + extra_left_shift.get(r.name, 0.0)
            dx, dy = left_nudge.get(r.name, (0.0, 0.0))
            anchor_x = r.lon_min - shift + dx
            anchor_y = cy + dy
            ha, va = "right", "center"
        ax.text(anchor_x, anchor_y, block,
                transform=ccrs.PlateCarree(),
                ha=ha, va=va, fontsize=9, color="0.15",
                bbox=dict(facecolor="white", alpha=0.88,
                          edgecolor="0.65", lw=0.4, pad=2.5),
                zorder=4)

    fig.suptitle(
        "FIREX Regions — Smoke Radiative Efficiency & AOD Statistics",
        fontsize=12,
    )
    fig.tight_layout()
    out = output_root / "region_map_stats.png"
    plots.save_figure(fig, out)
    print(f"wrote {out} (and .pdf)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
