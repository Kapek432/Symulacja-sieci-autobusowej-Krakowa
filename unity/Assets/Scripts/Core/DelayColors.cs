using UnityEngine;

namespace BusReplay.Core
{
    /// <summary>Mapowanie opoznienia (s) na kolor autobusu.</summary>
    public static class DelayColors
    {
        public static readonly Color Green = new Color(0.20f, 0.75f, 0.30f);
        public static readonly Color Yellow = new Color(0.95f, 0.80f, 0.15f);
        public static readonly Color Red = new Color(0.85f, 0.15f, 0.15f);
        public static readonly Color Blue = new Color(0.25f, 0.50f, 0.95f);
        public static readonly Color Grey = new Color(0.55f, 0.55f, 0.55f);

        public static readonly (string label, Color color)[] Legend =
        {
            ("przed czasem (< -1 min)", Blue),
            ("do 1 min", Green),
            ("3 min", Yellow),
            ("5 min i wi\u0119cej", Red),
            ("post\u00f3j / brak danych", Grey),
        };

        /// <summary>Kolor dla opoznienia; postoj na petli lub brak danych (NaN) daje szary.</summary>
        public static Color For(float delayS, bool layover)
        {
            if (layover || float.IsNaN(delayS)) return Grey;
            if (delayS < -60f) return Blue;
            if (delayS <= 60f) return Green;
            if (delayS < 180f) return Color.Lerp(Green, Yellow, (delayS - 60f) / 120f);
            if (delayS < 300f) return Color.Lerp(Yellow, Red, (delayS - 180f) / 120f);
            return Red;
        }
    }
}
