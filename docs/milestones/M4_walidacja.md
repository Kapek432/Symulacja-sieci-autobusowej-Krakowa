# M4 — Walidacja + korytarz + start city-wide

**Najpóźniej:** 5.12.2026  
**Tor:** M + N (+ viz pydeck)  
**Wymaga:** M3 (parametry, `u` korytarza, zamrożony leave-line-out, API per-route), M1, M2

## Cel

Udowodnić wartość modelu poza dopasowaniem S; domknąć **korytarz**; **domknąć MVP z `TEMAT.md`** (sekcja 4) jako zobowiązanie wobec prowadzącego; równolegle odpalić **pierwsze batche kalibracji per linia** poza korytarzem (tor N). Nie czekamy z city-wide do M6.

## Wejście

- Parametry / job calib z M3, `global.yaml`, `groups.yaml`
- Zamrożone wyniki leave-line-out (`data/processed/calib/leave_line_out/`)
- Ranking linii z M1
- Lista z `TEMAT.md` (pilot, korytarz, OOS)

## Wyjście

- Tabela walidacyjna (metryki × model × dzień/linia)
- Ablacje + baseline’y
- Symulacja korytarza end-to-end
- Coverage report: korytarz 100% + pierwszy batch city (np. top 30–50 linii lub ≥X% zdarzeń sieci)
- Artefakty pydeck / heatmapy
- Draft raportu (rozdziały: dane, model, weryfikacja, kalibracja)

## Kolejność

### A. Walidacja czasowa (dni OOS) — pilot / korytarz

- [ ] Model z parametrami M3 na dniach walidacyjnych
- [ ] Wariant A: znany `e_d`; wariant B: `e_d` z rozkładu kalibracyjnego
- [ ] RMSE, KS, korelacje kolejnych kursów; bootstrap → CI
- [ ] Weekendy jako reżim dodatkowy (jeśli dane są)
- [ ] Dni specjalne (z `special_days.yaml`) raportowane osobno, nie w średniej OOS
- [ ] Walidacja out-of-time: dni `complete`, które przyszły po zamrożeniu podziału w M3 (rola `valid` z automatu), raportowane osobno od dni walidacyjnych wybranych przed kalibracją; tabela odświeżana po każdym wgraniu bez ponownej kalibracji
- [ ] Każda tabela walidacyjna ma migawkę danych (lista dni + hash `manifest.json`)

### B. Walidacja przestrzenna (linie OOS) — leave-line-out

Linie walidacyjne walidujemy wynikami z M3 F (warstwa global + grupa, bez danych tej linii). To jest walidacja z TEMAT.

- [ ] 194, 494, 139 (częściowo wspólne z korytarzem)
- [ ] 138, 123 (zewnętrzne wg TEMAT)
- [ ] 704 porównawczo (krótkie zapasy na pętli)
- [ ] Sprawdzić, że wyniki pochodzą z zamrożonego configu (hash z M3 F), a nie z rejestru po batchach N
- [ ] Osobno, jako **dopasowanie** (nie walidacja): te same metryki po kalibracji per linia w torze N — różnica „leave-line-out vs per linia” pokazuje, ile daje warstwa route-level

### C. Nietrywialne vs konstrukcja

| Nie jako walidacja | Testować |
|--------------------|----------|
| dryf przy a>0 | krzywa pochłaniania OOS |
| liniowy wzrost var przy η | slope σ_e, wzór dobowy OOS |
| średnia korelacja między liniami na korytarzu (jest w S warstwy `u`) | wzór dobowy korelacji między liniami; korelacje na wspólnych odcinkach poza korytarzem; ogony; γ=0 vs γ>0 |
| metryki linii po ich kalibracji per linia | metryki leave-line-out (B) |

### C2. Sprzężenie pośrednie przez bloki (decyzja 9 C)

- [ ] Graf linii: krawędź „wspólny odcinek” i krawędź „blok przechodzący między liniami”; wybrać pary linii połączone tylko blokami (bez wspólnych odcinków)
- [ ] Dane: korelacja opóźnień takich par (po dniu i oknie, względem par losowych o tej samej częstotliwości) na dniach walidacyjnych
- [ ] Symulacja `scope=city` z parametrami M3: ta sama statystyka; porównanie sim vs obs z CI. Statystyka nie jest w S (predykcja, nie dopasowanie)
- [ ] Ablacja: ten sam model z blokami rozciętymi na granicach linii → korelacja par powinna zniknąć

### D. Ablacje + baseline’y

- [ ] Bez łańcuchów; bez `u`; bez `e_d`; bez bloków międzyliniowych; bez interakcji na słupku (γ = 0) — wkład każdego filaru z decyzji 9
- [ ] Baseline: rozkład; AR wzdłuż trasy; empiryczny (linia, odcinek, godzina)
- [ ] Tabela vs nasz model na OOS

### E. Korytarz w symulacji

`u` korytarza jest skalibrowane w M3 B2; tutaj korytarz jedzie end-to-end i jest walidowany.

- [ ] 169, 174, 173, 144, 124 (+ 608 jeśli aktywna)
- [ ] Wspólne `u` na odcinkach; sanity korelacji sim vs obs na dniach OOS
- [ ] Łańcuchy międzyliniowe w korytarzu: przenoszenie sim vs obs
- [ ] Przesiadki: pomijamy

### F. Start city-wide (tor N — obowiązkowy w M4, nie „jak będzie czas”)

- [ ] Batch 2: wszystkie linie korytarza skalibrowane per route
- [ ] Batch 3: linie walidacyjne (po zamrożeniu leave-line-out) i 704, następnie kolejne z rankingu (cel: znaczący % zdarzeń sieci, np. ≥50–70%)
- [ ] Coverage CSV zaktualizowany
- [ ] Smoke `scope=city` z dotychczasowym rejestrem (brakujące linie: warstwa grupowa — jawnie oznaczone, dociągane w M6)

Szczegóły batchy: [N_siec_krakow.md](N_siec_krakow.md).

### G. Viz

- [ ] pydeck, kontagion korytarza, Marey real vs sim

### H. Draft raportu

- [ ] Szkielet z [M7](M7_raport.md) A w repo (`docs/raport/` lub uzgodniony format)
- [ ] Napisane rozdziały: dane (z regułą wersji rozkładu i listą dni), model, weryfikacja (testy M2, test równoważności fast vs SimPy), kalibracja (S, hierarchia warstw, `u` korytarza, leave-line-out)
- [ ] Figurki z M1–M4 podpięte ścieżkami z `data/processed/` (nie wklejane ręcznie)

## Definition of Done

- **MVP z TEMAT sekcja 4 kompletne:** pilot + korytarz w symulacji, kalibracja na dniach roboczych, walidacja na dniach OOS i liniach spoza kalibracji (leave-line-out), ablacje, baseline'y, viz podstawowa. Scenariusze domyka M5.
- Walidacja + ablacje + baseline’y udokumentowane.
- Korytarz jeździ end-to-end ze wspólnym `u`.
- Tor N ma **więcej niż pilot**: korytarz skalibrowany per linia + kolejny batch city wystartowany / domknięty wg celu % powyżej.
- Draft raportu z rozdziałami z H.
- Brak decyzji „zostajemy przy samym korytarzu”.

## Pułapki

- Walidacja na dniach z M3 = oszustwo.
- Walidacja linii OOS po ich kalibracji per linia = to samo oszustwo w przestrzeni.
- Nie blokować batchy N na „idealnej” tabeli walidacyjnej — idą równolegle po stabilnym jobie calib (z wyjątkiem linii walidacyjnych przed M3 F).
