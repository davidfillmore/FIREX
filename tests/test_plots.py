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
