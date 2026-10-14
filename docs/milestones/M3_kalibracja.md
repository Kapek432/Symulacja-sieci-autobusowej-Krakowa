# M3 — Kalibracja

**Najpóźniej:** 21.11.2026  
**Tor:** M  
**Wymaga:** M1 (czyste opóźnienia + łańcuchy), M2 (silnik + szybkie replikacje)

## Cel

Dopasować parametry modelu do statystyk z dni kalibracyjnych z uczciwą niepewnością; porównać γ=0 vs γ>0. Nie zużywać miar walidacyjnych w funkcji celu.

## Wejście

- `observed_events` + `vehicle_chains` (po M1)
- Uruchamialny DES (M2)
- Lista dni kalibracyjnych vs hold-out

## Wyjście

- `configs/calib_*.yaml` lub artefakt Optuna/ABC (best + rozkłady / trials)
- Tabela: parametry, CI / percentyle, γ=0 vs γ>0
- Raport wrażliwości (Morris / Sobol) — notebook lub `docs/` / `data/processed/calib/`
- Skrypt: `uv run …` odpala N replikacji z danym wektorem parametrów

## Kolejność

### A. Split i wektor S

- [ ] Ustawić dni kalibracji vs walidacji (zapisane w YAML; nie tylko w głowie)
- [ ] Zaimplementować funkcję `summarize(events) → S` wspólną dla obs i sim
- [ ] Składowe S (minimum):
  - kwantyle przyrostu opóźnienia na odcinkach (np. po okresie dnia)
  - krzywa pochłaniania / reset na pętli (vs zapas)
  - korelacja opóźnień kolejnych kursów w łańcuchu
- [ ] **Nie wkładać do S:** slope σ_e, pełny wzór dobowy σ_e — zostają na M4
- [ ] Skale `s_k` (np. std z danych) i wagi `w_k` w configu

### B. Odległość i optymalizacja

- [ ] d(S_sim, S_obs) = Σ w_k | (S_sim,k − S_obs,k) / s_k |
- [ ] Wybrać narzędzie: **Optuna** (szybszy start) lub ABC-SMC (jeśli chcecie pełny bayesowski vibe)
- [ ] Przestrzeń parametrów: a (dryf / okres×odcinek uproszczone), skala/ogon η, parametry u, ℓ_min, rozkład δ, e_d (efekt dnia), opcjonalnie γ
- [ ] Osobne runy lub flaga: γ=0 (bazowy) vs γ wolne
- [ ] Multistart / wystarczająco dużo trialów; seed runów zapisany

### C. Wrażliwość (SALib)

- [ ] Morris (screening) na parametrach
- [ ] Sobol na istotnych (kosztowne — mniej parametrów, mniej N jeśli trzeba)
- [ ] Wynik: które parametry realnie ruszają S; które są płaskie / niezidentyfikowalne

### D. Wydajność

- [ ] Profil jednego runu doby: wąskie gardło?
- [ ] Równoległe replikacje (procesy); cache grafu GTFS
- [ ] Ewentualnie uproszczenie sieci w kalibracji (ta sama 179, mniej logowania)

### E. Identyfikowalność γ

- [ ] Przypomnienie z danych: FE okno×odcinek dawało γ≈0 — powtórzyć na czystym M1
- [ ] W symulacji: czy γ>0 poprawia S na hold-in bez psucia prostoty?
- [ ] Werdykt roboczy do raportu: bazowo γ=0 / γ>0 z uzasadnieniem (nie musi być „sensacyjny”)

## Definition of Done

- Jest zestaw parametrów bazowych (γ=0) odtwarzający S na dniach kalibracyjnych w akceptowalnym d.
- Jest porównanie z wariantem γ>0.
- Jest choćby Morris + krótki komentarz identyfikowalności.
- Parametry i seed da się wczytać w M4 bez ręcznego kopiowania liczb z czatu.

## Pułapki

- Kalibracja na slope σ_e = brak niezależnej walidacji później.
- Za bogaty wektor a_{p,s} na każdy odcinek → overfitting; zacznijcie od grup (okres × typ odcinka / kwantyle).
- Nie ruszać dni walidacyjnych „żeby poprawić fit”.
