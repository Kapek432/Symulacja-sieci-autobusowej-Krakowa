import pandas as pd
import pytest

from krakbus.ingest.gtfs_versions import (
    active_services,
    assign_service_date,
    effective_calendar,
    gtfs_day_start,
)


def _ts(local: str) -> int:
    return int(pd.Timestamp(local, tz="Europe/Warsaw").timestamp())


def _cal(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["service_id", "date"])


def test_gtfs_day_start_is_local_midnight_on_regular_day() -> None:
    start = gtfs_day_start(pd.Series(["20261012"]))
    assert start.iloc[0] == _ts("2026-10-12 00:00")


def test_gtfs_day_start_uses_noon_minus_12h_on_dst_change() -> None:
    # 25.10.2026 ma 25 h (CEST -> CET); poludnie minus 12 h to 01:00 CEST, godzine po polnocy
    start = gtfs_day_start(pd.Series(["20261025"]))
    assert start.iloc[0] == _ts("2026-10-25 12:00") - 12 * 3600
    assert start.iloc[0] == _ts("2026-10-25 00:00") + 3600


def test_unknown_trip_gets_no_service_date() -> None:
    date, ref = assign_service_date(
        pd.Series([_ts("2026-10-09 08:00")]),
        pd.Series([float("nan")]),
        pd.Series([None], dtype=object),
        _cal([("20261005_4", "20261009")]),
    )
    assert date.isna().all()
    assert ref.isna().all()


def test_inactive_service_gets_no_service_date() -> None:
    date, _ = assign_service_date(
        pd.Series([_ts("2026-10-09 08:00")]),
        pd.Series([8 * 3600.0]),
        pd.Series(["20261005_4"]),
        _cal([("20261005_4", "20261016")]),
    )
    assert date.isna().all()


def test_regular_trip_gets_today() -> None:
    date, ref = assign_service_date(
        pd.Series([_ts("2026-10-09 08:02")]),
        pd.Series([8 * 3600.0]),
        pd.Series(["20261005_4"]),
        _cal([("20261005_4", "20261009")]),
    )
    assert date.iloc[0] == "2026-10-09"
    assert _ts("2026-10-09 08:02") - (ref.iloc[0] + 8 * 3600) == 120


def test_after_midnight_trip_of_previous_service_day() -> None:
    # kurs z doby 9.10 o rozkladowej 24:30 (88200 s), przyjazd 10.10 o 00:33
    date, _ = assign_service_date(
        pd.Series([_ts("2026-10-10 00:33")]),
        pd.Series([88200.0]),
        pd.Series(["20261005_4"]),
        _cal([("20261005_4", "20261009"), ("20261005_4", "20261010")]),
    )
    assert date.iloc[0] == "2026-10-09"


def test_vehicle_early_for_next_service_day() -> None:
    # pojazd na petli przed polnoca z kursem doby nastepnej o 00:05
    date, _ = assign_service_date(
        pd.Series([_ts("2026-10-12 23:58")]),
        pd.Series([300.0]),
        pd.Series(["20261013_1"]),
        _cal([("20261013_1", "20261013")]),
    )
    assert date.iloc[0] == "2026-10-13"


def test_candidate_restricted_to_active_dates() -> None:
    # nocny kurs aktywny tylko 13.10; bez kalendarza wygraloby "dzis" (12.10)
    date, _ = assign_service_date(
        pd.Series([_ts("2026-10-12 23:30")]),
        pd.Series([23 * 3600 + 1800.0]),
        pd.Series(["20261013_1"]),
        _cal([("20261013_1", "20261013")]),
    )
    assert date.iloc[0] == "2026-10-13"


def test_active_services_applies_removals_and_weekly_calendar() -> None:
    cal = pd.DataFrame(
        [["W", "1", "1", "1", "1", "1", "0", "0", "20261012", "20261018"]],
        columns=[
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ],
    )
    cd = pd.DataFrame(
        [["W", "20261014", "2"], ["X", "20261018", "1"]],
        columns=["service_id", "date", "exception_type"],
    )
    act = active_services(cal, cd)
    got = set(map(tuple, act[["service_id", "date"]].to_numpy()))
    assert got == {
        ("W", "20261012"),
        ("W", "20261013"),
        ("W", "20261015"),
        ("W", "20261016"),
        ("X", "20261018"),
    }


def test_effective_calendar_takes_newest_version_covering_each_day() -> None:
    old = _cal([("20261005_1", "20261009"), ("20261005_1", "20261012")])
    new = _cal([("20261010_1", "20261012")])
    eff = effective_calendar({"20261008_081112": old, "20261012_123022": new})
    by_day = eff.groupby("date")["service_id"].apply(set).to_dict()
    assert by_day == {"20261009": {"20261005_1"}, "20261012": {"20261010_1"}}
    assert eff.set_index("date").loc["20261012", "gtfs_stamp"] == "20261012_123022"


def test_nullable_inputs_from_pandas_parsing() -> None:
    date, ref = assign_service_date(
        pd.Series([_ts("2026-10-09 08:02"), _ts("2026-10-09 08:02")], dtype="Int64"),
        pd.Series([8 * 3600, pd.NA], dtype="Int64"),
        pd.Series(["20261005_4", None], dtype=object),
        _cal([("20261005_4", "20261009")]),
    )
    assert date.iloc[0] == "2026-10-09"
    assert pd.isna(date.iloc[1])
    assert ref.notna().iloc[0] and ref.isna().iloc[1]


@pytest.mark.parametrize("n", [0, 3])
def test_assign_service_date_keeps_index(n: int) -> None:
    idx = pd.RangeIndex(10, 10 + n)
    date, ref = assign_service_date(
        pd.Series([_ts("2026-10-09 08:00")] * n, index=idx, dtype="int64"),
        pd.Series([8 * 3600.0] * n, index=idx, dtype=float),
        pd.Series(["20261005_4"] * n, index=idx, dtype=object),
        _cal([("20261005_4", "20261009")]),
    )
    assert list(date.index) == list(idx)
    assert list(ref.index) == list(idx)
