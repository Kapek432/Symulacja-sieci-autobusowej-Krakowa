import pandas as pd

from krakbus.config import ChainsConfig
from krakbus.observed.chains import build_chains
from krakbus.observed.events import plan_blocks

CFG = ChainsConfig(l_min_s=60)


def _plan() -> pd.DataFrame:
    trips = pd.DataFrame(
        {
            "trip_id": ["a1", "a2", "a3", "b1"],
            "route_id": ["179", "179", "179", "124"],
            "direction_id": ["0", "1", "0", "0"],
            "service_id": ["s"] * 4,
            "block_id": ["179-01", "179-01", "179-01", "124-01"],
        }
    )
    st = pd.DataFrame(
        {
            "trip_id": ["a1", "a1", "a2", "a2", "a3", "a3", "b1", "b1"],
            "stop_sequence": [1, 2, 1, 2, 1, 2, 1, 2],
            "arr_s": [3600, 5400, 6000, 7800, 8400, 10200, 6000, 7000],
            "dep_s": [3600, 5400, 6000, 7800, 8400, 10200, 6000, 7000],
        }
    )
    return plan_blocks(trips, st)


def _ev(rows: list[tuple]) -> pd.DataFrame:
    cols = [
        "vehicle_id",
        "trip_id",
        "arr_ts",
        "dep_ts",
        "is_first",
        "is_last",
        "arr_ok",
        "dep_ok",
        "arr_delay_s",
        "dep_delay_s",
    ]
    return pd.DataFrame(rows, columns=cols).assign(service_date="2026-10-07")


def test_plan_blocks_order_and_next_trip() -> None:
    plan = _plan()
    assert plan.loc["a1", "block_next_trip"] == "a2"
    assert pd.isna(plan.loc["a3", "block_next_trip"])
    assert plan.loc["a2", "blk_idx"] == 1
    assert (plan.loc["a1", "start_s"], plan.loc["a1", "end_s"]) == (3600, 5400)


def test_chain_follows_block_and_carries_delay() -> None:
    ev = _ev(
        [
            ("v1", "a1", 100, 110, True, False, False, True, 0.0, 10.0),
            ("v1", "a1", 1900, 1950, False, True, True, True, 500.0, 520.0),
            ("v1", "a2", 2400, 2450, True, False, False, True, 0.0, 300.0),
        ]
    )
    ch = build_chains(ev, _plan(), CFG).set_index("trip_id")
    a1 = ch.loc["a1"]
    assert a1["chain_idx"] == 0
    assert a1["next_trip_id"] == "a2"
    assert a1["layover_sched_s"] == 600
    assert a1["arr_end_delay_s"] == 500
    assert a1["next_dep_first_delay_s"] == 300
    assert bool(a1["follows_block"]) and not bool(a1["cross_route"])
    # 500 > 600 - 60 jest falszem: opoznienie miesci sie w postoju
    assert not bool(a1["carried"])
    assert pd.isna(ch.loc["a2", "next_trip_id"])
    assert pd.isna(ch.loc["a2", "carried"])


def test_vehicle_switching_route_is_cross_route_and_off_block() -> None:
    ev = _ev(
        [
            ("v1", "a1", 100, 110, True, False, False, True, 0.0, 0.0),
            ("v1", "a1", 1900, 1950, False, True, True, True, 580.0, 580.0),
            ("v1", "b1", 2400, 2450, True, False, False, True, 0.0, 60.0),
        ]
    )
    a1 = build_chains(ev, _plan(), CFG).set_index("trip_id").loc["a1"]
    assert bool(a1["cross_route"])
    assert not bool(a1["follows_block"])
    assert bool(a1["carried"])


def test_first_stop_uses_last_departure_and_bad_end_is_missing() -> None:
    ev = _ev(
        [
            ("v1", "a1", 100, 110, True, False, False, True, 0.0, 10.0),
            ("v1", "a1", 300, 400, True, False, False, True, 0.0, 300.0),
            ("v1", "a1", 1900, 1950, False, True, False, True, 500.0, 520.0),
        ]
    )
    a1 = build_chains(ev, _plan(), CFG).set_index("trip_id").loc["a1"]
    assert a1["dep_first_delay_s"] == 300
    assert pd.isna(a1["arr_end_delay_s"])
