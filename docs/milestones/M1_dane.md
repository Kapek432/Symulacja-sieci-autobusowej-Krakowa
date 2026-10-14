# M1 — Dane obserwowane wiarygodne

**Najpóźniej:** 24.10.2026  
**Tor:** D  
**Blokuje:** sensowną kalibrację (M3) i uczciwe fakty stylizowane pod model

## Cel

Opóźnienia i łańcuchy kursów liczone z **właściwą wersją rozkładu na dany dzień**, z flagami jakości i powtórzonymi faktami stylizowanymi na kilku pełnych dniach roboczych.

## Wejście

- `data/raw_A/vehicle_positions/`, `trip_updates/`, `static/GTFS_KRK_A_*.zip`
- `sandbox/gtfs-experiments/build_events.py`, `week_analysis.py`
- Raport: `data/processed/week_report/report.txt`

## Wyjście

- `data/processed/observed_events.parquet` (przeliczony, ze wskazaniem wersji GTFS / `gtfs_stamp` per wiersz lub per dzień)
- `data/processed/vehicle_chains.parquet` (lub równoważna tabela)
- Odświeżony `week_report/` z wykresami
- Krótka notatka: które dni → kalibracja, które → walidacja (propozycja; twardy split w M3)

## Kolejność (sugerowana)

Zróbcie **najpierw A**, potem B–D równolegle kto może.

### A. Match wersji GTFS do dnia (P0)

Problem: `build_events.py` bierze `sorted(…GTFS_KRK_A_*.zip)[-1]` — jeden rozkład na wszystkie dni. Raport pokazał `z_rozkladem = 0` dla 5–8.10.

- [ ] Spisać dostępne ZIP-y i ich timestampy (`GTFS_KRK_A_YYYYMMDD_HHMMSS.zip`)
- [ ] Reguła: dla dnia `D` użyj najnowszego ZIP z `stamp.date <= D` (albo jawna mapa dzień → plik w YAML)
- [ ] Przerobić budowę zdarzeń tak, by każdy `service_date` merge’ował się ze swoim `stop_times` / `trips`
- [ ] Zapis w zdarzeniach: kolumna `gtfs_stamp` (lub osobna tabela dni)
- [ ] Przeliczyć `observed_events` od zera
- [ ] Smoke: dla dnia roboczego sprzed zmiany rozkładu `z_rozkladem` / udział dopasowanych kursów sensowny (nie ~0); sekcja 2 `week_analysis` nie pokazuje samych NaN dla 5–8.10
- [ ] Uwzględnić zmianę czasu 25/26.10, jeśli wpadnie w zbieranie (jawna obsługa lub wykluczenie doby)

### B. Jakość zdarzeń

- [ ] Flaga `outlier = |arr_delay_s| > 1800` (albo równoważna) — jeden spójny filtr zamiast rozproszonych
- [ ] Kandydaci daty obsługi: wczoraj / dziś / jutro (pojazdy na pętli z kursem „na jutro”)
- [ ] Opcjonalnie (jak będzie czas): `move_ts` = pierwszy raport >15 m od postoju; porównać z `dep_ts`
- [ ] Zachować `arr_ok` / `dep_ok` (niepewność ≤ 30 s); udokumentować w README skryptów

### C. Łańcuchy kursów (`vehicle_chains`)

- [ ] Z `trips.block_id` + zdarzeń: dla (vehicle_id lub block_id, service_date) uporządkowana lista kursów
- [ ] Kolumny minimum: kolejność, route_id, direction, trip_id, zaplanowany zapas pętli `L`, opóźnienie na końcu kursu, opóźnienie odjazdu następnego, czy przeniesienie (opóźnienie > zapas − ℓ_min)
- [ ] Krzywa pochłaniania: udział / wielkość resetu vs zapas (jak sekcja 6 raportu, ale na poprawionych opóźnieniach)
- [ ] Sprawdzić, że `block_id` nadal ≈ zgodny z pojazdem (~99% w starym raporcie)

### D. Fakty stylizowane + tooling raportu

- [ ] Dodać `matplotlib` (i brakujące deps) do `pyproject.toml` / `uv`
- [ ] Naprawić crash KS w `week_analysis` (puste dni w `WORK` → `ks_stat`)
- [ ] Przegonić raport na poprawionych zdarzeniach dla pełnych dni roboczych
- [ ] Potwierdzić na ≥3 dniach: dryf wzdłuż trasy, wzrost rozrzutu, slope σ_e, krzywa pętli, korelacja między liniami
- [ ] Bootstrap po kursach dla CI przy kluczowych statystykach (przynajmniej dryf / reset)
- [ ] Notebook lub skrypt: Marey rzeczywistości dla 179 (jeden dzień)
- [ ] Propozycja split dni: np. pierwsze pełne robocze → kalibracja, późniejsze → walidacja (zaktualizować gdy przybędą dni)

### E. Jak będzie czas (nie blokuje M1 Done)

- [ ] Interpolacja luk na `shapes.txt` tylko dla brakujących przystanków, z flagą gorszej jakości
- [ ] Pokrycie statusem 1 vs wielkość odstępu

## Pliki, których to dotyczy

| Plik | Rola |
|------|------|
| `sandbox/gtfs-experiments/build_events.py` | główna naprawa GTFS per dzień |
| `sandbox/gtfs-experiments/week_analysis.py` | fakty + KS + wykresy |
| `sandbox/gtfs-experiments/README_skrypty.md` | zaktualizować kontrakt wyjścia |
| `data/processed/observed_events.parquet` | artefakt |
| `data/processed/vehicle_chains.parquet` | artefakt (nowy) |
| `pyproject.toml` | matplotlib i deps |

## Definition of Done

- Zdarzenia z dni 5–8.10 (i kolejnych) mają sensowny match rozkładu.
- Istnieje tabela łańcuchów z zapasem i przenoszeniem.
- Raport tygodnia odpala się bez crashy i zapisuje wykresy.
- Zespół ma listę pełnych dni roboczych i roboczą propozycję split kalibracja/walidacja.
- Nikt nie zaczyna M3 na starym parquet bez `gtfs_stamp` / per-day GTFS.

## Pułapki

- Sam weekend z „dobrym” `z_rozkladem` nie ratuje dni roboczych sprzed zmiany ZIP.
- Pooling dni przed naprawą GTFS zafałszuje dryf i pętlę.
- 704 ma krótkie zapasy — nie uśredniać wniosków o przenoszeniu tylko po 179.
