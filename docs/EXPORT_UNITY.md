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

## Graf sieci: `network.json`

Generuje go `uv run export-network --positions data/processed/unity_samples/obs_peak30.meta.json` (GTFS i linie z metadanych pozycji) albo `--gtfs ZIP [--routes 102 104 ...]`; `--out DIR` zmienia katalog (domyślnie `data/processed/unity_samples`). Układ współrzędnych: `x` na wschód, `z` na północ, metry od Rynku Głównego (`origin`: lat 50.0617, lon 19.9373), rzut equirectangular. Wartości zaokrąglone do 0,1 m.

```json
{"meta": {...}, "stops": [...], "segments": [...]}
```

| Pole | Znaczenie |
|---|---|
| `meta.schema_version` | wersja kontraktu (1) |
| `meta.origin` | `lat`, `lon`, `axes` (`x=east m, z=north m`) |
| `meta.routes` | wyeksportowane linie |
| `meta.n_stops`, `meta.n_segments` | liczby elementów |
| `meta.n_straight` | odcinki proste zamiast kształtu wg powodu: `no_shape` (kurs bez `shape_id`), `far_stop` (przystanek dalej niż 100 m od kształtu; dotyczy obu sąsiednich odcinków) |
| `meta.bbox` | `x_min`, `x_max`, `z_min`, `z_max` przystanków |
| `stops[]` | `stop_id`, `name`, `x`, `z` (tylko przystanki użyte w odcinkach) |
| `segments[]` | `from_stop`, `to_stop` (skierowany odcinek między kolejnymi przystankami), `routes` (posortowana lista linii), `points` |

`points` to płaska lista `[x0, z0, x1, z1, ...]` (co najmniej 2 punkty): fragment `shapes.txt` między rzutami przystanków, uproszczony algorytmem Douglasa-Peuckera (2 m). Odcinek wspólny dla wielu linii występuje raz, z geometrią z pierwszego wzorca.

## Pozycje GPS: `obs_peak30.jsonl`

Pozycje pojazdów w stałym kroku czasu, jeden wiersz JSON na pojazd i chwilę.

| Pole | Typ | Znaczenie |
|---|---|---|
| `t` | int | czas, sekundy epoki Unix (UTC) |
| `sim_time_s` | int | sekundy od północy dnia `service_date` (czas lokalny) |
| `service_date` | str | dzień rozkładowy |
| `vehicle_id` | str | pojazd |
| `trip_id` | str | kurs GTFS |
| `route_id` | str | linia |
| `lat`, `lon` | float | pozycja (WGS84) |
| `x`, `z` | float | pozycja w układzie `network.json` (metry) |
| `bearing` | float | kierunek jazdy, stopnie |
| `status` | int | `current_status` GTFS-RT: 0 podjeżdża, 1 stoi na przystanku, 2 w drodze |
| `delay_s` | float / null | opóźnienie w sekundach (kolor); null = brak |
| `layover` | bool | postój na pętli (kolor szary) |
| `source` | str | `obs` albo `sim` |

Metadane (`obs_peak30.meta.json`): `schema_version`, `run_id`, `gtfs` (nazwa ZIP-a w `data/raw_*/static`), `origin`, `t_min`, `t_max`, `rows`, `vehicles`, `routes`.
