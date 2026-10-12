"""Logger GTFS-Realtime ZTP Krakow: pozycje pojazdow i aktualizacje kursow.

Konfiguracja przez zmienne srodowiskowe:
  GROUP      T (tramwaje), A (autobusy MPK), M (Mobilis); domyslnie A
  OUT_DIR    katalog wyjsciowy; domyslnie data/raw (T) lub data/raw_<GROUP>
  POLL_S     odstep odpytywania w sekundach; domyslnie 15
  FLUSH_S    co ile sekund zapisywac bufor na dysk; domyslnie 600
  MAX_STOPS  ile pierwszych przystankow kursu zapisywac z TripUpdates
             (0 = wszystkie); domyslnie 5 dla autobusow, 0 dla tramwajow
  SAVE_RAW   1 = zapisuj dodatkowo surowe pliki .pb (gzip)
"""
import gzip
import hashlib
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from google.transit import gtfs_realtime_pb2
from google.protobuf.message import DecodeError

RETRIES = 3
RETRY_WAIT_S = 1.5

BASE = "https://gtfs.ztp.krakow.pl"
GROUP = os.environ.get("GROUP", "A").upper()
URL_VP = f"{BASE}/VehiclePositions_{GROUP}.pb"
URL_TU = f"{BASE}/TripUpdates_{GROUP}.pb"
URL_STATIC = f"{BASE}/GTFS_KRK_{GROUP}.zip"

OUT = Path(os.environ.get("OUT_DIR", "data/raw" if GROUP == "T" else f"data/raw_{GROUP}"))
POLL_S = int(os.environ.get("POLL_S", "15"))
FLUSH_S = int(os.environ.get("FLUSH_S", "600"))
MAX_STOPS = int(os.environ.get("MAX_STOPS", "0" if GROUP == "T" else "5"))
SAVE_RAW = os.environ.get("SAVE_RAW", "0") == "1"
TU_EVERY = int(os.environ.get("TU_EVERY", "1"))   # TripUpdates co N cykli odpytywania

STATIC_CHECK_S = 6 * 3600
TIMEOUT_S = 10
STALE_WARN_POLLS = max(1, 300 // POLL_S)   # ostrzezenie po ok. 5 min bez zmian
STALE_POSITION_S = 300                      # pozycja starsza niz 5 min = ostrzezenie
HEADERS = {"User-Agent": "tram-bunching-student-project (kontakt: klipiec@student.agh.edu.pl)"}

log = logging.getLogger("logger")

DTYPES = {
    "feed_ts": "Int64", "veh_ts": "Int64", "tu_ts": "Int64",
    "direction_id": "Int64", "current_stop_sequence": "Int64",
    "current_status": "Int64", "stop_sequence": "Int64",
    "trip_delay": "Int64", "arr_delay": "Int64", "arr_time": "Int64",
    "dep_delay": "Int64", "dep_time": "Int64", "sched_rel": "Int64",
    "lat": "float64", "lon": "float64", "bearing": "float64", "speed": "float64",
    "fetched_at": "float64",
}


def g(msg, name):
    """Zwraca wartosc pola opcjonalnego albo None, jesli nie ustawiono."""
    return getattr(msg, name) if msg.HasField(name) else None


def trip_fields(trip):
    return {
        "trip_id": trip.trip_id or None,
        "route_id": trip.route_id or None,
        "direction_id": g(trip, "direction_id"),
        "start_date": trip.start_date or None,
        "start_time": trip.start_time or None,
    }


def parse_vehicle_positions(feed, fetched_at):
    rows = []
    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        pos = v.position if v.HasField("position") else None
        rows.append({
            "fetched_at": fetched_at,
            "feed_ts": feed.header.timestamp,
            "entity_id": e.id,
            "vehicle_id": g(v.vehicle, "id") if v.HasField("vehicle") else None,
            "vehicle_label": g(v.vehicle, "label") if v.HasField("vehicle") else None,
            **trip_fields(v.trip),
            "lat": pos.latitude if pos else None,
            "lon": pos.longitude if pos else None,
            "bearing": g(pos, "bearing") if pos else None,
            "speed": g(pos, "speed") if pos else None,
            "veh_ts": g(v, "timestamp"),
            "current_stop_sequence": g(v, "current_stop_sequence"),
            "stop_id": v.stop_id or None,
            "current_status": g(v, "current_status"),
        })
    return rows


def parse_trip_updates(feed, fetched_at):
    rows = []
    for e in feed.entity:
        if not e.HasField("trip_update"):
            continue
        tu = e.trip_update
        base = {
            "fetched_at": fetched_at,
            "feed_ts": feed.header.timestamp,
            "entity_id": e.id,
            "vehicle_id": g(tu.vehicle, "id") if tu.HasField("vehicle") else None,
            **trip_fields(tu.trip),
            "tu_ts": g(tu, "timestamp"),
            "trip_delay": g(tu, "delay"),
        }
        empty = {"stop_sequence": None, "stop_id": None, "arr_delay": None,
                 "arr_time": None, "dep_delay": None, "dep_time": None,
                 "sched_rel": None}
        updates = list(tu.stop_time_update)
        if MAX_STOPS:
            updates = updates[:MAX_STOPS]
        if not updates:
            rows.append({**base, **empty})
            continue
        for s in updates:
            arr = s.arrival if s.HasField("arrival") else None
            dep = s.departure if s.HasField("departure") else None
            rows.append({
                **base,
                "stop_sequence": g(s, "stop_sequence"),
                "stop_id": s.stop_id or None,
                "arr_delay": g(arr, "delay") if arr else None,
                "arr_time": g(arr, "time") if arr else None,
                "dep_delay": g(dep, "delay") if dep else None,
                "dep_time": g(dep, "time") if dep else None,
                "sched_rel": g(s, "schedule_relationship"),
            })
    return rows


def fetch_feed(session, url, name):
    """Pobiera feed, ponawiajac przy bledzie sieci, uszkodzonym pliku i pustym feedzie.
    Zwraca (feed, content, last_modified) albo None, jesli sie nie udalo."""
    reason = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT_S)
            r.raise_for_status()
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(r.content)
            if feed.entity or attempt == RETRIES:
                if attempt > 1:
                    log.info("%s: OK po %d. probie", name, attempt)
                return feed, r.content, r.headers.get("Last-Modified")
            reason = "pusty feed"
        except DecodeError:
            reason = "uszkodzony plik (odczyt w trakcie zapisu po stronie serwera?)"
        except requests.RequestException as e:
            reason = f"blad sieci: {e}"
        if attempt < RETRIES:
            time.sleep(RETRY_WAIT_S)
    log.warning("%s: pomijam odczyt po %d probach: %s", name, RETRIES, reason)
    return None


def flush(name, rows):
    if not rows:
        return
    now = datetime.now(timezone.utc)
    folder = OUT / name / f"date={now:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df = df.astype({c: t for c, t in DTYPES.items() if c in df.columns})
    str_cols = [c for c in df.columns if c not in DTYPES]
    df[str_cols] = df[str_cols].astype("string")
    path = folder / f"part-{now:%H%M%S}.parquet"
    df.to_parquet(path, index=False, compression="zstd")
    log.info("zapisano %s: %d wierszy", path, len(df))
    rows.clear()  # czyscimy dopiero po udanym zapisie


def save_raw(name, content, fetched_at):
    now = datetime.fromtimestamp(fetched_at, timezone.utc)
    folder = OUT / "raw_pb" / name / f"date={now:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    with gzip.open(folder / f"{now:%H%M%S}.pb.gz", "wb") as f:
        f.write(content)


def update_static(session):
    """Pobiera rozklad i zapisuje nowa wersje tylko, gdy sie zmienil."""
    r = session.get(URL_STATIC, timeout=120)
    r.raise_for_status()
    digest = hashlib.sha256(r.content).hexdigest()
    folder = OUT / "static"
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / f"GTFS_KRK_{GROUP}.sha256"
    if marker.exists() and marker.read_text().strip() == digest:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (folder / f"GTFS_KRK_{GROUP}_{stamp}.zip").write_bytes(r.content)
    marker.write_text(digest)
    log.info("nowa wersja rozkladu zapisana (%s)", stamp)


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    log.info("start: GROUP=%s OUT=%s POLL_S=%d TU_EVERY=%d FLUSH_S=%d MAX_STOPS=%d SAVE_RAW=%s",
             GROUP, OUT, POLL_S, TU_EVERY, FLUSH_S, MAX_STOPS, SAVE_RAW)

    stop = {"flag": False}

    def handler(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    feeds = {
        "vehicle_positions": (URL_VP, parse_vehicle_positions),
        "trip_updates": (URL_TU, parse_trip_updates),
    }
    buffers = {name: [] for name in feeds}
    last_hash = {name: None for name in feeds}
    unchanged = {name: 0 for name in feeds}

    session = requests.Session()
    session.headers.update(HEADERS)

    next_tick = time.monotonic()
    last_flush = time.monotonic()
    last_static = float("-inf")
    cycle = 0

    while not stop["flag"]:
        cycle += 1
        if time.monotonic() - last_static > STATIC_CHECK_S:
            try:
                update_static(session)
                last_static = time.monotonic()
            except Exception as e:
                log.warning("blad pobierania rozkladu statycznego: %s", e)
                last_static = time.monotonic() - STATIC_CHECK_S + 600  # ponow za 10 min

        fetched_at = time.time()
        for name, (url, parser) in feeds.items():
            if name == "trip_updates" and (cycle - 1) % TU_EVERY != 0:
                continue  # prognozy pobieramy rzadziej niz pozycje

            result = fetch_feed(session, url, name)
            if result is None:
                continue
            feed, content, last_mod = result

            digest = hashlib.md5(content).hexdigest()
            if digest == last_hash[name]:
                unchanged[name] += 1
                if unchanged[name] % STALE_WARN_POLLS == 0:
                    log.warning("%s: plik bez zmian od %d odczytow (Last-Modified: %s)",
                                name, unchanged[name], last_mod)
                continue
            unchanged[name] = 0
            last_hash[name] = digest

            try:
                new_rows = parser(feed, fetched_at)
            except Exception:
                log.exception("%s: blad przetwarzania encji", name)
                continue
            for row in new_rows:
                row["server_last_modified"] = last_mod
            buffers[name].extend(new_rows)

            msg = "%s: encje=%d wierszy=%d bufor=%d"
            args = [name, len(feed.entity), len(new_rows), len(buffers[name])]
            level = logging.INFO
            if name == "vehicle_positions":
                ages = [fetched_at - r["veh_ts"] for r in new_rows if r["veh_ts"]]
                if ages:
                    age = min(ages)
                    msg += " najswiezsza_pozycja=%.0f s"
                    args.append(age)
                    if age > STALE_POSITION_S:
                        level = logging.WARNING
            log.log(level, msg, *args)

            if SAVE_RAW:
                try:
                    save_raw(name, content, fetched_at)
                except Exception:
                    log.exception("%s: blad zapisu surowego pliku", name)

        if time.monotonic() - last_flush >= FLUSH_S:
            for name, rows in buffers.items():
                try:
                    flush(name, rows)
                except Exception:
                    log.exception("blad zapisu %s", name)
            last_flush = time.monotonic()

        next_tick += POLL_S
        delay = next_tick - time.monotonic()
        if delay < 0:
            next_tick = time.monotonic()
            delay = 0
        time.sleep(delay)

    for name, rows in buffers.items():  # zapis reszty przy zamknieciu
        try:
            flush(name, rows)
        except Exception:
            log.exception("blad zapisu %s przy zamknieciu", name)
    log.info("zakonczono")


if __name__ == "__main__":
    main()