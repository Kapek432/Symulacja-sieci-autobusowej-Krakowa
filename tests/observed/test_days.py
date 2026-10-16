from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from krakbus.config import DaysConfig
from krakbus.observed.days import (
    COMPLETE,
    GAP,
    PROVISIONAL,
    SPECIAL,
    DayStats,
    assign_role,
    classify_day,
    snapshot_gaps,
)

TZ = "Europe/Warsaw"
CFG = DaysConfig(
    logger_gap_s=120,
    service_hours=(5, 23),
    max_gap_min=30,
    min_events=500,
    night_end_hour=4,
    special_days_file=Path("/nonexistent"),
    split_file=Path("/nonexistent"),
    valid_fraction=0.34,
)
OK = DayStats(
    service_date="2026-10-07",
    n_events=150000,
    n_routes=150,
    n_vehicles=500,
    max_gap_min=1.0,
    gap_min_total=0.0,
    data_until="2026-10-09T01:57:00+02:00",
    calendar_stamp="20261006_120000",
)


def _epoch(s: str) -> float:
    return datetime.fromisoformat(s).replace(tzinfo=ZoneInfo(TZ)).timestamp()


def test_full_day_is_complete() -> None:
    assert classify_day(OK, {}, CFG, TZ) == (COMPLETE, "")


def test_day_without_next_night_is_provisional() -> None:
    s = replace(OK, data_until="2026-10-08T03:59:00+02:00")
    assert classify_day(s, {}, CFG, TZ)[0] == PROVISIONAL
    assert classify_day(replace(OK, data_until=""), {}, CFG, TZ)[0] == PROVISIONAL


def test_provisional_wins_over_special_and_special_over_gap() -> None:
    special = {"2026-10-07": "test"}
    late = replace(OK, data_until="2026-10-08T01:00:00+02:00", max_gap_min=99)
    assert classify_day(late, special, CFG, TZ)[0] == PROVISIONAL
    assert classify_day(replace(OK, max_gap_min=99), special, CFG, TZ) == (
        SPECIAL,
        "test",
    )


def test_long_gap_or_few_events_is_gap() -> None:
    assert classify_day(replace(OK, max_gap_min=31), {}, CFG, TZ)[0] == GAP
    assert classify_day(replace(OK, n_events=10), {}, CFG, TZ)[0] == GAP


def test_dst_day_needs_data_until_local_4am_next_day() -> None:
    s = replace(OK, service_date="2026-10-25", data_until="2026-10-26T04:00:00+01:00")
    assert classify_day(s, {}, CFG, TZ)[0] == COMPLETE
    s = replace(s, data_until="2026-10-26T03:59:00+01:00")
    assert classify_day(s, {}, CFG, TZ)[0] == PROVISIONAL


def test_snapshot_gaps_counts_missing_morning() -> None:
    ts = np.arange(
        _epoch("2026-10-07T06:00:00"), _epoch("2026-10-07T23:00:00") + 1, 20.0
    )
    max_gap, total = snapshot_gaps(ts, "2026-10-07", CFG, TZ)
    assert max_gap == pytest.approx(60)
    assert total == pytest.approx(60)


def test_snapshot_gaps_dense_day() -> None:
    ts = np.arange(_epoch("2026-10-07T04:00:00"), _epoch("2026-10-08T01:00:00"), 20.0)
    max_gap, total = snapshot_gaps(ts, "2026-10-07", CFG, TZ)
    assert max_gap <= 20 / 60
    assert total == 0


def test_roles_before_and_after_split_freeze() -> None:
    assert assign_role("2026-10-07", COMPLETE, {}) == "unassigned"
    assert assign_role("2026-10-07", GAP, {}) == "excluded"
    split = {"calib": {"2026-10-07"}, "excluded": {"2026-10-08"}}
    assert assign_role("2026-10-07", COMPLETE, split) == "calib"
    assert assign_role("2026-10-08", COMPLETE, split) == "excluded"
    assert assign_role("2026-11-20", COMPLETE, split) == "valid"
