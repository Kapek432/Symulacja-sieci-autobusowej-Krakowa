import json

import numpy as np
import pandas as pd
import pytest

from krakbus.viz.export_unity import (
    EXPORT_COLUMNS,
    SCHEMA_VERSION,
    export_meta,
    export_rows,
    stop_coords,
    write_export,
)
from krakbus.viz.layers import LAYER_COLUMNS


def _layer() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "vehicle_id": ["v1", "v1", "v2"],
            "trip_id": ["A0", "A0", "B0"],
            "route_id": ["A", "A", "B"],
            "direction_id": ["0", "0", "0"],
            "stop_sequence": [2, 1, 1],
            "stop_id": ["s2", "s1", "zz"],
            "arr_ts": [1060.0, 1000.0, 900.0],
            "dep_ts": [np.nan, 1030.0, 950.0],
            "arr_delay_s": [60.0, 0.0, 5.0],
            "dep_delay_s": [np.nan, 30.0, 10.0],
        }
    )[LAYER_COLUMNS]


def test_rows_per_arrival_and_departure_sorted_with_coords(small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    assert list(rows.columns) == EXPORT_COLUMNS
    assert rows["t"].tolist() == [1000.0, 1030.0, 1060.0]
    assert rows["event"].tolist() == ["arr", "dep", "arr"]
    assert rows["delay_s"].tolist() == [0.0, 30.0, 60.0]
    assert rows["lat"].tolist() == [50.00, 50.00, 50.01]
    assert (rows["seed"] == 3).all() and (rows["source"] == "sim").all()


def test_observed_rows_have_null_seed(small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "obs", "obs_2026-10-14", None)
    assert rows["seed"].isna().all()


def test_meta_has_version_bbox_and_counts(small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    meta = export_meta(rows, "sim", "run1", 3, "2026-10-14", ["A"])
    assert meta["schema_version"] == SCHEMA_VERSION == 1
    assert meta["n_rows"] == 3 and meta["n_vehicles"] == 1
    assert meta["t_min"] == 1000.0 and meta["t_max"] == 1060.0
    assert meta["bbox"] == {"lat_min": 50.0, "lat_max": 50.01, "lon_min": 19.9, "lon_max": 19.9}
    assert meta["columns"] == EXPORT_COLUMNS


@pytest.mark.parametrize("fmt", ["parquet", "jsonl"])
def test_write_export_roundtrip(tmp_path, small_stops, fmt) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    meta = export_meta(rows, "sim", "run1", 3, "2026-10-14", None)
    path = write_export(rows, meta, tmp_path, "run1", fmt)
    back = pd.read_parquet(path) if fmt == "parquet" else pd.read_json(path, lines=True)
    assert len(back) == 3 and back["t"].tolist() == [1000.0, 1030.0, 1060.0]
    side = json.loads((tmp_path / "run1.meta.json").read_text(encoding="utf-8"))
    assert side["data_file"] == path.name and side["schema_version"] == 1


def test_unknown_format_rejected(tmp_path, small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    with pytest.raises(ValueError, match="format"):
        write_export(rows, {}, tmp_path, "x", "csv")
