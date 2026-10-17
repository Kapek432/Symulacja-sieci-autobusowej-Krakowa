namespace BusReplay.Core
{
    /// <summary>Blad wczytywania lub walidacji danych odtwarzania.</summary>
    public class ReplayDataException : System.Exception
    {
        public ReplayDataException(string m) : base(m) {}
    }
}
