# M2 etap 3: Marey z symulacji i eksport dla Unity — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wykres Mareya linii z nakladka obserwacja ‖ symulacja (`uv run marey`) oraz eksport trajektorii przystankowych dla Unity w wersjonowanym kontrakcie (`uv run export-unity`, `docs/EXPORT_UNITY.md`).

**Architecture:** Nowy pakiet `src/krakbus/viz/`. `layers.py` sprowadza zdarzenia obserwowane i przebieg symulacji do jednego schematu warstwy. `marey.py` rysuje rozklad z sieci dnia (`sim.network.Network`) i dowolne warstwy na wspolnej osi czasu; skrypt w sandboxie staje sie nakladka na modul. `export_unity.py` zamienia warstwe na wiersze przyjazdu i odjazdu ze wspolrzednymi przystanku i zapisuje parquet albo JSON Lines z plikiem metadanych.

**Tech Stack:** Python 3.14, uv, pandas 3, numpy, matplotlib 3.11 (bez pyplot: `matplotlib.figure.Figure`), pyarrow, pytest, ruff.

Spec: `docs/superpowers/specs/2026-10-16-m2-des-design.md` (sekcja „Etap 3”), kontrakt w `docs/milestones/U_unity_mcp.md`.

## Global Constraints

- `uv run` zamiast `python`; testy `uv run pytest`, lint `uv run ruff check src tests`.
- Kod w `src/krakbus/viz/`, testy w `tests/viz/`; `logging` zamiast `print`; Google docstrings dla API publicznego; typy wszedzie, `X | None`.
- Komentarze i docstringi po polsku bez polskich znakow; bez emoji i separatorow.
- Commity: `(feat|fix|docs|chore) opis`, bez stopek AI. Nie commitowac `data/` (probki eksportu zostaja lokalnie w `data/processed/unity_samples/`).
- Kontrakt: `schema_version: 1`, jeden wiersz na przyjazd i odjazd; `t` w sekundach epoki; `lat`, `lon` przystanku; `delay_s`; `source` w {`obs`, `sim`}; `run_id`, `seed`.
- Czas na osi Mareya: godziny od poczatku doby GTFS (`net.day_start`), tak jak w dotychczasowym `marey.py`.

## File Structure

| Plik | Odpowiedzialnosc |
|---|---|
| `tests/__init__.py`, `tests/viz/__init__.py` | pakiety testow, zeby `tests/viz` mogl uzyc syntetyki z `tests/sim/conftest.py` |
| `tests/viz/conftest.py` | `small_net`, `small_stops`, `sim_events` |
| `src/krakbus/viz/__init__.py` | pakiet |
| `src/krakbus/viz/layers.py` | `LAYER_COLUMNS`, `observed_layer`, `sim_layer`, `last_complete_workday` |
| `src/krakbus/viz/marey.py` | `pattern_km`, `marey_figure`, CLI `marey` |
| `src/krakbus/viz/export_unity.py` | `SCHEMA_VERSION`, `EXPORT_COLUMNS`, `stop_coords`, `export_rows`, `export_meta`, `write_export`, CLI `export-unity` |
| `docs/EXPORT_UNITY.md` | kontrakt eksportu v1 (1 strona) |
| `sandbox/gtfs-experiments/marey.py` | nakladka wolajaca `krakbus.viz.marey.main` |
| `pyproject.toml` | skrypty `marey`, `export-unity` |

Istniejace interfejsy (etap 1):

- `build_network(idx, service_date, tz) -> Network`; `net.trips` (indeks `trip_id`; `route_id`, `direction_id` jako str), `net.stop_times` (`trip_id`, `stop_sequence`, `stop_id`, `arr_s`, ...; wiersze kursu ciagle i w kolejnosci `stop_sequence`), `net.day_start`, `net.service_date`.
- `simulate(net, sim_cfg, routes, label, seed, engine, end_delays) -> (ev, meta)`; `ev` ma `SIM_COLUMNS` (`vehicle_id`, `trip_id`, `route_id`, `direction_id`, `stop_sequence`, `stop_id`, `arr_ts`, `dep_ts`, `arr_delay_s`, `dep_delay_s`, ...); przebieg zapisany w `data/processed/sim/<run_id>/events.parquet` i `run.json` (`run_id`, `service_date`, `seed`, `routes`, ...).
- Zdarzenia obserwowane (`load_events([day], statuses=None, processed_dir=...)`): `vehicle_id`, `trip_id`, `route_id`, `stop_sequence`, `stop_id`, `arr_ts`, `dep_ts` (int, epoka), `arr_delay_s`, `dep_delay_s`, `delay_class`; bez `direction_id`.
- `load_days(processed)`, `select_days(reg, statuses=...)`, `COMPLETE` z `krakbus.observed.days`; `Schedule.stops` (`stop_id`, `stop_name`, `stop_lat`, `stop_lon` jako str).
- `atomic_write_parquet(df, path)`, `atomic_write_bytes(path, data)` z `krakbus.observed.manifest`.
- `tests/sim/conftest.py`: `TRIPS`, `DATE`, `TZ`, `make_schedule`, `zero_model`.

---

### Task 1: Warstwy zdarzen

**Files:**
- Create: `tests/__init__.py` (pusty), `tests/viz/__init__.py` (pusty), `tests/viz/conftest.py`, `tests/viz/test_layers.py`, `src/krakbus/viz/__init__.py`, `src/krakbus/viz/layers.py`

**Interfaces:**
- Consumes: `Network`, `simulate`, `load_sim_config`, `load_days`, `select_days`, `COMPLETE`.
- Produces: `LAYER_COLUMNS: list[str]` = `vehicle_id, trip_id, route_id, direction_id, stop_sequence, stop_id, arr_ts, dep_ts, arr_delay_s, dep_delay_s` (czasy i opoznienia float); `observed_layer(ev: pd.DataFrame, net: Network, routes: list[str] | None) -> pd.DataFrame`; `sim_layer(run_dir: Path, routes: list[str] | None) -> tuple[pd.DataFrame, dict]`; `last_complete_workday(processed: Path) -> str`; fixtures `small_net`, `small_stops`, `sim_events`.

- [ ] **Step 1: conftest i test**

`tests/viz/conftest.py`:

```python
from dataclasses import replace

import pandas as pd
import pytest

from krakbus.observed.events import index_schedule
from krakbus.sim.network import Network, build_network
from krakbus.sim.params import load_sim_config
from krakbus.sim.run import simulate

from ..sim.conftest import DATE, TRIPS, TZ, make_schedule

COORDS = {
    "s1": (50.00, 19.90),
    "s2": (50.01, 19.90),
    "s3": (50.02, 19.90),
    "s4": (50.03, 19.90),
    "x1": (50.01, 19.80),
    "x2": (50.02, 19.95),
}


@pytest.fixture
def small_net() -> Network:
    return build_network(index_schedule(make_schedule(TRIPS)), DATE, TZ)


@pytest.fixture
def small_stops() -> pd.DataFrame:
    return pd.DataFrame(
        [(s, str(lat), str(lon), s.upper()) for s, (lat, lon) in COORDS.items()],
        columns=["stop_id", "stop_lat", "stop_lon", "stop_name"],
    )


@pytest.fixture
def sim_events(small_net: Network) -> pd.DataFrame:
    cfg = replace(load_sim_config(), boundary="delta")
    ev, _ = simulate(small_net, cfg, None, "city", seed=0, engine="simpy", end_delays=None)
    return ev
```

`tests/viz/test_layers.py`:

```python
import json

import numpy as np
import pandas as pd

from krakbus.viz.layers import LAYER_COLUMNS, observed_layer, sim_layer


def _as_observed(sim_events: pd.DataFrame) -> pd.DataFrame:
    obs = sim_events.drop(columns="direction_id").copy()
    obs["arr_delay_s"] = obs["arr_delay_s"].round().astype("Int64")
    obs.loc[0, "arr_delay_s"] = pd.NA
    obs["arr_ts"] = obs["arr_ts"].round().astype("int64")
    obs["delay_class"] = pd.array(["ok"] * len(obs), dtype="string")
    obs.loc[1, "delay_class"] = "outlier"
    obs.loc[2, "delay_class"] = pd.NA
    return obs


def test_observed_layer_keeps_ok_and_adds_direction(small_net, sim_events) -> None:
    obs = _as_observed(sim_events)
    layer = observed_layer(obs, small_net, None)
    assert list(layer.columns) == LAYER_COLUMNS
    assert len(layer) == len(obs) - 2
    assert set(layer["direction_id"]) == {"0", "1"}
    assert layer["arr_delay_s"].dtype == np.float64 and layer["arr_delay_s"].isna().sum() == 1
    assert layer["arr_ts"].dtype == np.float64


def test_observed_layer_filters_routes(small_net, sim_events) -> None:
    layer = observed_layer(_as_observed(sim_events), small_net, ["B"])
    assert set(layer["route_id"]) == {"B"}


def test_sim_layer_reads_run_dir(tmp_path, sim_events) -> None:
    sim_events.to_parquet(tmp_path / "events.parquet", index=False)
    (tmp_path / "run.json").write_text(json.dumps({"run_id": "r", "seed": 0}), encoding="utf-8")
    layer, meta = sim_layer(tmp_path, ["A"])
    assert meta["run_id"] == "r"
    assert list(layer.columns) == LAYER_COLUMNS
    assert set(layer["trip_id"]) == {"A0", "A1", "A2"}
```

- [ ] **Step 2:** `uv run pytest tests/viz -q` → FAIL (`No module named 'krakbus.viz'`).
- [ ] **Step 3:** `src/krakbus/viz/__init__.py`:

```python
"""Wizualizacja i eksport wynikow (Marey, Unity)."""
```

`src/krakbus/viz/layers.py`:

```python
"""Warstwy zdarzen do wizualizacji i eksportu: obserwacja dnia i przebieg symulacji w jednym schemacie."""

import json
from pathlib import Path

import pandas as pd

from krakbus.observed.days import COMPLETE
from krakbus.observed.store import load_days, select_days
from krakbus.sim.network import Network

LAYER_COLUMNS = [
    "vehicle_id",
    "trip_id",
    "route_id",
    "direction_id",
    "stop_sequence",
    "stop_id",
    "arr_ts",
    "dep_ts",
    "arr_delay_s",
    "dep_delay_s",
]
FLOAT_COLUMNS = ["arr_ts", "dep_ts", "arr_delay_s", "dep_delay_s"]


def _normalize(ev: pd.DataFrame, routes: list[str] | None) -> pd.DataFrame:
    if routes is not None:
        ev = ev[ev["route_id"].astype(str).isin(routes)]
    out = ev[LAYER_COLUMNS].astype({c: "float64" for c in FLOAT_COLUMNS})
    return out.astype({"route_id": str, "vehicle_id": str, "trip_id": str}).reset_index(drop=True)


def observed_layer(ev: pd.DataFrame, net: Network, routes: list[str] | None) -> pd.DataFrame:
    """Zdarzenia obserwowane z `delay_class` = ok, z kierunkiem kursu z rozkladu dnia.

    Args:
        ev: zdarzenia dnia z `load_events`.
        net: siec tego dnia (zrodlo `direction_id`).
        routes: linie; None = wszystkie.

    Returns:
        Ramka `LAYER_COLUMNS`; czasy i opoznienia jako float (brak = NaN).
    """
    ok = ev[ev["delay_class"].fillna("") == "ok"]
    ok = ok.assign(direction_id=ok["trip_id"].map(net.trips["direction_id"]))
    return _normalize(ok, routes)


def sim_layer(run_dir: Path, routes: list[str] | None) -> tuple[pd.DataFrame, dict]:
    """Zdarzenia przebiegu z `data/processed/sim/<run_id>/` i jego `run.json`."""
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    return _normalize(pd.read_parquet(run_dir / "events.parquet"), routes), meta


def last_complete_workday(processed: Path) -> str:
    """Ostatni dzien roboczy o statusie `complete` z `days.csv`.

    Raises:
        ValueError: brak takiego dnia.
    """
    reg = load_days(processed)
    work = reg[pd.to_datetime(reg["service_date"]).dt.dayofweek < 5]
    days = select_days(work, statuses=(COMPLETE,))
    if not days:
        raise ValueError("brak dni roboczych complete; najpierw uv run build-events")
    return days[-1]
```

- [ ] **Step 4:** `uv run pytest -q` → PASS (caly zestaw: dodanie `tests/__init__.py` nie moze zepsuc `tests/ingest` i `tests/observed`); `uv run ruff check src tests`.
- [ ] **Step 5:** commit `(feat) event layers for observed and simulated days`.

---

### Task 2: Marey z nakladka obserwacja ‖ symulacja

**Files:**
- Create: `src/krakbus/viz/marey.py`, `tests/viz/test_marey.py`
- Modify: `sandbox/gtfs-experiments/marey.py` (nakladka), `pyproject.toml` (`marey = "krakbus.viz.marey:main"`)

**Interfaces:**
- Consumes: `LAYER_COLUMNS`, `observed_layer`, `sim_layer`, `last_complete_workday` (Task 1); `Network`, `build_network`, `index_schedule`, `load_schedule`, `load_events`.
- Produces: `pattern_km(st: pd.DataFrame, stops: pd.DataFrame) -> pd.Series` (indeks `stop_id`, km od poczatku najczestszego wariantu); `marey_figure(net: Network, stops: pd.DataFrame, route: str, layers: dict[str, pd.DataFrame]) -> Figure`; CLI `uv run marey [linia] [YYYY-MM-DD] [--sim RUN_ID] [--no-obs]`.

- [ ] **Step 1: test** `tests/viz/test_marey.py`

```python
import pandas as pd
import pytest

from krakbus.viz.marey import marey_figure, pattern_km


def test_pattern_km_follows_most_common_stop_sequence(small_stops) -> None:
    st = pd.DataFrame(
        {
            "trip_id": ["t1"] * 3 + ["t2"] * 3 + ["t3"] * 2,
            "stop_sequence": [1, 2, 3, 1, 2, 3, 1, 2],
            "stop_id": ["s1", "s2", "s3", "s1", "s2", "s3", "s1", "x1"],
        }
    )
    km = pattern_km(st, small_stops)
    assert list(km.index) == ["s1", "s2", "s3"]
    assert km["s1"] == 0.0
    assert km["s3"] == pytest.approx(2.2239, rel=1e-3)


def test_single_layer_draws_schedule_and_trips_per_direction(small_net, small_stops, sim_events) -> None:
    fig = marey_figure(small_net, small_stops, "A", {"sim": sim_events})
    axes = fig.get_axes()
    assert len(axes) == 2
    assert len(axes[0].lines) == 4
    assert len(axes[1].lines) == 2
    assert axes[0].get_legend() is None


def test_two_layers_get_legend(small_net, small_stops, sim_events) -> None:
    fig = marey_figure(small_net, small_stops, "A", {"obs": sim_events, "sim": sim_events})
    ax = fig.get_axes()[0]
    assert len(ax.lines) == 6
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["obs", "sim"]


def test_route_without_trips_raises(small_net, small_stops, sim_events) -> None:
    with pytest.raises(ValueError, match="brak kursow"):
        marey_figure(small_net, small_stops, "Z", {"sim": sim_events})
```

Liczby linii: kierunek 0 linii A to kursy A0 i A2 (2 linie rozkladu + 2 warstwy), kierunek 1 to A1 (1 + 1). Przy dwoch warstwach kierunek 0 ma 2 + 2 + 2; legenda z uchwytow `Line2D`, ktore nie trafiaja do `ax.lines`.

- [ ] **Step 2:** `uv run pytest tests/viz/test_marey.py -q` → FAIL.
- [ ] **Step 3:** `src/krakbus/viz/marey.py`:

```python
"""Wykres Mareya linii w dniu: rozklad oraz warstwy obserwacji i symulacji na wspolnej osi.

Os pionowa to odleglosc wzdluz najczestszego wariantu trasy w kierunku (proste miedzy
przystankami, bo feed nie ma `shape_dist_traveled`), pozioma to godziny od poczatku doby GTFS.
Szare linie to rozklad kursow obecnych w warstwach. Jedna warstwa jest kolorowana wg pojazdu,
kilka warstw wg zrodla (z legenda).
"""

import argparse
import logging

import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from krakbus.config import load_config
from krakbus.ingest.gtfs_versions import load_schedule
from krakbus.logger import setup_logging
from krakbus.observed.events import index_schedule
from krakbus.observed.store import load_events
from krakbus.sim.network import Network, build_network
from krakbus.viz.layers import last_complete_workday, observed_layer, sim_layer

EARTH_KM = 6371.0
LAYER_COLORS = {"obs": "tab:blue", "sim": "tab:orange"}
logger = logging.getLogger("marey")


def pattern_km(st: pd.DataFrame, stops: pd.DataFrame) -> pd.Series:
    """Odleglosc [km] przystankow najczestszego wariantu trasy od jego poczatku.

    Args:
        st: `trip_id`, `stop_sequence` (int), `stop_id` kursow jednego kierunku.
        stops: `stop_id`, `stop_lat`, `stop_lon`.

    Returns:
        Seria km z indeksem `stop_id` w kolejnosci wariantu (przystanek powtorzony: pierwsze wystapienie).
    """
    seqs = st.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id")["stop_id"].agg(tuple)
    pattern = list(seqs.value_counts().idxmax())
    xy = stops.drop_duplicates("stop_id").set_index("stop_id").loc[pattern, ["stop_lat", "stop_lon"]]
    lat = np.radians(xy["stop_lat"].to_numpy(float))
    lon = np.radians(xy["stop_lon"].to_numpy(float))
    dlat, dlon = np.diff(lat), np.diff(lon)
    h = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    km = np.r_[0, np.cumsum(2 * EARTH_KM * np.arcsin(np.sqrt(h)))]
    return pd.Series(km, index=pattern).groupby(level=0, sort=False).first()


def _draw_layers(ax: Axes, layers: dict[str, pd.DataFrame], km: pd.Series, t0: float) -> None:
    by_vehicle = len(layers) == 1
    for name, ev in layers.items():
        e = ev[ev["stop_id"].isin(km.index)].sort_values("stop_sequence")
        if by_vehicle:
            vehicles = sorted(e["vehicle_id"].unique())
            cmap = colormaps["tab20"]
            colors = {v: cmap(i % cmap.N) for i, v in enumerate(vehicles)}
        for (veh, _), g in e.groupby(["vehicle_id", "trip_id"]):
            color = colors[veh] if by_vehicle else LAYER_COLORS.get(name, "tab:green")
            ax.plot((g["arr_ts"] - t0) / 3600, g["stop_id"].map(km), color=color, lw=1.0, marker=".", ms=2)
    if not by_vehicle:
        handles = [Line2D([], [], color=LAYER_COLORS.get(n, "tab:green"), label=n) for n in layers]
        ax.legend(handles=handles, loc="upper left")


def _panel(
    ax: Axes,
    net: Network,
    stops: pd.DataFrame,
    trip_ids: set[str],
    layers: dict[str, pd.DataFrame],
    title: str,
) -> None:
    st = net.stop_times[net.stop_times["trip_id"].isin(trip_ids)]
    km = pattern_km(st, stops)
    for _, g in st[st["stop_id"].isin(km.index)].groupby("trip_id", sort=False):
        ax.plot(g["arr_s"] / 3600, g["stop_id"].map(km), color="0.75", lw=0.6)
    _draw_layers(ax, {n: ev[ev["trip_id"].isin(trip_ids)] for n, ev in layers.items()}, km, net.day_start)
    names = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]
    first, last = km.idxmin(), km.idxmax()
    ax.set_yticks([km[first], km[last]], [names.get(first, first), names.get(last, last)])
    ax.set_ylabel("km wzdluz trasy")
    ax.set_title(title)
    ax.grid(alpha=0.3)


def _trip_counts(layers: dict[str, pd.DataFrame], ids: set[str]) -> str:
    return ", ".join(
        f"{n} {ev.loc[ev['trip_id'].isin(ids), 'trip_id'].nunique()}" for n, ev in layers.items()
    )


def marey_figure(
    net: Network, stops: pd.DataFrame, route: str, layers: dict[str, pd.DataFrame]
) -> Figure:
    """Marey linii `route`: panel na kierunek, rozklad kursow z warstw i same warstwy.

    Args:
        net: siec dnia (rozklad, kierunki, poczatek doby).
        stops: przystanki z `stop_lat`, `stop_lon`, `stop_name`.
        route: linia.
        layers: nazwa warstwy (`obs`, `sim`) -> ramka `LAYER_COLUMNS`.

    Returns:
        Figura matplotlib (bez pyplot, do `savefig`).

    Raises:
        ValueError: zadna warstwa nie ma kursow tej linii w sieci dnia.
    """
    in_layers = set().union(*(set(ev["trip_id"]) for ev in layers.values()))
    trips = net.trips[(net.trips["route_id"].astype(str) == route) & net.trips.index.isin(in_layers)]
    if trips.empty:
        raise ValueError(f"brak kursow linii {route} w warstwach dnia {net.service_date}")
    dirs = sorted(trips["direction_id"].dropna().unique())
    fig = Figure(figsize=(18, 6 * len(dirs)))
    axes = fig.subplots(len(dirs), 1, squeeze=False)[:, 0]
    for ax, d in zip(axes, dirs):
        ids = set(trips.index[trips["direction_id"] == d])
        title = f"linia {route}, {net.service_date}, kierunek {d}: kursow {_trip_counts(layers, ids)}"
        _panel(ax, net, stops, ids, layers, title)
    axes[-1].set_xlabel("godzina (od poczatku doby GTFS)")
    fig.tight_layout()
    return fig


def main() -> None:
    """Punkt wejscia `uv run marey`."""
    parser = argparse.ArgumentParser(description="Wykres Mareya linii: rozklad, obserwacja, symulacja")
    parser.add_argument("route", nargs="?", default="179")
    parser.add_argument("date", nargs="?", help="YYYY-MM-DD; domyslnie dzien przebiegu albo ostatni pelny roboczy")
    parser.add_argument("--sim", help="run_id z data/processed/sim/ (nakladka symulacji)")
    parser.add_argument("--no-obs", action="store_true", help="bez warstwy obserwacji")
    args = parser.parse_args()
    if args.no_obs and not args.sim:
        parser.error("--no-obs bez --sim: nie ma czego rysowac")
    setup_logging()
    cfg = load_config()
    processed = cfg.data.processed_dir
    layers: dict[str, pd.DataFrame] = {}
    sim_ev: pd.DataFrame | None = None
    sim_meta: dict | None = None
    if args.sim:
        sim_ev, sim_meta = sim_layer(processed / "sim" / args.sim, [args.route])
    if args.date and sim_meta and args.date != sim_meta["service_date"]:
        parser.error(f"przebieg {args.sim} jest z dnia {sim_meta['service_date']}, nie {args.date}")
    day = args.date or (sim_meta["service_date"] if sim_meta else last_complete_workday(processed))
    sched = load_schedule(cfg.data.raw_dir / "static")
    net = build_network(index_schedule(sched), day, cfg.data.timezone)
    if not args.no_obs:
        ev = load_events([day], statuses=None, processed_dir=processed)
        layers["obs"] = observed_layer(ev, net, [args.route])
    if sim_ev is not None:
        layers["sim"] = sim_ev
    fig = marey_figure(net, sched.stops, args.route, layers)
    suffix = f"_{args.sim}" if args.sim else ""
    out = processed / "week_report" / "figures" / f"marey_{args.route}_{day}{suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    logger.info("zapisano %s", out)
```

`sandbox/gtfs-experiments/marey.py` (cala zawartosc):

```python
"""marey.py: nakladka na `uv run marey` (kod w `krakbus.viz.marey`).

Uzycie: uv run sandbox/gtfs-experiments/marey.py [linia] [YYYY-MM-DD] [--sim RUN_ID] [--no-obs]
"""

from krakbus.viz.marey import main

if __name__ == "__main__":
    main()
```

`pyproject.toml`, `[project.scripts]`: dopisac `marey = "krakbus.viz.marey:main"`, potem `uv sync`.

- [ ] **Step 4:** `uv run pytest tests/viz -q` → PASS; `uv run ruff check src tests` (dlugie linie w `marey.py` zawinac wg `ruff format`, jesli lint zglosi).
- [ ] **Step 5:** smoke na prawdziwych danych (wymaga przebiegu pilota z etapu 1):

```bash
uv run simulate --date 2026-10-14 --scope pilot
uv run marey 179 2026-10-14
uv run marey 179 --sim 2026-10-14_pilot_simpy_s0
```

Obejrzec `data/processed/week_report/figures/marey_179_2026-10-14_2026-10-14_pilot_simpy_s0.png`: dwa panele, szary rozklad, niebieska obserwacja, pomaranczowa symulacja; kursy monotoniczne w czasie; pierwszy wykres taki sam jak przed przeniesieniem (kolory wg pojazdu).
- [ ] **Step 6:** commit `(feat) Marey module with observed and simulated overlay`.

---

### Task 3: Eksport dla Unity i kontrakt v1

**Files:**
- Create: `src/krakbus/viz/export_unity.py`, `tests/viz/test_export_unity.py`, `docs/EXPORT_UNITY.md`
- Modify: `pyproject.toml` (`export-unity = "krakbus.viz.export_unity:main"`)

**Interfaces:**
- Consumes: `LAYER_COLUMNS`, `observed_layer`, `sim_layer` (Task 1); `atomic_write_parquet`, `atomic_write_bytes`.
- Produces: `SCHEMA_VERSION = 1`; `EXPORT_COLUMNS = [t, event, vehicle_id, trip_id, route_id, direction_id, stop_id, stop_sequence, lat, lon, delay_s, source, run_id, seed]`; `FORMATS = ("parquet", "jsonl")`; `stop_coords(stops) -> pd.DataFrame` (indeks `stop_id`; `lat`, `lon`); `export_rows(layer, coords, source, run_id, seed: int | None) -> pd.DataFrame`; `export_meta(rows, source, run_id, seed, service_date, routes) -> dict`; `write_export(rows, meta, out_dir, name, fmt) -> Path`; CLI `uv run export-unity`.

- [ ] **Step 1: test** `tests/viz/test_export_unity.py`

```python
import json

import numpy as np
import pandas as pd
import pytest

from krakbus.viz.export_unity import (
    EXPORT_COLUMNS,
    SCHEMA_VERSION,
    export_meta,
    export_rows,
    stop_coords,
    write_export,
)
from krakbus.viz.layers import LAYER_COLUMNS


def _layer() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "vehicle_id": ["v1", "v1", "v2"],
            "trip_id": ["A0", "A0", "B0"],
            "route_id": ["A", "A", "B"],
            "direction_id": ["0", "0", "0"],
            "stop_sequence": [2, 1, 1],
            "stop_id": ["s2", "s1", "zz"],
            "arr_ts": [1060.0, 1000.0, 900.0],
            "dep_ts": [np.nan, 1030.0, 950.0],
            "arr_delay_s": [60.0, 0.0, 5.0],
            "dep_delay_s": [np.nan, 30.0, 10.0],
        }
    )[LAYER_COLUMNS]


def test_rows_per_arrival_and_departure_sorted_with_coords(small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    assert list(rows.columns) == EXPORT_COLUMNS
    assert rows["t"].tolist() == [1000.0, 1030.0, 1060.0]
    assert rows["event"].tolist() == ["arr", "dep", "arr"]
    assert rows["delay_s"].tolist() == [0.0, 30.0, 60.0]
    assert rows["lat"].tolist() == [50.00, 50.00, 50.01]
    assert (rows["seed"] == 3).all() and (rows["source"] == "sim").all()


def test_observed_rows_have_null_seed(small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "obs", "obs_2026-10-14", None)
    assert rows["seed"].isna().all()


def test_meta_has_version_bbox_and_counts(small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    meta = export_meta(rows, "sim", "run1", 3, "2026-10-14", ["A"])
    assert meta["schema_version"] == SCHEMA_VERSION == 1
    assert meta["n_rows"] == 3 and meta["n_vehicles"] == 1
    assert meta["t_min"] == 1000.0 and meta["t_max"] == 1060.0
    assert meta["bbox"] == {"lat_min": 50.0, "lat_max": 50.01, "lon_min": 19.9, "lon_max": 19.9}
    assert meta["columns"] == EXPORT_COLUMNS


@pytest.mark.parametrize("fmt", ["parquet", "jsonl"])
def test_write_export_roundtrip(tmp_path, small_stops, fmt) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    meta = export_meta(rows, "sim", "run1", 3, "2026-10-14", None)
    path = write_export(rows, meta, tmp_path, "run1", fmt)
    back = pd.read_parquet(path) if fmt == "parquet" else pd.read_json(path, lines=True)
    assert len(back) == 3 and back["t"].tolist() == [1000.0, 1030.0, 1060.0]
    side = json.loads((tmp_path / "run1.meta.json").read_text(encoding="utf-8"))
    assert side["data_file"] == path.name and side["schema_version"] == 1


def test_unknown_format_rejected(tmp_path, small_stops) -> None:
    rows = export_rows(_layer(), stop_coords(small_stops), "sim", "run1", 3)
    with pytest.raises(ValueError, match="format"):
        write_export(rows, {}, tmp_path, "x", "csv")
```

Wiersz z przystankiem `zz` (brak wspolrzednych) odpada; brak `dep_ts` w pierwszym wierszu warstwy daje tylko przyjazd.

- [ ] **Step 2:** `uv run pytest tests/viz/test_export_unity.py -q` → FAIL.
- [ ] **Step 3:** `src/krakbus/viz/export_unity.py`:

```python
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
    parser = argparse.ArgumentParser(description="Eksport przyjazdow i odjazdow dla Unity (kontrakt v1)")
    parser.add_argument("--sim", help="run_id z data/processed/sim/")
    parser.add_argument("--obs", action="store_true", help="eksport obserwacji dnia --date")
    parser.add_argument("--date", help="YYYY-MM-DD (wymagane z --obs; przy --sim z run.json)")
    parser.add_argument("--routes", nargs="*", help="linie; domyslnie wszystkie z przebiegu albo dnia")
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
        jobs.append((observed_layer(ev, net, routes), "obs", run_id, None, args.date, f"{run_id}_{label}"))
    for layer, source, run_id, seed, day, name in jobs:
        rows = export_rows(layer, coords, source, run_id, seed)
        meta = export_meta(rows, source, run_id, seed, day, routes)
        path = write_export(rows, meta, out_dir, name, args.format)
        logger.info("%s: %d wierszy, %d pojazdow -> %s", source, meta["n_rows"], meta["n_vehicles"], path)
```

`docs/EXPORT_UNITY.md`:

````markdown
# Eksport dla Unity, kontrakt v1

Unity tylko odtwarza wyniki; model zostaje w Pythonie (tor U, `docs/milestones/U_unity_mcp.md`).

## Pliki

`uv run export-unity` zapisuje do `data/processed/unity_samples/` (lokalnie, `data/` nie idzie do gita) parę plików:

- `<nazwa>.parquet` albo `<nazwa>.jsonl` (`--format jsonl`: jeden obiekt JSON na linię),
- `<nazwa>.meta.json`: metadane.

Nazwy: symulacja `<run_id>` (np. `2026-10-14_pilot_simpy_s0`, z `_<linie>` przy `--routes`), obserwacja `obs_<dzień>_<linie|all>`.

```
uv run export-unity --sim 2026-10-14_pilot_simpy_s0
uv run export-unity --obs --date 2026-10-14 --routes 179 --format jsonl
```

## Wiersze

Jeden wiersz na przyjazd i jeden na odjazd pojazdu z przystanku, posortowane wg `vehicle_id`, potem `t` (przy równym czasie przyjazd przed odjazdem).

| Kolumna | Typ | Znaczenie |
|---|---|---|
| `t` | float | czas zdarzenia, sekundy epoki Unix (UTC) |
| `event` | str | `arr` albo `dep` |
| `vehicle_id` | str | pojazd; w symulacji klucz bloku (`service_id\|block_id`) |
| `trip_id` | str | kurs GTFS |
| `route_id` | str | linia |
| `direction_id` | str / null | kierunek z GTFS |
| `stop_id` | str | przystanek (słupek) GTFS |
| `stop_sequence` | int | kolejność przystanku w kursie |
| `lat`, `lon` | float | współrzędne przystanku (WGS84) |
| `delay_s` | float / null | opóźnienie względem rozkładu w sekundach (kolor) |
| `source` | str | `obs` albo `sim` |
| `run_id` | str | przebieg symulacji albo `obs_<dzień>` |
| `seed` | int / null | ziarno symulacji; null dla obserwacji |

Obserwacja zawiera tylko zdarzenia z `delay_class` = `ok`. W symulacji postój na przystanku pośrednim trwa tyle co w rozkładzie (w GTFS ZTP 0 s), więc `arr` i `dep` mają ten sam czas.

## Odtwarzanie

Pozycja pojazdu w chwili `T`: dwa kolejne wiersze pojazdu z `t1 ≤ T < t2`; między nimi interpolacja liniowa `lat`, `lon` (albo po geometrii `shapes.txt`, jeśli scena ją ma). Przerwa między końcem kursu a startem następnego to postój na pętli. Pojazd nie istnieje przed pierwszym i po ostatnim wierszu. Kolor wg `delay_s` z ostatniego wiersza przed `T`.

## Metadane (`<nazwa>.meta.json`)

`schema_version`, `source`, `run_id`, `seed`, `service_date`, `routes` (null = wszystkie), `n_rows`, `n_vehicles`, `t_min`, `t_max`, `bbox` (`lat_min`, `lat_max`, `lon_min`, `lon_max`), `columns`, `data_file`.

## Wersjonowanie

Zmiana, która psuje istniejący loader (usunięcie albo zmiana znaczenia kolumny, inna jednostka), podnosi `schema_version`. Dodanie kolumny na końcu nie podnosi wersji; loader ignoruje nieznane kolumny.
````

`pyproject.toml`, `[project.scripts]`: dopisac `export-unity = "krakbus.viz.export_unity:main"`, potem `uv sync`.

- [ ] **Step 4:** `uv run pytest tests/viz -q` → PASS; `uv run ruff check src tests`.
- [ ] **Step 5:** smoke:

```bash
uv run export-unity --sim 2026-10-14_pilot_simpy_s0
uv run export-unity --obs --date 2026-10-14 --routes 179 --format jsonl
```

Sprawdzic w `data/processed/unity_samples/`: liczba wierszy symulacji = 2 × liczba zdarzen przebiegu (6 027 → 12 054), `bbox` w granicach Krakowa (lat ok. 49,9–50,2, lon ok. 19,7–20,3), `t_min`/`t_max` w dobie 14.10.
- [ ] **Step 6:** commit `(feat) Unity export with versioned contract`.

---

### Task 4: Dokumentacja

**Files:**
- Modify: `docs/milestones/M2_des.md`, `docs/milestones/U_unity_mcp.md`, `docs/milestones/M1_dane.md` (tylko odnosnik do nowego miejsca Mareya, bez zmiany odhaczen), `docs/PLAN_REALIZACJI.md`, `sandbox/gtfs-experiments/README_skrypty.md`, `docs/DZIENNIK.md`

- [ ] `M2_des.md`: odhaczyc E (oba punkty) i F; jesli etap 2 jest juz zrobiony, zaktualizowac status M2 i Definition of Done.
- [ ] `U_unity_mcp.md`, „Kontrakt eksportu”: odhaczyc opis kontraktu (`docs/EXPORT_UNITY.md`), exporter (`krakbus.viz.export_unity`), wersjonowanie; probka lokalnie w `data/processed/unity_samples/` (nie w gicie, zasada repo) — odhaczyc z ta adnotacja.
- [ ] `M1_dane.md`, punkt o Mareyu: dopisac „(od M2: `uv run marey`, kod w `krakbus.viz.marey`)”.
- [ ] `PLAN_REALIZACJI.md`, „Stan na 16.10”: linia o etapie 3.
- [ ] `README_skrypty.md`: sekcja `marey` (zastapic opis `marey.py`: `uv run marey [linia] [dzien] [--sim RUN_ID] [--no-obs]`, nakladka obs ‖ sim, nazwy plikow), nowa sekcja `export-unity` z odnosnikiem do `docs/EXPORT_UNITY.md`; w „Kolejnosc uruchamiania” dopisac obie komendy.
- [ ] `DZIENNIK.md`: wpis na gorze (autor z `git config user.name`); decyzje: rozklad w Mareyu z `Network` zamiast osobnego parsowania `stop_times`; kolor wg pojazdu przy jednej warstwie, wg zrodla przy dwoch; eksport per przystanek ze wspolrzednymi przystanku (interpolacja w Unity) zamiast probkowania pozycji co N sekund (mniejsze pliki, bez decyzji o kroku); parquet i JSONL; probka nie w gicie. Sprawdzone: testy, liczby wierszy ze smoke, obejrzany Marey.
- [ ] commit `(docs) M2 stage 3: Marey overlay and Unity export contract`.

## Self-review

- Spec etapu 3: Marey przeniesiony do `src/krakbus/viz/marey.py`, sandbox woła moduł, nakładka obs i sim tej samej linii i dnia (Task 2); `export_unity.py` i `docs/EXPORT_UNITY.md` z `schema_version: 1`, wiersz na przyjazd i odjazd, `t` w sekundach epoki, `vehicle_id`, `trip_id`, `route_id`, `lat`, `lon` przystanku, `delay_s`, `source`, `run_id`, `seed`, parquet; próbka lokalnie (Task 3). Dodatkowo JSONL i `direction_id`, `stop_id`, `stop_sequence`, `event` (Unity potrzebuje kolejności i rozróżnienia przyjazd/odjazd).
- Typy: `LAYER_COLUMNS` z Task 1 konsumowane przez `marey_figure` (`trip_id`, `stop_id`, `stop_sequence`, `arr_ts`, `vehicle_id`) i `export_rows` (`KEYS`, `*_ts`, `*_delay_s`); `sim_layer` zwraca `(DataFrame, dict)` w obu CLI; `last_complete_workday` tylko w `marey.main`.
- Liczby w testach: `small_stops` daje s1 (50,00), s2 (50,01), więc `lat` = [50,00, 50,00, 50,01]; 0,02° szerokości = 2,2239 km.
