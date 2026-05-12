"""Render global spatial-pattern plots into `output/global/plots/`.

Three figures:
  - smoke_aod_seasonal           (2×2 seasonal climatology)
  - smoke_radiative_effect       (1×2 TOA + SFC mean radiative effect)
  - event_anomaly_<event>        (2×2 per event from EVENT_CATALOG)

Builds (and caches) the aligned MERRA-2 + CERES dataset on first run.

Invoke from the davinci-monet env (needs dask for the MERRA-2 mfdataset
open; sarb lacks dask):

    conda run -n davinci-monet python scripts/regen_global_plots.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Make `firex` importable when launched from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firex import global_plots, plots  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("regen-global-plots")
    plots.setup_style()

    out_dir = Path.home() / "FIREX" / "output" / "global" / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("building global dataset (cached at %s)",
             global_plots.CACHE_FILE)
    t0 = time.monotonic()
    ds = global_plots.build_global_dataset()
    log.info("dataset ready: %d months, %d×%d grid (%.1fs)",
             ds.sizes["time"], ds.sizes["lat"], ds.sizes["lon"],
             time.monotonic() - t0)

    failures: list[tuple[str, str]] = []

    def _run(slug: str, fn) -> None:
        try:
            t = time.monotonic()
            fn()
            log.info("  %s ok (%.1fs)", slug, time.monotonic() - t)
        except Exception as e:
            log.error("  %s FAILED: %s", slug, e)
            failures.append((slug, repr(e)))

    _run("smoke_aod_seasonal",
         lambda: global_plots.plot_smoke_aod_seasonal(
             ds, out_dir / "smoke_aod_seasonal.png"))
    _run("smoke_radiative_effect",
         lambda: global_plots.plot_smoke_radiative_effect(
             ds, out_dir / "smoke_radiative_effect.png"))
    for event_key in global_plots.EVENT_CATALOG:
        _run(f"event_anomaly_{event_key}",
             lambda k=event_key: global_plots.plot_event_anomaly(
                 ds, k, out_dir / f"event_anomaly_{k}.png"))

    # Period-comparison set: 2000–2019 baseline + 2020-onwards anomaly,
    # for smoke AOD and surface SW clear-sky.
    baseline = ("2000-03", "2019-12")
    target = ("2020-01", "2025-12")
    _run("smoke_aod_seasonal_2000_2019",
         lambda: global_plots.plot_seasonal_climatology(
             ds, "smoke_aod",
             out_dir / "smoke_aod_seasonal_2000_2019.png",
             period=baseline, cmap="Spectral_r",
             norm=global_plots.smoke_aod_norm(),
             cbar_label="Smoke AOD",
             title="MERRA-2 Smoke AOD — Seasonal Climatology, 2000–2019",
             gridlines=False, region_boxes=False))

    # Single-season cuts: DJF + JJA baseline + anomaly per variable.
    for season in ("DJF", "JJA"):
        season_l = season.lower()
        _run(f"smoke_aod_{season_l}_baseline_2000_2019",
             lambda s=season: global_plots.plot_seasonal_climatology(
                 ds, "smoke_aod",
                 out_dir / f"smoke_aod_{s.lower()}_baseline_2000_2019.png",
                 period=baseline, cmap="Spectral_r",
                 norm=global_plots.smoke_aod_norm(),
                 cbar_label="Smoke AOD",
                 title=f"MERRA-2 Smoke AOD — {s} Climatology, 2000–2019",
                 gridlines=False, region_boxes=False, seasons=(s,)))
        _run(f"smoke_aod_{season_l}_anom",
             lambda s=season: global_plots.plot_seasonal_anomaly(
                 ds, "smoke_aod",
                 out_dir / f"smoke_aod_{s.lower()}_anom.png",
                 baseline=baseline, target=target,
                 cmap="PuOr_r", lim=0.20,
                 cbar_label=r"$\Delta$Smoke AOD",
                 title=(f"MERRA-2 Smoke AOD — {s}, "
                        "2020–2025 minus 2000–2019"),
                 gridlines=False, region_boxes=False, seasons=(s,)))

    # SFC SW JJA anomaly: cmap RdBu (negative→red, fire-impact direction),
    # cbar inverted so negative sits at the top.
    _run("sfc_sw_clr_jja_anom",
         lambda: global_plots.plot_seasonal_anomaly(
             ds, "sfc_sw_down_clr",
             out_dir / "sfc_sw_clr_jja_anom.png",
             baseline=baseline, target=target,
             cmap="RdBu", lim=10.0,
             cbar_label=r"$\Delta$SW$_\downarrow$ clear-sky (W m$^{-2}$)",
             title=(r"CERES Surface SW$_\downarrow$ Clear-Sky — JJA, "
                    "2020–2025 minus 2000–2019"),
             gridlines=False, region_boxes=False,
             seasons=("JJA",), invert_cbar=True))
    _run("sfc_sw_clr_seasonal_2000_2019",
         lambda: global_plots.plot_seasonal_climatology(
             ds, "sfc_sw_down_clr",
             out_dir / "sfc_sw_clr_seasonal_2000_2019.png",
             period=baseline, cmap="viridis", vmin=0, vmax=400,
             cbar_label=r"SW$_\downarrow$ clear-sky at surface (W m$^{-2}$)",
             title=(r"CERES Surface SW$_\downarrow$ Clear-Sky — "
                    "Seasonal Climatology, 2000–2019")))
    _run("smoke_aod_seasonal_2020_anom",
         lambda: global_plots.plot_seasonal_anomaly(
             ds, "smoke_aod",
             out_dir / "smoke_aod_seasonal_2020_anom.png",
             baseline=baseline, target=target,
             cmap="PuOr_r", lim=0.20,
             cbar_label=r"$\Delta$Smoke AOD",
             title=("MERRA-2 Smoke AOD — "
                    "2020–2025 minus 2000–2019 baseline"),
             gridlines=False, region_boxes=False))
    _run("sfc_sw_clr_seasonal_2020_anom",
         lambda: global_plots.plot_seasonal_anomaly(
             ds, "sfc_sw_down_clr",
             out_dir / "sfc_sw_clr_seasonal_2020_anom.png",
             baseline=baseline, target=target,
             cmap="RdBu_r", lim=10.0,
             cbar_label=r"$\Delta$SW$_\downarrow$ clear-sky (W m$^{-2}$)",
             title=(r"CERES Surface SW$_\downarrow$ Clear-Sky — "
                    "2020–2025 minus 2000–2019 baseline"),
             gridlines=False, region_boxes=False))

    if failures:
        log.error("%d failures:", len(failures))
        for s, e in failures:
            log.error("  %s: %s", s, e)
        return 1
    log.info("all global plots rendered into %s", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
