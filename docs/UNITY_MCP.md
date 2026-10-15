# Unity MCP: konfiguracja

Tor U (patrz [milestones/U_unity_mcp.md](milestones/U_unity_mcp.md)). Symulacja zostaje w Pythonie, Unity tylko odtwarza wyeksportowane wyniki. Agent (Claude Code) steruje edytorem Unity przez serwer MCP.

Używamy **MCP for Unity** (CoplayDev, https://github.com/CoplayDev/unity-mcp), wersja 10.x, obsługuje Unity 2021.3 LTS – 6.x.

## Wymagania

- Unity Hub + Unity 6 LTS (projekt 3D URP)
- `uv` (jest już w projekcie) i Python 3.10+
- Claude Code CLI (`claude` w PATH)

## Kroki

1. **Projekt Unity** w katalogu `unity/` w repo (Unity Hub → New project → 3D (URP) → lokalizacja: katalog główny repo, nazwa `unity`). `Library/`, `Temp/`, `Logs/`, `UserSettings/` są w `.gitignore`.
2. **Pakiet MCP:** Window → Package Manager → `+` → *Add package from git URL*:
   ```
   https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#v10.3.0
   ```
   (wersja przypięta, żeby cały zespół miał to samo; aktualizacja = zmiana tagu tutaj i w `unity/Packages/manifest.json`).
3. **Rejestracja w Claude Code:** w Unity Window → MCP for Unity → *Configure All Detected Clients* (lub przycisk rejestracji przy Claude Code). Okno pokazuje status połączenia.
4. **Sprawdzenie:** w terminalu `claude mcp list` powinno pokazać serwer Unity jako połączony. Smoke-test z Claude Code: „Utwórz w scenie pusty obiekt Bus i kamerę patrzącą na niego”.

Unity musi być otwarte, żeby serwer odpowiadał. Po zmianie gałęzi git z innym `manifest.json` Unity trzeba zrestartować.

## Zasady

- Logika modelu nie trafia do C#. Unity czyta pliki eksportu (kontrakt w U_unity_mcp.md, `schema_version: 1`).
- Duże assety (budynki z geoportalu, pełne eksporty) poza gitem; w repo tylko projekt, skrypty i małe próbki w `data/processed/unity_samples/`.
