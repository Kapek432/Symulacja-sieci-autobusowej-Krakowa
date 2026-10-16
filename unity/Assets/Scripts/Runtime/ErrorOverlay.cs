using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace BusReplay
{
    /// <summary>Wyswietla komunikat bledu na srodku ekranu.</summary>
    public static class ErrorOverlay
    {
        public static void Show(string msg)
        {
            var go = new GameObject("ErrorOverlay");
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 1000;
            go.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;

            var textGo = new GameObject("Text");
            textGo.transform.SetParent(go.transform, false);
            var tmp = textGo.AddComponent<TextMeshProUGUI>();
            tmp.text = msg;
            tmp.color = new Color(1f, 0.2f, 0.2f);
            tmp.fontSize = 28;
            tmp.alignment = TextAlignmentOptions.Center;
            var rt = tmp.rectTransform;
            rt.anchorMin = new Vector2(0.1f, 0.1f);
            rt.anchorMax = new Vector2(0.9f, 0.9f);
            rt.offsetMin = rt.offsetMax = Vector2.zero;
        }
    }
}
