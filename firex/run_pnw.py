"""End-to-end runner: 6 stages → tidy NetCDFs + 13 PNGs.

Usage:
    python -m firex.run_pnw --config configs/pacific-northwest.yaml
"""
from __future__ import annotations

import argparse
import datetime
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

import firex
from firex import attribution, anomaly, plots, regression
from firex.loaders import (
    aeronet, ceres_ebaf, merra2_monthly, modis_monthly, qfed_monthly, viirs_monthly,
)
from firex.cache import atomic_to_netcdf, output_is_fresh
from firex.masks import build_mask, save_mask
from firex.regions import REGIONS

logger = logging.getLogger("firex.run_pnw")


def _setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = log_dir / f"run_{stamp}.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stderr))
    root.setLevel(logging.INFO)
    return log_path


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parents[1]
        ).decode().strip()
    except Exception:
        return "unknown"


def _log_header(cfg: dict) -> None:
    logger.info("FIREX run starting")
    logger.info("  firex version: %s", firex.__version__)
    try:
        import davinci_monet
        dm_version = getattr(davinci_monet, "__version__", "unknown")
    except ImportError:
        dm_version = "not-installed"
    logger.info("  davinci_monet version: %s", dm_version)
    logger.info("  git SHA (FIREX): %s", _git_sha())
    logger.info("  region: %s", cfg["region"])
    logger.info("  bbox: %s", cfg["bbox"])
    logger.info("  time: %s → %s", cfg["time"]["start"], cfg["time"]["end"])


def _stage1_mask(cfg: dict, out_dir: Path, force: bool) -> Path:
    out = out_dir / "data" / "mask.nc"
    if not force and output_is_fresh(out, []):
        logger.info("[stage 1] skipped (fresh)")
        return out
    region = REGIONS[cfg["region"]]
    mask = build_mask(region)
    save_mask(mask, out)
    logger.info("[stage 1] wrote %s", out)
    return out


def _glob_files(root: Path, pattern: str) -> list[Path]:
    return sorted(Path(root).expanduser().glob(pattern))


def _to_month_start(ds: xr.Dataset) -> xr.Dataset:
    """Snap the `time` coord to month-start so CERES (mid-month), MERRA-2
    (mid-month + 30 min), and the satellite/QFED/AERONET (already month-start)
    loaders share an aligned monthly axis. Drops duplicate months
    (MODIS C6.1 occasionally has two granules for the same month, e.g.
    reprocessed versions)."""
    if "time" not in ds.coords:
        return ds
    t = pd.DatetimeIndex(ds["time"].values).to_period("M").to_timestamp()
    ds = ds.assign_coords(time=t)
    return ds.drop_duplicates("time", keep="first")


def _stage2_loaders(cfg: dict, out_dir: Path, mask_path: Path, force: bool) -> dict[str, Path]:
    mask = xr.open_dataset(mask_path).load()
    data_dir = out_dir / "data"
    region = REGIONS[cfg["region"]]
    out: dict[str, Path] = {}

    # AERONET first — the resulting site list is passed to gridded loaders so
    # they can emit per-site nearest-gridcell samples alongside the region mean.
    aeronet_root = Path(cfg["paths"]["aeronet"]).expanduser()
    aeronet_files = _glob_files(aeronet_root, "AeroNet_*.nc")
    sites: xr.Dataset | None = None
    if aeronet_files:
        out_path = data_dir / "aeronet_pnw.nc"
        if force or not output_is_fresh(out_path, aeronet_files):
            atomic_to_netcdf(aeronet.load_aeronet(aeronet_root, region=region), out_path)
            logger.info("[stage 2] AERONET → %s (%d monthly files)", out_path, len(aeronet_files))
        out["aeronet"] = out_path
        sites = xr.open_dataset(out_path).load()
        if sites.sizes.get("site", 0) == 0:
            sites = None
    else:
        logger.warning("No AERONET files found at %s; aeronet stage skipped", aeronet_root)

    # CERES EBAF: pick the latest granule
    ceres_files = _glob_files(cfg["paths"]["ceres_ebaf"], "CERES_EBAF_Edition*.nc")
    if not ceres_files:
        raise FileNotFoundError("No CERES EBAF files found")
    latest = max(ceres_files, key=lambda p: p.stat().st_mtime)
    out_path = data_dir / "ceres_ebaf.nc"
    if force or not output_is_fresh(out_path, [latest]):
        atomic_to_netcdf(ceres_ebaf.load_ceres_ebaf(latest, mask=mask), out_path)
        logger.info("[stage 2] CERES EBAF → %s (granule: %s)", out_path, latest.name)
    out["ceres_ebaf"] = out_path

    # MODIS Terra + Aqua
    for plat, key in [("terra", "modis_terra"), ("aqua", "modis_aqua")]:
        files = _glob_files(cfg["paths"][key], "*_M3*.hdf*") + _glob_files(cfg["paths"][key], "*.nc4")
        out_path = data_dir / f"modis_{plat}.nc"
        if force or not output_is_fresh(out_path, files):
            atomic_to_netcdf(
                modis_monthly.load_modis_monthly(files, plat, mask=mask, sites=sites),
                out_path,
            )
            logger.info("[stage 2] MODIS %s → %s (%d files)", plat, out_path, len(files))
        out[key] = out_path

    # VIIRS SNPP + NOAA-20
    for plat, key in [("snpp", "viirs_snpp"), ("noaa20", "viirs_noaa20")]:
        files = _glob_files(cfg["paths"][key], "*.nc")
        out_path = data_dir / f"viirs_{plat}.nc"
        if force or not output_is_fresh(out_path, files):
            atomic_to_netcdf(
                viirs_monthly.load_viirs_monthly(files, plat, mask=mask, sites=sites),
                out_path,
            )
            logger.info("[stage 2] VIIRS %s → %s (%d files)", plat, out_path, len(files))
        out[key] = out_path

    # MERRA-2 aer + slv (slv is optional — skip if not staged)
    for coll, key in [("aer", "merra2_aer"), ("slv", "merra2_slv")]:
        coll_root = Path(cfg["paths"][key]).expanduser()
        files = _glob_files(coll_root, "*.nc4")
        if not files:
            logger.warning(
                "[stage 2] MERRA-2 %s: no files at %s — skipping (predictors using "
                "this collection will be dropped from regression at stage 5)",
                coll, coll_root,
            )
            continue
        out_path = data_dir / f"merra2_{coll}.nc"
        if force or not output_is_fresh(out_path, files):
            atomic_to_netcdf(
                merra2_monthly.load_merra2_monthly(files, coll, mask=mask, sites=sites),
                out_path,
            )
            logger.info("[stage 2] MERRA-2 %s → %s (%d files)", coll, out_path, len(files))
        out[key] = out_path

    # QFED — region-mean only; no per-site companion (not used in AERONET plots).
    out_path = data_dir / "qfed.nc"
    qfed_root = Path(cfg["paths"]["qfed"]).expanduser()
    if force or not output_is_fresh(out_path, list(qfed_root.rglob("*.nc4"))):
        atomic_to_netcdf(
            qfed_monthly.load_qfed_monthly(qfed_root, cfg["species_qfed"], mask=mask),
            out_path,
        )
        logger.info("[stage 2] QFED → %s", out_path)
    out["qfed"] = out_path

    return out


def _stage3_attribution(stage2: dict[str, Path], out_dir: Path, force: bool) -> Path:
    out_path = out_dir / "data" / "smoke_attribution.nc"
    inputs = [stage2["merra2_aer"], stage2["modis_terra"], stage2["modis_aqua"],
              stage2["viirs_snpp"], stage2["viirs_noaa20"], stage2["qfed"]]
    if not force and output_is_fresh(out_path, inputs):
        logger.info("[stage 3] skipped (fresh)")
        return out_path
    merra2 = _to_month_start(xr.open_dataset(stage2["merra2_aer"]).load())
    qfed = _to_month_start(xr.open_dataset(stage2["qfed"]).load())
    obs: dict[str, xr.DataArray] = {}
    for k, var in [("modis_terra", "modis_terra_aod"), ("modis_aqua", "modis_aqua_aod"),
                   ("viirs_snpp", "viirs_snpp_aod"), ("viirs_noaa20", "viirs_noaa20_aod")]:
        ds = _to_month_start(xr.open_dataset(stage2[k]).load())
        obs[var] = ds[var]
    atomic_to_netcdf(
        attribution.compute_smoke_attribution(merra2=merra2, obs=obs, qfed=qfed),
        out_path,
    )
    logger.info("[stage 3] wrote %s", out_path)
    return out_path


def _stage4_merge(
    stage2: dict[str, Path], stage3: Path, out_dir: Path, force: bool,
    cfg: dict | None = None,
) -> Path:
    out_path = out_dir / "data" / "merged.nc"
    inputs = list(stage2.values()) + [stage3]
    if not force and output_is_fresh(out_path, inputs):
        logger.info("[stage 4] skipped (fresh)")
        return out_path
    parts = [_to_month_start(xr.open_dataset(p).load()) for p in inputs if p is not None]
    merged = xr.merge(parts, compat="override")
    # Stamp region + bbox explicitly — xr.merge inherits whichever input's attrs
    # were first, which may not be the one carrying region context.
    if cfg is not None:
        merged.attrs["region"] = cfg["region"]
        bb = cfg.get("bbox") or {}
        if bb:
            merged.attrs["bbox"] = (
                f"lon[{bb['lon_min']},{bb['lon_max']}] lat[{bb['lat_min']},{bb['lat_max']}]"
            )
    # Append _anom columns (only for vars with a `time` axis)
    for var in list(merged.data_vars):
        if "time" in merged[var].dims:
            merged[f"{var}_anom"] = anomaly.compute_anomaly(merged[var])
    atomic_to_netcdf(merged, out_path)
    logger.info("[stage 4] wrote %s", out_path)
    return out_path


def _stage5_regression(merged_path: Path, cfg: dict, out_dir: Path, force: bool) -> Path:
    out_csv = out_dir / "data" / "regression_table.csv"
    if not force and output_is_fresh(out_csv, [merged_path]):
        logger.info("[stage 5] skipped (fresh)")
        return out_csv
    merged = xr.open_dataset(merged_path).load()
    # Drop predictors not present (e.g. merra2_slv_TQV when slv data isn't staged).
    predictors = [p for p in cfg["regression"]["predictors"] if p in merged]
    dropped = [p for p in cfg["regression"]["predictors"] if p not in merged]
    if dropped:
        logger.warning("[stage 5] dropping missing predictors: %s", dropped)
    rows = []
    for response in [
        "ceres_toa_sw_all", "ceres_toa_sw_clr",
        "ceres_toa_lw_all", "ceres_toa_lw_clr",
        "ceres_toa_net_all", "ceres_toa_net_clr",
        "ceres_sfc_sw_down_all", "ceres_sfc_sw_down_clr",
        "ceres_sfc_net_all", "ceres_sfc_net_clr",
    ]:
        if response not in merged:
            continue
        if not predictors:
            continue
        result = regression.fit_radiative_efficiency(
            merged, response=response,
            predictors=predictors,
            hac_lags=cfg["regression"]["hac_lags"],
        )
        for var in predictors:
            rows.append(
                {
                    "response": response,
                    "predictor": var,
                    "coef": result.params[var],
                    "std_err": result.bse[var],
                    "t_stat": result.tvalues[var],
                    "p_value": result.pvalues[var],
                    "rsquared": result.rsquared,
                    "n_obs": result.nobs,
                }
            )
    import pandas as pd
    df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    logger.info("[stage 5] wrote %s (%d rows)", out_csv, len(df))
    return out_csv


def _pick_peak_year(merged_path: Path) -> int:
    merged = xr.open_dataset(merged_path).load()
    annual_oc = merged["qfed_oc"].groupby("time.year").mean()
    return int(annual_oc.idxmax().item())


def _stage6_plots(cfg: dict, merged_path: Path, out_dir: Path, force: bool) -> None:
    plots.setup_style()
    merged = xr.open_dataset(merged_path).load()
    aeronet_path = out_dir / "data" / "aeronet_pnw.nc"
    aeronet_ds = xr.open_dataset(aeronet_path).load() if aeronet_path.exists() else None
    plots_dir = out_dir / "plots"
    plot_fns = {
        "aod_total_timeseries":
            lambda: plots.plot_aod_total_timeseries(merged, aeronet_ds, plots_dir / "aod_total_timeseries.png"),
        "aod_sfc":
            lambda: plots.plot_aod_sfc(merged, plots_dir / "aod_sfc.png"),
        "aod_toa":
            lambda: plots.plot_aod_toa(merged, plots_dir / "aod_toa.png"),
        "aod_sfc_all":
            lambda: plots.plot_aod_sfc_all(merged, plots_dir / "aod_sfc_all.png"),
        "aod_toa_all":
            lambda: plots.plot_aod_toa_all(merged, plots_dir / "aod_toa_all.png"),
        "qfed_smoke_aod":
            lambda: plots.plot_qfed_smoke_aod(merged, plots_dir / "qfed_smoke_aod.png"),
        "qfed_vs_smoke_aod_scatter":
            lambda: plots.plot_qfed_vs_smoke_aod_scatter(merged, plots_dir / "qfed_vs_smoke_aod_scatter.png"),
        "smoke_radiative_efficiency":
            lambda: plots.plot_smoke_radiative_efficiency(merged, plots_dir / "smoke_radiative_efficiency.png"),
        "smoke_radiative_efficiency_tertiles":
            lambda: plots.plot_smoke_radiative_efficiency_tertiles(merged, plots_dir / "smoke_radiative_efficiency_tertiles.png"),
        "qfed_daily_bursts":
            lambda: plots.plot_qfed_daily_bursts(merged, plots_dir / "qfed_daily_bursts.png"),
        "smoke_fraction_timeseries":
            lambda: plots.plot_smoke_fraction_timeseries(merged, plots_dir / "smoke_fraction_timeseries.png"),
        "smoke_aod_timeseries":
            lambda: plots.plot_smoke_aod_timeseries(merged, plots_dir / "smoke_aod_timeseries.png"),
        "ceres_toa_anomaly":
            lambda: plots.plot_ceres_toa_anomaly(merged, plots_dir / "ceres_toa_anomaly.png"),
        "ceres_sfc_anomaly":
            lambda: plots.plot_ceres_sfc_anomaly(merged, plots_dir / "ceres_sfc_anomaly.png"),
        "scatter_dF_TOA_vs_smoke":
            lambda: plots.plot_scatter_dF_TOA_vs_smoke(merged, plots_dir / "scatter_dF_TOA_vs_smoke.png"),
        "scatter_dF_SFC_vs_smoke":
            lambda: plots.plot_scatter_dF_SFC_vs_smoke(merged, plots_dir / "scatter_dF_SFC_vs_smoke.png"),
        "seasonal_climatology":
            lambda: plots.plot_seasonal_climatology(merged, plots_dir / "seasonal_climatology.png"),
        "qfed_emissions_timeseries":
            lambda: plots.plot_qfed_emissions_timeseries(merged, plots_dir / "qfed_emissions_timeseries.png"),
        "aeronet_vs_modis_scatter":
            lambda: plots.plot_aeronet_vs_modis_scatter(merged, aeronet_ds, plots_dir / "aeronet_vs_modis_scatter.png"),
        "cloud_fraction_timeseries":
            lambda: plots.plot_cloud_fraction_timeseries(merged, plots_dir / "cloud_fraction_timeseries.png"),
        "merra2_obs_scaling":
            lambda: plots.plot_merra2_obs_scaling(merged, plots_dir / "merra2_obs_scaling.png"),
    }
    for name in cfg["plots"]:
        if name == "spatial_maps_peak_year":
            continue  # needs gridded path; current prototype regional-mean only — log and skip
        if name not in plot_fns:
            logger.warning("Unknown plot name in config: %s", name)
            continue
        plot_fns[name]()
        logger.info("[stage 6] %s.png", name)
    if "spatial_maps_peak_year" in cfg["plots"]:
        logger.warning(
            "spatial_maps_peak_year requires a gridded merged file (lat/lon retained); "
            "this prototype writes regional-mean only. Plot skipped."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FIREX PNW pipeline")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stages", default="1,2,3,4,5,6")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--end", default=None, help="Override config end-date (YYYY-MM)")
    args = parser.parse_args(argv)

    import yaml  # CLI-only dep; keep loader/stage helpers importable without it
    cfg = yaml.safe_load(args.config.read_text())
    if args.end is not None:
        cfg["time"]["end"] = args.end

    out_dir = Path(cfg["output_dir"])
    log_path = _setup_logging(out_dir / "logs")
    _log_header(cfg)
    logger.info("Log file: %s", log_path)

    stages = {int(s) for s in args.stages.split(",")}
    mask_path = _stage1_mask(cfg, out_dir, args.force) if 1 in stages else out_dir / "data" / "mask.nc"
    if 2 in stages:
        stage2 = _stage2_loaders(cfg, out_dir, mask_path, args.force)
    else:
        # Resume mode: only include stage-2 outputs that actually exist on disk.
        candidate_keys = ("ceres_ebaf", "modis_terra", "modis_aqua", "viirs_snpp",
                          "viirs_noaa20", "merra2_aer", "merra2_slv", "qfed", "aeronet")
        # Aeronet writes as `aeronet_pnw.nc`, not `aeronet.nc`.
        stage2 = {}
        for k in candidate_keys:
            fname = "aeronet_pnw.nc" if k == "aeronet" else f"{k}.nc"
            p = out_dir / "data" / fname
            if p.exists():
                stage2[k] = p
    stage3 = _stage3_attribution(stage2, out_dir, args.force) if 3 in stages else out_dir / "data" / "smoke_attribution.nc"
    merged = _stage4_merge(stage2, stage3, out_dir, args.force, cfg=cfg) if 4 in stages else out_dir / "data" / "merged.nc"
    if 5 in stages:
        _stage5_regression(merged, cfg, out_dir, args.force)
    if 6 in stages:
        _stage6_plots(cfg, merged, out_dir, args.force)
    logger.info("FIREX run finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
