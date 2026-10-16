"""Warstwy zdarzen do wizualizacji i eksportu: obserwacja dnia i przebieg symulacji w jednym schemacie."""

import json
from pathlib import Path

import pandas as pd

from krakbus.observed.days import COMPLETE
from krakbus.observed.store import load_days, select_days
from krakbus.sim.network import Network

LAYER_COLUMNS = [
    "vehicle_id",
    "trip_id",
    "route_id",
    "direction_id",
    "stop_sequence",
    "stop_id",
    "arr_ts",
    "dep_ts",
    "arr_delay_s",
    "dep_delay_s",
]
FLOAT_COLUMNS = ["arr_ts", "dep_ts", "arr_delay_s", "dep_delay_s"]


def _normalize(ev: pd.DataFrame, routes: list[str] | None) -> pd.DataFrame:
    if routes is not None:
        ev = ev[ev["route_id"].astype(str).isin(routes)]
    out = ev[LAYER_COLUMNS].astype({c: "float64" for c in FLOAT_COLUMNS})
    return out.astype({"route_id": str, "vehicle_id": str, "trip_id": str}).reset_index(drop=True)


def observed_layer(ev: pd.DataFrame, net: Network, routes: list[str] | None) -> pd.DataFrame:
    """Zdarzenia obserwowane z `delay_class` = ok, z kierunkiem kursu z rozkladu dnia.

    Args:
        ev: zdarzenia dnia z `load_events`.
        net: siec tego dnia (zrodlo `direction_id`).
        routes: linie; None = wszystkie.

    Returns:
        Ramka `LAYER_COLUMNS`; czasy i opoznienia jako float (brak = NaN).
    """
    ok = ev[ev["delay_class"].fillna("") == "ok"]
    ok = ok.assign(direction_id=ok["trip_id"].map(net.trips["direction_id"]))
    return _normalize(ok, routes)


def sim_layer(run_dir: Path, routes: list[str] | None) -> tuple[pd.DataFrame, dict]:
    """Zdarzenia przebiegu z `data/processed/sim/<run_id>/` i jego `run.json`."""
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    return _normalize(pd.read_parquet(run_dir / "events.parquet"), routes), meta


def last_complete_workday(processed: Path) -> str:
    """Ostatni dzien roboczy o statusie `complete` z `days.csv`.

    Raises:
        ValueError: brak takiego dnia.
    """
    reg = load_days(processed)
    work = reg[pd.to_datetime(reg["service_date"]).dt.dayofweek < 5]
    days = select_days(work, statuses=(COMPLETE,))
    if not days:
        raise ValueError("brak dni roboczych complete; najpierw uv run build-events")
    return days[-1]
