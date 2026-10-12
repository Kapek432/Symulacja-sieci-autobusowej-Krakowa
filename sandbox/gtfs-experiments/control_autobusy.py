import pandas as pd

vp = pd.read_parquet("data/raw_A/vehicle_positions")
tu = pd.read_parquet("data/raw_A/trip_updates")
print(vp.shape, tu.shape)
print("pojazdow:", vp["vehicle_id"].nunique(), " kursow:", vp["trip_id"].nunique())
print("snapshotow:", vp["fetched_at"].nunique())
print((vp["fetched_at"] - vp["veh_ts"]).describe())   # wiek pozycji w sekundach
print(tu[["arr_delay", "dep_delay", "trip_delay", "arr_time", "dep_time"]].notna().mean().round(2))