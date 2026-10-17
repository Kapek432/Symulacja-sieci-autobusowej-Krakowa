"""geo.py: wspolny uklad wspolrzednych dla eksportu i wizualizacji.

Wspolrzedne lokalne w metrach wzgledem ORIGIN (Rynek Glowny):
x na wschod, z na polnoc. Rzut equirectangular, dokladny w skali miasta.
"""

import numpy as np
from numpy.typing import ArrayLike

# poczatek lokalnego ukladu Unity: Rynek Glowny
ORIGIN_LAT, ORIGIN_LON = 50.0617, 19.9373
EARTH_R = 6_371_000.0


def to_xz(lat: ArrayLike, lon: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """Zamienia wspolrzedne geograficzne na metry od ORIGIN.

    Args:
        lat: Szerokosc geograficzna w stopniach (skalar lub tablica).
        lon: Dlugosc geograficzna w stopniach (skalar lub tablica).

    Returns:
        Para (x, z): x na wschod, z na polnoc, w metrach.
    """
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    x = np.radians(lon - ORIGIN_LON) * EARTH_R * np.cos(np.radians(ORIGIN_LAT))
    z = np.radians(lat - ORIGIN_LAT) * EARTH_R
    return x, z
