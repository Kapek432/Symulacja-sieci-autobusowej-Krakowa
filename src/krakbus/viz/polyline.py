"""Geometria lamanej: rzutowanie przystankow, ciecie i upraszczanie."""

import numpy as np

MAX_CANDIDATES = 5


def _cumulative(line: np.ndarray) -> np.ndarray:
    """Zwraca skumulowana dlugosc luku w wierzcholkach lamanej."""
    seg_len = np.hypot(*np.diff(line, axis=0).T)
    return np.concatenate([[0.0], np.cumsum(seg_len)])


def _point_at(line: np.ndarray, cum: np.ndarray, s: float) -> np.ndarray:
    """Zwraca punkt lamanej w odleglosci luku `s` (obcinane do zakresu)."""
    s = float(np.clip(s, 0.0, cum[-1]))
    i = int(np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(line) - 2))
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg <= 0 else (s - cum[i]) / seg
    return line[i] + t * (line[i + 1] - line[i])


def _candidates(line: np.ndarray, cum: np.ndarray, stop: np.ndarray) -> list[tuple[float, float]]:
    """Kandydaci rzutu przystanku: lokalne minima odleglosci po segmentach."""
    a, b = line[:-1], line[1:]
    ab = b - a
    len2 = np.einsum("ij,ij->i", ab, ab)
    safe = np.where(len2 > 0, len2, 1.0)
    t = np.clip(np.einsum("ij,ij->i", stop - a, ab) / safe, 0.0, 1.0)
    t = np.where(len2 > 0, t, 0.0)
    foot = a + t[:, None] * ab
    dist = np.hypot(*(stop - foot).T)
    s = cum[:-1] + t * np.sqrt(len2)
    left = np.concatenate([[np.inf], dist[:-1]])
    right = np.concatenate([dist[1:], [np.inf]])
    idx = np.flatnonzero((dist <= left) & (dist <= right))
    idx = idx[np.argsort(dist[idx], kind="stable")][:MAX_CANDIDATES]
    return [(float(s[i]), float(dist[i])) for i in idx]


def project_stops(line: np.ndarray, stops: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rzutuje przystanki na lamana z zachowaniem niemalejacej kolejnosci.

    Dla kazdego przystanku bierze kandydatow (lokalne minima odleglosci po
    segmentach, maks. 5 najblizszych), a potem programowaniem dynamicznym
    (Viterbi) wybiera sekwencje o najmniejszej sumie odleglosci z warunkiem
    `s[j] >= s[j-1]`. Gdy z kandydata nie ma dozwolonego przejscia, dodawany
    jest kandydat zastepczy w tym samym `s`.

    Args:
        line: Lamana (n, 2) w metrach.
        stops: Przystanki (k, 2) w metrach, w kolejnosci przejazdu.

    Returns:
        Krotka `(s, dist)`: pozycja rzutu jako dlugosc luku od poczatku
        lamanej (niemalejaca) oraz odleglosc przystanku od rzutu.
    """
    line = np.asarray(line, float)
    stops = np.asarray(stops, float)
    k = len(stops)
    if k == 0:
        return np.empty(0), np.empty(0)
    cum = _cumulative(line)

    layers = [_candidates(line, cum, stops[0])]
    back: list[list[int]] = [[-1] * len(layers[0])]
    cost: list[list[float]] = [[c[1] for c in layers[0]]]
    for j in range(1, k):
        cands = _candidates(line, cum, stops[j])
        prev = layers[j - 1]
        for p_s, _ in prev:
            if not any(c_s >= p_s for c_s, _ in cands):
                d = float(np.hypot(*(stops[j] - _point_at(line, cum, p_s))))
                cands.append((p_s, d))
        cur_cost: list[float] = []
        cur_back: list[int] = []
        for c_s, c_d in cands:
            best, arg = np.inf, -1
            for pi, (p_s, _) in enumerate(prev):
                if c_s >= p_s and cost[j - 1][pi] < best:
                    best, arg = cost[j - 1][pi], pi
            cur_cost.append(best + c_d)
            cur_back.append(arg)
        layers.append(cands)
        cost.append(cur_cost)
        back.append(cur_back)

    ci = int(np.argmin(cost[-1]))
    s_out = np.empty(k)
    d_out = np.empty(k)
    for j in range(k - 1, -1, -1):
        s_out[j], d_out[j] = layers[j][ci]
        ci = back[j][ci]
    return s_out, d_out


def cut_polyline(line: np.ndarray, s_from: float, s_to: float) -> np.ndarray:
    """Wycina fragment lamanej miedzy dlugosciami luku `s_from` i `s_to`.

    Args:
        line: Lamana (n, 2) w metrach.
        s_from: Poczatek fragmentu (dlugosc luku).
        s_to: Koniec fragmentu (dlugosc luku).

    Returns:
        Tablica (m, 2), m >= 2: punkt w `s_from`, wierzcholki oryginalu
        pomiedzy oraz punkt w `s_to`.
    """
    line = np.asarray(line, float)
    cum = _cumulative(line)
    start = _point_at(line, cum, s_from)
    end = _point_at(line, cum, s_to)
    inner = line[(cum > s_from) & (cum < s_to)]
    return np.vstack([start[None, :], inner.reshape(-1, 2), end[None, :]])


def simplify(points: np.ndarray, tol_m: float = 2.0) -> np.ndarray:
    """Upraszcza lamana algorytmem Douglasa-Peuckera (konce zachowane).

    Args:
        points: Punkty (n, 2) w metrach.
        tol_m: Maksymalne odchylenie w metrach.

    Returns:
        Uproszczone punkty (m, 2), m >= 2 gdy n >= 2.
    """
    pts = np.asarray(points, float)
    n = len(pts)
    if n <= 2:
        return pts.copy()
    keep = np.zeros(n, bool)
    keep[[0, n - 1]] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg = pts[j] - pts[i]
        rel = pts[i + 1 : j] - pts[i]
        norm = np.hypot(*seg)
        if norm > 0:
            d = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / norm
        else:
            d = np.hypot(*rel.T)
        m = int(np.argmax(d))
        if d[m] > tol_m:
            k = i + 1 + m
            keep[k] = True
            stack += [(i, k), (k, j)]
    return pts[keep]
