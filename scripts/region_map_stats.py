"""Annotated region map + RESULTS.md with per-region key statistics.

For each region, compute from `output/<region>/data/merged.nc`:
  - η_SFC and η_TOA: OLS slopes of clear-sky SW anomalies on ensemble-
    mean smoke AOD (W m⁻² per AOD), with 1σ standard error, computed
    independently from CERES EBAF (`ceres_*_clr_anom`) and from MERRA-2
    rad (`merra2_rad_SW{GDN,TNT}CLR_anom`). MERRA-2 SWTNT is net-down
    at TOA, so we flip its sign to share CERES outgoing convention:
    +ΔF_TOA = more outgoing SW = cooling.
  - peak smoke AOD and the year it occurred
  - count of months with smoke AOD ≥ 50% of peak

Render a global PlateCarree map with all region boxes drawn equally
(no orange highlight) and a stats block placed near each box.
Per-region placement nudges live in `LAYOUT` below — edit there when
the region set or layout changes.

Outputs:
  - `output/region_map_stats.{png,pdf}` — annotated map
  - `RESULTS.md` (repo root) — summary table, git-tracked

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

# (label, response variable, sign multiplier).
# MERRA-2 SWTNT* is net-down (positive into earth); CERES TOA SW is
# upward outgoing (positive cooling). Flip the MERRA-2 TOA response
# so the η_TOA columns are directly comparable across both records.
RESPONSES = (
    ("eta_sfc_ceres",  "ceres_sfc_sw_down_clr_anom", +1),
    ("eta_sfc_merra2", "merra2_rad_SWGDNCLR_anom",   +1),
    ("eta_toa_ceres",  "ceres_toa_sw_clr_anom",      +1),
    ("eta_toa_merra2", "merra2_rad_SWTNTCLR_anom",   -1),
)

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


def _ols_slope_se(x: np.ndarray, y: np.ndarray) -> tuple[float, float] | None:
    """OLS slope + 1σ standard error on a single predictor. None if
    underdetermined (n < 3 or zero variance in x)."""
    if x.size < 3 or x.var() == 0:
        return None
    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    resid = y - yhat
    sxx = ((x - x.mean()) ** 2).sum()
    se = float(np.sqrt((resid ** 2).sum() / (x.size - 2) / sxx))
    return float(slope), se


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

    out: dict = {
        "peak_aod": peak_aod, "peak_year": peak_year,
        "n_near_peak": n_near_peak,
    }
    for key, y_var, sign in RESPONSES:
        if y_var not in ds:
            out[key] = None
            continue
        y = sign * ds[y_var].values.astype(float)
        v2 = valid & np.isfinite(y)
        fit = _ols_slope_se(smoke[v2], y[v2])
        out[key] = fit  # (slope, se) or None
    return out


def _fmt_eta_pair(ceres, merra2) -> str:
    """Format a 'Z±W / Z±W' string (CERES / M2 by position; legend on figure)."""
    parts = []
    for fit in (ceres, merra2):
        parts.append("n/a" if fit is None else f"{fit[0]:+.1f}±{fit[1]:.1f}")
    return " / ".join(parts)


def fmt_block(stats: dict | None) -> str:
    """Map block: SFC efficiency only (TOA stays in RESULTS.md)."""
    if stats is None:
        return "no data"
    sfc = _fmt_eta_pair(stats["eta_sfc_ceres"], stats["eta_sfc_merra2"])
    return (
        f"η$_{{SFC}}$: {sfc}\n"
        f"τ$_{{peak}}$ {stats['peak_aod']:.2f} ({stats['peak_year']})  "
        f"n≥50%: {stats['n_near_peak']}"
    )


def _md_eta(fit) -> str:
    if fit is None:
        return "n/a"
    return f"{fit[0]:+.1f} ± {fit[1]:.1f}"


def write_results_md(region_stats: dict, out_path: Path) -> None:
    """Emit a git-trackable summary table mirroring the map's stats."""
    # Featured first (preserving REGIONS order), then the rest.
    ordered = [n for n, r in REGIONS.items() if r.featured] + \
              [n for n, r in REGIONS.items() if not r.featured]

    lines: list[str] = []
    lines.append("# FIREX Results Summary")
    lines.append("")
    lines.append(
        "Regional smoke radiative-efficiency and AOD statistics, computed from "
        "`output/<region>/data/merged.nc` over the CERES record (2000-03 → present)."
    )
    lines.append(
        "Featured regions (★) form the current presentation arc; the remaining "
        "regions are defined for future analysis."
    )
    lines.append("")
    lines.append(
        "Efficiency η is the OLS slope of the clear-sky SW anomaly on the "
        "ensemble-mean smoke AOD (mean of MODIS Terra/Aqua + VIIRS SNPP/NOAA-20 "
        "smoke AODs), in W m⁻² per unit AOD, with 1σ standard error. Both CERES "
        "EBAF and MERRA-2 rad fluxes are reported. MERRA-2 SWTNT (net-down) is "
        "negated so SFC and TOA share the CERES outgoing convention: "
        "+ΔF$_{TOA}$ = more outgoing SW = cooling, −ΔF$_{SFC}$ = surface dimming."
    )
    lines.append("")
    lines.append(
        "This file is auto-generated by `scripts/region_map_stats.py` — "
        "do not hand-edit. Re-run the script after refreshing merged.nc."
    )
    lines.append("")
    lines.append(
        "| Region | Peak τ$_{smoke}$ (year) | n ≥ 50% peak | "
        "η$_{SFC}$ CERES | η$_{SFC}$ MERRA-2 | "
        "η$_{TOA}$ CERES | η$_{TOA}$ MERRA-2 |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|"
    )
    for name in ordered:
        r = REGIONS[name]
        s = region_stats.get(name)
        label = name.replace("-", " ").title()
        if r.featured:
            label += " ★"
        if s is None:
            lines.append(f"| {label} | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {label} "
            f"| {s['peak_aod']:.2f} ({s['peak_year']}) "
            f"| {s['n_near_peak']} "
            f"| {_md_eta(s['eta_sfc_ceres'])} "
            f"| {_md_eta(s['eta_sfc_merra2'])} "
            f"| {_md_eta(s['eta_toa_ceres'])} "
            f"| {_md_eta(s['eta_toa_merra2'])} |"
        )
    lines.append("")
    out_path.write_text("\n".join(lines))


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

    # Single global legend explaining the η_SFC number ordering. Avoids
    # repeating "CERES / M2" inside every per-region block.
    ax.text(
        0.005, 0.012,
        "η$_{SFC}$ values: CERES / MERRA-2  (W m⁻² per unit AOD; clear-sky)",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=9,
        color="0.15",
        bbox=dict(facecolor="white", alpha=0.92,
                  edgecolor="0.55", lw=0.5, pad=3.0),
        zorder=5,
    )

    fig.suptitle(
        "FIREX Regions — Smoke Radiative Efficiency & AOD Statistics",
        fontsize=12,
    )
    fig.tight_layout()
    out = output_root / "region_map_stats.png"
    plots.save_figure(fig, out)
    print(f"wrote {out} (and .pdf)")

    md_path = Path(__file__).resolve().parents[1] / "RESULTS.md"
    write_results_md(region_stats, md_path)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
