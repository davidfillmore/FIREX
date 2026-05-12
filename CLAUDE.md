# FIREX

Wildfire analysis with global atmospheric models and observational datasets.

**Study methodology:** see [`FIREX.md`](FIREX.md) — describes the science (regional radiative effects of wildfire smoke over the CERES record), dataset roles, smoke-AOD attribution approach, and intended analysis pipeline. This file (`CLAUDE.md`) covers data staging, fetchers, and conventions.

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

## Related repos

- **DAVINCI-MONET** (Python package `davinci_monet`, conda env `davinci-monet`, branch `ceres` for FIREX-related work) lives at different paths per machine:
  - This Mac: `~/DAVINCI/`
  - Other system: `~/EarthSystem/DAVINCI-MONET/`
- Package name, env name, and branch name are machine-independent; only the filesystem path varies.

## Data staging

- All transferred data lives at `~/Data/<DATASET>/...` — sibling to existing `AeroNet/`, `MATCH/`, `MERRA2_tavgM/`, `MODIS/`, etc.
- **Never stage data inside this repo.**
- Each dataset stage dir holds a fetcher log (`_fetch_<dataset>.log`).

## Layout

- `scripts/` — data-transfer and analysis scripts.

## Datasets

| Dataset | Local path | Source | Status |
|---|---|---|---|
| QFED v2.6r1 (biomass-burning emissions) | `~/Data/QFED/Y{YYYY}/M{MM}/` | `portal.nccs.nasa.gov/datashare/iesa/aerosol/emissions/QFED/v2.6r1/0.25/QFED/` | Fetched 2000–2015, 2017 → present (7 species: bc/oc/pm25/co/so2/no/nh3) via `scripts/fetch_qfed.sh`. **Y2016 deliberately skipped**: NCCS reprocessed Y2016 on 2025-03-19 with files inflated to 16.7 MB each (vs ~300 KB for adjacent years) — likely an erroneous regeneration; revisit if/when NCCS publishes a corrected Y2016. **Y2017 known-bad**: every daily file for 2017 contains the same `biomass` array (verified — `np.array_equal` across days), so the daily series is a placeholder/static repeat and the monthly mean is meaningless. Cause unclear (fetch error, NCCS source issue, or local archive replacement). The `_mask_bad_qfed` helper in `firex/plots.py` masks Y2017 QFED-* variables to NaN at plot time as a workaround. Refetch from NCCS to fix properly. 0.25°×0.3125° MERRA-2 grid. Each file has `biomass` + biome breakdown (`_tf`, `_xf`, `_sv`, `_gl`). |
| MERRA-2 monthly 2D (tavgM) | `~/Data/MERRA2_tavgM/{coll}_Nx/` | GES DISC (`~/.netrc`) via `scripts/fetch_merra2_monthly.sh` | Default coll: `aer` (others available via `MERRA2_COLLECTIONS`). aer_Nx pre-existing 200001–202312 (288 files, ~31 GB), being extended to present. Stream codes 100/200/300/400 by year, 401 fallback for NRT. aer ~59 MB/file; slv ~51, lnd ~18, flx ~52. **No 2D monthly chm** — only model-level (M2I3NVCHM daily) or pressure-level (M2TMNPCHM monthly 3D). |
| MERRA-2 daily (cataloged, not staged) | — | `/ASDC_archive/GMAO/MERRA2/{YYYY}/{MM}/` (AMI) | 14 daily collections, 1980–present. Fire-relevant 2D: `tavg1_2d_{aer,slv,lnd,flx}_Nx`. 3D: `inst3_3d_aer_Nv`, `inst3_3d_chm_Nv`. ~2 TB/yr fire subset — won't fit current free disk. |
| MODIS C6.1 monthly L3 (Terra + Aqua) | `~/Data/{MOD08_M3,MYD08_M3}/` (flat) | LAADS (`~/.laads_token`) via `scripts/fetch_modis_monthly.sh` | Terra MOD08_M3 (2000-02→) + Aqua MYD08_M3 (2002-07→). ~385 MB/file. Existing 2000-02→2023-03 already on disk; fetcher backfills 2023-04→present. |
| MODIS Aqua C6.1 L2 (cataloged, not staged) | — | `/ASDC_archive/MODIS/Aqua/C61/{YYYY}/{DOY}/` (AMI) | HDF4 5-min granules: MYD02SS1, MYD03, MYD04_L2, MYD08_D3. |
| VIIRS monthly L3 (SNPP + NOAA-20) | `~/Data/VIIRS/AERDB_M3_VIIRS_{SNPP,NOAA20}/` | LAADS coll **5200** (`~/.laads_token`) via `scripts/fetch_viirs_monthly.sh` | AERDB (Deep Blue) only — **AERDT is L2-only** on VIIRS for both platforms; no D3/M3 published. SNPP from ~2012-03, NOAA-20 from 2018. ~6 MB/file. |
| VIIRS J1 L2 (cataloged, not staged) | — | `/ASDC_archive/VIIRS/J1/002/{YYYY}/{DOY}/` (AMI) | NetCDF 6-min granules: AERDB_L2 + AERDT_L2, 2018–present. |
| CERES EBAF Ed4.2.1 (TOA + Surface monthly) | `~/Data/CERES_EBAF/ceres/CERES_EBAF_Edition4.2.1_200003-202512.nc` | ASDC (`~/.netrc`) — `data.asdc.earthdata.nasa.gov/asdc-prod-protected/CERES/CERES_EBAF_Edition4.2.1/2000.03.01/` | Single global 1°×1° monthly file, 2000-03 → 2025-12 (310 months, 247 vars: 72 TOA + 144 SFC + 31 cloud/solar/aux), ~1.9 GiB. ASDC publishes one rolling granule (not month-by-month) so refresh = re-download the latest `Edition4.2.1_200003-{YYYYMM}.nc` from CMR. Ed4.2.1 supersedes Ed4.2 (Section 7 DQS fix); old `Edition4.2_200003-202407.nc` retired. No fetcher script — pulled manually with `curl --netrc -L -b ~/.urs_cookies -c ~/.urs_cookies`. |

**Notable absence in ASDC:** no MOD14/MYD14 (active fire), no MCD64 (burned area). Pull from LAADS or FIRMS if needed.

## Candidate datasets — smoke radiative-effects study

Study scope: regional monthly time series, CERES record (2000-03 → present). Forcing-side AOD + emissions are covered by what's already staged; gaps are independent fire activity, smoke-vs-other-aerosol attribution, vertical structure, and surface validation.

### Tier 1 — high priority

- **GFED4.1s** (top priority) — Global Fire Emissions Database, 1997 → present, 0.25° monthly burned area + emissions for ~50 species incl. CO, BC, OC, PM2.5. Built from MCD64A1 burned area + MODIS active fire for small fires, scaled by emission factors. Canonical reference in the smoke-radiative-effects literature. Complements QFED (FRP-based) with a burned-area-based estimate — running both lets us bound emissions uncertainty.
  - Source: `https://www.geo.vu.nl/~gwerf/GFED/GFED4/` (HDF5 monthly files, ~100 MB/yr) and mirror at `https://daac.ornl.gov/VEGETATION/guides/fire_emissions_v4.html` (NetCDF). Anonymous HTTP, no auth.
  - GFED5 is in development but not yet published (as of 2026-04); track at `https://www.globalfiredata.org/`.
- **MCD64A1** — MODIS Collection 6 burned area, 500 m monthly, 2000-11 → present. The observational basis under GFED. Independent of QFED's FRP approach.
  - Source: LAADS coll **61**, product `MCD64A1`, MODIS sinusoidal tiles. Same bearer token as MOD08/MYD08.
- **OMI / OMPS UV Aerosol Index (UVAI)** — best absorbing-smoke proxy; separates smoke from sulfate/dust in MODIS AOD. OMI: 2004 → present (row anomaly post-2007). OMPS: 2012 → present (continuity).
  - OMI L3: GES DISC, `OMAERUVd` (daily 0.25°, with UVAI). Monthly means easy to compute from daily.
  - OMPS aerosol: NASA Ozone SIPS — verify exact short-name (likely `OMPS-NPP_NMMIEAER` family) before fetching.
  - Auth: same `~/.netrc` as MERRA-2 (GES DISC).
- **MOPITT CO L3 monthly** — Terra MOPITT, 2000-03 → present, 1° monthly, total-column and profile CO. Long-record fire-transport tracer aligned exactly to the CERES record.
  - Source: ASDC, `MOP03JM` (joint TIR/NIR monthly L3). Same `~/.netrc`.
- **MERRA-2 monthly extras** — fetcher already supports this via `MERRA2_COLLECTIONS`. For regional analysis we want `slv` (single-level state — T2M, U10M, V10M, PBLH, TQV), `flx` (turbulent fluxes — HFLUX, EFLUX, USTAR), `lnd` (soil moisture, runoff, fire risk). Trivial to add.

### Tier 2 — complementary

- **MISR** — 2000-02 → present. (a) `MIL3MAEN` monthly L3 AOD at 0.5°, independent of MODIS. (b) MISR plume-height climatology (MINX-derived) for vertical placement of smoke. Source: ASDC.
- **CALIPSO/CALIOP** — 2006-06 → 2023-08 (instrument shut down). Aerosol layer products `CAL_LID_L3_APro` for vertical aerosol distribution. Limited record but irreplaceable for the vertical question. Source: ASDC.
- **MTBS** (Monitoring Trends in Burn Severity) — U.S. fire perimeters and burn severity since 1984. Useful regional fire mask if focusing on Pacific NW / California. Shapefiles, no auth. `https://mtbs.gov/`.
- **SURFRAD** — NOAA 7-site network of 1-min surface SW/LW broadband, 1995 → present. Direct ground truth for CERES SFC SW↓/LW↓. Pacific NW site: Sioux Falls SD is closest; western U.S. site: Desert Rock NV, Boulder CO. `https://gml.noaa.gov/grad/surfrad/`.

### Tier 3 — case-by-case

- **ESA Fire_cci** — independent ESA burned-area record, cross-validation against MCD64/GFED.
- **GBBEPx** (NOAA) — alternative emissions inventory for QFED sensitivity tests.
- **NOAA HMS smoke polygons** — daily analyst-drawn smoke plumes; useful for smoke-day classification when compositing CERES anomalies.
- **AirNow / EPA AQS PM2.5** — surface health impact; out of scope unless we extend the study.

### Already staged but worth flagging for this study

- **AERONET** at `~/Data/AeroNet/` — 300 monthly NetCDF files (2000-01 → 2024-12), multi-wavelength AOD per site, sub-daily samples. Surface AOD validation against MODIS/VIIRS column AOD; SSA at AERONET inversion sites also available. For Pacific NW: Trinidad Head, BSRN_BAO_Boulder, Bondville, Railroad_Valley are nearby. Last refresh: 2025-07-28.

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

## Regions

The full registry lives in `firex/regions.py`. Four regions are *featured*
(highlighted orange on the region map and form the current presentation
arc); the rest are defined but only enter the analysis pipeline when added
to a config. Editing this table without also updating the dataclass — or
vice versa — drifts the docs from the code; keep them in sync.

| Region | bbox (lon, lat) | Featured | Notes |
|---|---|:---:|---|
| pacific-northwest | 130°W–110°W, 42°N–52°N | ★ | 2017 / 2018 / 2020 / 2021 fire seasons |
| eastern-canada | 90°W–65°W, 48°N–58°N | ★ | 2023 Quebec/Ontario record boreal season |
| eastern-australia | 140°E–154°E, 44°S–25°S | ★ | 2019-20 Black Summer (incl. Tasmania) |
| eastern-siberia | 110°E–155°E, 55°N–72°N | ★ | 2019 / 2021 Yakutia megafires |
| western-canada | 130°W–105°W, 52°N–62°N |  | 2023 NWT/BC; Yellowknife evacuation |
| alaska | 165°W–141°W, 60°N–72°N |  | 2004 record, 2022 boreal |
| california | 124°W–114°W, 32°N–42°N |  | 2018 Camp; 2020 Creek + August Complex |
| central-africa | 15°E–35°E, 15°S–5°N |  | World's largest savanna BB region by area |
| amazon | 75°W–50°W, 15°S–5°S |  | Deforestation arc; 2019 / 2023 |
| maritime-se-asia | 95°E–120°E, 5°S–5°N |  | Indonesian peat fires; 2015 ENSO |
| northern-australia | 125°E–145°E, 20°S–10°S |  | Annual dry-season savanna |
| mediterranean | 10°W–30°E, 35°N–45°N |  | Greece / Spain / Portugal recurring |

## Presentation plot set

Canonical store: `~/FIREX/output/<region>/plots/` — `scripts/regen_all_plots.py`
renders the curated figure pool here for every region. Slugs (PNG + PDF
per region):

- `aod_sfc`, `aod_sfc_all`
- `aod_toa`, `aod_toa_all`
- `qfed_smoke_aod`
- `qfed_vs_smoke_aod_scatter`
- `smoke_radiative_efficiency`
- `dF_sfc_compare`, `dF_toa_compare` (CERES-vs-MERRA-2 ΔF, clear-sky)
- `region_map` (single file, region-agnostic — `output/region_map.{png,pdf}`)

`~/Desktop/` is a **review staging area**, not a canonical mirror.
`scripts/sync_presentation_plots.sh` copies a curated subset (its
`SLUGS` array — the *active review queue*) to Desktop with the region
appended to each filename. Desktop copies are throwaway: the canonical
copy in the FIREX folder is the source of truth. `REGIONS` in the sync
script chooses which featured regions get staged (currently the four
featured regions).

Workflow for adding or modifying a slug:

1. Add the slug to `PRESENTATION_SLUGS` + `_plot_fns` in
   `scripts/regen_all_plots.py` so it renders for every region.
2. Add it to `SLUGS` in `scripts/sync_presentation_plots.sh` so it
   lands on Desktop for review.
3. Run `scripts/regen_all_plots.py` (renders to FIREX folder) then
   `scripts/sync_presentation_plots.sh` (mirrors to Desktop).
4. Review on Desktop. When the plot is approved, delete the staged
   files from Desktop and remove the slug from `SLUGS` in the sync
   script — the canonical copy in `~/FIREX/output/<region>/plots/`
   stays put, but the slug exits the review queue and won't re-stage
   on the next sync.

### Global spatial plots

Canonical store: `~/FIREX/output/global/plots/` —
`scripts/regen_global_plots.py` renders global maps from MERRA-2 aer_Nx
(smoke AOD = BCEXTTAU + OCEXTTAU) and CERES EBAF clear-sky fluxes,
interpolated onto the CERES 1° grid and cached at
`output/global/data/global_monthly.nc`. Run from the davinci-monet env
(needs dask).

Builders in `firex/global_plots.py`:

- `plot_smoke_aod_seasonal`         — 2×2 DJF/MAM/JJA/SON climatology
- `plot_smoke_radiative_effect`     — 1×2 TOA + SFC β·⟨AOD⟩ panels
- `plot_event_anomaly`              — 2×2 per event from `EVENT_CATALOG`
- `plot_seasonal_climatology`       — generic single-var seasonal mean,
                                      optional `period` window + `seasons`
                                      tuple for single-panel cuts
- `plot_seasonal_anomaly`           — generic target-minus-baseline anomaly,
                                      same panel/season knobs plus `sign`
                                      and `invert_cbar` for flipping the
                                      reading direction
- `plot_total_aod_match_vs_merra2`  — two-panel side-by-side total-AOD
                                      anomaly from MATCH Ed4 and MERRA-2
                                      on a shared scale; an independent
                                      satellite-derived check on MERRA-2

`load_match_modis()` opens the MATCH Terra-Aqua MODIS Ed4 TOTEXTTAU
stream from `~/Data/MATCH/` (192×94 T62-like Gaussian grid, no
embedded time coord — year-month parsed from filename). Coverage is
2000-03 through 2024-09, so MATCH-vs-MERRA-2 comparisons cap the
target window at 2024-09.

Smoke-AOD climatology maps use `cmap='Spectral_r'` with the
log-spaced `SMOKE_AOD_LEVELS` BoundaryNorm (see `smoke_aod_norm()`),
which resolves both the central-African burning peak (~0.3–0.5) and
the global background (~0.005–0.02) on the same scale. Smoke-AOD
anomaly maps use `PuOr_r`, ±0.20. Surface SW clear-sky anomaly uses
`RdBu` with `invert_cbar=True` so fire-impact direction (negative ΔSW)
sits at the top of the scale in warm colors, consistent with the
smoke-AOD anomaly aesthetic. All pcolormesh calls are rasterized to
keep PDF file sizes small.

## Running a long transfer

For any transfer expected to run more than a few minutes, launch detached so it survives the terminal/session closing and the Mac going to sleep:

```
nohup caffeinate -i ~/FIREX/scripts/fetch_<dataset>.sh \
      >> ~/Data/<DATASET>/_fetch_<dataset>.out 2>&1 < /dev/null &
```

Verify it's truly detached: `ps -o ppid= -p <PID>` should print `1` (reparented to launchd).

Monitor: `tail -f ~/Data/<DATASET>/_fetch_<dataset>.log`. Stop: `pkill -f fetch_<dataset>.sh` (lockfile auto-cleans via EXIT trap).

## External-drive sync (Io)

`/Volumes/Io` is an external exFAT drive used as a portable backup of
locally fetched datasets plus the FIREX merged outputs. Run
`scripts/sync_to_io.sh` after a new fetch or regen to keep Io current.

Layout on Io:

- `/Volumes/Io/<DATASET>/` mirrors `~/Data/<DATASET>/` for QFED, VIIRS,
  MERRA2_tavgM, MOD08_M3, MYD08_M3, and Optics.
- `/Volumes/Io/FIREX/<region>/data/merged.nc` mirrors
  `~/FIREX/output/<region>/data/merged.nc`. Region list is
  auto-discovered from the local glob — adding a region locally is
  picked up on the next sync without script edits.

The script is idempotent (rsync delta), holds a lockfile, and uses
exFAT-safe flags: `-rltDv --modify-window=1 --human-readable --stats`
(no permissions/owner/group preservation — exFAT can't store them).
Logs to `/Volumes/Io/_sync_to_io.log`. Launch detached using the same
`nohup caffeinate -i … &` pattern as the fetchers if the run is
expected to take more than a few minutes (large initial mirror or
many newly-fetched files).
