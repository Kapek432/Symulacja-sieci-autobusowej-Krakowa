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
