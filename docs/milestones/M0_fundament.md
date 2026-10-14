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

## Stałe obowiązki (cały projekt)

Kolejność w praktyce po każdym „sejwie” z maszyny loggera:

1. [ ] Skopiować `data/raw_A` (vehicle_positions, trip_updates, static) na maszynę roboczą
2. [ ] Kopia zapasowa tego samego zestawu na **inny dysk**
3. [ ] Sprawdzić dziury: odstępy `fetched_at` > ~120 s w godzinach ruchu (albo sekcja 1 `week_analysis`)
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

- 9.10 w raporcie prawie pusty — nie używać jako dnia roboczego.
- Kilka wersji GTFS w `static/` — obsługa per dzień to zadanie **M1**, nie M0.
