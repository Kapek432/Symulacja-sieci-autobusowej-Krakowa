import glob
import zipfile
import pandas as pd

vp = pd.read_parquet("data/raw/vehicle_positions")
tu = pd.read_parquet("data/raw/trip_updates")
print("VP:", vp.shape, " TU:", tu.shape)

cols = ["vehicle_id", "trip_id", "route_id", "lat", "lon", "veh_ts",
        "current_stop_sequence", "stop_id", "current_status"]
print(vp[cols].head(10))

print("\nunikalnych feed_ts:", vp["feed_ts"].nunique())
print("pojazdow:", vp["vehicle_id"].nunique())
print("linie:", sorted(vp["route_id"].dropna().unique()))

print("\nodsetek wypelnionych pol, VehiclePositions:")
print(vp.notna().mean().round(2))
print("\nodsetek wypelnionych pol, TripUpdates:")
print(tu.notna().mean().round(2))

ts = vp["feed_ts"].drop_duplicates().sort_values()
print("\nodstepy miedzy odswiezeniami pliku [s]:")
print(ts.diff().describe())

print("\nwiek pozycji pojazdu: fetched_at - veh_ts [s]:")
print((vp["fetched_at"] - vp["veh_ts"]).describe())

zpath = sorted(glob.glob("data/raw/static/GTFS_KRK_T_*.zip"))[-1]
with zipfile.ZipFile(zpath) as z:
    print("\npliki w GTFS:", z.namelist())
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
print("trip_id z VP obecne w rozkladzie:",
      vp["trip_id"].isin(trips["trip_id"]).mean().round(3))