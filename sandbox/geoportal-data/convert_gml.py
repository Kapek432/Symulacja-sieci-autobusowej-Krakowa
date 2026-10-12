#!/usr/bin/env python3
"""Konwersja CityGML 2.0 LoD1 (GUGiK, EPSG:2180) do GeoJSON (EPSG:4326) dla deck.gl.

Przyklady:
  python convert_gml.py gml_dir out.geojson
  python convert_gml.py gml_dir out.geojson --shapes gtfs/shapes.txt --shape-id 179_1 --buffer 250
"""

import argparse
import csv
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

from shapely.geometry import Polygon

from pyproj import Transformer

NS = {
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "gen": "http://www.opengis.net/citygml/generics/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
}

TO_WGS = Transformer.from_crs(2180, 4326, always_xy=True)
TO_PL = Transformer.from_crs(4326, 2180, always_xy=True)


def parse_poslist(text):
    vals = [float(v) for v in text.split()]
    return [(vals[i], vals[i + 1], vals[i + 2]) for i in range(0, len(vals) - 2, 3)]


def building_footprint(building):
    """Zwraca (pierscien [(x, y)], z_podstawy, z_dachu) albo None."""
    rings = []
    for pl in building.iterfind(
        ".//gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS
    ):
        pts = parse_poslist(pl.text)
        if len(pts) >= 4:
            rings.append(pts)
    if not rings:
        return None
    zmin = min(p[2] for r in rings for p in r)
    zmax = max(p[2] for r in rings for p in r)
    base = None
    for r in rings:
        zs = [p[2] for p in r]
        if max(zs) - min(zs) < 1e-6 and abs(zs[0] - zmin) < 1e-6:
            base = r
            break
    if base is None:
        return None
    return [(p[0], p[1]) for p in base], zmin, zmax


def read_buildings(path, stats=None):
    tree = ET.parse(path)
    for b in tree.getroot().iterfind(".//bldg:Building", NS):
        if stats is not None:
            stats["buildings_in_files"] = stats.get("buildings_in_files", 0) + 1
        fp = building_footprint(b)
        if fp is None:
            if stats is not None:
                stats["no_footprint"] = stats.get("no_footprint", 0) + 1
            continue
        ring, zmin, zmax = fp
        height = None
        mh = b.find("bldg:measuredHeight", NS)
        if mh is not None and mh.text:
            height = float(mh.text)
        if height is None:
            height = round(zmax - zmin, 2)
        bid = None
        for attr in b.iterfind("gen:stringAttribute", NS):
            if attr.get("name") == "buildingId":
                bid = attr.find("gen:value", NS).text
        yield bid or b.get("{%s}id" % NS["gml"]), ring, zmin, height


def load_route_buffer(shapes_path, shape_ids, buffer_m):
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    by_shape = {}
    with open(shapes_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if shape_ids and row["shape_id"] not in shape_ids:
                continue
            by_shape.setdefault(row["shape_id"], []).append(
                (
                    int(row["shape_pt_sequence"]),
                    float(row["shape_pt_lon"]),
                    float(row["shape_pt_lat"]),
                )
            )
    if not by_shape:
        sys.exit("Brak pasujacych shape_id w shapes.txt")
    lines = []
    for pts in by_shape.values():
        pts.sort()
        xy = [TO_PL.transform(lon, lat) for _, lon, lat in pts]
        lines.append(LineString(xy))
    return unary_union([ln.buffer(buffer_m) for ln in lines])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="plik .gml albo folder z plikami .gml")
    ap.add_argument("output", help="wyjsciowy plik .geojson")
    ap.add_argument("--shapes", help="GTFS shapes.txt, do przyciecia do trasy")
    ap.add_argument(
        "--shape-id", action="append", help="shape_id do uzycia (mozna powtarzac)"
    )
    ap.add_argument(
        "--buffer", type=float, default=250.0, help="bufor wokol trasy w metrach"
    )
    args = ap.parse_args()

    if os.path.isdir(args.input):
        files = sorted(
            glob.glob(os.path.join(args.input, "**", "*.gml"), recursive=True)
        )
    else:
        files = [args.input]
    if not files:
        sys.exit("Nie znaleziono plikow .gml")

    area = None
    if args.shapes:
        area = load_route_buffer(args.shapes, set(args.shape_id or []), args.buffer)

    features, seen = [], set()
    for i, path in enumerate(files, 1):
        for bid, ring, zmin, height in read_buildings(path):
            if bid in seen:
                continue
            if area is not None:
                poly = Polygon(ring)
                if not poly.is_valid or not poly.intersects(area):
                    continue
            seen.add(bid)
            lon, lat = TO_WGS.transform([p[0] for p in ring], [p[1] for p in ring])
            coords = [[round(x, 7), round(y, 7)] for x, y in zip(lon, lat)]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": bid,
                        "height": height,
                        "base_z": round(zmin, 2),
                    },
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }
            )
        if i % 200 == 0:
            print(f"{i}/{len(files)} plikow, {len(features)} budynkow", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    print(f"Zapisano {len(features)} budynkow z {len(files)} plikow do {args.output}")


if __name__ == "__main__":
    main()
