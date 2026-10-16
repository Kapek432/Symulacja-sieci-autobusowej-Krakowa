import pandas as pd
import yaml

from krakbus.observed.split import day_generations, propose_split, split_yaml


def _gens() -> pd.Series:
    days = {
        "2026-10-05": "20261005",
        "2026-10-06": "20261005",
        "2026-10-07": "20261005",
        "2026-10-08": "20261005",
        "2026-10-09": "20261005",
        "2026-10-10": "20261010",
        "2026-10-12": "20261010",
        "2026-10-13": "20261013",
        "2026-10-14": "20261013",
    }
    return pd.Series(days)


def test_valid_days_spread_within_each_stratum() -> None:
    s = propose_split(_gens(), 0.34).set_index("service_date")["role"]
    valid = sorted(s[s == "valid"].index)
    assert valid == ["2026-10-06", "2026-10-08", "2026-10-14"]
    assert s["2026-10-10"] == "calib"
    assert s["2026-10-12"] == "calib"


def test_split_yaml_round_trips() -> None:
    split = propose_split(_gens(), 0.34)
    raw = yaml.safe_load(split_yaml(split, ["2026-10-04"]))
    assert raw["excluded"] == ["2026-10-04"]
    assert len(raw["calib"]) + len(raw["valid"]) == 9


def test_day_generation_is_dominant_prefix() -> None:
    ev = pd.DataFrame(
        {
            "service_date": ["2026-10-12"] * 3,
            "service_id": ["20261010_1", "20261010_1", "20261013_1"],
        }
    )
    assert day_generations(ev)["2026-10-12"] == "20261010"
