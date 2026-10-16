import json

import numpy as np
import pandas as pd

from krakbus.viz.layers import LAYER_COLUMNS, observed_layer, sim_layer


def _as_observed(sim_events: pd.DataFrame) -> pd.DataFrame:
    obs = sim_events.drop(columns="direction_id").copy()
    obs["arr_delay_s"] = obs["arr_delay_s"].round().astype("Int64")
    obs.loc[0, "arr_delay_s"] = pd.NA
    obs["arr_ts"] = obs["arr_ts"].round().astype("int64")
    obs["delay_class"] = pd.array(["ok"] * len(obs), dtype="string")
    obs.loc[1, "delay_class"] = "outlier"
    obs.loc[2, "delay_class"] = pd.NA
    return obs


def test_observed_layer_keeps_ok_and_adds_direction(small_net, sim_events) -> None:
    obs = _as_observed(sim_events)
    layer = observed_layer(obs, small_net, None)
    assert list(layer.columns) == LAYER_COLUMNS
    assert len(layer) == len(obs) - 2
    assert set(layer["direction_id"]) == {"0", "1"}
    assert layer["arr_delay_s"].dtype == np.float64 and layer["arr_delay_s"].isna().sum() == 1
    assert layer["arr_ts"].dtype == np.float64


def test_observed_layer_filters_routes(small_net, sim_events) -> None:
    layer = observed_layer(_as_observed(sim_events), small_net, ["B"])
    assert set(layer["route_id"]) == {"B"}


def test_sim_layer_reads_run_dir(tmp_path, sim_events) -> None:
    sim_events.to_parquet(tmp_path / "events.parquet", index=False)
    (tmp_path / "run.json").write_text(json.dumps({"run_id": "r", "seed": 0}), encoding="utf-8")
    layer, meta = sim_layer(tmp_path, ["A"])
    assert meta["run_id"] == "r"
    assert list(layer.columns) == LAYER_COLUMNS
    assert set(layer["trip_id"]) == {"A0", "A1", "A2"}
