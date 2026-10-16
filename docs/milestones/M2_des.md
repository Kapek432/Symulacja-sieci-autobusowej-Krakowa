# M2 — DES pilota + graf całego miasta

**Najpóźniej:** 7.11.2026  
**Tor:** M (+ start U i N — [U_unity_mcp.md](U_unity_mcp.md), [N_siec_krakow.md](N_siec_krakow.md))  
**Wymaga:** sensowny graf/rozkład z GTFS (`gtfs_versions.load_schedule`); idealnie M1 Done (można zacząć szkielet wcześniej na syntetyce)

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
- [ ] Zależności: `simpy` (`uv add simpy`); `pyyaml` już jest
- [x] Logger zamiast `print` w `src/` (`krakbus.logger.setup_logging`, `logging.getLogger(...)` per moduł); progi w `configs/config.yaml` przez `krakbus.config.load_config`
- [ ] Jedno wejście CLI: doba z parametrem `scope=pilot|corridor|city` (+ opcjonalnie lista `route_id`)

### B. Graf sieci z GTFS

- [ ] Wierzchołki = słupki (stop_id); krawędzie = odcinki kolejnych stop_sequence na tripie
- [ ] Bazowy czas przejazdu z rozkładu (różnica arrival/departure kolejnych przystanków)
- [ ] Loader buduje graf dla **wszystkich** route_id; filtr scope tylko przy spawnieniu pojazdów
- [ ] `scope=pilot` → 179 (oba `direction_id`) na testy
- [ ] Smoke `scope=city` z γ=0 i zerowym/sztywnym szumem: czy w ogóle wstaje (może być wolne — OK, profil pod N)
- [ ] Ładowanie łańcuchów: block_id → sekwencja tripów dnia (cała sieć), łańcuchy przechodzące między liniami zachowane w całości (flaga `cross_route` z M1 C)
- [ ] Przy `scope` węższym niż city: kurs wjeżdżający do łańcucha z linii spoza scope dostaje opóźnienie startowe z warunku brzegowego (obserwowane albo z rozkładu empirycznego), a nie zero
- [ ] **Decyzja: struktura przestrzenna `u`** (niezależne odcinki vs korelacja sąsiednich odcinków / korytarza ulicznego) na podstawie analizy residuów z M1 D; zapisać w configu (`u.spatial: independent|neighbors|corridor`) i uzasadnienie w `docs/`

### C. Silnik SimPy

- [ ] Proces pojazdu: for trip in chain: for stop in trip: przyjazd → (postój) → odjazd → odcinek
- [ ] Propagacja opóźnienia (bazowo):

  Δ_{s+1} = Δ_s + a_{p,s} + e_d + u_{d,h,s} + γ(h − h_rozk) + η

  z przełącznikami: na M2 wystarczy a, η, u uproszczone (np. stałe/losowe), γ=0 domyślnie
- [ ] Reguła pętli:

  Δ_odj(i+) = max(Δ_koniec + ℓ_min − L, δ)

  δ z rozkładu empirycznego (placeholder OK, jeśli M1 jeszcze domyka krzywą)
- [ ] Zegar symulacji = sekundy doby; ziarno w configu
- [ ] Zapis zdarzeń: te same kluczowe kolumny co observed (`service_date`, `trip_id`, `stop_id`, `arr_ts`/`dep_ts` lub delay, `route_id`, `vehicle_id` / block)

### C2. Szybka ścieżka wektorowa (pod kalibrację)

Przy γ=0 pojazdy są niezależne poza łańcuchem i polem `u`, więc dobę da się policzyć rekursją po odcinkach w numpy (wszystkie kursy naraz, pętla tylko po pozycji w łańcuchu).

- [ ] `sim.fast`: ta sama specyfikacja Δ i reguły pętli, wejście = te same tablice losowe co SimPy (wspólny generator szumu)
- [ ] Test równoważności: te same seedy → identyczne opóźnienia SimPy vs fast (tolerancja zaokrągleń) dla pilota i korytarza
- [ ] Przy γ>0 fast odmawia (wyjątek), żeby nikt cicho nie liczył sprzężenia od odstępu bez SimPy
- [ ] Pomiar: czas doby pilota i city w obu ścieżkach (wejście do toru N B)

### D. Testy weryfikacyjne

- [ ] η=0, a=0, u=0, γ=0 → czasy = rozkład (z tolerancją zaokrągleń)
- [ ] Opóźnienie < L − ℓ_min → pochłonięte; większe → przechodzi na następny kurs
- [ ] Sam dryf a>0 → mediana rośnie wzdłuż trasy; rozrzut bez η nie eksploduje
- [ ] Z η → std opóźnienia rośnie z numerem przystanku
- [ ] To samo ziarno → bitowo / numerycznie reprodukowalne wyniki
- [ ] γ=0 → brak wpływu sąsida poza łańcuchem i wspólnym u (gdy u wyłączone: pełna niezależność kursów poza pętlą)

### E. Wizualizacja kontrolna

- [ ] Marey: czas vs pozycja na trasie dla kilku kursów z symulacji
- [ ] (Opcjonalnie) nakładka na Marey z observed z tego samego „typu dnia”

### F. Most do Unity (minimalny)

- [ ] Wywołanie eksportu zgodnego z kontraktem w [U_unity_mcp.md](U_unity_mcp.md) (nawet na syntetycznych pozycjach)

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
