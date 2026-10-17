# Unity replay v1 (sieć + 30 min GPS): plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scena Unity odtwarza 30 minut ruchu wszystkich autobusów Krakowa (`obs_peak30.jsonl`) na płaskiej planszy z grafem sieci (przystanki + odcinki po ulicach z `shapes.txt`), z kolorem wg opóźnienia, zegarem i panelem po kliknięciu w autobus.

**Architecture:** Python (`krakbus.viz.export_network`) liczy z GTFS graf sieci z łamanymi i zapisuje `network.json` w tym samym układzie metrów co plik pozycji (wspólny moduł `krakbus.viz.geo`). Unity czyta oba pliki ze `StreamingAssets/data/`: czysty C# (`BusReplay.Core`) parsuje i próbkuje trajektorie, a warstwa MonoBehaviour (`BusReplay`) rysuje sieć, autobusy i UI. Scena ma jeden obiekt startowy `ReplayApp`, który buduje resztę w kodzie, więc ręcznego łączenia w Edytorze jest mało.

**Tech Stack:** Python 3.14, uv, numpy, pandas 3, pytest, ruff; Unity 6000.6 URP, Input System 1.20 (tylko nowy), uGUI 2.6 z TextMeshPro, `com.unity.nuget.newtonsoft-json`, `com.unity.test-framework` (EditMode); Unity MCP (CoplayDev v10.3).

**Spec:** [docs/superpowers/specs/2026-10-16-unity-replay-v1-design.md](../specs/2026-10-16-unity-replay-v1-design.md)

## Global Constraints

- Gałąź `bartek_branch`. Commity: temat `(feat|fix|docs|style|chore) opis`, **bez stopek AI** (AGENTS.md).
- `uv run` zamiast `python`; testy `uv run pytest`, lint `uv run ruff check src tests`; `logging` (`krakbus.logger.setup_logging`) zamiast `print` w `src/`; Google docstrings, typy, `X | None`; komentarze i docstringi po polsku bez polskich znaków (dotyczy też C#).
- Nie commitować `data/` ani `unity/Assets/StreamingAssets/data/`.
- Układ współrzędnych: początek Rynek `ORIGIN_LAT = 50.0617`, `ORIGIN_LON = 19.9373`, `EARTH_R = 6_371_000.0`; x na wschód, z na północ, metry (równoodległościowe, `cos(ORIGIN_LAT)`).
- `network.json`: `schema_version: 1`; współrzędne zaokrąglone do 0,1 m; `points` płaska lista `[x0, z0, x1, z1, ...]`, ≥ 2 punkty.
- Progi: przystanek > **100 m** od łamanej oznacza odcinek prosty; uproszczenie Douglas–Peucker **2 m**; dziura w danych pojazdu > **120 s** oznacza ukrycie; przyspieszenie domyślne **×10**, pętla.
- Kolory: ≤ 60 s zielony → 180 s żółty → ≥ 300 s czerwony (płynnie); < −60 s niebieski; postój na pętli albo brak `delay_s` szary.
- Wygląd: trasy szerokość 6 m jasnoszare, przystanki kółka 12 m białe, autobus prostopadłościan ~36 × 9 × 7,5 m (dł. × wys. × szer., ~3× rzeczywistego), plansza ciemnoszara.
- Unity tylko odtwarza: żadnej logiki modelu ani przetwarzania GTFS w C#.
- Unity sterowane przez MCP: po każdej zmianie skryptów `read_console` (0 błędów kompilacji) przed dalszymi krokami; testy przez `run_tests` (EditMode).

## Review Focus

1. **Ten sam pojazd zmienia kurs w trakcie pliku** (koniec kursu, postój, nowy `trip_id`): panel ma pokazywać bieżący kurs i linię z próbki `i`, a nie pierwszy kurs pojazdu. Test w Task 5.
2. **Dwie próbki pojazdu z tym samym `t`** (duplikat z loggera): `Sample` nie dzieli przez zero i nie zwraca NaN pozycji. Test w Task 5.
3. **Trasa „tam i z powrotem” tą samą ulicą albo pętla, w której najbliższy punkt łamanej leży przed rzutem poprzedniego przystanku:** rzuty muszą być niemalejące, a odcinek nie może być pusty ani odwrócony. Test w Task 2.
4. **Przewinięcie zegara z 8:00 na 7:30:** brak przeskoku pozycji z interpolacji „przez pętlę”, a zegar i pozycje zgodne. Test w Task 6 (`PlaybackClock`) i bezstanowe `Sample` z Task 5.
5. **Plik zapisany na Windows (CRLF, BOM, pusta ostatnia linia):** loader nie liczy ich jako uszkodzonych linii. Test w Task 5.

---

## File Structure

| Plik | Odpowiedzialność |
|---|---|
| `src/krakbus/viz/geo.py` | stałe początku układu, `to_xz` |
| `src/viz/export_unity.py` (modyfikacja) | import `to_xz`/stałych z `krakbus.viz.geo` zamiast własnych kopii |
| `src/krakbus/viz/polyline.py` | geometria: `project_stops`, `cut_polyline`, `simplify` |
| `src/krakbus/viz/export_network.py` | GTFS → graf → `network.json`, CLI `export-network` |
| `tests/viz/test_geo.py`, `tests/viz/test_polyline.py`, `tests/viz/test_export_network.py` | testy |
| `pyproject.toml` | skrypt `export-network` |
| `.gitignore` | `unity/Assets/StreamingAssets/data*` |
| `unity/Packages/manifest.json` | newtonsoft-json, test-framework |
| `unity/Assets/Scripts/Core/BusReplay.Core.asmdef` + `*.cs` | czysty C#: `NetworkData`, `NetworkLoader`, `VehicleTrack`, `PositionsLoader`, `DelayColors`, `PlaybackClock`, `ReplayDataException` |
| `unity/Assets/Scripts/Runtime/BusReplay.asmdef` + `*.cs` | `ReplayApp`, `NetworkRenderer`, `BusFleet`, `BusView`, `CameraRig`, `HudView`, `SelectionPanel`, `StopLabels`, `ErrorOverlay` |
| `unity/Assets/Tests/EditMode/BusReplay.Tests.asmdef` + `*Tests.cs` | testy EditMode |
| `unity/Assets/Materials/*.mat` | `Ground`, `Route`, `Stop` (URP/Unlit), `Bus` (URP/Lit) |
| `unity/Assets/Scenes/BusReplay.unity` | scena |
| `docs/EXPORT_UNITY.md`, `docs/UNITY_MCP.md`, `docs/milestones/U_unity_mcp.md`, `docs/DZIENNIK.md` | dokumentacja |

---

### Task 1: Wspólny układ współrzędnych

**Files:**
- Create: `src/krakbus/viz/geo.py`, `tests/viz/test_geo.py`
- Modify: `src/viz/export_unity.py` (usunąć lokalne `ORIGIN_LAT`, `ORIGIN_LON`, `EARTH_R`, `to_xz`; importować z `krakbus.viz.geo`)

**Interfaces:**
- Produces: `ORIGIN_LAT: float`, `ORIGIN_LON: float`, `EARTH_R: float`; `to_xz(lat: ArrayLike, lon: ArrayLike) -> tuple[np.ndarray, np.ndarray]` (x na wschód, z na północ, metry; działa na skalarach i tablicach).

- [ ] **Step 1: Test**

```python
from krakbus.viz.geo import ORIGIN_LAT, ORIGIN_LON, to_xz

def test_origin_is_zero():
    x, z = to_xz(ORIGIN_LAT, ORIGIN_LON)
    assert abs(float(x)) < 1e-9 and abs(float(z)) < 1e-9

def test_matches_positions_file_row():
    # wiersz z obs_peak30.jsonl: lat 50.01012, lon 19.992535 -> x 3942.8, z -5735.4
    x, z = to_xz(np.array([50.01012]), np.array([19.992535]))
    assert x[0] == pytest.approx(3942.8, abs=0.1)
    assert z[0] == pytest.approx(-5735.4, abs=0.1)

def test_axes_east_north():
    x, z = to_xz(np.array([ORIGIN_LAT + 0.01]), np.array([ORIGIN_LON + 0.01]))
    assert x[0] > 0 and z[0] > 0
```

- [ ] **Step 2:** `uv run pytest tests/viz/test_geo.py -v`. Oczekiwane: FAIL (brak modułu).
- [ ] **Step 3:** Utworzyć `geo.py` (przenieść stałe i `to_xz` 1:1 z `src/viz/export_unity.py`); w skrypcie zastąpić je `from krakbus.viz.geo import ORIGIN_LAT, ORIGIN_LON, to_xz`.
- [ ] **Step 4:** `uv run pytest tests/viz -v` i `uv run ruff check src tests`. Oczekiwane: PASS, brak błędów. Dodatkowo `uv run src/viz/export_unity.py --help` kończy się kodem 0.
- [ ] **Step 5: Commit** `(feat) viz: wspolny uklad wspolrzednych geo.to_xz`

---

### Task 2: Geometria łamanej

**Files:**
- Create: `src/krakbus/viz/polyline.py`, `tests/viz/test_polyline.py`

**Interfaces:**
- Produces:
  - `project_stops(line: np.ndarray, stops: np.ndarray) -> tuple[np.ndarray, np.ndarray]`: `line` (n, 2) metry, `stops` (k, 2). Zwraca `s` (k,) pozycję rzutu jako długość łuku od początku łamanej, niemalejącą, oraz `dist` (k,) odległość przystanku od rzutu.
  - `cut_polyline(line: np.ndarray, s_from: float, s_to: float) -> np.ndarray`: (m, 2), m ≥ 2. Pierwszy punkt to punkt łamanej w `s_from`, ostatni w `s_to`, a wierzchołki pomiędzy z oryginału.
  - `simplify(points: np.ndarray, tol_m: float = 2.0) -> np.ndarray`: Douglas–Peucker, końce zachowane.

- [ ] **Step 1: Testy**

```python
L = np.array([[0, 0], [100, 0], [100, 100]], float)          # litera L, dlugosc 200

def test_project_simple():
    s, d = project_stops(L, np.array([[50, 5], [105, 50]], float))
    assert s == pytest.approx([50, 150]); assert d == pytest.approx([5, 5])

def test_project_out_and_back_same_street():
    # tam po y=0, z powrotem po y=8 (ta sama ulica, dwa pasy)
    line = np.array([[0, 0], [200, 0], [200, 8], [0, 8]], float)   # dlugosc 408
    stops = np.array([[50, 1], [150, 1], [150, 7], [50, 7]], float)
    s, _ = project_stops(line, stops)
    assert s == pytest.approx([50, 150, 258, 358])

def test_project_monotonic_when_best_is_behind():
    # przystanek 2 lezy blizej poczatku niz rzut przystanku 1 -> nie cofamy sie
    s, _ = project_stops(L, np.array([[80, 0], [60, 3]], float))
    assert s[1] >= s[0]

def test_cut_endpoints_and_inner_vertex():
    c = cut_polyline(L, 50, 150)
    assert c[0] == pytest.approx([50, 0]); assert c[-1] == pytest.approx([100, 50])
    assert [100, 0] in c.tolist()

def test_cut_consecutive_pieces_touch():
    a, b = cut_polyline(L, 0, 120), cut_polyline(L, 120, 200)
    assert a[-1] == pytest.approx(b[0])

def test_cut_degenerate_gives_two_points():
    assert len(cut_polyline(L, 70, 70)) == 2

def test_simplify_keeps_ends_and_tolerance():
    pts = np.array([[0, 0], [50, 1], [100, 0], [100, 100]], float)
    out = simplify(pts, 2.0)
    assert out[0].tolist() == [0, 0] and out[-1].tolist() == [100, 100]
    assert [50, 1] not in out.tolist() and [100, 0] in out.tolist()
```

- [ ] **Step 2:** `uv run pytest tests/viz/test_polyline.py -v`. Oczekiwane: FAIL (brak modułu).
- [ ] **Step 3: Implementacja.** Rzut punktu na każdy segment łamanej (wektorowo w numpy), a potem wybór sekwencji programowaniem dynamicznym:
  1. kandydaci przystanku `j` to lokalne minima odległości po segmentach (maks. 5 najbliższych), każdy z `(s, dist)`,
  2. przejście z kandydata `p` przystanku `j-1` do kandydata `c` przystanku `j` jest dozwolone, gdy `c.s ≥ p.s`. Jeśli z `p` nie ma dozwolonego przejścia, dodajemy kandydata zastępczego `(p.s, odległość przystanku od punktu łamanej w p.s)`,
  3. wynik to sekwencja o **najmniejszej sumie odległości** (Viterbi).

  Na trasie tam i z powrotem przystanek trafia na właściwy przejazd, bo przypisanie go do drugiego przejazdu zwiększa sumę albo łamie monotoniczność.

  `cut_polyline`: interpolacja po skumulowanej długości łuku. `simplify`: rekurencyjny Douglas–Peucker.
- [ ] **Step 4:** `uv run pytest tests/viz/test_polyline.py -v`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `(feat) viz: rzutowanie przystankow i ciecie lamanej`

---

### Task 3: Eksporter `network.json` i CLI

**Files:**
- Create: `src/krakbus/viz/export_network.py`, `tests/viz/test_export_network.py`
- Modify: `pyproject.toml` (`export-network = "krakbus.viz.export_network:main"`), `docs/EXPORT_UNITY.md` (sekcje „Graf sieci: `network.json`” i „Pozycje GPS: `obs_peak30.jsonl`”: pola z wiersza pliku pozycji `t, sim_time_s, service_date, vehicle_id, trip_id, route_id, lat, lon, x, z, bearing, status, delay_s, layover, source` oraz metadane `schema_version, run_id, gtfs, origin, t_min, t_max, rows, vehicles, routes`)

**Interfaces:**
- Consumes: `to_xz` (Task 1); `project_stops`, `cut_polyline`, `simplify` (Task 2); `load_config().data.raw_dir`, `.processed_dir`; `setup_logging`.
- Produces:
  - `SCHEMA_VERSION = 1`, `MAX_STOP_DIST_M = 100.0`, `SIMPLIFY_TOL_M = 2.0`
  - `read_gtfs(zip_path: Path) -> dict[str, pd.DataFrame]`: klucze `stops`, `trips`, `stop_times`, `shapes`, wszystkie kolumny jako `str`. Brak pliku w ZIP-ie oznacza `ValueError` z nazwą pliku.
  - `build_network(gtfs: dict[str, pd.DataFrame], routes: list[str] | None) -> dict`: struktura `network.json` (`meta`, `stops`, `segments`) i dodatkowo `meta["n_straight"]: dict[str, int]` z powodami `no_shape`, `far_stop`. Brak kursów dla `routes` oznacza `ValueError`.
  - `write_network(net: dict, out_dir: Path) -> Path`: zapis `out_dir/network.json` (UTF-8, bez BOM).
  - `main() -> None`: argumenty `--positions PATH` (meta pliku pozycji; z niej `gtfs` i `routes`), `--gtfs PATH`, `--routes` (lista), `--out DIR` (domyślnie `processed_dir / "unity_samples"`). Wymagane jest `--positions` albo `--gtfs`. ZIP podany nazwą w meta jest szukany w `raw_dir / "static"`.

- [ ] **Step 1: Testy na syntetycznym GTFS** (fixture `mini_gtfs`: 2 linie `A` i `B` dzielące odcinek `s2→s3`; linia `A` z kształtem w kształcie L, `B` z własnym kształtem; linia `C` bez `shape_id`; przystanek `far` 300 m od kształtu linii `B`; współrzędne podane w lat/lon blisko `ORIGIN`).

```python
def test_shared_segment_merged(mini_gtfs):
    net = build_network(mini_gtfs, None)
    seg = [s for s in net["segments"] if (s["from_stop"], s["to_stop"]) == ("s2", "s3")]
    assert len(seg) == 1 and seg[0]["routes"] == ["A", "B"]

def test_segment_follows_shape(mini_gtfs):
    seg = _seg(build_network(mini_gtfs, ["A"]), "s1", "s2")
    assert len(seg["points"]) >= 6              # wiecej niz prosta (2 punkty = 4 liczby)

def test_segment_endpoints_near_stops(mini_gtfs):
    net = build_network(mini_gtfs, ["A"]); stops = {s["stop_id"]: s for s in net["stops"]}
    p = _seg(net, "s1", "s2")["points"]
    assert math.dist(p[:2], (stops["s1"]["x"], stops["s1"]["z"])) < 15

def test_no_shape_is_straight(mini_gtfs):
    net = build_network(mini_gtfs, ["C"])
    assert all(len(s["points"]) == 4 for s in net["segments"])
    assert net["meta"]["n_straight"]["no_shape"] == len(net["segments"])

def test_far_stop_is_straight(mini_gtfs, caplog):
    net = build_network(mini_gtfs, ["B"])
    assert net["meta"]["n_straight"]["far_stop"] >= 1 and "far" in caplog.text

def test_routes_filter_and_stops_subset(mini_gtfs):
    net = build_network(mini_gtfs, ["A"])
    assert net["meta"]["routes"] == ["A"]
    assert {s["stop_id"] for s in net["stops"]} == {"s1", "s2", "s3"}

def test_meta_and_rounding(mini_gtfs, tmp_path):
    net = build_network(mini_gtfs, None)
    assert net["meta"]["schema_version"] == 1
    assert net["meta"]["origin"] == {"lat": 50.0617, "lon": 19.9373, "axes": "x=east m, z=north m"}
    assert {"x_min", "x_max", "z_min", "z_max"} <= net["meta"]["bbox"].keys()
    assert net["meta"]["n_stops"] == len(net["stops"])
    assert all(round(v, 1) == v for s in net["segments"] for v in s["points"])
    path = write_network(net, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["meta"]["n_segments"] == len(net["segments"])

def test_unknown_routes_raise(mini_gtfs):
    with pytest.raises(ValueError):
        build_network(mini_gtfs, ["999"])
```

- [ ] **Step 2:** `uv run pytest tests/viz/test_export_network.py -v`. Oczekiwane: FAIL.
- [ ] **Step 3: Implementacja.** Kursy wybranych linii; grupowanie po (`shape_id`, krotka `stop_id` w kolejności `stop_sequence`), czyli jeden rzut na unikalny wzorzec. Odcinek przystanku z `dist > 100` (obu sąsiadujących odcinków) albo wzorzec bez kształtu daje prostą z `log.warning`. Scalanie po (`from_stop`, `to_stop`): geometria z pierwszego wystąpienia, `routes` jako posortowany zbiór. Następnie `simplify(…, 2.0)`, zaokrąglenie do 0,1 i `bbox` z przystanków. Na koniec `log.info` z liczbą przystanków, odcinków, prostych (z powodem) i rozmiarem pliku.
- [ ] **Step 4:** `uv run pytest tests/viz -v` i `uv run ruff check src tests`. Oczekiwane: PASS.
- [ ] **Step 5: Eksport na prawdziwych danych.** `uv run export-network --positions data/processed/unity_samples/obs_peak30.meta.json`. Oczekiwane: `data/processed/unity_samples/network.json`, w logu ok. 2–3 tys. przystanków i kilka tysięcy odcinków, odcinki proste < 5% (jeśli więcej, sprawdzić przyczynę przed commitem).
- [ ] **Step 6: Commit** `(feat) viz: export-network, graf sieci z lamanymi dla Unity` (bez pliku danych).

---

### Task 4: Projekt Unity: pakiety, assembly, dane

**Files:**
- Modify: `.gitignore` (dopisać `unity/Assets/StreamingAssets/data/` i `unity/Assets/StreamingAssets/data.meta`; zachować niezacommitowaną linię `unity/*.slnx`), `unity/Packages/manifest.json`
- Create: `unity/Assets/Scripts/Core/BusReplay.Core.asmdef`, `unity/Assets/Scripts/Runtime/BusReplay.asmdef`, `unity/Assets/Tests/EditMode/BusReplay.Tests.asmdef`, `unity/Assets/Tests/EditMode/SmokeTests.cs`

**Interfaces:**
- Produces: assembly `BusReplay.Core` (referencje: `Newtonsoft.Json.dll` jako precompiled, `overrideReferences: true`); `BusReplay` (referencje: `BusReplay.Core`, `Unity.InputSystem`, `Unity.TextMeshPro`, `Unity.ugui`); `BusReplay.Tests` (Editor-only, `UNITY_INCLUDE_TESTS`, referencje: `BusReplay.Core`, `nunit.framework.dll`, `UnityEngine.TestRunner`, `UnityEditor.TestRunner`).

- [ ] **Step 1:** Przez MCP `manage_packages`: dodać `com.unity.nuget.newtonsoft-json` i `com.unity.test-framework` (wersje rozwiązane przez Package Manager). `read_console`: 0 błędów.
- [ ] **Step 2:** Utworzyć trzy pliki `.asmdef` i `SmokeTests.cs` z jednym testem `Core_assembly_loads` (`Assert.AreEqual("BusReplay.Core", typeof(BusReplay.Core.ReplayDataException).Assembly.GetName().Name)`) oraz pustą klasą `public class ReplayDataException : System.Exception { public ReplayDataException(string m) : base(m) {} }` w `Core/ReplayDataException.cs`.
- [ ] **Step 3:** `refresh_unity`, `read_console` (0 błędów), `run_tests` EditMode. Oczekiwane: 1 PASS.
- [ ] **Step 4:** Skopiować dane: `mkdir -p unity/Assets/StreamingAssets/data && cp data/processed/unity_samples/{network.json,obs_peak30.jsonl,obs_peak30.meta.json} unity/Assets/StreamingAssets/data/`. `git status` nie pokazuje plików z `StreamingAssets/data`.
- [ ] **Step 5: Commit** `(chore) unity: projekt URP, pakiety i assembly BusReplay`. Commit zawiera `unity/Assets`, `unity/Packages`, `unity/ProjectSettings`, `.gitignore`, bez `Library`, `Temp` i danych. Przed commitem `git status` sprawdza, że nie wchodzą pliki > 5 MB.

---

### Task 5: Dane w C#: sieć, trajektorie, wczytywanie

**Files:**
- Create: `unity/Assets/Scripts/Core/NetworkData.cs`, `NetworkLoader.cs`, `VehicleTrack.cs`, `PositionsLoader.cs`; `unity/Assets/Tests/EditMode/NetworkLoaderTests.cs`, `VehicleTrackTests.cs`, `PositionsLoaderTests.cs`

**Interfaces (namespace `BusReplay.Core`):**
- Consumes: `ReplayDataException` (Task 4).
- Produces:
  - `NetworkStop { string StopId; string Name; Vector2 Pos; }` (Pos.x = x, Pos.y = z)
  - `NetworkSegment { string FromStop; string ToStop; string[] Routes; Vector2[] Points; }`
  - `NetworkData { string Gtfs; NetworkStop[] Stops; NetworkSegment[] Segments; Rect Bbox; }`
  - `static NetworkData NetworkLoader.Parse(string json)`: `schema_version != 1` daje `ReplayDataException` z komunikatem zawierającym `schema_version`. Nieznane pola są ignorowane.
  - `struct TrackSample { bool Visible; Vector2 Pos; float HeadingDeg; float DelayS; bool Layover; string RouteId; string TripId; }` (`DelayS` = `float.NaN` dla `null`)
  - `VehicleTrack(string vehicleId, double[] t, float[] x, float[] z, float[] bearing, float[] delay, bool[] layover, string[] routeId, string[] tripId)`, `string VehicleId`, `const double MaxGapS = 120`, `TrackSample Sample(double T)`
  - `PositionsMeta { int SchemaVersion; string Gtfs; double TMin; double TMax; }`, `static PositionsMeta PositionsLoader.ParseMeta(string json)` (zła wersja daje `ReplayDataException`)
  - `PositionsData { Dictionary<string, VehicleTrack> Tracks; double TMin; double TMax; double LocalOffsetS; int SkippedLines; }` (`LocalOffsetS` = `sim_time_s − t` z pierwszego poprawnego wiersza; zegar lokalny = `(T + LocalOffsetS) mod 86400`)
  - `static PositionsData PositionsLoader.Parse(IEnumerable<string> lines)`: wiersze grupowane po `vehicle_id`, w grupie sortowanie stabilne po `t`.

- [ ] **Step 1: Testy (NUnit)**

```csharp
// VehicleTrackTests
var tr = Track(t: new[]{0d, 10, 20, 200}, x: new[]{0f, 100, 200, 300}, bearing: new[]{350f, 10, 10, 10},
               route: new[]{"A","B","B","B"}, trip: new[]{"a1","b1","b1","b1"});
[Test] Interpolates_position()   => Assert.AreEqual(50f, tr.Sample(5).Pos.x, 1e-3);
[Test] Heading_wraps_through_zero() => Assert.AreEqual(0f, Mathf.DeltaAngle(0, tr.Sample(5).HeadingDeg), 1e-3);
[Test] Hidden_before_after()     { Assert.IsFalse(tr.Sample(-1).Visible); Assert.IsFalse(tr.Sample(201).Visible); }
[Test] Hidden_in_gap_over_120s() => Assert.IsFalse(tr.Sample(100).Visible);
[Test] Visible_at_last_sample()  => Assert.IsTrue(tr.Sample(200).Visible);
[Test] Route_and_trip_from_current_sample() { Assert.AreEqual("B", tr.Sample(15).RouteId) /* proba 1 */; Assert.AreEqual("a1", tr.Sample(5).TripId); }
[Test] Duplicate_timestamp_no_nan() { var d = Track(t: new[]{0d, 0, 10}, x: new[]{0f, 5, 10}); var s = d.Sample(0);
                                       Assert.IsTrue(s.Visible); Assert.IsFalse(float.IsNaN(s.Pos.x)); }

// PositionsLoaderTests
const string Row1 = "{\"t\":100,\"sim_time_s\":27000,\"vehicle_id\":\"v1\",\"trip_id\":\"a\",\"route_id\":\"179\",\"x\":1,\"z\":2,\"bearing\":90,\"delay_s\":null,\"layover\":true,\"extra\":1}";
[Test] Null_delay_is_nan_and_layover() { var p = Parse(Row1, Row2); var s = p.Tracks["v1"].Sample(100);
                                          Assert.IsTrue(float.IsNaN(s.DelayS)); Assert.IsTrue(s.Layover); }
[Test] Groups_and_sorts_by_t()          { /* v1 z t=110 przed t=100 w pliku -> Sample(105).Pos.x miedzy */ }
[Test] Bad_line_counted()               => Assert.AreEqual(1, Parse(Row1, "{oops", Row2).SkippedLines);
[Test] Crlf_bom_and_blank_ignored()     => Assert.AreEqual(0, Parse("﻿" + Row1 + "\r", Row2, "").SkippedLines);
[Test] Local_offset_from_sim_time()     => Assert.AreEqual(26900d, Parse(Row1).LocalOffsetS);
[Test] Meta_wrong_version_throws()      => Assert.Throws<ReplayDataException>(() => PositionsLoader.ParseMeta("{\"schema_version\":2}"));

// NetworkLoaderTests
[Test] Parses_stops_segments_points()   { /* 1 stop, 1 segment z points [0,0,3,4] -> Points.Length==2, Points[1]==(3,4), Routes=={"169","179"} */ }
[Test] Wrong_schema_throws()            => Assert.Throws<ReplayDataException>(() => NetworkLoader.Parse("{\"meta\":{\"schema_version\":2}}"));
```

- [ ] **Step 2:** `refresh_unity`, `read_console`, `run_tests` EditMode. Oczekiwane: nowe testy FAIL (brak typów, błędy kompilacji testów są tu dopuszczalnym „FAIL”).
- [ ] **Step 3: Implementacja.** Parsowanie Newtonsoft (`JObject`/`JsonConvert` na lekkie DTO z `float?` dla `delay_s`). Linie z BOM, `\r` albo puste usuwane przed parsowaniem; puste nie są liczone. `Sample` przez `Array.BinarySearch` po `t`. Przy `t[i+1] == t[i]` brana jest próbka `i+1` bez interpolacji. Kąt przez `Mathf.LerpAngle`.
- [ ] **Step 4:** `run_tests` EditMode. Oczekiwane: wszystkie PASS; `read_console` bez błędów.
- [ ] **Step 5: Commit** `(feat) unity: wczytywanie sieci i trajektorii pojazdow`

---

### Task 6: Kolory opóźnienia i zegar odtwarzania

**Files:**
- Create: `unity/Assets/Scripts/Core/DelayColors.cs`, `PlaybackClock.cs`; `unity/Assets/Tests/EditMode/DelayColorsTests.cs`, `PlaybackClockTests.cs`

**Interfaces (`BusReplay.Core`):**
- Produces:
  - `static Color DelayColors.For(float delayS, bool layover)`; stałe `Green = (0.20, 0.75, 0.30)`, `Yellow = (0.95, 0.80, 0.15)`, `Red = (0.85, 0.15, 0.15)`, `Blue = (0.25, 0.50, 0.95)`, `Grey = (0.55, 0.55, 0.55)`; publiczna tablica legendy `(string label, Color color)[] Legend`.
  - `PlaybackClock(double tMin, double tMax, float speed = 10f)`, `double T`, `float Speed`, `void Advance(float dtReal)` (T += dt·Speed; po przekroczeniu `tMax` zawija do `tMin + nadmiar`), `static string LocalHms(double t, double localOffsetS)` (np. `"07:43:12"`).

- [ ] **Step 1: Testy**

```csharp
[Test] Thresholds() { AreClose(DelayColors.Green, DelayColors.For(30, false)); AreClose(DelayColors.Yellow, DelayColors.For(180, false));
                      AreClose(DelayColors.Red, DelayColors.For(400, false)); AreClose(DelayColors.Blue, DelayColors.For(-120, false)); }
[Test] Between_green_and_yellow_is_blend() { var c = DelayColors.For(120, false); Assert.That(c.r, Is.InRange(DelayColors.Green.r, DelayColors.Yellow.r)); }
[Test] Layover_and_nan_are_grey() { AreClose(DelayColors.Grey, DelayColors.For(500, true)); AreClose(DelayColors.Grey, DelayColors.For(float.NaN, false)); }
[Test] Clock_advances_with_speed() { var c = new PlaybackClock(0, 1800, 10); c.Advance(1f); Assert.AreEqual(10d, c.T, 1e-9); }
[Test] Clock_wraps() { var c = new PlaybackClock(0, 1800, 10); c.Advance(181f); Assert.AreEqual(10d, c.T, 1e-6); }
[Test] Local_hms() => Assert.AreEqual("07:30:00", PlaybackClock.LocalHms(1791955800, 27000 - 1791955800d));
```

- [ ] **Step 2:** `run_tests`. Oczekiwane: FAIL.
- [ ] **Step 3:** Implementacja (`Color.Lerp` między progami z Global Constraints).
- [ ] **Step 4:** `run_tests`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `(feat) unity: kolory opoznienia i zegar odtwarzania`

---

### Task 7: Scena: sieć, autobusy, kamera

**Files:**
- Create: `unity/Assets/Scripts/Runtime/ReplayApp.cs`, `NetworkRenderer.cs`, `BusFleet.cs`, `BusView.cs`, `CameraRig.cs`, `ErrorOverlay.cs`; materiały `unity/Assets/Materials/Ground.mat`, `Route.mat`, `Stop.mat` (URP/Unlit), `Bus.mat` (URP/Lit); scena `unity/Assets/Scenes/BusReplay.unity`
- Modify: `unity/ProjectSettings/EditorBuildSettings.asset` (scena `BusReplay` jako pierwsza)

**Interfaces (namespace `BusReplay`):**
- Consumes: wszystko z `BusReplay.Core` (Task 5–6).
- Produces:
  - `ReplayApp : MonoBehaviour`: pola `string networkFile = "network.json"`, `string positionsFile = "obs_peak30.jsonl"`, `float speed = 10f`, materiały `ground, route, stop, bus`. Właściwości `NetworkData Network`, `PositionsData Positions`, `PlaybackClock Clock`, `BusFleet Fleet`, zdarzenie `event Action Loaded`. `Start()` czyta pliki z `Path.Combine(Application.streamingAssetsPath, "data", …)` (meta pozycji: nazwa pliku z `.jsonl` zamienionym na `.meta.json`). Brak pliku albo `ReplayDataException` oznacza `ErrorOverlay.Show(msg)` + `Debug.LogError`, bez rzucania. Brak pliku: komunikat z nazwą i komendą (`uv run export-network --positions …` albo `uv run src/viz/export_unity.py …`, potem kopiowanie do `StreamingAssets/data/`). Różne `Gtfs` w obu plikach: `Debug.LogWarning`. `SkippedLines > 0`: jedno `Debug.LogWarning` z liczbą. `Update()`: `Clock.Advance(Time.deltaTime)`, `Fleet.Tick(Clock.T)`.
  - `static GameObject NetworkRenderer.Build(NetworkData net, Material ground, Material route, Material stop)`: plansza (quad pod `Bbox` + 1 km zapasu, y = 0), jeden mesh wstęg 6 m (y = 0.05, `IndexFormat.UInt32`), jeden mesh kółek 12 m, 16 boków (y = 0.1).
  - `BusFleet : MonoBehaviour`: `void Init(PositionsData data, Material bus)`, `void Tick(double T)`, `IReadOnlyDictionary<string, BusView> Views`, `int VisibleCount`.
  - `BusView : MonoBehaviour`: `string VehicleId`, `TrackSample Current`, `void Apply(TrackSample s)` (pozycja y = 4,5, obrót `Quaternion.Euler(0, HeadingDeg, 0)` (bearing GTFS: 0 = północ = +z, zgodnie z ruchem wskazówek, jak Unity Y), kolor `MaterialPropertyBlock` `_BaseColor`, `SetActive(Visible)`), `void SetHighlighted(bool on)` (skala 1,3× i jaśniejszy kolor). Ma `BoxCollider` do klikania.
  - `CameraRig : MonoBehaviour` (na `Main Camera`): Input System (`Mouse.current`, `Keyboard.current`). Lewy przycisk przeciągnięty albo WASD przesuwają po płaszczyźnie, kółko przybliża (wysokość 150–25000 m), prawy przycisk obraca wokół osi Y. Start: nad (0, 0), wysokość 12 km, pochylenie 55°. `Camera.farClipPlane = 60000`.
  - `ErrorOverlay`: `static void Show(string msg)` tworzy Canvas z czerwonym tekstem TMP na środku.

- [ ] **Step 1: Scena przez MCP.** `manage_scene` tworzy `Assets/Scenes/BusReplay.unity` z `Main Camera` (+`CameraRig`), `Directional Light`, pustym `ReplayApp` (+`ReplayApp`); materiały przez `manage_material`/`manage_asset` (shadery: `Universal Render Pipeline/Unlit` i `Universal Render Pipeline/Lit`, kolory z Global Constraints) przypięte w Inspektorze `ReplayApp`. Scenę dodać do Build Settings.
- [ ] **Step 2: Skrypty.** Implementacja według Interfaces. `refresh_unity`, `read_console`: 0 błędów. `run_tests` EditMode: wszystko nadal PASS.
- [ ] **Step 3: Smoke 1–4 przez MCP.**
  - `manage_editor` play, odczekać ~5 s, `read_console`: 0 błędów (dopuszczalne ostrzeżenie o liczbie pominiętych linii).
  - `execute_code` (albo `find_gameobjects`): `FindFirstObjectByType<BusFleet>().VisibleCount` w przedziale 200–537.
  - Zrzut ekranu z kamery (`manage_camera` screenshot). Wizualnie: sieć układa się w Kraków (Wisła jako przerwa między liniami z mostami), autobusy leżą na liniach tras.
  - Drugi zrzut po ~5 s: autobusy są w innych miejscach.
  - Test błędu: zmienić `positionsFile` na `brak.jsonl`, Play, na ekranie komunikat z nazwą pliku, w konsoli 1 błąd, brak wyjątku. Przywrócić.
  - `manage_editor` stop.
- [ ] **Step 4: Commit** `(feat) unity: scena BusReplay z siecia, autobusami i kamera`

---

### Task 8: Zegar, legenda, panel autobusu, nazwy przystanków

**Files:**
- Create: `unity/Assets/Scripts/Runtime/HudView.cs`, `SelectionPanel.cs`, `StopLabels.cs`
- Modify: `ReplayApp.cs` (po `Loaded` dodaje te komponenty do siebie)

**Interfaces (`BusReplay`):**
- Consumes: `ReplayApp` (`Clock`, `Positions.LocalOffsetS`, `Network`, `Fleet`, `Loaded`), `BusView`, `DelayColors.Legend`, `PlaybackClock.LocalHms`.
- Produces:
  - `HudView`: Canvas (Screen Space Overlay). Lewy górny róg: zegar `HH:MM:SS` i `×10`. Lewy dolny: legenda (kwadrat koloru + etykieta z `DelayColors.Legend`).
  - `SelectionPanel`: klik lewym przyciskiem bez przeciągnięcia (< 5 px), `Physics.Raycast` w `BusView`. Trafienie zaznacza (`SetHighlighted`) i pokazuje panel w prawym górnym rogu z polami `Linia`, `Kurs`, `Pojazd`, `Opóźnienie` (`+3 min 12 s` / `−1 min 05 s` / `—`), `Na pętli: tak/nie`, odświeżany co klatkę z `BusView.Current`. Pudło albo zniknięcie autobusu zamyka panel. `string FormatDelay(float delayS)` jako `public static` (testowalne).
  - `StopLabels`: pula 40 obiektów TextMeshPro (world space, obrócone do kamery, rozmiar zależny od wysokości). Co 0,25 s, gdy wysokość kamery < 1500 m: wybiera do 40 przystanków widocznych w kadrze, najbliższych środka ekranu. Powyżej 1500 m wszystkie ukryte.

- [ ] **Step 1: Test** `SelectionPanelTests.Format_delay` w EditMode, jeśli `BusReplay.Tests` ma referencję do `BusReplay` (dodać ją w asmdef testów): `"+3 min 12 s" == FormatDelay(192)`, `"−1 min 05 s" == FormatDelay(-65)`, `"—" == FormatDelay(float.NaN)`. `run_tests`: FAIL.
- [ ] **Step 2:** Implementacja. `refresh_unity`, `read_console`: 0 błędów. `run_tests`: PASS.
- [ ] **Step 3: Smoke 5 przez MCP.** Play. `execute_code`: ustawić kamerę nad wybranym widocznym autobusem i wywołać logikę zaznaczenia dla jego `VehicleId` (albo symulować klik raycastem w jego pozycję ekranową). Zrzut ekranu: panel z linią i opóźnieniem, autobus podświetlony. Zjazd kamerą na wysokość 800 m nad Rynkiem (0, 0), zrzut: widoczne nazwy przystanków. Zegar w zrzucie między 07:30:00 a 08:00:00. Stop.
- [ ] **Step 4: Commit** `(feat) unity: zegar, legenda, panel autobusu i nazwy przystankow`

---

### Task 9: Dokumentacja i dziennik

**Files:**
- Modify: `docs/UNITY_MCP.md` (sekcja „Replay v1: uruchomienie”: 1) `uv run export-network --positions data/processed/unity_samples/obs_peak30.meta.json`, 2) skopiowanie trzech plików do `unity/Assets/StreamingAssets/data/`, 3) otwarcie sceny `BusReplay`, Play; sterowanie kamerą; skąd wziąć `obs_peak30.jsonl`), `docs/milestones/U_unity_mcp.md` (odhaczyć fazę 1: projekt w repo, scena + Bus + kamera, loader, pojazd po trasie, kolor wg `delay_s`, smoke; w fazie 2: wiele pojazdów naraz, etykieta czasu), `docs/DZIENNIK.md` (wpis na górze wg szablonu: autor z `git config user.name`, commity z Task 1–8, decyzje: GPS zamiast zdarzeń, graf jako tło, wspólne `geo`, rzut przystanków programowaniem dynamicznym (monotoniczny, minimalna suma odległości); sprawdzone: wyniki testów i smoke; otwarte: tło miasta, sterowanie czasem, symulacja po łamanych)

- [ ] **Step 1:** Edycja trzech plików.
- [ ] **Step 2:** `uv run pytest` (cały zestaw) i `uv run ruff check src tests`: PASS. `run_tests` EditMode w Unity: PASS.
- [ ] **Step 3: Commit** `(docs) unity replay v1: uruchomienie, milestone U, dziennik`
