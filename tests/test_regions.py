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
