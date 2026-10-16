# Plan realizacji: propagacja opóźnień w sieci autobusowej Krakowa

Aktualizacja: 16.10.2026.

Dokument roboczy zespołu (3 osoby). Opis tematu dla prowadzącego jest w `TEMAT.md` i tu go nie dublujemy ani nie redagujemy.

**Cel oddania:** pełny zakres z `TEMAT.md` (model, kalibracja, walidacja, scenariusze, viz) **oraz docelowo DES całej autobusowej sieci Krakowa z gęstą kalibracją per linia** (nie tylko parametry zbiorcze), plus Unity MCP — **najpóźniej 31.12.2026**. Nic z zakresu nie jest ścieżką ucieczki.

**Relacja do `TEMAT.md`:** TEMAT traktuje rozbudowaną sieć i Unity jako zakres zaawansowany („jeśli wystarczy czasu”), a plan podnosi je do celu oddania. Zobowiązaniem wobec prowadzącego pozostaje MVP z sekcji 4 TEMAT (pilot, korytarz, linie walidacyjne spoza kalibracji, ablacje, baseline'y, 5 scenariuszy, viz lekka) — dlatego jest ono jawnym kryterium Done w M4/M5, niezależnie od postępu toru N. „Parametry zbiorcze” z TEMAT to w tym planie warstwa globalna/grupowa hierarchii kalibracji (global → grupa linii → linia); kalibracja per linia jest warstwą nad nią, nie zamiast niej.

**Gęstość pracy:** świadomie wyższa niż przy samym korytarzu — więcej równoległych torów i wcześniejszy scale-out (graf całego miasta od M2, pipeline kalibracji wieloliniowej od M3). Kto ma czas, bierze kolejne odblokowane zadanie.

**Organizacja pracy:** bez sztywnego podziału ról i bez bramek decyzyjnych. Statusy: **Done / In progress / Blocked** (Blocked zawsze z powodem). Każdy tor ma jedną **osobę odpowiedzialną**: pilnuje, że tor się rusza, aktualizuje checklistę i zgłasza Blocked. Nie oznacza to, że robi wszystko sama.

| Tor | Osoba odpowiedzialna |
|-----|----------------------|
| D (Dane) | *do uzupełnienia* |
| M (Model) | *do uzupełnienia* |
| N (Sieć city-wide) | *do uzupełnienia* |
| U (Unity MCP) | *do uzupełnienia* |

**Oś czasu:** kamienie milowe z datą „najpóźniej do”. Wcześniej = lepiej.

**Dane:** logger GTFS-RT działa **ciągle na osobnym komputerze**. Co jakiś czas dane trafiają z niego na wspólny folder Google Drive, a każdy z zespołu pobiera je stamtąd ręcznie i scala z lokalnym `data/raw_A` (do końca projektu; procedura w M0). Drive służy też jako kopia poza dyskiem loggera, plus okresowa kopia na inny dysk. Pipeline przetwarza je przyrostowo, a kalibracja pracuje na zamrożonej liście dni (decyzja 8). Surowych danych nie commitować publicznie.

**Unity:** tor równoległy od M2; **Unity MCP**. Symulacja w Pythonie; Unity odtwarza eksport.

**Szczegóły operacyjne:** [`milestones/`](milestones/README.md).

---

## Docelowa sieć (definicja Done produktu)

| Warstwa | Wymaganie |
|---------|-----------|
| Topologia | Wszystkie linie autobusowe z aktywnego GTFS dnia (słupki, odcinki, shapes, łańcuchy `block_id`, także łańcuchy przechodzące między liniami) |
| Symulacja | Pełna doba ruchu sieci w DES (SimPy), wspólne `u` na współdzielonych odcinkach |
| Kalibracja | Hierarchicznie: globalne / segmentowe `u`, `e_d`, γ → grupa linii (pooling, „parametry zbiorcze”) → **per linia** (dryf / skale η / reguła pętli) |
| Walidacja | OOS dni; **linie spoza kalibracji metodą leave-line-out** (prognoza z warstwy global/grupa przed dopasowaniem linii); ablacje; baseline'y; metryki sieciowe i per-route coverage |
| Scenariusze | Jak w TEMAT, uruchamiane na korytarzu **i** (gdzie ma sens) na pełnej sieci |
| Viz | pydeck + Unity: replay; obs‖sim; docelowo widok sieci / korytarza z danymi city-wide |

Ścieżka budowy (nie da się zacząć od „wszystkie linie naraz” w debugu): **179 → korytarz → batche linii → cała sieć**, ale architektura i joby kalibracyjne od początku pod city-wide.

---

## Kamienie milowe

Kolejność wg daty domknięcia.

| ID | Kamień | Najpóźniej | Done oznacza | Szczegóły |
|----|--------|------------|--------------|-----------|
| **M0** | Fundament | *trwa* | Logger, TEMAT, pierwsze dane/raport | [M0](milestones/M0_fundament.md) |
| **M1** | Dane wiarygodne | **24.10.2026** | GTFS per dzień, events, łańcuchy, fakty, kalendarz dni specjalnych; pipeline gotowy na wszystkie linie | [M1](milestones/M1_dane.md) |
| **M2** | DES (pilot + graf miasta) | **7.11.2026** | Silnik + testy na 179; loader grafu/łańcuchów **całego** GTFS (z łańcuchami międzyliniowymi); szybka ścieżka wektorowa zgodna z SimPy; CLI scope=pilot\|corridor\|city | [M2](milestones/M2_des.md) |
| **M3** | Kalibracja (skalowalna) | **21.11.2026** | Pipeline S + Optuna/ABC; **wspólne `u` skalibrowane na korytarzu**; γ; prognozy leave-line-out zamrożone; **batch per-route** (API pod wszystkie linie) | [M3](milestones/M3_kalibracja.md) |
| **M4** | Walidacja + korytarz + start city | **5.12.2026** | **MVP z TEMAT kompletne** (walidacja/ablacje/baseline, korytarz); draft raportu; **pierwsze batche linii poza korytarzem** skalibrowane | [M4](milestones/M4_walidacja.md) |
| **M5** | Scenariusze | **12.12.2026** | 5 scenariuszy; warianty korytarz + sieć (S2/S3) | [M5](milestones/M5_scenariusze.md) |
| **M6** | Cały Kraków + Unity | **20.12.2026** | **100% aktywnych linii** w sim + kalibracja per linia; Unity demo; viz | [M6](milestones/M6_cala_siec.md) |
| **U** | Unity MCP | ‖ M2→M6, domknięcie **20.12** | Replay + obs‖sim; potem skala wizualizacji | [U](milestones/U_unity_mcp.md) |
| **N** | Scale-out sieci | ‖ M2→M6, domknięcie **20.12** | Tor gęstości: batche, compute, coverage, perf | [N](milestones/N_siec_krakow.md) |
| **M7** | Raport + oddanie | **31.12.2026** | Raport, README, prezentacja | [M7](milestones/M7_raport.md) |

---

## Cztery tory równoległe

```
TOR D (Dane)       TOR M (Model)                  TOR N (Sieć city-wide)     TOR U (Unity MCP)

logger+sync
GTFS/events/łańcuchy (M1) ──► DES + graf ALL (M2) ────────► batche linii (N)
fakty + kalendarz ──────────► calib API + u korytarza (M3) ► per-route jobs (N)
                              leave-line-out (M3) ────────► dopiero potem fit linii OOS (N)
                              walidacja+korytarz (M4) ────► coverage→100% (M6)
                              scenariusze (M5) ───────────► S2/S3 na sieci
eksport ◄── wyniki ─────────────────────────────────────────────────────► Unity replay
```

1. **D** — sync, przetwarzanie przyrostowe i rejestr dni, jakość, events dla całej sieci (nie tylko 179), kalendarz dni specjalnych.
2. **M** — mechanika, kalibracja, walidacja, scenariusze.
3. **N** — scale-out: kolejka linii, joby, wydajność doby city-wide, coverage report.
4. **U** — Unity MCP; nie kasujemy przy obciążeniu N — idzie równolegle na eksporcie.

---

## Decyzje metodologiczne (przekrojowe)

Dotyczą kilku kamieni naraz; szczegóły w checklistach.

1. **Wersje rozkładu.** Feed ZTP jest kroczący: `service_id` i `trip_id` mają prefiks daty pokolenia (np. `20261005_1_…`), kalendarz jest tylko w `calendar_dates.txt`. Rozkład kursu bierzemy po `trip_id` z najnowszej wersji, która go zawiera (ten sam `trip_id` ma identyczne `stop_times` we wszystkich wersjach); kalendarz dnia D z najnowszej wersji, która ma wpis na D. Data obsługi zdarzenia: wczoraj / dziś / jutro, tylko spośród dni, w których usługa kursu jest aktywna; brak dopasowania = brak daty (nie cichy wybór „wczoraj”). Implementacja: `sandbox/gtfs-experiments/gtfs_versions.py`.
2. **Walidacja na liniach spoza kalibracji przy kalibracji per linia.** Skoro docelowo każda linia dostaje własne parametry, linie walidacyjne z TEMAT (194, 494, 139, 138, 123, porównawczo 704) walidujemy **leave-line-out**: symulacja z warstwy global/grupa, bez danych tej linii w kalibracji. Wyniki zapisujemy i zamrażamy (M3) **zanim** tor N dopasuje te linie. Metryki po dopasowaniu per linia to dopasowanie na danych uczących, nie walidacja.
3. **Identyfikacja `u`.** Na jednej linii wspólne zakłócenie `u` zlewa się z dryfem `a` i szumem `η` — wyróżnia je dopiero korelacja między liniami na wspólnych odcinkach. Dlatego parametry `u` kalibrujemy wspólnie co najmniej na korytarzu (M3), a nie na samym 179. Korelacja między liniami na wspólnych odcinkach jest wtedy składową S do kalibracji `u`, ale jej wzór dobowy i korelacja na liniach spoza korytarza zostają do walidacji.
4. **Łańcuchy międzyliniowe.** `block_id` czasem przechodzi między liniami. W jobie kalibracji pojedynczej linii opóźnienie wjeżdżające z innej linii jest warunkiem brzegowym z danych (obserwowane opóźnienie na końcu poprzedniego kursu w łańcuchu), a nie zerem. W symulacji city-wide łańcuch jedzie w całości.
5. **Struktura przestrzenna `u` w skali miasta.** Do decyzji w M2 (przed S2 na sieci): niezależne pola `u` na odcinkach vs korelacja między sąsiednimi odcinkami / w obrębie korytarza ulicznego. Bez tego „fala” rozchodzi się tylko przez dosłownie wspólne odcinki. Decyzję i jej uzasadnienie z danych (korelacja residuów na odcinkach sąsiednich vs odległych) zapisać w configu i w raporcie. **Decyzja (16.10, M2): `independent`** — `u` wspólne dla wszystkich linii na tym samym skierowanym odcinku, niezależne między odcinkami, AR(1) w czasie (okna 900 s). Korelacja residuów między liniami z M1: ten sam odcinek 0,29, sąsiedni 0,04, od 3 odcinków dalej tyle co losowe pary (0,005). `configs/sim.yaml` (`u.spatial`), spec M2.
6. **Szybka ścieżka obliczeń.** Przy γ=0 pojazdy są niezależne poza łańcuchem i polem `u`, więc dobę można liczyć zwektoryzowaną rekursją (numpy) zamiast pełnego SimPy. Używamy jej w jobach kalibracyjnych; SimPy zostaje silnikiem referencyjnym (walidacja, scenariusze, γ>0). Test równoważności (te same seedy → te same opóźnienia) jest warunkiem użycia.
7. **Kalendarz dni.** Do kalibracji/walidacji tylko pełne dni robocze. Jawna lista dni specjalnych w configu: zmiana czasu 25.10 (nd), 1.11 (nd, Wszystkich Świętych) i dni okołoświąteczne 31.10/2.11, 11.11 (śr, Święto Niepodległości) i 10.11/12.11 do sprawdzenia, okres przedświąteczny w grudniu. Split dni kalibracja/walidacja zbalansowany względem wersji rozkładu (zmiany 5.10, 10.10, 13.10, kolejne wg loggera).
8. **Ciągły napływ danych.** Dane przybywają do końca projektu, więc:
   - **Przetwarzanie przyrostowe:** wyniki zapisywane osobno dla każdej daty obsługi (`data/processed/events/YYYY-MM-DD.parquet`, komenda `uv run build-events`), dzień D liczony z okna surowych partycji D-1..D+1 (partycje loggera są w UTC, kursy nocne jadą po północy). `manifest.json` trzyma odcisk wejść każdego dnia; wgranie przelicza tylko dni ze zmienionym odciskiem, nowa wersja GTFS tylko dni ze zmienionym właścicielem kalendarza, `--full` wszystko. Pamięć i czas zależą od liczby nowych dni, nie od wszystkich zebranych.
   - **Rejestr dni `days.csv`** ze statusem `complete` / `provisional` / `gap` / `special`. Do analiz, kalibracji i walidacji wchodzą tylko dni `complete`. Ostatni dzień wgrania jest zawsze `provisional` i dolicza się przy kolejnym wgraniu.
   - **Zamrożony podział dni:** do M3 rola dnia (`calib` / `valid` / `excluded`) jest propozycją; przy starcie kalibracji w M3 lista dni kalibracyjnych zostaje zamrożona w `configs/days_split.yaml`. Każdy dzień `complete`, który przyjdzie później, automatycznie dostaje rolę `valid` — to dodatkowa walidacja na dniach z przyszłości (out-of-time), a nie powód do ponownej kalibracji.
   - **Migawka danych przy wynikach:** każdy artefakt kalibracji, walidacji i scenariuszy zapisuje listę użytych dni i hash `manifest.json`. Nowe dane nigdy nie zmieniają po cichu już policzonego wyniku; ponowna kalibracja na większej liczbie dni to świadoma decyzja z nową migawką.
   - **Rutyna po wgraniu:** ręczne pobranie z Google Drive, rozpakowanie, scalenie z `data/raw_A` (tylko dokładanie plików; pliki `part-*` są niezmienne, niepełny bywa tylko ostatni dzień), `build-events` (przyrostowo), raport — konkretne polecenia w [M0](milestones/M0_fundament.md). Każdy robi to u siebie; zgodność danych między osobami sprawdza się po hashu manifestu wypisywanym przez `build-events`.

---

## Układ repo (przy M2)

```
configs/                 # config.yaml, special_days.yaml, days_split.yaml; parametry per route, scenariusze, batche kalibracji
data/raw_A|processed/
src/krakbus/             # pakiet (uv sync), komendy w [project.scripts]
  config.py, logger.py
  ingest/                # gtfs_versions.py, raw.py (partycje loggera)
  observed/              # zdarzenia, rejestr dni, manifest; build-events, events-quality
  sim/                   # DES; scope=pilot|corridor|city; szybka ścieżka wektorowa
  calib/                 # S, Optuna/ABC, per-route batch runner, leave-line-out
  scenarios/
  viz/
sandbox/gtfs-experiments/ # logger, week_analysis.py (eksploracja)
notebooks/
tests/                   # lustro src/krakbus/ (ingest/, observed/, ...)
docs/
```

---

## Backlog (skrót P0)

Pełne checklisty: [`milestones/`](milestones/README.md).

- [x] **M1 / P0:** match GTFS do dnia + przeliczenie events (wszystkie linie w parquet) — `gtfs_versions.py`, testy w `tests/`
- [x] **M1 / P0:** `build-events` przyrostowo per dzień + `manifest.json` + `days.csv` (M1 A2), szkielet `src/krakbus/` (M2 A)
- [x] **M1 / P0:** `vehicle_chains` per dzień z flagą `cross_route` (M1 C)
- [ ] Stałe: logger + sync + backup (rutyna w M0)
- [ ] Wpisać osoby odpowiedzialne za tory (tabela wyżej)
- [ ] **M2:** silnik 179 **oraz** graf/łańcuchy całego miasta w loaderze; decyzja o strukturze przestrzennej `u`
- [ ] **M3/N:** API kalibracji per `route_id` + kolejka batchy; `u` na korytarzu; zamrożone prognozy leave-line-out
- [ ] Tor U: kontrakt eksportu (od M2)

---

## Ryzyka (bez bramek — alarm i naprawa, bez cięcia zakresu)

| Ryzyko | Objaw | Reakcja |
|--------|--------|---------|
| Zły match GTFS | brudne opóźnienia, dni przesunięte o 1 | reguła z decyzji 1 + kontrola liczby zdarzeń i `calendar_stamp` dzień po dniu w `days.csv` |
| Walidacja linii OOS zjedzona przez kalibrację per linia | brak niezależnego testu przestrzennego | leave-line-out zamrożony w M3 przed batchami N (decyzja 2) |
| `u` niezidentyfikowane | `u` zamienia się z `a`/`η` przy fit na jednej linii | wspólna kalibracja na korytarzu (decyzja 3) |
| Łańcuchy międzyliniowe | job jednej linii zaniża przenoszenie | warunek brzegowy z obserwacji (decyzja 4) |
| Perf. doby city-wide | sim nie kończy się w praktycznym czasie | szybka ścieżka wektorowa (decyzja 6), mniej I/O, równoległe pojazdy/repliki, profilowanie (tor N) — zakres zostaje |
| Kalibracja per linia nie mieści się w czasie | kolejka stoi | więcej równoległych jobów, ciepły start z sąsiednich linii, hierarchia (global → grupa → route), **nie** redukcja do „tylko korytarz” |
| Linie z małą liczbą zdarzeń | niestabilne S | reguły minimum n + pooling części parametrów z grupą; i tak osobny rekord per linia |
| Dni specjalne w próbie | zawyżony `e_d`, fałszywe efekty | lista dni specjalnych w configu (decyzja 7) |
| Czas i pamięć przeliczenia rosną z liczbą dni | pełne przeliczenie ~1 h i kilkanaście GB przy końcu zbierania | przetwarzanie przyrostowe per dzień z manifestem (decyzja 8, M1 A2) |
| Nowe dane zmieniają wyniki po cichu | inna kalibracja / walidacja przy każdym wgraniu, niepowtarzalne liczby w raporcie | zamrożony podział dni + migawka danych przy każdym wyniku (decyzja 8) |
| Niepełny ostatni dzień w analizach | sztuczna dziura wieczorem, zaniżone liczby | status `provisional` w `days.csv`, do analiz tylko `complete` |
| Unity vs sieć | konflikt czasu | oba tory; eksport city-wide może być downsamplowany do viz |
| Święta / M7 | raport | draft jako zadanie w M4; M6 twardo 20.12 |

---

## Stan na 16.10.2026 (skrót)

- Logger od 4.10 (wieczór), dane do 16.10. Dziury łącznie ~1,8 h, wszystkie w nocy albo poza szczytem.
- **Naprawiony błąd dat** (16.10): stary pipeline brał jeden, najnowszy rozkład i przy kursach spoza niego przypisywał datę „wczoraj”, więc dni 5–9.10 były przesunięte o jeden, a rozkład był dopasowany tylko dla ~30% zdarzeń. Rzekomo pusty 9.10 był w pełni zebrany. Po naprawie: 100% zdarzeń dopasowanych do rozkładu, 99,8% z datą obsługi, ~150 tys. zdarzeń i 147–153 linie na dzień roboczy.
- **Pełne dni robocze: 9** — 5–9.10 i 12–15.10 (wcześniej raport widział 5). Weekend: 10–11.10. Pokolenia rozkładu w danych: 20261005, 20261010, 20261013.
- Fakty stylizowane z TEMAT potwierdzone na 9 dniach: KS między dniami roboczymi ≤ 0,10 (pooling uzasadniony), dryf mediany 59 → 205 s wzdłuż trasy, reset na pętli ~84%, γ z efektami stałymi ≈ 0, brak zbijania (obserwacja / model zerowy 0,68), korytarz 179: 124, 144, 169, 173, 174, 608.
- Pipeline events/raport działa na wszystkich liniach (`gtfs_versions.py` + testy).
- **Przetwarzanie przyrostowe działa** (16.10, M1 A2): `uv run build-events` w pakiecie `src/krakbus/`, wynik zgodny z pełnym przeliczeniem. W `days.csv`: 10 dni `complete` (5–14.10), 4.10 `gap` (start loggera), 15.10 `provisional` (dane kończą się 16.10 o 00:06, brak kursów nocnych; przejdzie w `complete` po kolejnym wgraniu). Raport `week_analysis` liczy więc teraz 8 pełnych dni roboczych zamiast 9; kluczowe liczby bez zmian do trzeciej cyfry.
- **Zmiana względem planu z 14.10:** docelowo **cała sieć + kalibracja per linia**, bez ucinania Unity/scenariuszy; dodany tor **N** i wyższa gęstość zadań; decyzje metodologiczne 2–6 (leave-line-out, `u` z korytarza, łańcuchy międzyliniowe, struktura przestrzenna `u`, szybka ścieżka).
- **Łańcuchy kursów** (16.10, M1 C): `data/processed/chains/`, łańcuch obserwowany per pojazd; `block_id` zgodny z pojazdem w 99%, przejścia na inną linię 5,3% (większość linii 0–2,5%, 151: 17,5%).
- **Jakość zdarzeń** (16.10, M1 B): jeden filtr `delay_class` / `arr_good` / `dep_good`; kursy zgłaszane z `trip_id` innej doby przepinane na bliźniaka (5018 zdarzeń), bez bliźniaka zostaje 36. Noce graniczne pokoleń mają w RT lukę w godz. 2–3 (tylko linie nocne).
- **M1 Done** (16.10): `route_ranking.csv` (160 linii; 26 linii daje 50% zdarzeń, 49 daje 70%), robocza propozycja podziału dni (valid 6, 8, 14.10; reszta calib), raport na `arr_good` z CI z bootstrapu (dryf 145 s [143, 147], reset X 0,836 [0,827, 0,840]), Marey dla dowolnej linii. Korelacja residuów między liniami: ten sam odcinek 0,29, sąsiedni 0,04, dalej jak losowe, co jest wejściem do decyzji 5 w M2. Czeka na dane: kontrola 25.10 i okres przedświąteczny.
- **M2 etap 1** (16.10): `uv run simulate` — sieć dnia z całego GTFS, silnik SimPy z regułą pętli, γ i warunkiem brzegowym, testy weryfikacyjne D zielone, decyzja 5 = `independent`. Doba city (10 279 kursów) liczy się w 0,4 s.
- Następne: M2 etap 2 (szybka ścieżka numpy i test równoważności z SimPy), etap 3 (Marey z symulacji, eksport do Unity).

Szczegóły liczb — `data/processed/week_report/report.txt`.
