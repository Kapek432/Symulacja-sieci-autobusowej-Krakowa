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
        const float DuplicateRadiusM = 150f;
        const float RectMarginPx = 60f;

        ReplayApp app;
        HudView hud;
        SelectionPanel selection;
        readonly List<TextMeshPro> pool = new List<TextMeshPro>();
        readonly NetworkStop[] assigned = new NetworkStop[PoolSize];
        readonly float[] assignedHeight = new float[PoolSize];
        readonly List<(float d, NetworkStop stop)> candidates = new List<(float, NetworkStop)>();
        readonly List<Rect> blocked = new List<Rect>();
        float nextRefresh;

        public void Init(ReplayApp replay, HudView hudView, SelectionPanel panel)
        {
            app = replay;
            hud = hudView;
            selection = panel;
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

        bool IsBlocked(Vector3 viewport)
        {
            var p = new Vector2(viewport.x * Screen.width, viewport.y * Screen.height);
            foreach (var r in blocked)
            {
                var e = Rect.MinMaxRect(r.xMin - RectMarginPx, r.yMin - RectMarginPx,
                                        r.xMax + RectMarginPx, r.yMax + RectMarginPx);
                if (e.Contains(p)) return true;
            }
            return false;
        }

        void Refresh(Camera cam, float h)
        {
            blocked.Clear();
            if (hud != null) hud.GetScreenRects(blocked);
            if (selection != null) selection.GetScreenRects(blocked);

            candidates.Clear();
            foreach (var st in app.Network.Stops)
            {
                Vector3 v = cam.WorldToViewportPoint(new Vector3(st.Pos.x, 0f, st.Pos.y));
                if (v.z <= 0f || v.x < 0f || v.x > 1f || v.y < 0f || v.y > 1f) continue;
                if (IsBlocked(v)) continue;
                float dx = v.x - 0.5f, dy = v.y - 0.5f;
                candidates.Add((dx * dx + dy * dy, st));
            }
            candidates.Sort((a, b) => a.d.CompareTo(b.d));

            // fontSize w TMP 3D to ok. 0,1 m na punkt; dobrane tak, by tekst byl czytelny
            float size = h * 0.4f;
            int used = 0;
            for (int c = 0; c < candidates.Count && used < PoolSize; c++)
            {
                var st = candidates[c].stop;
                if (IsDuplicate(st, used)) continue;
                var t = pool[used];
                bool changed = assigned[used] != st ||
                               Mathf.Abs(assignedHeight[used] - h) > 0.05f * h;
                if (changed)
                {
                    t.text = st.Name;
                    t.fontSize = size;
                    assigned[used] = st;
                    assignedHeight[used] = h;
                }
                t.transform.position = new Vector3(st.Pos.x, 12f + size * 0.05f, st.Pos.y);
                t.transform.rotation = cam.transform.rotation;
                if (!t.gameObject.activeSelf) t.gameObject.SetActive(true);
                used++;
            }
            for (int i = used; i < pool.Count; i++)
                if (pool[i].gameObject.activeSelf) pool[i].gameObject.SetActive(false);
        }

        // przystanek o tej samej nazwie wybrany juz w promieniu DuplicateRadiusM
        bool IsDuplicate(NetworkStop st, int used)
        {
            for (int i = 0; i < used; i++)
            {
                var o = assigned[i];
                if (o.Name == st.Name && (o.Pos - st.Pos).sqrMagnitude < DuplicateRadiusM * DuplicateRadiusM)
                    return true;
            }
            return false;
        }
    }
}
