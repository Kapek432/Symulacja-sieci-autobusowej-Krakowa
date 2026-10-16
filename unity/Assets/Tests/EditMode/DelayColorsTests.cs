using BusReplay.Core;
using NUnit.Framework;
using UnityEngine;

namespace BusReplay.Tests
{
    public class DelayColorsTests
    {
        static void AreClose(Color expected, Color actual)
        {
            Assert.AreEqual(expected.r, actual.r, 1e-3f);
            Assert.AreEqual(expected.g, actual.g, 1e-3f);
            Assert.AreEqual(expected.b, actual.b, 1e-3f);
        }

        [Test] public void Thresholds()
        {
            AreClose(DelayColors.Green, DelayColors.For(30, false));
            AreClose(DelayColors.Yellow, DelayColors.For(180, false));
            AreClose(DelayColors.Red, DelayColors.For(400, false));
            AreClose(DelayColors.Blue, DelayColors.For(-120, false));
        }

        [Test] public void Between_green_and_yellow_is_blend()
        {
            var c = DelayColors.For(120, false);
            Assert.That(c.r, Is.InRange(DelayColors.Green.r, DelayColors.Yellow.r));
            Assert.That(c.r, Is.Not.EqualTo(DelayColors.Green.r).Within(1e-3f));
        }

        [Test] public void Layover_and_nan_are_grey()
        {
            AreClose(DelayColors.Grey, DelayColors.For(500, true));
            AreClose(DelayColors.Grey, DelayColors.For(float.NaN, false));
        }

        [Test] public void Legend_has_grey_entry()
        {
            Assert.That(DelayColors.Legend.Length, Is.GreaterThanOrEqualTo(5));
            AreClose(DelayColors.Grey, DelayColors.Legend[DelayColors.Legend.Length - 1].color);
        }
    }
}
