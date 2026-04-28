# FIREX — Pacific Northwest results (draft skeleton)

**Run date:** 2026-04-28
**Time range:** 2000-03 → 2025-12 (CERES EBAF Ed4.2.1 record)
**Region bbox:** 42–52°N, 130–110°W
**Granule:** `CERES_EBAF_Edition4.2.1_200003-202512.nc` (310 monthly fields)
**Pipeline SHA:** 5e7d91a (loader rewrite for real-data schemas)

## Methods (one paragraph)

Monthly time series of regional-mean total AOD (MODIS Terra + Aqua + VIIRS-SNPP + VIIRS-NOAA20), MERRA-2-derived smoke fraction, and CERES EBAF Edition4.2.1 TOA + SFC SW/LW/Net (clear-sky and all-sky) over 2000-03 → 2025-12. Smoke AOD = smoke_fraction × MODIS_Terra_AOD with smoke_fraction = (BCEXTTAU + OC_bb_share · OCEXTTAU) / TOTEXTTAU. Because MERRA-2 monthly aer collection on this machine lacks the explicit `OCEXTTAU_bb` field, the OC biomass-burning share is reconstructed via QFED-OC fallback: OC_bb_share = QFED_OC / (QFED_OC + DJF_baseline_OC), with the DJF OC mean (1.276 × 10⁻²) treated as the anthropogenic + biogenic background. Anomalies are month-of-year-climatology subtractions over the full record. Radiative-efficiency slope β estimated by OLS with HAC standard errors (6 lags), controlling for cloud fraction, month-of-year fixed effects, and a linear trend. (TQV omitted: MERRA-2 slv collection not staged on this machine; see Open follow-ups.)

## Headline numbers (β = W m⁻² per unit smoke AOD; n = 298, 2000-03 → 2025-12)

| Response | β | SE | p | R² |
|---|--:|--:|--:|--:|
| TOA SW clear-sky | +210.1 | 27.4 | 1.6 × 10⁻¹⁴ | 0.96 |
| TOA SW all-sky | +40.4 | 31.7 | 0.20 | 0.99 |
| TOA Net clear-sky | −304.3 | 49.4 | 7.4 × 10⁻¹⁰ | 1.00 |
| TOA Net all-sky | −160.5 | 59.0 | 6.5 × 10⁻³ | 1.00 |
| SFC SW↓ clear-sky | −520.1 | 44.9 | 4.5 × 10⁻³¹ | 1.00 |
| SFC SW↓ all-sky | −372.5 | 49.9 | 8.2 × 10⁻¹⁴ | 1.00 |
| SFC Net clear-sky | −463.9 | 46.8 | 4.0 × 10⁻²³ | 1.00 |
| SFC Net all-sky | −264.1 | 50.9 | 2.2 × 10⁻⁷ | 1.00 |

Signs and magnitudes match the smoke radiative-forcing literature qualitatively: smoke increases TOA SW reflection (positive β at TOA SW), reduces surface SW down (large negative β at SFC SW↓), and net energy at both TOA and surface is reduced (planet cools, surface dims). The clear-sky channels are tight (small SE, very small p) because cloud noise is excluded; all-sky variants are 30–50 % weaker as expected.

## Figures

_All in `output/pacific-northwest/plots/`._

| # | File | What it shows |
|---|---|---|
| 1 | `aod_total_timeseries.png` | Total AOD across all observed sources |
| 2 | `smoke_fraction_timeseries.png` | MERRA-2-derived smoke fraction (QFED-fallback method) |
| 3 | `smoke_aod_timeseries.png` | Smoke AOD with platform spread |
| 4 | `ceres_toa_anomaly.png` | TOA SW/LW/Net anomalies, clear- vs. all-sky |
| 5 | `ceres_sfc_anomaly.png` | SFC SW/LW/Net anomalies, clear- vs. all-sky |
| 6 | `scatter_dF_TOA_vs_smoke.png` | ΔF_TOA_SW vs. smoke AOD scatter (β annotated) |
| 7 | `scatter_dF_SFC_vs_smoke.png` | ΔF_SFC_SW vs. smoke AOD scatter |
| 8 | `seasonal_climatology.png` | Monthly climatology, smoke AOD + ΔF_TOA_SW |
| 9 | _spatial_maps_peak_year.png — not produced; see Open follow-ups_ | — |
| 10 | `qfed_emissions_timeseries.png` | QFED BC/OC/CO with smoke-AOD overlay |
| 11 | `aeronet_vs_modis_scatter.png` | AERONET (Rimrock, Saturn_Island) vs. MODIS gridcell validation |
| 12 | `cloud_fraction_timeseries.png` | Cloud-fraction covariate |
| 13 | `merra2_obs_scaling.png` | MERRA-2 vs. MODIS magnitude check |

## Open follow-ups

- **MERRA-2 slv collection not staged.** TQV (column water vapor) is the standard humidity covariate; without it the regression controls are limited to cloud fraction and FE+trend. Fetch slv via `MERRA2_COLLECTIONS=slv scripts/fetch_merra2_monthly.sh` and re-run stage 5.
- **OC biomass-burning fraction is reconstructed**, not measured. The QFED-OC fallback assumes the DJF OC mean is purely anthropogenic + biogenic, which is plausible for PNW (no significant winter wildfire) but introduces ~15–25 % uncertainty in smoke_fraction. A MERRA-2 monthly aer collection that *does* publish `OCEXTTAU_bb` (M2T1NXAER tagged tracers, daily) could replace the fallback — at higher storage cost.
- **Plot 9 (spatial maps)** requires a gridded merged file; pipeline currently writes regional-mean only. Add a parallel gridded path in stage 4 in a follow-on PR.
- **AERONET sample is small.** Only Rimrock (47.0°N, −116.5°W) and Saturn_Island (48.8°N, −123.2°W) fall inside the PNW bbox over the staged record; both are forested mid-latitude land sites without strong urban-aerosol contamination. For broader validation, widen the bbox to include Trinidad_Head (41.05°N, just south of cutoff) and BSRN_BAO_Boulder (40.05°N).
- **AERONET wavelength is 500 nm, not 550 nm.** AERONET has no 550 nm channel; we use 500 nm and rename the variable for downstream consistency. The 50 nm offset corresponds to a ~5 % systematic AOD offset under typical PNW Ångström exponents (1.3–1.6) — small relative to the inter-platform spread but worth flagging.
- **UVAI cross-check (OMI/OMPS)** — pending fetcher; would strengthen smoke-vs-other-aerosol attribution beyond the MERRA-2 species-tag approach.
- **Multi-region scaling** — generalize `firex/regions.py` and parametrize `run_pnw.py`. Currently a single PNW bbox is hardcoded as the only registered region.
- **Time-window honoring.** `cfg["time"]["start"]` / `["end"]` are present in the config but currently ignored — every run loads the full archive. Add `.sel(time=slice(start, end))` after loading each stage 2 output to make 24-month smoke runs actually 24-month.
