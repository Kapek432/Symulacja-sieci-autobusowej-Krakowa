# Skrypty i komendy danych: propagacja opóźnień autobusów ZTP Kraków

Dokument opisuje kod danych, jego zależności i kolejność uruchamiania.

## Układ folderów

Logika przetwarzania jest w pakiecie `src/krakbus/` (instalowany przez `uv sync`, komendy `uv run build-events` i `uv run events-quality`). W `sandbox/gtfs-experiments/` zostają logger i eksploracyjna analiza `week_analysis.py`. Ścieżki i progi są w `configs/config.yaml` (względem katalogu głównego repozytorium), więc komendy działają z dowolnego katalogu. Logger robi inaczej: zapisuje do `data/raw_A` obok własnego pliku (na komputerze z loggerem to `C:\gtfs\data\raw_A`), chyba że ustawiono `OUT_DIR`.

```
Symulacja-sieci.../                <- katalog glowny repozytorium
  configs/
    config.yaml                    <- sciezki, progi zdarzen i klasyfikacji dni
    special_days.yaml              <- dni nietypowe (swieta, zmiana czasu)
    days_split.yaml                <- (od M3) zamrozony podzial dni calib/excluded
  src/krakbus/
    config.py, logger.py
    ingest/gtfs_versions.py        <- laczenie wersji GTFS, data obslugi
    ingest/raw.py                  <- partycje loggera, okno D-1..D+1
    observed/events.py             <- zdarzenia przystankowe jednego dnia
    observed/days.py               <- statystyki, status i rola dnia
    observed/manifest.py           <- odciski wejsc, zapis atomowy
    observed/pipeline.py           <- komenda build-events
    observed/quality.py            <- komenda events-quality
    observed/store.py              <- load_events() do analiz
  sandbox/gtfs-experiments/
    logger_autobusy.py
    week_analysis.py
  data/
    raw_A/                         <- dane z loggera (kopia z C:\gtfs\data\raw_A)
      vehicle_positions/date=YYYY-MM-DD/part-*.parquet
      trip_updates/date=YYYY-MM-DD/part-*.parquet
      static/GTFS_KRK_A_<stamp>.zip
      static/GTFS_KRK_A.sha256
    processed/
      events/YYYY-MM-DD.parquet    <- zdarzenia per data obslugi
      days.csv                     <- rejestr dni
      manifest.json                <- odciski wejsc kazdego dnia
      week_report/report.txt
      week_report/figures/*.png
```

Logger działa na osobnym komputerze (`C:\gtfs`, zadanie ZTP-logger). Dane z niego trafiają co jakiś czas na wspólny Google Drive; każdy pobiera stamtąd folder `raw_A` (razem z `static`) i scala go z `data/raw_A` w katalogu projektu. Procedura krok po kroku, z komendą scalania dla macOS/Linux i Windows: `docs/milestones/M0_fundament.md`.

## Kolejność uruchamiania

1. `logger_autobusy.py` - ciągle, zbiera dane.
2. `uv run build-events` - po każdym dociągnięciu nowych danych; przelicza tylko zmienione dni.
3. `uv run events-quality` - raport jakości ostatnich 3 dni `complete` (albo `--days ...`).
4. `week_analysis.py` - pełny raport na dniach `complete`.

```
uv run build-events
uv run events-quality
uv run sandbox/gtfs-experiments/week_analysis.py 179
```

## Zależności

Analiza: `pandas`, `numpy`, `pyarrow`, `matplotlib`, `pyyaml` — zadeklarowane w `pyproject.toml`, wystarczy `uv sync`.

Logger (tylko na komputerze z loggerem): dodatkowo `requests` i `gtfs-realtime-bindings` (importowane jako `google.transit`).

## logger_autobusy.py

Logger GTFS-Realtime ZTP Kraków. Co `POLL_S` sekund (domyślnie 15) pobiera `VehiclePositions_<GROUP>.pb` i `TripUpdates_<GROUP>.pb`, parsuje je do tabel i co `FLUSH_S` sekund (domyślnie 600) zapisuje bufor do nowego pliku `part-HHMMSS.parquet` w katalogu `date=...` (data UTC zapisu). Raz zapisany plik nie jest potem zmieniany. Co 6 godzin sprawdza rozkład statyczny i zapisuje nową wersję tylko wtedy, gdy zmienił się jego skrót SHA-256. Przy błędzie sieci, uszkodzonym pliku lub pustym feedzie ponawia odczyt do 3 razy. Zamyka się poprawnie na SIGINT/SIGTERM z zapisem reszty bufora.

- Wejście: API `gtfs.ztp.krakow.pl`.
- Wyjście: `data/raw_<GROUP>/vehicle_positions`, `trip_updates`, `static`.
- Konfiguracja zmiennymi środowiskowymi: `GROUP` (T, A lub M, domyślnie A), `OUT_DIR`, `POLL_S`, `FLUSH_S`, `MAX_STOPS` (ile pierwszych przystanków kursu z TripUpdates, domyślnie 5 dla autobusów), `TU_EVERY`, `SAVE_RAW`.

## build-events (`krakbus.observed.pipeline`)

Buduje zdarzenia przystankowe z VehiclePositions: epizody postoju ze statusem 1 (`STOPPED_AT`), łączone w kursach i przystankach (przerwa dłuższa niż `episode_gap_s` = 600 s zaczyna nowy epizod). Dla każdego zdarzenia liczy czas przyjazdu i odjazdu, niepewność czasu (odstęp do sąsiednich raportów pojazdu), dopasowuje rozkład z właściwej wersji GTFS, wyznacza datę obsługi i opóźnienia przyjazdu i odjazdu. Flagi `arr_ok` i `dep_ok` oznaczają niepewność do `unc_ok_s` = 30 s, `arr_ok` dodatkowo wyklucza pierwszy przystanek kursu.

Przetwarzanie przyrostowe (decyzja 8 w `docs/PLAN_REALIZACJI.md`):

- Dzień obsługi D jest liczony z partycji UTC D-1, D, D+1 (lokalna doba zaczyna się o 22:00/23:00 UTC poprzedniego dnia, kursy nocne kończą się po północy). Zachowywane są tylko zdarzenia z `service_date == D`.
- Odcisk wejść dnia w `manifest.json`: nazwy i rozmiary plików `part-*` z okna, wersja GTFS będąca właścicielem kalendarza dla D-1..D+1, progi z sekcji `events` configu, `PIPELINE_VERSION` (stała w `pipeline.py`, podbijana przy zmianie logiki). Przeliczane są tylko dni ze zmienionym odciskiem albo brakującym plikiem.
- Status i rola dnia są liczone od nowa przy każdym uruchomieniu z zapisanych statystyk, więc zmiana progów `days` albo `special_days.yaml` nie wymaga przeliczania zdarzeń.
- Statusy: `provisional` (brak danych do 04:00 lokalnego czasu doby D+1, np. ostatni dzień wgrania), `special` (z `special_days.yaml`), `gap` (przerwa w migawkach w godzinach 5–23 dłuższa niż 30 min albo mniej niż 500 zdarzeń), `complete`. Rola: `unassigned` do zamrożenia podziału w M3, potem `calib` / `valid` / `excluded`.
- Zapis atomowy (plik tymczasowy i zmiana nazwy), przerwane przeliczenie nie zostawia uszkodzonych plików.

```
uv run build-events             # tylko zmienione dni
uv run build-events --dry-run   # pokaz, co zostaloby przeliczone
uv run build-events --days 2026-10-07 2026-10-08   # wymus te dni
uv run build-events --full      # wszystko od zera
```

- Wejście: `data/raw_A/vehicle_positions`, wszystkie `data/raw_A/static/GTFS_KRK_A_*.zip`.
- Wyjście: `data/processed/events/YYYY-MM-DD.parquet` (m.in. `service_date`, `service_id`, `gtfs_stamp`, `arr_delay_s`, `dep_delay_s`, `arr_ok`, `dep_ok`), `days.csv`, `manifest.json`. Zdarzenia bez daty obsługi (kurs spoza wszystkich wersji rozkładu albo usługa nieaktywna wczoraj, dziś i jutro) nie trafiają do żadnego dnia.
- Pełne przeliczenie 12 dni: ~2,5 min; uruchomienie bez nowych danych: < 1 s; jeden nowy plik `part-*` przelicza 2–3 dni.

Do analiz: `from krakbus.observed.store import load_events` (domyślnie wszystkie dni `complete`).

## events-quality (`krakbus.observed.quality`)

Raport jakości wybranych dni (domyślnie 3 ostatnie `complete`, albo `--days ...`): rejestr dni, rozkład niepewności i opóźnień, odjazdy z pierwszego przystanku, pokrycie przystanków, udział powtórzonych pozycji, niezależna kontrola względem prognoz z TripUpdates, ekstremalne opóźnienia (|opóźnienie| > 6 h to kursy z innej doby, znany artefakt).

## gtfs_versions (`krakbus.ingest.gtfs_versions`)

Łączy wszystkie wersje rozkładu zapisane przez logger.

Feed ZTP jest kroczący: każda wersja zawiera kilka pokoleń usług z prefiksem daty w `service_id` i `trip_id` (np. `20261005_1_128936604_2`), a kalendarz jest tylko w `calendar_dates.txt`. Ten sam `trip_id` ma identyczne `stop_times` we wszystkich wersjach.

- Rozkład kursu: z najnowszej wersji, która zawiera dany `trip_id` (kolumna `gtfs_stamp`).
- Kalendarz dnia D: z najnowszej wersji, która ma jakikolwiek wpis na D (starsza wersja może jeszcze wymieniać usługi zastąpione przez nowszą).
- Data obsługi zdarzenia: kandydaci wczoraj, dziś i jutro względem lokalnej daty przyjazdu, tylko dni z aktywną usługą kursu; wygrywa najmniejsze |opóźnienie|, przy remisie dziś.
- Czasy GTFS liczone od „lokalne południe minus 12 h”, więc doba zmiany czasu (23 albo 25 h) nie przesuwa opóźnień.

Testy: `uv run pytest`.

## week_analysis.py

Pełna analiza zebranych danych, uruchamiana z linią pilotową jako argumentem (domyślnie 179). Domyślnie bierze wszystkie dni `complete` z `days.csv`; zbiór dni można wybrać ręcznie (dowolny status): `DAYS=2026-10-05,2026-10-06 uv run sandbox/gtfs-experiments/week_analysis.py 179`. Dzień roboczy jest uznany za pełny, gdy ma co najmniej 70% mediany liczby zdarzeń.

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

- Wejście: `data/processed/events/` przez `load_events`, `data/raw_A/vehicle_positions` (tylko kolumna `fetched_at`, do wykrywania dziur), wszystkie wersje GTFS (sekcja 2 liczy kursy wg kalendarza efektywnego danego dnia).
- Wyjście: wydruk na ekran, `data/processed/week_report/report.txt`, wykresy w `data/processed/week_report/figures/`.
