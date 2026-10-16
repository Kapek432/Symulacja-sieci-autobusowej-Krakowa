import pandas as pd

from krakbus.observed.events import clean_positions, hms, stop_episodes


def _vp(rows: list[tuple[str, str, int, int, int]]) -> pd.DataFrame:
    df = pd.DataFrame(
        rows,
        columns=[
            "vehicle_id",
            "trip_id",
            "veh_ts",
            "current_stop_sequence",
            "current_status",
        ],
    )
    return df.assign(fetched_at=df["veh_ts"] + 5.0, lat=50.0, lon=19.9)


def test_hms_after_midnight_and_missing() -> None:
    out = hms(pd.Series(["25:01:02", None, " 07:00:00"]))
    assert out.iloc[0] == 25 * 3600 + 62
    assert pd.isna(out.iloc[1])
    assert out.iloc[2] == 7 * 3600


def test_episode_bounds_and_uncertainty() -> None:
    vp = _vp(
        [
            ("v1", "t1", 1000, 1, 2),
            ("v1", "t1", 1010, 2, 1),
            ("v1", "t1", 1030, 2, 1),
            ("v1", "t1", 1030, 2, 1),
            ("v1", "t1", 1050, 3, 2),
        ]
    )
    ev = stop_episodes(clean_positions(vp), episode_gap_s=600)
    assert len(ev) == 1
    e = ev.iloc[0]
    assert (e["arr_ts"], e["dep_ts"], e["n"]) == (1010, 1030, 2)
    assert (e["arr_unc"], e["dep_unc"]) == (10, 20)


def test_long_pause_at_same_stop_splits_episode() -> None:
    vp = _vp([("v1", "t1", 1000, 2, 1), ("v1", "t1", 1000 + 601, 2, 1)])
    ev = stop_episodes(clean_positions(vp), episode_gap_s=600)
    assert len(ev) == 2
    assert pd.isna(ev["arr_unc"].iloc[0])
