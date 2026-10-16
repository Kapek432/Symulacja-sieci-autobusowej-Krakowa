# M2: DES pilota i grafu miasta, projekt

Data: 2026-10-16. Kamień: [M2](../../milestones/M2_des.md). Zatwierdzone w rozmowie 16.10 (wariant „szum losowany z góry, dwa silniki na tych samych tablicach”).

## Cel i zakres

Symulacja zdarzeń dyskretnych doby obsługi dla dowolnego zakresu linii (`pilot`, `corridor`, `city`), z modelem propagacji opóźnienia z `TEMAT.md`, regułą pętli i przełączalnym sprzężeniem od odstępu γ. Obok silnika SimPy szybka ścieżka w numpy dla γ = 0, zgodna z SimPy na tych samych liczbach losowych. W M2 nie kalibrujemy: parametry są robocze, liczy się poprawność mechaniki.

Realizacja w trzech etapach:

1. Sieć dnia, szum, silnik SimPy, warunek brzegowy, CLI `simulate`, testy weryfikacyjne (M2 A, B, C, D).
2. Szybka ścieżka `sim.fast` i test równoważności, pomiar czasu doby (M2 C2).
3. Marey z symulacji z nakładką obserwacji, eksport dla Unity z kontraktem (M2 E, F).

## Decyzje

- **Struktura przestrzenna `u`: `independent`.** `u` jest wspólne dla wszystkich linii na tym samym skierowanym odcinku, niezależne między odcinkami, w czasie AR(1) między kolejnymi oknami. Dane z M1 (sekcja 13 `week_analysis`, 8 dni roboczych): korelacja residuów przyrostów między liniami na tym samym odcinku 0,29, na sąsiednim 0,04, od trzech odcinków dalej 0,002 do 0,008, czyli tyle co losowe pary w tym samym oknie (0,005). Odrzucone `neighbors` (korelacja z sąsiednim odcinkiem): przy 0,04 dodatkowy parametr nie byłby identyfikowalny w kalibracji.
- **Łańcuchy z planu (`block_id`).** Pojazd symulacji realizuje blok rozkładowy (`plan_blocks`); w danych 99% przejść między kursami bloku robi ten sam pojazd. Obserwowane łańcuchy z `chains/` służą tylko jako warunek brzegowy.
- **Szum losowany z góry.** `draw_noise` losuje wszystkie składniki dla przebiegu, oba silniki je tylko czytają. Test równoważności sprawdza wtedy wyłącznie mechanikę, a scenariusze (np. S2 „zakłócenie na korytarzu”) modyfikują tablicę `u`. Odrzucone losowanie w locie ze strumieniem per kurs: wolniejsze i łatwo rozjechać kolejność losowań między silnikami.
- **Okno `u` wg rozkładowego czasu odjazdu z odcinka**, nie faktycznego. Pozwala liczyć szybką ścieżkę sumą skumulowaną po odcinkach. Przy oknie 15 min i medianie opóźnienia ok. 2 min różnica dotyczy tylko kursów blisko granicy okna.
- **Postój pośredni rozkładowy.** Opóźnienie odjazdu z przystanku = opóźnienie przyjazdu; postój jest częścią przyrostu na odcinku, tak jak w przyrostach liczonych z danych (sekcja 10 `week_analysis`).

## Model

Dla kursu `i` i odcinka `s → s+1` (czasy w sekundach doby GTFS danego dnia obsługi):

```
Δ[i, s+1] = Δ[i, s] + a_p · t_s / 60 + e_d + u[s, w(i, s)] + γ · (h[i, s] − h_rozk[i, s]) + η[i, s]
```

- `t_s`: rozkładowy czas odcinka (`arr_s(s+1) − dep_s(s)`), `a_p`: dryf w sekundach na minutę rozkładową w porze `p` (szczyt poranny 7–9, popołudniowy 15–18, poza szczytem; godziny w configu).
- `e_d`: efekt dnia, jedna wartość na przebieg, N(0, σ_e) albo stała z configu.
- `u[s, w]`: odcinek `s`, okno `w` długości `window_s`; dla każdego odcinka szereg AR(1) po oknach z parametrem `rho` i wariancją stacjonarną `sigma²`.
- `η[i, s]`: t-Studenta ze stopniami swobody `df`, skalowany przez `scale`; niezależny między kursami i odcinkami.
- γ: odstęp `h` to czas od przyjazdu poprzedniego autobusu tej samej linii i kierunku na przystanek `s`, `h_rozk` analogicznie z rozkładu; dla pierwszego autobusu składnik = 0. Tylko SimPy.

Pętla i start łańcucha (zapas `L = start_s(i+) − end_s(i)`):

```
Δ_odj[i+] = max(Δ_koniec[i] + l_min − L, δ[i+])
Δ_odj[pierwszy kurs łańcucha] = δ
```

`δ` ma rozkład normalny (`mean_s`, `sd_s`) z wartością roboczą do czasu krzywej pochłaniania z M3.

## Komponenty (`src/krakbus/sim/`)

| Moduł | Odpowiedzialność | Wejście → wyjście |
|---|---|---|
| `params.py` | dataclassy parametrów i zakresów, `load_sim_config(path)` | `configs/sim.yaml` → `SimConfig` |
| `network.py` | sieć doby obsługi dla wszystkich linii, `select(scope)` | `ScheduleIndex`, data → `Network` |
| `noise.py` | wszystkie składniki losowe przebiegu | `Network`, parametry, ziarno → `Noise` |
| `boundary.py` | `Δ` startowe kursów, których poprzednik w łańcuchu jest spoza zakresu | `Network`, wybór, `chains/` dnia → tablica `Δ0` |
| `engine.py` | silnik SimPy: proces na łańcuch | `Network`, `Noise`, parametry → zdarzenia |
| `fast.py` | rekursja numpy po pozycji w łańcuchu, odmawia przy γ ≠ 0 | to samo → zdarzenia |
| `run.py` | CLI `simulate`, zapis wyników i metadanych | argumenty → `data/processed/sim/<run_id>/` |

`Network` (tablice, nie obiekty per przystanek):

- `trips`: indeks `trip_id`; `route_id`, `direction_id`, `block_key` (`service_id` + `block_id`), `blk_idx`, `start_s`, `end_s`, `layover_s` (do następnego kursu bloku), `prev_trip`, `next_trip`.
- `stop_times`: kolejność kursu, `stop_id`, `arr_s`, `dep_s`, `seg_id` odcinka wychodzącego z przystanku (brak na ostatnim), `t_s`.
- `segments`: `seg_id` → (`from_stop`, `to_stop`).
- `select(routes)` zwraca kursy linii z zakresu; łańcuch w symulacji obejmuje tylko te kursy, a kurs, którego poprzednik w bloku jest spoza zakresu, dostaje `Δ0` z `boundary.py`. Dla `city` warunku brzegowego nie ma.

Warunek brzegowy (`boundary: observed | delta`): `observed` bierze `arr_end_delay_s` poprzedniego kursu z `chains/` tego dnia i stosuje regułę pętli; brak obserwacji albo `delta` daje `δ`.

Wynik przebiegu: `data/processed/sim/<run_id>/events.parquet` z kolumnami `service_date`, `vehicle_id` (= `block_key`), `trip_id`, `route_id`, `direction_id`, `stop_sequence`, `stop_id`, `arr_s`, `dep_s`, `arr_ts`, `dep_ts`, `arr_delay_s`, `dep_delay_s`, `source` = `sim`, `run_id`, `seed`; `arr_ts` w sekundach epoki (początek doby GTFS + `arr_s` + Δ), jak w zdarzeniach obserwowanych. Obok `run.json`: config, ziarno, zakres i linie, silnik, wersje GTFS, hash manifestu, czas obliczeń.

CLI: `uv run simulate --date YYYY-MM-DD --scope pilot|corridor|city [--routes ...] [--seed N] [--engine simpy|fast] [--config configs/sim.yaml]`.

`configs/sim.yaml` zawiera zakresy (`pilot: [179]`, `corridor: [179, 169, 174, 173, 144, 124]`, `city`: wszystkie), pory dnia, parametry modelu (`drift`, `day_effect`, `u` z `spatial: independent`, `window_s: 900`, `rho`, `sigma_s`; `eta` z `df`, `scale_s`; `loop` z `l_min_s: 60`, `delta`; `gamma: 0`), `boundary`, `seed`.

## Etap 2: szybka ścieżka

Kursy w kolejności pozycji w łańcuchu (`blk_idx` w obrębie zakresu). Dla pozycji `k` wszystkie kursy naraz: `Δ0` z reguły pętli dla poprzedników (pozycja `k−1`) albo z warunku brzegowego, potem suma skumulowana przyrostów po odcinkach (segmentowana po kursach). Przyrosty liczone z tych samych tablic `Noise`. γ ≠ 0 → `ValueError`. Test: te same ziarna → opóźnienia SimPy i fast równe z tolerancją 1e-6 s na syntetyce, pilocie i korytarzu. Pomiar czasu doby pilota i city w obu silnikach trafia do `run.json` i do M2.

## Etap 3: wizualizacja i eksport

- `src/krakbus/viz/marey.py`: rysowanie Mareya przeniesione z `sandbox/gtfs-experiments/marey.py` (sandbox woła moduł), z opcjonalną nakładką: obserwacja i symulacja tej samej linii i dnia.
- `src/krakbus/viz/export_unity.py` i `docs/EXPORT_UNITY.md`: `schema_version: 1`, jeden wiersz na przyjazd i odjazd (`t` w sekundach epoki, `vehicle_id`, `trip_id`, `route_id`, `lat`, `lon` przystanku, `delay_s`, `source`, `run_id`, `seed`), parquet. Unity interpoluje między wierszami. Próbka zostaje lokalnie w `data/processed/unity_samples/` (zasada repo: bez `data/` w gicie).

## Testy (`tests/sim/`)

Syntetyczna sieć z dwiema liniami dzielącymi odcinek i blokiem przechodzącym między kierunkami:

- zerowy szum, `a = 0`, `γ = 0`, `δ = 0` → czasy równe rozkładowi;
- pętla: `Δ_koniec < L − l_min` pochłonięte, większe przechodzi na następny kurs dokładnie o nadwyżkę;
- sam dryf → mediana rośnie wzdłuż trasy, rozrzut zerowy;
- `η` → std opóźnienia rośnie z numerem przystanku;
- to samo ziarno → identyczne wyniki; inne ziarno → inne;
- `γ = 0`, `u = 0` → zmiana szumu jednego kursu nie zmienia kursów spoza jego łańcucha;
- `u`: dwie linie na wspólnym odcinku w tym samym oknie dostają ten sam składnik; AR(1) ma zadaną korelację między oknami (test statystyczny na długim szeregu);
- warunek brzegowy: kurs z poprzednikiem spoza zakresu startuje z reguły pętli zastosowanej do obserwacji;
- (etap 2) równoważność SimPy i fast; fast odmawia przy γ ≠ 0;
- testy na prawdziwym GTFS (pilot, korytarz) pomijane, gdy brak `data/raw_A/static`.

## Poza zakresem M2

Kalibracja parametrów, per-route tabele dryfu, krzywa pochłaniania jako rozkład `δ`, replikacje i CI scenariuszy (M3, M5), projekt Unity (tor U).
