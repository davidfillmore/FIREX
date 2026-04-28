# FIREX

Wildfire analysis with global atmospheric models and observational datasets.

## Response style (for Claude)

- Keep prompt responses minimal. No verbose framing or recap.
- Bullets over paragraphs. Complete paragraphs not required.
- State results, surface findings, ask the next question — nothing else.

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
| QFED v2.6r1 (biomass-burning emissions) | `~/Data/QFED/Y{YYYY}/M{MM}/` | `portal.nccs.nasa.gov/datashare/iesa/aerosol/emissions/QFED/v2.6r1/0.25/QFED/` | Fetched 2000–2015, 2017 → present (7 species: bc/oc/pm25/co/so2/no/nh3) via `scripts/fetch_qfed.sh`. **Y2016 deliberately skipped**: NCCS reprocessed Y2016 on 2025-03-19 with files inflated to 16.7 MB each (vs ~300 KB for adjacent years) — likely an erroneous regeneration; revisit if/when NCCS publishes a corrected Y2016. 0.25°×0.3125° MERRA-2 grid. Each file has `biomass` + biome breakdown (`_tf`, `_xf`, `_sv`, `_gl`). |
| MERRA-2 monthly 2D (tavgM) | `~/Data/MERRA2_tavgM/{coll}_Nx/` | GES DISC (`~/.netrc`) via `scripts/fetch_merra2_monthly.sh` | Default coll: `aer` (others available via `MERRA2_COLLECTIONS`). aer_Nx pre-existing 200001–202312 (288 files, ~31 GB), being extended to present. Stream codes 100/200/300/400 by year, 401 fallback for NRT. aer ~59 MB/file; slv ~51, lnd ~18, flx ~52. **No 2D monthly chm** — only model-level (M2I3NVCHM daily) or pressure-level (M2TMNPCHM monthly 3D). |
| MERRA-2 daily (cataloged, not staged) | — | `/ASDC_archive/GMAO/MERRA2/{YYYY}/{MM}/` (AMI) | 14 daily collections, 1980–present. Fire-relevant 2D: `tavg1_2d_{aer,slv,lnd,flx}_Nx`. 3D: `inst3_3d_aer_Nv`, `inst3_3d_chm_Nv`. ~2 TB/yr fire subset — won't fit current free disk. |
| MODIS C6.1 monthly L3 (Terra + Aqua) | `~/Data/{MOD08_M3,MYD08_M3}/` (flat) | LAADS (`~/.laads_token`) via `scripts/fetch_modis_monthly.sh` | Terra MOD08_M3 (2000-02→) + Aqua MYD08_M3 (2002-07→). ~385 MB/file. Existing 2000-02→2023-03 already on disk; fetcher backfills 2023-04→present. |
| MODIS Aqua C6.1 L2 (cataloged, not staged) | — | `/ASDC_archive/MODIS/Aqua/C61/{YYYY}/{DOY}/` (AMI) | HDF4 5-min granules: MYD02SS1, MYD03, MYD04_L2, MYD08_D3. |
| VIIRS monthly L3 (SNPP + NOAA-20) | `~/Data/VIIRS/AERDB_M3_VIIRS_{SNPP,NOAA20}/` | LAADS coll **5200** (`~/.laads_token`) via `scripts/fetch_viirs_monthly.sh` | AERDB (Deep Blue) only — **AERDT is L2-only** on VIIRS for both platforms; no D3/M3 published. SNPP from ~2012-03, NOAA-20 from 2018. ~6 MB/file. |
| VIIRS J1 L2 (cataloged, not staged) | — | `/ASDC_archive/VIIRS/J1/002/{YYYY}/{DOY}/` (AMI) | NetCDF 6-min granules: AERDB_L2 + AERDT_L2, 2018–present. |
| CERES EBAF Ed4.2.1 (TOA + Surface monthly) | `~/Data/CERES_EBAF/ceres/CERES_EBAF_Edition4.2.1_200003-202512.nc` | ASDC (`~/.netrc`) — `data.asdc.earthdata.nasa.gov/asdc-prod-protected/CERES/CERES_EBAF_Edition4.2.1/2000.03.01/` | Single global 1°×1° monthly file, 2000-03 → 2025-12 (310 months, 247 vars: 72 TOA + 144 SFC + 31 cloud/solar/aux), ~1.9 GiB. ASDC publishes one rolling granule (not month-by-month) so refresh = re-download the latest `Edition4.2.1_200003-{YYYYMM}.nc` from CMR. Ed4.2.1 supersedes Ed4.2 (Section 7 DQS fix); old `Edition4.2_200003-202407.nc` retired. No fetcher script — pulled manually with `curl --netrc -L -b ~/.urs_cookies -c ~/.urs_cookies`. |

**Notable absence in ASDC:** no MOD14/MYD14 (active fire), no MCD64 (burned area). Pull from LAADS or FIRMS if needed.

## Auth

- **GES DISC** (MERRA-2): `~/.netrc` machine `urs.earthdata.nasa.gov` with username/password (chmod 600). "NASA GESDISC DATA ARCHIVE" must be authorized at urs.earthdata.nasa.gov/profile/applications.
- **LAADS** (MODIS/VIIRS): bearer token in `~/.laads_token` (chmod 600). Generate at urs.earthdata.nasa.gov/profile → "Generate Token". ~60-day expiry.
- LAADS `.csv` directory listings are open; file GETs require the token. GES DISC requires auth on everything.
- Browser session does not transfer to terminal curl — generating a token is the supported bridge.

## Conventions

- New datasets: add a fetcher to `scripts/`, stage at `~/Data/<DATASET>/`, document in the table above.
- Fetchers must be idempotent and resumable (skip files already present, retry transient failures).
- Fetchers must use a lockfile (PID in `_fetch_<dataset>.lock`), per-request `--max-time` on curl (not just `--connect-timeout`), and `.part` cleanup on start. See `scripts/fetch_qfed.sh` for the canonical pattern.
- Env-override fetcher parameters where reasonable (year range, species, dest path) so re-runs don't require code edits.
- AMI transfers: AMI hostname / SSH config not yet captured — confirm before scripting AMI-side fetches.

## Running a long transfer

For any transfer expected to run more than a few minutes, launch detached so it survives the terminal/session closing and the Mac going to sleep:

```
nohup caffeinate -i ~/FIREX/scripts/fetch_<dataset>.sh \
      >> ~/Data/<DATASET>/_fetch_<dataset>.out 2>&1 < /dev/null &
```

Verify it's truly detached: `ps -o ppid= -p <PID>` should print `1` (reparented to launchd).

Monitor: `tail -f ~/Data/<DATASET>/_fetch_<dataset>.log`. Stop: `pkill -f fetch_<dataset>.sh` (lockfile auto-cleans via EXIT trap).
