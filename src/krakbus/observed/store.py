"""Odczyt przetworzonych danych dzien po dniu z `data/processed/events/` i `chains/`."""

from pathlib import Path

import pandas as pd

from krakbus.config import load_config
from krakbus.observed.days import COMPLETE

KINDS = ("events", "chains")


def day_path(processed_dir: Path, day: str, kind: str = "events") -> Path:
    """Plik dnia `day` danego rodzaju (`events` albo `chains`)."""
    return processed_dir / kind / f"{day}.parquet"


def load_days(processed_dir: Path | None = None) -> pd.DataFrame:
    """Wczytuje rejestr `days.csv`."""
    processed_dir = processed_dir or load_config().data.processed_dir
    return pd.read_csv(processed_dir / "days.csv", dtype={"service_date": str})


def select_days(
    registry: pd.DataFrame,
    days: list[str] | None = None,
    statuses: tuple[str, ...] | None = (COMPLETE,),
) -> list[str]:
    """Daty z rejestru o podanych statusach (None = dowolny), opcjonalnie zawezone do `days`."""
    sel = registry
    if statuses is not None:
        sel = sel[sel["status"].isin(statuses)]
    if days is not None:
        sel = sel[sel["service_date"].isin(days)]
    return sorted(sel["service_date"])


def _load(
    kind: str,
    days: list[str] | None,
    statuses: tuple[str, ...] | None,
    processed_dir: Path | None,
    columns: list[str] | None,
) -> pd.DataFrame:
    processed_dir = processed_dir or load_config().data.processed_dir
    chosen = select_days(load_days(processed_dir), days, statuses)
    paths = [day_path(processed_dir, d, kind) for d in chosen]
    frames = [pd.read_parquet(p, columns=columns) for p in paths if p.exists()]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def load_events(
    days: list[str] | None = None,
    statuses: tuple[str, ...] | None = (COMPLETE,),
    processed_dir: Path | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Zdarzenia z wybranych dni, domyslnie wszystkich dni `complete`.

    Args:
        days: daty YYYY-MM-DD do wczytania (None = wszystkie z rejestru).
        statuses: dopuszczalne statusy z `days.csv`; None wylacza filtr.
        processed_dir: katalog z `days.csv` i `events/` (domyslnie z configu).
        columns: kolumny do wczytania (None = wszystkie).

    Returns:
        Polaczone zdarzenia; pusta ramka, gdy zaden dzien nie pasuje.
    """
    return _load("events", days, statuses, processed_dir, columns)


def load_chains(
    days: list[str] | None = None,
    statuses: tuple[str, ...] | None = (COMPLETE,),
    processed_dir: Path | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Lancuchy kursow (`krakbus.observed.chains.CHAIN_COLUMNS`) z wybranych dni; argumenty jak w `load_events`."""
    return _load("chains", days, statuses, processed_dir, columns)
