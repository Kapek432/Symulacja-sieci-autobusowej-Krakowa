# Unity MCP: setup

Track U (see [milestones/U_unity_mcp.md](milestones/U_unity_mcp.md)). The simulation stays in Python; Unity only plays back exported results. The agent (Claude Code) drives the Unity editor through an MCP server.

We use **MCP for Unity** (CoplayDev, https://github.com/CoplayDev/unity-mcp), version 10.x, which supports Unity 2021.3 LTS – 6.x.

## Requirements

- Unity Hub + Unity 6 LTS (3D URP project)
- `uv` (already used in the project) and Python 3.10+
- Claude Code CLI (`claude` on PATH)

## Steps

1. **Unity project** in the `unity/` directory of the repo (Unity Hub → New project → 3D (URP) → location: repo root, name `unity`). `Library/`, `Temp/`, `Logs/`, `UserSettings/` are in `.gitignore`.
2. **MCP package:** Window → Package Manager → `+` → *Add package from git URL*:
   ```
   https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#v10.3.0
   ```
   (pinned so the whole team has the same version; to upgrade, change the tag here and in `unity/Packages/manifest.json`).
3. **Register with Claude Code:** in Unity, Window → MCP for Unity → *Configure All Detected Clients* (or the register button next to Claude Code). The window shows the connection status.
4. **Check:** in a terminal, `claude mcp list` should show the Unity server as connected. Smoke test from Claude Code: "Create an empty Bus object in the scene and a camera looking at it".

Unity must be open for the server to respond. After switching to a git branch with a different `manifest.json`, restart Unity.

## Rules

- Model logic does not go into C#. Unity reads export files (contract in [../src/viz/EXPORT.md](../src/viz/EXPORT.md), `schema_version: 1`).
- Large assets (geoportal buildings, full exports) stay out of git; the repo holds only the project, scripts and small samples in `data/processed/unity_samples/`.

## Replay v1: uruchomienie

Odtwarzanie pozycji GPS autobusow (obs) na grafie sieci. Python przygotowuje pliki, Unity tylko je czyta. Katalog `data/` nie jest w gicie, wiec kazdy generuje pliki lokalnie.

1. **Pozycje** (skrypt wymaga `data/raw_A/vehicle_positions`; `--out` to rdzen nazwy bez rozszerzenia; okno 30 min szczytu, 14.10.2026):
   ```
   uv run src/viz/export_unity.py --from 2026-10-14T07:30 --to 2026-10-14T08:00 --out data/processed/unity_samples/obs_peak30
   ```
   Powstaja `obs_peak30.jsonl` i `obs_peak30.meta.json` (537 pojazdow).
2. **Siec** (przystanki i lamane tras; GTFS i linie bierze z meta pozycji, ok. 19 s):
   ```
   uv run export-network --positions data/processed/unity_samples/obs_peak30.meta.json
   ```
   Powstaje `data/processed/unity_samples/network.json` (ok. 0,9 MB).
3. **Kopiowanie** trzech plikow (`network.json`, `obs_peak30.jsonl`, `obs_peak30.meta.json`) do `unity/Assets/StreamingAssets/data/` (katalog jest w `.gitignore`).
4. **Unity:** otworz scene `BusReplay`, Play. Wczytanie ok. 2,6 s; kilka sekund po starcie widac ok. 500 autobusow. Przy brakujacym pliku na ekranie pojawia sie komunikat z oczekiwana sciezka.

Sterowanie kamera: lewy przycisk (przeciaganie) albo WASD = przesuw, kolko = zoom (150–25000 m), prawy przycisk (przeciaganie) = obrot. Klik w autobus otwiera panel z danymi. Nazwy przystankow pojawiaja sie ponizej 1500 m wysokosci kamery. Domyslnie predkosc x10, odtwarzanie w petli; kolor wg opoznienia (zielony -> zolty -> czerwony, niebieski = przed czasem, szary = brak danych).

Testy: Python `uv run pytest`; Unity EditMode przez Window > General > Test Runner albo MCP `run_tests` (27 testow).

