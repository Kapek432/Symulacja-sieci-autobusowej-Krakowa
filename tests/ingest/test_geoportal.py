"""Pobieranie WCS: dane, georeferencja, bledy serwera i wznowienie."""

import io
import json
import ssl
from dataclasses import replace
from http.client import IncompleteRead
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio", reason="uv run --group geodata pytest")
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

from krakbus.ingest import geoportal as gp

BBOX = (566967, 244147, 566971, 244151)


@pytest.fixture
def settings():
    return replace(gp.load_settings(), retry_delay_s=0)


def ascii_grid():
    return (
        "ncols 4\nnrows 4\nxllcorner 566967\nyllcorner 244147\n"
        "cellsize 1\nNODATA_value -9999\n" + "209 210 211 212\n" * 4
    ).encode()


def rgb_tiff(*, bounds=BBOX, crs="EPSG:2180", nodata=None):
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            width=8,
            height=8,
            count=3,
            dtype="uint8",
            crs=crs,
            transform=from_bounds(*bounds, 8, 8),
            nodata=nodata,
        ) as dst:
            data = np.zeros((3, 8, 8), dtype="uint8")
            if nodata is None:
                data[:] = np.arange(64).reshape(8, 8) + 30
            dst.write(data)
        return mem.read()


def serve(monkeypatch, payloads):
    calls = []
    responses = iter(payloads)

    def open_url(request, timeout, context=None):
        calls.append(request.full_url)
        payload = next(responses)
        if isinstance(payload, Exception):
            raise payload
        return io.BytesIO(payload)

    monkeypatch.setattr(gp, "urlopen", open_url)
    return calls


def test_https_certificate_verification(settings, monkeypatch, tmp_path):
    def verified_open(request, timeout, context=None):
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        assert len(context.get_ca_certs()) > 0
        return io.BytesIO(ascii_grid())

    monkeypatch.setattr(gp, "urlopen", verified_open)
    gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)


def test_retry_incomplete_response(settings, monkeypatch, tmp_path):
    calls = serve(monkeypatch, [IncompleteRead(b"partial", 100), ascii_grid()])
    assert gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)[0].exists()
    assert len(calls) == 2


def test_tiles_cover_aligned_area_without_overlap():
    tiles = gp.plan_tiles((0.2, 0.1, 1001.2, 501.1), 500, 1, 20)
    assert len(tiles) == 6
    assert tiles[0] == (0, 0, 500, 500)
    assert tiles[-1] == (1000, 500, 1002, 502)
    assert sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in tiles) == 1002 * 502


@pytest.mark.parametrize("bbox", [(2, 0, 1, 1), (0, 0, float("nan"), 2), (0, 0, 0, 1)])
def test_invalid_bbox_rejected(bbox):
    with pytest.raises(ValueError):
        gp.plan_tiles(bbox, 500, 1, 20)


def test_large_area_rejected_before_download(settings, monkeypatch, tmp_path):
    calls = serve(monkeypatch, [])
    with pytest.raises(ValueError, match="kafelk"):
        gp.fetch_area(
            replace(settings, max_tiles=1), (0, 0, 1001, 1001), ["nmt"], tmp_path
        )
    assert calls == [] and list(tmp_path.iterdir()) == []


def test_fetch_both_layers_geotiff_metadata_and_resume(
    settings, monkeypatch, tmp_path, caplog
):
    calls = serve(monkeypatch, [ascii_grid(), rgb_tiff()])
    paths = gp.fetch_area(settings, BBOX, ["nmt", "ortho"], tmp_path)
    assert len(paths) == 2
    for path in paths:
        with rasterio.open(path) as ds:
            assert ds.crs.to_epsg() == 2180
            assert tuple(ds.bounds) == pytest.approx(BBOX)
        meta = json.loads(path.with_suffix(".json").read_text())
        assert meta["sha256"] and meta["downloaded_at_utc"]
        assert meta["valid_percent"] == 100
    with rasterio.open(paths[0]) as ds:
        assert ds.read(1).min() == 209
    query = parse_qs(urlsplit(calls[0]).query)
    assert query["COVERAGE"] == ["DTM_PL-EVRF2007-NH"]
    assert query["BBOX"] == [",".join(map(str, BBOX))]
    assert query["WIDTH"] == ["4"]
    assert gp.fetch_area(settings, BBOX, ["nmt", "ortho"], tmp_path) == paths
    assert len(calls) == 2
    assert "BLOCKXSIZE" not in caplog.text


def test_partial_nodata_mask_survives_conversion(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [ascii_grid().replace(b"209", b"-9999", 1)])
    path = gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)[0]
    with rasterio.open(path) as ds:
        assert ds.read(1, masked=True).count() == 15
    assert json.loads(path.with_suffix(".json").read_text())["valid_percent"] == 93.75


def test_other_area_cannot_silently_reuse_cache(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [ascii_grid()])
    gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)
    with pytest.raises(ValueError, match="overwrite"):
        gp.fetch_area(settings, (566967, 244147, 566972, 244151), ["nmt"], tmp_path)


def test_pixel_limit_checked_before_network(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [])
    with pytest.raises(ValueError, match="max_tile_pixels"):
        gp.fetch_area(replace(settings, max_tile_pixels=10), BBOX, ["ortho"], tmp_path)


@pytest.mark.parametrize(
    "bad",
    [b"", b"<ServiceException>busy</ServiceException>", URLError("connection reset")],
)
def test_retry_transient_or_non_raster_response(settings, monkeypatch, tmp_path, bad):
    calls = serve(monkeypatch, [bad, ascii_grid()])
    paths = gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)
    assert paths[0].exists() and len(calls) == 2


@pytest.mark.parametrize(
    "payload",
    [
        rgb_tiff(bounds=(0, 0, 4, 4)),
        rgb_tiff(crs="EPSG:4326"),
        rgb_tiff(nodata=0),
        b"<ServiceException>bad request</ServiceException>",
    ],
)
def test_bad_raster_never_published(settings, monkeypatch, tmp_path, payload):
    serve(monkeypatch, [payload] * settings.attempts)
    with pytest.raises(RuntimeError, match="ortho"):
        gp.fetch_area(settings, BBOX, ["ortho"], tmp_path)
    assert not list(tmp_path.glob("*.tif"))
    assert not list(tmp_path.glob("*.json"))
    assert not list(tmp_path.glob("*.part"))


def test_corrupt_cache_detected(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [ascii_grid()])
    paths = gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)
    paths[0].write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="overwrite"):
        gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)


def test_dry_run_no_network_or_files(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [])
    gp.fetch_area(settings, BBOX, ["nmt", "ortho"], tmp_path / "new", dry_run=True)
    assert not (tmp_path / "new").exists()


def test_size_limit(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [ascii_grid()] * settings.attempts)
    with pytest.raises(RuntimeError, match="nmt"):
        gp.fetch_area(replace(settings, max_response_bytes=10), BBOX, ["nmt"], tmp_path)


def test_overwrite_failure_preserves_previous_tile(settings, monkeypatch, tmp_path):
    serve(monkeypatch, [ascii_grid()])
    path = gp.fetch_area(settings, BBOX, ["nmt"], tmp_path)[0]
    previous = path.read_bytes()
    serve(monkeypatch, [b"error"] * settings.attempts)
    with pytest.raises(RuntimeError):
        gp.fetch_area(settings, BBOX, ["nmt"], tmp_path, overwrite=True)
    assert path.read_bytes() == previous
