"""Kursy z usluga innego dnia (`wrong_service_day`) i ich przepiecie na odpowiednik z wlasciwej doby.

RT ZTP czasem podaje `trip_id` z uslugi innego dnia tygodnia albo z nastepnego pokolenia rozkladu
(np. w czwartek kursy uslugi pon-sr, w poniedzialek 12.10 kursy pokolenia 20261013, w nocy 9->10.10
kursy nocne piatku z uslugi 20261010_4, ktora nie jest aktywna w zadnym dniu). Godzina i przebieg
sa te same, wiec data obslugi wypada o dobe obok (opoznienie ok. +-24 h) albo nie ma jej wcale.
Takie kursy przepinamy na kurs z uslugi aktywnej w faktycznym dniu o tej samej linii, kierunku,
godzinie startu i identycznym przebiegu (przystanki i czasy); bez jednoznacznego odpowiednika
zostaja z klasa `wrong_service_day`.
"""

from typing import TYPE_CHECKING

import pandas as pd

from krakbus.config import EventsConfig
from krakbus.ingest.gtfs_versions import gtfs_day_start

if TYPE_CHECKING:
    from krakbus.observed.events import ScheduleIndex

DAY_S = 86400


def _signatures(stop_times: pd.DataFrame, trip_ids: set[str]) -> pd.Series:
    """Przebieg kursu jako tekst `seq:stop:arr:dep|...`, do porownania dwoch kursow."""
    st = stop_times[stop_times["trip_id"].isin(trip_ids)].sort_values(
        ["trip_id", "stop_sequence"]
    )
    parts = (
        st["stop_sequence"].astype(str)
        + ":"
        + st["stop_id"].astype(str)
        + ":"
        + st["arr_s"].astype(str)
        + ":"
        + st["dep_s"].astype(str)
    )
    return parts.groupby(st["trip_id"]).agg("|".join)


def find_equivalents(wrong: pd.DataFrame, idx: ScheduleIndex) -> pd.DataFrame:
    """Jednoznaczne odpowiedniki kursow w uslugach aktywnych w faktycznym dniu.

    Args:
        wrong: unikalne pary `trip_id`, `actual_date` (YYYYMMDD).
        idx: rozklad z `index_schedule`.

    Returns:
        Ramka `trip_id`, `actual_date`, `new_trip_id`; tylko kursy z dokladnie jednym odpowiednikiem.
    """
    plan = idx.trip_plan
    key = ["route_id", "direction_id", "start_s"]
    w = wrong.join(plan[key], on="trip_id")
    cand = plan.reset_index()[["trip_id", "service_id", *key]].rename(
        columns={"trip_id": "new_trip_id"}
    )
    cand = w.merge(cand, on=key)
    active = pd.MultiIndex.from_frame(idx.calendar[["service_id", "date"]].astype(str))
    on_day = pd.MultiIndex.from_arrays([cand["service_id"], cand["actual_date"]])
    cand = cand[on_day.isin(active) & (cand["new_trip_id"] != cand["trip_id"])]
    if cand.empty:
        return pd.DataFrame(columns=["trip_id", "actual_date", "new_trip_id"])
    sig = _signatures(idx.stop_times, set(cand["trip_id"]) | set(cand["new_trip_id"]))
    cand = cand[cand["trip_id"].map(sig) == cand["new_trip_id"].map(sig)]
    n = cand.groupby(["trip_id", "actual_date"])["new_trip_id"].transform("nunique")
    return cand.loc[n == 1, ["trip_id", "actual_date", "new_trip_id"]].drop_duplicates()


def actual_service_dates(ev: pd.DataFrame, tz: str) -> pd.Series:
    """Faktyczna doba obslugi zdarzenia (YYYYMMDD) wprost z obserwacji, niezaleznie od kalendarza.

    Poczatek doby GTFS to w przyblizeniu `arr_ts - arr_s` (z dokladnoscia do opoznienia); plus 12 h
    daje lokalna date odporna na opoznienia do +-12 h i na kursy nocne z czasami po 24:00. Liczone
    per zdarzenie, bo ten sam pojazd moze jechac ten sam `trip_id` w dwoch dobach okna.
    """
    mid = ev["arr_ts"].astype(float) - ev["arr_s"].astype(float) + DAY_S / 2
    out = pd.Series(pd.NA, index=ev.index, dtype="string")
    ok = mid.notna()
    local = pd.to_datetime(mid[ok], unit="s", utc=True).dt.tz_convert(tz)
    out[ok] = local.dt.strftime("%Y%m%d")
    return out


def remap_wrong_day(
    ev: pd.DataFrame, idx: ScheduleIndex, cfg: EventsConfig, tz: str
) -> pd.DataFrame:
    """Przepina kursy z usluga innego dnia na odpowiednik z faktycznej doby obslugi.

    Kandydaci: kursy bez daty obslugi (usluga nieaktywna wczoraj, dzis i jutro) albo z medianowym
    |opoznieniem| > `wrong_day_min_s`. Decyzja zapada dla calego kursu pojazdu w jednej dobie
    (mediana opoznienia po zdarzeniach o tej samej dacie przypisanej i faktycznej). Oryginalny kurs zostaje w `rt_trip_id`, `trip_remapped` oznacza
    przepiete zdarzenia.
    """
    ev = ev.copy()
    ev["rt_trip_id"] = ev["trip_id"]
    ev["trip_remapped"] = False
    sd = ev["service_date"].astype("string")
    actual = actual_service_dates(ev, tz)
    groups = [ev["vehicle_id"], ev["trip_id"], sd.fillna(""), actual.fillna("")]
    med_delay = ev["arr_delay_s"].astype(float).groupby(groups).transform("median")
    suspicious = sd.isna() | (med_delay.abs() > cfg.wrong_day_min_s)
    differs = (actual != sd.str.replace("-", "")).fillna(True).astype(bool)
    sel = suspicious.fillna(False).astype(bool) & differs & actual.notna()
    if not sel.any():
        return ev
    sub = pd.DataFrame({"trip_id": ev.loc[sel, "trip_id"], "actual_date": actual[sel]})
    eq = find_equivalents(sub.drop_duplicates(), idx)
    sub = sub.reset_index().merge(eq, on=["trip_id", "actual_date"]).set_index("index")
    if sub.empty:
        return ev
    rows = sub.index
    new_trip = sub["new_trip_id"]
    plan = idx.trip_plan.loc[new_trip]
    gtfs_stamp = idx.trips.set_index("trip_id")["gtfs_stamp"]
    ev.loc[rows, "trip_id"] = new_trip.to_numpy()
    ev.loc[rows, "service_id"] = plan["service_id"].to_numpy()
    ev.loc[rows, "gtfs_stamp"] = gtfs_stamp.loc[new_trip].to_numpy()
    actual = pd.Series(sub["actual_date"].to_numpy(), index=rows)
    mid = gtfs_day_start(actual, tz)
    ev.loc[rows, "service_date"] = (
        pd.to_datetime(actual, format="%Y%m%d").dt.strftime("%Y-%m-%d").to_numpy()
    )
    ev.loc[rows, "arr_delay_s"] = (
        ev.loc[rows, "arr_ts"] - (mid + ev.loc[rows, "arr_s"])
    ).to_numpy()
    ev.loc[rows, "dep_delay_s"] = (
        ev.loc[rows, "dep_ts"] - (mid + ev.loc[rows, "dep_s"])
    ).to_numpy()
    ev.loc[rows, "trip_remapped"] = True
    return ev


def classify_delays(ev: pd.DataFrame, cfg: EventsConfig) -> pd.DataFrame:
    """Jeden filtr jakosci opoznien dla wszystkich analiz.

    `delay_class`: `ok` (|opoznienie przyjazdu| <= `outlier_s`), `outlier`, `wrong_service_day`
    (|opoznienie| > `wrong_day_min_s` po probie przepiecia). `arr_good` / `dep_good` = dobra
    niepewnosc i opoznienie w klasie `ok` (dla odjazdu: |opoznienie odjazdu| <= `outlier_s`).
    """
    d = ev["arr_delay_s"].abs()
    cls = pd.Series("ok", index=ev.index, dtype="string")
    cls[d > cfg.outlier_s] = "outlier"
    cls[d > cfg.wrong_day_min_s] = "wrong_service_day"
    cls[ev["arr_delay_s"].isna()] = pd.NA
    ev["delay_class"] = cls
    ok = (cls == "ok").fillna(False).astype(bool)
    ev["arr_good"] = ev["arr_ok"].fillna(False).astype(bool) & ok
    dep_in = (ev["dep_delay_s"].abs() <= cfg.outlier_s).fillna(False).astype(bool)
    ev["dep_good"] = (
        ev["dep_ok"].fillna(False).astype(bool)
        & dep_in
        & (cls.fillna("") != "wrong_service_day").astype(bool)
    )
    return ev
