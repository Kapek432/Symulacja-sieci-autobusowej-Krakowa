# M5 — Scenariusze „co by było, gdyby”

**Najpóźniej:** 12.12.2026  
**Tor:** M  
**Wymaga:** M4 (korytarz + postęp city); parametry per linia z rejestru N w miarę dostępności

## Cel

Odpowiedzi na pytania badawcze z `TEMAT.md` przez kontrolowane eksperymenty: 3 scenariusze oparte na danych + 2 warunkowe, z replikacjami i CI. **S2/S3 także w wariancie sieciowym** (`scope=city` lub duży subset), nie tylko korytarz.

## Wejście

- Model korytarza + dostępny rejestr city (nawet niepełny — wtedy subset)
- Configi bazowe z M3/M4/N

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
| S2 | Zakłócenie na korytarzu **i** hotspot city | skok / podwyższone `u` na odcinkach wspólnych przez T minut | macierz kontagionu, czas powrotu do normy |
| S3 | Częstotliwość (korytarz + wybrana linia/sieć) | usuń/dodaj kursy w łańcuchach (spójnie z block_id) | rozrzut, czas oczekiwania W |

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
- [ ] S2 (i jeśli perf pozwala S3) na `scope=city` / dużym subsecie z parametrami per linia; zakłócenie rozchodzi się zgodnie ze strukturą przestrzenną `u` z decyzji M2 (opisać w wynikach, bo od niej zależy zasięg kontagionu)
- [ ] S4, S5 z wrażliwością (korytarz wystarczy, jeśli city za drogie — ale nie wykreślamy S2 city)
- [ ] Baseline = model bazowy bez interwencji (te same seed’y)

### D. Narracja

- [ ] Uzupełnić szablon: „Pętla resetuje X% opóźnienia; najlepsza interwencja obniża rozrzut o Y% kosztem Z”
- [ ] Oddzielić wnioski twarde (S1–S3) od warunkowych (S4–S5)

## Definition of Done

- Pięć scenariuszy policzonych z CI (korytarz).
- S2 (preferowane też S3) ma wariant na szerszej / pełnej sieci.
- Tabele + jedno zdanie prezentacyjne.
- Scenariusze warunkowe opisane jako warunkowe.

## Pułapki

- Zmiana częstotliwości bez przebudowy łańcuchów = niespójne block_id (także w łańcuchach międzyliniowych).
- Scenariusze w korytarzu z linią spoza scope w łańcuchu: warunek brzegowy z rozkładu empirycznego, nie z obserwacji konkretnego dnia (inaczej scenariusz „wie”, co się stało).
- Jedna replikacja = nie wyniki.
- Nie sprzedawać S4/S5 jako „empirycznie zmierzone efekty priorytetu”.
