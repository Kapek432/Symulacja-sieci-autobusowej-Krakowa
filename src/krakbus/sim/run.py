"""Komenda `simulate`: doba obslugi w DES dla zakresu linii, wynik w schemacie zdarzen obserwowanych."""

import argparse
import json
import logging
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from krakbus.config import ROOT, load_config
from krakbus.ingest.gtfs_versions import load_schedule
from krakbus.logger import setup_logging
from krakbus.observed.events import index_schedule
from krakbus.observed.manifest import (
    atomic_write_bytes,
    atomic_write_parquet,
    manifest_hash,
)
from krakbus.observed.store import day_path
from krakbus.sim.boundary import boundary_starts, observed_end_delays
from krakbus.sim.engine import run_simpy
from krakbus.sim.network import Network, build_network, select_trips
from krakbus.sim.noise import draw_noise
from krakbus.sim.params import DEFAULT_SIM_CONFIG, SimConfig, load_sim_config

ENGINES = {"simpy": run_simpy}
SIM_COLUMNS = [
    "service_date",
    "vehicle_id",
    "trip_id",
    "route_id",
    "direction_id",
    "stop_sequence",
    "stop_id",
    "arr_s",
    "dep_s",
    "arr_ts",
    "dep_ts",
    "arr_delay_s",
    "dep_delay_s",
    "source",
    "run_id",
    "seed",
]
logger = logging.getLogger("simulate")


def scope_routes(sim_cfg: SimConfig, scope: str, routes: list[str] | None) -> list[str] | None:
    """Linie przebiegu: jawna lista albo zakres z configu (None = cala siec).

    Raises:
        ValueError: zakresu nie ma w configu.
    """
    if routes:
        return [str(r) for r in routes]
    if scope not in sim_cfg.scopes:
        raise ValueError(f"nieznany zakres {scope}; dostepne: {sorted(sim_cfg.scopes)}")
    return sim_cfg.scopes[scope]


def to_events(
    net: Network, sel: np.ndarray, delay: np.ndarray, run_id: str, seed: int
) -> pd.DataFrame:
    """Zdarzenia symulacji w schemacie zblizonym do `data/processed/events/`.

    `vehicle_id` to klucz bloku: w symulacji pojazd jedzie caly blok z planu.
    """
    st = net.stop_times
    rows = np.flatnonzero(~np.isnan(delay))
    ev = st.iloc[rows][["trip_id", "stop_sequence", "stop_id", "arr_s", "dep_s"]].copy()
    trips = net.trips.loc[ev["trip_id"]]
    d = delay[rows]
    ev["service_date"] = net.service_date
    ev["vehicle_id"] = trips["block_key"].to_numpy()
    ev["route_id"] = trips["route_id"].to_numpy()
    ev["direction_id"] = trips["direction_id"].to_numpy()
    ev["arr_ts"] = net.day_start + ev["arr_s"].to_numpy() + d
    ev["dep_ts"] = net.day_start + ev["dep_s"].to_numpy() + d
    ev["arr_delay_s"] = d
    ev["dep_delay_s"] = d
    ev["source"] = "sim"
    ev["run_id"] = run_id
    ev["seed"] = seed
    return ev[SIM_COLUMNS].reset_index(drop=True)


def simulate(
    net: Network,
    sim_cfg: SimConfig,
    routes: list[str] | None,
    label: str,
    seed: int,
    engine: str,
    end_delays: pd.Series | None,
) -> tuple[pd.DataFrame, dict]:
    """Jeden przebieg doby bez zapisu na dysk.

    Args:
        net: siec dnia.
        sim_cfg: config symulacji (model, `boundary`).
        routes: linie zakresu; None = cala siec.
        label: nazwa zakresu w `run_id`.
        seed: ziarno szumu.
        engine: klucz z `ENGINES`.
        end_delays: obserwowane opoznienia na koncu kursow (uzywane przy `boundary: observed`).

    Returns:
        Zdarzenia (`SIM_COLUMNS`) i metadane przebiegu.

    Raises:
        ValueError: w zakresie nie ma kursow tego dnia.
    """
    t0 = time.perf_counter()
    sel = select_trips(net, routes)
    if len(sel) == 0:
        raise ValueError(f"brak kursow linii {routes} w dniu {net.service_date}")
    noise = draw_noise(net, sim_cfg.model, seed)
    obs = end_delays if sim_cfg.boundary == "observed" else None
    starts = boundary_starts(net, sel, noise, sim_cfg.model, obs)
    delay = ENGINES[engine](net, sel, noise, sim_cfg.model, starts)
    run_id = f"{net.service_date}_{label}_{engine}_s{seed}"
    ev = to_events(net, sel, delay, run_id, seed)
    meta = {
        "run_id": run_id,
        "service_date": net.service_date,
        "routes": routes,
        "engine": engine,
        "seed": seed,
        "boundary": sim_cfg.boundary,
        "n_trips": len(sel),
        "n_boundary": len(starts),
        "n_events": len(ev),
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "model": asdict(sim_cfg.model),
    }
    return ev, meta


def _git_commit() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def _end_delays(processed: Path, day: str) -> pd.Series | None:
    path = day_path(processed, day, "chains")
    if not path.exists():
        logger.warning("brak %s; warunek brzegowy z delta", path)
        return None
    return observed_end_delays(pd.read_parquet(path, columns=["trip_id", "arr_end_delay_s"]))


def main() -> None:
    """Punkt wejscia `uv run simulate`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", required=True, help="data obslugi YYYY-MM-DD")
    parser.add_argument("--scope", default="pilot", help="pilot | corridor | city")
    parser.add_argument("--routes", nargs="*", help="jawna lista linii (zamiast zakresu)")
    parser.add_argument("--seed", type=int, help="ziarno (domyslnie z configu)")
    parser.add_argument("--engine", default="simpy", choices=sorted(ENGINES))
    parser.add_argument("--config", type=Path, default=DEFAULT_SIM_CONFIG)
    args = parser.parse_args()
    setup_logging()
    cfg = load_config()
    sim_cfg = load_sim_config(args.config)
    routes = scope_routes(sim_cfg, args.scope, args.routes)
    seed = sim_cfg.seed if args.seed is None else args.seed
    sched = load_schedule(cfg.data.raw_dir / "static")
    net = build_network(index_schedule(sched), args.date, cfg.data.timezone)
    processed = cfg.data.processed_dir
    end_delays = _end_delays(processed, args.date) if sim_cfg.boundary == "observed" else None
    label = "-".join(args.routes) if args.routes else args.scope
    ev, meta = simulate(net, sim_cfg, routes, label, seed, args.engine, end_delays)
    meta |= {
        "scope": args.scope,
        "gtfs_versions": sched.versions,
        "manifest_hash": manifest_hash(processed / "manifest.json"),
        "git_commit": _git_commit(),
    }
    out = processed / "sim" / meta["run_id"]
    atomic_write_parquet(ev, out / "events.parquet")
    atomic_write_bytes(out / "run.json", json.dumps(meta, indent=1, ensure_ascii=False).encode())
    logger.info(
        "%s: kursow %d (brzegowych %d), zdarzen %d, %.1f s; mediana opoznienia %.0f s",
        meta["run_id"],
        meta["n_trips"],
        meta["n_boundary"],
        meta["n_events"],
        meta["elapsed_s"],
        float(np.median(ev["arr_delay_s"])),
    )
    logger.info("zapisano %s", out)
