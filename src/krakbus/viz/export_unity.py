"""Komenda `export-unity`: przyjazdy i odjazdy obserwacji albo symulacji jako trajektorie dla Unity.

Kontrakt: `docs/EXPORT_UNITY.md` (`schema_version` 1).
"""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from krakbus.config import load_config
from krakbus.ingest.gtfs_versions import load_schedule
from krakbus.logger import setup_logging
from krakbus.observed.events import index_schedule
from krakbus.observed.manifest import atomic_write_bytes, atomic_write_parquet
from krakbus.observed.store import load_events
from krakbus.sim.network import build_network
from krakbus.viz.layers import observed_layer, sim_layer

SCHEMA_VERSION = 1
EXPORT_COLUMNS = [
    "t",
    "event",
    "vehicle_id",
    "trip_id",
    "route_id",
    "direction_id",
    "stop_id",
    "stop_sequence",
    "lat",
    "lon",
    "delay_s",
    "source",
    "run_id",
    "seed",
]
FORMATS = ("parquet", "jsonl")
KEYS = ["vehicle_id", "trip_id", "route_id", "direction_id", "stop_id", "stop_sequence"]
logger = logging.getLogger("export_unity")


def stop_coords(stops: pd.DataFrame) -> pd.DataFrame:
    """Wspolrzedne przystankow: indeks `stop_id`, kolumny `lat`, `lon` (float)."""
    s = stops.drop_duplicates("stop_id").set_index("stop_id")
    return pd.DataFrame({"lat": s["stop_lat"].astype(float), "lon": s["stop_lon"].astype(float)})


def export_rows(
    layer: pd.DataFrame, coords: pd.DataFrame, source: str, run_id: str, seed: int | None
) -> pd.DataFrame:
    """Wiersz na przyjazd i na odjazd ze wspolrzednymi przystanku, posortowane wg pojazdu i czasu.

    Args:
        layer: ramka `LAYER_COLUMNS` (`observed_layer` albo `sim_layer`).
        coords: `stop_coords`.
        source: `obs` albo `sim`.
        run_id: identyfikator przebiegu (dla obserwacji `obs_<dzien>`).
        seed: ziarno symulacji; None dla obserwacji.

    Returns:
        Ramka `EXPORT_COLUMNS`; zdarzenia bez czasu albo bez wspolrzednych przystanku odpadaja.
    """
    parts = [
        layer[KEYS].assign(t=layer[f"{e}_ts"], event=e, delay_s=layer[f"{e}_delay_s"])
        for e in ("arr", "dep")
    ]
    rows = pd.concat(parts, ignore_index=True).dropna(subset=["t"])
    rows = rows.join(coords, on="stop_id", how="inner")
    rows["source"] = source
    rows["run_id"] = run_id
    rows["seed"] = pd.array([seed] * len(rows), dtype="Int64")
    rows = rows.astype({"stop_sequence": "int64", "direction_id": "string"})
    # przy rownym czasie "arr" < "dep" alfabetycznie, wiec przyjazd jest przed odjazdem
    rows = rows.sort_values(["vehicle_id", "t", "event"], kind="stable")
    return rows[EXPORT_COLUMNS].reset_index(drop=True)


def export_meta(
    rows: pd.DataFrame,
    source: str,
    run_id: str,
    seed: int | None,
    service_date: str,
    routes: list[str] | None,
) -> dict:
    """Metadane pliku eksportu (`<nazwa>.meta.json`)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "run_id": run_id,
        "seed": seed,
        "service_date": service_date,
        "routes": routes,
        "n_rows": len(rows),
        "n_vehicles": int(rows["vehicle_id"].nunique()),
        "t_min": float(rows["t"].min()),
        "t_max": float(rows["t"].max()),
        "bbox": {
            "lat_min": float(rows["lat"].min()),
            "lat_max": float(rows["lat"].max()),
            "lon_min": float(rows["lon"].min()),
            "lon_max": float(rows["lon"].max()),
        },
        "columns": EXPORT_COLUMNS,
    }


def write_export(rows: pd.DataFrame, meta: dict, out_dir: Path, name: str, fmt: str) -> Path:
    """Zapisuje `<name>.parquet|jsonl` i `<name>.meta.json`.

    Raises:
        ValueError: format spoza `FORMATS`.
    """
    if fmt not in FORMATS:
        raise ValueError(f"format {fmt}; dostepne: {FORMATS}")
    path = out_dir / f"{name}.{fmt}"
    if fmt == "parquet":
        atomic_write_parquet(rows, path)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, rows.to_json(orient="records", lines=True).encode())
    side = meta | {"data_file": path.name}
    atomic_write_bytes(out_dir / f"{name}.meta.json", json.dumps(side, indent=1).encode())
    return path


def main() -> None:
    """Punkt wejscia `uv run export-unity`."""
    parser = argparse.ArgumentParser(
        description="Eksport przyjazdow i odjazdow dla Unity (kontrakt v1)"
    )
    parser.add_argument("--sim", help="run_id z data/processed/sim/")
    parser.add_argument("--obs", action="store_true", help="eksport obserwacji dnia --date")
    parser.add_argument("--date", help="YYYY-MM-DD (wymagane z --obs; przy --sim z run.json)")
    parser.add_argument("--routes", nargs="*", help="linie; domyslnie wszystkie")
    parser.add_argument("--format", default="parquet", choices=FORMATS)
    parser.add_argument("--out", type=Path, help="katalog; domyslnie data/processed/unity_samples")
    args = parser.parse_args()
    if not args.sim and not args.obs:
        parser.error("podaj --sim RUN_ID i/lub --obs --date D")
    if args.obs and not args.date:
        parser.error("--obs wymaga --date")
    setup_logging()
    cfg = load_config()
    processed = cfg.data.processed_dir
    out_dir = args.out or processed / "unity_samples"
    routes = [str(r) for r in args.routes] if args.routes else None
    sched = load_schedule(cfg.data.raw_dir / "static")
    coords = stop_coords(sched.stops)
    label = "-".join(routes) if routes else "all"
    jobs: list[tuple[pd.DataFrame, str, str, int | None, str, str]] = []
    if args.sim:
        layer, meta = sim_layer(processed / "sim" / args.sim, routes)
        name = args.sim if routes is None else f"{args.sim}_{label}"
        jobs.append((layer, "sim", meta["run_id"], int(meta["seed"]), meta["service_date"], name))
    if args.obs:
        net = build_network(index_schedule(sched), args.date, cfg.data.timezone)
        ev = load_events([args.date], statuses=None, processed_dir=processed)
        run_id = f"obs_{args.date}"
        layer = observed_layer(ev, net, routes)
        jobs.append((layer, "obs", run_id, None, args.date, f"{run_id}_{label}"))
    for layer, source, run_id, seed, day, name in jobs:
        rows = export_rows(layer, coords, source, run_id, seed)
        meta = export_meta(rows, source, run_id, seed, day, routes)
        path = write_export(rows, meta, out_dir, name, args.format)
        logger.info(
            "%s: %d wierszy, %d pojazdow -> %s", source, meta["n_rows"], meta["n_vehicles"], path
        )
