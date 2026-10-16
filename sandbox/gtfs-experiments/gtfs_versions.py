"""gtfs_versions.py: laczenie wersji rozkladu GTFS zapisanych przez logger i przypisanie daty obslugi.

ZTP publikuje feed kroczacy: kazda wersja zawiera kilka "pokolen" uslug (prefiks daty w `service_id`
i `trip_id`, np. `20261005_1_...`), a kalendarz jest tylko w `calendar_dates.txt`. Ten sam `trip_id`
w roznych wersjach ma identyczne `stop_times`, wiec rozklad kursu bierzemy z najnowszej wersji,
ktora go zawiera. Kalendarz dnia D bierzemy z najnowszej wersji, ktora ma jakikolwiek wpis na D
(starsza wersja moze jeszcze wymieniac uslugi, ktore nowsza zastapila).
"""

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/Warsaw"
STOP_TIME_COLS = [
    "trip_id",
    "stop_sequence",
    "stop_id",
    "arrival_time",
    "departure_time",
]
WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


@dataclass
class Schedule:
    """Polaczony rozklad ze wszystkich wersji GTFS.

    Attributes:
        trips: `trips.txt` bez duplikatow `trip_id`, z kolumna `gtfs_stamp` (wersja zrodlowa).
        stop_times: `stop_times.txt` dla kursow z `trips`.
        stops: `stops.txt`, najnowszy wpis dla kazdego `stop_id`.
        calendar: aktywne pary (`service_id`, `date` YYYYMMDD) z kolumnami `exception_type` = "1"
            i `gtfs_stamp` (wersja, z ktorej wzieto kalendarz tego dnia).
        versions: znaczniki wersji (`YYYYMMDD_HHMMSS`) od najstarszej.
    """

    trips: pd.DataFrame
    stop_times: pd.DataFrame
    stops: pd.DataFrame
    calendar: pd.DataFrame
    versions: list[str] = field(default_factory=list)


def version_stamp(path: Path) -> str:
    """Zwraca znacznik wersji z nazwy `GTFS_KRK_A_YYYYMMDD_HHMMSS.zip`."""
    return "_".join(path.stem.split("_")[-2:])


def _expand_calendar(cal: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in cal.itertuples(index=False):
        flags = [getattr(r, w) == "1" for w in WEEKDAYS]
        if not any(flags):
            continue
        days = pd.date_range(r.start_date, r.end_date, freq="D")
        days = days[np.array(flags)[days.dayofweek]]
        rows.append(
            pd.DataFrame({"service_id": r.service_id, "date": days.strftime("%Y%m%d")})
        )
    if not rows:
        return pd.DataFrame(columns=["service_id", "date"])
    return pd.concat(rows, ignore_index=True)


def active_services(
    cal: pd.DataFrame | None, cal_dates: pd.DataFrame | None
) -> pd.DataFrame:
    """Aktywne pary (`service_id`, `date`) jednej wersji GTFS.

    Args:
        cal: zawartosc `calendar.txt` (kolumny jako tekst) albo None.
        cal_dates: zawartosc `calendar_dates.txt` (kolumny jako tekst) albo None.

    Returns:
        Ramka z kolumnami `service_id`, `date` bez duplikatow.
    """
    parts = []
    if cal is not None and len(cal):
        parts.append(_expand_calendar(cal))
    removed = pd.DataFrame(columns=["service_id", "date"])
    if cal_dates is not None and len(cal_dates):
        parts.append(
            cal_dates.loc[cal_dates["exception_type"] == "1", ["service_id", "date"]]
        )
        removed = cal_dates.loc[
            cal_dates["exception_type"] == "2", ["service_id", "date"]
        ]
    if not parts:
        return pd.DataFrame(columns=["service_id", "date"])
    act = pd.concat(parts, ignore_index=True).drop_duplicates()
    act = act.merge(removed.assign(_rm=True), on=["service_id", "date"], how="left")
    return act[act["_rm"].isna()].drop(columns="_rm").reset_index(drop=True)


def effective_calendar(per_version: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Wybiera dla kazdego dnia kalendarz z najnowszej wersji, ktora ma wpis na ten dzien.

    Args:
        per_version: znacznik wersji -> aktywne pary (`service_id`, `date`) tej wersji.

    Returns:
        Ramka `service_id`, `date`, `exception_type` ("1"), `gtfs_stamp`.
    """
    frames = [
        df.assign(gtfs_stamp=stamp) for stamp, df in per_version.items() if len(df)
    ]
    if not frames:
        return pd.DataFrame(
            columns=["service_id", "date", "exception_type", "gtfs_stamp"]
        )
    allv = pd.concat(frames, ignore_index=True)
    owner = allv.groupby("date")["gtfs_stamp"].max().rename("owner")
    allv = allv.join(owner, on="date")
    out = allv[allv["gtfs_stamp"] == allv["owner"]].drop(columns="owner")
    return (
        out.assign(exception_type="1")
        .sort_values(["date", "service_id"])
        .reset_index(drop=True)
    )


def load_schedule(
    static_dir: Path, stop_time_cols: list[str] | None = None
) -> Schedule:
    """Wczytuje i laczy wszystkie wersje `GTFS_KRK_A_*.zip` z katalogu.

    Args:
        static_dir: katalog z plikami ZIP zapisanymi przez logger.
        stop_time_cols: kolumny `stop_times.txt` do wczytania (domyslnie `STOP_TIME_COLS`).

    Returns:
        Polaczony rozklad.

    Raises:
        FileNotFoundError: gdy w katalogu nie ma zadnej wersji GTFS.
    """
    zips = sorted(static_dir.glob("GTFS_KRK_A_*.zip"), key=version_stamp)
    if not zips:
        raise FileNotFoundError(f"brak plikow GTFS_KRK_A_*.zip w {static_dir}")
    cols = stop_time_cols or STOP_TIME_COLS
    trips, stop_times, stops, cals = [], [], [], {}
    seen: set[str] = set()
    for zpath in reversed(zips):
        stamp = version_stamp(zpath)
        with zipfile.ZipFile(zpath) as z:
            names = set(z.namelist())
            tr = pd.read_csv(z.open("trips.txt"), dtype=str)
            tr = tr[~tr["trip_id"].isin(seen)]
            new_ids = set(tr["trip_id"])
            if new_ids:
                st = pd.read_csv(z.open("stop_times.txt"), dtype=str, usecols=cols)
                stop_times.append(st[st["trip_id"].isin(new_ids)])
                trips.append(tr.assign(gtfs_stamp=stamp))
                seen |= new_ids
            stops.append(
                pd.read_csv(z.open("stops.txt"), dtype=str).assign(gtfs_stamp=stamp)
            )
            cal = (
                pd.read_csv(z.open("calendar.txt"), dtype=str)
                if "calendar.txt" in names
                else None
            )
            cd = (
                pd.read_csv(z.open("calendar_dates.txt"), dtype=str)
                if "calendar_dates.txt" in names
                else None
            )
            cals[stamp] = active_services(cal, cd)
    return Schedule(
        trips=pd.concat(trips, ignore_index=True),
        stop_times=pd.concat(stop_times, ignore_index=True),
        stops=pd.concat(stops, ignore_index=True).drop_duplicates(
            "stop_id", keep="first"
        ),
        calendar=effective_calendar(cals),
        versions=[version_stamp(z) for z in zips],
    )


def gtfs_day_start(dates: pd.Series, tz: str = TZ) -> pd.Series:
    """Poczatek doby GTFS (lokalne poludnie minus 12 h) w sekundach epoki.

    Tak definiuje czasy `stop_times` specyfikacja GTFS, dzieki czemu doby zmiany czasu (25 albo 23 h)
    nie przesuwaja opoznien o godzine.

    Args:
        dates: daty w formacie YYYYMMDD.
        tz: strefa czasowa feedu.

    Returns:
        Seria liczb (float) z tym samym indeksem.
    """
    uniq = pd.Series(dates.dropna().unique())
    noon = pd.to_datetime(uniq, format="%Y%m%d") + pd.Timedelta(hours=12)
    start = noon.dt.tz_localize(tz) - pd.Timedelta(hours=12)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    lookup = dict(zip(uniq, (start - epoch).dt.total_seconds()))
    return dates.map(lookup).astype(float)


def assign_service_date(
    arr_ts: pd.Series,
    sched_arr_s: pd.Series,
    service_id: pd.Series,
    active: pd.DataFrame,
    tz: str = TZ,
) -> tuple[pd.Series, pd.Series]:
    """Przypisuje zdarzeniu date obslugi: wczoraj, dzis albo jutro wzgledem lokalnej daty przyjazdu.

    Kandydat musi miec usluge kursu aktywna w kalendarzu tego dnia. Sposrod aktywnych wybierany jest
    ten, ktory daje najmniejsze |opoznienie|; przy remisie wygrywa dzis. Zdarzenie bez rozkladu albo
    bez aktywnego kandydata dostaje brak daty (nie cichy wybor "wczoraj").

    Args:
        arr_ts: czas przyjazdu w sekundach epoki.
        sched_arr_s: rozkladowy czas przyjazdu w sekundach od poczatku doby GTFS (NaN = brak).
        service_id: usluga kursu (NaN = kurs nieznany w rozkladzie).
        active: aktywne pary (`service_id`, `date` YYYYMMDD).
        tz: strefa czasowa feedu.

    Returns:
        Para serii: data obslugi `YYYY-MM-DD` (pd.NA gdy brak) i poczatek doby GTFS tej daty
        w sekundach epoki (NaN gdy brak).
    """
    # wejscie z pandas 3 bywa nullable (Int64/Float64), a porownania z pd.NA nie daja masek bool
    arr_ts = pd.Series(
        pd.to_numeric(arr_ts).to_numpy(dtype=float, na_value=np.nan), index=arr_ts.index
    )
    sched_arr_s = pd.Series(
        pd.to_numeric(sched_arr_s).to_numpy(dtype=float, na_value=np.nan),
        index=sched_arr_s.index,
    )
    local = pd.to_datetime(arr_ts.astype("int64"), unit="s", utc=True).dt.tz_convert(tz)
    base = local.dt.tz_localize(None).dt.normalize()
    act_idx = pd.MultiIndex.from_frame(active[["service_id", "date"]].astype(str))
    best_abs = pd.Series(np.inf, index=arr_ts.index)
    best_date = pd.Series(pd.NA, index=arr_ts.index, dtype="string")
    best_ref = pd.Series(np.nan, index=arr_ts.index)
    for k in (0, -1, 1):
        cand = (base + pd.Timedelta(days=k)).dt.strftime("%Y%m%d")
        ok = pd.MultiIndex.from_arrays([service_id.astype(str), cand]).isin(act_idx)
        ok &= sched_arr_s.notna().to_numpy() & service_id.notna().to_numpy()
        ref = gtfs_day_start(cand, tz)
        dev = (arr_ts - (ref + sched_arr_s)).abs()
        better = ok & (dev < best_abs).to_numpy()
        best_abs = best_abs.mask(better, dev)
        best_ref = best_ref.mask(better, ref)
        iso = (base + pd.Timedelta(days=k)).dt.strftime("%Y-%m-%d").astype("string")
        best_date = best_date.mask(better, iso)
    return best_date, best_ref
