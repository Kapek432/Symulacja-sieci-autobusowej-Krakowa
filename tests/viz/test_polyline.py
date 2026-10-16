"""Testy geometrii lamanej: rzutowanie przystankow, ciecie, upraszczanie."""

import numpy as np
import pytest

from krakbus.viz.polyline import cut_polyline, project_stops, simplify

L = np.array([[0, 0], [100, 0], [100, 100]], float)  # litera L, dlugosc 200


def test_project_simple():
    s, d = project_stops(L, np.array([[50, 5], [105, 50]], float))
    assert s == pytest.approx([50, 150])
    assert d == pytest.approx([5, 5])


def test_project_out_and_back_same_street():
    # tam po y=0, z powrotem po y=8 (ta sama ulica, dwa pasy)
    line = np.array([[0, 0], [200, 0], [200, 8], [0, 8]], float)  # dlugosc 408
    stops = np.array([[50, 1], [150, 1], [150, 7], [50, 7]], float)
    s, _ = project_stops(line, stops)
    assert s == pytest.approx([50, 150, 258, 358])


def test_project_monotonic_when_best_is_behind():
    # przystanek 2 lezy blizej poczatku niz rzut przystanku 1 -> nie cofamy sie
    s, _ = project_stops(L, np.array([[80, 0], [60, 3]], float))
    assert s[1] >= s[0]


def test_cut_endpoints_and_inner_vertex():
    c = cut_polyline(L, 50, 150)
    assert c[0] == pytest.approx([50, 0])
    assert c[-1] == pytest.approx([100, 50])
    assert [100, 0] in c.tolist()


def test_cut_consecutive_pieces_touch():
    a, b = cut_polyline(L, 0, 120), cut_polyline(L, 120, 200)
    assert a[-1] == pytest.approx(b[0])


def test_cut_degenerate_gives_two_points():
    assert len(cut_polyline(L, 70, 70)) == 2


def test_simplify_keeps_ends_and_tolerance():
    pts = np.array([[0, 0], [50, 1], [100, 0], [100, 100]], float)
    out = simplify(pts, 2.0)
    assert out[0].tolist() == [0, 0]
    assert out[-1].tolist() == [100, 100]
    assert [50, 1] not in out.tolist()
    assert [100, 0] in out.tolist()
