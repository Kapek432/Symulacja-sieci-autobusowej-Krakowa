# M7 — Raport, odtwarzalność, oddanie

**Najpóźniej:** 31.12.2026  
**Tor:** wszyscy  
**Wymaga:** artefakty M3–M6; draft rozdziałów dane / model / weryfikacja / kalibracja powstaje w M4 H — tutaj tylko uzupełnienie i redakcja

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
- [ ] Dane: GTFS + GTFS-RT, okres, luki, match wersji rozkładu (feed kroczący, reguła z `gtfs_versions.py`), dni specjalne
- [ ] Model: opis ODD-like (encje, procesy, skala, wejścia/wyjścia, stochastyka), struktura przestrzenna `u`
- [ ] Weryfikacja (testy M2, test równoważności szybkiej ścieżki z SimPy)
- [ ] Kalibracja (S, metoda, γ, hierarchia global → grupa → linia, `u` z korytarza, **per linia / coverage całej sieci**)
- [ ] Walidacja (OOS dni, leave-line-out, ablacje, baseline’y) — „z konstrukcji” vs nietrywialne; metryki sieciowe; jawnie: fit per linia ≠ walidacja
- [ ] Scenariusze (korytarz + warianty city) + wrażliwość warunkowych
- [ ] Unity / viz
- [ ] Ograniczenia (γ≈0, okres danych i liczba wersji rozkładu, S4/S5, low_n pooling, perf city-wide, warunek brzegowy łańcuchów międzyliniowych, założona struktura przestrzenna `u`)
- [ ] Wnioski — odpowiedzi 1:1 na pytania badawcze

### B. Odtwarzalność

- [ ] `README.md`: wymagania, `uv sync`, gdzie dane, jak zbudować events, jak odpalić sim, calib (skrót), scenariusze, eksport Unity
- [ ] Jedno „główne” polecenie lub krótki skrypt `scripts/reproduce_core.sh` (nawet jeśli pełna kalibracja trwa długo — wtedy reproduce na zamrożonych artefaktach)
- [ ] Wersje zależności (`uv.lock`)
- [ ] Jakie dane muszą być lokalnie (raw niepubliczny) vs co jest w `processed/` do odtworzenia wykresów

### C. Prezentacja

- [ ] Konspekt: problem → dane → model → kalibracja per linia / cała sieć → walidacja → scenariusze → Unity
- [ ] FAQ przygotowane:
  - Dlaczego to nie „rozkład + szum”?
  - Jak skalibrowaliście **wszystkie** linie (job per route, pooling low_n)?
  - Skoro wszystkie linie są skalibrowane, gdzie jest walidacja na liniach spoza kalibracji? (leave-line-out zamrożony przed fitem)
  - Skąd wiecie, że `u` to zakłócenie wspólne, a nie dryf linii? (wspólna kalibracja na korytarzu, ablacja bez `u`)
  - Co z γ / zbijaniem?
  - Czy łańcuchy mają efekt przy dużym zapasie?
  - Co jest założeniem w scenariuszach warunkowych?
  - Jak krótki okres danych i perf city-wide ograniczają wnioski?
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
