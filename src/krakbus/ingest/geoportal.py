"""Pobieranie NMT i ortofotomapy z WCS Geoportalu do lokalnych GeoTIFF-ow.

Obszar i georeferencja: EPSG:2180, kolejnosc x=easting, y=northing.
NMT jest pobierany jako wysokosci (AAIGrid), a nie obraz cieniowania WMS.
"""

import argparse
import hashlib
import importlib.util
import json
import logging
import math
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import IncompleteRead
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import yaml

from krakbus.config import DEFAULT_CONFIG, ROOT
from krakbus.logger import setup_logging

log = logging.getLogger(__name__)
CRS = "EPSG:2180"
Bbox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Settings:
    output_dir: Path
    tile_size_m: float
    max_tiles: int
    max_tile_pixels: int
    max_response_bytes: int
    timeout_s: float
    attempts: int
    retry_delay_s: float
    layers: dict


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    """Wczytuje progi i definicje uslug; sciezki wzgledne od korzenia repo."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["geoportal"]
    return Settings(**(raw | {"output_dir": ROOT / raw["output_dir"]}))


def plan_tiles(
    bbox: Bbox, tile_size_m: float, grid_m: float, max_tiles: int
) -> list[Bbox]:
    """Wyrownuje bbox na zewnatrz do siatki i dzieli bez nakladania kafelkow."""
    if len(bbox) != 4 or not all(math.isfinite(x) for x in bbox):
        raise ValueError("bbox musi zawierac cztery skonczone liczby")
    x0, y0, x1, y1 = bbox
    if x0 >= x1 or y0 >= y1:
        raise ValueError("bbox wymaga xmin < xmax i ymin < ymax")
    if not math.isfinite(grid_m) or grid_m <= 0:
        raise ValueError("rozdzielczosc musi byc dodatnia i skonczona")
    if (
        not math.isfinite(tile_size_m)
        or tile_size_m <= 0
        or not math.isclose(tile_size_m / grid_m, round(tile_size_m / grid_m))
    ):
        raise ValueError("rozmiar kafelka musi byc dodatnia wielokrotnoscia siatki")
    x0, y0 = math.floor(x0 / grid_m) * grid_m, math.floor(y0 / grid_m) * grid_m
    x1, y1 = math.ceil(x1 / grid_m) * grid_m, math.ceil(y1 / grid_m) * grid_m
    nx, ny = math.ceil((x1 - x0) / tile_size_m), math.ceil((y1 - y0) / tile_size_m)
    if nx * ny > max_tiles:
        raise ValueError(f"obszar wymaga {nx * ny} kafelkow; limit to {max_tiles}")
    return [
        (
            x0 + i * tile_size_m,
            y0 + j * tile_size_m,
            min(x1, x0 + (i + 1) * tile_size_m),
            min(y1, y0 + (j + 1) * tile_size_m),
        )
        for j in range(ny)
        for i in range(nx)
    ]


def _sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _download(url: str, path: Path, settings: Settings) -> None:
    import certifi

    # Dodaj CA Mozilli do systemowych; nie wylaczaj weryfikacji HTTPS.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    request = Request(url, headers={"User-Agent": "krakbus-geoportal/0.1"})
    with (
        urlopen(request, timeout=settings.timeout_s, context=context) as response,
        path.open("wb") as dst,
    ):
        total = 0
        while chunk := response.read(65536):
            total += len(chunk)
            if total > settings.max_response_bytes:
                raise ValueError("odpowiedz przekracza max_response_bytes")
            dst.write(chunk)
    if total == 0:
        raise ValueError("pusta odpowiedz serwera")


def _convert(
    raw: Path, target: Path, bbox: Bbox, width: int, height: int, layer: str
) -> dict:
    import rasterio

    with rasterio.open(raw) as src:
        if (src.width, src.height) != (width, height):
            raise ValueError("niezgodny rozmiar rastra")
        if not np.allclose(src.bounds, bbox, rtol=0, atol=1e-5):
            raise ValueError("niezgodny bbox rastra")
        if src.crs is not None and src.crs.to_epsg() != 2180:
            raise ValueError("niezgodny uklad wspolrzednych")
        # AAIGrid NMT nie ma CRS w naglowku: pochodzi z jawnego RESPONSE_CRS.
        if src.crs is None and (layer != "nmt" or src.driver != "AAIGrid"):
            raise ValueError("brak ukladu wspolrzednych w GeoTIFF")
        if (layer == "nmt" and src.count != 1) or (layer == "ortho" and src.count < 3):
            raise ValueError("niezgodna liczba kanalow")
        data = src.read(masked=True)
        valid = data.compressed()
        if not valid.size or not np.isfinite(valid).all():
            raise ValueError("brak poprawnych danych lub nieskonczone wartosci")
        # meta zawiera georeferencje bez opcji blokow specyficznych dla zrodla.
        profile = src.meta.copy()
        profile.update(driver="GTiff", crs=CRS, compress="deflate")
        with (
            rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True),
            rasterio.open(target, "w", **profile) as dst,
        ):
            dst.write(src.read())
            # Zachowaj maski np. przy granicy zasiegu ortofotomapy.
            dst.write_mask(src.dataset_mask())
        return {
            "crs": CRS,
            "bounds": list(src.bounds),
            "width": width,
            "height": height,
            "bands": src.count,
            "resolution_m": list(src.res),
            "dtype": src.dtypes[0],
            "valid_percent": round(100 * valid.size / data.size, 3),
            "min": float(valid.min()),
            "max": float(valid.max()),
        }


def _fetch_tile(
    settings: Settings, layer: str, bbox: Bbox, index: int, out: Path, overwrite: bool
) -> Path:
    spec = settings.layers[layer]
    res = spec["resolution_m"]
    width, height = round((bbox[2] - bbox[0]) / res), round((bbox[3] - bbox[1]) / res)
    query = {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": spec["coverage"],
        "CRS": CRS,
        "RESPONSE_CRS": CRS,
        "BBOX": ",".join(f"{v:.15g}" for v in bbox),
        "WIDTH": width,
        "HEIGHT": height,
        "FORMAT": spec["format"],
    }
    url = spec["endpoint"] + "?" + urlencode(query)
    identity = {"url": url, "vertical_crs": spec.get("vertical_crs")}
    target = out / f"{layer}_{index:04d}.tif"
    side = target.with_suffix(".json")
    if not overwrite and (target.exists() or side.exists()):
        try:
            meta = json.loads(side.read_text(encoding="utf-8"))
            if meta["request"] == identity and meta["sha256"] == _sha256(target):
                log.info("cache: %s", target)
                return target
        except OSError, ValueError, KeyError, TypeError:
            pass
        raise ValueError(
            f"niezgodny lub uszkodzony cache {target}; uzyj --overwrite lub innego --out"
        )

    out.mkdir(parents=True, exist_ok=True)
    # Publikuj tylko poprawny plik. Nie nadpisuj poprzedniej wersji przy bledzie serwera.
    with TemporaryDirectory(prefix=".wcs-", dir=out) as work:
        raw, tif, metadata = (Path(work) / n for n in ("raw", "tile.tif", "tile.json"))
        for attempt in range(settings.attempts):
            try:
                _download(url, raw, settings)
                stats = _convert(raw, tif, bbox, width, height, layer)
                break
            except (OSError, ValueError, IncompleteRead) as exc:
                if attempt + 1 == settings.attempts:
                    raise RuntimeError(f"{layer} kafelek {index}: {exc}") from exc
                log.warning(
                    "%s proba %d/%d: %s", layer, attempt + 1, settings.attempts, exc
                )
                time.sleep(settings.retry_delay_s * 2**attempt)
        meta = stats | {
            "schema_version": 1,
            "layer": layer,
            "request": identity,
            "downloaded_at_utc": datetime.now(UTC).isoformat(),
            "sha256": _sha256(tif),
            "bytes": tif.stat().st_size,
        }
        metadata.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        tif.replace(target)
        metadata.replace(side)
    log.info(
        "zapisano %s (%d B, %.1f%% danych)",
        target,
        meta["bytes"],
        meta["valid_percent"],
    )
    return target


def fetch_area(
    settings: Settings,
    bbox: Bbox,
    layers: list[str],
    out: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Pobiera kafelki i metadane; zgodny cache pomija, uszkodzony wymaga --overwrite."""
    if (
        not layers
        or set(layers) - {"nmt", "ortho"}
        or set(layers) - settings.layers.keys()
    ):
        raise ValueError("wybierz warstwy nmt i/lub ortho")
    if (
        settings.attempts < 1
        or settings.timeout_s <= 0
        or settings.retry_delay_s < 0
        or settings.max_response_bytes < 1
    ):
        raise ValueError("niepoprawne limity pobierania w konfiguracji")
    layers = list(dict.fromkeys(layers))
    resolutions = [float(settings.layers[name]["resolution_m"]) for name in layers]
    if any(not math.isfinite(r) or r <= 0 for r in resolutions):
        raise ValueError("rozdzielczosc musi byc dodatnia i skonczona")
    grid = max(resolutions)
    if any(not math.isclose(grid / r, round(grid / r)) for r in resolutions):
        raise ValueError("rozdzielczosci musza miec wspolna siatke")
    tiles = plan_tiles(bbox, settings.tile_size_m, grid, settings.max_tiles)
    for tile in tiles:
        for res in resolutions:
            pixels = round((tile[2] - tile[0]) / res) * round((tile[3] - tile[1]) / res)
            if pixels > settings.max_tile_pixels:
                raise ValueError(
                    "kafelek przekracza max_tile_pixels; zmniejsz tile_size_m"
                )
    log.info(
        "%d kafelkow x %d warstw, bbox %s, katalog %s",
        len(tiles),
        len(layers),
        (tiles[0][0], tiles[0][1], tiles[-1][2], tiles[-1][3]),
        out,
    )
    if dry_run:
        return []
    return [
        _fetch_tile(settings, layer, tile, i, out, overwrite)
        for i, tile in enumerate(tiles)
        for layer in layers
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        required=True,
        metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
        help="EPSG:2180, metry (x=east, y=north)",
    )
    parser.add_argument(
        "--layers", nargs="+", choices=["nmt", "ortho"], default=["nmt", "ortho"]
    )
    parser.add_argument(
        "--out", type=Path, help="katalog obszaru; domyslnie z konfiguracji"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="ponownie pobierz i zastap poprawnym wynikiem",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="sprawdz plan bez pobierania i zapisu"
    )
    args = parser.parse_args()
    setup_logging()
    if not args.dry_run and importlib.util.find_spec("rasterio") is None:
        parser.error(
            "brak rasterio; uruchom: uv run --group geodata fetch-geoportal ..."
        )
    try:
        cfg = load_settings(args.config)
        fetch_area(
            cfg,
            tuple(args.bbox),
            args.layers,
            args.out or cfg.output_dir,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
