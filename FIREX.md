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
- **Regions:** TBD; first candidate is **Pacific Northwest** (heavy seasonal smoke, mid-latitude, well-instrumented). Other candidates worth visiting: California, Boreal Canada, Boreal Russia / Siberia, Amazon, Indonesia/Maritime Continent, Southeast Australia, Southern Africa.
- **Spatial scale:** regional monthly means (single time series per region) is the primary unit. 1°×1° gridded fields are the working layer; regional masks aggregate to time series.
- **Boundaries:** TBD — leaning on standard fire-research regions (GFED14 basis regions are a common choice and aligned with the literature) supplemented by U.S.-specific MTBS-aligned regions.

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

MERRA-2 ingests QFED as its biomass-burning emission and runs full transport/aging chemistry. We trust MERRA-2's *fractional* species split more than its absolute AOD. So:

```
smoke_fraction(t, x, y)  =  (BCEXTTAU + OCEXTTAU_bb) / TOTEXTTAU
smoke_AOD_obs(t, x, y)   =  smoke_fraction × MODIS_AOD_observed
```

with `OCEXTTAU_bb` = the biomass-burning portion of total OC AOD. MERRA-2 separates anthropogenic vs. biomass-burning OC in some collections; if the monthly `aer` we have doesn't carry the split, fall back to using QFED's local OC:BC emission ratio to apportion MERRA-2 OC.

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
