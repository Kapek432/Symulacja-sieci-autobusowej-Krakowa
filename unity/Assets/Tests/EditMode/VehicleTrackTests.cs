using BusReplay.Core;
using NUnit.Framework;
using UnityEngine;

namespace BusReplay.Tests
{
    public class VehicleTrackTests
    {
        static VehicleTrack Track(double[] t, float[] x = null, float[] bearing = null,
                                  string[] route = null, string[] trip = null)
        {
            int n = t.Length;
            x = x ?? new float[n];
            bearing = bearing ?? new float[n];
            route = route ?? new string[n];
            trip = trip ?? new string[n];
            return new VehicleTrack("v", t, x, new float[n], bearing, new float[n],
                                    new bool[n], route, trip);
        }

        static VehicleTrack Std() => Track(
            t: new[] { 0d, 10, 20, 200 }, x: new[] { 0f, 100, 200, 300 },
            bearing: new[] { 350f, 10, 10, 10 },
            route: new[] { "A", "B", "B", "B" }, trip: new[] { "a1", "b1", "b1", "b1" });

        [Test] public void Interpolates_position() => Assert.AreEqual(50f, Std().Sample(5).Pos.x, 1e-3);

        [Test] public void Heading_wraps_through_zero() =>
            Assert.AreEqual(0f, Mathf.DeltaAngle(0, Std().Sample(5).HeadingDeg), 1e-3);

        [Test] public void Hidden_before_after()
        {
            var tr = Std();
            Assert.IsFalse(tr.Sample(-1).Visible);
            Assert.IsFalse(tr.Sample(201).Visible);
        }

        [Test] public void Hidden_in_gap_over_120s() => Assert.IsFalse(Std().Sample(100).Visible);

        [Test] public void Visible_at_last_sample() => Assert.IsTrue(Std().Sample(200).Visible);

        [Test] public void Route_and_trip_from_current_sample()
        {
            var tr = Std();
            Assert.AreEqual("B", tr.Sample(15).RouteId);
            Assert.AreEqual("a1", tr.Sample(5).TripId);
        }

        [Test] public void Delay_from_sample_without_interpolation()
        {
            var tr = new VehicleTrack("v", new[] { 0d, 10 }, new float[2], new float[2], new float[2],
                                      new[] { 0f, 100f }, new bool[2], new string[2], new string[2]);
            Assert.AreEqual(0f, tr.Sample(5).DelayS, 1e-3);
        }

        [Test] public void Duplicate_timestamp_no_nan()
        {
            var d = Track(t: new[] { 0d, 0, 10 }, x: new[] { 0f, 5, 10 });
            var s = d.Sample(0);
            Assert.IsTrue(s.Visible);
            Assert.IsFalse(float.IsNaN(s.Pos.x));
        }
    }
}
