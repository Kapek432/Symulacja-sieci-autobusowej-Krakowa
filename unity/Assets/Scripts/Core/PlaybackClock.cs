using System;
using System.Globalization;

namespace BusReplay.Core
{
    /// <summary>Zegar odtwarzania z zapetlaniem w zakresie [tMin, tMax].</summary>
    public class PlaybackClock
    {
        readonly double _tMin;
        readonly double _tMax;

        public double T { get; private set; }
        public float Speed { get; set; }

        public PlaybackClock(double tMin, double tMax, float speed = 10f)
        {
            _tMin = tMin;
            _tMax = tMax;
            Speed = speed;
            T = tMin;
        }

        /// <summary>Przesuwa czas o dtReal * Speed; po przekroczeniu tMax zawija do tMin + nadmiar.</summary>
        public void Advance(float dtReal)
        {
            T += dtReal * (double)Speed;
            double span = _tMax - _tMin;
            if (span > 0 && T > _tMax)
                T = _tMin + (T - _tMin) % span;
        }

        /// <summary>Czas lokalny HH:MM:SS dla czasu epoch t i przesuniecia lokalnego (s).</summary>
        public static string LocalHms(double t, double localOffsetS)
        {
            double s = (t + localOffsetS) % 86400.0;
            if (s < 0) s += 86400.0;
            int sec = (int)Math.Floor(s);
            return string.Format(CultureInfo.InvariantCulture, "{0:00}:{1:00}:{2:00}",
                sec / 3600, sec / 60 % 60, sec % 60);
        }
    }
}
