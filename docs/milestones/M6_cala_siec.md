# M6 — „Na 5” domknięte

**Najpóźniej:** 20.12.2026  
**Tory:** U + M  
**Wymaga:** M5 (wyniki do pokazania), tor U w fazach 1–3 ([U_unity_mcp.md](U_unity_mcp.md)), sensowny M4

## Cel

Spąć produkt demonstracyjny i rozszerzenie naukowe wymagane ścieżką „na 5” z `TEMAT.md`: Unity (replay + rzeczywistość ‖ symulacja) oraz szersza sieć z parametrami zbiorczymi / walidacją zagregowaną. Domknąć wizualizacje podstawowe.

## Co wchodzi w „na 5” (checklist produktowa)

### A. Unity MCP — pokaz

- [ ] Replay dnia roboczego (przyspieszenie, kolory opóźnienia)
- [ ] Rzeczywistość ‖ symulacja na uzgodnionym fragmencie
- [ ] Skrypt / README: jak odpalić demo (plik eksportu + Play)
- [ ] (Opcjonalnie) budynki w bbox korytarza
- [ ] (Opcjonalnie) przełączanie run_id scenariusza — tylko jeśli A już działa

Szczegóły zadań: [U_unity_mcp.md](U_unity_mcp.md).

### B. Szersza sieć (nie digital twin wszystkiego)

Cel z TEMAT: parametry zbiorcze + walidacja na wielkościach zagregowanych — nie każda linia MPK mikrokalibrowana.

- [ ] Zdefiniować „szerszą sieć”: np. top N linii wg liczby zdarzeń **lub** wszystkie linie dzielące odcinki z korytarzem + próbka zewnętrzna
- [ ] Parametry zbiorcze: wspólne rozkłady η / u / reguła pętli; ewentualnie route-level random effects uproszczone
- [ ] Walidacja zagregowana: rozkład opóźnień sieciowo, dryf średni, korelacja na wspólnych odcinkach (nie per-trip RMSE wszędzie)
- [ ] Krótka nota: co jest przeniesione z korytarza, co niedostrojone
- [ ] Limit świadomy: brak pełnego dopasowania każdej linii ≠ porażka, jeśli agregaty i uczciwe limity są w raporcie

### C. Wizualizacje podstawowe (spięcie)

- [ ] Mapa sieci z autobusami (kolor = opóźnienie) — matplotlib/plotly/pydeck
- [ ] Marey: observed vs simulated obok siebie
- [ ] Heatmapa kontagionu korytarza
- [ ] Krzywa pochłaniania na pętli (obs + sim)
- [ ] pydeck jako lekki 3D (nawet jeśli Unity jest głównym wow)

### D. Materiał pod M7 (wcześniej!)

- [ ] Folder `data/processed/figures/` lub `docs/figures/` z finalnymi PNG/HTML do raportu
- [ ] Lista 5–8 figurek „must have” na prezentację

## Definition of Done

- Da się pokazać Unity demo osobie z zewnątrz w <10 min setupu.
- Jest wynik „szerszej sieci” (agregaty + opis zakresu).
- Wizualizacje podstawowe istnieją jako pliki, nie tylko w notebooku w RAM.

## Pułapki

- „Cały Kraków w Unity” zjada M7 — trzymajcie bbox.
- Nie zaczynać interaktywnych scenariuszy kosztem replayu.
- Święta: M6 ma datę 20.12 właśnie po to, by M7 miało bufor.
