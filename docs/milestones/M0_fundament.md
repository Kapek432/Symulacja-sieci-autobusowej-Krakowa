# M0 — Fundament (stan + stałe)

**Status:** w dużej mierze Done; obowiązki stałe trwają do M7.  
**Najpóźniej:** nie dotyczy (ciągłe).

## Cel

Utrzymać zbieranie danych i mieć wspólny punkt odniesienia: temat, skrypty, pierwszy raport.

## Już jest (nie robić od zera)

- [x] `TEMAT.md` — opis dla prowadzącego (nie edytować pod plan realizacji)
- [x] Logger `sandbox/gtfs-experiments/logger_autobusy.py` na osobnym PC (od ~4.10)
- [x] `build_events.py` → `data/processed/observed_events.parquet`
- [x] `week_analysis.py` → `data/processed/week_report/`
- [x] Pilot 179, korytarz (169, 174, 173, 144, 124, …) z raportu
- [x] Geoportal LoD1/LoD2 w `data/geoportal/` (pod późniejsze viz / Unity)
- [x] `docs/PLAN_REALIZACJI.md`
- [x] `sandbox/gtfs-experiments/gtfs_versions.py` — łączenie wersji GTFS i data obsługi (testy: `uv run pytest`)

## Stałe obowiązki (cały projekt)

### Rutyna po każdym wgraniu danych z maszyny loggera

Dane trafiają z komputera loggera na Google Drive, a każdy pobiera je stamtąd ręcznie. Dane z loggera tylko przybywają (nowe pliki `part-*` co ~10 min, nowe wersje GTFS w `static/`), więc przy scalaniu niczego nie usuwamy; nadpisujemy tylko pliki, które w nowym pobraniu są pełniejsze. Zasady przetwarzania: decyzja 8 w [`PLAN_REALIZACJI.md`](../PLAN_REALIZACJI.md).

1. [ ] Na komputerze z loggerem: wrzucić aktualny `C:\gtfs\data\raw_A` (vehicle_positions, trip_updates, static) na wspólny folder Google Drive. Robi to osoba z dostępem do tego komputera, od czasu do czasu
2. [ ] Każdy u siebie, ręcznie: pobrać folder `raw_A` z Google Drive przez przeglądarkę. Drive pakuje folder do jednego lub kilku plików `drive-download-*.zip` (powyżej ~2 GB dzieli na części) — pobrać **wszystkie części**
3. [ ] Rozpakować wszystkie części do jednego folderu tymczasowego (np. `~/Downloads/raw_A_import/`) i sprawdzić, że w środku jest `raw_A/` z podfolderami `vehicle_positions/`, `trip_updates/`, `static/`
4. [ ] Scalić z `data/raw_A` w projekcie. Pliki tylko przybywają, ale ostatni plik `part-*` z poprzedniego pobrania mógł być niepełny (logger go dopisywał) — dlatego kopiujemy też pliki o tej samej nazwie i innym rozmiarze, a niczego nie usuwamy:

   macOS / Linux:

   ```
   rsync -av --size-only ~/Downloads/raw_A_import/raw_A/ data/raw_A/
   ```

   Windows (PowerShell):

   ```
   robocopy $HOME\Downloads\raw_A_import\raw_A data\raw_A /E /XO
   ```

   Zawsze importować **najnowsze** pobranie; wgranie starszej paczki po nowszej mogłoby nadpisać pełny plik `part-*` jego niepełną wersją
5. [ ] Usunąć folder tymczasowy i pobrane ZIP-y (zajmują tyle samo co dane)
6. [ ] Kopia zapasowa: Google Drive pełni rolę kopii poza dyskiem loggera; dodatkowo raz w tygodniu jedna osoba trzyma kopię `data/raw_A` na **innym dysku** (ta sama komenda scalania, inny cel)
7. [ ] Przeliczyć przyrostowo: `uv run sandbox/gtfs-experiments/build_events.py` (tylko zmienione dni; `--full` tylko po zmianie logiki). Do czasu wdrożenia M1 A2 skrypt liczy wszystko od zera
8. [ ] Przejrzeć wydruk `build_events`: które dni przeliczono, które zmieniły status (`provisional` → `complete`), tabela „zdarzenia dzień po dniu” (`wg_daty_obslugi` i `wg_daty_lokalnej` w tym samym rzędzie wielkości, `bez_daty_obslugi` bliskie zera)
9. [ ] Raport: `uv run sandbox/gtfs-experiments/week_analysis.py 179` (domyślnie tylko dni `complete`)
10. [ ] Jeśli dziura w dzień roboczy: status `gap` w `days.csv` ustawia się sam; dopisać przyczynę, jeśli znana (restart, awaria sieci)
11. [ ] Nie commitować surowego `raw_A` ani `data/processed/` do publicznego repo (`.gitignore`)

Każdy z zespołu robi kroki 2–9 u siebie niezależnie. Ponieważ przetwarzanie jest deterministyczne, te same pobrane dane dają u wszystkich te same `days.csv` i zdarzenia; porównując wyniki między osobami, porównujcie hash `manifest.json` (ten sam hash = te same wejścia).

Logger:

- [ ] Potwierdzić, że zadanie na Windowsie nadal działa (auto-restart po awarii)
- [ ] Unikać restartów / update’ów systemu w godzinach ~6:00–22:00

## Wejście / wyjście

| Wejście | Wyjście |
|---------|---------|
| Feed ZTP na PC loggera | Przyrost `data/raw_A/…/date=YYYY-MM-DD/` |
| Google Drive (ręczne pobranie, scalenie) | Lokalna kopia `data/raw_A` do `build_events` / analiz |
| `build_events` przyrostowo | `data/processed/events/service_date=D/`, `days.csv`, `manifest.json` |

## Definition of Done (część ciągła)

- Nowe dni pojawiają się regularnie na maszynie roboczej.
- Jest przynajmniej jedna aktualna kopia zapasowa poza dyskiem loggera.
- Zespół wie, które dni są dziurawe (`days.csv`, status `gap`).
- Każde wgranie kończy się przeliczeniem przyrostowym i aktualnym `days.csv`.

## Notatki

- „Pusty 9.10” w starym raporcie był błędem pipeline'u, nie dziurą w danych: surowe dane z 9.10 są kompletne (logger 24 h, ~44 MB pozycji jak w inne dni robocze). Stary `build_events.py` przy kursach spoza najnowszego ZIP-a przypisywał zdarzeniom datę „wczoraj”, więc dni 5–9.10 były przesunięte o jeden (4.10 = faktycznie 5.10 itd.). Naprawione w M1 A; stare liczby dzień po dniu z raportu sprzed 16.10 są nieaktualne.
- Dziury liczymy po godzinach pracy loggera (sekcja 1 `week_analysis`), nie po liczbie zdarzeń na datę obsługi — ta druga zależy od poprawności dopasowania rozkładu.
- Kilka wersji GTFS w `static/` — obsługa per dzień w `gtfs_versions.py` (M1).
