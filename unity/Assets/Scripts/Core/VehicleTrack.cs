using UnityEngine;

namespace BusReplay.Core
{
    /// <summary>Probka trajektorii pojazdu w danej chwili.</summary>
    public struct TrackSample
    {
        public bool Visible;
        public Vector2 Pos;
        public float HeadingDeg;
        public float DelayS;   // NaN gdy brak opoznienia
        public bool Layover;
        public string RouteId;
        public string TripId;
    }

    /// <summary>Trajektoria jednego pojazdu: probki posortowane po czasie t.</summary>
    public class VehicleTrack
    {
        public const double MaxGapS = 120;

        public string VehicleId { get; }
        readonly double[] _t;
        readonly float[] _x, _z, _bearing, _delay;
        readonly bool[] _layover;
        readonly string[] _route, _trip;

        public VehicleTrack(string vehicleId, double[] t, float[] x, float[] z, float[] bearing,
                            float[] delay, bool[] layover, string[] routeId, string[] tripId)
        {
            VehicleId = vehicleId; _t = t; _x = x; _z = z; _bearing = bearing;
            _delay = delay; _layover = layover; _route = routeId; _trip = tripId;
        }

        /// <summary>Probkuje trajektorie w chwili T (interpolacja liniowa, luka powyzej MaxGapS ukrywa).</summary>
        public TrackSample Sample(double T)
        {
            int n = _t.Length;
            if (n == 0 || T < _t[0] || T > _t[n - 1]) return default;

            // ostatni indeks i z t[i] <= T (przy duplikatach wybiera ostatni, wiec brak dzielenia przez 0)
            int lo = 0, hi = n - 1;
            while (lo < hi)
            {
                int mid = (lo + hi + 1) >> 1;
                if (_t[mid] <= T) lo = mid; else hi = mid - 1;
            }
            int i = lo;

            if (i == n - 1) return Make(i, i, 0f);
            double gap = _t[i + 1] - _t[i];
            if (gap > MaxGapS) return default;
            return Make(i, i + 1, (float)((T - _t[i]) / gap));
        }

        TrackSample Make(int a, int b, float f)
        {
            return new TrackSample
            {
                Visible = true,
                Pos = new Vector2(Mathf.Lerp(_x[a], _x[b], f), Mathf.Lerp(_z[a], _z[b], f)),
                HeadingDeg = Mathf.LerpAngle(_bearing[a], _bearing[b], f),
                DelayS = _delay[a],  // z probki a, bez interpolacji
                Layover = _layover[a],
                RouteId = _route[a],
                TripId = _trip[a],
            };
        }
    }
}
