# M2 — DES pilota z łańcuchami

**Najpóźniej:** 7.11.2026  
**Tor:** M (+ start toru U — patrz [U_unity_mcp.md](U_unity_mcp.md))  
**Wymaga:** sensowny graf/rozkład z GTFS; idealnie M1 Done (można zacząć szkielet wcześniej na syntetyce)

## Cel

Działająca symulacja zdarzeń dyskretnych (SimPy): pojazd = proces realizujący łańcuch kursów linii 179 (oba kierunki), z regułą pętli i wyjściem porównywalnym 1:1 z `observed_events`.

## Wejście

- GTFS static (przestanki, stop_times, trips, shapes, block_id)
- Spec modelu z `TEMAT.md` (równania Δ, pętla, γ)
- (Preferowane) poprawione zdarzenia z M1 do sanity-checków jakościowych

## Wyjście

- Pakiet `src/sim/` uruchamialny przez `uv run …`
- `configs/` YAML (linia, dzień, ziarno, γ, ścieżki danych)
- Parquet/tabela wyników w schemacie zbliżonym do `observed_events`
- Testy weryfikacyjne zielone
- Surowy Marey z symulacji (png/html)

## Kolejność

### A. Szkielet repo (można równolegle z końcówką M1)

- [ ] Układ katalogów z `PLAN_REALIZACJI.md` (`src/`, `configs/`, `tests/`)
- [ ] Zależności: `simpy`, ewentualnie `pyyaml`; `uv add …`
- [ ] Logger zamiast `print` w `src/` (`logging.getLogger(__name__)`)
- [ ] Jedno wejście CLI / moduł: „uruchom dobę pilota”

### B. Graf sieci z GTFS

- [ ] Wierzchołki = słupki (stop_id); krawędzie = odcinki kolejnych stop_sequence na tripie
- [ ] Bazowy czas przejazdu z rozkładu (różnica arrival/departure kolejnych przystanków)
- [ ] Filtrowanie do route 179 (oba `direction_id`) na start
- [ ] Ładowanie łańcuchów: block_id → sekwencja tripów dnia

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

- `uv run …` odpala pełną dobę 179 w rozsądnym czasie (orientacyjnie: minuty, nie godziny).
- Testy z sekcji D przechodzą.
- Jest plik wyników + Marey.
- Tor U może podłączyć pierwszy replay.

## Pułapki

- Nie kalibrować parametrów w M2 — tu chodzi o poprawność mechaniki.
- Nie budować od razu całego korytarza (to M4).
- Nie blokować M2 na perfekcyjnym M1: szkielet i testy zerowego szumu idą na samym GTFS.
