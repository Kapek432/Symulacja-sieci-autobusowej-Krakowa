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

Kolejność w praktyce po każdym „sejwie” z maszyny loggera:

1. [ ] Skopiować `data/raw_A` (vehicle_positions, trip_updates, static) na maszynę roboczą
2. [ ] Kopia zapasowa tego samego zestawu na **inny dysk**
3. [ ] Sprawdzić dziury: odstępy `fetched_at` > ~120 s w godzinach ruchu (albo sekcja 1 `week_analysis`); w wydruku `build_events` tabela „zdarzenia dzień po dniu” — kolumny `wg_daty_obslugi` i `wg_daty_lokalnej` powinny mieć ten sam rząd wielkości, a `bez_daty_obslugi` bliskie zera
4. [ ] Jeśli dziura w dzień roboczy: zanotować datę/godziny (przydaje się przy wyłączaniu dni z kalibracji)
5. [ ] Nie commitować surowego `raw_A` do publicznego repo (`.gitignore`)

Logger:

- [ ] Potwierdzić, że zadanie na Windowsie nadal działa (auto-restart po awarii)
- [ ] Unikać restartów / update’ów systemu w godzinach ~6:00–22:00

## Wejście / wyjście

| Wejście | Wyjście |
|---------|---------|
| Feed ZTP na PC loggera | Przyrost `data/raw_A/…/date=YYYY-MM-DD/` |
| Sync na laptopie | Lokalna kopia do `build_events` / analiz |

## Definition of Done (część ciągła)

- Nowe dni pojawiają się regularnie na maszynie roboczej.
- Jest przynajmniej jedna aktualna kopia zapasowa poza dyskiem loggera.
- Zespół wie, które dni są dziurawe.

## Notatki

- „Pusty 9.10” w starym raporcie był błędem pipeline'u, nie dziurą w danych: surowe dane z 9.10 są kompletne (logger 24 h, ~44 MB pozycji jak w inne dni robocze). Stary `build_events.py` przy kursach spoza najnowszego ZIP-a przypisywał zdarzeniom datę „wczoraj”, więc dni 5–9.10 były przesunięte o jeden (4.10 = faktycznie 5.10 itd.). Naprawione w M1 A; stare liczby dzień po dniu z raportu sprzed 16.10 są nieaktualne.
- Dziury liczymy po godzinach pracy loggera (sekcja 1 `week_analysis`), nie po liczbie zdarzeń na datę obsługi — ta druga zależy od poprawności dopasowania rozkładu.
- Kilka wersji GTFS w `static/` — obsługa per dzień w `gtfs_versions.py` (M1).
