# M7 — Raport, odtwarzalność, oddanie

**Najpóźniej:** 31.12.2026  
**Tor:** wszyscy  
**Wymaga:** artefakty M3–M6; draft można zacząć wcześniej (zalecane od M4)

## Cel

Oddawalny pakiet: raport końcowy, repo odtwarzalne, prezentacja / FAQ. Bez dopisywania nowych feature’ów — tylko domknięcie i poprawki.

## Wyjście

- Raport PDF/MD (uzgodnić format z zajęciami)
- `README.md` z instrukcją end-to-end
- Zamrożona konfiguracja runów (YAML + seed + wersje)
- Slajdy lub konspekt prezentacji
- (Opcjonalnie) nagranie 2–3 min Unity demo

## Kolejność

### A. Raport — szkielet treści

- [ ] Cel i pytania badawcze (z TEMAT, bez rozdmuchiwania)
- [ ] Dane: GTFS + GTFS-RT, okres, luki, match wersji rozkładu
- [ ] Model: opis ODD-like (encje, procesy, skala, wejścia/wyjścia, stochastyka)
- [ ] Weryfikacja (testy M2)
- [ ] Kalibracja (S, metoda, parametry, γ)
- [ ] Walidacja (OOS, ablacje, baseline’y) — osobno „z konstrukcji” vs nietrywialne
- [ ] Scenariusze + wrażliwość warunkowych
- [ ] Unity / viz (co pokazano)
- [ ] Ograniczenia i ryzyka (γ≈0, długość zbierania, założenia S4/S5, słabe średnie przenoszenie)
- [ ] Wnioski — odpowiedzi 1:1 na pytania badawcze

### B. Odtwarzalność

- [ ] `README.md`: wymagania, `uv sync`, gdzie dane, jak zbudować events, jak odpalić sim, calib (skrót), scenariusze, eksport Unity
- [ ] Jedno „główne” polecenie lub krótki skrypt `scripts/reproduce_core.sh` (nawet jeśli pełna kalibracja trwa długo — wtedy reproduce na zamrożonych artefaktach)
- [ ] Wersje zależności (`uv.lock`)
- [ ] Jakie dane muszą być lokalnie (raw niepubliczny) vs co jest w `processed/` do odtworzenia wykresów

### C. Prezentacja

- [ ] Konspekt: problem → dane → model (łańcuchy + u) → wynik walidacji → scenariusze → Unity
- [ ] FAQ przygotowane:
  - Dlaczego to nie „rozkład + szum”?
  - Co z γ / zbijaniem?
  - Czy łańcuchy mają efekt przy dużym zapasie?
  - Co jest założeniem w scenariuszach warunkowych?
  - Jak krótki okres danych ogranicza wnioski?
- [ ] Próbna prezentacja wewnątrz zespołu (timer)

### D. Freeze

- [ ] Tag / commit „submission” (gdy będziecie gotowi commitować)
- [ ] Lista ścieżek do figurek i demo Unity
- [ ] Sprawdzenie, że `TEMAT.md` nadal jest czystym opisem tematu (plan realizacji osobno)

## Definition of Done

- Raport kompletny względem szkieletu A.
- Obca osoba z README odpala przynajmniej: zbudowanie zdarzeń **albo** wczytanie processed + jeden run sim + otwarcie 1 wykresu / Unity sample.
- Zespół przećwiczył odpowiedzi na FAQ.

## Pułapki

- Nie otwierać nowych epików feature po 20.12.
- Nie wkładać surowego `raw_A` do publicznego archiwum oddania bez świadomej decyzji licencyjnej — processed + opis pozyskania zwykle wystarczy.
