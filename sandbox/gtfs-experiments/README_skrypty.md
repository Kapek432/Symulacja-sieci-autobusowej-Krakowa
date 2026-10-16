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
      chains/YYYY-MM-DD.parquet    <- lancuchy kursow pojazdow per data obslugi
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
4. `uv run route-ranking` - ranking linii (`data/processed/route_ranking.csv`).
5. `uv run propose-split` - robocza propozycja podziału dni (`data/processed/days_split_proposal.yaml`).
6. `week_analysis.py` - pełny raport na dniach `complete`; `uv run marey` - wykres Mareya jednej linii (opcjonalnie z nakładką symulacji).
7. `uv run simulate` - doba w DES (M2) dla zakresu linii.
8. `uv run export-unity` - przebieg symulacji albo obserwacja dnia dla Unity.

```
uv run build-events
uv run events-quality
uv run route-ranking
uv run propose-split
uv run simulate --date 2026-10-14 --scope pilot
uv run sandbox/gtfs-experiments/week_analysis.py 179
uv run marey 179 2026-10-14
uv run marey 179 --sim 2026-10-14_pilot_simpy_s0
uv run export-unity --sim 2026-10-14_pilot_simpy_s0
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
- Wyjście: `data/processed/events/YYYY-MM-DD.parquet` (m.in. `service_date`, `service_id`, `gtfs_stamp`, `arr_delay_s`, `dep_delay_s`, `arr_ok`, `dep_ok`, `rt_trip_id`, `trip_remapped`, `delay_class`, `arr_good`, `dep_good`), `data/processed/chains/YYYY-MM-DD.parquet`, `days.csv`, `manifest.json`. Zdarzenia bez daty obsługi, których nie udało się przepiąć (kurs spoza wszystkich wersji rozkładu), nie trafiają do żadnego dnia.
- Kurs z niewłaściwej doby (`krakbus.observed.wrong_day`): RT czasem podaje `trip_id` z usługi innego dnia tygodnia, następnego pokolenia albo usługi nieaktywnej w żadnym dniu (noc 9→10.10, `20261010_4`). Faktyczną dobę liczę z obserwacji: lokalna data `arr_ts − arr_s + 12 h`. Jeśli kurs pojazdu nie ma daty obsługi albo mediana |opóźnienia| > `wrong_day_min_s` (12 h), a faktyczna doba jest inna, kurs jest przepinany na bliźniaka: ta sama linia, kierunek i godzina startu, identyczne `stop_times`, usługa aktywna w faktycznej dobie. Oryginał zostaje w `rt_trip_id`, przepięcie oznacza `trip_remapped`.
- Jeden filtr jakości: `delay_class` = `ok` / `outlier` (|`arr_delay_s`| > `outlier_s` = 1800 s) / `wrong_service_day` (> 12 h, bez bliźniaka), brak przy braku opóźnienia. `arr_good` = `arr_ok` i `ok`; `dep_good` = `dep_ok`, |`dep_delay_s`| ≤ 1800 s i nie `wrong_service_day`. Analizy opóźnień powinny filtrować po tych flagach zamiast własnych progów.
- Łańcuchy (`krakbus.observed.chains`): jeden wiersz na kurs pojazdu w dobie, w kolejności zaobserwowanej (`chain_idx`), z następnym kursem pojazdu, zapasem rozkładowym na pętli (`layover_sched_s`), opóźnieniem na końcu kursu (`arr_end_delay_s`) i na odjeździe następnego (`next_dep_first_delay_s`), flagami `follows_block` (następny kurs = następny w `block_id`), `cross_route` (następny kurs na innej linii) i `carried` (opóźnienie > zapas − `l_min_s`). Opóźnienia surowe, bez filtra outlierów.
- Pełne przeliczenie 12 dni: ~2,5 min; uruchomienie bez nowych danych: < 1 s; jeden nowy plik `part-*` przelicza 2–3 dni.

Do analiz: `from krakbus.observed.store import load_events, load_chains` (domyślnie wszystkie dni `complete`).

## events-quality (`krakbus.observed.quality`)

Raport jakości wybranych dni (domyślnie 3 ostatnie `complete`, albo `--days ...`): rejestr dni, rozkład niepewności i opóźnień, odjazdy z pierwszego przystanku, pokrycie przystanków, udział powtórzonych pozycji, niezależna kontrola względem prognoz z TripUpdates, łańcuchy (zgodność z `block_id`, udział `cross_route` per linia, reset X i przenoszenie na pętli z tymi samymi filtrami co sekcja 6 `week_analysis`), ekstremalne opóźnienia (|opóźnienie| > 6 h to kursy z innej doby, znany artefakt).

## route-ranking (`krakbus.observed.routes`)

Ranking linii pod batche toru N, domyślnie z pełnych dni roboczych (albo `--days ...`). Liczy zdarzenia `arr_good`. Kolumny: `rank`, `route_id`, `n_events`, `events_per_day`, `cum_share_events` (udział zdarzeń sieci pokryty do tej pozycji), `n_days`, `n_trips`, `n_vehicles`, `med_delay_s`, `p90_delay_s`, `n_transitions`, `cross_route_share`, `carried_share` (z łańcuchów, tylko kursy z zaobserwowanym następnym kursem pojazdu).

## propose-split (`krakbus.observed.split`)

Robocza propozycja podziału dni `complete` na `calib` i `valid`. Warstwy to typ dnia (roboczy, sobota, niedziela) × pokolenie rozkładu (dominujący prefiks `service_id` dnia). W każdej warstwie dni walidacyjne (`days.valid_fraction`) są rozłożone równomiernie w czasie. Wynik `data/processed/days_split_proposal.yaml` ma format `configs/days_split.yaml`; zamrożenie w M3 to skopiowanie go do configs. Dni bez statusu `complete` nie trafiają do `excluded`, bo wyklucza je sam status (dzień `provisional` po kolejnym wgraniu staje się pełny).

## simulate (`krakbus.sim.run`)

Doba obsługi w symulacji zdarzeń dyskretnych (SimPy), parametry w `configs/sim.yaml` (spec: `docs/superpowers/specs/2026-10-16-m2-des-design.md`). Sieć dnia jest budowana z całego GTFS (wszystkie linie aktywne w efektywnym kalendarzu, bloki z `block_id`), zakres wybiera tylko kursy do symulacji: `pilot` (179), `corridor` (179, 169, 174, 173, 144, 124), `city` (wszystko) albo jawna lista `--routes`. Pojazd jedzie cały blok z planu; kurs, którego poprzednik w bloku jest spoza zakresu, startuje z opóźnieniem z warunku brzegowego (`boundary: observed` = opóźnienie na końcu poprzednika z `chains/` dnia przez regułę pętli, brak obserwacji albo `delta` = losowe δ). Szum losowany z góry z ziarna, `u` wspólne dla linii na tym samym skierowanym odcinku, niezależne między odcinkami, AR(1) po oknach 900 s. Parametry modelu robocze (kalibracja w M3).

```
uv run simulate --date 2026-10-14 --scope pilot
uv run simulate --date 2026-10-14 --scope corridor --seed 3
uv run simulate --date 2026-10-14 --routes 704 503
uv run simulate --date 2026-10-14 --scope city --engine fast
```

- Silniki: `simpy` (referencyjny, jedyny z γ ≠ 0) i `fast` (numpy, tylko γ = 0; ten sam wynik do 1e-6 s na tych samych ziarnach, sprawdzane testem). `run.json` ma `engine_s` (sam silnik) i `elapsed_s` (cały przebieg bez wczytania rozkładu).

- Wejście: `data/raw_A/static`, opcjonalnie `data/processed/chains/<dzień>.parquet`.
- Wyjście: `data/processed/sim/<dzień>_<zakres>_<silnik>_s<ziarno>/events.parquet` (`service_date`, `vehicle_id` = klucz bloku, `trip_id`, `route_id`, `direction_id`, `stop_sequence`, `stop_id`, `arr_s`, `dep_s`, `arr_ts`, `dep_ts`, `arr_delay_s`, `dep_delay_s`, `source` = `sim`, `run_id`, `seed`) i `run.json` (parametry, liczby kursów, wersje GTFS, hash manifestu, commit).
- Czas 14.10 (sam silnik): city 10 279 kursów SimPy 0,30 s, fast 0,015 s; całe polecenie ok. 16 s, prawie tylko wczytanie rozkładu.

## marey (`krakbus.viz.marey`)

`uv run marey [linia] [YYYY-MM-DD] [--sim RUN_ID] [--no-obs]` (domyślnie 179 i ostatni pełny dzień roboczy, a przy `--sim` dzień przebiegu). Jeden panel na kierunek; oś pionowa to odległość wzdłuż najczęstszego wariantu trasy (proste między przystankami, bo feed nie ma `shape_dist_traveled`). Rozkład kursów obecnych na wykresie jest szary. Sama obserwacja (`delay_class` = ok) jest kolorowana wg pojazdu; z `--sim` obserwacja jest niebieska, symulacja pomarańczowa (legenda). Wynik `data/processed/week_report/figures/marey_<linia>_<dzień>[_<run_id>].png`. `sandbox/gtfs-experiments/marey.py` to nakładka na tę komendę (te same argumenty).

## export-unity (`krakbus.viz.export_unity`)

Przyjazdy i odjazdy przebiegu symulacji (`--sim RUN_ID`) albo obserwacji dnia (`--obs --date D`) jako wiersze ze współrzędnymi przystanku dla Unity; kontrakt i zasady odtwarzania w `docs/EXPORT_UNITY.md` (`schema_version` 1). Opcje: `--routes ...`, `--format parquet|jsonl`, `--out DIR`. Wynik w `data/processed/unity_samples/`: `<nazwa>.parquet|jsonl` i `<nazwa>.meta.json`. Pilot 14.10: 12 054 wiersze symulacji (2 na zdarzenie), 10 950 wierszy obserwacji.

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
12. Bootstrap klastrowy (B = 200): CI dla dryfu mediany, ilorazu rozrzutu, resetu X i przenoszenia OLS.
13. Struktura przestrzenna u: korelacja residuów przyrostów między liniami na tym samym odcinku, odcinkach odległych o k i losowych w tym samym oknie 15 min.

Filtry: zdarzenia `arr_good`, odjazdy `dep_good` (bez własnych progów outlierów). Na końcu drukuje listę kluczowych liczb do projektu.

- Wejście: `data/processed/events/` przez `load_events`, `data/raw_A/vehicle_positions` (tylko kolumna `fetched_at`, do wykrywania dziur), wszystkie wersje GTFS (sekcja 2 liczy kursy wg kalendarza efektywnego danego dnia).
- Wyjście: wydruk na ekran, `data/processed/week_report/report.txt`, wykresy w `data/processed/week_report/figures/`.
