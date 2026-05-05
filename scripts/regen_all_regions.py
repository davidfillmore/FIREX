"""Build merged.nc for every region in firex.regions.REGIONS.

Runs stages 1-4 (mask, loaders, attribution, merge) per region. PNW and EAU
short-circuit on cache; new regions re-load gridded data through their
mask. Skips stages 5-6 (regression + plots) so the only artifact per
region is `output/<region>/data/merged.nc` and the stage-2 NetCDFs.

Invoke from the davinci-monet env (pyhdf required for MODIS HDF4):

    conda run -n davinci-monet python scripts/regen_all_regions.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Make `firex` importable when launched from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firex.regions import REGIONS
from firex.run_pnw import (  # noqa: E402
    _stage1_mask, _stage2_loaders, _stage3_attribution, _stage4_merge,
)


BASE_PATHS = {
    "ceres_ebaf":   "~/Data/CERES_EBAF/ceres",
    "modis_terra":  "~/Data/MOD08_M3",
    "modis_aqua":   "~/Data/MYD08_M3",
    "viirs_snpp":   "~/Data/VIIRS/AERDB_M3_VIIRS_SNPP",
    "viirs_noaa20": "~/Data/VIIRS/AERDB_M3_VIIRS_NOAA20",
    "merra2_aer":   "~/Data/MERRA2_tavgM/aer_Nx",
    "merra2_slv":   "~/Data/MERRA2_tavgM/slv_Nx",
    "qfed":         "~/Data/QFED",
    "aeronet":      "~/Data/AeroNet",
}
SPECIES_QFED = ["bc", "oc", "co"]


def cfg_for(region_name: str) -> dict:
    r = REGIONS[region_name]
    return {
        "region": region_name,
        "bbox": {
            "lon_min": r.lon_min, "lon_max": r.lon_max,
            "lat_min": r.lat_min, "lat_max": r.lat_max,
        },
        "paths": dict(BASE_PATHS),
        "species_qfed": list(SPECIES_QFED),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("regen")
    output_root = Path.home() / "FIREX" / "output"
    total_start = time.monotonic()

    for region_name in REGIONS:
        cfg = cfg_for(region_name)
        out_dir = output_root / region_name
        log.info("=== region: %s ===", region_name)
        t0 = time.monotonic()
        try:
            mask_path = _stage1_mask(cfg, out_dir, force=False)
            stage2 = _stage2_loaders(cfg, out_dir, mask_path, force=False)
            stage3 = _stage3_attribution(stage2, out_dir, force=False)
            _stage4_merge(stage2, stage3, out_dir, force=False, cfg=cfg)
        except Exception as e:
            log.error("FAILED %s: %s", region_name, e, exc_info=True)
            continue
        log.info("done %s in %.1f min",
                 region_name, (time.monotonic() - t0) / 60)
    log.info("regen-all finished in %.1f min",
             (time.monotonic() - total_start) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
