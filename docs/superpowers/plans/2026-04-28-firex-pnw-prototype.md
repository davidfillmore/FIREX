# FIREX Pacific Northwest Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end pipeline that turns staged FIREX datasets into 13 PNG figures plus a regression table for the Pacific Northwest region over the CERES record (2000-03 → 2025-12).

**Architecture:** P2 procedural stage runner — `firex/` Python package with one module per concern (masks, loaders, attribution, anomaly, regression, plots, run_pnw orchestrator). Each stage reads/writes tidy NetCDFs in `output/pacific-northwest/data/` and is independently re-runnable (mtime-based skip + atomic writes). Plotting reuses `davinci_monet.plots.style.apply_ncar_style()` from the `ceres` branch.

**Tech Stack:** Python 3.11+, xarray, numpy, pandas, netCDF4, statsmodels, cartopy, matplotlib, pyyaml, pytest. Active conda env: `davinci-monet`.

**Spec:** `docs/superpowers/specs/2026-04-28-firex-pnw-prototype-design.md`

> **Note (2026-05):** the smoke-attribution code listings later in this plan describe the original `(BC + OC_bb_share · OC) / TOT` formulation with the `QFED_OC / (QFED_OC + DJF_baseline_OC)` fallback. That fallback was dimensionally broken (mixed kg m⁻² s⁻¹ with unitless AOD) and was replaced 2026-05 (commit `4e946cf`) by a per-month-of-year 10th-percentile baseline subtraction. See the spec §"Stage 3" for the current method. This plan is preserved as the historical record of the initial prototype.

**Conventions in this plan:**
- All `pytest` commands run from repo root (`~/FIREX/`).
- All `git` commits use this format and never skip hooks:
  ```
  git commit -m "<short>" -m "<details, optional>"
  ```
- Synthetic fixtures use ≤24 months and ≤5×5° spatial extent so they round-trip in milliseconds.
- All loader return values are `xarray.Dataset` with monthly time coord and variables prefixed by dataset short name (`ceres_*`, `modis_terra_*`, `merra2_aer_*`, `qfed_*`, `aeronet_*`).

---

## Task 0: Environment + repo skeleton

**Files:**
- Create: `firex/__init__.py`
- Create: `firex/loaders/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/__init__.py`
- Create: `configs/.gitkeep`
- Create: `output/.gitkeep`
- Create: `pyproject.toml`

- [ ] **Step 1: Verify required packages and install missing**

```bash
conda run -n davinci-monet python -c "import xarray, numpy, pandas, netCDF4, statsmodels, cartopy, matplotlib, yaml, pytest, davinci_monet; print('all imports OK')"
```

Expected: prints `all imports OK`. If any `ModuleNotFoundError`, install with:
```bash
conda run -n davinci-monet pip install pytest statsmodels pyyaml
```
Re-run the import check. Stop and surface the missing package to the user only if a required one (e.g., `davinci_monet`) is unavailable.

- [ ] **Step 2: Create skeleton directories and empty `__init__.py` files**

```bash
mkdir -p firex/loaders tests/fixtures configs output
touch firex/__init__.py firex/loaders/__init__.py tests/__init__.py tests/fixtures/__init__.py configs/.gitkeep output/.gitkeep
```

Then write `firex/__init__.py` with version stamp:

```python
"""FIREX — wildfire smoke radiative-effect analysis pipeline."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "firex"
version = "0.1.0"
description = "Pacific Northwest wildfire-smoke radiative-effects pipeline"
requires-python = ">=3.10"
dependencies = [
    "xarray",
    "numpy",
    "pandas",
    "netCDF4",
    "statsmodels",
    "cartopy",
    "matplotlib",
    "pyyaml",
    "davinci_monet",
]

[project.optional-dependencies]
test = ["pytest"]

[tool.pytest.ini_options]
markers = ["slow: end-to-end tests reading from ~/Data/"]
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["firex*"]
```

- [ ] **Step 4: Create `tests/conftest.py` with shared fixture-path helper**

```python
"""Shared pytest configuration."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to `tests/fixtures/` directory."""
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 5: Install firex package in editable mode**

```bash
conda run -n davinci-monet pip install -e .
```

Then verify:
```bash
conda run -n davinci-monet python -c "import firex; print(firex.__version__)"
```
Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add firex/ tests/ configs/ output/ pyproject.toml
git commit -m "chore: scaffold firex package and test layout"
```

---

## Task 1: Region registry

**Files:**
- Create: `firex/regions.py`
- Test: `tests/test_regions.py`

- [ ] **Step 1: Write failing test**

`tests/test_regions.py`:
```python
"""Tests for the region registry."""
import pytest

from firex.regions import REGIONS, Region


def test_pnw_default_bbox():
    pnw = REGIONS["pacific-northwest"]
    assert isinstance(pnw, Region)
    assert pnw.lon_min == -130.0
    assert pnw.lon_max == -110.0
    assert pnw.lat_min == 42.0
    assert pnw.lat_max == 52.0


def test_unknown_region_raises():
    with pytest.raises(KeyError):
        REGIONS["nonexistent"]


def test_region_contains_point():
    pnw = REGIONS["pacific-northwest"]
    assert pnw.contains(46.0, -120.0)
    assert not pnw.contains(36.0, -120.0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
conda run -n davinci-monet pytest tests/test_regions.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'firex.regions'`.

- [ ] **Step 3: Implement `firex/regions.py`**

```python
"""Region definitions for FIREX analyses."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    def contains(self, lat: float, lon: float) -> bool:
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lon_min <= lon <= self.lon_max
        )


REGIONS: dict[str, Region] = {
    "pacific-northwest": Region(
        name="pacific-northwest",
        lon_min=-130.0,
        lon_max=-110.0,
        lat_min=42.0,
        lat_max=52.0,
    ),
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
conda run -n davinci-monet pytest tests/test_regions.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/regions.py tests/test_regions.py
git commit -m "feat(regions): add Region dataclass and PNW default bbox"
```

---

## Task 2: Mask builder

**Files:**
- Create: `firex/masks.py`
- Test: `tests/test_masks.py`

- [ ] **Step 1: Write failing test**

`tests/test_masks.py`:
```python
"""Tests for regional mask construction."""
import numpy as np
import xarray as xr

from firex.masks import build_mask, save_mask, load_mask
from firex.regions import REGIONS


def test_build_mask_shape_and_dtype():
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    assert isinstance(mask, xr.Dataset)
    assert mask["mask"].dtype == bool
    assert "weight" in mask
    assert mask.sizes["lat"] == 180
    assert mask.sizes["lon"] == 360


def test_build_mask_pnw_inside_outside():
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    inside = mask["mask"].sel(lat=46.5, lon=-120.5).item()
    outside = mask["mask"].sel(lat=46.5, lon=-90.5).item()
    assert inside is True or inside == 1
    assert outside is False or outside == 0


def test_weight_positive_inside_zero_outside():
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    weight = mask["weight"]
    assert (weight.where(mask["mask"]) > 0).all()
    assert (weight.where(~mask["mask"]) == 0).all()


def test_weight_uses_cosine_latitude():
    """Higher latitudes should have smaller area-weight."""
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    inside = mask["weight"].where(mask["mask"], drop=True)
    w_low = inside.sel(lat=42.5, lon=-120.5).item()
    w_high = inside.sel(lat=51.5, lon=-120.5).item()
    assert w_low > w_high  # cos(42°) > cos(51°)


def test_save_load_roundtrip(tmp_path):
    pnw = REGIONS["pacific-northwest"]
    mask = build_mask(pnw, resolution_deg=1.0)
    path = tmp_path / "mask.nc"
    save_mask(mask, path)
    reloaded = load_mask(path)
    np.testing.assert_array_equal(mask["mask"].values, reloaded["mask"].values)
    np.testing.assert_allclose(mask["weight"].values, reloaded["weight"].values)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
conda run -n davinci-monet pytest tests/test_masks.py -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement `firex/masks.py`**

```python
"""Build and persist regional masks on the 1° CERES EBAF grid."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from firex.regions import Region


def build_mask(region: Region, resolution_deg: float = 1.0) -> xr.Dataset:
    """Build a global 1° boolean mask + cosine-latitude area weight."""
    if resolution_deg <= 0:
        raise ValueError(f"resolution_deg must be positive, got {resolution_deg}")
    lat_centers = np.arange(-90 + resolution_deg / 2, 90, resolution_deg)
    lon_centers = np.arange(-180 + resolution_deg / 2, 180, resolution_deg)

    lat2d, lon2d = np.meshgrid(lat_centers, lon_centers, indexing="ij")
    inside = (
        (lat2d >= region.lat_min)
        & (lat2d <= region.lat_max)
        & (lon2d >= region.lon_min)
        & (lon2d <= region.lon_max)
    )

    cos_lat = np.cos(np.deg2rad(lat2d))
    weight = np.where(inside, cos_lat, 0.0)

    return xr.Dataset(
        {
            "mask": (("lat", "lon"), inside),
            "weight": (("lat", "lon"), weight),
        },
        coords={"lat": lat_centers, "lon": lon_centers},
        attrs={
            "region": region.name,
            "lon_min": region.lon_min,
            "lon_max": region.lon_max,
            "lat_min": region.lat_min,
            "lat_max": region.lat_max,
            "resolution_deg": resolution_deg,
        },
    )


def save_mask(mask: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    mask.to_netcdf(tmp)
    tmp.rename(path)


def load_mask(path: Path) -> xr.Dataset:
    return xr.open_dataset(path).load()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
conda run -n davinci-monet pytest tests/test_masks.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/masks.py tests/test_masks.py
git commit -m "feat(masks): build and persist 1° regional masks with area weights"
```

---

## Task 3: Atomic-write cache helpers

**Files:**
- Create: `firex/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: Write failing test**

`tests/test_cache.py`:
```python
"""Tests for atomic-write and freshness helpers."""
import time
from pathlib import Path

import xarray as xr

from firex.cache import atomic_to_netcdf, output_is_fresh


def test_atomic_to_netcdf_writes_file(tmp_path):
    ds = xr.Dataset({"x": ("t", [1.0, 2.0, 3.0])}, coords={"t": [0, 1, 2]})
    out = tmp_path / "out.nc"
    atomic_to_netcdf(ds, out)
    assert out.exists()
    reloaded = xr.open_dataset(out).load()
    assert (reloaded["x"].values == [1.0, 2.0, 3.0]).all()


def test_atomic_to_netcdf_no_tmp_left(tmp_path):
    ds = xr.Dataset({"x": ("t", [1.0])}, coords={"t": [0]})
    out = tmp_path / "out.nc"
    atomic_to_netcdf(ds, out)
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_output_is_fresh_when_newer(tmp_path):
    inp = tmp_path / "in.nc"
    inp.write_text("dummy")
    time.sleep(0.05)
    out = tmp_path / "out.nc"
    out.write_text("dummy")
    assert output_is_fresh(out, [inp]) is True


def test_output_is_stale_when_older(tmp_path):
    out = tmp_path / "out.nc"
    out.write_text("dummy")
    time.sleep(0.05)
    inp = tmp_path / "in.nc"
    inp.write_text("dummy")
    assert output_is_fresh(out, [inp]) is False


def test_output_is_fresh_missing_output_returns_false(tmp_path):
    out = tmp_path / "out.nc"
    inp = tmp_path / "in.nc"
    inp.write_text("dummy")
    assert output_is_fresh(out, [inp]) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
conda run -n davinci-monet pytest tests/test_cache.py -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement `firex/cache.py`**

```python
"""Atomic write + mtime-based freshness checks for stage outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import xarray as xr


def atomic_to_netcdf(ds: xr.Dataset, path: Path) -> None:
    """Write `ds` to `path` atomically (write `.tmp` then rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    ds.to_netcdf(tmp)
    tmp.rename(path)


def output_is_fresh(output: Path, inputs: Iterable[Path]) -> bool:
    """True iff `output` exists and is newer than every input."""
    output = Path(output)
    if not output.exists():
        return False
    out_mtime = output.stat().st_mtime
    for inp in inputs:
        inp = Path(inp)
        if not inp.exists():
            return False
        if inp.stat().st_mtime > out_mtime:
            return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
conda run -n davinci-monet pytest tests/test_cache.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/cache.py tests/test_cache.py
git commit -m "feat(cache): atomic NetCDF writes and mtime-based freshness checks"
```

---

## Task 4: Synthetic fixture builder

**Files:**
- Create: `tests/fixtures/build_fixtures.py`
- Generate: `tests/fixtures/ceres_ebaf_synth.nc`
- Generate: `tests/fixtures/modis_terra_synth.nc`
- Generate: `tests/fixtures/modis_aqua_synth.nc`
- Generate: `tests/fixtures/viirs_snpp_synth.nc`
- Generate: `tests/fixtures/viirs_noaa20_synth.nc`
- Generate: `tests/fixtures/merra2_aer_synth.nc`
- Generate: `tests/fixtures/merra2_slv_synth.nc`
- Generate: `tests/fixtures/qfed_synth/Y2020/M07/qfed2.emis_oc.005.20200715.nc4` (and a few more)
- Generate: `tests/fixtures/aeronet_synth.nc`

This task produces all the synthetic NetCDFs that loader tests will read against.

- [ ] **Step 1: Write fixture-builder script**

`tests/fixtures/build_fixtures.py`:
```python
"""Generate small synthetic NetCDF fixtures for loader tests.

Run this once to populate `tests/fixtures/*.nc`. Re-run if schemas change.

    python tests/fixtures/build_fixtures.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).parent
RNG = np.random.default_rng(seed=20260428)


def _months(n: int = 24, start: str = "2020-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="MS")


def _grid(lat_min: float = 40.0, lat_max: float = 50.0,
          lon_min: float = -130.0, lon_max: float = -110.0,
          step: float = 1.0):
    lat = np.arange(lat_min + step / 2, lat_max, step)
    lon = np.arange(lon_min + step / 2, lon_max, step)
    return lat, lon


def build_ceres_ebaf() -> None:
    """CERES EBAF Ed4.2.1 — TOA + SFC SW/LW/Net, both clear-sky and all-sky."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "toa_sw_all_mon": (("time", "lat", "lon"), 100 + 5 * RNG.standard_normal(shape)),
            "toa_sw_clr_t_mon": (("time", "lat", "lon"), 95 + 4 * RNG.standard_normal(shape)),
            "toa_lw_all_mon": (("time", "lat", "lon"), 230 + 5 * RNG.standard_normal(shape)),
            "toa_lw_clr_t_mon": (("time", "lat", "lon"), 250 + 4 * RNG.standard_normal(shape)),
            "toa_net_all_mon": (("time", "lat", "lon"), 20 + 3 * RNG.standard_normal(shape)),
            "toa_net_clr_t_mon": (("time", "lat", "lon"), 18 + 2 * RNG.standard_normal(shape)),
            "sfc_sw_down_all_mon": (("time", "lat", "lon"), 180 + 10 * RNG.standard_normal(shape)),
            "sfc_sw_down_clr_t_mon": (("time", "lat", "lon"), 220 + 8 * RNG.standard_normal(shape)),
            "sfc_lw_down_all_mon": (("time", "lat", "lon"), 320 + 5 * RNG.standard_normal(shape)),
            "sfc_lw_down_clr_t_mon": (("time", "lat", "lon"), 310 + 5 * RNG.standard_normal(shape)),
            "sfc_net_tot_all_mon": (("time", "lat", "lon"), 90 + 5 * RNG.standard_normal(shape)),
            "sfc_net_tot_clr_t_mon": (("time", "lat", "lon"), 110 + 5 * RNG.standard_normal(shape)),
            "cldarea_total_daynight_mon": (("time", "lat", "lon"), 0.5 + 0.1 * RNG.standard_normal(shape)),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / "ceres_ebaf_synth.nc")


def build_modis(short: str) -> None:
    """MODIS MOD08_M3 / MYD08_M3 — monthly L3 AOD."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "Aerosol_Optical_Depth_Land_Ocean_Mean_Mean": (
                ("time", "lat", "lon"),
                0.15 + 0.05 * RNG.standard_normal(shape),
            ),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / f"{short}_synth.nc")


def build_viirs(short: str, start: str) -> None:
    """VIIRS AERDB monthly L3."""
    months = _months(start=start)
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "Aerosol_Optical_Thickness_550_Land_Ocean_Mean": (
                ("time", "lat", "lon"),
                0.13 + 0.04 * RNG.standard_normal(shape),
            ),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / f"{short}_synth.nc")


def build_merra2_aer() -> None:
    """MERRA-2 monthly aer_Nx species AOD (no OCEXTTAU_bb -> exercises fallback)."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "TOTEXTTAU": (("time", "lat", "lon"), 0.20 + 0.05 * RNG.standard_normal(shape)),
            "BCEXTTAU": (("time", "lat", "lon"), 0.02 + 0.005 * RNG.standard_normal(shape)),
            "OCEXTTAU": (("time", "lat", "lon"), 0.06 + 0.01 * RNG.standard_normal(shape)),
            "SUEXTTAU": (("time", "lat", "lon"), 0.05 + 0.01 * RNG.standard_normal(shape)),
            "DUEXTTAU": (("time", "lat", "lon"), 0.04 + 0.01 * RNG.standard_normal(shape)),
            "SSEXTTAU": (("time", "lat", "lon"), 0.03 + 0.01 * RNG.standard_normal(shape)),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / "merra2_aer_synth.nc")


def build_merra2_slv() -> None:
    """MERRA-2 monthly slv_Nx covariates."""
    months = _months()
    lat, lon = _grid()
    shape = (len(months), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "T2M": (("time", "lat", "lon"), 285 + 5 * RNG.standard_normal(shape)),
            "TQV": (("time", "lat", "lon"), 18 + 4 * RNG.standard_normal(shape)),
            "PBLH": (("time", "lat", "lon"), 1500 + 200 * RNG.standard_normal(shape)),
        },
        coords={"time": months, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(HERE / "merra2_slv_synth.nc")


def build_qfed() -> None:
    """A handful of QFED daily files in the Y{YYYY}/M{MM}/ layout."""
    base = HERE / "qfed_synth"
    days = pd.date_range("2020-07-01", "2020-07-03", freq="D")
    lat, lon = _grid(step=0.5)
    for sp in ("oc", "bc", "co"):
        for d in days:
            d_dir = base / f"Y{d.year}" / f"M{d.month:02d}"
            d_dir.mkdir(parents=True, exist_ok=True)
            arr = 1e-10 + 1e-11 * RNG.standard_normal((1, len(lat), len(lon)))
            ds = xr.Dataset(
                {"biomass": (("time", "lat", "lon"), arr)},
                coords={"time": [d], "lat": lat, "lon": lon},
            )
            ds.to_netcdf(d_dir / f"qfed2.emis_{sp}.005.{d:%Y%m%d}.nc4")


def build_aeronet() -> None:
    """AERONET monthly site file (~3 PNW sites)."""
    months = _months()
    sites = ["Trinidad_Head", "Railroad_Valley", "Bondville"]
    site_lat = np.array([41.05, 38.5, 40.05])
    site_lon = np.array([-124.15, -115.7, -88.4])
    ds = xr.Dataset(
        {
            "AOD_550nm": (
                ("time", "site"),
                0.10 + 0.04 * RNG.standard_normal((len(months), len(sites))),
            ),
            "site_lat": (("site",), site_lat),
            "site_lon": (("site",), site_lon),
        },
        coords={"time": months, "site": sites},
    )
    ds.to_netcdf(HERE / "aeronet_synth.nc")


if __name__ == "__main__":
    build_ceres_ebaf()
    build_modis("modis_terra")
    build_modis("modis_aqua")
    build_viirs("viirs_snpp", start="2020-01")
    build_viirs("viirs_noaa20", start="2020-01")
    build_merra2_aer()
    build_merra2_slv()
    build_qfed()
    build_aeronet()
    print("Synthetic fixtures written to", HERE)
```

- [ ] **Step 2: Run the builder**

```bash
conda run -n davinci-monet python tests/fixtures/build_fixtures.py
```
Expected: prints "Synthetic fixtures written to ...". Verify with:
```bash
ls tests/fixtures/*.nc tests/fixtures/qfed_synth/Y2020/M07/
```

- [ ] **Step 3: Add `.gitignore` rule for the `qfed_synth/` tree (since it's regenerable) and commit fixtures otherwise**

Append to `.gitignore`:
```
tests/fixtures/qfed_synth/
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/build_fixtures.py tests/fixtures/*.nc .gitignore
git commit -m "test: add synthetic NetCDF fixtures for loader tests"
```

---

## Task 5: CERES EBAF loader

**Files:**
- Create: `firex/loaders/ceres_ebaf.py`
- Test: `tests/test_loaders.py` (extends across tasks)

- [ ] **Step 1: Write failing test**

`tests/test_loaders.py`:
```python
"""Tests for per-dataset monthly regional-mean loaders."""
import pytest
import xarray as xr

from firex.loaders.ceres_ebaf import load_ceres_ebaf
from firex.masks import build_mask
from firex.regions import REGIONS


def _pnw_mask():
    return build_mask(REGIONS["pacific-northwest"], resolution_deg=1.0)


def test_ceres_ebaf_returns_dataset_with_expected_vars(fixtures_dir):
    ds = load_ceres_ebaf(fixtures_dir / "ceres_ebaf_synth.nc", mask=_pnw_mask())
    assert isinstance(ds, xr.Dataset)
    assert ds.dims == {"time": 24}
    expected_vars = {
        "ceres_toa_sw_all", "ceres_toa_sw_clr",
        "ceres_toa_lw_all", "ceres_toa_lw_clr",
        "ceres_toa_net_all", "ceres_toa_net_clr",
        "ceres_sfc_sw_down_all", "ceres_sfc_sw_down_clr",
        "ceres_sfc_lw_down_all", "ceres_sfc_lw_down_clr",
        "ceres_sfc_net_all", "ceres_sfc_net_clr",
        "ceres_cloud_fraction",
    }
    assert expected_vars.issubset(set(ds.data_vars))


def test_ceres_ebaf_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_ceres_ebaf(tmp_path / "nope.nc", mask=_pnw_mask())


def test_ceres_ebaf_missing_variable_raises(fixtures_dir, tmp_path):
    """If a required variable is absent, fail loudly."""
    src = xr.open_dataset(fixtures_dir / "ceres_ebaf_synth.nc")
    src = src.drop_vars(["toa_sw_all_mon"])
    bad = tmp_path / "bad.nc"
    src.to_netcdf(bad)
    with pytest.raises(KeyError, match="toa_sw_all_mon"):
        load_ceres_ebaf(bad, mask=_pnw_mask())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py::test_ceres_ebaf_returns_dataset_with_expected_vars -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement `firex/loaders/ceres_ebaf.py`**

```python
"""Load CERES EBAF Ed4.2.1 monthly file → masked, area-weighted regional means."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr


_VAR_MAP: dict[str, str] = {
    "toa_sw_all_mon": "ceres_toa_sw_all",
    "toa_sw_clr_t_mon": "ceres_toa_sw_clr",
    "toa_lw_all_mon": "ceres_toa_lw_all",
    "toa_lw_clr_t_mon": "ceres_toa_lw_clr",
    "toa_net_all_mon": "ceres_toa_net_all",
    "toa_net_clr_t_mon": "ceres_toa_net_clr",
    "sfc_sw_down_all_mon": "ceres_sfc_sw_down_all",
    "sfc_sw_down_clr_t_mon": "ceres_sfc_sw_down_clr",
    "sfc_lw_down_all_mon": "ceres_sfc_lw_down_all",
    "sfc_lw_down_clr_t_mon": "ceres_sfc_lw_down_clr",
    "sfc_net_tot_all_mon": "ceres_sfc_net_all",
    "sfc_net_tot_clr_t_mon": "ceres_sfc_net_clr",
    "cldarea_total_daynight_mon": "ceres_cloud_fraction",
}


def load_ceres_ebaf(path: Path, mask: xr.Dataset) -> xr.Dataset:
    """Open CERES EBAF, regrid mask if needed, area-weighted mean per month."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CERES EBAF file not found: {path}")

    src = xr.open_dataset(path)
    missing = [k for k in _VAR_MAP if k not in src.data_vars]
    if missing:
        raise KeyError(f"CERES EBAF file missing variables: {missing}")

    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)

    out = {}
    for src_name, out_name in _VAR_MAP.items():
        weighted = src[src_name].weighted(weight)
        out[out_name] = weighted.mean(dim=("lat", "lon"))

    ds = xr.Dataset(out)
    ds = ds.assign_attrs(
        source_file=str(path),
        region=mask.attrs.get("region", "unknown"),
    )
    return ds
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k ceres
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/loaders/ceres_ebaf.py tests/test_loaders.py
git commit -m "feat(loaders): CERES EBAF Ed4.2.1 monthly regional-mean loader"
```

---

## Task 6: MODIS monthly loader (Terra + Aqua)

**Files:**
- Create: `firex/loaders/modis_monthly.py`
- Modify: `tests/test_loaders.py` (add MODIS tests)

- [ ] **Step 1: Append failing tests to `tests/test_loaders.py`**

```python
from firex.loaders.modis_monthly import load_modis_monthly


def test_modis_terra_returns_dataset(fixtures_dir):
    ds = load_modis_monthly(
        [fixtures_dir / "modis_terra_synth.nc"], platform="terra", mask=_pnw_mask()
    )
    assert isinstance(ds, xr.Dataset)
    assert "modis_terra_aod" in ds.data_vars
    assert ds.dims == {"time": 24}


def test_modis_aqua_returns_dataset(fixtures_dir):
    ds = load_modis_monthly(
        [fixtures_dir / "modis_aqua_synth.nc"], platform="aqua", mask=_pnw_mask()
    )
    assert "modis_aqua_aod" in ds.data_vars


def test_modis_invalid_platform_raises(fixtures_dir):
    with pytest.raises(ValueError, match="platform must be"):
        load_modis_monthly(
            [fixtures_dir / "modis_terra_synth.nc"], platform="other", mask=_pnw_mask()
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k modis
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement `firex/loaders/modis_monthly.py`**

```python
"""Load MODIS C6.1 monthly L3 (MOD08_M3 / MYD08_M3) → regional means."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import xarray as xr

_AOD_VAR = "Aerosol_Optical_Depth_Land_Ocean_Mean_Mean"


def load_modis_monthly(
    paths: Iterable[Path],
    platform: Literal["terra", "aqua"],
    mask: xr.Dataset,
) -> xr.Dataset:
    if platform not in ("terra", "aqua"):
        raise ValueError(f"platform must be 'terra' or 'aqua', got {platform!r}")
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise FileNotFoundError("No MODIS files supplied")
    src = xr.open_mfdataset(paths, combine="by_coords")
    if _AOD_VAR not in src.data_vars:
        raise KeyError(f"MODIS file missing variable: {_AOD_VAR}")
    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    aod = src[_AOD_VAR].weighted(weight).mean(dim=("lat", "lon"))
    return xr.Dataset({f"modis_{platform}_aod": aod}).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        platform=platform,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k modis
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/loaders/modis_monthly.py tests/test_loaders.py
git commit -m "feat(loaders): MODIS monthly L3 AOD loader (Terra + Aqua)"
```

---

## Task 7: VIIRS monthly loader (SNPP + NOAA-20)

**Files:**
- Create: `firex/loaders/viirs_monthly.py`
- Modify: `tests/test_loaders.py`

- [ ] **Step 1: Append failing tests**

```python
from firex.loaders.viirs_monthly import load_viirs_monthly


def test_viirs_snpp_returns_dataset(fixtures_dir):
    ds = load_viirs_monthly(
        [fixtures_dir / "viirs_snpp_synth.nc"], platform="snpp", mask=_pnw_mask()
    )
    assert "viirs_snpp_aod" in ds.data_vars


def test_viirs_noaa20_returns_dataset(fixtures_dir):
    ds = load_viirs_monthly(
        [fixtures_dir / "viirs_noaa20_synth.nc"], platform="noaa20", mask=_pnw_mask()
    )
    assert "viirs_noaa20_aod" in ds.data_vars
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k viirs
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement `firex/loaders/viirs_monthly.py`**

```python
"""Load VIIRS AERDB_M3 monthly L3 → regional means."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import xarray as xr

_AOD_VAR = "Aerosol_Optical_Thickness_550_Land_Ocean_Mean"


def load_viirs_monthly(
    paths: Iterable[Path],
    platform: Literal["snpp", "noaa20"],
    mask: xr.Dataset,
) -> xr.Dataset:
    if platform not in ("snpp", "noaa20"):
        raise ValueError(f"platform must be 'snpp' or 'noaa20', got {platform!r}")
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise FileNotFoundError("No VIIRS files supplied")
    src = xr.open_mfdataset(paths, combine="by_coords")
    if _AOD_VAR not in src.data_vars:
        raise KeyError(f"VIIRS file missing variable: {_AOD_VAR}")
    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    aod = src[_AOD_VAR].weighted(weight).mean(dim=("lat", "lon"))
    return xr.Dataset({f"viirs_{platform}_aod": aod}).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        platform=platform,
    )
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k viirs
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/loaders/viirs_monthly.py tests/test_loaders.py
git commit -m "feat(loaders): VIIRS AERDB_M3 monthly loader (SNPP + NOAA-20)"
```

---

## Task 8: MERRA-2 monthly loader

**Files:**
- Create: `firex/loaders/merra2_monthly.py`
- Modify: `tests/test_loaders.py`

- [ ] **Step 1: Append failing tests**

```python
from firex.loaders.merra2_monthly import load_merra2_monthly


def test_merra2_aer_loads_species(fixtures_dir):
    ds = load_merra2_monthly(
        [fixtures_dir / "merra2_aer_synth.nc"], collection="aer", mask=_pnw_mask()
    )
    assert "merra2_aer_TOTEXTTAU" in ds.data_vars
    assert "merra2_aer_BCEXTTAU" in ds.data_vars
    assert "merra2_aer_OCEXTTAU" in ds.data_vars


def test_merra2_slv_loads_covariates(fixtures_dir):
    ds = load_merra2_monthly(
        [fixtures_dir / "merra2_slv_synth.nc"], collection="slv", mask=_pnw_mask()
    )
    assert "merra2_slv_T2M" in ds.data_vars
    assert "merra2_slv_TQV" in ds.data_vars


def test_merra2_unknown_collection_raises(fixtures_dir):
    with pytest.raises(ValueError, match="Unknown collection"):
        load_merra2_monthly(
            [fixtures_dir / "merra2_aer_synth.nc"], collection="bogus", mask=_pnw_mask()
        )
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k merra2
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/loaders/merra2_monthly.py`**

```python
"""Load MERRA-2 monthly tavgM_2d_{aer,slv,flx,lnd}_Nx → regional means."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import xarray as xr

_COLLECTION_VARS: dict[str, list[str]] = {
    "aer": ["TOTEXTTAU", "BCEXTTAU", "OCEXTTAU", "SUEXTTAU", "DUEXTTAU", "SSEXTTAU"],
    "slv": ["T2M", "TQV", "PBLH"],
    "flx": ["HFLUX", "EFLUX", "USTAR"],
    "lnd": ["GWETROOT", "RUNOFF"],
}


def load_merra2_monthly(
    paths: Iterable[Path],
    collection: str,
    mask: xr.Dataset,
) -> xr.Dataset:
    if collection not in _COLLECTION_VARS:
        raise ValueError(
            f"Unknown collection {collection!r}; expected one of {list(_COLLECTION_VARS)}"
        )
    wanted = _COLLECTION_VARS[collection]
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise FileNotFoundError("No MERRA-2 files supplied")
    src = xr.open_mfdataset(paths, combine="by_coords")
    missing = [v for v in wanted if v not in src.data_vars]
    if missing:
        raise KeyError(f"MERRA-2 {collection} file missing variables: {missing}")
    weight = mask["weight"].interp(
        lat=src["lat"], lon=src["lon"], method="nearest"
    ).fillna(0.0)
    out = {}
    for v in wanted:
        out[f"merra2_{collection}_{v}"] = src[v].weighted(weight).mean(dim=("lat", "lon"))
    return xr.Dataset(out).assign_attrs(
        source_files=";".join(str(p) for p in paths),
        collection=collection,
    )
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k merra2
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/loaders/merra2_monthly.py tests/test_loaders.py
git commit -m "feat(loaders): MERRA-2 tavgM monthly loader (aer/slv/flx/lnd)"
```

---

## Task 9: QFED monthly loader

**Files:**
- Create: `firex/loaders/qfed_monthly.py`
- Modify: `tests/test_loaders.py`

QFED ships as daily files in `Y{YYYY}/M{MM}/qfed2.emis_{species}.005.{YYYYMMDD}.nc4` with one variable `biomass`. Loader sums daily → monthly per species and aggregates the staged species (bc/oc/co for the prototype).

- [ ] **Step 1: Append failing tests**

```python
from firex.loaders.qfed_monthly import load_qfed_monthly


def test_qfed_loads_monthly_species(fixtures_dir):
    ds = load_qfed_monthly(
        fixtures_dir / "qfed_synth", species=["bc", "oc", "co"], mask=_pnw_mask()
    )
    assert "qfed_bc" in ds.data_vars
    assert "qfed_oc" in ds.data_vars
    assert "qfed_co" in ds.data_vars
    assert ds.dims["time"] == 1  # July 2020 only in fixture


def test_qfed_skips_2016(tmp_path, fixtures_dir):
    """Y2016 is on the deny-list per CLAUDE.md."""
    base = tmp_path / "qfed"
    src_dir = fixtures_dir / "qfed_synth" / "Y2020" / "M07"
    dst_dir = base / "Y2016" / "M07"
    dst_dir.mkdir(parents=True)
    for f in src_dir.iterdir():
        new_name = f.name.replace("20200", "20160")
        (dst_dir / new_name).write_bytes(f.read_bytes())
    ds = load_qfed_monthly(base, species=["bc"], mask=_pnw_mask())
    assert ds.dims["time"] == 0
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k qfed
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/loaders/qfed_monthly.py`**

```python
"""Aggregate QFED v2.6r1 daily files into monthly regional emission totals."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)
_QFED_FILE_GLOB = "qfed2.emis_{species}.005.{date:%Y%m%d}.nc4"


def load_qfed_monthly(
    base_dir: Path,
    species: Iterable[str],
    mask: xr.Dataset,
) -> xr.Dataset:
    """Walk ``base_dir/Y{yyyy}/M{mm}/`` summing daily files into monthly means.

    Y2016 is hard-skipped per CLAUDE.md (NCCS reprocess anomaly).
    """
    base = Path(base_dir)
    species = list(species)
    monthly_arrays: dict[str, list] = {sp: [] for sp in species}
    months: list[pd.Timestamp] = []

    for year_dir in sorted(p for p in base.glob("Y*") if p.is_dir()):
        year = int(year_dir.name[1:])
        if year == 2016:
            logger.info("Skipping Y2016 per CLAUDE.md note (NCCS reprocess anomaly)")
            continue
        for month_dir in sorted(p for p in year_dir.glob("M*") if p.is_dir()):
            month = int(month_dir.name[1:])
            month_start = pd.Timestamp(year=year, month=month, day=1)
            for sp in species:
                files = sorted(month_dir.glob(f"qfed2.emis_{sp}.005.*.nc4"))
                if not files:
                    continue
                src = xr.open_mfdataset(files, combine="by_coords")["biomass"]
                weight = mask["weight"].interp(
                    lat=src["lat"], lon=src["lon"], method="nearest"
                ).fillna(0.0)
                regional = src.weighted(weight).mean(dim=("lat", "lon"))
                monthly_arrays[sp].append((month_start, regional.sum(dim="time").item()))
            months.append(month_start)

    months = sorted(set(months))
    out = {}
    for sp in species:
        records = dict(monthly_arrays[sp])
        values = [records.get(m, float("nan")) for m in months]
        out[f"qfed_{sp}"] = xr.DataArray(values, dims=("time",), coords={"time": months})
    return xr.Dataset(out, coords={"time": months})
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k qfed
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/loaders/qfed_monthly.py tests/test_loaders.py
git commit -m "feat(loaders): QFED daily → monthly regional aggregator"
```

---

## Task 10: AERONET loader

**Files:**
- Create: `firex/loaders/aeronet.py`
- Modify: `tests/test_loaders.py`

The synthetic fixture mirrors a `(time, site)` Dataset with `AOD_550nm`, `site_lat`, `site_lon`. Real `~/Data/AeroNet/*.nc` files are per-site; this loader concatenates and filters to those whose site_lat/lon fall in the PNW bbox.

- [ ] **Step 1: Append failing tests**

```python
from firex.loaders.aeronet import load_aeronet


def test_aeronet_filters_to_pnw_sites(fixtures_dir):
    ds = load_aeronet(
        fixtures_dir / "aeronet_synth.nc", region=REGIONS["pacific-northwest"]
    )
    sites = list(ds["site"].values)
    assert "Trinidad_Head" in sites
    # Bondville (40.05, -88.4) is outside the PNW bbox; should be filtered out.
    assert "Bondville" not in sites
```

- [ ] **Step 2: Run test**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k aeronet
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/loaders/aeronet.py`**

```python
"""Load AERONET monthly site file and filter to a region."""
from __future__ import annotations

from pathlib import Path

import xarray as xr

from firex.regions import Region


def load_aeronet(path: Path, region: Region) -> xr.Dataset:
    src = xr.open_dataset(Path(path)).load()
    if "site_lat" not in src or "site_lon" not in src:
        raise KeyError("AERONET file must contain site_lat and site_lon coordinates")
    inside = (
        (src["site_lat"] >= region.lat_min)
        & (src["site_lat"] <= region.lat_max)
        & (src["site_lon"] >= region.lon_min)
        & (src["site_lon"] <= region.lon_max)
    )
    return src.where(inside, drop=True).rename({"AOD_550nm": "aeronet_aod_550"})
```

- [ ] **Step 4: Run test**

```bash
conda run -n davinci-monet pytest tests/test_loaders.py -v -k aeronet
```
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add firex/loaders/aeronet.py tests/test_loaders.py
git commit -m "feat(loaders): AERONET monthly site loader with bbox filter"
```

---

## Task 11: Smoke attribution

**Files:**
- Create: `firex/attribution.py`
- Test: `tests/test_attribution.py`

- [ ] **Step 1: Write failing test**

`tests/test_attribution.py`:
```python
"""Tests for smoke-AOD attribution."""
import numpy as np
import pandas as pd
import xarray as xr

from firex.attribution import compute_smoke_attribution


def _make_merra2(bc, oc, total, *, has_oc_bb=False, oc_bb=None) -> xr.Dataset:
    times = pd.date_range("2020-01", periods=12, freq="MS")
    n = len(times)
    data = {
        "merra2_aer_BCEXTTAU": ("time", np.full(n, bc)),
        "merra2_aer_OCEXTTAU": ("time", np.full(n, oc)),
        "merra2_aer_TOTEXTTAU": ("time", np.full(n, total)),
    }
    if has_oc_bb:
        data["merra2_aer_OCEXTTAU_bb"] = ("time", np.full(n, oc_bb))
    return xr.Dataset(data, coords={"time": times})


def _make_obs(name: str, value: float) -> xr.Dataset:
    times = pd.date_range("2020-01", periods=12, freq="MS")
    return xr.Dataset({name: ("time", np.full(len(times), value))}, coords={"time": times})


def _make_qfed(oc_value: float) -> xr.Dataset:
    times = pd.date_range("2020-01", periods=12, freq="MS")
    return xr.Dataset({"qfed_oc": ("time", np.full(len(times), oc_value))}, coords={"time": times})


def test_known_split_present_path():
    """When OCEXTTAU_bb is present, OC_bb_share = OC_bb / OC."""
    merra2 = _make_merra2(bc=0.02, oc=0.06, total=0.20, has_oc_bb=True, oc_bb=0.04)
    obs = _make_obs("modis_terra_aod", 0.30)
    qfed = _make_qfed(1e-9)
    out = compute_smoke_attribution(
        merra2=merra2, obs={"modis_terra_aod": obs["modis_terra_aod"]}, qfed=qfed,
    )
    # smoke_fraction = (BC + OC_bb) / TOTAL = (0.02 + 0.04) / 0.20 = 0.30
    np.testing.assert_allclose(out["smoke_fraction"].values, 0.30, atol=1e-6)
    np.testing.assert_allclose(out["smoke_aod_terra"].values, 0.09, atol=1e-6)
    assert out.attrs["oc_split_method"] == "explicit"


def test_fallback_path_triggers():
    """No OCEXTTAU_bb → fallback uses QFED ratio + DJF baseline."""
    merra2 = _make_merra2(bc=0.02, oc=0.06, total=0.20, has_oc_bb=False)
    obs = _make_obs("modis_terra_aod", 0.30)
    qfed = _make_qfed(1e-9)
    out = compute_smoke_attribution(
        merra2=merra2, obs={"modis_terra_aod": obs["modis_terra_aod"]}, qfed=qfed,
    )
    assert out.attrs["oc_split_method"] == "fallback"
    # smoke_fraction must be in [0, 1]
    assert (out["smoke_fraction"].values >= 0).all()
    assert (out["smoke_fraction"].values <= 1).all()


def test_multiple_obs_sources():
    merra2 = _make_merra2(bc=0.02, oc=0.06, total=0.20, has_oc_bb=True, oc_bb=0.04)
    qfed = _make_qfed(1e-9)
    out = compute_smoke_attribution(
        merra2=merra2,
        obs={
            "modis_terra_aod": _make_obs("modis_terra_aod", 0.30)["modis_terra_aod"],
            "modis_aqua_aod": _make_obs("modis_aqua_aod", 0.32)["modis_aqua_aod"],
            "viirs_snpp_aod": _make_obs("viirs_snpp_aod", 0.28)["viirs_snpp_aod"],
            "viirs_noaa20_aod": _make_obs("viirs_noaa20_aod", 0.29)["viirs_noaa20_aod"],
        },
        qfed=qfed,
    )
    for name in ("smoke_aod_terra", "smoke_aod_aqua", "smoke_aod_snpp", "smoke_aod_noaa20"):
        assert name in out
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_attribution.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/attribution.py`**

```python
"""Compute smoke-fraction and smoke-AOD per observed source."""
from __future__ import annotations

import logging

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

_OBS_TO_SLUG = {
    "modis_terra_aod": "terra",
    "modis_aqua_aod": "aqua",
    "viirs_snpp_aod": "snpp",
    "viirs_noaa20_aod": "noaa20",
}


def _djf_baseline_oc(merra2: xr.Dataset) -> float:
    """Per-record DJF mean of OCEXTTAU as anthropogenic+biogenic baseline."""
    oc = merra2["merra2_aer_OCEXTTAU"]
    djf = oc.where(oc["time"].dt.month.isin([12, 1, 2]), drop=True)
    if djf.size == 0:
        raise ValueError("No DJF months available for fallback baseline")
    return float(djf.mean().item())


def compute_smoke_attribution(
    *,
    merra2: xr.Dataset,
    obs: dict[str, xr.DataArray],
    qfed: xr.Dataset,
) -> xr.Dataset:
    """Smoke fraction (MERRA-2-based) and smoke AOD per observation source."""
    bc = merra2["merra2_aer_BCEXTTAU"]
    oc = merra2["merra2_aer_OCEXTTAU"]
    total = merra2["merra2_aer_TOTEXTTAU"]

    if "merra2_aer_OCEXTTAU_bb" in merra2:
        oc_bb = merra2["merra2_aer_OCEXTTAU_bb"]
        oc_split_method = "explicit"
    else:
        baseline = _djf_baseline_oc(merra2)
        share = qfed["qfed_oc"] / (qfed["qfed_oc"] + baseline)
        oc_bb = oc * share.clip(0.0, 1.0)
        oc_split_method = "fallback"
        logger.warning(
            "MERRA-2 lacks OCEXTTAU_bb; using QFED-ratio fallback with DJF baseline %.3e",
            baseline,
        )

    smoke_fraction = ((bc + oc_bb) / total).clip(0.0, 1.0)

    out_vars: dict[str, xr.DataArray] = {"smoke_fraction": smoke_fraction}
    for obs_name, obs_da in obs.items():
        if obs_name not in _OBS_TO_SLUG:
            raise KeyError(f"Unknown observation source: {obs_name}")
        slug = _OBS_TO_SLUG[obs_name]
        out_vars[f"smoke_aod_{slug}"] = smoke_fraction * obs_da

    ds = xr.Dataset(out_vars)
    ds.attrs["oc_split_method"] = oc_split_method
    return ds
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_attribution.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/attribution.py tests/test_attribution.py
git commit -m "feat(attribution): MERRA-2-based smoke fraction with QFED fallback"
```

---

## Task 12: Anomaly module

**Files:**
- Create: `firex/anomaly.py`
- Test: `tests/test_anomaly.py`

- [ ] **Step 1: Write failing test**

`tests/test_anomaly.py`:
```python
"""Tests for monthly anomaly construction and regression-design helpers."""
import numpy as np
import pandas as pd
import xarray as xr

from firex.anomaly import compute_anomaly, build_design_matrix


def _seasonal(amp: float, n_years: int = 5) -> xr.DataArray:
    months = pd.date_range("2010-01", periods=12 * n_years, freq="MS")
    seasonal = amp * np.sin(2 * np.pi * months.month.values / 12)
    return xr.DataArray(seasonal, dims="time", coords={"time": months})


def test_pure_seasonal_has_zero_anomaly():
    da = _seasonal(amp=2.0)
    anom = compute_anomaly(da)
    np.testing.assert_allclose(anom.values, 0.0, atol=1e-12)


def test_anomaly_recovers_injected_trend():
    da = _seasonal(amp=1.0)
    t = np.arange(da.size, dtype=float)
    da = da + 0.05 * t
    anom = compute_anomaly(da)
    # Injected trend should remain (climatology subtraction removes seasonal only)
    slope = np.polyfit(t, anom.values, 1)[0]
    np.testing.assert_allclose(slope, 0.05, atol=1e-3)


def test_design_matrix_shape_and_columns():
    months = pd.date_range("2010-01", periods=24, freq="MS")
    times = xr.DataArray(months, dims="time")
    X = build_design_matrix(times)
    # 11 month dummies + linear trend + intercept = 13 columns
    assert X.shape == (24, 13)
    assert "intercept" in X.columns
    assert "trend" in X.columns
    # Reference month dropped (should leave 11 month-FE columns)
    fe_cols = [c for c in X.columns if c.startswith("month_")]
    assert len(fe_cols) == 11
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_anomaly.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/anomaly.py`**

```python
"""Climatology subtraction and regression design-matrix construction."""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr


def compute_anomaly(da: xr.DataArray) -> xr.DataArray:
    """Subtract month-of-year climatology computed over the full record."""
    if "time" not in da.dims:
        raise ValueError("DataArray must have a `time` dimension")
    climatology = da.groupby("time.month").mean()
    return da.groupby("time.month") - climatology


def build_design_matrix(times: xr.DataArray) -> pd.DataFrame:
    """Construct intercept + linear trend + month-of-year fixed effects."""
    if times.dtype.kind != "M":
        raise ValueError(f"`times` must be datetime, got {times.dtype}")
    n = times.size
    df = pd.DataFrame(index=range(n))
    df["intercept"] = 1.0
    df["trend"] = np.arange(n, dtype=float)
    months = pd.DatetimeIndex(times.values).month
    # Reference month = 1 (January). Add month_2..month_12 dummies.
    for m in range(2, 13):
        df[f"month_{m}"] = (months == m).astype(float)
    return df
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_anomaly.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/anomaly.py tests/test_anomaly.py
git commit -m "feat(anomaly): climatology subtraction and FE+trend design matrix"
```

---

## Task 13: Regression module

**Files:**
- Create: `firex/regression.py`
- Test: `tests/test_regression.py`

- [ ] **Step 1: Write failing test**

`tests/test_regression.py`:
```python
"""Tests for the OLS regression helper."""
import numpy as np
import pandas as pd
import xarray as xr

from firex.regression import fit_radiative_efficiency


def _make_synth(beta: float = -30.0, n: int = 240, seed: int = 0) -> xr.Dataset:
    rng = np.random.default_rng(seed)
    times = pd.date_range("2000-01", periods=n, freq="MS")
    smoke_aod = np.abs(0.10 + 0.05 * rng.standard_normal(n))
    cloud = 0.5 + 0.05 * rng.standard_normal(n)
    tqv = 18 + 4 * rng.standard_normal(n)
    seasonal = 5 * np.sin(2 * np.pi * times.month.values / 12)
    noise = 0.5 * rng.standard_normal(n)
    F = 100 + beta * smoke_aod + 2.0 * cloud + 0.1 * tqv + seasonal + noise
    return xr.Dataset(
        {
            "F_TOA_SW_clr": ("time", F),
            "smoke_aod": ("time", smoke_aod),
            "cloud_fraction": ("time", cloud),
            "tqv": ("time", tqv),
        },
        coords={"time": times},
    )


def test_recovers_known_beta():
    ds = _make_synth(beta=-30.0)
    result = fit_radiative_efficiency(
        ds, response="F_TOA_SW_clr",
        predictors=["smoke_aod", "cloud_fraction", "tqv"],
    )
    beta_hat = result.params["smoke_aod"]
    se = result.bse["smoke_aod"]
    assert abs(beta_hat - (-30.0)) < 2 * se


def test_hac_se_nonzero():
    ds = _make_synth()
    result = fit_radiative_efficiency(
        ds, response="F_TOA_SW_clr",
        predictors=["smoke_aod", "cloud_fraction", "tqv"],
    )
    assert result.bse["smoke_aod"] > 0


def test_summary_table_has_expected_columns():
    ds = _make_synth()
    result = fit_radiative_efficiency(
        ds, response="F_TOA_SW_clr",
        predictors=["smoke_aod", "cloud_fraction", "tqv"],
    )
    table = result.summary_frame()
    for col in ("coef", "std_err", "t_stat", "p_value"):
        assert col in table.columns
    assert "smoke_aod" in table.index
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_regression.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/regression.py`**

```python
"""OLS with HAC standard errors plus month-FE + linear trend."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm
import xarray as xr

from firex.anomaly import build_design_matrix


@dataclass
class RegressionResult:
    params: pd.Series
    bse: pd.Series
    tvalues: pd.Series
    pvalues: pd.Series
    rsquared: float
    nobs: int

    def summary_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "coef": self.params,
                "std_err": self.bse,
                "t_stat": self.tvalues,
                "p_value": self.pvalues,
            }
        )


def fit_radiative_efficiency(
    ds: xr.Dataset,
    response: str,
    predictors: list[str],
    hac_lags: int = 6,
) -> RegressionResult:
    """Fit `response = α + Σ β_i · predictors_i + month_FE + trend + ε` via OLS+HAC."""
    if response not in ds:
        raise KeyError(f"Response variable {response!r} not in dataset")
    for p in predictors:
        if p not in ds:
            raise KeyError(f"Predictor {p!r} not in dataset")

    fe_trend = build_design_matrix(ds["time"])
    pred_df = pd.DataFrame({p: ds[p].values for p in predictors})
    X = pd.concat([pred_df, fe_trend.drop(columns=["intercept"])], axis=1)
    X = sm.add_constant(X, has_constant="add")

    y = pd.Series(ds[response].values, name=response)

    valid = X.notna().all(axis=1) & y.notna()
    X = X.loc[valid]
    y = y.loc[valid]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    return RegressionResult(
        params=model.params,
        bse=model.bse,
        tvalues=model.tvalues,
        pvalues=model.pvalues,
        rsquared=float(model.rsquared),
        nobs=int(model.nobs),
    )
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_regression.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/regression.py tests/test_regression.py
git commit -m "feat(regression): OLS+HAC with FE/trend design matrix"
```

---

## Task 14: Plot module skeleton + style hookup

**Files:**
- Create: `firex/plots.py`
- Test: `tests/test_plots.py`

- [ ] **Step 1: Write failing test**

`tests/test_plots.py`:
```python
"""Tests for the plotting layer (light: existence + write-out only)."""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from firex.plots import setup_style, save_figure


def test_setup_style_runs():
    setup_style()
    # spot-check a known NCAR-styled rcParam
    assert plt.rcParams["savefig.dpi"] == 300


def test_save_figure_writes_png(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 4])
    out = tmp_path / "fig.png"
    save_figure(fig, out)
    assert out.exists()
    assert out.stat().st_size > 0
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_plots.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `firex/plots.py`**

```python
"""Plot module: NCAR styling hook plus 13 figure-builder functions.

Plot builders are added incrementally across tasks 15a..15c. This file
holds the shared style hook and `save_figure` helper.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from davinci_monet.plots.style import apply_ncar_style


_STYLE_APPLIED = False


def setup_style() -> None:
    """Apply NCAR brand styling once per process. Idempotent."""
    global _STYLE_APPLIED
    if _STYLE_APPLIED:
        return
    apply_ncar_style(context="publication")
    _STYLE_APPLIED = True


def save_figure(fig, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fig.savefig(tmp)
    tmp.rename(path)
    plt.close(fig)
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_plots.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add firex/plots.py tests/test_plots.py
git commit -m "feat(plots): style hook and atomic figure writer"
```

---

## Task 15a: Time-series plots (#1–#5, #8, #10, #12)

**Files:**
- Modify: `firex/plots.py`
- Modify: `tests/test_plots.py`

- [ ] **Step 1: Append failing tests**

```python
# Add at top of tests/test_plots.py:
from firex.plots import (
    plot_aod_total_timeseries,
    plot_smoke_fraction_timeseries,
    plot_smoke_aod_timeseries,
    plot_ceres_toa_anomaly,
    plot_ceres_sfc_anomaly,
    plot_seasonal_climatology,
    plot_qfed_emissions_timeseries,
    plot_cloud_fraction_timeseries,
)


def _synth_merged() -> xr.Dataset:
    times = pd.date_range("2000-03", periods=300, freq="MS")
    n = times.size
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "modis_terra_aod": ("time", 0.15 + 0.05 * rng.standard_normal(n)),
            "modis_aqua_aod": ("time", 0.16 + 0.05 * rng.standard_normal(n)),
            "viirs_snpp_aod": ("time", 0.14 + 0.04 * rng.standard_normal(n)),
            "viirs_noaa20_aod": ("time", 0.14 + 0.04 * rng.standard_normal(n)),
            "smoke_fraction": ("time", 0.20 + 0.05 * rng.standard_normal(n)),
            "smoke_aod_terra": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "smoke_aod_aqua": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "smoke_aod_snpp": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "smoke_aod_noaa20": ("time", 0.05 + 0.02 * rng.standard_normal(n)),
            "ceres_toa_sw_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_sw_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_lw_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_lw_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_net_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_toa_net_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_sw_down_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_sw_down_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_lw_down_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_lw_down_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_net_all_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_sfc_net_clr_anom": ("time", 1.0 * rng.standard_normal(n)),
            "ceres_cloud_fraction": ("time", 0.5 + 0.05 * rng.standard_normal(n)),
            "qfed_bc": ("time", 1e-10 + 1e-11 * rng.standard_normal(n)),
            "qfed_oc": ("time", 5e-10 + 1e-10 * rng.standard_normal(n)),
            "qfed_co": ("time", 5e-9 + 1e-9 * rng.standard_normal(n)),
        },
        coords={"time": times},
        attrs={"region": "pacific-northwest", "bbox": "[42N–52N, 130W–110W]"},
    )


def test_plot_aod_total_timeseries(tmp_path):
    setup_style()
    ds = _synth_merged()
    out = tmp_path / "p1.png"
    plot_aod_total_timeseries(ds, aeronet=None, output=out)
    assert out.exists()


def test_plot_smoke_fraction_timeseries(tmp_path):
    setup_style()
    plot_smoke_fraction_timeseries(_synth_merged(), tmp_path / "p2.png")
    assert (tmp_path / "p2.png").exists()


def test_plot_smoke_aod_timeseries(tmp_path):
    setup_style()
    plot_smoke_aod_timeseries(_synth_merged(), tmp_path / "p3.png")
    assert (tmp_path / "p3.png").exists()


def test_plot_ceres_toa_anomaly(tmp_path):
    setup_style()
    plot_ceres_toa_anomaly(_synth_merged(), tmp_path / "p4.png")
    assert (tmp_path / "p4.png").exists()


def test_plot_ceres_sfc_anomaly(tmp_path):
    setup_style()
    plot_ceres_sfc_anomaly(_synth_merged(), tmp_path / "p5.png")
    assert (tmp_path / "p5.png").exists()


def test_plot_seasonal_climatology(tmp_path):
    setup_style()
    plot_seasonal_climatology(_synth_merged(), tmp_path / "p8.png")
    assert (tmp_path / "p8.png").exists()


def test_plot_qfed_emissions(tmp_path):
    setup_style()
    plot_qfed_emissions_timeseries(_synth_merged(), tmp_path / "p10.png")
    assert (tmp_path / "p10.png").exists()


def test_plot_cloud_fraction(tmp_path):
    setup_style()
    plot_cloud_fraction_timeseries(_synth_merged(), tmp_path / "p12.png")
    assert (tmp_path / "p12.png").exists()
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_plots.py -v
```
Expected: 8 new tests FAIL with ImportError.

- [ ] **Step 3: Append plot functions to `firex/plots.py`**

```python
import matplotlib.pyplot as plt
import xarray as xr


def _annotate_caption(fig, ds: xr.Dataset, methods: str = "") -> None:
    region = ds.attrs.get("region", "?")
    bbox = ds.attrs.get("bbox", "")
    t0 = str(xr.DataArray(ds["time"].values[0]).dt.strftime("%Y-%m").item())
    t1 = str(xr.DataArray(ds["time"].values[-1]).dt.strftime("%Y-%m").item())
    caption = f"region={region} {bbox} | {t0}–{t1}"
    if methods:
        caption += f" | {methods}"
    fig.text(0.5, -0.02, caption, ha="center", fontsize=8)


def plot_aod_total_timeseries(ds: xr.Dataset, aeronet, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    for var, label in [
        ("modis_terra_aod", "MODIS Terra"),
        ("modis_aqua_aod", "MODIS Aqua"),
        ("viirs_snpp_aod", "VIIRS-SNPP"),
        ("viirs_noaa20_aod", "VIIRS-NOAA20"),
    ]:
        if var in ds:
            ax.plot(ds["time"], ds[var], label=label, lw=1.0)
    if aeronet is not None and "aeronet_aod_550" in aeronet:
        for site in aeronet["site"].values:
            ax.scatter(
                aeronet["time"], aeronet["aeronet_aod_550"].sel(site=site),
                s=8, alpha=0.6, label=f"AERONET {site}",
            )
    ax.set_xlabel("Year")
    ax.set_ylabel("AOD 550 nm")
    ax.set_title("Total AOD — Pacific Northwest monthly")
    ax.legend(fontsize=8, loc="upper left")
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_smoke_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(ds["time"], ds["smoke_fraction"], lw=1.0)
    ax.set_xlabel("Year")
    ax.set_ylabel("Smoke fraction (–)")
    ax.set_title("MERRA-2-derived smoke fraction — Pacific Northwest")
    _annotate_caption(fig, ds, methods="smoke_fraction = (BC + OC_bb) / TOTAL")
    save_figure(fig, output)


def plot_smoke_aod_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    cols = ["smoke_aod_terra", "smoke_aod_aqua", "smoke_aod_snpp", "smoke_aod_noaa20"]
    arr = xr.concat([ds[c] for c in cols if c in ds], dim="src")
    ax.fill_between(ds["time"], arr.min("src"), arr.max("src"), alpha=0.3, label="inter-platform spread")
    ax.plot(ds["time"], arr.mean("src"), lw=1.0, label="ensemble mean")
    ax.set_xlabel("Year")
    ax.set_ylabel("Smoke AOD 550 nm")
    ax.set_title("Smoke AOD — Pacific Northwest monthly")
    ax.legend(fontsize=9)
    _annotate_caption(fig, ds, methods="smoke_AOD = smoke_fraction × observed AOD")
    save_figure(fig, output)


def _three_panel_anomaly(ds, prefix: str, label: str, output) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for ax, comp, ylabel in zip(
        axes, ("sw", "lw", "net"),
        (f"{label} SW anomaly (W m⁻²)", f"{label} LW anomaly (W m⁻²)", f"{label} Net anomaly (W m⁻²)"),
    ):
        all_var = f"{prefix}_{comp}_all_anom" if "sfc" not in prefix else f"{prefix}_{comp}_down_all_anom"
        clr_var = f"{prefix}_{comp}_clr_anom" if "sfc" not in prefix else f"{prefix}_{comp}_down_clr_anom"
        # Net at sfc lacks "_down" suffix in CERES
        if "sfc" in prefix and comp == "net":
            all_var = f"{prefix}_net_all_anom"
            clr_var = f"{prefix}_net_clr_anom"
        if all_var in ds:
            ax.plot(ds["time"], ds[all_var], label="all-sky", lw=1.0)
        if clr_var in ds:
            ax.plot(ds["time"], ds[clr_var], label="clear-sky", lw=1.0)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=9)
    axes[-1].set_xlabel("Year")
    fig.suptitle(f"CERES {label} radiative-flux anomalies — Pacific Northwest")
    _annotate_caption(fig, ds, methods="anomaly = monthly value − month-of-year climatology")
    save_figure(fig, output)


def plot_ceres_toa_anomaly(ds: xr.Dataset, output) -> None:
    _three_panel_anomaly(ds, prefix="ceres_toa", label="TOA", output=output)


def plot_ceres_sfc_anomaly(ds: xr.Dataset, output) -> None:
    _three_panel_anomaly(ds, prefix="ceres_sfc", label="SFC", output=output)


def plot_seasonal_climatology(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    smoke_clim = ds["smoke_aod_terra"].groupby("time.month").mean()
    dF_clim = ds["ceres_toa_sw_clr_anom"].groupby("time.month").mean()
    width = 0.4
    months = smoke_clim["month"].values
    ax.bar(months - width / 2, smoke_clim, width=width, label="smoke AOD")
    ax2 = ax.twinx()
    ax2.bar(months + width / 2, dF_clim, width=width, color="C1", label="ΔF_TOA_SW (clear-sky)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Smoke AOD")
    ax2.set_ylabel("ΔF_TOA_SW (W m⁻²)")
    ax.set_title("Seasonal climatology — Pacific Northwest")
    ax.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_qfed_emissions_timeseries(ds: xr.Dataset, output) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for ax, var, label in zip(axes, ("qfed_bc", "qfed_oc", "qfed_co"), ("BC", "OC", "CO")):
        ax.plot(ds["time"], ds[var], lw=1.0, label=label)
        ax.set_ylabel(f"{label} (kg m⁻² s⁻¹)")
        if "smoke_aod_terra" in ds:
            ax2 = ax.twinx()
            ax2.plot(ds["time"], ds["smoke_aod_terra"], color="C1", lw=0.8, alpha=0.6)
            ax2.set_ylabel("smoke AOD", color="C1")
        ax.legend(loc="upper left", fontsize=9)
    axes[-1].set_xlabel("Year")
    fig.suptitle("QFED biomass-burning emissions — Pacific Northwest")
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_cloud_fraction_timeseries(ds: xr.Dataset, output) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(ds["time"], ds["ceres_cloud_fraction"], lw=1.0)
    ax.set_xlabel("Year")
    ax.set_ylabel("Cloud fraction")
    ax.set_title("CERES total-column cloud fraction — Pacific Northwest")
    _annotate_caption(fig, ds)
    save_figure(fig, output)
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_plots.py -v
```
Expected: 10 passed (2 from Task 14 + 8 new).

- [ ] **Step 5: Commit**

```bash
git add firex/plots.py tests/test_plots.py
git commit -m "feat(plots): time-series plots #1-5, #8, #10, #12"
```

---

## Task 15b: Scatter plots (#6, #7, #11, #13)

**Files:**
- Modify: `firex/plots.py`
- Modify: `tests/test_plots.py`

- [ ] **Step 1: Append failing tests**

```python
from firex.plots import (
    plot_scatter_dF_TOA_vs_smoke,
    plot_scatter_dF_SFC_vs_smoke,
    plot_aeronet_vs_modis_scatter,
    plot_merra2_obs_scaling,
)


def test_plot_scatter_toa(tmp_path):
    setup_style()
    plot_scatter_dF_TOA_vs_smoke(_synth_merged(), tmp_path / "p6.png")
    assert (tmp_path / "p6.png").exists()


def test_plot_scatter_sfc(tmp_path):
    setup_style()
    plot_scatter_dF_SFC_vs_smoke(_synth_merged(), tmp_path / "p7.png")
    assert (tmp_path / "p7.png").exists()


def test_plot_aeronet_vs_modis(tmp_path):
    setup_style()
    times = pd.date_range("2000-03", periods=300, freq="MS")
    aeronet = xr.Dataset(
        {"aeronet_aod_550": (("time", "site"), np.full((times.size, 2), 0.1))},
        coords={"time": times, "site": ["Trinidad_Head", "Railroad_Valley"]},
    )
    plot_aeronet_vs_modis_scatter(_synth_merged(), aeronet, tmp_path / "p11.png")
    assert (tmp_path / "p11.png").exists()


def test_plot_merra2_obs_scaling(tmp_path):
    setup_style()
    ds = _synth_merged().assign(merra2_aer_TOTEXTTAU=("time", np.full(300, 0.18)))
    plot_merra2_obs_scaling(ds, tmp_path / "p13.png")
    assert (tmp_path / "p13.png").exists()
```

- [ ] **Step 2: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_plots.py -v -k scatter -k merra2 -k aeronet
```
Expected: 4 new FAIL.

- [ ] **Step 3: Append plot functions to `firex/plots.py`**

```python
import numpy as np


def _scatter_with_ols(ax, x: np.ndarray, y: np.ndarray, label: str) -> None:
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    ax.scatter(x, y, s=10, alpha=0.5)
    if x.size >= 3:
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 50)
        ax.plot(xs, slope * xs + intercept, color="C3", lw=1.5)
        # SE estimate from residuals
        yhat = slope * x + intercept
        resid = y - yhat
        sxx = ((x - x.mean()) ** 2).sum()
        se = np.sqrt((resid ** 2).sum() / (x.size - 2) / sxx) if x.size > 2 else float("nan")
        r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum() if y.var() > 0 else 0
        ax.text(
            0.05, 0.95,
            f"β = {slope:.1f} ± {se:.1f}\nn = {x.size}\nR² = {r2:.2f}",
            transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"),
        )
    ax.set_title(label)


def _scatter_pair(ds, smoke_var: str, all_var: str, clr_var: str, ylabel: str, output) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    smoke = ds[smoke_var].values
    _scatter_with_ols(axes[0], smoke, ds[clr_var].values, "clear-sky")
    _scatter_with_ols(axes[1], smoke, ds[all_var].values, "all-sky")
    axes[0].set_ylabel(ylabel)
    for ax in axes:
        ax.set_xlabel("Smoke AOD (MODIS Terra)")
    _annotate_caption(fig, ds, methods="OLS regression on monthly anomalies")
    save_figure(fig, output)


def plot_scatter_dF_TOA_vs_smoke(ds, output) -> None:
    _scatter_pair(
        ds, smoke_var="smoke_aod_terra",
        all_var="ceres_toa_sw_all_anom", clr_var="ceres_toa_sw_clr_anom",
        ylabel="ΔF_TOA_SW (W m⁻²)", output=output,
    )


def plot_scatter_dF_SFC_vs_smoke(ds, output) -> None:
    _scatter_pair(
        ds, smoke_var="smoke_aod_terra",
        all_var="ceres_sfc_sw_down_all_anom", clr_var="ceres_sfc_sw_down_clr_anom",
        ylabel="ΔF_SFC_SW↓ (W m⁻²)", output=output,
    )


def plot_aeronet_vs_modis_scatter(ds, aeronet, output) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    if aeronet is not None and "aeronet_aod_550" in aeronet:
        for site in aeronet["site"].values:
            modis = ds["modis_terra_aod"].interp(time=aeronet["time"])
            site_aod = aeronet["aeronet_aod_550"].sel(site=site)
            ax.scatter(site_aod, modis, s=10, alpha=0.6, label=str(site))
        lim = max(np.nanmax(aeronet["aeronet_aod_550"].values), float(ds["modis_terra_aod"].max()))
        ax.plot([0, lim], [0, lim], "k--", lw=0.8)
    ax.set_xlabel("AERONET AOD 550 nm")
    ax.set_ylabel("MODIS Terra gridcell AOD")
    ax.set_title("AERONET vs. MODIS — PNW sites")
    ax.legend(fontsize=8)
    _annotate_caption(fig, ds)
    save_figure(fig, output)


def plot_merra2_obs_scaling(ds, output) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].scatter(ds["modis_terra_aod"], ds["merra2_aer_TOTEXTTAU"], s=10, alpha=0.5)
    lim = float(max(ds["modis_terra_aod"].max(), ds["merra2_aer_TOTEXTTAU"].max()))
    axes[0].plot([0, lim], [0, lim], "k--", lw=0.8)
    axes[0].set_xlabel("MODIS Terra AOD")
    axes[0].set_ylabel("MERRA-2 TOTEXTTAU")
    axes[0].set_title("Magnitude comparison")
    ratio = ds["merra2_aer_TOTEXTTAU"] / ds["modis_terra_aod"]
    axes[1].plot(ds["time"], ratio, lw=1.0)
    axes[1].set_xlabel("Year")
    axes[1].set_ylabel("MERRA-2 / MODIS")
    axes[1].set_title("Scaling-factor time series")
    _annotate_caption(fig, ds, methods="ratio used to validate MERRA-2 fractional split, not magnitude")
    save_figure(fig, output)
```

- [ ] **Step 4: Run tests**

```bash
conda run -n davinci-monet pytest tests/test_plots.py -v
```
Expected: 14 total passed.

- [ ] **Step 5: Commit**

```bash
git add firex/plots.py tests/test_plots.py
git commit -m "feat(plots): scatter plots #6, #7, #11, #13"
```

---

## Task 15c: Spatial map (#9)

**Files:**
- Modify: `firex/plots.py`
- Modify: `tests/test_plots.py`

This plot needs gridded `(time, lat, lon)` data, not the monthly time-series merged file. It reads directly from a separate "gridded" dataset that the runner produces alongside the regional aggregate. Add the helper function and a small fixture for the test.

- [ ] **Step 1: Append failing test**

```python
from firex.plots import plot_spatial_maps_peak_year


def test_plot_spatial_maps(tmp_path):
    setup_style()
    times = pd.date_range("2000-03", periods=300, freq="MS")
    lat = np.arange(40.5, 53)
    lon = np.arange(-130.5, -109)
    rng = np.random.default_rng(0)
    shape = (times.size, lat.size, lon.size)
    gridded = xr.Dataset(
        {
            "smoke_aod_terra": (("time", "lat", "lon"), 0.05 + 0.02 * rng.standard_normal(shape)),
            "ceres_toa_sw_clr_anom": (("time", "lat", "lon"), 1.0 * rng.standard_normal(shape)),
        },
        coords={"time": times, "lat": lat, "lon": lon},
    )
    out = tmp_path / "p9.png"
    plot_spatial_maps_peak_year(gridded, peak_year=2020, region_bbox=(-130, -110, 42, 52), output=out)
    assert out.exists()
```

- [ ] **Step 2: Run test**

```bash
conda run -n davinci-monet pytest tests/test_plots.py::test_plot_spatial_maps -v
```
Expected: FAIL.

- [ ] **Step 3: Append plot function to `firex/plots.py`**

```python
import cartopy.crs as ccrs
import cartopy.feature as cfeature


def plot_spatial_maps_peak_year(
    gridded: xr.Dataset,
    peak_year: int,
    region_bbox: tuple[float, float, float, float],
    output,
) -> None:
    """2x2 cartopy grid: rows = climatology / peak-year anomaly, cols = smoke AOD / ΔF_TOA_SW_clr."""
    smoke = gridded["smoke_aod_terra"]
    dF = gridded["ceres_toa_sw_clr_anom"]

    smoke_clim = smoke.mean("time")
    dF_clim = dF.mean("time")
    smoke_peak = smoke.sel(time=str(peak_year)).mean("time") - smoke_clim
    dF_peak = dF.sel(time=str(peak_year)).mean("time") - dF_clim

    fig = plt.figure(figsize=(11, 8))
    panels = [
        ("Climatology — smoke AOD", smoke_clim, "viridis", None),
        ("Climatology — ΔF_TOA_SW_clr", dF_clim, "RdBu_r", (-5, 5)),
        (f"{peak_year} anomaly — smoke AOD", smoke_peak, "viridis", None),
        (f"{peak_year} anomaly — ΔF_TOA_SW_clr", dF_peak, "RdBu_r", (-10, 10)),
    ]
    for i, (title, data, cmap, vrange) in enumerate(panels, start=1):
        ax = fig.add_subplot(2, 2, i, projection=ccrs.PlateCarree())
        kwargs = {"cmap": cmap}
        if vrange is not None:
            kwargs["vmin"], kwargs["vmax"] = vrange
        m = ax.pcolormesh(data["lon"], data["lat"], data, transform=ccrs.PlateCarree(), **kwargs)
        ax.coastlines(lw=0.5)
        ax.add_feature(cfeature.STATES.with_scale("50m"), lw=0.3)
        lon_min, lon_max, lat_min, lat_max = region_bbox
        ax.plot(
            [lon_min, lon_max, lon_max, lon_min, lon_min],
            [lat_min, lat_min, lat_max, lat_max, lat_min],
            "k", lw=1.0, transform=ccrs.PlateCarree(),
        )
        ax.set_extent([lon_min - 5, lon_max + 5, lat_min - 5, lat_max + 5])
        ax.set_title(title, fontsize=10)
        plt.colorbar(m, ax=ax, shrink=0.7)
    fig.suptitle(f"Spatial fields: climatology vs. {peak_year} anomaly")
    save_figure(fig, output)
```

- [ ] **Step 4: Run test**

```bash
conda run -n davinci-monet pytest tests/test_plots.py::test_plot_spatial_maps -v
```
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add firex/plots.py tests/test_plots.py
git commit -m "feat(plots): spatial-fields map #9 (climatology + peak-year anomaly)"
```

---

## Task 16: Pipeline orchestrator + config

**Files:**
- Create: `firex/run_pnw.py`
- Create: `configs/pacific-northwest.yaml`

This is the assembly: 6 stages run in order, each writes a tidy NetCDF, with an mtime-based skip and `--force`/`--stages` controls.

- [ ] **Step 1: Write the config file**

`configs/pacific-northwest.yaml`:
```yaml
region: pacific-northwest
bbox:
  lon_min: -130.0
  lon_max: -110.0
  lat_min: 42.0
  lat_max: 52.0

time:
  start: "2000-03"
  end: null   # null → use most recent available granule

paths:
  ceres_ebaf: "~/Data/CERES_EBAF/ceres"
  modis_terra: "~/Data/MOD08_M3"
  modis_aqua: "~/Data/MYD08_M3"
  viirs_snpp: "~/Data/VIIRS/AERDB_M3_VIIRS_SNPP"
  viirs_noaa20: "~/Data/VIIRS/AERDB_M3_VIIRS_NOAA20"
  merra2_aer: "~/Data/MERRA2_tavgM/aer_Nx"
  merra2_slv: "~/Data/MERRA2_tavgM/slv_Nx"
  qfed: "~/Data/QFED"
  aeronet: "~/Data/AeroNet"

output_dir: "output/pacific-northwest"

species_qfed: ["bc", "oc", "co"]
peak_year: null   # null → auto-pick from QFED OC

regression:
  predictors: ["smoke_aod_terra", "merra2_slv_TQV", "ceres_cloud_fraction"]
  hac_lags: 6

plots:
  - aod_total_timeseries
  - smoke_fraction_timeseries
  - smoke_aod_timeseries
  - ceres_toa_anomaly
  - ceres_sfc_anomaly
  - scatter_dF_TOA_vs_smoke
  - scatter_dF_SFC_vs_smoke
  - seasonal_climatology
  - spatial_maps_peak_year
  - qfed_emissions_timeseries
  - aeronet_vs_modis_scatter
  - cloud_fraction_timeseries
  - merra2_obs_scaling
```

- [ ] **Step 2: Write the orchestrator**

`firex/run_pnw.py`:
```python
"""End-to-end runner: 6 stages → tidy NetCDFs + 13 PNGs.

Usage:
    python -m firex.run_pnw --config configs/pacific-northwest.yaml
"""
from __future__ import annotations

import argparse
import datetime
import logging
import subprocess
import sys
from pathlib import Path

import yaml
import xarray as xr

import davinci_monet
import firex
from firex import attribution, anomaly, plots, regression
from firex.cache import atomic_to_netcdf, output_is_fresh
from firex.loaders import (
    aeronet, ceres_ebaf, merra2_monthly, modis_monthly, qfed_monthly, viirs_monthly,
)
from firex.masks import build_mask, save_mask
from firex.regions import REGIONS

logger = logging.getLogger("firex.run_pnw")


def _setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = log_dir / f"run_{stamp}.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stderr))
    root.setLevel(logging.INFO)
    return log_path


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parents[1]
        ).decode().strip()
    except Exception:
        return "unknown"


def _log_header(cfg: dict) -> None:
    logger.info("FIREX run starting")
    logger.info("  firex version: %s", firex.__version__)
    logger.info("  davinci_monet version: %s", getattr(davinci_monet, "__version__", "unknown"))
    logger.info("  git SHA (FIREX): %s", _git_sha())
    logger.info("  region: %s", cfg["region"])
    logger.info("  bbox: %s", cfg["bbox"])
    logger.info("  time: %s → %s", cfg["time"]["start"], cfg["time"]["end"])


def _stage1_mask(cfg: dict, out_dir: Path, force: bool) -> Path:
    out = out_dir / "data" / "mask.nc"
    if not force and output_is_fresh(out, []):
        logger.info("[stage 1] skipped (fresh)")
        return out
    region = REGIONS[cfg["region"]]
    mask = build_mask(region)
    save_mask(mask, out)
    logger.info("[stage 1] wrote %s", out)
    return out


def _glob_files(root: Path, pattern: str) -> list[Path]:
    return sorted(Path(root).expanduser().glob(pattern))


def _stage2_loaders(cfg: dict, out_dir: Path, mask_path: Path, force: bool) -> dict[str, Path]:
    mask = xr.open_dataset(mask_path).load()
    data_dir = out_dir / "data"
    region = REGIONS[cfg["region"]]
    out: dict[str, Path] = {}

    # CERES EBAF: pick the latest granule
    ceres_files = _glob_files(cfg["paths"]["ceres_ebaf"], "CERES_EBAF_Edition*.nc")
    if not ceres_files:
        raise FileNotFoundError("No CERES EBAF files found")
    latest = max(ceres_files, key=lambda p: p.stat().st_mtime)
    out_path = data_dir / "ceres_ebaf.nc"
    if force or not output_is_fresh(out_path, [latest]):
        atomic_to_netcdf(ceres_ebaf.load_ceres_ebaf(latest, mask=mask), out_path)
        logger.info("[stage 2] CERES EBAF → %s (granule: %s)", out_path, latest.name)
    out["ceres_ebaf"] = out_path

    # MODIS Terra + Aqua
    for plat, key in [("terra", "modis_terra"), ("aqua", "modis_aqua")]:
        files = _glob_files(cfg["paths"][key], "*_M3*.hdf*") + _glob_files(cfg["paths"][key], "*.nc4")
        out_path = data_dir / f"modis_{plat}.nc"
        if force or not output_is_fresh(out_path, files):
            atomic_to_netcdf(modis_monthly.load_modis_monthly(files, plat, mask=mask), out_path)
            logger.info("[stage 2] MODIS %s → %s (%d files)", plat, out_path, len(files))
        out[key] = out_path

    # VIIRS SNPP + NOAA-20
    for plat, key in [("snpp", "viirs_snpp"), ("noaa20", "viirs_noaa20")]:
        files = _glob_files(cfg["paths"][key], "*.nc")
        out_path = data_dir / f"viirs_{plat}.nc"
        if force or not output_is_fresh(out_path, files):
            atomic_to_netcdf(viirs_monthly.load_viirs_monthly(files, plat, mask=mask), out_path)
            logger.info("[stage 2] VIIRS %s → %s (%d files)", plat, out_path, len(files))
        out[key] = out_path

    # MERRA-2 aer + slv
    for coll, key in [("aer", "merra2_aer"), ("slv", "merra2_slv")]:
        files = _glob_files(cfg["paths"][key], "*.nc4")
        out_path = data_dir / f"merra2_{coll}.nc"
        if force or not output_is_fresh(out_path, files):
            atomic_to_netcdf(merra2_monthly.load_merra2_monthly(files, coll, mask=mask), out_path)
            logger.info("[stage 2] MERRA-2 %s → %s (%d files)", coll, out_path, len(files))
        out[key] = out_path

    # QFED
    out_path = data_dir / "qfed.nc"
    qfed_root = Path(cfg["paths"]["qfed"]).expanduser()
    if force or not output_is_fresh(out_path, list(qfed_root.rglob("*.nc4"))):
        atomic_to_netcdf(
            qfed_monthly.load_qfed_monthly(qfed_root, cfg["species_qfed"], mask=mask),
            out_path,
        )
        logger.info("[stage 2] QFED → %s", out_path)
    out["qfed"] = out_path

    # AERONET — single file expected to be the most recent monthly aggregate
    aeronet_files = _glob_files(cfg["paths"]["aeronet"], "*.nc")
    if aeronet_files:
        latest = max(aeronet_files, key=lambda p: p.stat().st_mtime)
        out_path = data_dir / "aeronet_pnw.nc"
        if force or not output_is_fresh(out_path, [latest]):
            atomic_to_netcdf(aeronet.load_aeronet(latest, region=region), out_path)
            logger.info("[stage 2] AERONET → %s", out_path)
        out["aeronet"] = out_path
    else:
        logger.warning("No AERONET files found; aeronet stage skipped")

    return out


def _stage3_attribution(stage2: dict[str, Path], out_dir: Path, force: bool) -> Path:
    out_path = out_dir / "data" / "smoke_attribution.nc"
    inputs = [stage2["merra2_aer"], stage2["modis_terra"], stage2["modis_aqua"],
              stage2["viirs_snpp"], stage2["viirs_noaa20"], stage2["qfed"]]
    if not force and output_is_fresh(out_path, inputs):
        logger.info("[stage 3] skipped (fresh)")
        return out_path
    merra2 = xr.open_dataset(stage2["merra2_aer"]).load()
    qfed = xr.open_dataset(stage2["qfed"]).load()
    obs: dict[str, xr.DataArray] = {}
    for k, var in [("modis_terra", "modis_terra_aod"), ("modis_aqua", "modis_aqua_aod"),
                   ("viirs_snpp", "viirs_snpp_aod"), ("viirs_noaa20", "viirs_noaa20_aod")]:
        ds = xr.open_dataset(stage2[k]).load()
        obs[var] = ds[var]
    atomic_to_netcdf(
        attribution.compute_smoke_attribution(merra2=merra2, obs=obs, qfed=qfed),
        out_path,
    )
    logger.info("[stage 3] wrote %s", out_path)
    return out_path


def _stage4_merge(stage2: dict[str, Path], stage3: Path, out_dir: Path, force: bool) -> Path:
    out_path = out_dir / "data" / "merged.nc"
    inputs = list(stage2.values()) + [stage3]
    if not force and output_is_fresh(out_path, inputs):
        logger.info("[stage 4] skipped (fresh)")
        return out_path
    parts = [xr.open_dataset(p).load() for p in inputs if p is not None]
    merged = xr.merge(parts, compat="override")
    # Append _anom columns
    for var in list(merged.data_vars):
        merged[f"{var}_anom"] = anomaly.compute_anomaly(merged[var])
    atomic_to_netcdf(merged, out_path)
    logger.info("[stage 4] wrote %s", out_path)
    return out_path


def _stage5_regression(merged_path: Path, cfg: dict, out_dir: Path, force: bool) -> Path:
    out_csv = out_dir / "data" / "regression_table.csv"
    if not force and output_is_fresh(out_csv, [merged_path]):
        logger.info("[stage 5] skipped (fresh)")
        return out_csv
    merged = xr.open_dataset(merged_path).load()
    rows = []
    for response in [
        "ceres_toa_sw_all", "ceres_toa_sw_clr",
        "ceres_toa_lw_all", "ceres_toa_lw_clr",
        "ceres_toa_net_all", "ceres_toa_net_clr",
        "ceres_sfc_sw_down_all", "ceres_sfc_sw_down_clr",
        "ceres_sfc_net_all", "ceres_sfc_net_clr",
    ]:
        if response not in merged:
            continue
        result = regression.fit_radiative_efficiency(
            merged, response=response,
            predictors=cfg["regression"]["predictors"],
            hac_lags=cfg["regression"]["hac_lags"],
        )
        for var in cfg["regression"]["predictors"]:
            rows.append(
                {
                    "response": response,
                    "predictor": var,
                    "coef": result.params[var],
                    "std_err": result.bse[var],
                    "t_stat": result.tvalues[var],
                    "p_value": result.pvalues[var],
                    "rsquared": result.rsquared,
                    "n_obs": result.nobs,
                }
            )
    import pandas as pd
    df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    logger.info("[stage 5] wrote %s (%d rows)", out_csv, len(df))
    return out_csv


def _pick_peak_year(merged_path: Path) -> int:
    merged = xr.open_dataset(merged_path).load()
    annual_oc = merged["qfed_oc"].groupby("time.year").mean()
    return int(annual_oc.idxmax().item())


def _stage6_plots(cfg: dict, merged_path: Path, out_dir: Path, force: bool) -> None:
    plots.setup_style()
    merged = xr.open_dataset(merged_path).load()
    aeronet_path = out_dir / "data" / "aeronet_pnw.nc"
    aeronet_ds = xr.open_dataset(aeronet_path).load() if aeronet_path.exists() else None
    plots_dir = out_dir / "plots"
    plot_fns = {
        "aod_total_timeseries":
            lambda: plots.plot_aod_total_timeseries(merged, aeronet_ds, plots_dir / "aod_total_timeseries.png"),
        "smoke_fraction_timeseries":
            lambda: plots.plot_smoke_fraction_timeseries(merged, plots_dir / "smoke_fraction_timeseries.png"),
        "smoke_aod_timeseries":
            lambda: plots.plot_smoke_aod_timeseries(merged, plots_dir / "smoke_aod_timeseries.png"),
        "ceres_toa_anomaly":
            lambda: plots.plot_ceres_toa_anomaly(merged, plots_dir / "ceres_toa_anomaly.png"),
        "ceres_sfc_anomaly":
            lambda: plots.plot_ceres_sfc_anomaly(merged, plots_dir / "ceres_sfc_anomaly.png"),
        "scatter_dF_TOA_vs_smoke":
            lambda: plots.plot_scatter_dF_TOA_vs_smoke(merged, plots_dir / "scatter_dF_TOA_vs_smoke.png"),
        "scatter_dF_SFC_vs_smoke":
            lambda: plots.plot_scatter_dF_SFC_vs_smoke(merged, plots_dir / "scatter_dF_SFC_vs_smoke.png"),
        "seasonal_climatology":
            lambda: plots.plot_seasonal_climatology(merged, plots_dir / "seasonal_climatology.png"),
        "qfed_emissions_timeseries":
            lambda: plots.plot_qfed_emissions_timeseries(merged, plots_dir / "qfed_emissions_timeseries.png"),
        "aeronet_vs_modis_scatter":
            lambda: plots.plot_aeronet_vs_modis_scatter(merged, aeronet_ds, plots_dir / "aeronet_vs_modis_scatter.png"),
        "cloud_fraction_timeseries":
            lambda: plots.plot_cloud_fraction_timeseries(merged, plots_dir / "cloud_fraction_timeseries.png"),
        "merra2_obs_scaling":
            lambda: plots.plot_merra2_obs_scaling(merged, plots_dir / "merra2_obs_scaling.png"),
    }
    for name in cfg["plots"]:
        if name == "spatial_maps_peak_year":
            continue  # needs gridded path; current prototype regional-mean only — log and skip
        if name not in plot_fns:
            logger.warning("Unknown plot name in config: %s", name)
            continue
        plot_fns[name]()
        logger.info("[stage 6] %s.png", name)
    if "spatial_maps_peak_year" in cfg["plots"]:
        logger.warning(
            "spatial_maps_peak_year requires a gridded merged file (lat/lon retained); "
            "this prototype writes regional-mean only. Plot skipped."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FIREX PNW pipeline")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stages", default="1,2,3,4,5,6")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--end", default=None, help="Override config end-date (YYYY-MM)")
    args = parser.parse_args(argv)

    cfg = yaml.safe_load(args.config.read_text())
    if args.end is not None:
        cfg["time"]["end"] = args.end

    out_dir = Path(cfg["output_dir"])
    log_path = _setup_logging(out_dir / "logs")
    _log_header(cfg)
    logger.info("Log file: %s", log_path)

    stages = {int(s) for s in args.stages.split(",")}
    mask_path = _stage1_mask(cfg, out_dir, args.force) if 1 in stages else out_dir / "data" / "mask.nc"
    stage2 = _stage2_loaders(cfg, out_dir, mask_path, args.force) if 2 in stages else {
        k: out_dir / "data" / f"{k}.nc"
        for k in ("ceres_ebaf", "modis_terra", "modis_aqua", "viirs_snpp",
                  "viirs_noaa20", "merra2_aer", "merra2_slv", "qfed", "aeronet")
    }
    stage3 = _stage3_attribution(stage2, out_dir, args.force) if 3 in stages else out_dir / "data" / "smoke_attribution.nc"
    merged = _stage4_merge(stage2, stage3, out_dir, args.force) if 4 in stages else out_dir / "data" / "merged.nc"
    if 5 in stages:
        _stage5_regression(merged, cfg, out_dir, args.force)
    if 6 in stages:
        _stage6_plots(cfg, merged, out_dir, args.force)
    logger.info("FIREX run finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Smoke-test the CLI against `--help`**

```bash
conda run -n davinci-monet python -m firex.run_pnw --help
```
Expected: argparse usage prints; exit code 0.

- [ ] **Step 4: Commit**

```bash
git add firex/run_pnw.py configs/pacific-northwest.yaml
git commit -m "feat(run_pnw): orchestrator + PNW config (6 stages, mtime-based skip)"
```

---

## Task 17: End-to-end pipeline smoke test

**Files:**
- Create: `tests/test_pipeline_smoke.py`

This is a `@pytest.mark.slow` test that reads a 24-month subset of the real `~/Data/...` archive. Skipped by default (`pytest tests/`), runs explicitly with `pytest -m slow`.

- [ ] **Step 1: Write the slow test**

`tests/test_pipeline_smoke.py`:
```python
"""End-to-end smoke test against real ~/Data/... files. Runs all 6 stages
on a 24-month subset and asserts each output NetCDF exists with non-empty time.

Run explicitly:
    pytest tests/test_pipeline_smoke.py -m slow -v
"""
import os
import shutil
from pathlib import Path

import pytest
import xarray as xr
import yaml


@pytest.mark.slow
def test_pipeline_runs_end_to_end(tmp_path):
    # Copy the real config into a tmp path with a short date window.
    src_cfg = Path("configs/pacific-northwest.yaml")
    cfg = yaml.safe_load(src_cfg.read_text())
    cfg["time"]["start"] = "2020-01"
    cfg["time"]["end"] = "2021-12"
    cfg["output_dir"] = str(tmp_path)
    test_cfg = tmp_path / "config.yaml"
    test_cfg.write_text(yaml.safe_dump(cfg))

    from firex.run_pnw import main

    rc = main(["--config", str(test_cfg), "--force"])
    assert rc == 0

    data_dir = tmp_path / "data"
    expected = [
        "mask.nc", "ceres_ebaf.nc", "modis_terra.nc", "modis_aqua.nc",
        "viirs_snpp.nc", "merra2_aer.nc", "merra2_slv.nc", "qfed.nc",
        "smoke_attribution.nc", "merged.nc", "regression_table.csv",
    ]
    for name in expected:
        path = data_dir / name
        assert path.exists(), f"missing output: {path}"
        if path.suffix == ".nc":
            ds = xr.open_dataset(path)
            assert ds.sizes.get("time", 1) > 0, f"empty time axis in {path}"

    plots_dir = tmp_path / "plots"
    assert any(plots_dir.glob("*.png")), "no plots written"
```

- [ ] **Step 2: Run the slow test**

```bash
conda run -n davinci-monet pytest tests/test_pipeline_smoke.py -m slow -v
```
Expected: 1 passed (may take 1–5 minutes depending on disk speed). If a loader hits a real-world variable-name mismatch, fix the loader (loaders use synthetic-fixture names that may diverge from the real files; iterate until all stages clear).

- [ ] **Step 3: Run the default (fast) suite to confirm nothing regressed**

```bash
conda run -n davinci-monet pytest tests/ -v
```
Expected: all fast tests pass; slow test marked deselected.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline_smoke.py
git commit -m "test: end-to-end pipeline smoke test against real data (slow)"
```

---

## Task 18: Run the pipeline + drop a results-skeleton report

**Files:**
- Create: `output/pacific-northwest/reports/results-skeleton.md`

This task closes the loop: real run, real outputs, a writeable skeleton for the methods/results draft.

- [ ] **Step 1: Run the full pipeline**

```bash
conda run -n davinci-monet python -m firex.run_pnw --config configs/pacific-northwest.yaml --force
```
Expected: completes without error; logs show 6 stages; `output/pacific-northwest/data/` has all NetCDFs; `output/pacific-northwest/plots/` has 12 PNGs (skip count of 1: `spatial_maps_peak_year` is logged-skip per Task 16 note).

- [ ] **Step 2: Write the report skeleton**

`output/pacific-northwest/reports/results-skeleton.md`:
```markdown
# FIREX — Pacific Northwest results (draft skeleton)

**Run date:** _to fill_
**Time range:** _from log header_
**Region bbox:** 42–52°N, 130–110°W
**Granule:** _CERES EBAF Edition4.2.1 file used_

## Methods (one paragraph)

Monthly time series of regional-mean total AOD (MODIS Terra + Aqua + VIIRS-SNPP + VIIRS-NOAA20), MERRA-2-derived smoke fraction, and CERES EBAF Edition4.2.1 TOA + SFC SW/LW/Net (clear-sky and all-sky) over 2000-03 → 2025-12. Smoke AOD = smoke_fraction × MODIS_Terra_AOD with smoke_fraction = (BCEXTTAU + OC_bb_share · OCEXTTAU) / TOTEXTTAU. Anomalies are month-of-year-climatology subtractions. Radiative-efficiency slope β estimated by OLS with HAC standard errors, controlling for cloud fraction, TQV, month-of-year fixed effects, and a linear trend.

## Headline numbers

_To fill from `output/pacific-northwest/data/regression_table.csv`._

| Response | β [W m⁻² per AOD] | SE | n | R² |
|---|---|---|---|---|
| TOA SW clear-sky | _x.xx_ | _x.xx_ | _xxx_ | _x.xx_ |
| TOA SW all-sky | _x.xx_ | _x.xx_ | _xxx_ | _x.xx_ |
| SFC SW down clear-sky | _x.xx_ | _x.xx_ | _xxx_ | _x.xx_ |
| SFC SW down all-sky | _x.xx_ | _x.xx_ | _xxx_ | _x.xx_ |

## Figures

_All in `output/pacific-northwest/plots/`._

| # | File | What it shows |
|---|---|---|
| 1 | `aod_total_timeseries.png` | Total AOD across all observed sources |
| 2 | `smoke_fraction_timeseries.png` | MERRA-2-derived smoke fraction |
| 3 | `smoke_aod_timeseries.png` | Smoke AOD with platform spread |
| 4 | `ceres_toa_anomaly.png` | TOA SW/LW/Net anomalies, clear- vs. all-sky |
| 5 | `ceres_sfc_anomaly.png` | SFC SW/LW/Net anomalies, clear- vs. all-sky |
| 6 | `scatter_dF_TOA_vs_smoke.png` | ΔF_TOA_SW vs. smoke AOD scatter (β annotated) |
| 7 | `scatter_dF_SFC_vs_smoke.png` | ΔF_SFC_SW vs. smoke AOD scatter |
| 8 | `seasonal_climatology.png` | Monthly climatology, smoke AOD + ΔF_TOA_SW |
| 10 | `qfed_emissions_timeseries.png` | QFED BC/OC/CO with smoke-AOD overlay |
| 11 | `aeronet_vs_modis_scatter.png` | AERONET vs. MODIS gridcell validation |
| 12 | `cloud_fraction_timeseries.png` | Cloud-fraction covariate |
| 13 | `merra2_obs_scaling.png` | MERRA-2 vs. MODIS magnitude check |

## Open follow-ups

- Plot 9 (spatial maps) requires a gridded merged file; pipeline currently writes regional-mean only. Add a parallel gridded path in stage 4 in a follow-on PR.
- UVAI cross-check (OMI/OMPS) — pending fetcher.
- Multi-region scaling — generalize `firex/regions.py` and parametrize `run_pnw.py`.
```

- [ ] **Step 3: Commit run artifacts and report skeleton**

```bash
git add output/pacific-northwest/reports/results-skeleton.md
# Outputs themselves (data/*.nc, plots/*.png) stay un-committed; they are regenerable
echo "output/pacific-northwest/data/" >> .gitignore
echo "output/pacific-northwest/logs/" >> .gitignore
echo "output/pacific-northwest/plots/" >> .gitignore
git add .gitignore
git commit -m "docs: PNW results-skeleton report; ignore regenerable outputs"
```

---

## Self-Review Notes (filled by author)

**Spec coverage check (run after writing the plan):**

| Spec section | Implemented in task |
|---|---|
| §Architecture / repo layout | Tasks 0–3, 14 |
| §Stage 1 mask | Task 2 |
| §Stage 2 per-dataset loaders | Tasks 5–10 |
| §Stage 3 smoke attribution | Task 11 |
| §Stage 4 merge + anomaly | Task 12 + Task 16 stage4 |
| §Stage 5 regression | Task 13 + Task 16 stage5 |
| §Stage 6 plots (×13) | Tasks 14, 15a, 15b, 15c |
| §Plot inventory (#1–#13) | Tasks 15a, 15b, 15c |
| §Error-handling: stream codes | Loader globs + sort: latest-stream-wins (Task 16 stage 2) |
| §Error-handling: OC bb-split fallback | Task 11 |
| §Error-handling: VIIRS-NOAA20 NaN pre-2018 | Tolerated by loader + plots dropping NaN |
| §Error-handling: Y2016 QFED skip | Task 9 |
| §Error-handling: AERONET sparse sites | Task 10 (filter to bbox; sparse handling done at plot time) |
| §Logging / git SHA / atomic writes | Tasks 3, 16 |
| §Idempotency (mtime skip + atomic) | Tasks 3, 16 |
| §Defaults table (bbox, time slice, ...) | Task 16 config |
| §Test inventory | Tasks 1–17 |

**Acknowledged gap:** Plot 9 `spatial_maps_peak_year` (Task 15c) requires a gridded version of the merged dataset; the orchestrator (Task 16) currently writes regional-mean only and logs a skip. Filling this in is captured in the report skeleton's "Open follow-ups". The skip is by design for prototype scope; making plot 9 fully wired up belongs in a follow-on plan that adds a `merged_gridded.nc` companion output.
