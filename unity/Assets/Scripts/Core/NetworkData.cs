using UnityEngine;

namespace BusReplay.Core
{
    /// <summary>Przystanek sieci (Pos.x = x, Pos.y = z).</summary>
    public class NetworkStop
    {
        public string StopId;
        public string Name;
        public Vector2 Pos;
    }

    /// <summary>Odcinek sieci miedzy dwoma przystankami z lamana (x, z).</summary>
    public class NetworkSegment
    {
        public string FromStop;
        public string ToStop;
        public string[] Routes;
        public Vector2[] Points;
    }

    /// <summary>Wczytana siec: przystanki, odcinki i obwiednia.</summary>
    public class NetworkData
    {
        public string Gtfs;
        public NetworkStop[] Stops;
        public NetworkSegment[] Segments;
        public Rect Bbox;
    }
}
