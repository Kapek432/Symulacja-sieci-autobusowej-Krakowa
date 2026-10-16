# Tor U — Unity MCP (równolegle M2 → M6)

**Start:** wraz z M2 (można wcześniej na mocku)  
**Domknięcie produktowe:** M6 (20.12.2026)  
**Narzędzie:** **Unity MCP** — scena, obiekty, smoke-testy i iteracje z agenta; nie „ręcznie wszystko w Editorze bez kontraktu danych”.

## Cel

Odtwarzanie wyników symulacji (i obserwacji) w Unity: replay dnia, potem rzeczywistość ‖ symulacja. Symulacja zostaje w Pythonie.

## Zasada priorytetu

Przy konflikcie z D/M/N: **nie kasujemy Unity**. Model/sieć mają pierwszeństwo przy debugu kalibracji, ale tor U idzie równolegle na eksporcie (najpierw korytarz, potem downsamplowany city). Zakresu nie ucinamy.

## Kontrakt eksportu (zróbcie wcześnie)

Wspólny schemat (Parquet lub JSON Lines), np.:

| Pole | Znaczenie |
|------|-----------|
| `t` / `sim_time_s` | czas od północy lub epoch |
| `vehicle_id` / `trip_id` | identyfikator |
| `lat`, `lon` albo `shape_dist` + `shape_id` | pozycja |
| `delay_s` | opóźnienie (kolor) |
| `source` | `sim` \| `obs` |
| `run_id`, `seed` | reprodukowalność |

- [ ] Opisać kontrakt w `docs/` lub `src/viz/EXPORT.md` (1 strona)
- [ ] Exporter w Pythonie (`src/viz/export_unity.py` lub podobny)
- [ ] Jedna próbka pliku w `data/processed/unity_samples/` (mała, do gita OK jeśli bez surowego feedu)
- [ ] Wersjonowanie schematu (`schema_version: 1`)

## Backlog Unity MCP

### Faza 1 — scena i smoke (‖ M2)

- [ ] Projekt Unity w repo (albo podkatalog uzgodniony; duże Library/ w gitignore)
- [ ] Przez Unity MCP: pusta scena + obiekt „Bus” + kamera
- [ ] Loader pliku eksportu (Editor play mode / runtime)
- [ ] Pojazd jedzie po polyline trasy 179 (z shapes lub uproszczonych punktów)
- [ ] Kolor / materiał zależny od `delay_s`
- [ ] Smoke-test: załadowanie sample → 1 autobus się rusza

### Faza 2 — replay dnia (‖ M3–M4)

- [ ] Wiele pojazdów naraz
- [ ] Suwak czasu / przyspieszenie (×10, ×60)
- [ ] Etykieta czasu symulacji
- [ ] Podmiana sample → pełny eksport z DES

### Faza 3 — rzeczywistość ‖ symulacja (‖ M4–M5)

- [ ] Dwa źródła (`source=obs` i `source=sim`) zsynchronizowane tym samym zegarem
- [ ] Rozróżnialne wizualnie (np. dwa odcienie / outline)
- [ ] Co najmniej jedna linia / jeden korytarz do pokazu

### Faza 4 — kontekst miasta (po replayu)

- [ ] Import budynków (Geoportal LoD1 lub OSM) — uproszczenie OK
- [ ] Performance wizualizacji: bbox / LOD; **dane city-wide** mogą być downsamplowane (nie mylić z modelem — model ma jechać całą sieć w Pythonie)
- [ ] Opcja: warstwa „cała sieć” jako uproszczone trajektorie + szczegół na korytarzu

### Faza 5 — interakcja (tylko jeśli Fazy 1–3 Done i raport nie płonie)

- [ ] Proste przełączanie scenariusza / run_id z wyeksportowanych plików
- [ ] Nie budować pełnego UI „co by było gdyby” w Unity, jeśli pydeck + wykresy wystarczą do ocen

## Definition of Done (tor U na poziomie M6)

- Live demo: replay dnia z kolorami opóźnienia przez Unity, sterowane danymi z Pythona.
- Rzeczywistość ‖ symulacja działa na uzgodnionym fragmencie sieci.
- Zespół umie odtworzyć demo z README (ścieżka pliku + Play).

## Pułapki

- Nie trzymać logiki modelu w C# — tylko wizualizacja.
- Nie czekać z kontraktem eksportu na „idealną kalibrację”.
- Duże assety / Library Unity: gitignore; w repo tylko projekt + skrypty + małe sample.
