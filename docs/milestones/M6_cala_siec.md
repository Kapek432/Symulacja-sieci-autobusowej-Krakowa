# M6 — Cały Kraków + Unity

**Najpóźniej:** 20.12.2026  
**Tory:** N + U + M  
**Wymaga:** M4–M5, tor N blisko 100% coverage, tor U fazy 1–3 ([U_unity_mcp.md](U_unity_mcp.md), [N_siec_krakow.md](N_siec_krakow.md))

## Cel

**Produkt końcowy modelu:** symulacja **całej autobusowej sieci Krakowa** z **kalibracją per linia** + pokaz Unity (replay, rzeczywistość ‖ symulacja) + spięte wizualizacje. Bez redukcji do parametrów wyłącznie zbiorczych i bez ucinania Unity.

## Checklist produktowa

### A. Sieć city-wide (tor N — obowiązkowe)

- [ ] `scope=city`: pełna doba, wszystkie aktywne linie
- [ ] Rejestr parametrów per `route_id` (coverage 100% wg [N](N_siec_krakow.md))
- [ ] Raport coverage + metryki per linia (obs vs sim)
- [ ] Walidacja sieciowa: agregaty + próbka per-route OOS (dzień hold-out); w raporcie oddzielnie: leave-line-out (walidacja przestrzenna) i fit per linia (dopasowanie)
- [ ] Wspólne `u` na współdzielonych odcinkach w skali miasta (sanity korelacji)

### B. Unity MCP — pokaz

- [ ] Replay dnia (przyspieszenie, kolor = opóźnienie)
- [ ] Rzeczywistość ‖ symulacja (fragment lub downsamplowana sieć)
- [ ] README: jak odpalić demo
- [ ] Budynki w bbox (korytarz lub centrum) — po działającym replayu
- [ ] Opcjonalnie: przełączanie `run_id` scenariusza

Szczegóły: [U_unity_mcp.md](U_unity_mcp.md).

### C. Wizualizacje podstawowe

- [ ] Mapa sieci (city lub gęsty subset) — kolor opóźnienia
- [ ] Marey obs vs sim (pilot + 1–2 inne linie)
- [ ] Heatmapa kontagionu (korytarz; opcjonalnie hotspoty city)
- [ ] Krzywa pochłaniania na pętli
- [ ] pydeck jako lekki 3D obok Unity

### D. Materiał pod M7

- [ ] `data/processed/figures/` / `docs/figures/` — finalne assety
- [ ] 5–8 figurek must-have + 1 ścieżka demo Unity
- [ ] Jedno zdanie wyniku sieciowego (opóźnienie / kontagion / efekt pętli)

## Definition of Done

- Cała aktywna sieć autobusowa jeździ w DES z parametrami per linia.
- Unity demo odtwarzalne z README.
- Wizualizacje jako pliki na dysku.
- Brak ukrytego „zostawiliśmy pół miasta na parametry globalne bez rekordu per line”.

## Pułapki

- Perf: downsampluj eksport do Unity, nie model.
- Linie `low_n`: jawny pooling w coverage, nadal w sim.
- Po 20.12 tylko poprawki pod M7 — nie nowe epiki sieci.
