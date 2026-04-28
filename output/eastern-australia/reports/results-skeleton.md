# FIREX — Eastern Australia results (draft skeleton)

**Run date:** 2026-04-28
**Time range:** 2000-03 → 2025-12 (CERES EBAF Ed4.2.1 record)
**Region bbox:** 25–44°S, 140–154°E (VIC, TAS, NSW, ACT, SE Qld + Great Dividing Range)
**Granule:** `CERES_EBAF_Edition4.2.1_200003-202512.nc` (310 monthly fields)
**Pipeline SHA:** e6d3c19 (region addition) + plot guard for empty-AERONET path
**Headline event:** "Black Summer" 2019-2020 bushfires (peak Dec 2019 – Jan 2020)

## Methods (one paragraph)

Same pipeline as Pacific Northwest — see `output/pacific-northwest/reports/results-skeleton.md` for full methods. One **important caveat** specific to this region: the smoke-fraction QFED-OC fallback uses DJF months as the "fire-quiescent" baseline for the anthropogenic + biogenic OC background. That's true for PNW (boreal winter) but **inverted** for SE Australia, where DJF is the austral summer fire season. The DJF baseline OC computed here (2.46 × 10⁻²) is roughly 2× the PNW value (1.28 × 10⁻²), almost certainly because it's contaminated with fire-OC, which **biases smoke_fraction low** here. Replacing the fallback with an austral-fire-quiescent baseline (e.g. JJA mean) — or, better, fetching MERRA-2 with explicit `OCEXTTAU_bb` — should be done before drawing strong quantitative conclusions from the AU smoke_fraction time series.

## Headline numbers (β = W m⁻² per unit smoke AOD; n = 298, 2000-03 → 2025-12)

| Response | β | SE | p | Notes |
|---|--:|--:|--:|---|
| TOA SW clear-sky | **+442.8** | 53.0 | 6.5 × 10⁻¹⁷ | ~2× the PNW magnitude |
| TOA SW all-sky | −0.7 | 93.2 | 0.99 | clouds buffer entirely |
| TOA LW clear-sky | +126.5 | 44.2 | 4.2 × 10⁻³ | LW response present |
| TOA Net clear-sky | **−573.1** | 50.9 | 2.0 × 10⁻²⁹ | strong cooling |
| TOA Net all-sky | −184.4 | 78.1 | 1.8 × 10⁻² | |
| SFC SW↓ clear-sky | −498.9 | 66.6 | 6.6 × 10⁻¹⁴ | ~PNW magnitude |
| SFC SW↓ all-sky | +39.1 | 101.3 | 0.70 | inverted (cloud–smoke covariance) |
| SFC Net clear-sky | **−1053.4** | 106.3 | 3.8 × 10⁻²³ | ~2× PNW |
| SFC Net all-sky | −481.3 | 93.0 | 2.3 × 10⁻⁷ | |

### Comparison to Pacific Northwest

The clear-sky signals are physically consistent with both regions but **larger over AU**, especially TOA SW (+443 vs +210) and SFC Net (−1053 vs −464). Plausible drivers:
- Black Summer's exceptional smoke loading (very high AOD), with plumes reaching the lower stratosphere — extends the regression range and strengthens the slope.
- AU's drier atmosphere and lower mean cloud fraction → larger fraction of months where the clear-sky regime is the dominant aerosol pathway.
- AU's stronger surface albedo contrast across the bbox (arid interior + ocean) → larger SFC Net response per unit AOD.

The all-sky channels are **drastically more buffered** over AU than PNW — TOA SW all-sky is essentially zero, SFC SW↓ all-sky flips sign. Likely cloud–smoke anticorrelation: heavy fire days are also typically clear-sky days (no clouds for smoke to contend with), so cloud-fraction anomalies are negatively correlated with smoke AOD anomalies. The all-sky regression confounds the two unless cloud fraction is in the design — which it is, but the buffering remains.

## Figures

_All in `output/eastern-australia/plots/`._

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
| 11 | `aeronet_vs_modis_scatter.png` | _no AERONET sites loaded — placeholder annotation; see follow-up_ |
| 12 | `cloud_fraction_timeseries.png` | Cloud-fraction covariate |
| 13 | `merra2_obs_scaling.png` | MERRA-2 vs. MODIS magnitude check |

## Open follow-ups

- **DJF baseline is wrong for AU.** The QFED-OC fallback in `firex/attribution.py` uses a hard-coded DJF mean as the "quiescent OC background." That assumption is correct for boreal-winter regions (PNW) but inverted for SE Australia (DJF = austral summer = peak fire season). The reported smoke_fraction here is biased low. Either (a) parametrize the quiescent months per region (`cfg["attribution"]["quiescent_months"]: [6, 7, 8]` for AU), (b) compute a per-region quiescent window from QFED itself (months with bottom-quartile OC emissions), or (c) replace the fallback with explicit MERRA-2 `OCEXTTAU_bb` (M2T1NXAER tagged tracers, daily) to remove the assumption entirely.
- **AERONET loader doesn't align by site across files.** `firex/loaders/aeronet.py` concats monthly AeroNet_*.nc files along time. The non-time `x` dimension is preserved column-by-column, but the column ordering of sites isn't stable across the 25-year file series (sites are added/removed). The `_per_site` first-non-NaN lat/lon lookup ends up reading wrong values for columns that change identity over time, so the bbox filter dropped all 3 SE Australia sites (Aspendale_Mel_AU, Fowlers_Gap, Tumbarumba) that are present in the 2020-01 source file. Fix: align files by `siteid` before concat (build a master site index, reindex each file onto it, then concat with NaN padding).
- **Same outputs as PNW carry over:** spatial maps require a gridded merge (not yet wired); cfg time-window is ignored; multi-region generalization needs broader regions.yaml; UVAI cross-check pending.
- **Stage 2 AERONET filename is hardcoded `aeronet_pnw.nc`** in the orchestrator regardless of region. Cosmetic (filename has region in path), but worth renaming to `aeronet.nc`.
