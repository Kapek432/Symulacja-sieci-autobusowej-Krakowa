"""Manifest przetwarzania przyrostowego: odcisk wejsc i statystyki kazdego zbudowanego dnia."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from krakbus.ingest.raw import files_signature, window_dates
from krakbus.observed.days import DayStats


def calendar_owners(per_version: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Data YYYYMMDD -> znacznik najnowszej wersji GTFS z jakimkolwiek wpisem na ta date."""
    owners: dict[str, str] = {}
    for stamp in sorted(per_version):
        for d in per_version[stamp]["date"].unique():
            owners[str(d)] = stamp
    return owners


def day_fingerprint(
    day: str,
    partitions: dict[str, list[Path]],
    owners: dict[str, str],
    params: dict[str, Any],
    pipeline_version: str,
) -> str:
    """Hash wszystkiego, od czego zaleza zdarzenia i lancuchy dnia `day`.

    Kalendarz D-1..D+1, bo data obslugi wybiera sposrod tych trzech dni. Same `stop_times` kursu sa
    identyczne we wszystkich wersjach, wiec nowa wersja GTFS liczy sie tylko przez kalendarz.

    Args:
        day: data obslugi YYYY-MM-DD.
        partitions: partycje VehiclePositions z `list_partitions`.
        owners: wlasciciele kalendarza z `calendar_owners`.
        params: progi wplywajace na wynik (sekcje configu jako slowniki).
        pipeline_version: wersja logiki przetwarzania.
    """
    dates = window_dates(day)
    payload = {
        "files": files_signature(partitions, dates),
        "calendar": [owners.get(d.replace("-", ""), "") for d in dates],
        "params": params,
        "pipeline_version": pipeline_version,
    }
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Zapis przez plik tymczasowy, zeby przerwane przeliczenie nie zostawilo uszkodzonego pliku."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def load_manifest(path: Path) -> dict[str, Any]:
    """Wczytuje manifest; brak pliku daje pusty manifest."""
    if not path.exists():
        return {"days": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    blob = json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False)
    atomic_write_bytes(path, (blob + "\n").encode("utf-8"))


def manifest_hash(path: Path) -> str:
    """Hash odciskow dni z manifestu, do migawki danych przy wynikach i porownania miedzy osobami."""
    days = load_manifest(path).get("days", {})
    blob = json.dumps({d: v["fingerprint"] for d, v in days.items()}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def stats_from_manifest(manifest: dict[str, Any]) -> list[DayStats]:
    return [DayStats(**v["stats"]) for v in manifest.get("days", {}).values()]
