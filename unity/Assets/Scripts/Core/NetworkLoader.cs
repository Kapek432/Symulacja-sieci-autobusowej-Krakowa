using System.Collections.Generic;
using Newtonsoft.Json;
using UnityEngine;

namespace BusReplay.Core
{
    /// <summary>Parser pliku network.json.</summary>
    public static class NetworkLoader
    {
        class BboxDto
        {
            [JsonProperty("x_min")] public float XMin;
            [JsonProperty("x_max")] public float XMax;
            [JsonProperty("z_min")] public float ZMin;
            [JsonProperty("z_max")] public float ZMax;
        }
        class MetaDto
        {
            [JsonProperty("schema_version")] public int SchemaVersion;
            [JsonProperty("gtfs")] public string Gtfs;
            [JsonProperty("bbox")] public BboxDto Bbox;
        }
        class StopDto
        {
            [JsonProperty("stop_id")] public string StopId;
            [JsonProperty("name")] public string Name;
            [JsonProperty("x")] public float X;
            [JsonProperty("z")] public float Z;
        }
        class SegDto
        {
            [JsonProperty("from_stop")] public string From;
            [JsonProperty("to_stop")] public string To;
            [JsonProperty("routes")] public string[] Routes;
            [JsonProperty("points")] public float[] Points;
        }
        class RootDto
        {
            [JsonProperty("meta")] public MetaDto Meta;
            [JsonProperty("stops")] public List<StopDto> Stops;
            [JsonProperty("segments")] public List<SegDto> Segments;
        }

        /// <summary>Parsuje JSON sieci; zla wersja schematu daje ReplayDataException.</summary>
        public static NetworkData Parse(string json)
        {
            RootDto root;
            try { root = JsonConvert.DeserializeObject<RootDto>(json); }
            catch (JsonException e) { throw new ReplayDataException("network.json: " + e.Message); }
            if (root == null || root.Meta == null || root.Meta.SchemaVersion != 1)
                throw new ReplayDataException("network.json: nieobslugiwany schema_version (oczekiwano 1)");

            var data = new NetworkData { Gtfs = root.Meta.Gtfs };
            var b = root.Meta.Bbox;
            if (b != null) data.Bbox = new Rect(b.XMin, b.ZMin, b.XMax - b.XMin, b.ZMax - b.ZMin);

            var stops = root.Stops ?? new List<StopDto>();
            data.Stops = new NetworkStop[stops.Count];
            for (int i = 0; i < stops.Count; i++)
                data.Stops[i] = new NetworkStop
                {
                    StopId = stops[i].StopId,
                    Name = stops[i].Name,
                    Pos = new Vector2(stops[i].X, stops[i].Z)
                };

            var segs = root.Segments ?? new List<SegDto>();
            data.Segments = new NetworkSegment[segs.Count];
            for (int i = 0; i < segs.Count; i++)
            {
                var flat = segs[i].Points ?? new float[0];
                var pts = new Vector2[flat.Length / 2];
                for (int k = 0; k < pts.Length; k++) pts[k] = new Vector2(flat[2 * k], flat[2 * k + 1]);
                data.Segments[i] = new NetworkSegment
                {
                    FromStop = segs[i].From,
                    ToStop = segs[i].To,
                    Routes = segs[i].Routes ?? new string[0],
                    Points = pts
                };
            }
            return data;
        }
    }
}
