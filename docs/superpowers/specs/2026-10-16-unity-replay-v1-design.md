# Unity: replay 30 minut ruchu autobusów (v1), projekt

Data: 2026-10-16. Tor: [U](../../milestones/U_unity_mcp.md), faza 1 i część fazy 2. Zatwierdzone w rozmowie 16.10 (wariant „Python przygotowuje pliki, Unity je tylko czyta”).

## Cel i zakres

Aplikacja Unity odtwarza ruch wszystkich autobusów Krakowa z pliku obserwacji `obs_peak30.jsonl` (14.10.2026, 7:30–8:00, 537 pojazdów, ok. 140 linii) na płaskiej planszy, na której narysowany jest graf sieci: przystanki i odcinki tras prowadzone po ulicach (geometria z `shapes.txt`). Autobusy są kolorowane według opóźnienia, a kliknięcie w autobus pokazuje jego dane.

Unity nic nie liczy. Model i całe przetwarzanie danych zostają w Pythonie, zgodnie z zasadą toru U.

Agent (Claude Code) buduje scenę, skrypty i testy przez Unity MCP.

### W zakresie v1

- eksporter grafu sieci w Pythonie (`uv run export-network`) → `network.json`,
- scena `BusReplay`: plansza, trasy, przystanki z nazwami przy zbliżeniu, 537 autobusów jadących po pozycjach GPS,
- kolor autobusu według `delay_s`, legenda kolorów, zegar,
- kliknięcie w autobus otwiera panel z linią, kursem, pojazdem, opóźnieniem i informacją o postoju na pętli,
- odtwarzanie automatyczne z przyspieszeniem ×10 (ustawiane w Inspektorze), zapętlone,
- kamera: przesuwanie, przybliżanie, obrót.

### Poza zakresem v1 (kolejne warstwy, bez przebudowy v1)

Ortofotomapa lub podkład OSM, budynki 3D, drzewa, suwak czasu i sterowanie prędkością w trakcie działania, filtr linii, słupki opóźnień na przystankach, autobusy z symulacji (sterowane zdarzeniami przystankowymi po łamanych z `network.json`), porównanie obserwacja ‖ symulacja, przełączanie scenariuszy.

## Decyzje

- **Źródło ruchu: pozycje GPS, nie zdarzenia przystankowe.** Plik 30-minutowy zawiera próbki pozycji mniej więcej co 10 s na pojazd, więc autobusy jadą po prawdziwych ulicach. Kontrakt v1 z [EXPORT_UNITY.md](../../EXPORT_UNITY.md) (zdarzenia `arr`/`dep`) zostaje do symulacji. Jej autobusy pojadą między przystankami po łamanych odcinków z `network.json`.
- **Pod autobusami jest graf sieci, a nie mapa.** Wierzchołki to słupki, krawędzie to skierowane odcinki między kolejnymi przystankami kursu, tak jak `segments` w `krakbus.sim.network`. Każda krawędź ma do rysowania łamaną wyciętą z `shapes.txt`. Widać tylko ulice, którymi jeżdżą autobusy. Tło miasta to osobna, późniejsza warstwa.
- **Python przygotowuje pliki, Unity je czyta (wariant 1).** Odrzucone: parsowanie GTFS w Unity (łamie zasadę toru U, `stop_times.txt` ma 140 MB, geometria w C# bez testów); import do assetów w Edytorze (więcej kodu edytorowego, opłaca się dopiero przy pełnym dniu, do którego można przejść później bez zmiany formatu).
- **Ten sam GTFS i ten sam układ współrzędnych co plik pozycji.** Eksporter bierze nazwę ZIP-a z `gtfs` w `obs_peak30.meta.json`. Współrzędne liczy tą samą funkcją `to_xz` z tym samym początkiem (Rynek, 50.0617 N, 19.9373 E; x na wschód, z na północ, metry). Stałe i `to_xz` przenosimy do wspólnego modułu, z którego korzysta też `src/viz/export_unity.py`.
- **Bez pasażerów.** Model i dane nie mają liczby pasażerów, więc v1 nie pokazuje „obciążenia” przystanków.

## Python: eksporter grafu sieci

Moduł `src/krakbus/viz/export_network.py`, skrypt `export-network` w `pyproject.toml`.

```
uv run export-network --positions data/processed/unity_samples/obs_peak30.meta.json
uv run export-network --gtfs data/raw_A/static/GTFS_KRK_A_20261012_123022.zip --routes 179,169,174
```

- `--positions`: plik metadanych pozycji. Z niego brane są GTFS (`gtfs`) i lista linii (`routes`).
- `--gtfs`, `--routes`: jawne podanie zamiast `--positions`. Bez `--routes` eksportowane są wszystkie linie.
- `--out`: katalog wyjściowy, domyślnie `data/processed/unity_samples/`.

### Algorytm

1. Wczytaj `stops.txt`, `trips.txt`, `stop_times.txt`, `shapes.txt` z ZIP-a. Ogranicz do kursów wybranych linii.
2. Dla każdej unikalnej pary (`shape_id`, sekwencja przystanków) jeden raz:
   - zamień łamaną kształtu i przystanki na metry (`to_xz`),
   - **rzutuj przystanki na łamaną monotonicznie**: rzuty kolejnych przystanków nie cofają się wzdłuż łamanej, a spośród takich sekwencji wybierana jest ta o najmniejszej sumie odległości (programowanie dynamiczne), żeby trasa wracająca tą samą ulicą nie przeskoczyła na drugi przejazd,
   - jeśli odległość przystanku od łamanej > 100 m albo kurs nie ma `shape_id`: ostrzeżenie w logu, odcinek jako prosta przystanek → przystanek,
   - **potnij łamaną** między rzutami kolejnych przystanków. Każdy kawałek zaczyna się w rzucie przystanku `k` i kończy w rzucie przystanku `k+1`.
3. **Scal odcinki** po kluczu (`from_stop`, `to_stop`): jedna geometria (z pierwszego wystąpienia), suma zbioru linii w `routes`.
4. **Uprość łamane** algorytmem Douglasa–Peuckera z tolerancją 2 m (końce zostają).
5. Zapisz `network.json` i podsumuj w logu: liczbę przystanków, odcinków, odcinków prostych (z powodem) i rozmiar pliku.

### Format `network.json` (`schema_version: 1`)

```json
{
  "meta": {
    "schema_version": 1,
    "gtfs": "GTFS_KRK_A_20261012_123022.zip",
    "origin": {"lat": 50.0617, "lon": 19.9373, "axes": "x=east m, z=north m"},
    "routes": ["102", "104", "..."],
    "bbox": {"x_min": -9000.0, "x_max": 11000.0, "z_min": -8000.0, "z_max": 9000.0},
    "n_stops": 2400,
    "n_segments": 5200
  },
  "stops": [
    {"stop_id": "18057", "name": "AKF / PK", "x": 4310.2, "z": 1381.5}
  ],
  "segments": [
    {"from_stop": "18057", "to_stop": "18060", "routes": ["169", "179"],
     "points": [4310.2, 1381.5, 4352.0, 1390.1, 4401.7, 1422.8]}
  ]
}
```

- `stops`: tylko przystanki obsługiwane przez wybrane linie. `x`, `z` w metrach, zaokrąglone do 0,1 m.
- `segments.points`: płaska lista `[x0, z0, x1, z1, ...]`, co najmniej dwa punkty.
- Zasady wersjonowania jak w kontrakcie eksportu: dodanie pola nie podnosi `schema_version`, a usunięcie pola albo zmiana jego znaczenia podnosi.

## Unity: aplikacja

Projekt `unity/` (Unity 6000.6, URP). Scena `Assets/Scenes/BusReplay.unity`, kod w `Assets/Scripts/` (assembly `BusReplay`), testy w `Assets/Tests/EditMode/`.

### Dane wejściowe

`Assets/StreamingAssets/data/network.json` i `Assets/StreamingAssets/data/obs_peak30.jsonl` (+ `.meta.json`). Katalog `StreamingAssets/data/` jest w `.gitignore` (zasada repo: bez `data/` w gicie). README opisuje skopiowanie plików z `data/processed/unity_samples/`. Nazwa pliku pozycji jest polem w Inspektorze.

### Komponenty

| Komponent | Odpowiedzialność |
|---|---|
| `NetworkData`, `NetworkLoader` | czysty C#: wczytanie i walidacja `network.json` (Newtonsoft JSON) |
| `VehicleTrack` | czysty C#: tablice `t`, `x`, `z`, `bearing`, `delay` (`NaN` dla `null`), `layover` jednego pojazdu; `Sample(T)` |
| `PositionsLoader` | czysty C#: JSON Lines linia po linii → słownik `vehicle_id → VehicleTrack` (posortowane po `t`) |
| `DelayColors` | czysty C#: opóźnienie / postój → kolor |
| `PlaybackClock` | czas `T` od `t_min` do `t_max`, przyspieszenie (domyślnie ×10), pętla |
| `NetworkRenderer` | jeden mesh z wstęg wszystkich odcinków; przystanki jako instancjonowane kółka |
| `StopLabels` | nazwy przystanków (TextMeshPro) tylko przy zbliżeniu, dla przystanków blisko środka ekranu, z limitem liczby napisów |
| `BusFleet`, `BusView` | tworzy obiekt na pojazd; co klatkę `Sample(T)` → pozycja, obrót, kolor (`MaterialPropertyBlock`), widoczność |
| `SelectionPanel` | klik (raycast) → podświetlenie i panel z danymi autobusu, odświeżany na żywo; klik w puste miejsce zamyka |
| `HudView` | zegar `HH:MM:SS` czasu lokalnego (Europe/Warsaw) i legenda kolorów |
| `CameraRig` | widok z góry pod kątem; przesuwanie (mysz, WASD), przybliżanie (kółko), obrót (prawy przycisk) |

### `VehicleTrack.Sample(T)`

- Wyszukiwanie binarne pary `t[i] ≤ T < t[i+1]`, interpolacja liniowa `x`, `z`. Kąt interpolowany najkrótszą drogą (przejście przez 0°/360°).
- Opóźnienie i `layover` z próbki `i` (bez interpolacji).
- Pojazd **ukryty**, gdy `T < t[0]`, `T > t[last]` albo `t[i+1] − t[i] > 120 s` (dziura w danych). Wtedy nie „przelatuje” przez miasto.

### Wygląd

- Plansza: jednolity ciemnoszary prostokąt pod `bbox` z zapasem.
- Trasy: jasnoszare wstęgi o stałej szerokości ok. 6 m.
- Przystanki: białe kółka o średnicy ok. 12 m.
- Autobus: prostopadłościan wydłużony w kierunku jazdy (ok. 3× rzeczywistego rozmiaru, żeby był widoczny z wysokości).
- Kolory opóźnienia: ≤ 60 s zielony, płynnie do żółtego przy 180 s, do czerwonego przy ≥ 300 s. Przed czasem (< −60 s) niebieski. Postój na pętli albo brak `delay_s`: szary.

## Błędy

Zasada: komunikat jest czytelny i widoczny, a aplikacja się nie wywraca.

- Brak pliku w `StreamingAssets/data/`: komunikat na ekranie i w konsoli z nazwą pliku i komendą, która go tworzy.
- `schema_version` inna niż 1: komunikat, plik nie jest wczytywany.
- `gtfs` w `network.json` różne od `gtfs` w metadanych pozycji: ostrzeżenie (przystanki mogą nie pasować), aplikacja działa.
- Uszkodzona linia JSONL: pominięta. Na koniec jedno ostrzeżenie z liczbą pominiętych linii.
- Nieznane pola w JSON są ignorowane.
- Python: odcinki proste (brak kształtu lub przystanek > 100 m od łamanej) są logowane i podsumowywane, a eksport się nie przerywa. Brak wymaganego pliku w ZIP-ie albo brak kursów dla wybranych linii kończy eksport błędem.

## Testy i weryfikacja

**Python (`tests/viz/test_export_network.py`, syntetyczna mini-sieć):**
- rzutowanie przystanków na łamaną, w tym trasa wracająca tą samą ulicą,
- cięcie łamanej: kawałki zaczynają się i kończą w rzutach przystanków, kolejne kawałki się stykają,
- scalanie odcinków wspólnych dla dwóch linii (jeden odcinek, obie linie w `routes`),
- odcinek prosty dla przystanku daleko od łamanej i dla kursu bez kształtu,
- uproszczenie zachowuje końce i mieści się w tolerancji,
- `to_xz` daje te same wartości co w pliku pozycji (ten sam moduł),
- struktura i metadane `network.json`.

**Unity (Test Framework, EditMode, uruchamiane przez MCP `run_tests`):**
- `VehicleTrack.Sample`: interpolacja, kąt przez 0°/360°, ukrycie przed i po danych oraz przy dziurze > 120 s,
- `PositionsLoader`: linia z `delay_s: null`, uszkodzona linia, sortowanie po `t`,
- `NetworkLoader`: poprawny plik, zła `schema_version`,
- `DelayColors`: progi i kolory specjalne.

**Smoke-test przez MCP (definicja „działa”):**
1. Play, w konsoli 0 błędów.
2. Około 7:45 widocznych jest kilkaset autobusów.
3. Zrzut ekranu z góry: sieć tras układa się w Kraków, autobusy leżą na liniach tras.
4. Po kilku sekundach autobusy są w innych miejscach, zegar idzie.
5. Kliknięcie w autobus otwiera panel z linią i opóźnieniem.

## Dokumentacja

- `docs/EXPORT_UNITY.md`: sekcja o `network.json` i o pliku pozycji GPS (obecny format `obs_peak30.jsonl`).
- README projektu Unity albo sekcja w `docs/UNITY_MCP.md`: jak wygenerować pliki, skopiować je do `StreamingAssets/data/` i uruchomić scenę.
- `docs/milestones/U_unity_mcp.md`: odhaczenie punktów fazy 1. Wpis w `docs/DZIENNIK.md` po implementacji.
