# M4 — Walidacja + korytarz

**Najpóźniej:** 5.12.2026  
**Tor:** M (+ viz pydeck)  
**Wymaga:** M3 (parametry), M1 (dane), M2 (silnik)

## Cel

Pokazać, że model wyjaśnia coś poza dopasowaniem S; rozszerzyć z pilota na korytarz ze wspólnymi zakłóceniami `u`.

## Wejście

- Parametry z M3
- Dni i linie hold-out
- Lista linii z `TEMAT.md`

## Wyjście

- Tabela walidacyjna (metryki × model × dzień/linia)
- Rozdział wyników: „z konstrukcji” vs „nietrywialne”
- Ablacje + baseline’y
- Symulacja korytarza (179 + 169 + 174 + 173 + 144 + 124)
- Artefakty pydeck / heatmapy

## Kolejność

### A. Walidacja czasowa (dni OOS)

- [ ] Uruchomić model z parametrami M3 na dniach walidacyjnych
- [ ] Wariant A: znany efekt dzienny e_d (struktura się przenosi?)
- [ ] Wariant B: e_d wylosowany z rozkładu z dni kalibracyjnych
- [ ] Metryki: RMSE odcinków / opóźnień, KS rozkładów, korelacje kolejnych kursów
- [ ] Bootstrap po kursach → CI
- [ ] Osobno weekendy jako reżim dodatkowy (jeśli dane są)

### B. Walidacja przestrzenna (linie OOS)

Bez pełnej rekalibracji (lub z minimalnym dostrojeniem — opisać które):

- [ ] Częściowo wspólne z 179: 194, 494, 139
- [ ] Zewnętrzne (mało/zero wspólnych odcinków): 138, 123 (wg TEMAT)
- [ ] 704 jako przypadek porównawczy (krótkie zapasy)

### C. Nietrywialne testy vs konstrukcja

| Nie chwalić jako walidację | Testować |
|----------------------------|----------|
| dodatni dryf przy a>0 | krzywa pochłaniania na OOS |
| liniowy wzrost var przy niezależnym η | slope σ_e i wzór dobowy na OOS |
| | korelacje między liniami na wspólnych odcinkach |
| | ogony (KS), RMSE |
| | γ=0 vs γ>0 na OOS |

- [ ] Wypełnić tabelę wyników zgodnie z powyższym

### D. Ablacje

- [ ] Bez łańcuchów (każdy kurs niezależny start)
- [ ] Bez zakłóceń wspólnych u
- [ ] Bez efektu dziennego e_d
- [ ] Porównanie d / metryk vs model pełny

### E. Modele odniesienia (musi pobić)

- [ ] Sam rozkład jazdy (delay=0 lub tylko rozkład)
- [ ] Autoregresja opóźnienia wzdłuż trasy
- [ ] Empiryczny rozkład opóźnień po (linia, odcinek, godzina)
- [ ] Tabela: nasz model vs baseline na tych samych metrykach OOS

### F. Rozszerzenie korytarza

- [ ] Dodać linie 169, 174, potem 173, 144, 124 do grafu i łańcuchów
- [ ] Wspólne `u_{d,h,s}` dla kursów (różnych linii) na tym samym odcinku w oknie
- [ ] Sanity: korelacja między liniami w sim vs obs na wspólnych odcinkach
- [ ] Przesiadki pasażerów: **pomijamy**

### G. Viz wspierająca

- [ ] pydeck: kolumny opóźnienia nad przystankami / animacja
- [ ] Heatmapa kontagionu (korytarz)
- [ ] Marey real vs sim (pilot + 1 linia korytarza)

## Definition of Done

- Jest tabela walidacyjna z CI i baseline’ami.
- Ablacje policzone.
- Korytarz odpalany end-to-end (nie tylko 179).
- Werdykt jakości opisany uczciwie (co działa / co nie) — bez obcinania zakresu „na 5” w planie; ewentualne ograniczenia idą do raportu.

## Pułapki

- Walidacja na dniach użytych w M3 = oszustwo.
- Rozszerzenie korytarza przed stabilnym pilotem utrudnia debug — najpierw A–E na 179, potem F.
