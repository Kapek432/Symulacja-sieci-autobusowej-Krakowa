# M1 — Dane obserwowane wiarygodne

**Najpóźniej:** 24.10.2026  
**Tor:** D  
**Blokuje:** sensowną kalibrację (M3) i uczciwe fakty stylizowane pod model

## Cel

Opóźnienia i łańcuchy kursów liczone z **właściwą wersją rozkładu na dany dzień**, z flagami jakości i powtórzonymi faktami stylizowanymi na kilku pełnych dniach roboczych. Pipeline od razu obejmuje **wszystkie linie** w parquet (nie filtr „tylko 179”) — docelowo kalibracja city-wide per linia ([N](N_siec_krakow.md)).

## Wejście

- `data/raw_A/vehicle_positions/`, `trip_updates/`, `static/GTFS_KRK_A_*.zip`
- `sandbox/gtfs-experiments/build_events.py`, `week_analysis.py`
- Raport: `data/processed/week_report/report.txt`

## Wyjście

- `data/processed/observed_events.parquet` (przeliczony, ze wskazaniem wersji GTFS / `gtfs_stamp` per wiersz lub per dzień)
- `data/processed/vehicle_chains.parquet` (lub równoważna tabela)
- Odświeżony `week_report/` z wykresami
- Krótka notatka: które dni → kalibracja, które → walidacja (propozycja; twardy split w M3)
- Ranking `route_id` po liczbie zdarzeń (wejście do batchy toru N)

## Kolejność (sugerowana)

Zróbcie **najpierw A**, potem B–D równolegle kto może.

### A. Match wersji GTFS do dnia (P0)

Problem był podwójny: `build_events.py` brał `sorted(…GTFS_KRK_A_*.zip)[-1]` (jeden rozkład na wszystkie dni), a przy kursie spoza tego ZIP-a porównanie z `NaN` dawało `False` i zdarzenie dostawało datę obsługi „wczoraj”. Skutek: `z_rozkladem = 0` dla 4–8.10 i wszystkie te dni przesunięte o jeden (rzekomo pusty 9.10, 147 tys. zdarzeń w niedzielę 4.10).

Struktura feedu ZTP (sprawdzone na 4 wersjach): feed kroczący, `service_id`/`trip_id` z prefiksem daty pokolenia (`20261005_1_…`), kalendarz tylko w `calendar_dates.txt`, ten sam `trip_id` ma identyczne `stop_times` we wszystkich wersjach. Reguła „najnowszy ZIP z `stamp.date <= D`” nie działa (np. ZIP z 12.10 ma znacznik 12:30, a wersja z 6.10 jest niepełna).

- [x] Spisać dostępne ZIP-y i ich timestampy (`GTFS_KRK_A_YYYYMMDD_HHMMSS.zip`)
- [x] Reguła: rozkład kursu po `trip_id` z najnowszej wersji, która go zawiera; kalendarz dnia `D` z najnowszej wersji, która ma wpis na `D` (`gtfs_versions.load_schedule`)
- [x] Data obsługi: kandydaci wczoraj / dziś / jutro, tylko dni z aktywną usługą kursu, wybór min |opóźnienie|; brak dopasowania = brak daty (`gtfs_versions.assign_service_date`)
- [x] Zapis w zdarzeniach: kolumny `gtfs_stamp` i `service_id`
- [x] Przeliczyć `observed_events` od zera
- [x] Smoke: wydruk `build_events` „zdarzenia dzień po dniu” (data obsługi vs data lokalna, zdarzenia bez daty, wersja kalendarza); sekcja 2 `week_analysis` z sensownym udziałem dla 5–9.10
- [x] Zmiana czasu 25.10: czasy GTFS liczone od „południe − 12 h” (doba 25 h nie przesuwa opóźnień); test w `tests/test_gtfs_versions.py`. Dobę 25.10 i tak oznaczyć jako specjalną (patrz D)
- [ ] Po pierwszym sync po 25.10: sprawdzić w wydruku `build_events`, że 25–26.10 nie mają skoku zdarzeń bez daty
- [ ] Przenieść `gtfs_versions.py` do `src/ingest/` przy szkielecie repo (M2 A)

### B. Jakość zdarzeń

- [ ] Flaga `outlier = |arr_delay_s| > 1800` (albo równoważna) — jeden spójny filtr zamiast rozproszonych
- [ ] Osobna klasa `wrong_service_day`: |opóźnienie| ≈ 24 h (po naprawie A: 0,16% zdarzeń, 98 pojazdów, 288 kursów, głównie 7–8.10 i 13–14.10). RT zgłasza `trip_id` usługi z innego dnia, np. kurs usługi pon–śr w czwartek. Sprawdzić, czy da się dopasować odpowiednik kursu w usłudze właściwej dla dnia (ta sama linia, kierunek, godzina); jeśli nie — wykluczyć z flagą
- [ ] Noc na granicy pokoleń usług (np. 12→13.10, 9→10.10): zdarzenia 0–2 h trafiają do doby następnej (w raporcie 13.10 h0 ≈ 2× norma, 12.10 h0 ≈ 0). Prawdopodobnie RT używa kursów nowej doby od północy; potwierdzić i opisać (wpływa tylko na kursy nocne)
- [ ] Kandydaci daty obsługi: wczoraj / dziś / jutro (pojazdy na pętli z kursem „na jutro”)
- [ ] Opcjonalnie (jak będzie czas): `move_ts` = pierwszy raport >15 m od postoju; porównać z `dep_ts`
- [ ] Zachować `arr_ok` / `dep_ok` (niepewność ≤ 30 s); udokumentować w README skryptów

### C. Łańcuchy kursów (`vehicle_chains`)

- [ ] Z `trips.block_id` + zdarzeń: dla (vehicle_id lub block_id, service_date) uporządkowana lista kursów
- [ ] Kolumny minimum: kolejność, route_id, direction, trip_id, zaplanowany zapas pętli `L`, opóźnienie na końcu kursu, opóźnienie odjazdu następnego, czy przeniesienie (opóźnienie > zapas − ℓ_min)
- [ ] Flaga `cross_route` (następny kurs w łańcuchu na innej linii) + udział takich przejść per linia — wejście do warunku brzegowego w jobach per linia (M3 D)
- [ ] Krzywa pochłaniania: udział / wielkość resetu vs zapas (jak sekcja 6 raportu, ale na poprawionych opóźnieniach)
- [ ] Sprawdzić, że `block_id` nadal ≈ zgodny z pojazdem (~99% w starym raporcie)

### D. Fakty stylizowane + tooling raportu

- [x] Dodać `matplotlib` do `pyproject.toml`; `ruff` i `pytest` w grupie dev
- [x] Naprawić crash KS w `week_analysis` (dni bez dobrych zdarzeń w `WORK` są pomijane z komunikatem)
- [x] Przegonić raport na poprawionych zdarzeniach dla pełnych dni roboczych (9 dni: 5–9.10, 12–15.10)
- [x] Potwierdzić na ≥3 dniach: dryf wzdłuż trasy, wzrost rozrzutu, slope σ_e, krzywa pętli, korelacja między liniami (stan: `PLAN_REALIZACJI.md`, „Stan na 16.10”)
- [ ] Bootstrap po kursach dla CI przy kluczowych statystykach (przynajmniej dryf / reset)
- [ ] Notebook lub skrypt: Marey rzeczywistości dla 179 (jeden dzień)
- [ ] Propozycja split dni: zbalansowana względem wersji rozkładu (pokolenia 20261005, 20261010, 20261013, …) i dni tygodnia, a nie „pierwsze → kalibracja, późniejsze → walidacja” (zaktualizować gdy przybędą dni)
- [ ] `configs/special_days.yaml`: 25.10 (zmiana czasu), 31.10–2.11 (Wszystkich Świętych), 10–12.11 (Święto Niepodległości), okres przedświąteczny w grudniu; z decyzją: wyklucz / osobny reżim / sprawdź w danych
- [ ] Eksport rankingu linii (zdarzenia, dni, med opóźnienia, udział `cross_route`) → `data/processed/route_ranking.csv` pod tor N
- [ ] Korelacja residuów opóźnień na odcinkach sąsiednich vs odległych (wejście do decyzji o strukturze przestrzennej `u`, M2 B)

### E. Jak będzie czas (nie blokuje M1 Done)

- [ ] Interpolacja luk na `shapes.txt` tylko dla brakujących przystanków, z flagą gorszej jakości
- [ ] Pokrycie statusem 1 vs wielkość odstępu

## Pliki, których to dotyczy

| Plik | Rola |
|------|------|
| `sandbox/gtfs-experiments/gtfs_versions.py` | łączenie wersji GTFS, kalendarz efektywny, data obsługi |
| `tests/test_gtfs_versions.py` | testy reguł daty obsługi i kalendarza |
| `sandbox/gtfs-experiments/build_events.py` | zdarzenia na rozkładzie per dzień |
| `sandbox/gtfs-experiments/week_analysis.py` | fakty + KS + wykresy |
| `sandbox/gtfs-experiments/README_skrypty.md` | zaktualizować kontrakt wyjścia |
| `data/processed/observed_events.parquet` | artefakt |
| `data/processed/vehicle_chains.parquet` | artefakt (nowy) |
| `pyproject.toml` | matplotlib i deps |

## Definition of Done

- Zdarzenia z dni 5–9.10 (i kolejnych) mają sensowny match rozkładu; parquet zawiera **wszystkie** linie; liczba zdarzeń wg daty obsługi zgadza się z godzinami pracy loggera.
- Jest lista dni specjalnych w configu.
- Istnieje tabela łańcuchów z zapasem i przenoszeniem.
- Raport tygodnia odpala się bez crashy i zapisuje wykresy.
- Jest `route_ranking.csv` (lub równoważny) pod batche N.
- Zespół ma listę pełnych dni roboczych i roboczą propozycję split kalibracja/walidacja.
- Nikt nie zaczyna M3 na starym parquet bez `gtfs_stamp` / per-day GTFS.

## Pułapki

- Sam weekend z „dobrym” `z_rozkladem` nie ratuje dni roboczych sprzed zmiany ZIP.
- Pooling dni przed naprawą GTFS zafałszuje dryf i pętlę.
- 704 ma krótkie zapasy — nie uśredniać wniosków o przenoszeniu tylko po 179.
- Brak daty obsługi nie może być cicho zastępowany domysłem: zdarzenie bez aktywnej usługi to sygnał błędu w rozkładzie albo w RT, a nie „pewnie wczoraj”.
