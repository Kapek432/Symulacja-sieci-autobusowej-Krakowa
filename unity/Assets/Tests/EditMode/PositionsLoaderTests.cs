using BusReplay.Core;
using NUnit.Framework;

namespace BusReplay.Tests
{
    public class PositionsLoaderTests
    {
        const string Row1 = "{\"t\":100,\"sim_time_s\":27000,\"vehicle_id\":\"v1\",\"trip_id\":\"a\",\"route_id\":\"179\",\"x\":1,\"z\":2,\"bearing\":90,\"delay_s\":null,\"layover\":true,\"extra\":1}";
        const string Row2 = "{\"t\":110,\"sim_time_s\":27010,\"vehicle_id\":\"v1\",\"trip_id\":\"a\",\"route_id\":\"179\",\"x\":11,\"z\":2,\"bearing\":90,\"delay_s\":30,\"layover\":false}";

        static PositionsData Parse(params string[] lines) => PositionsLoader.Parse(lines);

        [Test] public void Null_delay_is_nan_and_layover()
        {
            var s = Parse(Row1, Row2).Tracks["v1"].Sample(100);
            Assert.IsTrue(float.IsNaN(s.DelayS));
            Assert.IsTrue(s.Layover);
        }

        [Test] public void Groups_and_sorts_by_t()
        {
            var p = Parse(Row2, Row1);
            var s = p.Tracks["v1"].Sample(105);
            Assert.IsTrue(s.Visible);
            Assert.AreEqual(6f, s.Pos.x, 1e-3);
            Assert.AreEqual(100d, p.TMin);
            Assert.AreEqual(110d, p.TMax);
        }

        [Test] public void Bad_line_counted() => Assert.AreEqual(1, Parse(Row1, "{oops", Row2).SkippedLines);

        [Test] public void Crlf_bom_and_blank_ignored() =>
            Assert.AreEqual(0, Parse("\uFEFF" + Row1 + "\r", Row2, "").SkippedLines);

        [Test] public void Local_offset_from_sim_time() => Assert.AreEqual(26900d, Parse(Row1).LocalOffsetS);

        [Test] public void Meta_wrong_version_throws() =>
            Assert.Throws<ReplayDataException>(() => PositionsLoader.ParseMeta("{\"schema_version\":2}"));

        [Test] public void Meta_parses() 
        {
            var m = PositionsLoader.ParseMeta("{\"schema_version\":1,\"gtfs\":\"g.zip\",\"t_min\":5,\"t_max\":9,\"rows\":3}");
            Assert.AreEqual("g.zip", m.Gtfs);
            Assert.AreEqual(5d, m.TMin);
            Assert.AreEqual(9d, m.TMax);
        }
    }
}
