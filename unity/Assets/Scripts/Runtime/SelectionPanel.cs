using System.Collections.Generic;
using System.Globalization;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace BusReplay
{
    /// <summary>Klik w autobus: podswietlenie i panel z informacjami w prawym gornym rogu.</summary>
    public class SelectionPanel : MonoBehaviour
    {
        public const float DragThresholdPx = 5f;

        ReplayApp app;
        BusView selected;
        GameObject panel;
        TextMeshProUGUI body;
        Vector2 pressPos;
        bool pressed;
        float nextRefresh;
        RectTransform panelRt;
        readonly Vector3[] corners = new Vector3[4];

        public BusView Selected => selected;

        /// <summary>Opoznienie jako "+3 min 12 s" / "-1 min 05 s"; NaN daje pauze.</summary>
        public static string FormatDelay(float delayS)
        {
            if (float.IsNaN(delayS)) return "\u2014";
            int total = Mathf.RoundToInt(Mathf.Abs(delayS));
            string sign = delayS < 0f && total > 0 ? "-" : "+";
            return string.Format(CultureInfo.InvariantCulture, "{0}{1} min {2:00} s", sign, total / 60, total % 60);
        }

        public void Init(ReplayApp replay)
        {
            app = replay;
            var canvas = HudView.CreateCanvas(transform, "SelectionCanvas", 11);
            panel = new GameObject("Panel");
            panel.transform.SetParent(canvas.transform, false);
            var bg = panel.AddComponent<Image>();
            bg.color = new Color(0f, 0f, 0f, 0.9f);
            bg.raycastTarget = false;
            var rt = panelRt = bg.rectTransform;
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(1f, 1f);
            rt.anchoredPosition = new Vector2(-20f, -20f);
            rt.sizeDelta = new Vector2(620f, 220f);

            body = HudView.MakeText(panel.transform, "Body", 28, TextAlignmentOptions.TopLeft);
            var brt = body.rectTransform;
            brt.anchorMin = Vector2.zero;
            brt.anchorMax = Vector2.one;
            brt.offsetMin = new Vector2(16f, 12f);
            brt.offsetMax = new Vector2(-16f, -12f);
            panel.SetActive(false);
        }

        /// <summary>Zaznacza autobus (null zamyka panel).</summary>
        public void Select(BusView view)
        {
            if (selected != null && selected != view) selected.SetHighlighted(false);
            selected = view;
            if (view == null)
            {
                panel.SetActive(false);
                return;
            }
            view.SetHighlighted(true);
            panel.SetActive(true);
            Refresh();
        }

        void Update()
        {
            HandleClick();
            if (selected == null) return;
            if (!selected.Current.Visible) { Select(null); return; }
            if (Time.unscaledTime >= nextRefresh) Refresh();
        }

        void HandleClick()
        {
            var mouse = Mouse.current;
            var cam = Camera.main;
            if (mouse == null || cam == null) return;
            if (mouse.leftButton.wasPressedThisFrame)
            {
                pressPos = mouse.position.ReadValue();
                pressed = true;
                if (selected != null && panelRt != null)
                {
                    panelRt.GetWorldCorners(corners);
                    if (Rect.MinMaxRect(corners[0].x, corners[0].y, corners[2].x, corners[2].y).Contains(pressPos))
                        pressed = false;
                }
            }
            if (mouse.leftButton.wasReleasedThisFrame && pressed)
            {
                pressed = false;
                Vector2 pos = mouse.position.ReadValue();
                if ((pos - pressPos).magnitude >= DragThresholdPx) return;
                BusView hit = null;
                if (Physics.Raycast(cam.ScreenPointToRay(pressPos), out var info))
                    hit = info.collider.GetComponent<BusView>();
                Select(hit);
            }
        }

        /// <summary>Dopisuje prostokat panelu (piksele ekranu), gdy panel jest widoczny.</summary>
        public void GetScreenRects(List<Rect> into)
        {
            if (selected == null || panelRt == null) return;
            panelRt.GetWorldCorners(corners);
            into.Add(Rect.MinMaxRect(corners[0].x, corners[0].y, corners[2].x, corners[2].y));
        }

        void Refresh()
        {
            nextRefresh = Time.unscaledTime + 0.1f;
            var s = selected.Current;
            body.text =
                "Linia: " + s.RouteId +
                "\nKurs: " + s.TripId +
                "\nPojazd: " + selected.VehicleId +
                "\nOp\u00f3\u017anienie: " + FormatDelay(s.DelayS) +
                "\nNa p\u0119tli: " + (s.Layover ? "tak" : "nie");
        }
    }
}
