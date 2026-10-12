import pandas as pd

ev = pd.read_parquet("data/processed/observed_events.parquet")
vp = pd.read_parquet("data/raw_A/vehicle_positions")
vp["vehicle_id"] = vp["vehicle_id"].astype(str)

out = ev[ev["arr_delay_s"].abs() > 1800]
print("zdarzen z |opoznieniem| > 30 min:", len(out), " udzial:", round(len(out) / len(ev), 4))
print("pierwszy/ostatni przystanek:", out[["is_first", "is_last"]].mean().round(2).to_dict())
print("mediana n (probek statusu 1): outliery", out["n"].median(), " reszta", ev["n"].median())
print("\nwedlug pojazdu:\n", out["vehicle_id"].value_counts().head(8))
print("\nwedlug linii:\n", out["route_id"].value_counts().head(8))

pos = out[out["arr_delay_s"] > 1800]
print("\ndodatnie outliery (kandydaci na opoznione trip_id): n =", len(pos),
      " mediana n:", pos["n"].median(), " is_first:", round(pos["is_first"].mean(), 2))

v = vp[vp["vehicle_id"] == "321"].sort_values("veh_ts")
chg = v[v["trip_id"] != v["trip_id"].shift()].assign(
    time=lambda d: pd.to_datetime(d["veh_ts"], unit="s", utc=True).dt.tz_convert("Europe/Warsaw"))
print("\nzmiany trip_id pojazdu 321:")
print(chg[["time", "trip_id", "current_stop_sequence", "current_status"]].to_string())