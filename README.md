# Symulacja sieci autobusowej Krakowa

Propagacja opóźnień w sieci autobusowej Krakowa: symulacja zdarzeń dyskretnych z łańcuchami kursów, kalibrowana i walidowana na danych GTFS-Realtime ZTP.

- Temat (dla prowadzącego): [`TEMAT.md`](TEMAT.md)
- Plan realizacji i kamienie milowe: [`docs/PLAN_REALIZACJI.md`](docs/PLAN_REALIZACJI.md)
- Opis skryptów danych: [`sandbox/gtfs-experiments/README_skrypty.md`](sandbox/gtfs-experiments/README_skrypty.md)

## Szybki start

Wymagania: [uv](https://docs.astral.sh/uv/), Python 3.14.

```
uv sync
```

Dane surowe nie są w repo. Pobierz folder `raw_A` (z `vehicle_positions/`, `trip_updates/`, `static/`) ze wspólnego Google Drive i scal go z `data/raw_A/` w katalogu projektu (procedura: [`docs/milestones/M0_fundament.md`](docs/milestones/M0_fundament.md)), potem:

```
uv run sandbox/gtfs-experiments/build_events.py
uv run sandbox/gtfs-experiments/week_analysis.py 179
```

Wyniki: `data/processed/observed_events.parquet`, raport w `data/processed/week_report/`.

## Testy i lint

```
uv run pytest
uv run ruff check .
```
