using System;
using System.Diagnostics;
using System.IO;
using BusReplay.Core;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace BusReplay
{
    /// <summary>Wczytuje dane, buduje scene i odtwarza pozycje autobusow.</summary>
    public class ReplayApp : MonoBehaviour
    {
        public string networkFile = "network.json";
        public string positionsFile = "obs_peak30.jsonl";
        public float speed = 10f;
        public Material ground, route, stop, bus;

        public NetworkData Network { get; private set; }
        public PositionsData Positions { get; private set; }
        public PlaybackClock Clock { get; private set; }
        public BusFleet Fleet { get; private set; }
        public event Action Loaded;

        void Start()
        {
            try
            {
                var sw = Stopwatch.StartNew();
                string dir = Path.Combine(Application.streamingAssetsPath, "data");
                string netPath = Path.Combine(dir, networkFile);
                string posPath = Path.Combine(dir, positionsFile);
                string metaName = positionsFile.EndsWith(".jsonl", StringComparison.OrdinalIgnoreCase)
                    ? positionsFile.Substring(0, positionsFile.Length - 6) + ".meta.json"
                    : positionsFile + ".meta.json";
                string metaPath = Path.Combine(dir, metaName);

                RequireFile(netPath, networkFile, NetworkCmd);
                RequireFile(posPath, positionsFile, PositionsCmd);
                RequireFile(metaPath, metaName, PositionsCmd);

                Network = NetworkLoader.Parse(File.ReadAllText(netPath));
                var meta = PositionsLoader.ParseMeta(File.ReadAllText(metaPath));
                Positions = PositionsLoader.Parse(File.ReadLines(posPath));

                if (!string.IsNullOrEmpty(meta.Gtfs) && !string.IsNullOrEmpty(Network.Gtfs) && meta.Gtfs != Network.Gtfs)
                    Debug.LogWarning($"Rozne GTFS: siec '{Network.Gtfs}', pozycje '{meta.Gtfs}'");
                if (Positions.SkippedLines > 0)
                    Debug.LogWarning($"Pominieto {Positions.SkippedLines} blednych linii pozycji");

                NetworkRenderer.Build(Network, ground, route, stop);
                Fleet = new GameObject("Fleet").AddComponent<BusFleet>();
                Fleet.Init(Positions, bus);
                Clock = new PlaybackClock(Positions.TMin, Positions.TMax, speed);
                Fleet.Tick(Clock.T);
                sw.Stop();
                Debug.Log($"BusReplay: wczytano {Positions.Tracks.Count} pojazdow w {sw.ElapsedMilliseconds} ms");
            }
            catch (ReplayDataException ex)
            {
                Fail(ex.Message);
                return;
            }
            catch (Exception ex)
            {
                Fail("Blad wczytywania danych: " + ex.Message);
                return;
            }
            var hud = new GameObject("Hud").AddComponent<HudView>();
            hud.Init(this);
            var panel = new GameObject("SelectionPanel").AddComponent<SelectionPanel>();
            panel.Init(this);
            new GameObject("StopLabels").AddComponent<StopLabels>().Init(this, hud, panel);
            Loaded?.Invoke();
        }

        const string NetworkCmd = "uv run export-network --positions data/processed/unity_samples/obs_peak30.meta.json";
        const string PositionsCmd = "uv run src/viz/export_unity.py --from 2026-10-14T07:30 --to 2026-10-14T08:00 --out data/processed/unity_samples/obs_peak30";

        static void RequireFile(string path, string name, string cmd)
        {
            if (File.Exists(path)) return;
            throw new ReplayDataException(
                $"Brak pliku danych: {name}\n(oczekiwano w {path})\n" +
                "Wygeneruj: " + cmd + "\n" +
                "i skopiuj do unity/Assets/StreamingAssets/data/");
        }

        static void Fail(string msg)
        {
            Debug.LogError(msg);
            ErrorOverlay.Show(msg);
        }

        void Update()
        {
            if (Clock == null) return;
            Clock.Advance(Time.deltaTime);
            Fleet.Tick(Clock.T);
        }
    }
}
