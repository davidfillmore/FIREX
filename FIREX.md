# FIREX — Regional Radiative Effects of Wildfire Smoke, CERES Record

Methodology notes. Companion to `CLAUDE.md` (which documents data staging, fetchers, and conventions). This file describes *what* we are doing scientifically; `CLAUDE.md` describes *how* the data is laid out.

## Study question

Quantify the regional radiative effect of wildfire-smoke aerosol at TOA and the surface, on monthly time scales, over the CERES observational record (2000-03 → present).

Key quantities we want to produce per region:
- Total AOD (observed) and smoke-AOD fraction.
- Anomalous TOA and SFC SW (and net) radiative response, regressed on smoke-AOD.
- Cloud / meteorological state co-variation, to separate smoke from confounders.

## Study domain

- **Time:** 2000-03 → present, monthly. Constrained by CERES EBAF start.
- **Spatial scale:** regional monthly means (single time series per region) is the primary unit. 1°×1° gridded fields are the working layer; regional masks aggregate to time series.
- **Regions:** the registry below covers the major biomass-burning biomes globally. Three are *featured* — the story arc for the current presentation; the others are defined for future analysis. Bboxes are loose enough to capture transport receptors as well as source areas. Definitive entries live in `firex/regions.py`; this table mirrors them.

| Region | bbox (lon, lat) | Featured | Notes |
|---|---|:---:|---|
| pacific-northwest | 130°W–110°W, 42°N–52°N | ★ | 2017 / 2018 / 2020 / 2021 fire seasons |
| eastern-canada | 90°W–65°W, 48°N–58°N | ★ | 2023 Quebec/Ontario record boreal season; smoke into eastern US |
| eastern-australia | 140°E–154°E, 44°S–25°S | ★ | 2019-20 Black Summer (VIC/TAS/NSW/ACT/SE-QLD) |
| western-canada | 130°W–105°W, 52°N–62°N |  | 2023 NWT/BC; Yellowknife evacuation |
| alaska | 165°W–141°W, 60°N–72°N |  | 2004 record season, 2022 boreal |
| california | 124°W–114°W, 32°N–42°N |  | 2018 Camp; 2020 Creek and August Complex |
| eastern-siberia | 110°E–155°E, 55°N–72°N |  | 2019 / 2021 Yakutia megafires |
| central-africa | 15°E–35°E, 15°S–5°N |  | World's largest savanna BB region by area |
| amazon | 75°W–50°W, 15°S–5°S |  | Deforestation arc; 2019 / 2023 events |
| maritime-se-asia | 95°E–120°E, 5°S–5°N |  | Indonesian peat fires; 2015 ENSO event |
| northern-australia | 125°E–145°E, 20°S–10°S |  | Annual dry-season savanna burning |
| mediterranean | 10°W–30°E, 35°N–45°N |  | Recurring Greece / Spain / Portugal fires |

## Dataset roles

The dataset table in `CLAUDE.md` is the canonical source-of-truth for paths and provenance. Roles for *this* study:

| Role | Dataset(s) | Status |
|---|---|---|
| **Radiative response** (TOA + SFC SW/LW/net, monthly 1°) | CERES EBAF Ed4.2.1 | staged |
| **Total AOD, observed** | MODIS Terra MOD08_M3 + Aqua MYD08_M3 monthly L3; VIIRS AERDB monthly L3 (SNPP + NOAA-20) | staged |
| **Speciated AOD** (BC, OC, sulfate, dust, sea salt) | MERRA-2 monthly `aer_Nx` | staged |
| **Biomass-burning emissions** | QFED v2.6r1 daily (aggregate to monthly); GFED4.1s monthly (cross-check) | QFED staged; GFED *candidate* |
| **Independent burned-area record** | MCD64A1 monthly | candidate |
| **Surface AOD validation** | AERONET monthly site files | staged |
| **Meteorological / cloud context** | MERRA-2 `slv` + `flx` + `lnd`; CERES EBAF cloud aux | `aer`+`rad` staged; others *candidate* |
| **Smoke attribution cross-check** | OMI/OMPS UV Aerosol Index | candidate |
| **Vertical structure** (case studies) | CALIPSO/CALIOP, MISR plume height | candidate |

## Smoke-AOD attribution

Total observed AOD includes smoke + dust + sulfate + sea salt + nitrate. To isolate the smoke component we use a layered approach:

### Primary: MERRA-2 speciated AOD, scaled to observations

MERRA-2 ingests QFED as its biomass-burning emission and runs full transport/aging chemistry. We trust MERRA-2's *fractional* species split more than its absolute AOD. The `aer_Nx` collection exposes only species totals (`BCEXTTAU`, `OCEXTTAU`, …) — there is no built-in biomass-burning split — so we approximate the smoke contribution with a per-month-of-year background subtraction:

```
BC_bg(m)              =  10th-percentile of BCEXTTAU across all years for calendar month m
OC_bg(m)              =  10th-percentile of OCEXTTAU across all years for calendar month m
smoke_AOD_merra2(t)   =  max(0, BCEXTTAU(t) − BC_bg) + max(0, OCEXTTAU(t) − OC_bg)
smoke_fraction(t)     =  smoke_AOD_merra2(t) / TOTEXTTAU(t),   clipped to [0, 1]
smoke_AOD_obs(t)      =  smoke_fraction × AOD_observed
```

With ~26 yr of monthly data the 10th percentile is the ~3rd-lowest year per calendar month — a robust proxy for the non-fire (anthropogenic + biogenic SOA) baseline. The method:

- is dimensionally honest (AOD − AOD; the earlier QFED-emission-flux fallback mixed kg m⁻² s⁻¹ with unitless AOD and collapsed `smoke_fraction` to BC/TOT — Sept 2020 PNW read 0.08 instead of ~0.81);
- works in either hemisphere because the baseline is computed per region and per calendar month, so it tracks the local biogenic-OA seasonal cycle (DJF ≠ no-fire in EAU);
- treats both BC and OC excess as smoke, which is appropriate for combustion-dominated fire events.

This anchors the smoke time series in observed AOD while using MERRA-2 only for the speciation step.

### Sanity check: emissions → AOD mass balance

Coarse box-model translation of QFED emissions to AOD:

```
AOD_smoke ≈ E × τ × MEE / column_factor
```

with E = emission flux (kg m⁻² s⁻¹), τ = aerosol residence time (~7 days fine-mode BB aerosol), MEE = mass extinction efficiency at 550 nm (~3–5 m² g⁻¹ for fresh BB). Useful as a methods-section sanity check; ignores transport so it under-predicts in receptor regions and over-predicts in source regions.

### Cross-check: UV Aerosol Index partitioning

OMI/OMPS UVAI is high for absorbing aerosols (smoke, dust). In regions where dust is small (Pacific NW, Boreal, Amazon), high-UVAI AOD anomalies are a clean smoke indicator independent of any model or emission inventory. Use as an out-of-sample test of the MERRA-2-based smoke fraction.

## Radiative-effect estimation

For each region, build a monthly time series of:
- `ΔF_TOA`, `ΔF_SFC` (anomalies in CERES SW, LW, net fluxes)
- `smoke_AOD` (from the attribution step above)
- co-variates: cloud fraction, water vapor (TQV), surface albedo, low/high cloud split

Fit:
```
ΔF = a + b · smoke_AOD + c · cloud_fraction + d · TQV + (other controls) + ε
```

Coefficient `b` (W m⁻² per unit AOD) is the regional radiative-efficiency of smoke.

Open methodological choices:
- Linear regression vs. partial-correlation / multi-variate ridge.
- Whether to detrend / deseasonalize first, or include month-of-year fixed effects.
- All-sky vs. clear-sky CERES (cloud-aerosol interactions complicate interpretation in all-sky).
- Lagged AOD (smoke days persist into following month) — revisit after looking at autocorrelation.

## Validation

- **AOD:** AERONET site-level monthly means against MODIS/VIIRS gridcell containing the site. Pacific NW priority sites: Trinidad Head, Bondville, Railroad Valley.
- **Surface SW↓:** SURFRAD sites (Boulder, Desert Rock, etc.) against CERES SFC SW↓.
- **Smoke fraction:** cross-check MERRA-2-based smoke fraction against UVAI-based independent estimate.

## Pipeline (intended)

1. Build regional masks (NetCDF, 1°×1°, weighted by area). One file per region.
2. Aggregate each gridded dataset to monthly regional means → tidy NetCDF (region × time × variable). One file per dataset.
3. Merge into a single analysis NetCDF per region (region × time × all variables).
4. Compute smoke-AOD attribution per region.
5. Anomaly / regression analysis → radiative-efficiency table.
6. Plotting & paper figures.

Repo layout for analysis code is TBD; current `scripts/` holds only data-transfer scripts.

## Open items / decisions

- Which regions, finalised list. (default: GFED14 basis regions + Pacific NW custom box.)
- MERRA-2 OC anthropogenic vs. biomass-burning split — confirm whether `aer_Nx` carries it; if not, decide on the QFED-ratio fallback.
- Whether to add GFED4.1s (top candidate) before starting analysis or after the first MERRA-2-only pass.
- Clear-sky vs. all-sky as the primary radiative metric.
- Cut-off year for the "current" record — if we draft mid-2026, do we use through 2025-12 (CERES EBAF current granule) or wait for the next refresh.
