"""Zdarzenia przystankowe (przyjazd, odjazd, opoznienie) z raportow VehiclePositions o statusie 1."""

from dataclasses import dataclass

import pandas as pd

from krakbus.config import EventsConfig
from krakbus.ingest.gtfs_versions import Schedule, assign_service_date

STOPPED_AT = 1


@dataclass(frozen=True)
class ScheduleIndex:
    """Rozklad przygotowany do laczenia ze zdarzeniami.

    Attributes:
        stop_times: `trip_id`, `stop_sequence` (int), `stop_id`, `arr_s`, `dep_s` (sekundy doby GTFS).
        trips: `trip_id`, `route_id`, `service_id`, `gtfs_stamp`.
        bounds: indeks `trip_id`, kolumny `first_seq`, `last_seq`.
        calendar: aktywne pary (`service_id`, `date`) z efektywnego kalendarza.
    """

    stop_times: pd.DataFrame
    trips: pd.DataFrame
    bounds: pd.DataFrame
    calendar: pd.DataFrame


def hms(col: pd.Series) -> pd.Series:
    """Zamienia `HH:MM:SS` (godziny moga przekraczac 24) na sekundy; brak daje `<NA>` (Int64)."""
    p = col.astype("string").str.strip().str.split(":", expand=True)
    return pd.to_numeric(p[0]) * 3600 + pd.to_numeric(p[1]) * 60 + pd.to_numeric(p[2])


def index_schedule(sched: Schedule) -> ScheduleIndex:
    """Liczy raz kolumny rozkladu potrzebne przy kazdym dniu."""
    st = sched.stop_times.copy()
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st["arr_s"] = hms(st["arrival_time"])
    st["dep_s"] = hms(st["departure_time"])
    bounds = st.groupby("trip_id")["stop_sequence"].agg(first_seq="min", last_seq="max")
    return ScheduleIndex(
        stop_times=st[["trip_id", "stop_sequence", "stop_id", "arr_s", "dep_s"]],
        trips=sched.trips[["trip_id", "route_id", "service_id", "gtfs_stamp"]],
        bounds=bounds,
        calendar=sched.calendar,
    )


def clean_positions(vp: pd.DataFrame) -> pd.DataFrame:
    """Odrzuca niepelne raporty i powtorzenia, sortuje po pojezdzie i czasie, dodaje sasiednie raporty.

    `prev_ts`/`next_ts` to czasy poprzedniego i nastepnego raportu pojazdu; odstep do nich jest
    niepewnoscia momentu przyjazdu i odjazdu.
    """
    vp = vp.dropna(
        subset=["veh_ts", "trip_id", "current_stop_sequence", "current_status"]
    )
    vp = vp.astype(
        {"veh_ts": "int64", "current_stop_sequence": "int64", "current_status": "int64"}
    )
    vp["vehicle_id"] = vp["vehicle_id"].astype(str)
    vp["trip_id"] = vp["trip_id"].astype(str)
    vp = (
        vp.drop_duplicates(["vehicle_id", "veh_ts"])
        .sort_values(["vehicle_id", "veh_ts"])
        .copy()
    )
    vp["prev_ts"] = vp.groupby("vehicle_id")["veh_ts"].shift(1)
    vp["next_ts"] = vp.groupby("vehicle_id")["veh_ts"].shift(-1)
    return vp


def stop_episodes(vp: pd.DataFrame, episode_gap_s: int) -> pd.DataFrame:
    """Sklada kolejne raporty statusu 1 na tym samym przystanku kursu w jeden postoj.

    Przyjazd to pierwszy raport epizodu, odjazd ostatni (dolne ograniczenie prawdziwego odjazdu).
    """
    s1 = (
        vp[vp["current_status"] == STOPPED_AT]
        .sort_values(["vehicle_id", "trip_id", "current_stop_sequence", "veh_ts"])
        .copy()
    )
    key = ["vehicle_id", "trip_id", "current_stop_sequence"]
    gap = s1.groupby(key)["veh_ts"].diff()
    s1["ep"] = (gap.isna() | (gap > episode_gap_s)).cumsum()
    ev = (
        s1.groupby("ep")
        .agg(
            vehicle_id=("vehicle_id", "first"),
            trip_id=("trip_id", "first"),
            stop_sequence=("current_stop_sequence", "first"),
            arr_ts=("veh_ts", "min"),
            dep_ts=("veh_ts", "max"),
            n=("veh_ts", "size"),
            lat=("lat", "first"),
            lon=("lon", "first"),
        )
        .reset_index(drop=True)
    )
    ev = ev.merge(
        vp[["vehicle_id", "veh_ts", "prev_ts"]].rename(columns={"veh_ts": "arr_ts"}),
        on=["vehicle_id", "arr_ts"],
        how="left",
    )
    ev = ev.merge(
        vp[["vehicle_id", "veh_ts", "next_ts"]].rename(columns={"veh_ts": "dep_ts"}),
        on=["vehicle_id", "dep_ts"],
        how="left",
    )
    # NaN = przyjazd albo odjazd na krawedzi obserwacji pojazdu
    ev["arr_unc"] = ev["arr_ts"] - ev["prev_ts"]
    ev["dep_unc"] = ev["next_ts"] - ev["dep_ts"]
    return ev


def attach_schedule(
    ev: pd.DataFrame, idx: ScheduleIndex, cfg: EventsConfig, tz: str
) -> pd.DataFrame:
    """Dolacza rozklad, przypisuje date obslugi i liczy opoznienia oraz flagi jakosci."""
    ev = ev.merge(idx.stop_times, on=["trip_id", "stop_sequence"], how="left")
    ev = ev.merge(idx.trips, on="trip_id", how="left")
    ev = ev.join(idx.bounds, on="trip_id")
    ev["is_first"] = ev["stop_sequence"] == ev["first_seq"]
    ev["is_last"] = ev["stop_sequence"] == ev["last_seq"]
    ev["service_date"], mid = assign_service_date(
        ev["arr_ts"], ev["arr_s"], ev["service_id"], idx.calendar, tz
    )
    ev["arr_delay_s"] = ev["arr_ts"] - (mid + ev["arr_s"])
    ev["dep_delay_s"] = ev["dep_ts"] - (mid + ev["dep_s"])
    # na pierwszym przystanku "przyjazd" to zwykle podstawienie pojazdu, nie przyjazd z trasy
    ev["arr_ok"] = (ev["arr_unc"] <= cfg.unc_ok_s) & ~ev["is_first"]
    ev["dep_ok"] = ev["dep_unc"] <= cfg.unc_ok_s
    return ev


def build_events(
    vp: pd.DataFrame, idx: ScheduleIndex, cfg: EventsConfig, tz: str
) -> pd.DataFrame:
    """Zdarzenia przystankowe ze wszystkich raportow `vp` (dowolnego okna czasu).

    Args:
        vp: surowe VehiclePositions (kolumny `krakbus.ingest.raw.VP_COLS`).
        idx: rozklad z `index_schedule`.
        cfg: progi epizodow i niepewnosci.
        tz: strefa czasowa feedu.

    Returns:
        Jeden wiersz na postoj pojazdu na przystanku, z data obslugi i opoznieniami.
    """
    ev = stop_episodes(clean_positions(vp), cfg.episode_gap_s)
    return attach_schedule(ev, idx, cfg, tz)


def build_day(
    vp_window: pd.DataFrame, idx: ScheduleIndex, day: str, cfg: EventsConfig, tz: str
) -> pd.DataFrame:
    """Zdarzenia z data obslugi `day`, liczone z okna partycji D-1..D+1.

    Args:
        vp_window: surowe VehiclePositions z partycji UTC `day`-1, `day`, `day`+1.
        idx: rozklad z `index_schedule`.
        day: data obslugi YYYY-MM-DD.
        cfg: progi epizodow i niepewnosci.
        tz: strefa czasowa feedu.

    Returns:
        Zdarzenia dnia posortowane po pojezdzie i czasie przyjazdu.
    """
    if vp_window.empty:
        return pd.DataFrame()
    ev = build_events(vp_window, idx, cfg, tz)
    ev = ev[ev["service_date"] == day]
    return ev.sort_values(["vehicle_id", "arr_ts", "stop_sequence"]).reset_index(
        drop=True
    )
