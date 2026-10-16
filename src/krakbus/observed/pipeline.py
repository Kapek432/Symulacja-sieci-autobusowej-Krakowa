"""Komenda `build-events`: przyrostowe przeliczenie zdarzen przystankowych i lancuchow dzien po dniu.

Przelicza tylko dni, ktorych odcisk wejsc (pliki `part-*` z okna D-1..D+1, wlasciciel kalendarza,
progi `events` i `chains`, `PIPELINE_VERSION`) zmienil sie od poprzedniego uruchomienia. Status i role
dni liczy od nowa za kazdym razem, bo zaleza tylko od zapisanych statystyk i plikow w `configs/`.
"""

import argparse
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from krakbus.config import Config, load_config
from krakbus.ingest.gtfs_versions import load_schedule, load_version_calendars
from krakbus.ingest.raw import VP_COLS, PartitionCache, list_partitions, window_dates
from krakbus.logger import setup_logging
from krakbus.observed.chains import build_chains
from krakbus.observed.days import COMPLETE, build_registry, day_stats
from krakbus.observed.events import build_day, index_schedule
from krakbus.observed.manifest import (
    atomic_write_bytes,
    atomic_write_parquet,
    calendar_owners,
    day_fingerprint,
    load_manifest,
    manifest_hash,
    save_manifest,
    stats_from_manifest,
)
from krakbus.observed.store import KINDS, day_path

# podbic przy kazdej zmianie logiki, ktora zmienia zawartosc plikow events/ albo chains/
PIPELINE_VERSION = "2"

logger = logging.getLogger("build_events")


def days_to_build(
    fingerprints: dict[str, str],
    manifest: dict[str, Any],
    processed_dir: Path,
    force: set[str],
) -> list[str]:
    """Dni z nowym lub zmienionym odciskiem, z brakujacym plikiem albo wymuszone."""
    known = manifest.get("days", {})
    out = []
    for day, fp in sorted(fingerprints.items()):
        entry = known.get(day, {})
        had_events = entry.get("stats", {}).get("n_events", 1) > 0
        missing = had_events and not all(
            day_path(processed_dir, day, k).exists() for k in KINDS
        )
        if day in force or entry.get("fingerprint") != fp or missing:
            out.append(day)
    return out


def _write_day(frames: dict[str, pd.DataFrame], day: str, processed_dir: Path) -> None:
    for kind, df in frames.items():
        path = day_path(processed_dir, day, kind)
        if df.empty:
            path.unlink(missing_ok=True)
        else:
            atomic_write_parquet(df, path)


def _rebuild(
    todo: list[str],
    partitions: dict[str, list[Path]],
    fingerprints: dict[str, str],
    owners: dict[str, str],
    manifest: dict[str, Any],
    cfg: Config,
) -> None:
    sched = load_schedule(cfg.data.raw_dir / "static")
    logger.info("rozklad: %d wersji, %d kursow", len(sched.versions), len(sched.trips))
    idx = index_schedule(sched)
    cache = PartitionCache(partitions, VP_COLS)
    tz = cfg.data.timezone
    for day in todo:
        vp = cache.window(window_dates(day))
        ev = build_day(vp, idx, day, cfg.events, tz)
        chains = build_chains(ev, idx.trip_plan, cfg.chains)
        stats = day_stats(
            day,
            ev,
            vp["fetched_at"].to_numpy(dtype=float),
            owners.get(day.replace("-", ""), ""),
            cfg.days,
            tz,
        )
        _write_day({"events": ev, "chains": chains}, day, cfg.data.processed_dir)
        manifest["days"][day] = {
            "fingerprint": fingerprints[day],
            "stats": asdict(stats),
        }
        logger.info(
            "%s: %d zdarzen, %d kursow w lancuchach, %d linii, maks. przerwa %.1f min",
            day,
            stats.n_events,
            len(chains),
            stats.n_routes,
            stats.max_gap_min,
        )


def _log_summary(
    old: pd.DataFrame | None, new: pd.DataFrame, rebuilt: list[str]
) -> None:
    logger.info("przeliczone dni (%d): %s", len(rebuilt), ", ".join(rebuilt) or "brak")
    if old is not None and len(old):
        prev = old.set_index("service_date")["status"]
        for r in new.itertuples(index=False):
            before = prev.get(r.service_date)
            if before is not None and before != r.status:
                logger.info("%s: status %s -> %s", r.service_date, before, r.status)
    counts = new.groupby(["status", "role"]).size()
    for (status, role), n in counts.items():
        logger.info("dni %s / %s: %d", status, role, n)
    logger.info(
        "dni complete: %d z %d", int((new["status"] == COMPLETE).sum()), len(new)
    )


def run(
    cfg: Config,
    full: bool = False,
    force: set[str] | None = None,
    dry_run: bool = False,
) -> None:
    """Przelicza zmienione dni i odswieza `days.csv` oraz `manifest.json`.

    Args:
        cfg: konfiguracja projektu.
        full: przelicz wszystkie dni od zera.
        force: dni YYYY-MM-DD do przeliczenia niezaleznie od odcisku.
        dry_run: tylko wypisz, co zostaloby przeliczone.
    """
    processed = cfg.data.processed_dir
    manifest_path = processed / "manifest.json"
    days_path = processed / "days.csv"
    partitions = list_partitions(cfg.data.raw_dir / "vehicle_positions")
    if not partitions:
        raise FileNotFoundError(
            f"brak partycji w {cfg.data.raw_dir / 'vehicle_positions'}"
        )
    owners = calendar_owners(load_version_calendars(cfg.data.raw_dir / "static"))
    params = {"events": asdict(cfg.events), "chains": asdict(cfg.chains)}
    fingerprints = {
        d: day_fingerprint(d, partitions, owners, params, PIPELINE_VERSION)
        for d in partitions
    }
    manifest = {"days": {}} if full else load_manifest(manifest_path)
    todo = days_to_build(fingerprints, manifest, processed, force or set())
    if dry_run:
        logger.info("do przeliczenia (%d): %s", len(todo), ", ".join(todo) or "brak")
        return
    old_registry = pd.read_csv(days_path, dtype=str) if days_path.exists() else None
    if todo:
        _rebuild(todo, partitions, fingerprints, owners, manifest, cfg)
    manifest["days"] = {d: v for d, v in manifest["days"].items() if d in partitions}
    manifest["pipeline_version"] = PIPELINE_VERSION
    save_manifest(manifest_path, manifest)
    registry = build_registry(
        stats_from_manifest(manifest), cfg.days, cfg.data.timezone
    )
    atomic_write_bytes(days_path, registry.to_csv(index=False).encode("utf-8"))
    _log_summary(old_registry, registry, todo)
    logger.info("hash manifestu: %s", manifest_hash(manifest_path))


def main() -> None:
    """Punkt wejscia `uv run build-events`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--full", action="store_true", help="przelicz wszystkie dni od zera"
    )
    parser.add_argument(
        "--days", nargs="*", default=[], help="wymus przeliczenie tych dni (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="pokaz, co zostaloby przeliczone"
    )
    args = parser.parse_args()
    setup_logging()
    run(load_config(), full=args.full, force=set(args.days), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
