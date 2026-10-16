# Skrypty projektu: propagacja opóźnień autobusów ZTP Kraków

Dokument opisuje skrypty, które zostają w projekcie, ich zależności i kolejność uruchamiania.

## Układ folderów

Skrypty leżą w `sandbox/gtfs-experiments/`, a dane w `data/` w katalogu głównym repozytorium. `build_events.py` i `week_analysis.py` szukają w górę drzewa folderu, który zawiera `data/raw_A`, i to on jest katalogiem głównym, więc można je uruchamiać z dowolnego katalogu. Logger robi inaczej: zapisuje do `data/raw_A` obok własnego pliku (na komputerze z loggerem to `C:\gtfs\data\raw_A`), chyba że ustawiono `OUT_DIR`.

```
Symulacja-sieci.../                <- katalog glowny repozytorium
  sandbox/gtfs-experiments/
    logger_autobusy.py
    gtfs_versions.py
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

Analiza (`build_events.py`, `week_analysis.py`): `pandas`, `numpy`, `pyarrow`, `matplotlib` — zadeklarowane w `pyproject.toml`, wystarczy `uv sync`.

Logger (tylko na komputerze z loggerem): dodatkowo `requests` i `gtfs-realtime-bindings` (importowane jako `google.transit`).

## logger_autobusy.py

Logger GTFS-Realtime ZTP Kraków. Co `POLL_S` sekund (domyślnie 15) pobiera `VehiclePositions_<GROUP>.pb` i `TripUpdates_<GROUP>.pb`, parsuje je do tabel i co `FLUSH_S` sekund (domyślnie 600) zapisuje bufor do plików parquet podzielonych na dni (`date=...`). Co 6 godzin sprawdza rozkład statyczny i zapisuje nową wersję tylko wtedy, gdy zmienił się jego skrót SHA-256. Przy błędzie sieci, uszkodzonym pliku lub pustym feedzie ponawia odczyt do 3 razy. Zamyka się poprawnie na SIGINT/SIGTERM z zapisem reszty bufora.

- Wejście: API `gtfs.ztp.krakow.pl`.
- Wyjście: `data/raw_<GROUP>/vehicle_positions`, `trip_updates`, `static`.
- Konfiguracja zmiennymi środowiskowymi: `GROUP` (T, A lub M, domyślnie A), `OUT_DIR`, `POLL_S`, `FLUSH_S`, `MAX_STOPS` (ile pierwszych przystanków kursu z TripUpdates, domyślnie 5 dla autobusów), `TU_EVERY`, `SAVE_RAW`.

## build_events.py

Buduje zdarzenia przystankowe z VehiclePositions: epizody postoju ze statusem 1 (`STOPPED_AT`), łączone w kursach i przystankach (przerwa dłuższa niż 600 s zaczyna nowy epizod). Dla każdego zdarzenia liczy czas przyjazdu i odjazdu, niepewność czasu (odstęp do sąsiednich raportów pojazdu), dopasowuje rozkład z właściwej wersji GTFS (`gtfs_versions.py`), wyznacza datę obsługi i opóźnienia przyjazdu i odjazdu. Flagi `arr_ok` i `dep_ok` oznaczają niepewność do 30 s, `arr_ok` dodatkowo wyklucza pierwszy przystanek kursu.

Na końcu drukuje raport jakości: udział zdarzeń dopasowanych do rozkładu i z datą obsługi, tabelę „zdarzenia dzień po dniu” (wg daty obsługi, wg daty lokalnej, bez daty obsługi, liczba linii, wersja kalendarza), rozkład niepewności, rozkład opóźnień, pokrycie przystanków, udział powtórzonych pozycji i niezależną kontrolę względem prognoz z TripUpdates.

- Wejście: `data/raw_A/vehicle_positions`, `data/raw_A/trip_updates`, wszystkie `data/raw_A/static/GTFS_KRK_A_*.zip`.
- Wyjście: `data/processed/observed_events.parquet` (m.in. `service_date`, `service_id`, `gtfs_stamp`, `arr_delay_s`, `dep_delay_s`, `arr_ok`, `dep_ok`). `service_date` jest pusta, gdy kurs nie występuje w żadnej wersji rozkładu albo jego usługa nie jest aktywna wczoraj, dziś ani jutro.
- Ważne stałe: `EPISODE_GAP_S = 600`, `UNC_OK_S = 30`.

## gtfs_versions.py

Moduł (nie skrypt) używany przez `build_events.py` i `week_analysis.py`. Łączy wszystkie wersje rozkładu zapisane przez logger.

Feed ZTP jest kroczący: każda wersja zawiera kilka pokoleń usług z prefiksem daty w `service_id` i `trip_id` (np. `20261005_1_128936604_2`), a kalendarz jest tylko w `calendar_dates.txt`. Ten sam `trip_id` ma identyczne `stop_times` we wszystkich wersjach.

- Rozkład kursu: z najnowszej wersji, która zawiera dany `trip_id` (kolumna `gtfs_stamp`).
- Kalendarz dnia D: z najnowszej wersji, która ma jakikolwiek wpis na D (starsza wersja może jeszcze wymieniać usługi zastąpione przez nowszą).
- Data obsługi zdarzenia: kandydaci wczoraj, dziś i jutro względem lokalnej daty przyjazdu, tylko dni z aktywną usługą kursu; wygrywa najmniejsze |opóźnienie|, przy remisie dziś.
- Czasy GTFS liczone od „lokalne południe minus 12 h”, więc doba zmiany czasu (23 albo 25 h) nie przesuwa opóźnień.

Testy: `uv run pytest`.

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

- Wejście: `data/processed/observed_events.parquet`, `data/raw_A/vehicle_positions` (tylko kolumna `fetched_at`, do wykrywania dziur), wszystkie wersje GTFS przez `gtfs_versions.py` (sekcja 2 liczy kursy wg kalendarza efektywnego danego dnia). Zdarzenia bez daty obsługi są pomijane z wypisaną liczbą.
- Wyjście: wydruk na ekran, `data/processed/week_report/report.txt`, wykresy w `data/processed/week_report/figures/`.
- Nie korzysta z żadnego wyniku innego skryptu poza `observed_events.parquet`.