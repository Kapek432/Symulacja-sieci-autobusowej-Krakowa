"""Siec doby obslugi: kursy wszystkich linii, przystanki, odcinki i lancuchy (bloki)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from krakbus.ingest.gtfs_versions import gtfs_day_start
from krakbus.observed.events import ScheduleIndex


@dataclass(frozen=True)
class Network:
    """Siec jednego dnia obslugi w postaci tablic.

    Attributes:
        service_date: data obslugi YYYY-MM-DD.
        day_start: poczatek doby GTFS (lokalne poludnie minus 12 h) w sekundach epoki.
        trips: indeks `trip_id` w kolejnosci (`block_key`, `start_s`); `route_id`, `direction_id`,
            `block_key`, `blk_idx`, `start_s`, `end_s`, `prev_trip` (poprzedni kurs bloku),
            `layover_in_s` (start minus koniec poprzednika), `row_start`, `n_rows`.
        stop_times: wiersze kursow w kolejnosci `trips` i `stop_sequence`; `trip_id`,
            `stop_sequence`, `stop_id`, `arr_s`, `dep_s`, `t_s` (rozkladowy czas odcinka
            wychodzacego, 0 na ostatnim przystanku), `seg_id` (-1 na ostatnim przystanku).
        segments: indeks `seg_id`; `from_stop`, `to_stop` (skierowany odcinek).
    """

    service_date: str
    day_start: float
    trips: pd.DataFrame
    stop_times: pd.DataFrame
    segments: pd.DataFrame


def _day_trips(idx: ScheduleIndex, ymd: str) -> pd.DataFrame:
    services = set(idx.calendar.loc[idx.calendar["date"] == ymd, "service_id"])
    plan = idx.trip_plan[idx.trip_plan["service_id"].isin(services)].reset_index()
    if plan.empty:
        raise ValueError(f"brak aktywnych kursow w dniu {ymd}")
    # kurs bez block_id jest osobnym lancuchem
    block = plan["block_id"].astype("string").fillna(plan["trip_id"].astype("string"))
    plan["block_key"] = plan["service_id"].astype(str) + "|" + block
    plan["start_s"] = plan["start_s"].astype(float)
    plan["end_s"] = plan["end_s"].astype(float)
    t = plan.sort_values(["block_key", "start_s", "trip_id"]).reset_index(drop=True)
    g = t.groupby("block_key", sort=False)
    t["blk_idx"] = g.cumcount()
    t["prev_trip"] = g["trip_id"].shift(1)
    t["layover_in_s"] = t["start_s"] - g["end_s"].shift(1)
    cols = ["trip_id", "route_id", "direction_id", "block_key", "blk_idx", "start_s", "end_s"]
    return t[cols + ["prev_trip", "layover_in_s"]]


def _day_stop_times(idx: ScheduleIndex, trips: pd.DataFrame) -> pd.DataFrame:
    order = pd.Series(np.arange(len(trips)), index=trips["trip_id"])
    st = idx.stop_times[idx.stop_times["trip_id"].isin(order.index)]
    st = st.assign(_o=st["trip_id"].map(order)).sort_values(["_o", "stop_sequence"])
    st = st.drop(columns="_o").reset_index(drop=True)
    st["arr_s"] = st["arr_s"].astype(float)
    st["dep_s"] = st["dep_s"].astype(float)
    g = st.groupby("trip_id", sort=False)
    st["to_stop"] = g["stop_id"].shift(-1)
    st["t_s"] = (g["arr_s"].shift(-1) - st["dep_s"]).fillna(0.0)
    return st


def build_network(idx: ScheduleIndex, service_date: str, tz: str) -> Network:
    """Siec dnia `service_date` dla wszystkich linii aktywnych w efektywnym kalendarzu.

    Args:
        idx: rozklad z `index_schedule`.
        service_date: data obslugi YYYY-MM-DD.
        tz: strefa czasowa feedu.

    Returns:
        Siec dnia; zakres linii wybiera sie pozniej (`select_trips`).

    Raises:
        ValueError: w dniu nie ma aktywnych kursow.
    """
    ymd = service_date.replace("-", "")
    trips = _day_trips(idx, ymd)
    st = _day_stop_times(idx, trips)
    has = st["to_stop"].notna()
    pairs = st.loc[has, ["stop_id", "to_stop"]].set_axis(["from_stop", "to_stop"], axis=1)
    segments = pairs.drop_duplicates().sort_values(["from_stop", "to_stop"]).reset_index(drop=True)
    seg_ix = pd.MultiIndex.from_frame(segments)
    st["seg_id"] = -1
    st.loc[has, "seg_id"] = seg_ix.get_indexer(pd.MultiIndex.from_frame(pairs))
    counts = st.groupby("trip_id", sort=False).size()
    trips["n_rows"] = trips["trip_id"].map(counts).fillna(0).astype(int)
    trips["row_start"] = np.r_[0, np.cumsum(trips["n_rows"].to_numpy())[:-1]]
    segments.index.name = "seg_id"
    day_start = float(gtfs_day_start(pd.Series([ymd]), tz).iloc[0])
    cols = ["trip_id", "stop_sequence", "stop_id", "arr_s", "dep_s", "t_s", "seg_id"]
    return Network(service_date, day_start, trips.set_index("trip_id"), st[cols], segments)


def select_trips(net: Network, routes: list[str] | None) -> np.ndarray:
    """Pozycje (w `net.trips`) kursow linii z `routes`; None = wszystkie linie."""
    if routes is None:
        return np.arange(len(net.trips))
    return np.flatnonzero(net.trips["route_id"].astype(str).isin(routes).to_numpy())


def chain_order(net: Network, sel: np.ndarray) -> pd.DataFrame:
    """Kursy z wyboru z pozycja w lancuchu i poprzednikiem w wyborze.

    Returns:
        Ramka `trip` (pozycja w `net.trips`), `pos` (numer kursu w lancuchu w obrebie wyboru),
        `prev_sel` (pozycja poprzedniego kursu bloku, gdy jest w wyborze, inaczej -1).
    """
    sel = np.sort(sel)
    trips = net.trips
    at = pd.Series(np.arange(len(trips)), index=trips.index)
    prev = trips["prev_trip"].map(at).to_numpy(float)[sel]
    chosen = np.zeros(len(trips), dtype=bool)
    chosen[sel] = True
    ok = ~np.isnan(prev)
    prev_sel = np.full(len(sel), -1)
    prev_sel[ok] = np.where(chosen[prev[ok].astype(int)], prev[ok].astype(int), -1)
    out = pd.DataFrame({"trip": sel, "block": trips["block_key"].to_numpy()[sel]})
    out["pos"] = out.groupby("block", sort=False).cumcount()
    out["prev_sel"] = prev_sel
    return out[["trip", "pos", "prev_sel"]]
