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
