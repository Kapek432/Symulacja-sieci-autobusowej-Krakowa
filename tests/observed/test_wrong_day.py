import pandas as pd

from krakbus.config import EventsConfig
from krakbus.ingest.gtfs_versions import Schedule, gtfs_day_start
from krakbus.observed.events import attach_schedule, index_schedule
from krakbus.observed.wrong_day import classify_delays, remap_wrong_day

TZ = "Europe/Warsaw"
CFG = EventsConfig(
    episode_gap_s=600, unc_ok_s=30, outlier_s=1800, wrong_day_min_s=43200
)


def _schedule(with_twin: bool = True) -> Schedule:
    trips = pd.DataFrame(
        {
            "trip_id": ["mon_t", "thu_t"],
            "route_id": ["179", "179"],
            "service_id": ["mon", "thu"],
            "direction_id": ["0", "0"],
            "block_id": ["179-01", "179-01"],
            "gtfs_stamp": ["20261005_000000"] * 2,
        }
    )
    times = ["06:00:00", "06:10:00", "06:20:00"]
    rows = []
    for t in ["mon_t", "thu_t"]:
        for seq, hhmmss in enumerate(times, start=1):
            rows.append((t, str(seq), f"s{seq}", hhmmss, hhmmss))
    st = pd.DataFrame(
        rows,
        columns=[
            "trip_id",
            "stop_sequence",
            "stop_id",
            "arrival_time",
            "departure_time",
        ],
    )
    if not with_twin:
        st.loc[st["trip_id"] == "thu_t", "arrival_time"] = "07:00:00"
    cal = pd.DataFrame(
        {
            "service_id": ["mon", "thu"],
            "date": ["20261007", "20261008"],
            "exception_type": ["1", "1"],
            "gtfs_stamp": ["20261005_000000"] * 2,
        }
    )
    return Schedule(trips=trips, stop_times=st, stops=pd.DataFrame(), calendar=cal)


def _events_on_thursday() -> pd.DataFrame:
    start = gtfs_day_start(pd.Series(["20261008"]), TZ).iloc[0]
    arr = [
        start + 6 * 3600 + 30,
        start + 6 * 3600 + 600 + 30,
        start + 6 * 3600 + 1200 + 30,
    ]
    return pd.DataFrame(
        {
            "vehicle_id": ["v1"] * 3,
            "trip_id": ["mon_t"] * 3,
            "stop_sequence": [1, 2, 3],
            "arr_ts": arr,
            "dep_ts": [a + 20 for a in arr],
            "arr_unc": [10.0] * 3,
            "dep_unc": [10.0] * 3,
        }
    )


def _run(sched: Schedule) -> pd.DataFrame:
    idx = index_schedule(sched)
    ev = attach_schedule(_events_on_thursday(), idx, CFG, TZ)
    return classify_delays(remap_wrong_day(ev, idx, CFG, TZ), CFG)


def test_trip_from_other_weekday_is_remapped_to_twin() -> None:
    ev = _run(_schedule())
    assert (ev["trip_id"] == "thu_t").all()
    assert (ev["rt_trip_id"] == "mon_t").all()
    assert ev["trip_remapped"].all()
    assert (ev["service_date"] == "2026-10-08").all()
    assert (ev["service_id"] == "thu").all()
    assert ev["arr_delay_s"].tolist() == [30, 30, 30]
    assert (ev["delay_class"] == "ok").all()
    assert ev["arr_good"].tolist() == [False, True, True]


def test_trip_of_never_active_service_gets_date_from_twin() -> None:
    sched = _schedule()
    sched.calendar = sched.calendar[sched.calendar["service_id"] == "thu"]
    idx = index_schedule(sched)
    ev = attach_schedule(_events_on_thursday(), idx, CFG, TZ)
    assert ev["service_date"].isna().all()
    ev = classify_delays(remap_wrong_day(ev, idx, CFG, TZ), CFG)
    assert (ev["trip_id"] == "thu_t").all()
    assert (ev["service_date"] == "2026-10-08").all()
    assert ev["arr_delay_s"].tolist() == [30, 30, 30]


def test_same_trip_on_two_days_only_wrong_day_is_remapped() -> None:
    sched = _schedule()
    wed = _events_on_thursday()
    wed[["arr_ts", "dep_ts"]] -= 86400
    both = pd.concat([wed, _events_on_thursday()], ignore_index=True)
    idx = index_schedule(sched)
    ev = classify_delays(
        remap_wrong_day(attach_schedule(both, idx, CFG, TZ), idx, CFG, TZ), CFG
    )
    assert ev["trip_id"].tolist() == ["mon_t"] * 3 + ["thu_t"] * 3
    assert ev["service_date"].tolist() == ["2026-10-07"] * 3 + ["2026-10-08"] * 3
    assert (ev["arr_delay_s"] == 30).all()


def test_without_identical_twin_stays_wrong_service_day() -> None:
    ev = _run(_schedule(with_twin=False))
    assert (ev["trip_id"] == "mon_t").all()
    assert not ev["trip_remapped"].any()
    assert (ev["service_date"] == "2026-10-07").all()
    assert (ev["delay_class"] == "wrong_service_day").all()
    assert not ev["arr_good"].any() and not ev["dep_good"].any()


def test_classify_delays_thresholds() -> None:
    ev = pd.DataFrame(
        {
            "arr_delay_s": [100.0, -1801.0, 50000.0, None],
            "dep_delay_s": [100.0, 0.0, 0.0, 0.0],
            "arr_ok": [True, True, True, True],
            "dep_ok": [True, True, True, True],
        }
    )
    out = classify_delays(ev, CFG)
    assert out["delay_class"].tolist()[:3] == ["ok", "outlier", "wrong_service_day"]
    assert pd.isna(out["delay_class"].iloc[3])
    assert out["arr_good"].tolist() == [True, False, False, False]
    # odjazd moze byc dobry przy duzym "opoznieniu przyjazdu" (np. dlugie czekanie na petli)
    assert out["dep_good"].tolist() == [True, True, False, True]
