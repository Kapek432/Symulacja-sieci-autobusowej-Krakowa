"""Surowe partycje loggera GTFS-RT i okna dni do przetwarzania przyrostowego.

Logger zapisuje co ~10 min nowy plik `part-HHMMSS.parquet` w katalogu `date=YYYY-MM-DD` wg daty UTC
zapisu i nigdy go potem nie zmienia. Lokalna doba D zaczyna sie o 22:00/23:00 UTC dnia D-1, a kursy
nocne doby D jada jeszcze w D+1, dlatego date obslugi D liczymy z partycji D-1, D i D+1.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

VP_COLS = [
    "fetched_at",
    "vehicle_id",
    "trip_id",
    "veh_ts",
    "current_stop_sequence",
    "current_status",
    "lat",
    "lon",
]
TU_COLS = ["fetched_at", "trip_id", "stop_id", "arr_time"]


def list_partitions(feed_dir: Path) -> dict[str, list[Path]]:
    """Zwraca date partycji (YYYY-MM-DD) -> posortowane pliki `part-*.parquet`."""
    out: dict[str, list[Path]] = {}
    for d in sorted(feed_dir.glob("date=*")):
        files = sorted(d.glob("*.parquet"))
        if files:
            out[d.name.removeprefix("date=")] = files
    return out


def shift_day(day: str, days: int) -> str:
    """Przesuwa date YYYY-MM-DD o podana liczbe dni."""
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def window_dates(day: str) -> list[str]:
    """Partycje UTC potrzebne do policzenia daty obslugi `day`: D-1, D, D+1."""
    return [shift_day(day, k) for k in (-1, 0, 1)]


def files_signature(
    partitions: dict[str, list[Path]], dates: list[str]
) -> list[list[str | int]]:
    """Lista [partycja/plik, rozmiar] plikow z podanych partycji, do odcisku wejsc dnia.

    Rozmiar zamiast czasu modyfikacji, bo pobranie z Google Drive i rozpakowanie zmienia mtime.
    """
    sig: list[list[str | int]] = []
    for d in dates:
        for f in partitions.get(d, []):
            sig.append([f"{d}/{f.name}", f.stat().st_size])
    return sig


class PartitionCache:
    """Wczytuje partycje jednego feedu leniwie i trzyma tylko te z biezacego okna."""

    def __init__(self, partitions: dict[str, list[Path]], columns: list[str]) -> None:
        self._partitions = partitions
        self._columns = columns
        self._loaded: dict[str, pd.DataFrame] = {}

    def _load(self, day: str) -> pd.DataFrame:
        files = self._partitions.get(day, [])
        if not files:
            return pd.DataFrame(columns=self._columns)
        return pd.concat(
            [pd.read_parquet(f, columns=self._columns) for f in files],
            ignore_index=True,
        )

    def window(self, dates: list[str]) -> pd.DataFrame:
        """Laczy partycje z `dates` (w tej kolejnosci) i zwalnia pozostale z pamieci."""
        for d in list(self._loaded):
            if d not in dates:
                del self._loaded[d]
        for d in dates:
            if d not in self._loaded:
                self._loaded[d] = self._load(d)
        frames = [self._loaded[d] for d in dates if len(self._loaded[d])]
        if not frames:
            return pd.DataFrame(columns=self._columns)
        return pd.concat(frames, ignore_index=True)
