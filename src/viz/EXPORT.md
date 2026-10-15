# Kontrakt eksportu do Unity (schema_version 1)

Python zapisuje, Unity tylko odczytuje i wyświetla. Ten sam format dla danych obserwowanych (`source = "obs"`) i symulacji (`source = "sim"`), żeby oba odtwarzać tym samym kodem i tym samym zegarem.

Eksporter danych obserwowanych: `src/viz/export_unity.py`.

```
uv run src/viz/export_unity.py                                   # wszystko z data/raw_A
uv run src/viz/export_unity.py --from 2026-10-16T07:00 --to 2026-10-16T09:00 --routes 179,169,174
```

Domyślne wyjście: `data/processed/unity_samples/obs.jsonl` + `obs.meta.json`.

## Plik `<nazwa>.jsonl`

Jeden wiersz = jeden raport pojazdu (obs: co ok. 5 s, z loggera). Wiersze posortowane po `t`. Unity interpoluje pozycję między kolejnymi raportami tego samego `vehicle_id`.

| Pole | Typ | Znaczenie |
|------|-----|-----------|
| `t` | int | czas raportu, epoch UTC [s] |
| `sim_time_s` | int / null | sekundy od północy lokalnej dnia obsługi (jak w GTFS, w nocy > 86400); wspólny zegar obs i sim |
| `service_date` | str / null | dzień obsługi `YYYY-MM-DD` (kurs po północy należy do dnia poprzedniego) |
| `vehicle_id` | str | pojazd |
| `trip_id`, `route_id` | str | kurs i linia z GTFS |
| `lat`, `lon` | float | WGS84 |
| `x`, `z` | float | metry od początku układu z `meta.origin`: `x` na wschód, `z` na północ. W Unity wprost `new Vector3(x, 0, z)` |
| `bearing` | float | kierunek jazdy [°], 0 = północ |
| `status` | int / null | GTFS-RT: 0 dojeżdża, 1 stoi na przystanku, 2 w drodze |
| `delay_s` | int / null | opóźnienie względem rozkładu [s], ujemne = przed czasem; null = nie liczymy (patrz `layover`) |
| `layover` | bool | pojazd czeka na pętli przed odjazdem kursu (w Unity np. kolor szary) |
| `source` | str | `obs` albo `sim` |

Opóźnienie w obs: na przystanku `t − rozkładowy przyjazd`; między przystankami rozkładowy czas interpolowany po odległości do sąsiednich przystanków. Na pierwszym przystanku dodatnie opóźnienie (spóźniony odjazd) zostaje, ujemne zamienia się na `layover`.

## Plik `<nazwa>.meta.json`

| Pole | Znaczenie |
|------|-----------|
| `schema_version` | wersja tego kontraktu; zmiana pól = podbicie wersji |
| `run_id`, `seed` | identyfikacja przebiegu (obs: `seed = null`) |
| `source` | `obs` / `sim` |
| `gtfs` | plik rozkładu użyty do liczenia opóźnień |
| `origin` | `lat`, `lon` początku układu `x`/`z` (Rynek Główny) |
| `t_min`, `t_max`, `rows`, `vehicles`, `routes` | zakres i podsumowanie |
