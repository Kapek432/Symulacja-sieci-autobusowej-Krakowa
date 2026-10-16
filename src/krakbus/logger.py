"""Wspolny format logowania dla komend projektu."""

import logging

FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Ustawia format i poziom logowania; wywolywane raz w `main()` komendy."""
    logging.basicConfig(level=level, format=FORMAT, datefmt="%H:%M:%S")
