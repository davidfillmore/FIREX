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
    # matplotlib infers format from extension, so keep the original extension
    # on the temp path (e.g. fig.png → fig.tmp.png, not fig.png.tmp).
    tmp = path.with_name(path.stem + ".tmp" + path.suffix)
    fig.savefig(tmp)
    tmp.rename(path)
    plt.close(fig)
