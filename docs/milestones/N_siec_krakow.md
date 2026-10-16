# Tor N — Scale-out: sieć całego Krakowa

**Równolegle:** M2 → M6  
**Cel produktu:** do **20.12.2026** wszystkie aktywne linie autobusowe w DES z **kalibracją per linia** (gęsta, nie tylko parametry zbiorcze).  
**Zakresu nie ucinamy** — przy poślizgu zwiększamy gęstość / równoległość jobów (patrz `PLAN_REALIZACJI.md`).

## Definicja „per linia”

Dla każdego `route_id` z ruchu w dniach kalibracyjnych:

- osobny zestaw parametrów route-level (co najmniej: skale dryfu / η, ewentualnie ℓ_min lub korekta pętli, wagi okresu dnia),
- nad warstwą grupową (`configs/calib/groups.yaml`, „parametry zbiorcze” z TEMAT) i globalną (`u`, `e_d`, γ z `global.yaml`, skalibrowane wspólnie na korytarzu w M3),
- artefakt: `configs/calib/routes/{route_id}.yaml` (lub jeden parquet parametrów),
- wiersz w coverage: `route_id`, n zdarzeń, udział łańcuchów `cross_route`, status calib (ok / low_n / failed / inactive), flaga `lol_frozen` dla linii walidacyjnych, metryki S.

Linie z `n` poniżej progu: nadal mają rekord; część parametrów z grupy (np. podobna częstotliwość / korytarz), reszta dociągnięta — **nie pomijamy linii w symulacji city**.

## Kolejność batchy (sugerowana)

1. [ ] Pilot **179** (oba kierunki) — wzorzec joba, oraz **704** (krótkie zapasy na pętli — test, że job radzi sobie z silnym przenoszeniem, zanim pójdzie skala)
2. [ ] Korytarz: **169, 174, 173, 144, 124** (+ 608 jeśli w danych)
3. [ ] Walidacyjne: **194, 494, 139, 138, 123** — **dopiero po zamrożeniu leave-line-out** (M3 F); job odmawia, jeśli `lol_frozen` nie jest ustawione
4. [ ] Pozostałe linie malejąco po liczbie zdarzeń w dniach roboczych
5. [ ] Domknięcie: coverage **100%** aktywnych `route_id` z GTFS dnia

704 w batchu 1 nie jest linią walidacyjną przestrzenną (TEMAT: „przypadek porównawczy”), więc nie wymaga leave-line-out przed fitem. Jeśli zespół zdecyduje inaczej, przesunąć ją do batcha 3.

## Backlog

### A. Infrastruktura (start ‖ M2)

- [ ] Loader: graf + łańcuchy dla `scope=city` (wszystkie route_id)
- [ ] Config: lista linii, progi `min_events`, ścieżki artefaktów
- [ ] Coverage report: skrypt → tabela/Markdown `%` linii gotowych
- [ ] Jedno polecenie: `calibrate-route --route 179` i `calibrate-batch --file batch1.yaml`

### B. Compute i wydajność (‖ M3–M4)

- [ ] Profil doby city-wide (cel orientacyjny: jedna replika w czasie akceptowalnym na CI/laptopie lub oznaczona maszyna), osobno SimPy i szybka ścieżka `sim.fast`
- [ ] Joby kalibracyjne przy γ=0 na `sim.fast` (po teście równoważności z M2 C2); SimPy do walidacji i scenariuszy
- [ ] Cache GTFS/grafu; minimum logowania w batchach
- [ ] Równoległe joby per linia (procesy); kolejka (nawet prosta: shell + GNU parallel / Python multiprocessing)
- [ ] Warm-start: init parametrów z linii sąsiedniej / mediany korytarza
- [ ] Checkpointowanie trialów Optuna (crash nie zeruje dnia pracy)

### C. Kalibracja gęsta (‖ M3–M6)

- [ ] Wspólna funkcja S działająca na filtrze `route_id` (i opcjonalnie dir)
- [ ] Job per linia: Optuna/ABC z fixed global `u`/`e_d`/`γ` z korytarza (M3 B2), potem ewentualny drugi przebieg globalny
- [ ] Warunek brzegowy łańcuchów międzyliniowych w jobie (M3 D); linie z wysokim udziałem `cross_route` oznaczone w coverage
- [ ] Blokada: linia z listy walidacyjnej bez `lol_frozen` nie wchodzi do kolejki
- [ ] Drugi przebieg (opcjonalnie, wysoka wartość): lekki refit wspólnych `u` przy zamrożonych route-level
- [ ] Rejestr nieudanych linii + retry z uproszczoną przestrzenią parametrów
- [ ] Test: po skalibrowaniu batcha korytarza korelacja między liniami na wspólnych odcinkach nie znika

### D. Symulacja city-wide (‖ M4–M6)

- [ ] Uruchomienie pełnej doby `scope=city` z parametrami z rejestru
- [ ] Sanity: liczba kursów / pojazdów w sim vs rząd wielkości z observed
- [ ] Eksport downsamplowany pod Unity/pydeck (nie pełny dump wszystkich pozycji co 1 s, jeśli zabija dysk)

### E. Jakość coverage (przed Done M6)

- [ ] Dashboard/tabela: wszystkie route_id, status, med_|delay| obs vs sim, d(S)
- [ ] Lista linii `low_n` z opisem reguły poolingu
- [ ] Ablacja sieciowa (opcjonalnie skrócona): wyłączenie łańcuchów / u na próbce linii

## Definition of Done (tor N / wkład w M6)

- Coverage kalibracji per linia = **100%** aktywnych linii dnia (z jawnymi wyjątkami tylko jeśli linia nie jeździ w danych — wtedy „inactive”, nie „skipped silently”).
- `scope=city` kończy dobę i zapisuje events.
- Coverage report zapisany w `data/processed/calib/coverage_*.csv` (lub md).

## Pułapki

- Kalibrować „całość naraz” jednym wektorem 10⁴ parametrów = nie do debugowania; **batch per route**.
- Nie blokować Unity na 100% coverage — eksport z korytarza/city sample idzie wcześniej.
- Nie mylić „linia w grafie” z „linia skalibrowana” — coverage musi rozróżniać.
- Metryki linii po jej kalibracji per linia to dopasowanie, nie walidacja — walidacją przestrzenną jest leave-line-out z M3 F.
- Job jednej linii z zerowym opóźnieniem na wejściu łańcucha z innej linii zaniża przenoszenie.
