# Unity export contract (schema_version 1)

Python writes, Unity only reads and displays. The same format is used for observed data (`source = "obs"`) and simulation output (`source = "sim"`), so both play back with the same code on the same clock.

Exporter for observed data: `src/viz/export_unity.py`.

```
uv run src/viz/export_unity.py                                   # everything in data/raw_A
uv run src/viz/export_unity.py --from 2026-10-16T07:00 --to 2026-10-16T09:00 --routes 179,169,174
```

Default output: `data/processed/unity_samples/obs.jsonl` + `obs.meta.json`.

## File `<name>.jsonl`

One row = one vehicle report (obs: roughly every 5 s, from the logger). Rows are sorted by `t`. Unity interpolates position between consecutive reports of the same `vehicle_id`.

| Field | Type | Meaning |
|-------|------|---------|
| `t` | int | report time, UTC epoch [s] |
| `sim_time_s` | int / null | seconds since local midnight of the service day (as in GTFS, > 86400 at night); shared obs/sim clock |
| `service_date` | str / null | service day `YYYY-MM-DD` (a trip after midnight belongs to the previous day) |
| `vehicle_id` | str | vehicle |
| `trip_id`, `route_id` | str | trip and route from GTFS |
| `lat`, `lon` | float | WGS84 |
| `x`, `z` | float | metres from the origin in `meta.origin`: `x` east, `z` north. In Unity simply `new Vector3(x, 0, z)` |
| `bearing` | float | heading [°], 0 = north |
| `status` | int / null | GTFS-RT: 0 incoming at, 1 stopped at stop, 2 in transit |
| `delay_s` | int / null | delay vs schedule [s], negative = early; null = not computed (see `layover`) |
| `layover` | bool | vehicle waiting at the terminus before the trip departs (e.g. grey in Unity) |
| `source` | str | `obs` or `sim` |

Delay in obs: at a stop, `t − scheduled arrival`; between stops, the scheduled time is interpolated by distance to the neighbouring stops. At the first stop a positive delay (late departure) is kept, a negative one becomes `layover`.

## File `<name>.meta.json`

| Field | Meaning |
|-------|---------|
| `schema_version` | version of this contract; changing fields = bump the version |
| `run_id`, `seed` | run identification (obs: `seed = null`) |
| `source` | `obs` / `sim` |
| `gtfs` | schedule file used to compute delays |
| `origin` | `lat`, `lon` of the `x`/`z` origin (Main Market Square) |
| `t_min`, `t_max`, `rows`, `vehicles`, `routes` | range and summary |
