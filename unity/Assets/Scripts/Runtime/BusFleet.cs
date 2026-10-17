using System.Collections.Generic;
using BusReplay.Core;
using UnityEngine;

namespace BusReplay
{
    /// <summary>Tworzy widoki wszystkich pojazdow i odswieza je co klatke.</summary>
    public class BusFleet : MonoBehaviour
    {
        public const float ScaleRefHeight = 1500f;

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
            var cam = Camera.main;
            float zs = cam != null ? Mathf.Max(1f, cam.transform.position.y / ScaleRefHeight) : 1f;
            foreach (var (track, view) in items)
            {
                view.SetZoomScale(zs);
                var s = track.Sample(T);
                view.Apply(s);
                if (s.Visible) n++;
            }
            VisibleCount = n;
        }
    }
}
