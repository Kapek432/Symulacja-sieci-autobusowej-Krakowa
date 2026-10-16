import json
import math
import zipfile

import numpy as np
import pandas as pd
import pytest

from krakbus.viz.export_network import (
    SCHEMA_VERSION,
    build_network,
    read_gtfs,
    write_network,
)
from krakbus.viz.geo import EARTH_R, ORIGIN_LAT, ORIGIN_LON


def _ll(x: float, z: float) -> tuple[float, float]:
    """Odwrotnosc `to_xz`: metry od ORIGIN na lat/lon."""
    lat = ORIGIN_LAT + math.degrees(z / EARTH_R)
    lon = ORIGIN_LON + math.degrees(x / (EARTH_R * math.cos(math.radians(ORIGIN_LAT))))
    return lat, lon


STOPS_XZ = {
    "s1": (0, 0),
    "s2": (1000, 500),
    "s3": (1000, 1000),
    "far": (1500, 1300),  # 300 m od ksztaltu B
}
SHAPES_XZ = {
    "shA": [(0, 0), (1000, 0), (1000, 1000)],  # litera L
    "shB": [(1000, 500), (1000, 1000), (2000, 1000)],
}
TRIPS = [  # trip_id, route_id, shape_id, przystanki
    ("tA", "A", "shA", ["s1", "s2", "s3"]),
    ("tB", "B", "shB", ["s2", "s3", "far"]),
    ("tC", "C", "", ["s1", "s3"]),
]


@pytest.fixture
def mini_gtfs() -> dict[str, pd.DataFrame]:
    stops = [(i, *map(str, _ll(*xz)), i.upper()) for i, xz in STOPS_XZ.items()]
    shapes = [
        (sid, str(lat), str(lon), str(k))
        for sid, pts in SHAPES_XZ.items()
        for k, (lat, lon) in enumerate(_ll(*p) for p in pts)
    ]
    st = [(t, s, str(k)) for t, _, _, seq in TRIPS for k, s in enumerate(seq, start=1)]
    return {
        "stops": pd.DataFrame(
            stops, columns=["stop_id", "stop_lat", "stop_lon", "stop_name"]
        ),
        "trips": pd.DataFrame(
            [(t, r, sh) for t, r, sh, _ in TRIPS],
            columns=["trip_id", "route_id", "shape_id"],
        ),
        "stop_times": pd.DataFrame(st, columns=["trip_id", "stop_id", "stop_sequence"]),
        "shapes": pd.DataFrame(
            shapes,
            columns=["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
        ),
    }


def _seg(net: dict, a: str, b: str) -> dict:
    return next(s for s in net["segments"] if (s["from_stop"], s["to_stop"]) == (a, b))


def test_shared_segment_merged(mini_gtfs):
    net = build_network(mini_gtfs, None)
    seg = [s for s in net["segments"] if (s["from_stop"], s["to_stop"]) == ("s2", "s3")]
    assert len(seg) == 1 and seg[0]["routes"] == ["A", "B"]


def test_segment_follows_shape(mini_gtfs):
    seg = _seg(build_network(mini_gtfs, ["A"]), "s1", "s2")
    assert len(seg["points"]) >= 6  # wiecej niz prosta (2 punkty = 4 liczby)


def test_segment_endpoints_near_stops(mini_gtfs):
    net = build_network(mini_gtfs, ["A"])
    stops = {s["stop_id"]: s for s in net["stops"]}
    p = _seg(net, "s1", "s2")["points"]
    assert math.dist(p[:2], (stops["s1"]["x"], stops["s1"]["z"])) < 15


def test_no_shape_is_straight(mini_gtfs):
    net = build_network(mini_gtfs, ["C"])
    assert all(len(s["points"]) == 4 for s in net["segments"])
    assert net["meta"]["n_straight"]["no_shape"] == len(net["segments"])


def test_far_stop_is_straight(mini_gtfs, caplog):
    net = build_network(mini_gtfs, ["B"])
    assert net["meta"]["n_straight"]["far_stop"] >= 1 and "far" in caplog.text
    assert len(_seg(net, "s3", "far")["points"]) == 4


def test_routes_filter_and_stops_subset(mini_gtfs):
    net = build_network(mini_gtfs, ["A"])
    assert net["meta"]["routes"] == ["A"]
    assert {s["stop_id"] for s in net["stops"]} == {"s1", "s2", "s3"}


def test_meta_and_rounding(mini_gtfs, tmp_path):
    net = build_network(mini_gtfs, None)
    assert net["meta"]["schema_version"] == SCHEMA_VERSION == 1
    assert net["meta"]["origin"] == {
        "lat": 50.0617,
        "lon": 19.9373,
        "axes": "x=east m, z=north m",
    }
    assert {"x_min", "x_max", "z_min", "z_max"} <= net["meta"]["bbox"].keys()
    assert net["meta"]["n_stops"] == len(net["stops"])
    assert all(round(v, 1) == v for s in net["segments"] for v in s["points"])
    path = write_network(net, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["meta"]["n_segments"] == len(
        net["segments"]
    )


def test_unknown_routes_raise(mini_gtfs):
    with pytest.raises(ValueError):
        build_network(mini_gtfs, ["999"])


def test_stop_sequence_sorted_numerically(mini_gtfs):
    st = mini_gtfs["stop_times"]
    st.loc[st["trip_id"] == "tA", "stop_sequence"] = [
        "2",
        "9",
        "10",
    ]  # tekstowo "10" < "2"
    mini_gtfs["stop_times"] = st.iloc[::-1].reset_index(drop=True)
    net = build_network(mini_gtfs, ["A"])
    assert {(s["from_stop"], s["to_stop"]) for s in net["segments"]} == {
        ("s1", "s2"),
        ("s2", "s3"),
    }


def test_read_gtfs(mini_gtfs, tmp_path):
    zp = tmp_path / "g.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for name in ("stops", "trips", "stop_times"):
            z.writestr(f"{name}.txt", mini_gtfs[name].to_csv(index=False))
    with pytest.raises(ValueError, match="shapes.txt"):
        read_gtfs(zp)
    with zipfile.ZipFile(zp, "a") as z:
        z.writestr("shapes.txt", mini_gtfs["shapes"].to_csv(index=False))
    g = read_gtfs(zp)
    assert set(g) == {"stops", "trips", "stop_times", "shapes"}
    assert pd.api.types.is_string_dtype(g["stop_times"]["stop_sequence"])
    assert np.all(g["trips"]["shape_id"].fillna("") == ["shA", "shB", ""])


def test_meta_gtfs_name(mini_gtfs):
    net = build_network(mini_gtfs, None, "GTFS_X.zip")
    assert net["meta"]["gtfs"] == "GTFS_X.zip"
