# M3 — Kalibracja (skalowalna → per linia)

**Najpóźniej:** 21.11.2026  
**Tor:** M (+ start batchy N — [N_siec_krakow.md](N_siec_krakow.md))  
**Wymaga:** M1 (czyste opóźnienia + łańcuchy), M2 (silnik + szybka ścieżka z testem równoważności)

## Cel

Dopasować parametry na pilocie **i wspólne `u` na korytarzu** (i domknąć metodę) z uczciwą niepewnością; porównać γ=0 vs γ>0. **API kalibracji od razu per `route_id`**, żeby tor N mógł odpalać batche na całą sieć — nie „jednorazowy skrypt tylko dla 179”. Przed startem batchy N zamrozić prognozy **leave-line-out** dla linii walidacyjnych. Nie zużywać miar walidacyjnych w funkcji celu.

## Wejście

- `observed_events` + `vehicle_chains` (po M1, z flagą `cross_route`)
- Uruchamialny DES (M2) i szybka ścieżka `sim.fast`
- Lista dni kalibracyjnych vs hold-out, lista dni specjalnych (`configs/special_days.yaml`)
- Lista linii walidacyjnych z TEMAT: 194, 494, 139, 138, 123 (+ 704 porównawczo)

## Wyjście

- `configs/calib/global.yaml` — warstwa globalna (`u`, `e_d`, γ) skalibrowana na korytarzu
- `configs/calib/groups.yaml` — warstwa grupowa (pooling dla linii bez własnego fitu i `low_n`)
- `configs/calib/routes/179.yaml` (+ szablon pod inne linie)
- Artefakt Optuna/ABC (best + trials); tabela γ=0 vs γ>0
- Raport wrażliwości (Morris / Sobol)
- `data/processed/calib/leave_line_out/` — zamrożone symulacje i metryki linii walidacyjnych z warstwy global/grupa
- CLI: `calibrate-route --route <id>` oraz `calibrate-batch` (choćby batch=[179])

## Kolejność

### A. Split i wektor S

- [ ] Ustawić dni kalibracji vs walidacji (zapisane w YAML; nie tylko w głowie), zbalansowane względem wersji rozkładu; dni specjalne poza próbą
- [ ] Zaimplementować funkcję `summarize(events) → S` wspólną dla obs i sim
- [ ] Składowe S (minimum):
  - kwantyle przyrostu opóźnienia na odcinkach (np. po okresie dnia)
  - krzywa pochłaniania / reset na pętli (vs zapas)
  - korelacja opóźnień kolejnych kursów w łańcuchu
  - (tylko dla warstwy `u`) korelacja opóźnień różnych linii na wspólnych odcinkach korytarza, uśredniona po dniu
- [ ] **Nie wkładać do S:** slope σ_e, pełny wzór dobowy σ_e, wzór dobowy korelacji między liniami, korelacje na liniach spoza korytarza — zostają na M4
- [ ] Skale `s_k` (np. std z danych) i wagi `w_k` w configu

### B. Odległość i optymalizacja

- [ ] d(S_sim, S_obs) = Σ w_k | (S_sim,k − S_obs,k) / s_k |
- [ ] Wybrać narzędzie: **Optuna** (szybszy start) lub ABC-SMC (jeśli chcecie pełny bayesowski vibe)
- [ ] Przestrzeń parametrów: a (dryf / okres×odcinek uproszczone), skala/ogon η, parametry u, ℓ_min, rozkład δ, e_d (efekt dnia), opcjonalnie γ
- [ ] Osobne runy lub flaga: γ=0 (bazowy) vs γ wolne
- [ ] Multistart / wystarczająco dużo trialów; seed runów zapisany
- [ ] Joby przy γ=0 liczone szybką ścieżką; γ>0 tylko SimPy

### B2. Wspólne `u` na korytarzu

Na samym 179 `u` zlewa się z `a` i `η` — wyróżnia je korelacja między liniami.

- [ ] Wspólny fit parametrów `u` (wariancja, skala czasowa, struktura przestrzenna wg decyzji z M2) na liniach korytarza 179, 169, 174, 173, 144, 124 naraz, z parametrami route-level tych linii jako wolnymi albo z ciepłego startu
- [ ] Porównanie: `u` z samego 179 vs `u` z korytarza — jeśli się różnią, raportujemy to jako argument za decyzją
- [ ] Zamrozić warstwę globalną (`global.yaml`) do reuse w jobach per linia

### C. Wrażliwość (SALib)

- [ ] Morris (screening) na parametrach
- [ ] Sobol na istotnych (kosztowne — mniej parametrów, mniej N jeśli trzeba)
- [ ] Wynik: które parametry realnie ruszają S; które są płaskie / niezidentyfikowalne

### D. Wydajność + API pod sieć

- [ ] Profil jednego runu doby: wąskie gardło?
- [ ] Równoległe replikacje; cache grafu GTFS
- [ ] `summarize` i objective przyjmują filtr `route_id`
- [ ] Zapis/odczyt parametrów route-level + warstwa grupowa + warstwa globalna
- [ ] Warunek brzegowy łańcuchów międzyliniowych: w jobie jednej linii kurs, który w łańcuchu następuje po kursie innej linii, startuje z obserwowanym opóźnieniem końca tamtego kursu (dni kalibracyjne) albo z rozkładu empirycznego (scenariusze)
- [ ] Smoke: ten sam job na drugiej linii z rankingu (np. 169) — nawet jeśli wynik wstępny
- [ ] Checkpoint trialów (crash-safe) pod długie batche N

### E. Identyfikowalność γ

- [ ] Przypomnienie z danych: FE okno×odcinek dawało γ≈0 — powtórzyć na czystym M1
- [ ] W symulacji: czy γ>0 poprawia S na hold-in bez psucia prostoty?
- [ ] Werdykt roboczy do raportu: bazowo γ=0 / γ>0 z uzasadnieniem (nie musi być „sensacyjny”)

### F. Leave-line-out (przed batchami N na liniach walidacyjnych)

- [ ] Warstwa grupowa (`groups.yaml`) skalibrowana bez danych linii walidacyjnych; reguła przypisania linii do grupy jawna (np. częstotliwość, długość, udział wspólnych odcinków z korytarzem)
- [ ] Dla 194, 494, 139, 138, 123, 704: symulacja z warstwy global + grupa na dniach kalibracyjnych i walidacyjnych, metryki z M4 C; zapis do `data/processed/calib/leave_line_out/` z hashem configu
- [ ] Zamrożenie: commit configu + hash wyników; tor N może kalibrować te linie dopiero po tym kroku (rejestr N ma flagę `lol_frozen`)

## Definition of Done

- Parametry 179 (γ=0) odtwarzają S na dniach kalibracyjnych w akceptowalnym d; jest wariant γ>0.
- `u` skalibrowane wspólnie na korytarzu i zamrożone w `global.yaml`.
- Morris (+ komentarz identyfikowalności).
- Istnieje **powtarzalny** job per `route_id` (nie tylko notebook „dla 179”) z warunkiem brzegowym dla łańcuchów międzyliniowych.
- Prognozy leave-line-out dla linii walidacyjnych zamrożone.
- Tor N może wystartować batch korytarza bez przepisywania calib.

## Pułapki

- Kalibracja na slope σ_e = brak niezależnej walidacji później.
- Za bogaty wektor a_{p,s} na każdy odcinek → overfitting; grupy (okres × typ odcinka).
- Nie ruszać dni walidacyjnych „żeby poprawić fit”.
- Nie odkładać API per-route „na M6” — wtedy nie zdążycie city-wide.
- Kalibracja linii walidacyjnej przed zamrożeniem leave-line-out = utrata walidacji przestrzennej z TEMAT.
- `u` z jednej linii przeniesione na miasto = zakłócenia wspólne niezidentyfikowane, a korelacje między liniami w sim przypadkowe.
