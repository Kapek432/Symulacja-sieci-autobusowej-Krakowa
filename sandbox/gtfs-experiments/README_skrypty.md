# Skrypty projektu: propagacja opóźnień autobusów ZTP Kraków

Dokument opisuje skrypty, które zostają w projekcie, ich zależności i kolejność uruchamiania.

## Układ folderów

Skrypty leżą w `sandbox/gtfs-experiments/`, a dane w `data/` w katalogu głównym repozytorium. `build_events.py` i `week_analysis.py` szukają w górę drzewa folderu, który zawiera `data/raw_A`, i to on jest katalogiem głównym, więc można je uruchamiać z dowolnego katalogu. Logger robi inaczej: zapisuje do `data/raw_A` obok własnego pliku (na komputerze z loggerem to `C:\gtfs\data\raw_A`), chyba że ustawiono `OUT_DIR`.

```
Symulacja-sieci.../                <- katalog glowny repozytorium
  sandbox/gtfs-experiments/
    logger_autobusy.py
    build_events.py
    week_analysis.py
    README_skrypty.md
  data/
    raw_A/                         <- dane z loggera (kopia z C:\gtfs\data\raw_A)
      vehicle_positions/date=YYYY-MM-DD/part-*.parquet
      trip_updates/date=YYYY-MM-DD/part-*.parquet
      static/GTFS_KRK_A_<stamp>.zip
      static/GTFS_KRK_A.sha256
    processed/                     <- tworzą build_events i week_analysis
      observed_events.parquet
      week_report/report.txt
      week_report/figures/*.png
```

Logger działa na osobnym komputerze (`C:\gtfs`, zadanie ZTP-logger). Do analizy trzeba skopiować cały folder `data/raw_A` (razem z `static`) do katalogu projektu na komputerze, na którym liczę.

## Kolejność uruchamiania

1. `logger_autobusy.py` - ciągle, zbiera dane.
2. `build_events.py` - po każdym dociągnięciu nowych danych (przelicza zdarzenia od zera).
3. `week_analysis.py` - po `build_events.py`, generuje pełny raport.

```
uv run sandbox/gtfs-experiments/build_events.py
uv run sandbox/gtfs-experiments/week_analysis.py 179
```

## Zależności

`pandas`, `numpy`, `pyarrow`, `requests`, `gtfs-realtime-bindings` (importowane jako `google.transit`), `matplotlib` (opcjonalnie, bez niego pomijane są tylko wykresy).

```
uv add pandas numpy pyarrow requests gtfs-realtime-bindings matplotlib
```

## logger_autobusy.py

Logger GTFS-Realtime ZTP Kraków. Co `POLL_S` sekund (domyślnie 15) pobiera `VehiclePositions_<GROUP>.pb` i `TripUpdates_<GROUP>.pb`, parsuje je do tabel i co `FLUSH_S` sekund (domyślnie 600) zapisuje bufor do plików parquet podzielonych na dni (`date=...`). Co 6 godzin sprawdza rozkład statyczny i zapisuje nową wersję tylko wtedy, gdy zmienił się jego skrót SHA-256. Przy błędzie sieci, uszkodzonym pliku lub pustym feedzie ponawia odczyt do 3 razy. Zamyka się poprawnie na SIGINT/SIGTERM z zapisem reszty bufora.

- Wejście: API `gtfs.ztp.krakow.pl`.
- Wyjście: `data/raw_<GROUP>/vehicle_positions`, `trip_updates`, `static`.
- Konfiguracja zmiennymi środowiskowymi: `GROUP` (T, A lub M, domyślnie A), `OUT_DIR`, `POLL_S`, `FLUSH_S`, `MAX_STOPS` (ile pierwszych przystanków kursu z TripUpdates, domyślnie 5 dla autobusów), `TU_EVERY`, `SAVE_RAW`.

## build_events.py

Buduje zdarzenia przystankowe z VehiclePositions: epizody postoju ze statusem 1 (`STOPPED_AT`), łączone w kursach i przystankach (przerwa dłuższa niż 600 s zaczyna nowy epizod). Dla każdego zdarzenia liczy czas przyjazdu i odjazdu, niepewność czasu (odstęp do sąsiednich raportów pojazdu), dopasowuje rozkład z GTFS, wyznacza datę obsługi (dziś albo wczoraj, zależnie od tego, która daje czas bliższy rozkładowi) i opóźnienia przyjazdu i odjazdu. Flagi `arr_ok` i `dep_ok` oznaczają niepewność do 30 s, `arr_ok` dodatkowo wyklucza pierwszy przystanek kursu.

Na końcu drukuje raport jakości: rozkład niepewności, rozkład opóźnień, pokrycie przystanków, udział powtórzonych pozycji i niezależną kontrolę względem prognoz z TripUpdates.

- Wejście: `data/raw_A/vehicle_positions`, `data/raw_A/trip_updates`, najnowszy `data/raw_A/static/GTFS_KRK_A_*.zip`.
- Wyjście: `data/processed/observed_events.parquet`.
- Ważne stałe: `EPISODE_GAP_S = 600`, `UNC_OK_S = 30`.
- Uwaga: używa tylko najnowszej wersji rozkładu. Jeśli w czasie zbierania danych rozkład się zmienił, opóźnienia z dni sprzed zmiany mogą być źle dopasowane.

## week_analysis.py

Pełna analiza zebranych danych, uruchamiana z linią pilotową jako argumentem (domyślnie 179). Zbiór dni roboczych można wybrać ręcznie: `DAYS=2026-10-05,2026-10-06 uv run week_analysis.py 179`. Dzień roboczy jest uznany za pełny, gdy ma co najmniej 70% mediany liczby zdarzeń, a dni z mniej niż 500 zdarzeń są odrzucane jako śmieciowe.

Sekcje raportu:

1. Pokrycie i jakość danych dzień po dniu, dziury w loggerze.
2. Rozkład: ile kursów powinno jechać, a ile zobaczono.
3. Opóźnienia wg dnia, typu dnia, pory i stabilność między dniami (statystyka KS).
4. Opóźnienie i rozrzut wzdłuż trasy, kształt wzrostu wariancji.
5. Błąd odstępu sigma_e, jego nachylenie wzdłuż trasy, wzór dobowy.
6. Pętla i łańcuchy kursów: reset opóźnienia, krzywa pochłaniania, kalibracja `l_min`.
7. Sprzężenie od odstępu gamma (regresja z efektami stałymi i błędami klastrowymi).
8. Zbijanie się: obserwacja kontra model zerowy z permutacją.
9. Zakłócenia wspólne u: korelacja residuów opóźnień kolejnych autobusów.
10. Przyrosty opóźnień na odcinkach, autokorelacja, postoje.
11. Ranking linii i korytarz wokół linii pilotowej.

Na końcu drukuje listę kluczowych liczb do projektu.

- Wejście: `data/processed/observed_events.parquet`, `data/raw_A/vehicle_positions` (tylko kolumna `fetched_at`, do wykrywania dziur), najnowszy GTFS.
- Wyjście: wydruk na ekran, `data/processed/week_report/report.txt`, wykresy w `data/processed/week_report/figures/`.
- Nie korzysta z żadnego wyniku innego skryptu poza `observed_events.parquet`.