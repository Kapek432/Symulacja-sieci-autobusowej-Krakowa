# M5 — Scenariusze „co by było, gdyby”

**Najpóźniej:** 12.12.2026  
**Tor:** M  
**Wymaga:** M4 (korytarz + zaufanie do modelu na tyle, by interpretować efekty)

## Cel

Odpowiedzi na pytania badawcze z `TEMAT.md` przez kontrolowane eksperymenty: 3 scenariusze oparte na danych + 2 warunkowe, z replikacjami i CI.

## Wejście

- Skalibrowany model korytarza
- Configi bazowe z M3/M4

## Wyjście

- `configs/scenarios/*.yaml`
- Tabele efektów (metryka × scenariusz × CI)
- Jedno zdanie „do opowiedzenia” na prezentację
- Krótki rozdział wrażliwości dla scenariuszy warunkowych

## Scenariusze

### Oparte na danych (główne)

| ID | Scenariusz | Dźwignia w modelu | Wskaźniki |
|----|------------|-------------------|-----------|
| S1 | Zapas na pętli | skaluj `L` (np. ×0.5, ×1.0, ×1.5) lub +/− stała | pochłonięte opóźnienie, rozrzut wzdłuż trasy, przenoszenie |
| S2 | Zakłócenie na korytarzu | skok / podwyższone `u` na odcinkach wspólnych przez T minut | macierz kontagionu, czas powrotu do normy |
| S3 | Częstotliwość | usuń/dodaj kursy w łańcuchach (spójnie z block_id) | rozrzut, czas oczekiwania W |

### Warunkowe (efekt = założenie)

| ID | Scenariusz | Założenie | Wskaźniki |
|----|------------|-----------|-----------|
| S4 | Przytrzymywanie | holding do rozkładu lub wg odstępu (parametr siły) | W pasażera, czas przejazdu |
| S5 | Priorytet / pas | mniejsza var η lub mniejszy a na odcinkach „z priorytetem” | opóźnienie, nachylenie rozrzutu |

Dla S4/S5: siatka 2–3 wartości założenia + wykres wrażliwości.

## Kolejność

### A. Infrastruktura eksperymentów

- [ ] YAML scenariusza: nazwa, seed bazowy, N replikacji, override parametrów, linie, dzień typowy
- [ ] Runner: N runów, wspólne losowe strumienie do porównań (CRN jeśli możliwe)
- [ ] Agregacja → parquet wyników + tabela summary
- [ ] N = 30 minimum; cel 50–100 jeśli wydajność pozwala

### B. Metryki

- [ ] Opóźnienie: mediana, p90
- [ ] Rozrzut / σ_e (slope jeśli liczony)
- [ ] Pochłonięte opóźnienie na pętli
- [ ] Kontagion (korelacje / macierz między liniami na korytarzu)
- [ ] Oczekiwany czas oczekiwania: W = E[h]/2 * (1 + CV_h²)
- [ ] CI (bootstrap lub percentyle z replikacji)

### C. Uruchomienia

- [ ] S1, S2, S3 na korytarzu
- [ ] S4, S5 z wrażliwością
- [ ] Baseline = model bazowy bez interwencji (te same seed’y)

### D. Narracja

- [ ] Uzupełnić szablon: „Pętla resetuje X% opóźnienia; najlepsza interwencja obniża rozrzut o Y% kosztem Z”
- [ ] Oddzielić wnioski twarde (S1–S3) od warunkowych (S4–S5)

## Definition of Done

- Pięć scenariuszy policzonych z CI.
- Tabele + jedno zdanie prezentacyjne.
- Scenariusze warunkowe opisane jako warunkowe.

## Pułapki

- Zmiana częstotliwości bez przebudowy łańcuchów = niespójne block_id.
- Jedna replikacja = nie wyniki.
- Nie sprzedawać S4/S5 jako „empirycznie zmierzone efekty priorytetu”.
