"""Render the presentation plot set for every region in firex.regions.REGIONS.

Reads `output/<region>/data/merged.nc` per region and writes PNG + PDF for
each of the 7 presentation slugs into `output/<region>/plots/`. Region map
(`output/region_map.{png,pdf}`) is left untouched — it's region-agnostic
and regenerated separately when the region set changes.

Slugs match `scripts/sync_presentation_plots.sh` and the curated set
documented in CLAUDE.md.

Invoke from the davinci-monet env (matches regen_all_regions.py for
consistency; sarb also works since plots only need cartopy + xarray):

    conda run -n davinci-monet python scripts/regen_all_plots.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Make `firex` importable when launched from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import xarray as xr  # noqa: E402

from firex import plots  # noqa: E402
from firex.regions import REGIONS  # noqa: E402


PRESENTATION_SLUGS = [
    "aod_sfc",
    "aod_sfc_all",
    "aod_toa",
    "aod_toa_all",
    "qfed_smoke_aod",
    "qfed_vs_smoke_aod_scatter",
    "smoke_radiative_efficiency",
]


def _plot_fns(merged: xr.Dataset, plots_dir: Path) -> dict:
    return {
        "aod_sfc":
            lambda: plots.plot_aod_sfc(merged, plots_dir / "aod_sfc.png"),
        "aod_sfc_all":
            lambda: plots.plot_aod_sfc_all(merged, plots_dir / "aod_sfc_all.png"),
        "aod_toa":
            lambda: plots.plot_aod_toa(merged, plots_dir / "aod_toa.png"),
        "aod_toa_all":
            lambda: plots.plot_aod_toa_all(merged, plots_dir / "aod_toa_all.png"),
        "qfed_smoke_aod":
            lambda: plots.plot_qfed_smoke_aod(merged, plots_dir / "qfed_smoke_aod.png"),
        "qfed_vs_smoke_aod_scatter":
            lambda: plots.plot_qfed_vs_smoke_aod_scatter(merged, plots_dir / "qfed_vs_smoke_aod_scatter.png"),
        "smoke_radiative_efficiency":
            lambda: plots.plot_smoke_radiative_efficiency(merged, plots_dir / "smoke_radiative_efficiency.png"),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("regen-plots")
    output_root = Path.home() / "FIREX" / "output"
    plots.setup_style()
    total_start = time.monotonic()
    failures: list[tuple[str, str, str]] = []

    for region_name in REGIONS:
        merged_path = output_root / region_name / "data" / "merged.nc"
        plots_dir = output_root / region_name / "plots"
        if not merged_path.exists():
            log.warning("skip %s: no merged.nc", region_name)
            continue
        log.info("=== region: %s ===", region_name)
        t0 = time.monotonic()
        merged = xr.open_dataset(merged_path).load()
        fns = _plot_fns(merged, plots_dir)
        for slug in PRESENTATION_SLUGS:
            try:
                fns[slug]()
                log.info("  %s ok", slug)
            except Exception as e:
                log.error("  %s FAILED: %s", slug, e)
                failures.append((region_name, slug, repr(e)))
        log.info("done %s in %.1fs", region_name, time.monotonic() - t0)

    log.info("regen-all-plots finished in %.1f min",
             (time.monotonic() - total_start) / 60)
    if failures:
        log.error("%d failures:", len(failures))
        for r, s, e in failures:
            log.error("  %s/%s: %s", r, s, e)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
