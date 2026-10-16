# M1 — Dane obserwowane wiarygodne

**Najpóźniej:** 24.10.2026  
**Status:** Done (16.10.2026). Otwarte punkty poniżej nie blokują M3: dwa czekają na dane (25.10, grudzień), krzywa pochłaniania z `chains/` przechodzi do modułu kalibracji pętli w M3, reszta jest opcjonalna (`move_ts`, sekcja E).  
**Tor:** D  
**Blokuje:** sensowną kalibrację (M3) i uczciwe fakty stylizowane pod model

## Cel

Opóźnienia i łańcuchy kursów liczone z **właściwą wersją rozkładu na dany dzień**, z flagami jakości i powtórzonymi faktami stylizowanymi na kilku pełnych dniach roboczych. Pipeline od razu obejmuje **wszystkie linie** w parquet (nie filtr „tylko 179”) — docelowo kalibracja city-wide per linia ([N](N_siec_krakow.md)).

## Wejście

- `data/raw_A/vehicle_positions/`, `trip_updates/`, `static/GTFS_KRK_A_*.zip`
- `uv run build-events` / `uv run events-quality` (`src/krakbus/observed/`), `sandbox/gtfs-experiments/week_analysis.py`
- Raport: `data/processed/week_report/report.txt`

## Wyjście

- `data/processed/events/YYYY-MM-DD.parquet` — zdarzenia per data obsługi, z `gtfs_stamp` (zastąpiły jeden plik `observed_events.parquet`, patrz A2)
- `data/processed/chains/YYYY-MM-DD.parquet` — łańcuchy kursów w tym samym układzie (jeden plik na dzień)
- `data/processed/days.csv` — rejestr dni: status, rola, liczby kontrolne
- `data/processed/manifest.json` — odciski wejść każdego dnia (co przeliczać przy kolejnym wgraniu)
- Odświeżony `week_report/` z wykresami
- Krótka notatka: które dni → kalibracja, które → walidacja (propozycja; twardy split i zamrożenie w M3)
- Ranking `route_id` po liczbie zdarzeń (wejście do batchy toru N)

## Kolejność (sugerowana)

Zróbcie **najpierw A, potem A2**, potem B–D równolegle kto może. A2 jest przed C, żeby `build_chains` od razu powstał w schemacie per dzień.

### A. Match wersji GTFS do dnia (P0)

Problem był podwójny: `build_events.py` brał `sorted(…GTFS_KRK_A_*.zip)[-1]` (jeden rozkład na wszystkie dni), a przy kursie spoza tego ZIP-a porównanie z `NaN` dawało `False` i zdarzenie dostawało datę obsługi „wczoraj”. Skutek: `z_rozkladem = 0` dla 4–8.10 i wszystkie te dni przesunięte o jeden (rzekomo pusty 9.10, 147 tys. zdarzeń w niedzielę 4.10).

Struktura feedu ZTP (sprawdzone na 4 wersjach): feed kroczący, `service_id`/`trip_id` z prefiksem daty pokolenia (`20261005_1_…`), kalendarz tylko w `calendar_dates.txt`, ten sam `trip_id` ma identyczne `stop_times` we wszystkich wersjach. Reguła „najnowszy ZIP z `stamp.date <= D`” nie działa (np. ZIP z 12.10 ma znacznik 12:30, a wersja z 6.10 jest niepełna).

- [x] Spisać dostępne ZIP-y i ich timestampy (`GTFS_KRK_A_YYYYMMDD_HHMMSS.zip`)
- [x] Reguła: rozkład kursu po `trip_id` z najnowszej wersji, która go zawiera; kalendarz dnia `D` z najnowszej wersji, która ma wpis na `D` (`gtfs_versions.load_schedule`)
- [x] Data obsługi: kandydaci wczoraj / dziś / jutro, tylko dni z aktywną usługą kursu, wybór min |opóźnienie|; brak dopasowania = brak daty (`gtfs_versions.assign_service_date`)
- [x] Zapis w zdarzeniach: kolumny `gtfs_stamp` i `service_id`
- [x] Przeliczyć `observed_events` od zera
- [x] Smoke: wydruk `build_events` „zdarzenia dzień po dniu” (data obsługi vs data lokalna, zdarzenia bez daty, wersja kalendarza); sekcja 2 `week_analysis` z sensownym udziałem dla 5–9.10
- [x] Zmiana czasu 25.10: czasy GTFS liczone od „południe − 12 h” (doba 25 h nie przesuwa opóźnień); test w `tests/ingest/test_gtfs_versions.py`. Dobę 25.10 i tak oznaczyć jako specjalną (patrz D)
- [ ] (czeka na dane) Po pierwszym sync po 25.10: sprawdzić w `days.csv` i `events-quality`, że 25–26.10 nie mają spadku liczby zdarzeń ani skoku |opóźnienia| ≈ 1 h
- [x] Przenieść `gtfs_versions.py` do `src/krakbus/ingest/` przy szkielecie repo (M2 A)

### A2. Przetwarzanie przyrostowe (dane napływają cały czas)

Problem: logger zbiera dane ciągle, a nowe dane są wgrywane do `data/raw_A` co jakiś czas. Stary `build_events.py` liczył wszystko od zera: przy 12 dniach ~8 min i ~2,2 GB RAM, rosło liniowo (koniec grudnia ~85 dni → ~1 h i kilkanaście GB przy każdym wgraniu). Zasada: każde wgranie przelicza tylko dni, których dotyczą nowe pliki. Szczegóły zasad: decyzja 8 w `PLAN_REALIZACJI.md`. Zrobione 16.10 jako `uv run build-events` (`src/krakbus/observed/pipeline.py`); stary skrypt usunięty.

- [x] Wydzielić `build_day(vp_window, schedule_index, day, cfg, tz)` (`observed/events.py`)
- [x] Okno surowych danych dla daty obsługi D: partycje `date=` z D-1, D, D+1. Logger dzieli pliki wg daty **UTC**, lokalna doba zaczyna się o 22:00/23:00 UTC dnia poprzedniego, a kursy nocne doby D jadą już w D+1. Ze wszystkich zdarzeń z okna zostają tylko te z `service_date == D` (`ingest/raw.py`, cache trzyma w pamięci tylko 3 partycje)
- [x] Zapis per dzień: `data/processed/events/YYYY-MM-DD.parquet` (nadpisywany atomowo: zapis do pliku tymczasowego i zmiana nazwy)
- [x] `manifest.json`: dla każdego D odcisk wejść = nazwy i rozmiary plików `part-*` z okna D-1..D+1, wersje GTFS będące właścicielem kalendarza D-1..D+1 (data obsługi wybiera spośród tych trzech dni), progi sekcji `events` z configu, `PIPELINE_VERSION`
- [x] Domyślnie przeliczane są tylko dni, których odcisk się zmienił albo brakuje ich pliku; `--days` wymusza wskazane, `--dry-run` tylko pokazuje, `--full` liczy wszystko od zera
- [x] `days.csv`: `service_date`, `weekday`, `status`, `role`, `reason`, zdarzenia, linie, pojazdy, najdłuższa przerwa i łączny czas przerw w godzinach 5–23, `data_until` (ostatnia migawka w oknie), `calendar_stamp`. Status i rola liczone od nowa przy każdym uruchomieniu z zapisanych statystyk, więc zmiana progów `days` albo `special_days.yaml` nie wymaga przeliczania zdarzeń
- [x] Statusy (w tej kolejności): `provisional` (brak danych do 04:00 doby D+1, `night_end_hour`), `special` (z `special_days.yaml`), `gap` (przerwa > `max_gap_min` = 30 min albo < 500 zdarzeń), `complete`. Dzień `provisional` po kolejnym wgraniu przelicza się sam (zmienia się odcisk okna) i może przejść w `complete`
- [x] Wydruk na końcu: które dni przeliczono, które zmieniły status, liczba dni w każdym statusie i roli, hash manifestu
- [x] `week_analysis.py` czyta `events/` przez `krakbus.observed.store.load_events` (domyślnie dni `complete`, `DAYS=` wybiera ręcznie dowolne)
- [x] Test zgodności z pełnym przeliczeniem z 16.10: 1 531 496 zdarzeń identycznych we wszystkich kolumnach poza `prev_ts`/`next_ts`/`arr_unc`/`dep_unc` w 310/224 zdarzeniach, gdzie poprzedni raport pojazdu jest sprzed > 25 h, czyli poza oknem (stara wartość ≥ 91 453 s, nowa NaN; flagi `arr_ok`/`dep_ok` bez zmian). Brakuje 14 zdarzeń: wszystkie z datą obsługi 16.10 (partycji 16.10 jeszcze nie ma), opóźnienia −4,5 h do −9 h, czyli artefakty `wrong_service_day`. `week_analysis` na nowym magazynie: kluczowe liczby zgodne do trzeciej cyfry (różnica: 15.10 jest teraz `provisional`)
- [x] Test przyrostu: drugie uruchomienie bez nowych plików nic nie przelicza (< 1 s); dopisanie jednego pliku `part-*` przelicza tylko dni, których okno go zawiera; nowy właściciel kalendarza tylko dni sąsiednie (`tests/observed/test_manifest.py`). Pełne przeliczenie 12 dni: ~2,5 min
- [x] `build_chains` (C) liczony w tym samym kroku i na tym samym manifeście (`chains/D.parquet`; brak któregokolwiek pliku dnia wymusza przeliczenie). Kolejne artefakty per dzień dopisywać tak samo (`store.KINDS`)

### B. Jakość zdarzeń

- [x] Jeden spójny filtr: `delay_class` (`ok` / `outlier` > `outlier_s` = 1800 s / `wrong_service_day`) oraz `arr_good`, `dep_good` w zdarzeniach (16.10: ok 1 522 975, outlier 11 086, wrong_service_day 36)
- [x] Klasa `wrong_service_day` z przepinaniem na bliźniaka (ta sama linia, kierunek, start, identyczne `stop_times`, usługa aktywna w faktycznej dobie liczonej z `arr_ts − arr_s + 12 h`). Przepiętych 5018 zdarzeń w 465 kursach, mediana opóźnienia 70 s; bez bliźniaka zostaje 36 zdarzeń z flagą
- [x] Noc na granicy pokoleń (4→5, 9→10, 12→13.10): przesunięcie godz. 0–1 do złej doby naprawione przepinaniem (noc 9→10: usługa `20261010_4` nieaktywna w żadnym dniu, 1282 zdarzenia odzyskane). Puste godz. 2–3 to brak w surowym RT: po ok. 01:00 feed przestaje podawać kursy nocne starego pokolenia (noc kontrolna 10→11 ma ~17 tys. raportów w tych godzinach). Nie do odzyskania, dotyczy tylko linii nocnych poza `service_hours`
- [x] Kandydaci daty obsługi: wczoraj / dziś / jutro (pojazdy na pętli z kursem „na jutro”)
- [ ] Opcjonalnie (jak będzie czas): `move_ts` = pierwszy raport >15 m od postoju; porównać z `dep_ts`
- [x] Zachować `arr_ok` / `dep_ok` (niepewność ≤ 30 s); udokumentować w README skryptów

### C. Łańcuchy kursów (`vehicle_chains`)

Zrobione 16.10: `src/krakbus/observed/chains.py`, wynik `data/processed/chains/YYYY-MM-DD.parquet`, odczyt `krakbus.observed.store.load_chains`. Łańcuch jest **obserwowany** (kolejne kursy pojazdu w dobie wg czasu), plan bloku tylko do porównania — pojazdy bywają podmieniane i przechodzą między liniami.

- [x] Dla (`vehicle_id`, `service_date`) uporządkowana lista kursów (`chain_idx`), z planem bloku (`block_id`, `blk_idx`, `block_next_trip`) i flagą `follows_block`
- [x] Kolumny: `chain_idx`, `route_id`, `direction_id`, `trip_id`, `start_s`/`end_s` (rozkład), `first_ts`/`last_ts` (obserwacja), zapas rozkładowy `layover_sched_s` = start następnego − koniec tego, `gap_obs_s`, `arr_end_delay_s` (przyjazd na ostatni przystanek, `arr_ok`), `dep_first_delay_s` (ostatni odjazd z pierwszego, `dep_ok`), `next_dep_first_delay_s`, `carried` = `arr_end_delay_s > layover_sched_s − l_min_s` (`l_min_s` = 60 w `configs/config.yaml`)
- [x] Flaga `cross_route` (następny kurs pojazdu na innej linii); udział per linia w `events-quality`. 5,3% przejść ogółem; dla większości linii 0–2,5%, ale np. 151 ma 17,5% — kandydaci na warunek brzegowy w M3 D
- [ ] (→ M3, moduł kalibracji pętli) Krzywa pochłaniania z `chains/` zamiast z `week_analysis` (sekcja 6 liczy ją już na poprawionych zdarzeniach)
- [x] `block_id` zgodny z pojazdem: 0,990 (8 dni roboczych, miara jak w sekcji 6; w starym raporcie 0,991). Ostrzejsza `follows_block` (następny zaobserwowany kurs = następny w bloku): 0,982. Reset X 0,84 i przenoszenie OLS 0,138 (sekcja 6: 0,84 i 0,13; różnica, bo odjazd z pierwszego przystanku to teraz ostatni epizod postoju, a nie pierwszy)

### D. Fakty stylizowane + tooling raportu

- [x] Dodać `matplotlib` do `pyproject.toml`; `ruff` i `pytest` w grupie dev
- [x] Naprawić crash KS w `week_analysis` (dni bez dobrych zdarzeń w `WORK` są pomijane z komunikatem)
- [x] Przegonić raport na poprawionych zdarzeniach dla pełnych dni roboczych (9 dni: 5–9.10, 12–15.10)
- [x] Potwierdzić na ≥3 dniach: dryf wzdłuż trasy, wzrost rozrzutu, slope σ_e, krzywa pętli, korelacja między liniami (stan: `PLAN_REALIZACJI.md`, „Stan na 16.10”)
- [x] Bootstrap po kursach dla CI przy kluczowych statystykach (sekcja 12 `week_analysis`, B = 200; klaster = kurs w dobie dla dryfu, pojazd w dobie dla pętli). 8 dni roboczych: dryf mediany 145 s [143, 147], std ostatnia/pierwsza piąta 1,77 [1,74, 1,80], reset X 0,836 [0,827, 0,840], przenoszenie OLS 0,129 [0,121, 0,138]. Przedziały z próby są wąskie; zmienność między dniami (KS do 0,108) trzeba oceniać osobno, np. leave-day-out w M3
- [x] Skrypt: Marey rzeczywistości (`sandbox/gtfs-experiments/marey.py [linia] [dzień]`, domyślnie 179 i ostatni pełny dzień roboczy; rozkład szary, obserwacja wg pojazdu; od M2: `uv run marey`, kod w `krakbus.viz.marey`)
- [x] Kolumna `role` w `days.csv` (`unassigned` do zamrożenia, potem `calib` / `valid` / `excluded` z `configs/days_split.yaml`; nowe dni `complete` po zamrożeniu dostają `valid`)
- [x] Propozycja split dni: zbalansowana względem wersji rozkładu i dni tygodnia (`uv run propose-split` → `data/processed/days_split_proposal.yaml`; warstwy typ dnia × pokolenie, w każdej ~1/3 dni do walidacji rozłożone w czasie, `days.valid_fraction` = 0,34). Stan 16.10: calib 5, 7, 9, 12, 13.10 i weekend 10–11.10; valid 6.10 (wt), 8.10 (czw), 14.10 (śr). Weekend i pokolenie 20261010 mają po jednym dniu roboczym, więc na razie bez walidacji; przeliczać po każdym wgraniu aż do zamrożenia w M3
- [x] `configs/special_days.yaml`: 25.10 (zmiana czasu), 31.10–2.11 (Wszystkich Świętych), 10–12.11 (Święto Niepodległości), 24–26.12; z decyzją: `exclude` / `regime` / `check`
- [ ] (czeka na dane) Uzupełnić `special_days.yaml` o okres przedświąteczny w grudniu (od kiedy ruch odbiega od normy — sprawdzić w danych)
- [x] Eksport rankingu linii → `data/processed/route_ranking.csv` (`uv run route-ranking`; zdarzenia `arr_good` z pełnych dni roboczych, dni, kursy, pojazdy, mediana i p90 opóźnienia, skumulowany udział zdarzeń sieci, udział `cross_route` i `carried`). Stan 16.10 (8 dni): 160 linii; 50% zdarzeń daje 26 linii, 70% daje 49. Top: 179, 704, 144, 139, 173, 174, 304, 164. Wysoki `cross_route` mają 194, 169 i 494 (0,36–0,42), co jest ważne dla batchy N, bo 169 jest w korytarzu
- [x] Korelacja residuów na odcinkach sąsiednich vs odległych (sekcja 13 `week_analysis`): residuum przyrostu opóźnienia na odcinku, średnia linii w oknie 15 min, pary tylko między różnymi liniami. Ten sam odcinek 0,29, sąsiedni 0,04, 2 odcinki dalej 0,01, od 3 w górę 0,002–0,008, czyli tyle co losowe pary w tym samym oknie (0,005). Wejście do decyzji M2 B

### E. Jak będzie czas (nie blokuje M1 Done)

- [ ] Interpolacja luk na `shapes.txt` tylko dla brakujących przystanków, z flagą gorszej jakości
- [ ] Pokrycie statusem 1 vs wielkość odstępu

## Pliki, których to dotyczy

| Plik | Rola |
|------|------|
| `src/krakbus/ingest/gtfs_versions.py` | łączenie wersji GTFS, kalendarz efektywny, data obsługi |
| `src/krakbus/ingest/raw.py` | partycje loggera, okno D-1..D+1 |
| `src/krakbus/observed/events.py`, `pipeline.py` | zdarzenia na rozkładzie per dzień, przyrostowo (A2) |
| `src/krakbus/observed/chains.py` | łańcuchy kursów pojazdów per dzień (C) |
| `src/krakbus/observed/days.py`, `manifest.py` | rejestr dni i odciski wejść |
| `src/krakbus/observed/quality.py` | raport jakości (`events-quality`) |
| `src/krakbus/observed/store.py` | `load_events()` dla analiz |
| `configs/config.yaml`, `special_days.yaml` | progi i dni nietypowe |
| `tests/ingest/`, `tests/observed/` | testy |
| `sandbox/gtfs-experiments/week_analysis.py` | fakty + KS + wykresy |
| `sandbox/gtfs-experiments/README_skrypty.md` | kontrakt wejścia/wyjścia |
| `data/processed/events/`, `days.csv`, `manifest.json` | artefakty |
| `data/processed/chains/` | artefakt (nowy) |
| `pyproject.toml` | zależności, komendy |

## Definition of Done

- Zdarzenia z dni 5–9.10 (i kolejnych) mają sensowny match rozkładu; parquet zawiera **wszystkie** linie; liczba zdarzeń wg daty obsługi zgadza się z godzinami pracy loggera.
- Jest lista dni specjalnych w configu.
- `build_events` działa przyrostowo: kolejne wgranie przelicza tylko zmienione dni, `days.csv` ma status każdego dnia, test zgodności z pełnym przeliczeniem przechodzi.
- Istnieje tabela łańcuchów z zapasem i przenoszeniem.
- Raport tygodnia odpala się bez crashy i zapisuje wykresy.
- Jest `route_ranking.csv` (lub równoważny) pod batche N.
- Zespół ma listę pełnych dni roboczych i roboczą propozycję split kalibracja/walidacja.
- Nikt nie zaczyna M3 na starym parquet bez `gtfs_stamp` / per-day GTFS.

## Pułapki

- Sam weekend z „dobrym” `z_rozkladem` nie ratuje dni roboczych sprzed zmiany ZIP.
- Pooling dni przed naprawą GTFS zafałszuje dryf i pętlę.
- 704 ma krótkie zapasy — nie uśredniać wniosków o przenoszeniu tylko po 179.
- Ostatni dzień każdego wgrania jest niepełny (logger dalej zbiera); bez statusu `provisional` łatwo wciągnąć go do analiz jako dzień z dziurą.
- Liczenie dnia D tylko z partycji `date=D` gubi kursy nocne i początek lokalnej doby (partycje są w UTC).
- Brak daty obsługi nie może być cicho zastępowany domysłem: zdarzenie bez aktywnej usługi to sygnał błędu w rozkładzie albo w RT, a nie „pewnie wczoraj”.
