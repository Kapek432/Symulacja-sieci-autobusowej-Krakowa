using BusReplay.Core;
using NUnit.Framework;
using UnityEngine;

namespace BusReplay.Tests
{
    public class NetworkLoaderTests
    {
        [Test] public void Parses_stops_segments_points()
        {
            const string json = "{\"meta\":{\"schema_version\":1,\"gtfs\":\"g.zip\",\"bbox\":{\"x_min\":-10,\"x_max\":10,\"z_min\":-20,\"z_max\":20},\"unknown\":5}," +
                "\"stops\":[{\"stop_id\":\"s1\",\"name\":\"Rynek\",\"x\":1.5,\"z\":2.5}]," +
                "\"segments\":[{\"from_stop\":\"s1\",\"to_stop\":\"s2\",\"routes\":[\"169\",\"179\"],\"points\":[0,0,3,4]}]}";
            var n = NetworkLoader.Parse(json);
            Assert.AreEqual("g.zip", n.Gtfs);
            Assert.AreEqual(1, n.Stops.Length);
            Assert.AreEqual(new Vector2(1.5f, 2.5f), n.Stops[0].Pos);
            Assert.AreEqual(1, n.Segments.Length);
            Assert.AreEqual(2, n.Segments[0].Points.Length);
            Assert.AreEqual(new Vector2(3, 4), n.Segments[0].Points[1]);
            Assert.AreEqual(new[] { "169", "179" }, n.Segments[0].Routes);
            Assert.AreEqual(-10f, n.Bbox.xMin, 1e-3);
            Assert.AreEqual(20f, n.Bbox.width, 1e-3);
            Assert.AreEqual(40f, n.Bbox.height, 1e-3);
        }

        [Test] public void Wrong_schema_throws() =>
            Assert.Throws<ReplayDataException>(() => NetworkLoader.Parse("{\"meta\":{\"schema_version\":2}}"));
    }
}
