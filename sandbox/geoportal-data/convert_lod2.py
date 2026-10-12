#!/usr/bin/env python3
"""Konwersja CityGML 2.0 LoD2 (GUGiK, EPSG:2180) do GLB (glTF) dla Unity.

Kazdy budynek jest osobnym wezlem w scenie o nazwie = buildingId.
Obok powstaje plik .json z poczatkiem ukladu (EPSG:2180 oraz lon/lat) i listą budynków.

Os: wschod -> +X, gora -> +Y, polnoc -> -Z (konwencja glTF, prawoskretna).
Unity po imporcie odwraca os Z, wiec budynki lada na swoich miejscach.

Przyklady:
  python convert_lod2.py gml_dir out.glb
  python convert_lod2.py gml_dir out.glb --shapes gtfs/shapes.txt --shape-id 179_1 --buffer 250
"""

import argparse
import csv
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

import mapbox_earcut as earcut
import numpy as np
import trimesh
from pyproj import Transformer
from shapely.geometry import Polygon

NS = {
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "gml": "http://www.opengis.net/gml",
    "gen": "http://www.opengis.net/citygml/generics/2.0",
}
SURFACES = (
    "GroundSurface",
    "WallSurface",
    "RoofSurface",
    "OuterCeilingSurface",
    "OuterFloorSurface",
    "ClosureSurface",
)

TO_WGS = Transformer.from_crs(2180, 4326, always_xy=True)
TO_PL = Transformer.from_crs(4326, 2180, always_xy=True)


def ring_points(ring):
    pos = ring.findall("gml:pos", NS)
    if pos:
        return [tuple(float(v) for v in p.text.split()[:3]) for p in pos]
    pl = ring.find("gml:posList", NS)
    if pl is not None:
        vals = [float(v) for v in pl.text.split()]
        return [tuple(vals[i : i + 3]) for i in range(0, len(vals) - 2, 3)]
    return []


def triangulate(points):
    """Triangulacja wielokata 3D przez rzut wzdluz dominujacej osi normalnej (earcut)."""
    pts = np.array(points[:-1] if points[0] == points[-1] else points, dtype=float)
    if len(pts) < 3:
        return None, None
    n = np.zeros(3)
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    if np.linalg.norm(n) < 1e-9:
        return None, None
    drop = int(np.argmax(np.abs(n)))
    keep = [i for i in range(3) if i != drop]
    p2 = pts[:, keep]
    tri = earcut.triangulate_float64(p2, np.array([len(p2)], dtype=np.uint32)).reshape(
        -1, 3
    )
    # zachowaj orientacje zgodna z normalna wielokata
    out = []
    for t in tri:
        a, b, c = pts[t[0]], pts[t[1]], pts[t[2]]
        if np.dot(np.cross(b - a, c - a), n) < 0:
            t = t[::-1]
        out.append(t)
    return pts, np.array(out, dtype=np.int64)


def read_buildings(path):
    root = ET.parse(path).getroot()
    for b in root.iterfind(".//bldg:Building", NS):
        bid = None
        for attr in b.iterfind("gen:stringAttribute", NS):
            if attr.get("name") == "buildingId":
                bid = attr.find("gen:value", NS).text
        bid = bid or b.get("{%s}id" % NS["gml"])
        polys = []
        for tag in SURFACES:
            for s in b.iterfind(".//bldg:%s" % tag, NS):
                for poly in s.iterfind(".//gml:Polygon", NS):
                    ring = poly.find("gml:exterior/gml:LinearRing", NS)
                    if ring is None:
                        continue
                    pts = ring_points(ring)
                    if len(pts) >= 4:
                        polys.append((tag, pts))
        if polys:
            yield bid, polys


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
        lines.append(LineString([TO_PL.transform(lon, lat) for _, lon, lat in pts]))
    return unary_union([ln.buffer(buffer_m) for ln in lines])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="plik .gml albo folder z plikami .gml")
    ap.add_argument("output", help="wyjsciowy plik .glb")
    ap.add_argument("--shapes")
    ap.add_argument("--shape-id", action="append")
    ap.add_argument("--buffer", type=float, default=250.0)
    args = ap.parse_args()

    files = (
        sorted(glob.glob(os.path.join(args.input, "**", "*.gml"), recursive=True))
        if os.path.isdir(args.input)
        else [args.input]
    )
    if not files:
        sys.exit("Nie znaleziono plikow .gml")
    area = (
        load_route_buffer(args.shapes, set(args.shape_id or []), args.buffer)
        if args.shapes
        else None
    )

    buildings, seen = [], set()
    for path in files:
        for bid, polys in read_buildings(path):
            if bid in seen:
                continue
            if area is not None:
                ground = [p for t, p in polys if t == "GroundSurface"] or [
                    p for _, p in polys
                ]
                fp = Polygon([(x, y) for x, y, _ in ground[0]])
                if not fp.is_valid or not fp.intersects(area):
                    continue
            seen.add(bid)
            buildings.append((bid, polys))
    if not buildings:
        sys.exit("Zadne budynki nie spelniaja warunkow")

    allp = np.array([p for _, polys in buildings for _, pts in polys for p in pts])
    ox, oy = (
        (allp[:, 0].min() + allp[:, 0].max()) / 2,
        (allp[:, 1].min() + allp[:, 1].max()) / 2,
    )
    oz = allp[:, 2].min()

    scene = trimesh.Scene()
    meta = []
    for bid, polys in buildings:
        verts, faces, off = [], [], 0
        for _, pts in polys:
            p, t = triangulate(pts)
            if p is None or len(t) == 0:
                continue
            verts.append(p)
            faces.append(t + off)
            off += len(p)
        if not verts:
            continue
        v = np.vstack(verts)
        local = np.column_stack([v[:, 0] - ox, v[:, 2] - oz, -(v[:, 1] - oy)])
        mesh = trimesh.Trimesh(vertices=local, faces=np.vstack(faces), process=False)
        scene.add_geometry(mesh, node_name=bid, geom_name=bid)
        meta.append({"id": bid, "triangles": int(len(mesh.faces))})

    scene.export(args.output)
    lon, lat = TO_WGS.transform(ox, oy)
    with open(os.path.splitext(args.output)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "origin_epsg2180": [ox, oy, oz],
                "origin_lonlat": [lon, lat],
                "axes": "east=+X, up=+Y, north=-Z (glTF)",
                "buildings": meta,
            },
            f,
            indent=1,
        )
    print(
        f"Zapisano {len(meta)} budynkow do {args.output}; poczatek: lon={lon:.6f} lat={lat:.6f}"
    )


if __name__ == "__main__":
    main()
