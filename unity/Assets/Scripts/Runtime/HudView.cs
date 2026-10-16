using BusReplay.Core;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace BusReplay
{
    /// <summary>Zegar i predkosc w lewym gornym rogu, legenda kolorow w lewym dolnym.</summary>
    public class HudView : MonoBehaviour
    {
        ReplayApp app;
        TextMeshProUGUI clockText;

        public static Canvas CreateCanvas(Transform parent, string name, int order)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = order;
            var scaler = go.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            return canvas;
        }

        public static TextMeshProUGUI MakeText(Transform parent, string name, float size, TextAlignmentOptions align)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var t = go.AddComponent<TextMeshProUGUI>();
            t.fontSize = size;
            t.color = Color.white;
            t.alignment = align;
            t.raycastTarget = false;
            return t;
        }

        public void Init(ReplayApp replay)
        {
            app = replay;
            var canvas = CreateCanvas(transform, "HudCanvas", 10);

            clockText = MakeText(canvas.transform, "Clock", 44, TextAlignmentOptions.TopLeft);
            var rt = clockText.rectTransform;
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(20f, -15f);
            rt.sizeDelta = new Vector2(500f, 120f);

            // legenda: wiersze od dolu
            var legend = DelayColors.Legend;
            for (int i = 0; i < legend.Length; i++)
            {
                float y = 20f + (legend.Length - 1 - i) * 34f;
                var sq = new GameObject("Swatch" + i).AddComponent<Image>();
                sq.transform.SetParent(canvas.transform, false);
                sq.color = legend[i].color;
                sq.raycastTarget = false;
                var srt = sq.rectTransform;
                srt.anchorMin = srt.anchorMax = srt.pivot = Vector2.zero;
                srt.anchoredPosition = new Vector2(20f, y);
                srt.sizeDelta = new Vector2(26f, 26f);

                var label = MakeText(canvas.transform, "Label" + i, 24, TextAlignmentOptions.MidlineLeft);
                var lrt = label.rectTransform;
                lrt.anchorMin = lrt.anchorMax = lrt.pivot = Vector2.zero;
                lrt.anchoredPosition = new Vector2(56f, y - 2f);
                lrt.sizeDelta = new Vector2(420f, 30f);
                label.text = legend[i].label;
            }
        }

        void Update()
        {
            if (app == null || app.Clock == null) return;
            string hms = PlaybackClock.LocalHms(app.Clock.T, app.Positions.LocalOffsetS);
            clockText.text = hms + "\n<size=60%>×" + app.Clock.Speed.ToString("0.##");
        }
    }
}
