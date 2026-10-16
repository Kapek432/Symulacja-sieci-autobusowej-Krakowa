# Dziennik prac

Po każdej zakończonej implementacji (kod, zmiana danych/pipeline'u, decyzja metodologiczna) dopisujemy wpis **na górze** listy. Wpis robi osoba (albo jej agent), która wykonała pracę. Dziennik mówi „co i dlaczego”; szczegóły kodu są w commitach, a stan zadań w `docs/milestones/`.

Szablon:

```
## YYYY-MM-DD — krótki tytuł (kamień milowy, np. M1 A2)

**Kto:** imię nazwisko
**Commity:** abc1234, def5678

Zrobione:
- ...

Decyzje:
- decyzja — dlaczego (odrzucona alternatywa, jeśli była)

Sprawdzone:
- testy / porównania / liczby, które potwierdzają wynik

Otwarte / dalej:
- ...
```

Zasady:

- Decyzja, która zmienia plan (zakres, metodologię, dane), trafia też do `docs/PLAN_REALIZACJI.md` albo odpowiedniego kamienia milowego; w dzienniku zostaje krótka notka z odnośnikiem.
- Liczby z dziennika muszą dać się odtworzyć: podawać dni danych (albo hash manifestu z `build-events`) i komendę.
- Bez wpisów dla drobiazgów (literówka, formatowanie).

---

## 2026-10-16 — DES etap 3: Marey obs ‖ sim, eksport dla Unity, M2 Done (M2 E, F; tor U)

**Kto:** Kacper Lipiec
**Commity:** f8f3e30, aabe019, 3dfe585

Zrobione:
- Pakiet `src/krakbus/viz/`: `layers` (obserwacja i przebieg symulacji w jednym schemacie warstwy), `marey` (`uv run marey`, nakładka obserwacja ‖ symulacja), `export_unity` (`uv run export-unity`).
- Kontrakt eksportu v1: `docs/EXPORT_UNITY.md`. `sandbox/gtfs-experiments/marey.py` jest teraz nakładką na moduł.
- `tests/__init__.py`, żeby testy `tests/viz` korzystały z syntetycznego rozkładu z `tests/sim/conftest.py`.
- M2 oznaczony jako Done; tor U ma odhaczony kontrakt eksportu.

Decyzje:
- Rozkład w Mareyu z `Network` (etap 1) zamiast osobnego parsowania `stop_times`: jedna definicja kursów i kierunków dnia dla symulacji i wykresu.
- Jedna warstwa kolorowana wg pojazdu (jak dotąd, widać łańcuchy), dwie wg źródła z legendą (przy kolorach pojazdów nakładka byłaby nieczytelna).
- Eksport per przystanek (wiersz na przyjazd i odjazd ze współrzędnymi przystanku), Unity interpoluje. Odrzucone próbkowanie pozycji co N sekund: większe pliki i decyzja o kroku, której model nie potrzebuje. Dodatkowe kolumny względem szkicu w `U_unity_mcp.md`: `event`, `direction_id`, `stop_id`, `stop_sequence` (kolejność i rozróżnienie przyjazd/odjazd).
- Parquet albo JSON Lines (`--format`): JSONL czyta się w C# bez dodatkowej biblioteki.
- Próbki eksportu zostają lokalnie: zasada repo „bez `data/`” ma pierwszeństwo przed dopuszczeniem małej próbki w `U_unity_mcp.md`.

Sprawdzone:
- 102 testy w całym projekcie (13 nowych w `tests/viz`), ruff.
- 14.10, manifest dd5a166abd0e2966: Marey 179 sam i z przebiegiem `2026-10-14_pilot_simpy_s0` obejrzany (dwa panele, kursy monotoniczne, obserwacja 119 kursów na kierunek, symulacja 123); wykres samej obserwacji taki jak przed przeniesieniem.
- Eksport pilota: 12 054 wiersze = 2 × 6 027 zdarzeń, 15 bloków, bbox w Krakowie (lat 50,004–50,074, lon 19,923–19,961); obserwacja 179: 10 950 wierszy, 20 pojazdów.

Otwarte / dalej:
- Tor U: scena i loader na próbce pilota (faza 1).
- Marey i eksport wczytują cały rozkład (ok. 16 s); przy wielu wykresach albo batchach warto cache'ować sieć dnia.

---

## 2026-10-16 — DES etap 2: szybka ścieżka `fast` i równoważność z SimPy (M2 C2)

**Kto:** Kacper Lipiec
**Commity:** 09929cd (plany etapów 2 i 3), da7814f, 0d89378

Zrobione:
- `src/krakbus/sim/fast.py`: `run_fast` z sygnaturą `run_simpy`; `uv run simulate --engine fast`.
- `run.json` ma osobno czas silnika (`engine_s`) i całego przebiegu (`elapsed_s`).

Decyzje:
- Przy γ = 0 przyrost na odcinku nie zależy od stanu sieci, więc opóźnienie na przystanku = odjazd kursu + suma przyrostów od jego początku; suma skumulowana raz dla całej sieci, pętla w Pythonie tylko po pozycji w bloku (do ok. 58 kroków). Odrzucona pętla po przystankach w numpy: tyle kroków, ile przystanków w najdłuższym kursie, bez zysku.
- Tolerancja równoważności 1e-6 s, nie równość bitowa: SimPy sumuje przyrosty po kolei, fast przez różnicę sum skumulowanych (błąd rzędu 1e-9 s przy sumach do 1e7 s).
- `fast` przy γ ≠ 0 rzuca wyjątek (decyzja 6 w planie: sprzężenie od odstępu tylko w SimPy).

Sprawdzone:
- 44 testy w `tests/sim` (13 nowych w `test_fast`, 1 w `test_run`, 3 na prawdziwym GTFS), ruff.
- Syntetyczna sieć z pętlami miała w pierwszej wersji przenoszenie opóźnienia tylko w 2 kursach na 200; zapas skrócony do 2 min, teraz 99 na 200, więc test sprawdza obie gałęzie reguły pętli.
- 14.10, manifest dd5a166abd0e2966, ziarno 0, `boundary: observed`: SimPy = fast do 1e-6 s dla pilota, korytarza (27 kursów brzegowych) i city. Czas samego silnika: pilot 0,025 / 0,013 s, city 0,30 / 0,015 s (SimPy / fast); mediany opóźnienia identyczne (70 i 67 s).

Otwarte / dalej:
- `fast` liczy przyrosty dla całej sieci dnia, nawet przy pilocie; przy kalibracji jednej linii można zawęzić do wierszy zakresu, jeśli to będzie wąskie gardło.
- Etap 3: Marey z symulacji, eksport do Unity.

---

## 2026-10-16 — DES etap 1: sieć dnia, silnik SimPy, `simulate`, decyzja o `u` (M2 A–D)

**Kto:** Kacper Lipiec
**Commity:** f910361 (spec), c18f1bd, e2820dc (plan), bccab4b, 88ce472, 7041d7a, 7bdf134, af63b3a, 6fadc80, 587f4fd

Zrobione:
- Pakiet `src/krakbus/sim/`: `params` (`configs/sim.yaml`), `network` (sieć dnia z całego GTFS: kursy w kolejności bloków, zapasy na pętli, skierowane odcinki ze wspólnym `seg_id`), `noise` (szum losowany z góry), `model` (przyrost na odcinku, reguła pętli), `boundary` (warunek brzegowy), `engine` (proces SimPy na blok, opcjonalne γ), `run` (CLI `uv run simulate`).
- Wynik w `data/processed/sim/<run_id>/`: zdarzenia w schemacie zbliżonym do obserwowanych i `run.json` z parametrami, wersjami GTFS, hashem manifestu i commitem.
- Spec i plan etapu 1 w `docs/superpowers/`.

Decyzje:
- Decyzja 5 z planu: `u` = `independent` (wspólne dla linii na tym samym odcinku, niezależne między odcinkami, AR(1) po oknach 900 s). Uzasadnienie z M1: korelacja residuów między liniami na tym samym odcinku 0,29, na sąsiednim 0,04, dalej jak losowe. Odrzucone `neighbors`/`corridor`: dodatkowe parametry bez sygnału w danych.
- Cały szum (e_d, δ, η, u) losowany z góry dla całej sieci dnia w stałej kolejności: kurs dostaje ten sam szum niezależnie od zakresu, a szybka ścieżka z etapu 2 może dostać te same tablice. Odrzucone losowanie wewnątrz procesów SimPy, bo wynik zależałby od kolejności zdarzeń.
- Okno `u` i pora dryfu wg rozkładowego odjazdu z przystanku, nie faktycznego: inaczej opóźnienie przesuwałoby kurs między oknami i silniki rozjeżdżałyby się na granicach okien.
- Pojazd jedzie blok z planu (`block_id`), nie zaobserwowany łańcuch (block_id zgadza się w 99,1%); obserwacje służą tylko warunkowi brzegowemu (`boundary: observed`).
- Postój pośredni = rozkładowy (w GTFS ZTP zawsze 0), więc opóźnienie odjazdu = przyjazdu; model postoju zostaje na później, jeśli kalibracja go wymusi.

Sprawdzone:
- 72 testy (`tests/sim`: zerowy szum = rozkład, pochłanianie i przenoszenie na pętli, dryf, wzrost rozrzutu z η, niezależność łańcuchów przy γ = 0 i u = 0, γ na odstępie, warunek brzegowy; 2 testy na prawdziwym GTFS), ruff na `src tests`.
- 14.10, manifest dd5a166abd0e2966, parametry robocze z `sim.yaml`, ziarno 0: pilot 246 kursów; korytarz 844 kursy, 27 brzegowych (`observed`); city 10 279 kursów, 218 738 zdarzeń, mediana opóźnienia 67 s, na końcu kursu 125 s (p10 −23 s, p90 299 s). Silnik city 0,4 s; całość komendy ok. 16 s (wczytanie rozkładu).
- 179 z prawdziwego GTFS przy zerowym szumie odtwarza rozkład co do sekundy.

Otwarte / dalej:
- Etap 2: `sim.fast` i test równoważności z SimPy. SimPy liczy dobę city w 0,4 s, więc szybka ścieżka jest potrzebna dopiero przy tysiącach przebiegów w kalibracji; zostaje w planie, ale bez pośpiechu.
- Wczytanie rozkładu (16 s) dominuje czas; przy batchach (tor N) warto cache'ować sieć dnia.
- Etap 3: Marey z symulacji z nakładką obserwacji, eksport do Unity.
- Parametry modelu nieskalibrowane (M3); bez porównań sim vs obs.

---

## 2026-10-16 — domknięcie M1: ranking linii, podział dni, CI, struktura u, Marey (M1 D)

**Kto:** Kacper Lipiec
**Commity:** d42c2e5

Zrobione:
- `uv run route-ranking` (`src/krakbus/observed/routes.py`) → `data/processed/route_ranking.csv`.
- `uv run propose-split` (`src/krakbus/observed/split.py`) → `data/processed/days_split_proposal.yaml` w formacie `days_split.yaml`; nowy próg `days.valid_fraction` = 0,34.
- `week_analysis`: filtry `arr_good`/`dep_good` zamiast własnego progu 1800 s; sekcja 12 (bootstrap klastrowy), sekcja 13 (korelacja residuów przyrostów na odcinkach).
- `sandbox/gtfs-experiments/marey.py`: Marey rozkład vs obserwacja dla linii i dnia.
- M1 oznaczony jako Done.

Decyzje:
- Ranking liczy tylko zdarzenia `arr_good` z pełnych dni roboczych; weekend to inny reżim i zaniżałby liczby linii dziennych.
- Podział dni: warstwy typ dnia × pokolenie rozkładu, dni walidacyjne rozłożone w czasie w każdej warstwie. Odrzucone „pierwsze dni → calib, ostatnie → valid”, bo walidacja wpadałaby wtedy w całości w jedno pokolenie. Warstwa jednodniowa idzie do kalibracji (weekend, 12.10).
- Dni bez statusu `complete` nie trafiają do `excluded` w propozycji: po zamrożeniu dzień `provisional` zostałby wykluczony na zawsze.
- Bootstrap: klaster = kurs w dobie (dryf) i pojazd w dobie (pętla), bo zdarzenia jednego kursu i kolejne pary jednego pojazdu nie są niezależne.
- Korelacja `u` tylko między różnymi liniami w oknie 15 min: para z tym samym autobusem dawałaby ujemną korelację z szumu wspólnego czasu przyjazdu na przystanku łączącym odcinki. Decyzja o strukturze `u` zostaje w M2; dane przemawiają za `independent` ze wspólnym `u` na odcinku dzielonym przez linie (notka w `M2_des.md`).
- Spearman liczony jako Pearson na rangach, bez dodawania scipy.

Sprawdzone:
- 45 testów (`test_routes`, `test_split`), ruff na `src tests`.
- Manifest dd5a166abd0e2966, dni robocze complete 5–9, 12–14.10: ranking 160 linii, 50% / 70% zdarzeń = 26 / 49 linii; wysoki `cross_route` 194, 169, 494 (0,36–0,42); 704 `carried` 0,96 (krótkie zapasy, zgodnie z pułapką w M1).
- Raport: kluczowe liczby jak przed zmianą filtra (dryf 59 → 204 s, reset X 0,84, OLS 0,129, block_id 0,991); KS max 0,108. CI 95%: dryf 145 s [143, 147], reset X [0,827, 0,840], OLS [0,121, 0,138].
- Korelacja residuów: ten sam odcinek 0,29 (n = 498 tys. par), k = 1: 0,04, k = 2: 0,01, k ≥ 3: 0,002–0,008, losowe 0,005.
- Marey 179 dla 14.10 obejrzany: kursy monotoniczne, obserwacja przy rozkładzie (błąd sortowania `stop_sequence` jako tekstu naprawiony przed commitem).

Otwarte / dalej:
- Po 25.10: kontrola zmiany czasu w `days.csv` i `events-quality`; w grudniu okres przedświąteczny w `special_days.yaml`.
- Propozycję podziału przeliczać po każdym wgraniu aż do zamrożenia w M3.
- Krzywa pochłaniania z `chains/` przy module kalibracji pętli (M3).

---

## 2026-10-16 — jakość zdarzeń: wrong_service_day i jeden filtr (M1 B)

**Kto:** Kacper Lipiec
**Commity:** fef3271

Zrobione:
- `src/krakbus/observed/wrong_day.py`: przepinanie kursów zgłoszonych z `trip_id` innej doby na bliźniaka w usłudze aktywnej w faktycznej dobie; oryginał w `rt_trip_id`, flaga `trip_remapped`.
- Jeden filtr jakości w zdarzeniach: `delay_class` (`ok` / `outlier` / `wrong_service_day`), `arr_good`, `dep_good`. Progi w configu: `events.outlier_s` = 1800, `events.wrong_day_min_s` = 43200.
- `PIPELINE_VERSION` = 4 (pełne przeliczenie).

Decyzje:
- Faktyczna doba kursu liczona z obserwacji (`arr_ts − arr_s + 12 h`, lokalna data), a nie z kalendarza: obejmuje też usługę nieaktywną w żadnym dniu (noc 9→10.10, `20261010_4`). Per zdarzenie, bo ten sam pojazd może jechać ten sam `trip_id` w dwóch dobach okna.
- Bliźniak = ta sama linia, kierunek i start oraz identyczne `stop_times`, tylko jednoznaczne dopasowania. Dopasowanie „po godzinie” bez sprawdzenia przebiegu odrzucone, bo mogłoby podmienić wariant trasy.
- Kursy z 1–2 zdarzeniami na pętli po przepięciu mają czasem |opóźnienie| w godzinach (32 zdarzenia); zostają, bo filtr `outlier` je odcina.
- Puste godz. 2–3 w nocach granicznych pokoleń (4→5, 9→10, 12→13) to brak danych w RT, nie błąd pipeline'u; tylko linie nocne, poza `service_hours`, bez działań.

Sprawdzone:
- 41 testów (w tym usługa nieaktywna w żadnym dniu i ten sam kurs w dwóch dobach).
- `uv run build-events`, hash manifestu dd5a166abd0e2966, dni 4–15.10: przepiętych 5018 zdarzeń w 465 kursach (mediana opóźnienia 70 s, 5–95%: −234..418 s); `delay_class`: ok 1 522 975, outlier 11 086, wrong_service_day 36. Noc 9→10 godz. 0–1: 838 i 469 zdarzeń (wcześniej bez daty).

Otwarte / dalej:
- `week_analysis` nadal ma własny próg 1800 s; przejść na `arr_good` przy najbliższej zmianie raportu.
- Ranking linii pod tor N, propozycja split dni.

---

## 2026-10-16 — łańcuchy kursów pojazdów (M1 C)

**Kto:** Kacper Lipiec
**Commity:** fabf091

Zrobione:
- `src/krakbus/observed/chains.py`: jeden wiersz na kurs pojazdu w dobie (`chain_idx`), z następnym kursem pojazdu, zapasem rozkładowym na pętli, opóźnieniem na końcu kursu i na odjeździe następnego, flagami `follows_block`, `cross_route`, `carried`. Zapis `data/processed/chains/D.parquet`, odczyt `store.load_chains`.
- Łańcuchy liczone w `build-events` razem ze zdarzeniami, na tym samym manifeście; odcisk obejmuje teraz też sekcję `chains` configu. `PIPELINE_VERSION` = 2.
- Plan bloków (`blk_idx`, `block_next_trip`, `start_s`, `end_s`) w `ScheduleIndex.trip_plan`.
- `events-quality` raportuje łańcuchy: zgodność z blokiem, `cross_route` per linia, reset X i przenoszenie OLS.

Decyzje:
- Łańcuch obserwowany (kolejność kursów pojazdu wg czasu), nie wzięty z `block_id` — pojazdy bywają podmieniane i zmieniają linię; plan bloku zostaje do porównania (`follows_block`). Odrzucone: łańcuch z bloku z dołączonym pojazdem (gubi podmiany i przejścia międzyliniowe, które są potrzebne do warunku brzegowego, decyzja 4).
- Odjazd z pierwszego przystanku = **ostatni** epizod postoju z `dep_ok` (właściwy odjazd po czekaniu na pętli); przyjazd na koniec = pierwszy epizod na ostatnim przystanku z `arr_ok`.
- `carried` = `arr_end_delay_s > layover_sched_s − l_min_s`, `l_min_s` = 60 s (najlepsze dopasowanie z sekcji 6 `week_analysis`); brak wartości, gdy brak opóźnienia albo następnego kursu.
- Opóźnienia w łańcuchach surowe; filtr outlierów zostaje dla M1 B (jeden spójny filtr).
- Dzień bez zdarzeń nie jest przeliczany w kółko (brak plików liczy się jako brak tylko, gdy manifest ma zdarzenia).

Sprawdzone:
- 8 dni roboczych (5–9.10, 12–14.10): ten sam pojazd na kolejnym kursie bloku 0,990 (sekcja 6: 0,991), reset X 0,84 (0,84), przenoszenie OLS 0,138 (0,13; różnica z wyboru epizodu na pierwszym przystanku). `follows_block` 0,982.
- `cross_route` 5,3% przejść; większość linii 0–2,5%, 151: 17,5%.
- 36 testów, ruff czysto; ponowne `build-events` nic nie przelicza, hash manifestu `87b84a4e18f73610`.

Otwarte / dalej:
- M1 B: flaga outlierów i klasa `wrong_service_day`.
- Krzywa pochłaniania liczona z `chains/` (dziś w sekcji 6 `week_analysis`).
- Ranking linii z udziałem `cross_route` pod tor N (`route_ranking.csv`).

## 2026-10-16 — przetwarzanie przyrostowe i pakiet `krakbus` (M1 A2, M2 A)

**Kto:** Kacper Lipiec
**Commity:** 4ff3f12, fe08379

Zrobione:
- Pakiet `src/krakbus/` (uv_build), komendy `uv run build-events` i `uv run events-quality`; `gtfs_versions.py` przeniesiony do `src/krakbus/ingest/`, stary `sandbox/.../build_events.py` usunięty.
- Zdarzenia zapisywane per data obsługi: `data/processed/events/YYYY-MM-DD.parquet`; rejestr `days.csv` (status, rola, pokrycie, `calendar_stamp`); `manifest.json` z odciskiem wejść każdego dnia.
- `configs/config.yaml` (ścieżki, progi), `configs/special_days.yaml` (25.10, 31.10–2.11, 10–12.11, 24–26.12).
- `week_analysis.py` czyta przez `krakbus.observed.store.load_events` (domyślnie dni `complete`).

Decyzje:
- Dzień D liczony z partycji UTC D-1..D+1, zostają zdarzenia z `service_date == D` — partycje loggera są w UTC, a doba lokalna i kursy nocne wychodzą poza `date=D`.
- Odcisk dnia = nazwy i rozmiary plików `part-*` z okna + właściciel kalendarza dla D-1..D+1 + progi `events` + `PIPELINE_VERSION`. Rozmiar zamiast mtime, bo pobranie z Google Drive zmienia mtime.
- Status liczony od nowa przy każdym uruchomieniu ze statystyk w manifeście, więc zmiana progów `days` albo listy dni specjalnych nie wymaga przeliczania zdarzeń.
- `provisional` = brak danych do 04:00 doby D+1; `gap` = przerwa > 30 min w godzinach 5–23 albo < 500 zdarzeń. Kolejność: provisional, special, gap, complete.
- Pliki zdarzeń płaskie (`events/D.parquet`) zamiast katalogów `service_date=D/` — jeden plik na dzień, prostsze nadpisanie atomowe.
- Pliki `part-*` są niezmienne (logger zapisuje każdy raz, w całości); niepełny bywa tylko ostatni dzień wgrania. Poprawione w M0.

Sprawdzone:
- Zgodność z pełnym przeliczeniem starym skryptem: 1 531 496 zdarzeń identycznych; 14 brakujących to artefakty z datą 16.10 (opóźnienia −4,5 do −9 h, partycji 16.10 jeszcze nie ma); różnice `prev_ts`/`arr_unc` tylko tam, gdzie poprzedni raport pojazdu jest sprzed > 25 h (flagi `arr_ok`/`dep_ok` bez zmian).
- Pełne przeliczenie 12 dni ~2,5 min; ponowne bez nowych danych < 1 s; hash manifestu `d20e19462d2b1b5d` identyczny po `--full`.
- 31 testów (`uv run pytest`), ruff czysto.
- `days.csv`: 10 dni `complete` (5–14.10), 4.10 `gap`, 15.10 `provisional`. `week_analysis`: kluczowe liczby zgodne z poprzednim raportem do trzeciej cyfry (8 pełnych dni roboczych zamiast 9, bo 15.10 czeka na noc).

Otwarte / dalej:
- `vehicle_chains` per dzień z flagą `cross_route` (M1 C), na tym samym manifeście.
- Okres przedświąteczny w `special_days.yaml` — ustalić z danych.

## 2026-10-16 — dopływ danych i rutyna wgrywania (decyzja 8)

**Kto:** Kacper Lipiec
**Commity:** 8d9c1c3, bf10fa1

Decyzje:
- Dane z PC loggera trafiają co jakiś czas na wspólny Google Drive; każdy pobiera i scala je u siebie ręcznie (`rsync --size-only` / `robocopy /XO`), bez usuwania. Procedura w M0.
- Do analiz tylko dni `complete`; podział dni kalibracja/walidacja zamrażany w M3 w `configs/days_split.yaml`, dni przychodzące później automatycznie `valid` (walidacja out-of-time).
- Każdy wynik kalibracji/walidacji zapisuje migawkę danych (lista dni + hash manifestu).

## 2026-10-16 — przegląd planu (PLAN_REALIZACJI, milestones)

**Kto:** Kacper Lipiec
**Commity:** 94d9f2c

Decyzje (szczegóły: decyzje 1–7 w `PLAN_REALIZACJI.md`):
- Walidacja leave-line-out zamrożona w M3 przed kalibracją per linia.
- `u` kalibrowane wspólnie na korytarzu; łańcuchy międzyliniowe dostają obserwowany warunek brzegowy; struktura przestrzenna `u` do decyzji w M2.
- Szybka ścieżka numpy z testem równoważności z SimPy (tylko γ = 0); hierarchia parametrów global → grupa → linia; kalendarz dni specjalnych.

## 2026-10-16 — dopasowanie wersji GTFS i data obsługi (M1 A)

**Kto:** Kacper Lipiec
**Commity:** 3fa2661

Zrobione:
- `gtfs_versions.py`: łączenie wszystkich wersji rozkładu, kalendarz efektywny, przypisanie daty obsługi; 13 testów.

Decyzje:
- Rozkład kursu z najnowszej wersji zawierającej `trip_id`; kalendarz dnia D z najnowszej wersji z wpisem na D (feed kroczący, kalendarz tylko w `calendar_dates.txt`).
- Data obsługi: kandydaci wczoraj/dziś/jutro z aktywną usługą, minimum |opóźnienia|, remis = dziś; brak kandydata = brak daty (nie cichy „wczoraj”).
- Czasy GTFS od „lokalne południe − 12 h” — poprawne przy zmianie czasu 25.10.

Sprawdzone:
- 100% zdarzeń dopasowanych do rozkładu (wcześniej ~30%), 99,8% z datą obsługi; rzekomo pusty 9.10 był błędem pipeline'u. Fakty stylizowane potwierdzone na 9 dniach roboczych (stan w `PLAN_REALIZACJI.md`).
