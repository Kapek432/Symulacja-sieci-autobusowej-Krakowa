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
