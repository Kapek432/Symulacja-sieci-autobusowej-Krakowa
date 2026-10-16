from pathlib import Path

import pandas as pd

from krakbus.ingest.raw import list_partitions
from krakbus.observed.manifest import calendar_owners, day_fingerprint
from krakbus.observed.pipeline import days_to_build
from krakbus.observed.store import KINDS

PARAMS = {"events": {"episode_gap_s": 600, "unc_ok_s": 30}, "chains": {"l_min_s": 60}}
DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]


def _part(root: Path, day: str, name: str, size: int = 10) -> None:
    d = root / f"date={day}"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(b"x" * size)


def _fingerprints(root: Path, owners: dict[str, str]) -> dict[str, str]:
    parts = list_partitions(root)
    return {d: day_fingerprint(d, parts, owners, PARAMS, "1") for d in parts}


def _manifest(fps: dict[str, str]) -> dict:
    return {"days": {d: {"fingerprint": fp} for d, fp in fps.items()}}


def _touch_outputs(processed: Path, days: list[str]) -> None:
    for kind in KINDS:
        (processed / kind).mkdir(parents=True, exist_ok=True)
        for d in days:
            (processed / kind / f"{d}.parquet").write_bytes(b"")


def test_new_part_rebuilds_only_days_whose_window_contains_it(tmp_path: Path) -> None:
    raw, processed = tmp_path / "vp", tmp_path / "processed"
    for d in DAYS:
        _part(raw, d, "part-000000.parquet")
    _touch_outputs(processed, DAYS)
    before = _fingerprints(raw, {})
    _part(raw, "2026-10-08", "part-120000.parquet")
    todo = days_to_build(_fingerprints(raw, {}), _manifest(before), processed, set())
    assert todo == ["2026-10-07", "2026-10-08"]


def test_unchanged_inputs_rebuild_nothing(tmp_path: Path) -> None:
    raw, processed = tmp_path / "vp", tmp_path / "processed"
    for d in DAYS:
        _part(raw, d, "part-000000.parquet")
    _touch_outputs(processed, DAYS)
    fps = _fingerprints(raw, {})
    assert days_to_build(fps, _manifest(fps), processed, set()) == []
    assert days_to_build(fps, _manifest(fps), processed, {"2026-10-06"}) == [
        "2026-10-06"
    ]


def test_missing_output_file_is_rebuilt(tmp_path: Path) -> None:
    raw, processed = tmp_path / "vp", tmp_path / "processed"
    for d in DAYS:
        _part(raw, d, "part-000000.parquet")
    _touch_outputs(processed, DAYS[:-1])
    fps = _fingerprints(raw, {})
    assert days_to_build(fps, _manifest(fps), processed, set()) == ["2026-10-08"]
    (processed / "chains" / "2026-10-05.parquet").unlink()
    assert days_to_build(fps, _manifest(fps), processed, set()) == [
        "2026-10-05",
        "2026-10-08",
    ]


def test_day_without_events_is_not_rebuilt_forever(tmp_path: Path) -> None:
    raw, processed = tmp_path / "vp", tmp_path / "processed"
    _part(raw, "2026-10-05", "part-000000.parquet")
    fps = _fingerprints(raw, {})
    manifest = {
        "days": {
            d: {"fingerprint": fp, "stats": {"n_events": 0}} for d, fp in fps.items()
        }
    }
    assert days_to_build(fps, manifest, processed, set()) == []


def test_new_calendar_owner_rebuilds_only_neighbouring_days(tmp_path: Path) -> None:
    raw, processed = tmp_path / "vp", tmp_path / "processed"
    for d in DAYS:
        _part(raw, d, "part-000000.parquet")
    _touch_outputs(processed, DAYS)
    old = {"20261005": "A", "20261006": "A", "20261007": "A", "20261008": "A"}
    new = {**old, "20261008": "B"}
    todo = days_to_build(
        _fingerprints(raw, new), _manifest(_fingerprints(raw, old)), processed, set()
    )
    assert todo == ["2026-10-07", "2026-10-08"]


def test_calendar_owner_is_newest_version_with_entry() -> None:
    per_version = {
        "20261005_000000": pd.DataFrame(
            {"service_id": ["s1", "s1"], "date": ["20261005", "20261006"]}
        ),
        "20261006_000000": pd.DataFrame({"service_id": ["s2"], "date": ["20261006"]}),
    }
    assert calendar_owners(per_version) == {
        "20261005": "20261005_000000",
        "20261006": "20261006_000000",
    }
