using System.Collections.Generic;
using BusReplay.Core;
using UnityEngine;

namespace BusReplay
{
    /// <summary>Tworzy widoki wszystkich pojazdow i odswieza je co klatke.</summary>
    public class BusFleet : MonoBehaviour
    {
        readonly Dictionary<string, BusView> views = new Dictionary<string, BusView>();
        readonly List<(VehicleTrack track, BusView view)> items = new List<(VehicleTrack, BusView)>();

        public IReadOnlyDictionary<string, BusView> Views => views;
        public int VisibleCount { get; private set; }

        public void Init(PositionsData data, Material bus)
        {
            foreach (var kv in data.Tracks)
            {
                var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                go.name = "Bus " + kv.Key;
                go.transform.SetParent(transform, false);
                go.transform.localScale = BusView.DefaultScale;
                go.GetComponent<Renderer>().sharedMaterial = bus;
                var view = go.AddComponent<BusView>();
                view.VehicleId = kv.Key;
                go.SetActive(false);
                views[kv.Key] = view;
                items.Add((kv.Value, view));
            }
        }

        public void Tick(double T)
        {
            int n = 0;
            foreach (var (track, view) in items)
            {
                var s = track.Sample(T);
                view.Apply(s);
                if (s.Visible) n++;
            }
            VisibleCount = n;
        }
    }
}
