using NUnit.Framework;

namespace BusReplay.Tests
{
    /// <summary>Testy dymne: sprawdzaja, ze assembly sa poprawnie powiazane.</summary>
    public class SmokeTests
    {
        [Test]
        public void Core_assembly_loads()
        {
            Assert.AreEqual("BusReplay.Core", typeof(BusReplay.Core.ReplayDataException).Assembly.GetName().Name);
        }
    }
}
