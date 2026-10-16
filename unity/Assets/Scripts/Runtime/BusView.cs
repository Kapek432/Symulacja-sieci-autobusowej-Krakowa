using BusReplay.Core;
using UnityEngine;

namespace BusReplay
{
    /// <summary>Widok jednego autobusu: pozycja, obrot, kolor opoznienia.</summary>
    public class BusView : MonoBehaviour
    {
        public const float BusY = 4.5f;
        public static readonly Vector3 DefaultScale = new Vector3(7.5f, 9f, 36f);
        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");

        public string VehicleId;
        [System.NonSerialized] public TrackSample Current;

        Renderer rend;
        MaterialPropertyBlock block;
        Color color = Color.white;
        bool highlighted;
        float zoomScale = 1f;

        void EnsureInit()
        {
            if (rend == null) rend = GetComponent<Renderer>();
            if (block == null) block = new MaterialPropertyBlock();
        }

        public void Apply(TrackSample s)
        {
            EnsureInit();
            Current = s;
            if (gameObject.activeSelf != s.Visible) gameObject.SetActive(s.Visible);
            if (!s.Visible) return;
            transform.position = new Vector3(s.Pos.x, BusY, s.Pos.y);
            transform.rotation = Quaternion.Euler(0f, s.HeadingDeg, 0f);
            color = DelayColors.For(s.DelayS, s.Layover);
            PushColor();
        }

        public void SetHighlighted(bool on)
        {
            EnsureInit();
            highlighted = on;
            UpdateScale();
            PushColor();
        }

        /// <summary>Skala zalezna od wysokosci kamery (>= 1).</summary>
        public void SetZoomScale(float s)
        {
            if (Mathf.Approximately(s, zoomScale)) return;
            zoomScale = s;
            UpdateScale();
        }

        void UpdateScale()
        {
            transform.localScale = DefaultScale * zoomScale * (highlighted ? 1.3f : 1f);
        }

        void PushColor()
        {
            Color c = highlighted ? Color.Lerp(color, Color.white, 0.5f) : color;
            rend.GetPropertyBlock(block);
            block.SetColor(BaseColorId, c);
            rend.SetPropertyBlock(block);
        }
    }
}
