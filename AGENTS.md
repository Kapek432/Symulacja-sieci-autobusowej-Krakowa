# Instrukcje dla agentów (cały zespół)

- Po każdej zakończonej implementacji dopisz wpis na górze `docs/DZIENNIK.md` (szablon w pliku): data, autor (`git config user.name`), commity, co zrobione, decyzje z uzasadnieniem, co sprawdzone, co otwarte. Nie zmieniaj cudzych wpisów. Zaznacz zrobione punkty w `docs/milestones/*.md`.
- Commity: bez stopek AI (`Co-authored-by: Cursor`, `Co-authored-by: Claude`, `Generated-by` itp.). Format tematu: `(feat|fix|docs|style|chore) opis`.
- Narzędzia: `uv run` zamiast `python`; testy `uv run pytest`, lint `uv run ruff check src tests`. Kod w `src/krakbus/`, progi w `configs/config.yaml`, `logging` zamiast `print` w `src/`.
- Nie commitować `data/` (surowe ani przetworzone). Nie edytować `TEMAT.md`.
- Plan i kamienie milowe: `docs/PLAN_REALIZACJI.md`, `docs/milestones/`.
