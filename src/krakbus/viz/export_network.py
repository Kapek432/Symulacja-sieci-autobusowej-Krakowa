"""Komenda `export-network`: graf sieci (przystanki i odcinki z lamanymi) dla Unity.

Kontrakt: `docs/EXPORT_UNITY.md` (`schema_version` 1).
"""

import argparse
import itertools
import json
import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from krakbus.config import load_config
from krakbus.logger import setup_logging
from krakbus.viz.geo import ORIGIN_LAT, ORIGIN_LON, to_xz
from krakbus.viz.polyline import cut_polyline, project_stops, simplify

SCHEMA_VERSION = 1
MAX_STOP_DIST_M = 100.0
SIMPLIFY_TOL_M = 2.0
GTFS_COLUMNS = {
    "stops": {"stop_id", "stop_name", "stop_lat", "stop_lon"},
    "trips": {"trip_id", "route_id", "shape_id"},
    "stop_times": {"trip_id", "stop_id", "stop_sequence"},
    "shapes": {"shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"},
}
log = logging.getLogger(__name__)


def read_gtfs(zip_path: Path) -> dict[str, pd.DataFrame]:
    """Wczytuje potrzebne pliki GTFS z ZIP-a (tylko wymagane kolumny, wszystko jako `str`).

    Args:
        zip_path: Sciezka do archiwum GTFS.

    Returns:
        Slownik `stops`, `trips`, `stop_times`, `shapes` -> ramki.

    Raises:
        ValueError: Gdy w archiwum brakuje ktoregos z plikow (komunikat zawiera jego nazwe).
    """
    out: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        for key, cols in GTFS_COLUMNS.items():
            fname = f"{key}.txt"
            if fname not in names:
                raise ValueError(f"brak pliku {fname} w {zip_path}")
            with z.open(fname) as f:
                out[key] = pd.read_csv(
                    f,
                    dtype=str,
                    usecols=lambda c, cols=cols: c in cols,
                    encoding="utf-8-sig",
                )
    return out


def _patterns(gtfs: dict[str, pd.DataFrame], routes: list[str] | None) -> pd.DataFrame:
    """Unikalne wzorce (route_id, shape_id, krotka przystankow) wybranych linii."""
    trips = gtfs["trips"]
    if "shape_id" not in trips.columns:
        trips = trips.assign(shape_id=None)
    if routes is not None:
        trips = trips[trips["route_id"].isin(routes)]
    if trips.empty:
        raise ValueError(f"brak kursow dla linii {routes}")
    st = gtfs["stop_times"]
    st = st[st["trip_id"].isin(trips["trip_id"])].copy()
    st["seq"] = st["stop_sequence"].astype(int)
    st = st.sort_values(["trip_id", "seq"], kind="stable")
    pat = (
        st.groupby("trip_id", sort=False)["stop_id"]
        .agg(tuple)
        .rename("stops")
        .reset_index()
    )
    pat = pat.merge(trips[["trip_id", "route_id", "shape_id"]], on="trip_id")
    pat["shape_id"] = pat["shape_id"].fillna("")
    pat = pat.drop_duplicates(["route_id", "shape_id", "stops"])
    return pat.sort_values(["route_id", "shape_id"], kind="stable").reset_index(
        drop=True
    )


def _shape_lines(shapes: pd.DataFrame, ids: set[str]) -> dict[str, np.ndarray]:
    """Lamane (n, 2) w metrach dla podanych `shape_id`, punkty wg numerycznej sekwencji."""
    sh = shapes[shapes["shape_id"].isin(ids)].copy()
    sh["seq"] = sh["shape_pt_sequence"].astype(int)
    sh = sh.sort_values(["shape_id", "seq"], kind="stable")
    x, z = to_xz(sh["shape_pt_lat"].astype(float), sh["shape_pt_lon"].astype(float))
    xz = np.column_stack([x, z])
    return {
        str(sid): xz[idx]
        for sid, idx in sh.groupby("shape_id", sort=False).indices.items()
    }


def build_network(gtfs: dict[str, pd.DataFrame], routes: list[str] | None) -> dict:
    """Buduje graf sieci: przystanki i skierowane odcinki z lamanymi z `shapes.txt`.

    Odcinek (przystanek -> nastepny) dostaje geometrie z pierwszego wzorca, w ktorym
    wystepuje; linie, ktore go uzywaja, sa scalane. Prosta zamiast ksztaltu: wzorzec
    bez ksztaltu (`no_shape`) albo przystanek dalej niz `MAX_STOP_DIST_M` od lamanej
    (`far_stop`, dotyczy obu sasiednich odcinkow).

    Args:
        gtfs: Wynik `read_gtfs`.
        routes: Linie do eksportu; None = wszystkie.

    Returns:
        Slownik `meta`, `stops`, `segments` (kontrakt `network.json`).

    Raises:
        ValueError: Gdy dla `routes` nie ma zadnych kursow.
    """
    pat = _patterns(gtfs, routes)
    stops_df = gtfs["stops"].drop_duplicates("stop_id").set_index("stop_id")
    sx, sz = to_xz(
        stops_df["stop_lat"].astype(float), stops_df["stop_lon"].astype(float)
    )
    xz_of = dict(zip(stops_df.index, np.column_stack([sx, sz]), strict=True))
    lines = _shape_lines(gtfs["shapes"], {s for s in pat["shape_id"] if s})
    segs: dict[tuple[str, str], dict] = {}

    def add(
        a: str, b: str, route: str, pts: np.ndarray | None, reason: str | None
    ) -> None:
        seg = segs.get((a, b))
        if seg is not None:
            seg["routes"].add(route)
            return
        pts = (
            np.vstack([xz_of[a], xz_of[b]])
            if pts is None
            else simplify(pts, SIMPLIFY_TOL_M)
        )
        segs[(a, b)] = {"routes": {route}, "points": pts, "reason": reason}
        if reason:
            log.warning("odcinek %s -> %s (linia %s) prosty: %s", a, b, route, reason)

    for route, shape_id, all_ids in pat[["route_id", "shape_id", "stops"]].itertuples(
        index=False
    ):
        ids = [s for s in all_ids if s in xz_of]
        if len(ids) < 2:
            continue
        pairs = list(itertools.pairwise(ids))
        line = lines.get(shape_id)
        if line is None or len(line) < 2:
            for a, b in pairs:
                add(a, b, route, None, "no_shape")
            continue
        s, dist = project_stops(line, np.array([xz_of[i] for i in ids]))
        far = dist > MAX_STOP_DIST_M
        for i, (a, b) in enumerate(pairs):
            if far[i] or far[i + 1]:
                add(a, b, route, None, "far_stop")
            else:
                add(a, b, route, cut_polyline(line, s[i], s[i + 1]), None)

    segments = [
        {
            "from_stop": a,
            "to_stop": b,
            "routes": sorted(v["routes"]),
            "points": [float(c) for c in np.round(v["points"], 1).ravel()],
        }
        for (a, b), v in sorted(segs.items())
    ]
    used = sorted({i for k in segs for i in k})
    stops = [
        {
            "stop_id": i,
            "name": str(stops_df.at[i, "stop_name"]) if "stop_name" in stops_df else "",
            "x": float(np.round(xz_of[i][0], 1)),
            "z": float(np.round(xz_of[i][1], 1)),
        }
        for i in used
    ]
    n_straight = {"no_shape": 0, "far_stop": 0}
    for v in segs.values():
        if v["reason"]:
            n_straight[v["reason"]] += 1
    xs, zs = [s["x"] for s in stops], [s["z"] for s in stops]
    meta = {
        "schema_version": SCHEMA_VERSION,
        "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON, "axes": "x=east m, z=north m"},
        "routes": sorted(set(pat["route_id"])),
        "n_stops": len(stops),
        "n_segments": len(segments),
        "n_straight": n_straight,
        "bbox": {
            "x_min": min(xs, default=0.0),
            "x_max": max(xs, default=0.0),
            "z_min": min(zs, default=0.0),
            "z_max": max(zs, default=0.0),
        },
    }
    return {"meta": meta, "stops": stops, "segments": segments}


def write_network(net: dict, out_dir: Path) -> Path:
    """Zapisuje `network.json` (UTF-8, bez BOM) w `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "network.json"
    path.write_text(
        json.dumps(net, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return path


def main() -> None:
    """Punkt wejscia `uv run export-network`."""
    parser = argparse.ArgumentParser(
        description="Eksport grafu sieci dla Unity (kontrakt v1)"
    )
    parser.add_argument(
        "--positions", type=Path, help="meta pliku pozycji (gtfs i routes)"
    )
    parser.add_argument("--gtfs", type=Path, help="sciezka do ZIP-a GTFS")
    parser.add_argument(
        "--routes", nargs="*", help="linie; domyslnie z --positions albo wszystkie"
    )
    parser.add_argument(
        "--out", type=Path, help="katalog; domyslnie data/processed/unity_samples"
    )
    args = parser.parse_args()
    if not args.positions and not args.gtfs:
        parser.error("podaj --positions albo --gtfs")
    setup_logging()
    cfg = load_config()
    gtfs_path, routes = args.gtfs, None
    if args.positions:
        meta = json.loads(args.positions.read_text(encoding="utf-8"))
        routes = [str(r) for r in meta.get("routes") or []] or None
        if gtfs_path is None:
            gtfs_path = cfg.data.raw_dir / "static" / meta["gtfs"]
    if args.routes:
        routes = [str(r) for r in args.routes]
    net = build_network(read_gtfs(gtfs_path), routes)
    path = write_network(net, args.out or cfg.data.processed_dir / "unity_samples")
    m = net["meta"]
    log.info(
        "%d przystankow, %d odcinkow, proste: %s, %.1f MB -> %s",
        m["n_stops"],
        m["n_segments"],
        m["n_straight"],
        path.stat().st_size / 1e6,
        path,
    )


if __name__ == "__main__":
    main()
