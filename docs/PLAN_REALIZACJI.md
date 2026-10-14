# Plan realizacji: propagacja opóźnień w sieci autobusowej Krakowa

Aktualizacja: 14.10.2026.

Dokument roboczy zespołu (3 osoby). Opis tematu dla prowadzącego jest w `TEMAT.md` i tu go nie dublujemy ani nie redagujemy.

**Cel oddania:** pełny zakres z `TEMAT.md` oraz ścieżka „na 5” (Unity + szersza sieć) **najpóźniej 31.12.2026**.

**Organizacja pracy:** bez sztywnego podziału ról i bez bramek decyzyjnych. Kto ma czas, bierze następne odblokowane zadanie. Statusy: **Done / In progress / Blocked** (Blocked zawsze z powodem, np. „czeka na match GTFS”).

**Oś czasu:** kamienie milowe z datą „najpóźniej do”. Wcześniej = lepiej. Między milestonami robicie z backlogu, gdy będzie czas.

**Dane:** logger GTFS-RT działa **ciągle na osobnym komputerze**. Na maszynie roboczej: regularny sync `data/raw_A` + kopia zapasowa na inny dysk. Surowych danych nie commitować publicznie.

**Unity:** tor równoległy od M2; praca ze sceną i smoke-testami przez **Unity MCP**. Symulacja zostaje w Pythonie; Unity odtwarza wyeksportowane wyniki.

Starszy, szczegółowy szkic sprintów (historyczny) leży w `local/SPRINTY - Propagacja opóźnień w sieci autobusowej.md`. Ten plik go zastępuje jako aktualny plan **przeglądowy**.

**Szczegóły operacyjne (kolejność zadań, DoD, pułapki, pliki):** katalog [`milestones/`](milestones/README.md).

---

## Kamienie milowe

| ID | Kamień | Najpóźniej | Done oznacza | Szczegóły |
|----|--------|------------|--------------|-----------|
| **M0** | Fundament | *zrobione / trwa* | Logger, `TEMAT.md`, pierwsze zdarzenia, raport tygodnia, pilot 179 i korytarz | [M0](milestones/M0_fundament.md) |
| **M1** | Dane obserwowane wiarygodne | **24.10.2026** | Wersja GTFS dopasowana do dnia, `observed_events` + łańcuchy, fakty stylizowane na pełnych dniach roboczych | [M1](milestones/M1_dane.md) |
| **M2** | DES pilota z łańcuchami | **7.11.2026** | SimPy: pojazd → łańcuch, pętla, wyjście jak dane obserwowane, testy weryfikacyjne, Marey z symulacji | [M2](milestones/M2_des.md) |
| **U** | Unity MCP (tor równoległy) | domknięcie **20.12** | Replay + obs‖sim; praca przez Unity MCP | [U](milestones/U_unity_mcp.md) |
| **M3** | Kalibracja | **21.11.2026** | Parametry (ABC/Optuna), wrażliwość SALib, porównanie γ=0 vs γ>0, niepewność na dniach kalibracyjnych | [M3](milestones/M3_kalibracja.md) |
| **M4** | Walidacja + korytarz | **5.12.2026** | Dni i linie poza próbą, ablacje, modele odniesienia, rozszerzenie korytarza | [M4](milestones/M4_walidacja.md) |
| **M5** | Scenariusze | **12.12.2026** | 3 oparte na danych + 2 warunkowe, replikacje, CI, odpowiedzi na pytania badawcze | [M5](milestones/M5_scenariusze.md) |
| **M6** | „Na 5”: Unity MCP + szersza sieć | **20.12.2026** | Replay (rzeczywistość ‖ symulacja), produkt Unity; parametry zbiorcze / szersza sieć; pydeck jako baza 3D | [M6](milestones/M6_na5.md) |
| **M7** | Raport + odtwarzalność | **31.12.2026** | Raport końcowy, README, odtworzenie na czystej maszynie, gotowość do prezentacji | [M7](milestones/M7_raport.md) |

Unity MCP **nie czeka na M6**: od M2 idzie tor równoległy; M6 zamyka produkt wizualny „na 5”.

---

## Trzy tory równoległe

```
TOR D (Dane)          TOR M (Model)              TOR U (Unity MCP + viz)
─────────────────────────────────────────────────────────────────────────
logger + sync ─────────────────────────┐
match GTFS / events / łańcuchy (M1) ───┼──► DES pilot (M2)
fakty stylizowane ─────────────────────┤         │
                                       │    kalibracja (M3)
                                       │         │
                                       ├──► walidacja + korytarz (M4)
                                       │         │
                                       │    scenariusze (M5)
                                       │         │
eksport parquet/JSON ◄── wyniki sym ───┴──► Unity MCP: scena, replay (‖ M2→M6)
pydeck / Marey / heatmap ─────────────────► raport + README (M7)
szersza sieć (param. zbiorcze) ───────────► M6 „na 5”
```

1. **Tor D** nigdy nie umiera — sync z komputera loggera, kontrola dziur, nowe dni do analiz.
2. **Tor M** nie kalibruje na brudnych opóźnieniach — najpierw Done na dopasowaniu wersji rozkładu do dnia.
3. **Tor U** startuje wcześnie (syntetyka / jeden dzień pilota); dociera wynikami z M2+; nie blokuje modelu, ale nie znika z planu „na 5”.

Proponowany układ repo (do wprowadzenia przy M2):

```
configs/                 # YAML: parametry, scenariusze
data/raw|interim|processed/
src/
  ingest/                # logger, parser GTFS / GTFS-RT
  observed/              # zdarzenia, łańcuchy
  sim/                   # DES SimPy
  calib/                 # statystyki, Optuna/ABC, SALib
  scenarios/
  viz/                   # mapa, Marey, pydeck, eksport do Unity
notebooks/
tests/
docs/
```

Obecne skrypty w `sandbox/gtfs-experiments/` przenosicie / owijacie stopniowo; nie trzeba przepisywać wszystkiego Day 1.

---

## Backlog (skrót)

Pełne checklisty, kolejność, DoD i pułapki: **[`milestones/`](milestones/README.md)**.

Tu tylko przypomnienie P0 na teraz:

- [ ] **M1 / P0:** match wersji GTFS do dnia w `build_events` + przeliczenie zdarzeń
- [ ] Stałe: logger + sync + backup `raw_A`
- [ ] Po M1: szkielet DES (M2) i kontrakt eksportu Unity MCP (tor U)

---

## Ryzyka (bez bramek — tylko alarm i naprawa)

| Ryzyko | Objaw | Reakcja |
|--------|--------|---------|
| Zły match wersji GTFS | `z_rozkladem ≈ 0` na wczesnych dniach, absurdy opóźnień | Priorytet M1; nie kalibrować na brudnych danych |
| Logger / sync | dziury, brak dni | sync + backup; dni dziurawe wyłączać z analiz |
| Słabe przenoszenie łańcuchów / γ≈0 w danych | „mało dramatycznej emergencji” | Uczciwie w raporcie; wartość z ablacji, zakłóceń wspólnych, scenariuszy pętli |
| Unity zjada kalendarz | scena bez wyników modelu | Model ma pierwszeństwo przy konflikcie czasu; tor U kontynuuje na eksporcie przez Unity MCP |
| Święta przed M6/M7 | raport niedowieziony | Draft raportu i kontrakt eksportu wcześniej; M6 trzymać do 20.12 |
| „Cała sieć” bez końca | nie zamyka się M6 | Parametry zbiorcze + walidacja zagregowana — nie pełny digital twin Krakowa |

---

## Stan na 14.10.2026 (skrót)

- Logger od 4.10; pełne dni robocze w raporcie: 5–8.10 i 12.10 (9.10 prawie pusty).
- Pipeline `build_events` → `week_analysis` istnieje; raport w `data/processed/week_report/`.
- Wstępne fakty: dryf i wzrost rozrzutu wzdłuż trasy; `block_id` zgodny z pojazdem; silny reset na pętli; słabe średnie przenoszenie; γ bliskie zera; korytarz wokół 179 zgodny z tematem.
- Najpilniejszy dług techniczny przed kalibracją: **wersja rozkładu per dzień**.

Szczegóły liczb — w `data/processed/week_report/report.txt`, nie w tym planie.
