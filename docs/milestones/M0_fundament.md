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

Dane z loggera tylko przybywają (nowe pliki `part-*` co ~10 min, nowe wersje GTFS w `static/`), więc kopiujemy wyłącznie nowe pliki i niczego nie nadpisujemy. Zasady przetwarzania: decyzja 8 w [`PLAN_REALIZACJI.md`](../PLAN_REALIZACJI.md).

1. [ ] Skopiować nowe pliki `data/raw_A` (vehicle_positions, trip_updates, static) z `C:\gtfs\data\raw_A` na maszynę roboczą, bez usuwania istniejących:

   ```
   rsync -av --ignore-existing <źródło>/raw_A/ data/raw_A/
   ```

   `<źródło>` zależy od sposobu przenoszenia (dysk sieciowy, pendrive, SSH) — wpisać tu konkretną ścieżkę, gdy będzie ustalona. Uwaga: ostatni, jeszcze dopisywany plik `part-*` może być niepełny; `--ignore-existing` go potem nie zaktualizuje, więc przy kolejnym wgraniu kopiować bez tej flagi albo z `--size-only`.
2. [ ] Kopia zapasowa tego samego zestawu na **inny dysk** (ta sama komenda, inny cel)
3. [ ] Przeliczyć przyrostowo: `uv run sandbox/gtfs-experiments/build_events.py` (tylko zmienione dni; `--full` tylko po zmianie logiki). Do czasu wdrożenia M1 A2 skrypt liczy wszystko od zera
4. [ ] Przejrzeć wydruk `build_events`: które dni przeliczono, które zmieniły status (`provisional` → `complete`), tabela „zdarzenia dzień po dniu” (`wg_daty_obslugi` i `wg_daty_lokalnej` w tym samym rzędzie wielkości, `bez_daty_obslugi` bliskie zera)
5. [ ] Raport: `uv run sandbox/gtfs-experiments/week_analysis.py 179` (domyślnie tylko dni `complete`)
6. [ ] Jeśli dziura w dzień roboczy: status `gap` w `days.csv` ustawia się sam; dopisać przyczynę, jeśli znana (restart, awaria sieci)
7. [ ] Nie commitować surowego `raw_A` ani `data/processed/` do publicznego repo (`.gitignore`)

Logger:

- [ ] Potwierdzić, że zadanie na Windowsie nadal działa (auto-restart po awarii)
- [ ] Unikać restartów / update’ów systemu w godzinach ~6:00–22:00

## Wejście / wyjście

| Wejście | Wyjście |
|---------|---------|
| Feed ZTP na PC loggera | Przyrost `data/raw_A/…/date=YYYY-MM-DD/` |
| Sync na laptopie | Lokalna kopia do `build_events` / analiz |
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
