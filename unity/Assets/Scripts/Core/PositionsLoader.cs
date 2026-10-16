using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace BusReplay.Core
{
    /// <summary>Naglowek pliku pozycji.</summary>
    public class PositionsMeta
    {
        public int SchemaVersion;
        public string Gtfs;
        public double TMin;
        public double TMax;
    }

    /// <summary>Wczytane trajektorie wszystkich pojazdow.</summary>
    public class PositionsData
    {
        public Dictionary<string, VehicleTrack> Tracks = new Dictionary<string, VehicleTrack>();
        public double TMin;
        public double TMax;
        /// <summary>sim_time_s - t z pierwszego poprawnego wiersza; zegar lokalny = (T + LocalOffsetS) mod 86400.</summary>
        public double LocalOffsetS;
        public int SkippedLines;
    }

    /// <summary>Parser meta i wierszy JSONL z pozycjami pojazdow.</summary>
    public static class PositionsLoader
    {
        class MetaDto
        {
            [JsonProperty("schema_version")] public int SchemaVersion;
            [JsonProperty("gtfs")] public string Gtfs;
            [JsonProperty("t_min")] public double TMin;
            [JsonProperty("t_max")] public double TMax;
        }

        class RowDto
        {
            [JsonProperty("t")] public double? T;
            [JsonProperty("sim_time_s")] public double? SimTimeS;
            [JsonProperty("vehicle_id")] public string VehicleId;
            [JsonProperty("trip_id")] public string TripId;
            [JsonProperty("route_id")] public string RouteId;
            [JsonProperty("x")] public float? X;
            [JsonProperty("z")] public float? Z;
            [JsonProperty("bearing")] public float? Bearing;
            [JsonProperty("delay_s")] public float? DelayS;
            [JsonProperty("layover")] public bool? Layover;
        }

        /// <summary>Parsuje meta; zla wersja schematu daje ReplayDataException.</summary>
        public static PositionsMeta ParseMeta(string json)
        {
            MetaDto m;
            try { m = JsonConvert.DeserializeObject<MetaDto>(json); }
            catch (JsonException e) { throw new ReplayDataException("positions meta: " + e.Message); }
            if (m == null || m.SchemaVersion != 1)
                throw new ReplayDataException("positions meta: nieobslugiwany schema_version (oczekiwano 1)");
            return new PositionsMeta { SchemaVersion = m.SchemaVersion, Gtfs = m.Gtfs, TMin = m.TMin, TMax = m.TMax };
        }

        // brak kierunku: bierzemy poprzedni znany, a wiodace braki z pierwszego znanego (calosc pusta -> 0)
        static void FillBearings(float[] br)
        {
            int first = -1;
            for (int i = 0; i < br.Length; i++) if (!float.IsNaN(br[i])) { first = i; break; }
            if (first < 0) { Array.Clear(br, 0, br.Length); return; }
            for (int i = 0; i < first; i++) br[i] = br[first];
            for (int i = first + 1; i < br.Length; i++) if (float.IsNaN(br[i])) br[i] = br[i - 1];
        }

        /// <summary>Parsuje wiersze JSONL; bledne wiersze sa liczone w SkippedLines, puste ignorowane.</summary>
        public static PositionsData Parse(IEnumerable<string> lines)
        {
            var data = new PositionsData();
            var groups = new Dictionary<string, List<RowDto>>();
            bool haveOffset = false;
            double tMin = double.PositiveInfinity, tMax = double.NegativeInfinity;

            foreach (var raw in lines)
            {
                if (raw == null) continue;
                var line = raw.Trim().TrimStart('﻿').Trim();
                if (line.Length == 0) continue;

                RowDto r;
                try { r = JsonConvert.DeserializeObject<RowDto>(line); }
                catch (JsonException) { data.SkippedLines++; continue; }
                if (r == null || r.T == null || r.X == null || r.Z == null || string.IsNullOrEmpty(r.VehicleId))
                {
                    data.SkippedLines++;
                    continue;
                }

                if (!haveOffset && r.SimTimeS != null)
                {
                    data.LocalOffsetS = r.SimTimeS.Value - r.T.Value;
                    haveOffset = true;
                }
                if (r.T.Value < tMin) tMin = r.T.Value;
                if (r.T.Value > tMax) tMax = r.T.Value;

                if (!groups.TryGetValue(r.VehicleId, out var list)) groups[r.VehicleId] = list = new List<RowDto>();
                list.Add(r);
            }

            foreach (var kv in groups)
            {
                var rows = kv.Value;
                // sortowanie stabilne po t (Array.Sort nie jest stabilny, wiec remis rozstrzyga indeks)
                var idx = new int[rows.Count];
                for (int i = 0; i < idx.Length; i++) idx[i] = i;
                Array.Sort(idx, (a, b) =>
                {
                    int c = rows[a].T.Value.CompareTo(rows[b].T.Value);
                    return c != 0 ? c : a.CompareTo(b);
                });

                int n = rows.Count;
                var t = new double[n]; var x = new float[n]; var z = new float[n]; var br = new float[n];
                var dl = new float[n]; var lay = new bool[n]; var rt = new string[n]; var tr = new string[n];
                for (int k = 0; k < n; k++)
                {
                    var r = rows[idx[k]];
                    t[k] = r.T.Value; x[k] = r.X.Value; z[k] = r.Z.Value; br[k] = r.Bearing ?? float.NaN;
                    dl[k] = r.DelayS ?? float.NaN; lay[k] = r.Layover ?? false;
                    rt[k] = r.RouteId == null ? null : string.Intern(r.RouteId);
                    tr[k] = r.TripId == null ? null : string.Intern(r.TripId);
                }
                FillBearings(br);
                data.Tracks[kv.Key] = new VehicleTrack(kv.Key, t, x, z, br, dl, lay, rt, tr);
            }

            if (groups.Count > 0) { data.TMin = tMin; data.TMax = tMax; }
            return data;
        }
    }
}
