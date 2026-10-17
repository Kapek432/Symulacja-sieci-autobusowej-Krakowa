using BusReplay.Core;
using NUnit.Framework;

namespace BusReplay.Tests
{
    public class PlaybackClockTests
    {
        [Test] public void Clock_advances_with_speed()
        {
            var c = new PlaybackClock(0, 1800, 10);
            c.Advance(1f);
            Assert.AreEqual(10d, c.T, 1e-9);
        }

        [Test] public void Clock_wraps()
        {
            var c = new PlaybackClock(0, 1800, 10);
            c.Advance(181f);
            Assert.AreEqual(10d, c.T, 1e-6);
        }

        [Test] public void Local_hms() =>
            Assert.AreEqual("07:30:00", PlaybackClock.LocalHms(1791955800, 27000 - 1791955800d));
    }
}
