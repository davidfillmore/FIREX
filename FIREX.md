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
- **Regions:** the registry below covers the major biomass-burning biomes globally. Four are *featured* — the story arc for the current presentation; the others are defined for future analysis. Bboxes are loose enough to capture transport receptors as well as source areas. Definitive entries live in `firex/regions.py`; this table mirrors them.

| Region | bbox (lon, lat) | Featured | Notes |
|---|---|:---:|---|
| pacific-northwest | 130°W–110°W, 42°N–52°N | ★ | 2017 / 2018 / 2020 / 2021 fire seasons |
| eastern-canada | 90°W–65°W, 48°N–58°N | ★ | 2023 Quebec/Ontario record boreal season; smoke into eastern US |
| eastern-australia | 140°E–154°E, 44°S–25°S | ★ | 2019-20 Black Summer (VIC/TAS/NSW/ACT/SE-QLD) |
| western-canada | 130°W–105°W, 52°N–62°N |  | 2023 NWT/BC; Yellowknife evacuation |
| alaska | 165°W–141°W, 60°N–72°N |  | 2004 record season, 2022 boreal |
| california | 124°W–114°W, 32°N–42°N |  | 2018 Camp; 2020 Creek and August Complex |
| eastern-siberia | 110°E–155°E, 55°N–72°N | ★ | 2019 / 2021 Yakutia megafires |
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

MERRA-2 ingests QFED as its biomass-burning emission and runs full transport/aging chemistry. We use MERRA-2 for an internally consistent *fractional* species split, while anchoring the final smoke-AOD magnitude to observed MODIS/VIIRS AOD. The `aer_Nx` collection exposes only species totals (`BCEXTTAU`, `OCEXTTAU`, …) — there is no built-in biomass-burning split — so we approximate the smoke contribution with a per-month-of-year background subtraction:

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

### Caveat: monthly-mean regression vs. per-event radiative efficiency

The β we report is the OLS regression slope between monthly-mean smoke AOD and monthly-mean ΔF. That is not the same quantity as a per-day or per-hour direct radiative-efficiency. Three places this matters:

- **Aggregation bias.** If the AOD↔ΔF relationship is at all nonlinear (saturation at high optical depth, sec(θ)-driven solar-zenith dependence, surface-albedo modulation), then `mean(f(x)) ≠ f(mean(x))`. Within-month variance is high during fire months — a 5-day plume embedded in 25 clean days — so the monthly mean dilutes both AOD and ΔF, and our β is a regression of dilution against dilution. Tends to bias β low relative to peak-day β.
- **Literature comparison.** Published clear-sky surface DRE efficiency for biomass-burning aerosol is typically −50 to −70 W m⁻² per AOD; our PNW/EAU values of ~ −40 sit slightly low, consistent with monthly-aggregation dampening.
- **Communication.** Frame β in the talk as a "monthly-aggregated regression slope," not a per-event radiative efficiency. The two have different physical meanings even when the linear approximation is good.

### Mitigation paths

#### 1. QFED-OC tertile split (no extra data; uses existing monthly merged.nc)

Bin months by QFED OC into low/mid/high tertiles and re-fit the OLS slope per tertile. If β shifts systematically with fire intensity, that's empirical evidence of within-month nonlinearity (saturation would make β shallower at high intensity; "purer smoke" would make it steeper).

Surface clear-sky result (W m⁻² per AOD, R² in parens, n ≈ 95 each, Y2017 QFED masked — see CLAUDE.md §Datasets):

| Region | Low QFED | Mid QFED | High QFED | All-record |
|---|---:|---:|---:|---:|
| Pacific Northwest | −33 (0.02)* | −77 (0.19)* | **−44 (0.64)** | −39 (0.44) |
| Eastern Australia | −278 (0.30)* | −218 (0.28)* | **−45 (0.31)** | −42 (0.15) |

\* Low/mid tertile slopes are unstable: the within-tertile smoke-AOD range is too narrow to fit reliably and the slopes wander widely (±50 W m⁻² per AOD) between specifications. Treat the high-tertile slope as the credible number.

Two takeaways: (i) the signal lives in fire-active months; (ii) high-intensity β is *steeper* than overall β, which rules out saturation/concavity as the dominant nonlinearity (plausibly the smoke fraction is "cleaner" at high intensity, less contaminated by non-smoke AOD).

#### 2. Daily-QFED duty-cycle correction (uses staged daily QFED)

For each top fire month, compute an effective active-day fraction `f_eff` from the daily QFED OC time series using a Herfindahl-style concentration index:

```
p_d   = q_d / Σ q   (daily emission share)
H     = Σ p_d²       (Herfindahl index)
f_eff = (1/H) / n_days
```

`f_eff = 1` for uniform emission, small for one big day. If we then assume the per-day response is `ΔF = β_event · A^p` with `p ∈ [0.8, 1.0]`, monthly aggregation gives:

```
β_naive = β_event · (mean A within month)^(p-1)
       ≈ β_event · f_eff^(1-p)        (assuming AOD ∝ daily emission)
```

so `β_event = β_naive · (1/f_eff)^(1-p)`.

Median `f_eff` across the labeled top fire months: **0.58 (PNW), 0.50 (EAU)**. Bracket on the corrected surface clear-sky efficiency:

| Region | p=1.00 | p=0.95 | p=0.90 | p=0.85 | p=0.80 |
|---|---:|---:|---:|---:|---:|
| PNW | −39 | −40 | −41 | −43 | −44 |
| EAU | −43 | −44 | −46 | −47 | −49 |

The correction is modest (a few W m⁻² per AOD) for plausible p; published per-event values of −50 to −70 are not reached without a stronger nonlinearity assumption *or* moving to daily data.

#### 3. Daily data (future work)

CERES SYN1deg (daily 1° SW) + MODIS L3 daily AOD + daily MERRA-2. Non-trivial loader + storage work; QFED is already daily on disk. A scoped first pass would target a single fire-active year per region (e.g. 2020 PNW, 2019-20 EAU) to compute per-event β directly.

### Other open methodological choices

- Linear regression vs. partial-correlation / multi-variate ridge.
- Whether to detrend / deseasonalize first, or include month-of-year fixed effects.
- All-sky vs. clear-sky CERES (cloud-aerosol interactions complicate interpretation in all-sky; cloud-fraction residualization in the current pipeline tightens the time series cosmetically but does not recover a clean smoke signal in the smoke-vs-ΔF scatter).
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
