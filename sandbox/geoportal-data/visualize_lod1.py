"""Wczytuje budynki CityGML LoD1 (GUGiK) i buduje przegladarkowy podglad 3D (deck.gl).

Powstaje folder z plikami: index.html, style.css, app.js, data.js.
Otworz index.html w przegladarce (potrzebny internet: biblioteka deck.gl i kafelki mapy),
albo uzyj --serve, ktore uruchamia lokalny serwer na http://localhost:8000.

Przyklady:
  python visualize_lod1.py gml_dir viewer
  python visualize_lod1.py gml_dir viewer --shapes shapes.txt --shape-id 179_1 --shape-id 179_2 --buffer 300
  python visualize_lod1.py gml_dir viewer --bbox 19.90 50.04 19.99 50.09 --serve
"""
import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

from convert_gml import TO_PL, TO_WGS, load_route_buffer, read_buildings
from shapely.geometry import Polygon, box
from shapely.validation import make_valid

STYLE_CSS = """html, body {
  margin: 0;
  height: 100%;
  background: #0e1116;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #e6edf3;
}

#map {
  position: absolute;
  inset: 0;
}

.panel {
  position: absolute;
  left: 16px;
  top: 16px;
  max-width: 280px;
  padding: 12px 14px;
  background: rgba(14, 17, 22, 0.88);
  border: 1px solid #2d333b;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.45;
}

.panel h1 {
  margin: 0 0 6px;
  font-size: 15px;
}

.panel .muted {
  color: #8b949e;
}

.field {
  display: block;
  margin-top: 10px;
  font-size: 12px;
  color: #8b949e;
}

.field select {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 5px 6px;
  background: #161b22;
  color: #e6edf3;
  border: 1px solid #2d333b;
  border-radius: 6px;
  font-size: 13px;
}

.ramp {
  height: 10px;
  margin: 10px 0 2px;
  border-radius: 3px;
  background: linear-gradient(90deg, #2c7bb6, #abd9e9, #ffffbf, #fdae61, #d7191c);
}

.ramp-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #8b949e;
}

.attribution {
  position: absolute;
  right: 8px;
  bottom: 6px;
  max-width: 60%;
  font-size: 11px;
  color: #8b949e;
  background: rgba(14, 17, 22, 0.7);
  padding: 2px 6px;
  border-radius: 4px;
}

.tooltip-box {
  font-size: 12px;
  line-height: 1.4;
}
"""

INDEX_HTML = """<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Budynki LoD1 - podglad</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="map"></div>
  <div class="panel">
    <h1>Budynki LoD1</h1>
    <div id="stats" class="muted"></div>
    <label class="field">Mapa podkladowa
      <select id="basemap"></select>
    </label>
    <div class="ramp"></div>
    <div class="ramp-labels"><span id="hmin"></span><span>wysokosc budynku [m]</span><span id="hmax"></span></div>
    <div class="muted" style="margin-top:8px">Przeciagnij: przesuwanie. Prawy przycisk lub Ctrl: obrot i nachylenie. Kolko: zoom.</div>
  </div>
  <div class="attribution" id="attribution"></div>
  <script src="https://unpkg.com/deck.gl@^9.0.0/dist.min.js"></script>
  <script src="data.js"></script>
  <script src="app.js"></script>
</body>
</html>
"""

APP_JS = """const data = window.VIEWER_DATA;
const buildings = data.buildings;
const route = data.route;

const hmin = 3;
const hmax = Math.max(hmin + 1, data.height_p95);
document.getElementById("hmin").textContent = hmin + " m";
document.getElementById("hmax").textContent = hmax.toFixed(0) + " m+";
const shown = buildings.features.length.toLocaleString("pl-PL");
const total = data.stats.total_in_files.toLocaleString("pl-PL");
document.getElementById("stats").textContent =
  shown + " z " + total + " budynkow w plikach" +
  (data.filter ? " (filtr: " + data.filter + ")" : "") +
  (route ? ", bufor trasy " + data.buffer_m + " m" : "");

const basemaps = {
  esri_dark: {
    label: "Esri - ciemna mapa",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    maxZoom: 16,
    attr: "Mapa: Esri, HERE, Garmin, OpenStreetMap contributors"
  },
  esri_light: {
    label: "Esri - jasna mapa",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    maxZoom: 16,
    attr: "Mapa: Esri, HERE, Garmin, OpenStreetMap contributors"
  },
  esri_sat: {
    label: "Esri - satelita",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    maxZoom: 19,
    attr: "Zdjecia: Esri, Maxar, Earthstar Geographics"
  },
  osm: {
    label: "OpenStreetMap (wymaga --serve)",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    maxZoom: 19,
    attr: "Mapa: OpenStreetMap contributors"
  },
  none: {
    label: "Bez mapy",
    url: null,
    attr: ""
  }
};

let currentKey = "esri_dark";

const stopsColors = [
  [44, 123, 182], [171, 217, 233], [255, 255, 191], [253, 174, 97], [215, 25, 28]
];

function heightColor(h) {
  const t = Math.min(1, Math.max(0, (h - hmin) / (hmax - hmin)));
  const x = t * (stopsColors.length - 1);
  const i = Math.min(stopsColors.length - 2, Math.floor(x));
  const f = x - i;
  const a = stopsColors[i];
  const b = stopsColors[i + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * f),
    Math.round(a[1] + (b[1] - a[1]) * f),
    Math.round(a[2] + (b[2] - a[2]) * f),
    235
  ];
}

function makeBasemap(key) {
  const src = basemaps[key];
  if (!src.url) {
    return null;
  }
  return new deck.TileLayer({
    id: "basemap-" + key,
    data: src.url,
    minZoom: 0,
    maxZoom: src.maxZoom,
    tileSize: 256,
    renderSubLayers: props => {
      const { west, south, east, north } = props.tile.bbox;
      return new deck.BitmapLayer(props, {
        data: null,
        image: props.data,
        bounds: [west, south, east, north]
      });
    }
  });
}

const overlays = [
  new deck.GeoJsonLayer({
    id: "buildings",
    data: buildings,
    extruded: true,
    wireframe: false,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 120],
    getElevation: f => f.properties.height,
    getFillColor: f => heightColor(f.properties.height),
    material: { ambient: 0.45, diffuse: 0.6, shininess: 24, specularColor: [60, 64, 70] }
  })
];

if (route) {
  overlays.push(new deck.PathLayer({
    id: "route",
    data: route,
    getPath: d => d.path,
    getColor: [255, 255, 255, 255],
    getWidth: 4,
    widthUnits: "meters",
    widthMinPixels: 3,
    parameters: { depthTest: false }
  }));
}

function allLayers(key) {
  return [makeBasemap(key), ...overlays].filter(Boolean);
}

function setAttribution(key) {
  const attr = basemaps[key].attr;
  document.getElementById("attribution").textContent =
    "Dane: GUGiK (modele 3D budynkow)" + (attr ? ". " + attr : "");
}

const view = new deck.Deck({
  parent: document.getElementById("map"),
  initialViewState: {
    longitude: data.center[0],
    latitude: data.center[1],
    zoom: data.zoom,
    pitch: 55,
    bearing: -20,
    maxPitch: 80
  },
  controller: true,
  layers: allLayers(currentKey),
  getTooltip: ({ object }) => object && object.properties && {
    className: "tooltip-box",
    html: "<div>Wysokosc: <b>" + object.properties.height.toFixed(1) + " m</b></div>" +
          "<div style='opacity:.7'>" + object.properties.id + "</div>",
    style: { backgroundColor: "rgba(14,17,22,0.92)", color: "#e6edf3", border: "1px solid #2d333b" }
  }
});

const select = document.getElementById("basemap");
Object.keys(basemaps).forEach(key => {
  const opt = document.createElement("option");
  opt.value = key;
  opt.textContent = basemaps[key].label;
  select.appendChild(opt);
});
select.value = currentKey;
setAttribution(currentKey);
select.addEventListener("change", () => {
  currentKey = select.value;
  view.setProps({ layers: allLayers(currentKey) });
  setAttribution(currentKey);
});
"""


def find_gml(root):
    if not os.path.isdir(root):
        return [root]
    found = []
    for folder, _, names in os.walk(root):
        for name in names:
            if name.lower().endswith(".gml") and not name.startswith("."):
                found.append(os.path.join(folder, name))
    return sorted(found)


def read_file(path):
    stats = {}
    try:
        return list(read_buildings(path, stats)), stats, None
    except Exception as exc:
        return [], stats, f"{path}: {exc}"


def serve(folder, port=8000):
    import functools
    import http.server
    import webbrowser

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=folder)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}"
    print(f"Serwer: {url} (Ctrl+C konczy)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="plik .gml albo folder z plikami .gml (LoD1)")
    ap.add_argument("output", help="folder wyjsciowy podgladu")
    ap.add_argument("--shapes", help="GTFS shapes.txt, przycina do bufora wokol trasy")
    ap.add_argument("--shape-id", action="append")
    ap.add_argument("--buffer", type=float, default=250.0, help="bufor wokol trasy [m]")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    ap.add_argument("--max", type=int, default=150000, help="limit liczby budynkow w podgladzie")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--serve", action="store_true", help="uruchom lokalny serwer i otworz przegladarke")
    args = ap.parse_args()

    files = find_gml(args.input)
    if not files:
        sys.exit("Nie znaleziono plikow .gml")

    area = None
    route_paths = None
    if args.shapes:
        import csv

        area = load_route_buffer(args.shapes, set(args.shape_id or []), args.buffer)
        by_shape = {}
        with open(args.shapes, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if args.shape_id and row["shape_id"] not in set(args.shape_id):
                    continue
                by_shape.setdefault(row["shape_id"], []).append(
                    (int(row["shape_pt_sequence"]), float(row["shape_pt_lon"]), float(row["shape_pt_lat"]))
                )
        route_paths = [
            {"id": sid, "path": [[lon, lat] for _, lon, lat in sorted(pts)]} for sid, pts in by_shape.items()
        ]
    if args.bbox:
        x0, y0 = TO_PL.transform(args.bbox[0], args.bbox[1])
        x1, y1 = TO_PL.transform(args.bbox[2], args.bbox[3])
        bb = box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        area = bb if area is None else area.intersection(bb)

    print(f"Czytam {len(files)} plikow ({args.workers} procesow)...", file=sys.stderr)
    seen, features, heights = set(), [], []
    totals = {"buildings_in_files": 0, "no_footprint": 0, "duplicates": 0, "repaired": 0, "outside_filter": 0}
    failed = []
    with Pool(args.workers) as pool:
        for n, (result, st, err) in enumerate(pool.imap_unordered(read_file, files, chunksize=4), 1):
            if err:
                failed.append(err)
            totals["buildings_in_files"] += st.get("buildings_in_files", 0)
            totals["no_footprint"] += st.get("no_footprint", 0)
            for bid, ring, zmin, height in result:
                if bid in seen:
                    totals["duplicates"] += 1
                    continue
                seen.add(bid)
                if area is not None:
                    poly = Polygon(ring)
                    if not poly.is_valid:
                        poly = make_valid(poly)
                        totals["repaired"] += 1
                    if not poly.intersects(area):
                        totals["outside_filter"] += 1
                        continue
                lon, lat = TO_WGS.transform([p[0] for p in ring], [p[1] for p in ring])
                features.append(
                    {
                        "type": "Feature",
                        "properties": {"id": bid, "height": round(height, 2)},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[round(x, 6), round(y, 6)] for x, y in zip(lon, lat)]],
                        },
                    }
                )
                heights.append(height)
            if n % 100 == 0:
                print(f"  {n}/{len(files)} plikow, {len(features)} budynkow", file=sys.stderr)

    unique = totals["buildings_in_files"] - totals["duplicates"]
    flt = " + ".join(x for x in ("bufor trasy" if args.shapes else None, "bbox" if args.bbox else None) if x) or None
    print("Podsumowanie wczytywania:")
    print(f"  plikow .gml: {len(files)}, z bledem odczytu: {len(failed)}")
    for msg in failed[:5]:
        print(f"    {msg}")
    print(f"  budynkow w plikach (z duplikatami): {totals['buildings_in_files']}")
    print(f"  duplikaty miedzy plikami: {totals['duplicates']}")
    print(f"  unikalnych budynkow w plikach: {unique}")
    print(f"  pominiete bez obrysu podstawy: {totals['no_footprint']}")
    print(f"  poza filtrem ({flt or 'brak filtra'}): {totals['outside_filter']}")
    print(f"  naprawione nieprawidlowe geometrie: {totals['repaired']}")
    print(f"  pasuje do podgladu: {len(features)}")
    if not features:
        sys.exit("Brak budynkow po filtrowaniu. Sprawdz bbox, shape_id i czy pliki obejmuja te okolice.")
    if len(features) > args.max:
        step = len(features) / args.max
        features = [features[int(i * step)] for i in range(args.max)]
        print(f"Uwaga: ograniczono do {args.max} budynkow (zwieksz --max lub zawez obszar).", file=sys.stderr)

    heights.sort()
    p95 = heights[int(0.95 * (len(heights) - 1))]
    lons = [c[0] for f in features for c in f["geometry"]["coordinates"][0]]
    lats = [c[1] for f in features for c in f["geometry"]["coordinates"][0]]
    center = [(min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2]
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 1.6, 1e-4)
    zoom = max(8.0, min(18.0, math.log2(360 / span) - 1.2))

    payload = {
        "buildings": {"type": "FeatureCollection", "features": features},
        "route": route_paths,
        "center": center,
        "zoom": zoom,
        "height_p95": round(p95, 1),
        "buffer_m": args.buffer if args.shapes else None,
        "stats": {"total_in_files": unique},
        "filter": flt,
    }

    os.makedirs(args.output, exist_ok=True)
    with open(os.path.join(args.output, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.VIEWER_DATA = ")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";\n")
    for name, text in (("index.html", INDEX_HTML), ("style.css", STYLE_CSS), ("app.js", APP_JS)):
        with open(os.path.join(args.output, name), "w", encoding="utf-8") as f:
            f.write(text)
    size_mb = os.path.getsize(os.path.join(args.output, "data.js")) / 1e6
    print(f"Gotowe: {len(features)} budynkow, data.js {size_mb:.1f} MB. Otworz {args.output}/index.html")
    if args.serve:
        serve(args.output)


if __name__ == "__main__":
    main()