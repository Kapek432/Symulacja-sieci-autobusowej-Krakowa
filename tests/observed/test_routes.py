import pandas as pd

from krakbus.observed.routes import RANKING_COLUMNS, route_ranking


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "service_date": ["2026-10-05"] * 4 + ["2026-10-06"] * 2,
            "route_id": ["179", "179", "179", "704", "179", "704"],
            "trip_id": ["a", "a", "b", "c", "a", "c"],
            "vehicle_id": ["1", "1", "2", "3", "1", "3"],
            "arr_delay_s": pd.array([10, 30, 50, 100, 20, 9999], dtype="Float64"),
            "arr_good": [True, True, True, True, True, False],
        }
    )


def _chains() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "route_id": ["179", "179", "179", "704"],
            "next_trip_id": ["b", "x", None, None],
            "cross_route": pd.array([False, True, pd.NA, pd.NA], dtype="boolean"),
            "carried": pd.array([True, pd.NA, pd.NA, pd.NA], dtype="boolean"),
        }
    )


def test_ranking_counts_good_events_and_chain_shares() -> None:
    raw = route_ranking(_events(), _chains())
    assert list(raw.columns) == RANKING_COLUMNS
    r = raw.set_index("route_id")
    assert r.loc["179", "rank"] == 1
    assert r.loc["179", "n_events"] == 4
    assert r.loc["179", "n_days"] == 2
    assert r.loc["179", "n_trips"] == 3
    assert r.loc["179", "med_delay_s"] == 25
    assert r.loc["179", "cross_route_share"] == 0.5
    assert r.loc["179", "carried_share"] == 1.0
    assert r.loc["704", "n_events"] == 1
    assert r.loc["704", "n_transitions"] == 0
    assert r.loc["704", "cum_share_events"] == 1.0
    assert r.loc["179", "cum_share_events"] == 0.8
