# M2 — DES pilota + graf całego miasta

**Najpóźniej:** 7.11.2026  
**Tor:** M (+ start U i N — [U_unity_mcp.md](U_unity_mcp.md), [N_siec_krakow.md](N_siec_krakow.md))  
**Wymaga:** sensowny graf/rozkład z GTFS (`gtfs_versions.load_schedule`); idealnie M1 Done (można zacząć szkielet wcześniej na syntetyce)  
**Status:** Done (16.10.2026). Spec: `docs/superpowers/specs/2026-10-16-m2-des-design.md`; plany etapów 1–3 w `docs/superpowers/plans/`. Parametry modelu robocze, kalibracja w M3.

## Cel

Działająca symulacja zdarzeń dyskretnych (SimPy): debug i testy na **179**, ale architektura od razu z **loaderem grafu i łańcuchów całego GTFS** oraz `scope=pilot|corridor|city`. Docelowo (M6) jedzie cała sieć — tu nie kalibrujemy miasta, tylko nie malujemy się w róg „hardcoded 179”.

## Wejście

- GTFS static (przestanki, stop_times, trips, shapes, block_id)
- Spec modelu z `TEMAT.md` (równania Δ, pętla, γ)
- (Preferowane) poprawione zdarzenia z M1 do sanity-checków jakościowych

## Wyjście

- Pakiet `src/krakbus/sim/` uruchamialny przez `uv run …` (komenda w `[project.scripts]`)
- `configs/` YAML (linia, dzień, ziarno, γ, ścieżki danych)
- Parquet/tabela wyników w schemacie zbliżonym do zdarzeń obserwowanych (`data/processed/events/`)
- Testy weryfikacyjne zielone
- Surowy Marey z symulacji (png/html)

## Kolejność

### A. Szkielet repo (można równolegle z końcówką M1)

- [x] Układ katalogów z `PLAN_REALIZACJI.md` (pakiet `src/krakbus/`, `configs/`, `tests/`); `gtfs_versions.py` przeniesiony do `src/krakbus/ingest/` razem z testami (16.10)
- [x] Zależności: `simpy` (`uv add simpy`); `pyyaml` już jest (16.10)
- [x] Logger zamiast `print` w `src/` (`krakbus.logger.setup_logging`, `logging.getLogger(...)` per moduł); progi w `configs/config.yaml` przez `krakbus.config.load_config`
- [x] Jedno wejście CLI: doba z parametrem `scope=pilot|corridor|city` (+ opcjonalnie lista `route_id`) — `uv run simulate --date --scope [--routes] [--seed]` (16.10)

### B. Graf sieci z GTFS

- [x] Wierzchołki = słupki (stop_id); krawędzie = odcinki kolejnych stop_sequence na tripie (`sim.network`, skierowane odcinki ze wspólnym `seg_id` dla wszystkich linii)
- [x] Bazowy czas przejazdu z rozkładu (różnica arrival/departure kolejnych przystanków)
- [x] Loader buduje graf dla **wszystkich** route_id; filtr scope tylko przy spawnieniu pojazdów
- [x] `scope=pilot` → 179 (oba `direction_id`) na testy
- [x] Smoke `scope=city` z γ=0 i zerowym/sztywnym szumem: czy w ogóle wstaje (14.10: 10 279 kursów, 218 738 zdarzeń, silnik 0,4 s; wczytanie rozkładu ok. 16 s)
- [x] Ładowanie łańcuchów: block_id → sekwencja tripów dnia (cała sieć), łańcuchy przechodzące między liniami zachowane w całości (flaga `cross_route` z M1 C)
- [x] Przy `scope` węższym niż city: kurs wjeżdżający do łańcucha z linii spoza scope dostaje opóźnienie startowe z warunku brzegowego (obserwowane albo z rozkładu empirycznego), a nie zero (`boundary: observed|delta`; korytarz 14.10: 27 kursów brzegowych)
- [x] **Decyzja: struktura przestrzenna `u`** — `independent` (16.10, `configs/sim.yaml`, spec `docs/superpowers/specs/2026-10-16-m2-des-design.md`) (niezależne odcinki vs korelacja sąsiednich odcinków / korytarza ulicznego) na podstawie analizy residuów z M1 D (16.10, sekcja 13 `week_analysis`: ten sam odcinek 0,29, sąsiedni 0,04, od 3 odcinków dalej tyle co losowe 0,005, co przemawia za `independent` ze wspólnym `u` na odcinku dzielonym przez linie); zapisać w configu (`u.spatial: independent|neighbors|corridor`) i uzasadnienie w `docs/`

### C. Silnik SimPy

- [x] Proces pojazdu: for trip in chain: for stop in trip: przyjazd → (postój) → odjazd → odcinek (postój rozkładowy, w GTFS ZTP zawsze 0)
- [x] Propagacja opóźnienia (bazowo):

  Δ_{s+1} = Δ_s + a_{p,s} + e_d + u_{d,h,s} + γ(h − h_rozk) + η

  z przełącznikami: na M2 wystarczy a, η, u uproszczone (np. stałe/losowe), γ=0 domyślnie
- [x] Reguła pętli:

  Δ_odj(i+) = max(Δ_koniec + ℓ_min − L, δ)

  δ z rozkładu empirycznego (placeholder OK, jeśli M1 jeszcze domyka krzywą)
- [x] Zegar symulacji = sekundy doby; ziarno w configu
- [x] Zapis zdarzeń (`data/processed/sim/<run_id>/events.parquet` + `run.json`): te same kluczowe kolumny co observed (`service_date`, `trip_id`, `stop_id`, `arr_ts`/`dep_ts` lub delay, `route_id`, `vehicle_id` / block)

### C2. Szybka ścieżka wektorowa (pod kalibrację)

Przy γ=0 pojazdy są niezależne poza łańcuchem i polem `u`, więc dobę da się policzyć rekursją po odcinkach w numpy (wszystkie kursy naraz, pętla tylko po pozycji w łańcuchu).

- [x] `sim.fast`: ta sama specyfikacja Δ i reguły pętli, wejście = te same tablice losowe co SimPy (wspólny generator szumu) — `uv run simulate --engine fast` (16.10)
- [x] Test równoważności: te same seedy → identyczne opóźnienia SimPy vs fast (tolerancja zaokrągleń) dla pilota i korytarza — 1e-6 s na syntetyce (w tym 40 bloków z przenoszeniem na pętli i zmianą linii) oraz na 14.10 dla pilota, korytarza i city
- [x] Przy γ>0 fast odmawia (wyjątek), żeby nikt cicho nie liczył sprzężenia od odstępu bez SimPy
- [x] Pomiar: czas doby pilota i city w obu ścieżkach (wejście do toru N B) — 14.10, sam silnik (`engine_s` w `run.json`): pilot SimPy 0,025 s, fast 0,013 s; city SimPy 0,30 s, fast 0,015 s. Całe polecenie ok. 16 s to wczytanie rozkładu.

### D. Testy weryfikacyjne

- [x] η=0, a=0, u=0, γ=0 → czasy = rozkład (z tolerancją zaokrągleń); też na 179 z prawdziwego GTFS
- [x] Opóźnienie < L − ℓ_min → pochłonięte; większe → przechodzi na następny kurs
- [x] Sam dryf a>0 → mediana rośnie wzdłuż trasy; rozrzut bez η nie eksploduje
- [x] Z η → std opóźnienia rośnie z numerem przystanku
- [x] To samo ziarno → bitowo / numerycznie reprodukowalne wyniki (szum losowany z góry; porównanie SimPy vs fast w C2)
- [x] γ=0 → brak wpływu sąsida poza łańcuchem i wspólnym u (gdy u wyłączone: pełna niezależność kursów poza pętlą)

### E. Wizualizacja kontrolna

- [x] Marey: czas vs pozycja na trasie dla kilku kursów z symulacji — `uv run marey 179 --sim <run_id>` (`krakbus.viz.marey`, 16.10)
- [x] (Opcjonalnie) nakładka na Marey z observed z tego samego „typu dnia” — obserwacja tego samego dnia co przebieg (obs niebieska, sim pomarańczowa)

### F. Most do Unity (minimalny)

- [x] Wywołanie eksportu zgodnego z kontraktem w [U_unity_mcp.md](U_unity_mcp.md) (nawet na syntetycznych pozycjach) — `uv run export-unity`, kontrakt v1 w [`../EXPORT_UNITY.md`](../EXPORT_UNITY.md)

## Definition of Done

- `scope=pilot` (179): pełna doba w rozsądnym czasie; testy z sekcji D zielone; Marey + wyniki.
- Loader obsługuje graf/łańcuchy całego GTFS, w tym łańcuchy międzyliniowe; CLI ma `scope` (city może być wolne, ale nie jest „niezaimplementowane”).
- Szybka ścieżka przechodzi test równoważności z SimPy.
- Decyzja o strukturze przestrzennej `u` zapisana.
- Tor U ma pierwszy eksport; tor N może zacząć coverage / batche.

## Pułapki

- Nie kalibrować parametrów w M2 — tu chodzi o poprawność mechaniki.
- Nie hardcodować 179 w środku silnika (tylko w configu scope).
- Nie blokować M2 na perfekcyjnym M1: szkielet i testy zerowego szumu idą na samym GTFS.
- Dwie ścieżki obliczeń bez testu równoważności = dwa różne modele; test jest warunkiem użycia fast w kalibracji.
