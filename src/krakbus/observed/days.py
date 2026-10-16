"""Rejestr dni: statystyki pokrycia, status (complete/provisional/gap/special) i rola w kalibracji."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

from krakbus.config import DaysConfig

COMPLETE = "complete"
PROVISIONAL = "provisional"
GAP = "gap"
SPECIAL = "special"

WEEKDAYS_PL = ["pon", "wt", "sr", "czw", "pt", "sob", "nd"]

DAYS_COLUMNS = [
    "service_date",
    "weekday",
    "status",
    "role",
    "reason",
    "n_events",
    "n_routes",
    "n_vehicles",
    "max_gap_min",
    "gap_min_total",
    "data_until",
    "calendar_stamp",
]


@dataclass(frozen=True)
class DayStats:
    """Pokrycie dnia obslugi policzone przy budowie jego zdarzen.

    Attributes:
        service_date: YYYY-MM-DD.
        n_events: liczba zdarzen z ta data obslugi.
        n_routes: liczba linii.
        n_vehicles: liczba pojazdow.
        max_gap_min: najdluzsza przerwa miedzy migawkami loggera w godzinach ruchu.
        gap_min_total: suma przerw dluzszych niz `logger_gap_s` w godzinach ruchu.
        data_until: ostatnia migawka w oknie D-1..D+1 (czas lokalny ISO); `""` gdy brak danych.
        calendar_stamp: wersja GTFS, z ktorej pochodzi kalendarz dnia (`""` gdy zadna go nie obejmuje).
    """

    service_date: str
    n_events: int
    n_routes: int
    n_vehicles: int
    max_gap_min: float
    gap_min_total: float
    data_until: str
    calendar_stamp: str


def _local_epoch(day: str, hour: int, tz: str) -> float:
    """Sekundy epoki lokalnej godziny zegarowej `hour` liczonej od polnocy `day` (moze byc >= 24)."""
    wall = datetime.fromisoformat(day) + timedelta(hours=hour)
    return wall.replace(tzinfo=ZoneInfo(tz)).timestamp()


def snapshot_gaps(
    fetched_at: np.ndarray, day: str, cfg: DaysConfig, tz: str
) -> tuple[float, float]:
    """Najdluzsza przerwa i suma przerw (minuty) miedzy migawkami w godzinach ruchu dnia.

    Poczatek i koniec godzin ruchu traktujemy jak migawki, wiec brak danych rano albo wieczorem
    tez jest przerwa.
    """
    start = _local_epoch(day, cfg.service_hours[0], tz)
    end = _local_epoch(day, cfg.service_hours[1], tz)
    ts = np.unique(fetched_at[(fetched_at >= start) & (fetched_at <= end)])
    diffs = np.diff(np.concatenate([[start], ts, [end]]))
    long = diffs[diffs > cfg.logger_gap_s]
    return float(diffs.max()) / 60, float(long.sum()) / 60


def day_stats(
    day: str,
    ev: pd.DataFrame,
    fetched_at: np.ndarray,
    calendar_stamp: str,
    cfg: DaysConfig,
    tz: str,
) -> DayStats:
    """Statystyki dnia z jego zdarzen i czasow migawek z okna D-1..D+1."""
    max_gap, total_gap = snapshot_gaps(fetched_at, day, cfg, tz)
    until = ""
    if len(fetched_at):
        until = pd.Timestamp(float(np.nanmax(fetched_at)), unit="s", tz="UTC")
        until = until.tz_convert(tz).isoformat(timespec="seconds")
    empty = ev.empty
    return DayStats(
        service_date=day,
        n_events=len(ev),
        n_routes=0 if empty else int(ev["route_id"].nunique()),
        n_vehicles=0 if empty else int(ev["vehicle_id"].nunique()),
        max_gap_min=round(max_gap, 1),
        gap_min_total=round(total_gap, 1),
        data_until=until,
        calendar_stamp=calendar_stamp,
    )


def load_special_days(path: Path) -> dict[str, str]:
    """Data YYYY-MM-DD -> powod; brak pliku daje pusty slownik."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(d["date"]): str(d.get("reason", "")) for d in raw.get("days", [])}


def load_split(path: Path) -> dict[str, set[str]]:
    """Zamrozony podzial dni z `days_split.yaml` (klucze `calib`, `excluded`); brak pliku = pusty."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: {str(d) for d in raw.get(k, [])} for k in ("calib", "excluded")}


def classify_day(
    stats: DayStats, special: dict[str, str], cfg: DaysConfig, tz: str
) -> tuple[str, str]:
    """Status dnia i powod, w kolejnosci: provisional, special, gap, complete.

    Dzien jest pelny dopiero, gdy logger ma dane do `night_end_hour` nastepnej doby, bo kursy nocne
    dnia D koncza sie po polnocy.
    """
    need_until = _local_epoch(stats.service_date, 24 + cfg.night_end_hour, tz)
    if not stats.data_until or pd.Timestamp(stats.data_until).timestamp() < need_until:
        return PROVISIONAL, f"dane do {stats.data_until or 'brak'}"
    if stats.service_date in special:
        return SPECIAL, special[stats.service_date]
    if stats.max_gap_min > cfg.max_gap_min:
        return GAP, f"przerwa {stats.max_gap_min} min"
    if stats.n_events < cfg.min_events:
        return GAP, f"tylko {stats.n_events} zdarzen"
    return COMPLETE, ""


def assign_role(day: str, status: str, split: dict[str, set[str]]) -> str:
    """Rola dnia: przed zamrozeniem podzialu `unassigned`, po nim nowe dni `complete` to `valid`."""
    if status != COMPLETE or day in split.get("excluded", set()):
        return "excluded"
    if not split:
        return "unassigned"
    return "calib" if day in split.get("calib", set()) else "valid"


def build_registry(stats: list[DayStats], cfg: DaysConfig, tz: str) -> pd.DataFrame:
    """Tabela `days.csv` ze statusem i rola kazdego dnia (liczona od nowa przy kazdym uruchomieniu)."""
    special = load_special_days(cfg.special_days_file)
    split = load_split(cfg.split_file)
    rows = []
    for s in sorted(stats, key=lambda x: x.service_date):
        status, reason = classify_day(s, special, cfg, tz)
        rows.append(
            {
                **asdict(s),
                "weekday": WEEKDAYS_PL[
                    datetime.fromisoformat(s.service_date).weekday()
                ],
                "status": status,
                "reason": reason,
                "role": assign_role(s.service_date, status, split),
            }
        )
    return pd.DataFrame(rows, columns=DAYS_COLUMNS)
