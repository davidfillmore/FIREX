# FIREX

Wildfire analysis with global atmospheric models and observational datasets.

## Workflow

- Analyses run locally on the Mac in conda env `sarb` (`/Users/Dfillmor/miniconda3/envs/sarb`).
  - Activate with `conda activate sarb`, or invoke as `conda run -n sarb python ...`.
  - Has: Python 3.14, xarray 2026.2, numpy 2.4, pandas 3.0, scipy, netCDF4, matplotlib, cartopy, cdo, wgrib2, cfgrib, eccodes, statsmodels, magics.
  - Missing: dask, pyhdf, h5py, pyyaml, requests/httpx, zarr/fsspec, pytest. Surface install requests rather than silently `pip install`.
- Source archives (NASA ASDC `/ASDC_archive/...`, NCCS portal, LAADS, FIRMS) are *source* paths for transfers — they are not mounted locally.

## Data staging

- All transferred data lives at `~/Data/<DATASET>/...` — sibling to existing `AeroNet/`, `MATCH/`, `MERRA2_tavgM/`, `MODIS/`, etc.
- **Never stage data inside this repo.**
- Each dataset stage dir holds a fetcher log (`_fetch_<dataset>.log`).

## Layout

- `scripts/` — data-transfer and analysis scripts.

## Datasets

| Dataset | Local path | Source | Status |
|---|---|---|---|
| QFED v2.6r1 (biomass-burning emissions) | `~/Data/QFED/Y{YYYY}/M{MM}/` | `portal.nccs.nasa.gov/datashare/iesa/aerosol/emissions/QFED/v2.6r1/0.25/QFED/` | Fetched 2020-01 → present (7 species: bc/oc/pm25/co/so2/no/nh3) via `scripts/fetch_qfed.sh`. 0.25°×0.3125° MERRA-2 grid. Each file has `biomass` + biome breakdown (`_tf`, `_xf`, `_sv`, `_gl`). |
| MERRA-2 (GMAO reanalysis) | TBD | `/ASDC_archive/GMAO/MERRA2/{YYYY}/{MM}/` (AMI host) | Cataloged, not yet transferred. 14 daily collections (aer/chm/slv/lnd/flx/rad/asm/ana), 1980–present. Fire-relevant: `tavg1_2d_aer_Nx`, `tavg1_2d_slv_Nx`, `tavg1_2d_lnd_Nx`, `tavg1_2d_flx_Nx`, `inst3_3d_aer_Nv`, `inst3_3d_chm_Nv`. |
| MODIS Aqua C6.1 | TBD | `/ASDC_archive/MODIS/Aqua/C61/{YYYY}/{DOY}/` (AMI) | Cataloged, not transferred. HDF4 5-min granules: MYD02SS1 (radiances), MYD03 (geo), MYD04_L2 (AOD), MYD08_D3 (daily L3). |
| VIIRS NOAA-20 (J1) | TBD | `/ASDC_archive/VIIRS/J1/002/{YYYY}/{DOY}/` (AMI) | Cataloged, not transferred. NetCDF 6-min AOD: AERDB (Deep Blue) + AERDT (Dark Target), 2018–present. |

**Notable absence in ASDC:** no MOD14/MYD14 (active fire), no MCD64 (burned area). Pull from LAADS or FIRMS if needed.

## Conventions

- New datasets: add a fetcher to `scripts/`, stage at `~/Data/<DATASET>/`, document in the table above.
- Fetchers must be idempotent and resumable (skip files already present, retry transient failures).
- Env-override fetcher parameters where reasonable (year range, species, dest path) so re-runs don't require code edits.
- AMI transfers: AMI hostname / SSH config not yet captured — confirm before scripting AMI-side fetches.
