using System.Collections.Generic;
using BusReplay.Core;
using TMPro;
using UnityEngine;

namespace BusReplay
{
    /// <summary>Pula 40 etykiet z nazwami przystankow widocznych w kadrze przy malej wysokosci kamery.</summary>
    public class StopLabels : MonoBehaviour
    {
        public const int PoolSize = 40;
        public const float MaxHeight = 1500f;
        public const float Interval = 0.25f;

        ReplayApp app;
        readonly List<TextMeshPro> pool = new List<TextMeshPro>();
        readonly List<(float d, NetworkStop stop)> candidates = new List<(float, NetworkStop)>();
        float nextRefresh;

        public void Init(ReplayApp replay)
        {
            app = replay;
            for (int i = 0; i < PoolSize; i++)
            {
                var go = new GameObject("StopLabel" + i);
                go.transform.SetParent(transform, false);
                var t = go.AddComponent<TextMeshPro>();
                t.alignment = TextAlignmentOptions.Center;
                t.color = Color.white;
                t.textWrappingMode = TextWrappingModes.NoWrap;
                go.SetActive(false);
                pool.Add(t);
            }
        }

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null || app == null || app.Network == null) return;
            float h = cam.transform.position.y;
            if (h >= MaxHeight)
            {
                foreach (var t in pool) if (t.gameObject.activeSelf) t.gameObject.SetActive(false);
                nextRefresh = 0f;
                return;
            }
            if (Time.unscaledTime >= nextRefresh)
            {
                nextRefresh = Time.unscaledTime + Interval;
                Refresh(cam, h);
            }
            // obrot do kamery co klatke
            foreach (var t in pool)
                if (t.gameObject.activeSelf) t.transform.rotation = cam.transform.rotation;
        }

        void Refresh(Camera cam, float h)
        {
            candidates.Clear();
            foreach (var st in app.Network.Stops)
            {
                Vector3 v = cam.WorldToViewportPoint(new Vector3(st.Pos.x, 0f, st.Pos.y));
                if (v.z <= 0f || v.x < 0f || v.x > 1f || v.y < 0f || v.y > 1f) continue;
                float dx = v.x - 0.5f, dy = v.y - 0.5f;
                candidates.Add((dx * dx + dy * dy, st));
            }
            candidates.Sort((a, b) => a.d.CompareTo(b.d));
            // fontSize w TMP 3D to ok. 0,1 m na punkt; dobrane tak, by tekst byl czytelny
            float size = h * 0.4f;
            for (int i = 0; i < pool.Count; i++)
            {
                var t = pool[i];
                if (i >= candidates.Count)
                {
                    if (t.gameObject.activeSelf) t.gameObject.SetActive(false);
                    continue;
                }
                var st = candidates[i].stop;
                t.text = st.Name;
                t.fontSize = size;
                t.transform.position = new Vector3(st.Pos.x, 12f + size * 0.05f, st.Pos.y);
                t.transform.rotation = cam.transform.rotation;
                if (!t.gameObject.activeSelf) t.gameObject.SetActive(true);
            }
        }
    }
}
