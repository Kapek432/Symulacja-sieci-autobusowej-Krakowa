import numpy as np
import pytest

from krakbus.viz.geo import ORIGIN_LAT, ORIGIN_LON, to_xz


def test_origin_is_zero():
    x, z = to_xz(ORIGIN_LAT, ORIGIN_LON)
    assert abs(float(x)) < 1e-9 and abs(float(z)) < 1e-9


def test_matches_positions_file_row():
    # wiersz z obs_peak30.jsonl: lat 50.01012, lon 19.992535 -> x 3942.8, z -5735.4
    x, z = to_xz(np.array([50.01012]), np.array([19.992535]))
    assert x[0] == pytest.approx(3942.8, abs=0.1)
    assert z[0] == pytest.approx(-5735.4, abs=0.1)


def test_axes_east_north():
    x, z = to_xz(np.array([ORIGIN_LAT + 0.01]), np.array([ORIGIN_LON + 0.01]))
    assert x[0] > 0 and z[0] > 0
