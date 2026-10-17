using NUnit.Framework;

namespace BusReplay.Tests
{
    public class CameraRigTests
    {
        [Test] public void Notch_up_zooms_in_10_percent() => Assert.AreEqual(900f, CameraRig.ZoomHeight(1000f, 1f), 1e-2);
        [Test] public void Notch_down_zooms_out() => Assert.AreEqual(1000f / 0.9f, CameraRig.ZoomHeight(1000f, -1f), 1e-2);
        [Test] public void Legacy_120_scale_same_as_1() => Assert.AreEqual(CameraRig.ZoomHeight(1000f, 1f), CameraRig.ZoomHeight(1000f, 120f), 1e-3);
        [Test] public void Clamped()
        {
            Assert.AreEqual(CameraRig.MinHeight, CameraRig.ZoomHeight(151f, 1f));
            Assert.AreEqual(CameraRig.MaxHeight, CameraRig.ZoomHeight(24999f, -1f));
        }
    }
}
