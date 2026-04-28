# FIREX Pacific Northwest Prototype — Design

**Date:** 2026-04-28
**Status:** Draft for review
**Companion docs:** [`../../../FIREX.md`](../../../FIREX.md) (study methodology), [`../../../CLAUDE.md`](../../../CLAUDE.md) (data staging)

## Goal

End-to-end monthly time-series pipeline producing 13 figures for the **Pacific Northwest** region over the CERES record (2000-03 → most recent EBAF granule, currently 2025-12). Validates the regional smoke-radiative-effects methodology in FIREX.md before scaling to additional regions.

## Scope

**In scope (this spec):**

- One region: Pacific Northwest. Default bbox **42–52°N, 130–110°W**, configurable.
- Smoke attribution via MERRA-2 species fraction × observed AOD (primary path in FIREX.md §"Smoke-AOD attribution").
- Both **clear-sky and all-sky** CERES quantities, carried in parallel.
- Hybrid anomaly handling: plots show climatology-subtracted anomalies; regression uses raw values with month-of-year fixed effects + linear trend.
- 13 plots (10 core + 3 optional).
- Standard Python project layout in `~/EarthSystem/FIREX/`.

**Out of scope (deferred to subsequent specs):**

- Additional regions (California, Boreal Canada, Siberia, Amazon, etc.) — pipeline is single-region in this iteration.
- UVAI cross-check (OMI/OMPS) — depends on candidate datasets not yet staged.
- QFED mass-balance smoke-AOD sanity check — methods-section sidebar, can be a follow-on.
- GFED4.1s ingest — runs with currently staged QFED only.
- SURFRAD surface-flux validation — defer to multi-region phase.
- CALIPSO/MISR vertical structure — case-study scope, not prototype.

## Constraints

- Active conda env: **`davinci-monet`**. Surface install requests rather than silent `pip install`. Known additions needed: `pytest`, `pytest-xdist`, `statsmodels` (verify availability).
- DAVINCI-MONET work strictly on the **`ceres` branch**. Any reusable extraction lands there as scoped commits.
- Never stage data inside this repo — all reads from `~/Data/...`.

## Architecture

### Repo layout (`~/EarthSystem/FIREX/`)

```
firex/                         # Python package
  __init__.py
  masks.py                     # build/load 1°×1° regional masks (area-weighted)
  regions.py                   # region registry: name → bbox + mask file
  loaders/
    ceres_ebaf.py              # CERES EBAF Ed4.2.1 → monthly regional means
    modis_monthly.py           # MOD08_M3 + MYD08_M3 → AOD monthly means
    viirs_monthly.py           # AERDB SNPP+NOAA-20 → AOD monthly means
    merra2_monthly.py          # aer_Nx species, plus slv/flx/lnd extras
    qfed_monthly.py            # QFED daily → monthly aggregate (mass flux)
    aeronet.py                 # thin wrapper around davinci_monet's reader
  attribution.py               # smoke-fraction calc (MERRA-2 BC+OC_bb / total)
  anomaly.py                   # climatology subtraction + month-FE/trend builder
  regression.py                # OLS with month FE + trend; clear-sky and all-sky
  plots.py                     # 13 plot functions, all calling apply_ncar_style()
  cache.py                     # tidy-NetCDF read/write helpers
configs/
  pacific-northwest.yaml       # bbox, time slice, dataset paths, plot list
output/pacific-northwest/
  data/                        # tidy NetCDFs (one per dataset + merged)
  plots/                       # 13 PNGs
  logs/
  reports/                     # markdown methods/results draft
scripts/
  fetch_*.sh                   # existing fetchers, untouched
  run_pnw.py                   # orchestrator (P2 stage runner)
tests/
  fixtures/                    # synthetic NetCDFs + a build helper
  test_masks.py
  test_loaders.py
  test_attribution.py
  test_anomaly.py
  test_regression.py
  test_pipeline_smoke.py       # @pytest.mark.slow, real-data end-to-end
docs/superpowers/specs/
  2026-04-28-firex-pnw-prototype-design.md
```

### Pipeline approach (P2 — procedural with stage functions)

`scripts/run_pnw.py` orchestrates six stages. Each stage:

1. Reads disk inputs or upstream-stage NetCDFs.
2. Returns xarray Datasets in memory.
3. Writes a tidy NetCDF to `output/pacific-northwest/data/`.
4. Is independently re-runnable: skip if all inputs are older than its output unless `--force`.

Atomic writes (write to `.tmp` then rename) so Ctrl-C never leaves a half-written cache.

### CLI

```
python -m firex.run_pnw --config configs/pacific-northwest.yaml \
       [--stages 1,2,3,4,5,6] [--force] [--end 2025-12]
```

### Code-reuse plan

- **Plotting:** call `davinci_monet.plots.style.apply_ncar_style(context="publication")` once in `firex.plots`. Reuse `PlotConfig` if it fits; otherwise wrap.
- **AERONET:** `davinci_monet.observations.surface.aeronet.AERONETReader`/`open_aeronet` is reused as-is via thin `firex/loaders/aeronet.py` adapter.
- **Reusable extractions toward davinci_monet (`ceres` branch only):** monthly EBAF loader, regional-mask helper, monthly QFED loader. Done as separate scoped commits, not a single dump. Promotion happens once a stage is stable, not preemptively.

## Pipeline stages

### Stage 1 — Build regional mask

- Input: bbox from config.
- Output: `data/mask.nc` — 1°×1° boolean mask + area-weight (`cos(lat)·dlat·dlon`) on the CERES EBAF grid.

### Stage 2 — Per-dataset monthly regional means

One file per dataset, all on shape `(time,)`. Schema is uniform: monthly time coord, variables named `<dataset>_<var>`.

| File | Variables |
|---|---|
| `data/ceres_ebaf.nc` | TOA + SFC SW/LW/Net, both clear-sky and all-sky; cloud fraction |
| `data/modis_terra.nc` | `Aerosol_Optical_Depth_Land_Ocean_Mean_Mean` |
| `data/modis_aqua.nc` | as above |
| `data/viirs_snpp.nc` | AERDB AOD550 |
| `data/viirs_noaa20.nc` | AERDB AOD550 |
| `data/merra2_aer.nc` | `TOTEXTTAU`, `BCEXTTAU`, `OCEXTTAU`, `SUEXTTAU`, `DUEXTTAU`, `SSEXTTAU` |
| `data/merra2_slv.nc` | `T2M`, `TQV`, `PBLH` (covariates) |
| `data/qfed.nc` | daily-summed monthly emissions: `bc`, `oc`, `co` |
| `data/aeronet_pnw.nc` | site-level monthly AOD550 for ~3 PNW sites |

Each loader: open dataset → spatial subset → apply mask + area-weight → time-aggregate to monthly.

### Stage 3 — Smoke attribution

- Inputs: `merra2_aer.nc`, `modis_terra.nc`, `modis_aqua.nc`, `viirs_snpp.nc`, `viirs_noaa20.nc`, `qfed.nc`.
- Compute:
  ```
  smoke_fraction = (BCEXTTAU + OC_bb_share · OCEXTTAU) / TOTEXTTAU
  smoke_AOD_obs  = smoke_fraction × AOD_obs
  ```
- `OC_bb_share` from `aer_Nx` if it carries the bb split; otherwise from `QFED_OC / (QFED_OC + DJF_baseline_OC)`, where `DJF_baseline_OC` is the per-gridcell mean of MERRA-2 `OCEXTTAU` over Dec/Jan/Feb across the full record (proxy for non-fire-season — i.e. anthropogenic + biogenic — OC). Fallback path emits a `WARNING` and writes `oc_split_method=fallback` on the output.
- `smoke_AOD_obs` computed against each of MODIS Terra (primary), MODIS Aqua, VIIRS-SNPP, and VIIRS-NOAA20 — stored as separate variables (e.g., `smoke_aod_terra`, `smoke_aod_noaa20`).
- Output: `data/smoke_attribution.nc`.

### Stage 4 — Merge + anomalies

- Merge all stage-2 outputs + stage-3 attribution into `data/merged.nc` on common monthly time axis.
- For each variable, add `<var>_anom = <var> − climatology(<var>)`, where climatology = month-of-year mean over full record.

### Stage 5 — Regression

For each radiative response `F ∈ {F_TOA_SW_clr, F_TOA_SW_all, F_SFC_SW_clr, F_SFC_SW_all, F_TOA_LW_*, F_SFC_LW_*, F_TOA_Net_*, F_SFC_Net_*}`:

```
F = α + β·smoke_AOD + γ·cloud_fraction + δ·TQV + month_FE + linear_trend·t + ε
```

- statsmodels OLS with HAC (Newey-West) standard errors.
- Output: `data/regression_table.nc` (coeffs, SEs, t-stats, R²) + `data/regression_table.csv`.

### Stage 6 — Plots

- Inputs: `data/merged.nc` + `data/regression_table.nc`.
- Generate 13 PNGs into `output/pacific-northwest/plots/` at 300 dpi.

## Plot inventory

NCAR palette (obs gray, model blue, accents orange/aqua). Every caption includes date range, region bbox, and a methods string. Slope annotations on scatter plots show `β ± SE [W m⁻² per AOD]`, n, R².

| # | Slug | Type | Content |
|---|---|---|---|
| 1 | `aod_total_timeseries` | Multi-line monthly | MODIS Terra + Aqua + VIIRS-SNPP + VIIRS-NOAA20; AERONET site means as scatter dots |
| 2 | `smoke_fraction_timeseries` | Single-line monthly | MERRA-2-derived smoke fraction |
| 3 | `smoke_aod_timeseries` | Multi-line monthly | smoke AOD per obs source; ribbon for inter-platform spread |
| 4 | `ceres_toa_anomaly` | 3-panel monthly | SW / LW / Net TOA anomaly; all-sky and clear-sky overlaid |
| 5 | `ceres_sfc_anomaly` | 3-panel monthly | SW / LW / Net SFC anomaly; all-sky + clear-sky |
| 6 | `scatter_dF_TOA_vs_smoke` | 2-panel scatter | clear-sky \| all-sky; ΔF_TOA_SW vs. smoke_AOD; OLS line + slope ± SE |
| 7 | `scatter_dF_SFC_vs_smoke` | 2-panel scatter | as #6 but for SFC SW |
| 8 | `seasonal_climatology` | 12-bar monthly | calendar-month mean of smoke_AOD and ΔF_TOA_SW (clear-sky) |
| 9 | `spatial_maps_peak_year` | 2×2 cartopy | rows = climatology / peak-year anomaly; cols = smoke_AOD / ΔF_TOA_SW_clr; PNW box outlined |
| 10 | `qfed_emissions_timeseries` | 3-panel monthly | BC / OC / CO; secondary-axis smoke_AOD overlay |
| 11 | `aeronet_vs_modis_scatter` *(opt)* | Scatter | per-site monthly AOD: AERONET vs. MODIS gridcell; 1:1 line |
| 12 | `cloud_fraction_timeseries` *(opt)* | Single-line monthly | covariate sanity check |
| 13 | `merra2_obs_scaling` *(opt)* | Scatter+ratio | MERRA-2 TOTEXTTAU vs. MODIS AOD; ratio time-series inset |

**Peak fire year (#9):** auto-picked as the calendar year with the largest annual-mean QFED OC emission inside the PNW box. Logged; overrideable in config.

## Error handling

**Boundary trust model:** validate at the system boundary (file presence, expected variables, non-empty monotonic time axis) and then trust contents. NaN fields are real data, not errors. Hard-fail with a clear message rather than silently fall back.

**Specific edge cases:**

1. **MERRA-2 stream codes** — files may carry stream codes 100/200/300/400/401 for the same year/month. Loader globs and selects the highest-numbered stream available; logs the choice.
2. **MERRA-2 OC bb-split absence** — if `OCEXTTAU_bb` is absent in `aer_Nx`, fall back to `OC_bb_share = QFED_OC / (QFED_OC + DJF_baseline_OC)`, where `DJF_baseline_OC` is the per-gridcell DJF mean of MERRA-2 `OCEXTTAU` over the full record. Emits a `WARNING` and writes `oc_split_method=fallback` on `data/smoke_attribution.nc`.
3. **VIIRS-NOAA20 starts 2018** — pre-2018 months are legitimately NaN; downstream code tolerates.
4. **Y2016 QFED skipped** (per CLAUDE.md) — loader hard-skips with a logged note; QFED time-series has 12 NaNs; regression drops those rows.
5. **MODIS Terra start** — common-record start computed as `max(dataset_start)`; CERES EBAF (2000-03) drives it.
6. **CERES EBAF rolling granule** — loader reads the latest `Edition4.2.1_200003-{YYYYMM}.nc` it finds; logs the granule end-month.
7. **AERONET sparse sites** — sites with <12 monthly samples are dropped from validation plots with a logged note.

**Logging:**

- One per-run log file at `output/pacific-northwest/logs/run_{timestamp}.log` (Python `logging`, level `INFO`).
- Stage start/end with elapsed seconds; per-loader input file count and time range; warnings on fallback paths (#2, #4, #7).
- Header records git SHA of `~/EarthSystem/FIREX/`, `davinci_monet.__version__`, conda env name, resolved bbox, time slice.

**Idempotency:**

- Stage skips itself if all input files are older than its output (mtime-based) unless `--force`.
- Atomic writes via `.tmp` + rename.

## Testing

`pytest`. Default `pytest tests/` runs without internet and without reading `~/Data/`.

| File | Coverage |
|---|---|
| `test_masks.py` | bbox → mask correctness; area-weight sums; lat/lon ordering invariance; mask written/read round-trip |
| `test_loaders.py` | one synthetic-NetCDF fixture per dataset; assert returned shape + variable names; expected-failure cases for missing variables and empty time axis |
| `test_attribution.py` | smoke fraction with known inputs; OC bb-split fallback path triggers when `OCEXTTAU_bb` absent; fallback flag set on output |
| `test_anomaly.py` | climatology subtraction over a synthetic seasonal cycle; trend term recovery |
| `test_regression.py` | OLS recovers known β within 2 SE on synthetic data; HAC SEs nonzero; month FE coefficients sum to ~0 |
| `test_pipeline_smoke.py` | `@pytest.mark.slow`; runs all 6 stages on a 24-month subset of real `~/Data/...`; asserts each output NetCDF exists with non-empty time axis |

**Fixtures:** `tests/fixtures/*.nc`, generated by `tests/fixtures/build_fixtures.py` (committed alongside, regeneratable).

**Tooling install:** `pytest`, `pytest-xdist`, `statsmodels` into the `davinci-monet` env. Lint/format follow whatever davinci_monet's `pyproject.toml` already defines (mirror, don't re-pick).

**CI:** out of scope. Local-run only.

## Defaults locked in this spec (overridable in config)

| Setting | Default | Rationale |
|---|---|---|
| Region bbox | 42–52°N, 130–110°W | PNW states + offshore receptor extension |
| Time slice end | most-recent EBAF granule (2025-12 today) | constrained by CERES EBAF rolling granule |
| Primary radiative metric | clear-sky (with all-sky carried side-by-side) | direct-effect interpretability |
| Anomaly handling | hybrid (climatology-subtracted for plots; raw + month FE + trend in regression) | intuitive plots, statistically clean regression |
| Smoke-fraction obs source for primary plot | MODIS Terra | longest record overlapping CERES EBAF |
| OC bb-share fallback | QFED-ratio with DJF-climatology anthro estimate | only invoked if `aer_Nx` lacks `OCEXTTAU_bb` |
| Peak fire year | auto-picked from QFED OC emissions | logged; overrideable |

## Open items deferred to implementation

- Final variable-name mapping for CERES EBAF (the file has 247 variables across TOA/SFC and clear-sky/all-sky pairs); to be discovered while writing `loaders/ceres_ebaf.py` against the staged file.
- Exact AERONET site list inside the PNW bbox — drawn from `~/Data/AeroNet/` at load time; expected to include Trinidad Head, Bondville (just outside), Railroad Valley.
- Whether `OCEXTTAU_bb` is present in `MERRA2_*.tavgM_2d_aer_Nx*.nc4` — checked at first run; determines whether fallback is exercised.

## References

- [`FIREX.md`](../../../FIREX.md) — study methodology
- [`CLAUDE.md`](../../../CLAUDE.md) — data staging and conventions
- DAVINCI-MONET branch `ceres` — `davinci_monet/plots/{style,base}.py`, `davinci_monet/observations/surface/aeronet.py`, `analyses/ceres-smoke/configs/west-coast-2020-gemini.yaml` (prior daily-event prototype)
