from pathlib import Path

import pandas as pd

from krakbus.ingest.raw import PartitionCache, list_partitions, window_dates


def _write(root: Path, day: str, name: str, values: list[int]) -> None:
    d = root / f"date={day}"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"v": values}).to_parquet(d / name, index=False)


def test_window_dates_cross_month() -> None:
    assert window_dates("2026-11-01") == ["2026-10-31", "2026-11-01", "2026-11-02"]


def test_cache_window_order_and_eviction(tmp_path: Path) -> None:
    _write(tmp_path, "2026-10-05", "part-000000.parquet", [1])
    _write(tmp_path, "2026-10-06", "part-000000.parquet", [2])
    _write(tmp_path, "2026-10-06", "part-100000.parquet", [3])
    _write(tmp_path, "2026-10-07", "part-000000.parquet", [4])
    parts = list_partitions(tmp_path)
    assert list(parts) == ["2026-10-05", "2026-10-06", "2026-10-07"]
    cache = PartitionCache(parts, ["v"])
    assert cache.window(window_dates("2026-10-06"))["v"].tolist() == [1, 2, 3, 4]
    assert cache.window(window_dates("2026-10-07"))["v"].tolist() == [2, 3, 4]
    assert set(cache._loaded) == {"2026-10-06", "2026-10-07", "2026-10-08"}
