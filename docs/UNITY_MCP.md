# Unity MCP: konfiguracja Codex i Claude Code

Tor [U](milestones/U_unity_mcp.md). Symulacja zostaje w Pythonie, Unity odtwarza wyeksportowane dane. Do pracy agenta w edytorze używamy **[MCP for Unity (CoplayDev)](https://github.com/CoplayDev/unity-mcp/tree/v10.3.0)** w wersji **10.3.0**.

**Ten pakiet obsługuje zarówno Codex, jak i Claude Code.** Wersja 10.3.0 zawiera konfigurator Codex zapisujący TOML do `~/.codex/config.toml`. Dotychczasowa instrukcja opisywała tylko Claude Code; nie jest on wymagany do korzystania z MCP w Codex.

## Wymagania

- Unity Hub i **Unity 6000.6.6f1** — wersja projektu jest zapisana w `unity/ProjectSettings/ProjectVersion.txt`.
- `uv`, Python i Git dostępne dla procesu Unity; zależności serwera sprawdza okno konfiguracji pakietu. Po instalacji narzędzi może być potrzebne ponowne otwarcie Unity.
- Jeden klient MCP: aplikacja Codex / Codex CLI albo Claude Code.
- Gałąź zawierająca projekt `unity/` z katalogami `Assets`, `Packages` i `ProjectSettings`. Sam pozostawiony cache `Library/` po zmianie gałęzi nie jest projektem.

## Uruchomienie projektu i serwera

1. Otwórz **istniejący** katalog `unity/` przez Unity Hub (Add project from disk). Nie twórz drugiego projektu. Poczekaj na import pakietów i kompilację.
2. Pakiet jest już zapisany w `unity/Packages/manifest.json`:
   ```text
   https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#v10.3.0
   ```
   Unity pobiera go automatycznie. Jeśli go brakuje, sprawdź gałąź i błędy Package Managera. Aktualizacja pakietu wymaga uzgodnionej zmiany wersji w manifeście i instrukcji.
3. Otwórz **Window → MCP for Unity → Toggle MCP Window**. Wybierz lokalny transport HTTP. Domyślny adres serwera to `http://127.0.0.1:8080`, a endpoint klienta to **`http://127.0.0.1:8080/mcp`**. Jeśli zmieniasz port, zmień go również w konfiguracji klienta.
4. Kliknij **Start Server**, a następnie **Connect**, jeśli edytor nie połączył się automatycznie. Status połączenia edytora powinien wskazywać **Connected**.

Unity musi pozostać otwarte, ale do sprawdzenia sceny przez MCP nie trzeba włączać Play. Sam działający proces serwera HTTP nie potwierdza jeszcze połączenia z edytorem.

## Codex

W oknie MCP wybierz klienta **Codex** i użyj konfiguratora. Alternatywnie dodaj serwer ręcznie, wybierając jedną z metod:

- W ustawieniach aplikacji Codex: **MCP servers → Add server**, nazwa `unityMCP`, transport **Streamable HTTP**, URL `http://127.0.0.1:8080/mcp`.
- W terminalu:
  ```bash
  codex mcp add unityMCP --url http://127.0.0.1:8080/mcp
  ```
- W `~/.codex/config.toml`:
  ```toml
  [mcp_servers.unityMCP]
  url = "http://127.0.0.1:8080/mcp"
  enabled = true
  ```

Jeżeli wpis `unityMCP` już istnieje, popraw go zamiast dodawać kolejny. Konfiguracja jest lokalna dla użytkownika i nie trafia do repozytorium. Po uruchomieniu serwera odśwież połączenie w ustawieniach MCP przyciskiem **Restart**; jeżeli narzędzia nadal nie są dostępne, uruchom ponownie klienta Codex.

`codex mcp list` sprawdza zapis konfiguracji. **Nie zastępuje próby wywołania narzędzia.** Poproś agenta: „Przez Unity MCP wypisz otwarte instancje Unity, wybierz ten projekt i odczytaj nazwę aktywnej sceny oraz obiekty w jej korzeniu. Nie zmieniaj sceny”. Wynik powinien zawierać właściwy projekt i rzeczywistą scenę, np. `BusReplay`, jeśli została otwarta.

Konfiguracja klienta: [oficjalna dokumentacja MCP w Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Sam wpis w TOML nie dowodzi, że bieżąca rozmowa ma już dostęp do narzędzi serwera.

## Claude Code

Użyj konfiguratora klienta **Claude Code** w tym samym oknie Unity MCP. Następnie sprawdź `claude mcp list` i wykonaj taką samą próbę odczytu sceny jak dla Codex. Obaj klienci korzystają z tego samego pakietu w Unity; nie trzeba instalować drugiej kopii pakietu.

## Gdy nie ma połączenia

- **Brak odpowiedzi na porcie 8080:** uruchom lokalny serwer w oknie Unity MCP; sprawdź adres i port. Dodawanie kolejnego wpisu klienta nie uruchamia serwera.
- **Serwer działa, ale nie widać edytora:** sprawdź status **Connected** i przycisk **Connect** w Unity; poczekaj na zakończenie kompilacji i usuń błędy z Console.
- **Codex ma konfigurację, ale agent nie ma narzędzi:** sprawdź, czy serwer jest włączony, i odśwież połączenie po uruchomieniu serwera. Zweryfikuj odczytem sceny, nie samą listą konfiguracji.
- **Zmiana gałęzi lub manifestu:** zamknij Unity przed przełączeniem, potem otwórz projekt ponownie. Jeśli Git blokuje przełączenie z powodu zmiany assetu fontu, najpierw zachowaj zmianę albo świadomie ją odrzuć.

## Unity CLI a Unity MCP

Projekt ma także pakiet `com.unity.pipeline`, używany przez **Unity CLI**. To osobne połączenie. `unity status --format json` sprawdza instancje Pipeline, a nie serwer CoplayDev na porcie 8080. Brak instancji w tym poleceniu nie dowodzi, że Unity MCP nie działa. Unity CLI może służyć do sterowania edytorem i uruchamiania testów niezależnie od konfiguracji MCP klienta.

## Zasady

- Logika modelu pozostaje w Pythonie; kontrakt danych opisuje [EXPORT.md](../src/viz/EXPORT.md), `schema_version: 1`.
- Duże eksporty i cache edytora pozostają lokalne. Wyjątek stanowią trzy pliki demonstracyjne w `unity/Assets/StreamingAssets/data/`, jawnie dopuszczone przez `.gitignore` tej gałęzi.

## Replay v1: uruchomienie

Odtwarzanie pozycji GPS autobusow (obs) na grafie sieci. **Gotowe demo jest w repo:** `network.json`, `obs_peak30.jsonl` i `obs_peak30.meta.json` w `unity/Assets/StreamingAssets/data/`. Do jego uruchomienia wystarczy otworzyc scene `BusReplay` i kliknac Play; MCP nie jest wymagane do recznego ogladania demo.

Ponizsze kroki eksportu sa potrzebne dopiero przy przygotowywaniu wlasnego zestawu danych. Wymagaja lokalnych danych z loggera, ktorych nie ma w repozytorium.

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
3. **Kopiowanie** trzech plikow (`network.json`, `obs_peak30.jsonl`, `obs_peak30.meta.json`) do `unity/Assets/StreamingAssets/data/`. Nadpisanie tych nazw zmienia sledzone pliki demonstracyjne; pozostale eksporty sa ignorowane przez Git.
4. **Unity:** otworz scene `BusReplay`, Play. Wczytanie ok. 2,6 s; kilka sekund po starcie widac ok. 500 autobusow. Przy brakujacym pliku na ekranie pojawia sie komunikat z oczekiwana sciezka.

Sterowanie kamera: lewy przycisk (przeciaganie) albo WASD = przesuw, kolko = zoom (150–25000 m), prawy przycisk (przeciaganie) = obrot. Klik w autobus otwiera panel z danymi. Nazwy przystankow pojawiaja sie ponizej 1500 m wysokosci kamery. Domyslnie predkosc x10, odtwarzanie w petli; kolor wg opoznienia (zielony -> zolty -> czerwony, niebieski = przed czasem, szary = brak danych).

Testy: Python `uv run pytest`; Unity EditMode przez Window > General > Test Runner albo MCP `run_tests`.
