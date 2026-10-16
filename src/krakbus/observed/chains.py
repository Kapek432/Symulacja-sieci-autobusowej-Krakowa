"""Lancuchy kursow pojazdow (`vehicle_chains`): kolejne kursy jednego pojazdu w dobie obslugi.

Lancuch jest obserwowany (kolejnosc kursow pojazdu wg czasu), a nie wziety z `block_id`: pojazdy
bywaja podmieniane i przechodza miedzy liniami. Zgodnosc z planem bloku mowi `follows_block`.
"""

import pandas as pd

from krakbus.config import ChainsConfig

CHAIN_COLUMNS = [
    "service_date",
    "vehicle_id",
    "chain_idx",
    "trip_id",
    "route_id",
    "direction_id",
    "service_id",
    "block_id",
    "blk_idx",
    "start_s",
    "end_s",
    "first_ts",
    "last_ts",
    "n_events",
    "dep_first_delay_s",
    "arr_end_delay_s",
    "next_trip_id",
    "next_route_id",
    "next_dep_first_delay_s",
    "block_next_trip",
    "layover_sched_s",
    "gap_obs_s",
    "follows_block",
    "cross_route",
    "carried",
]


def _trip_delays(ev: pd.DataFrame) -> pd.DataFrame:
    """Opoznienie odjazdu z pierwszego i przyjazdu na ostatni przystanek, z dobra niepewnoscia.

    Na pierwszym przystanku liczy sie ostatni epizod postoju (wlasciwy odjazd po czekaniu na petli),
    na ostatnim pierwszy (przyjazd z trasy).
    """
    key = ["vehicle_id", "trip_id"]
    first = (
        ev[ev["is_first"].fillna(False) & ev["dep_ok"].fillna(False)]
        .sort_values("dep_ts")
        .groupby(key)["dep_delay_s"]
        .last()
        .rename("dep_first_delay_s")
    )
    last = (
        ev[ev["is_last"].fillna(False) & ev["arr_ok"].fillna(False)]
        .sort_values("arr_ts")
        .groupby(key)["arr_delay_s"]
        .first()
        .rename("arr_end_delay_s")
    )
    return pd.concat([first, last], axis=1)


def build_chains(
    ev: pd.DataFrame, trip_plan: pd.DataFrame, cfg: ChainsConfig
) -> pd.DataFrame:
    """Jeden wiersz na kurs pojazdu w dobie, z nastepnym kursem tego pojazdu i zapasem na petli.

    Args:
        ev: zdarzenia jednej daty obslugi (`build_day`).
        trip_plan: `ScheduleIndex.trip_plan`.
        cfg: `l_min_s` do flagi przeniesienia.

    Returns:
        Tabela `CHAIN_COLUMNS`. `carried` = opoznienie na koncu kursu wieksze niz zapas minus
        `l_min_s` (opoznienie nie miesci sie w postoju na petli); brak, gdy nie ma opoznienia
        albo nastepnego kursu.
    """
    if ev.empty:
        return pd.DataFrame(columns=CHAIN_COLUMNS)
    key = ["vehicle_id", "trip_id"]
    t = (
        ev.groupby(key)
        .agg(
            service_date=("service_date", "first"),
            first_ts=("arr_ts", "min"),
            last_ts=("dep_ts", "max"),
            n_events=("arr_ts", "size"),
        )
        .join(_trip_delays(ev))
        .reset_index()
        .join(trip_plan, on="trip_id")
        .sort_values(["vehicle_id", "first_ts", "trip_id"])
        .reset_index(drop=True)
    )
    g = t.groupby("vehicle_id")
    t["chain_idx"] = g.cumcount()
    t["next_trip_id"] = g["trip_id"].shift(-1)
    t["next_route_id"] = g["route_id"].shift(-1)
    t["next_dep_first_delay_s"] = g["dep_first_delay_s"].shift(-1)
    t["layover_sched_s"] = g["start_s"].shift(-1) - t["end_s"]
    t["gap_obs_s"] = g["first_ts"].shift(-1) - t["last_ts"]
    has_next = t["next_trip_id"].notna()
    t["follows_block"] = (t["next_trip_id"] == t["block_next_trip"]).astype("boolean")
    t.loc[~has_next | t["block_next_trip"].isna(), "follows_block"] = pd.NA
    t["cross_route"] = (t["next_route_id"] != t["route_id"]).astype("boolean")
    t.loc[~has_next, "cross_route"] = pd.NA
    carried = t["arr_end_delay_s"] > t["layover_sched_s"] - cfg.l_min_s
    t["carried"] = carried.astype("boolean")
    t.loc[t["arr_end_delay_s"].isna() | t["layover_sched_s"].isna(), "carried"] = pd.NA
    return t[CHAIN_COLUMNS]
