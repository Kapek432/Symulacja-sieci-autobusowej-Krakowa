using NUnit.Framework;

namespace BusReplay.Tests
{
    public class SelectionPanelTests
    {
        [Test]
        public void Format_delay()
        {
            Assert.AreEqual("+3 min 12 s", SelectionPanel.FormatDelay(192f));
            Assert.AreEqual("-1 min 05 s", SelectionPanel.FormatDelay(-65f));
            Assert.AreEqual("—", SelectionPanel.FormatDelay(float.NaN));
        }
    }
}
