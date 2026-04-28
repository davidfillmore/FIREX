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


def test_eastern_australia_bbox():
    eau = REGIONS["eastern-australia"]
    assert isinstance(eau, Region)
    assert eau.lon_min == 140.0 and eau.lon_max == 154.0
    assert eau.lat_min == -44.0 and eau.lat_max == -25.0
    # Sydney (~-33.9, 151.2) and Melbourne (~-37.8, 145) inside; Perth (~-32, 116) outside.
    assert eau.contains(-33.9, 151.2)
    assert eau.contains(-37.8, 145.0)
    assert not eau.contains(-32.0, 116.0)
