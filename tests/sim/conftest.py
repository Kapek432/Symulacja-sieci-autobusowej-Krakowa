from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from krakbus.ingest.gtfs_versions import Schedule
from krakbus.observed.events import ScheduleIndex, index_schedule
from krakbus.sim.network import Network, build_network
from krakbus.sim.params import EtaParams, LoopParams, ModelParams, UParams

TZ = "Europe/Warsaw"
DATE = "2026-10-14"
TRIPS = [
    ("A0", "A", "0", "b1", [("s1", "06:00"), ("s2", "06:05"), ("s3", "06:10"), ("s4", "06:15")]),
    ("A1", "A", "1", "b1", [("s4", "06:20"), ("s3", "06:25"), ("s2", "06:30"), ("s1", "06:35")]),
    ("B0", "B", "0", "b2", [("x1", "06:00"), ("s2", "06:04"), ("s3", "06:09"), ("x2", "06:14")]),
    ("B1", "B", "1", "b3", [("x2", "07:00"), ("s3", "07:05"), ("x1", "07:15")]),
    ("A2", "A", "0", "b3", [("s1", "07:20"), ("s2", "07:25"), ("s3", "07:30")]),
]


def make_schedule(trips: list[tuple[str, str, str, str, list[tuple[str, str]]]]) -> Schedule:
    tr = pd.DataFrame(
        [(t, r, d, b) for t, r, d, b, _ in trips],
        columns=["trip_id", "route_id", "direction_id", "block_id"],
    ).assign(service_id="svc", gtfs_stamp="20261012_000000")
    rows = [
        (t, str(seq), stop, f"{hhmm}:00", f"{hhmm}:00")
        for t, _, _, _, stops in trips
        for seq, (stop, hhmm) in enumerate(stops, start=1)
    ]
    st = pd.DataFrame(
        rows, columns=["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time"]
    )
    cal = pd.DataFrame(
        {
            "service_id": ["svc"],
            "date": ["20261014"],
            "exception_type": ["1"],
            "gtfs_stamp": ["20261012_000000"],
        }
    )
    return Schedule(trips=tr, stop_times=st, stops=pd.DataFrame(), calendar=cal)


def zero_model(**changes: object) -> ModelParams:
    base = ModelParams(
        periods={"szczyt_rano": (7, 9)},
        drift_s_per_min={"szczyt_rano": 0.0, "poza": 0.0},
        day_effect_sd_s=0.0,
        u=UParams(spatial="independent", window_s=900, sigma_s=0.0, rho=0.7),
        eta=EtaParams(df=3.0, scale_s=0.0),
        loop=LoopParams(l_min_s=60.0, delta_mean_s=0.0, delta_sd_s=0.0),
        gamma=0.0,
    )
    return replace(base, **changes)


def pos(net: Network, trip_id: str) -> int:
    return int(net.trips.index.get_loc(trip_id))


def row(net: Network, trip_id: str, stop_id: str) -> int:
    st = net.stop_times
    return int(np.flatnonzero((st["trip_id"] == trip_id) & (st["stop_id"] == stop_id))[0])


@pytest.fixture
def small_idx() -> ScheduleIndex:
    return index_schedule(make_schedule(TRIPS))


@pytest.fixture
def small_net(small_idx: ScheduleIndex) -> Network:
    return build_network(small_idx, DATE, TZ)
