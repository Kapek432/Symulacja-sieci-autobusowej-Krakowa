import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", None)

DAY = "2026-10-05"
hp = pd.read_parquet("data/processed/headway_pairs.parquet")
hp = hp[hp["service_date"] == DAY].copy()
hp["h_obs"] = hp["h_obs"].astype(float)
hp["h_sched"] = hp["h_sched"].astype(float)
hp["e"] = hp["h_obs"] - hp["h_sched"]
hp["hour"] = pd.to_datetime(hp["t"], unit="s", utc=True).dt.tz_convert("Europe/Warsaw").dt.hour
print("par w dniu", DAY, ":", len(hp))

# 1. czy linia 704 (i inne) ma pary z krotkim odstepem rozkladowym?
short = hp.groupby("route_id")["h_sched"].agg(
    n="size", med_min=lambda s: s.median() / 60, share_lt_3min=lambda s: (s < 180).mean())
print("\nUdzial par z odstepem rozkladowym < 3 min (top 10):")
print(short.sort_values("share_lt_3min", ascending=False).head(10).round(3))
print("\nlinia 704:", short.loc[["704"]].round(3).to_dict("records") if "704" in short.index else "brak")

# 2. wskazniki w sekundach, tylko pary z odstepem rozkladowym >= 3 min
d = hp[hp["h_sched"] >= 180].copy()


def summ(g):
    return pd.Series({
        "n": len(g),
        "h_sched_med_min": g["h_sched"].median() / 60,
        "e_std_s": g["e"].std(),
        "e_iqr_s": g["e"].quantile(.75) - g["e"].quantile(.25),
        "near": (g["h_obs"] < 0.25 * g["h_sched"]).mean(),
        "far": (g["h_obs"] > 1.75 * g["h_sched"]).mean(),
        "swapped": (g["h_obs"] < 0).mean(),
    })


print("\nCALOSC (h_sched >= 3 min):")
print(summ(d).round(3))

by_line = (d.groupby(["route_id", "dir"]).apply(summ, include_groups=False)
           .query("n >= 200"))

# 3. nachylenie rozrzutu bledu odstepu wzdluz trasy (piatki trasy)
d["pos"] = pd.cut(d["frac"].astype(float), 5, labels=False)


def slope(g):
    a = g.groupby("pos")["e"].agg(["std", "size"])
    a = a[a["size"] >= 20]
    return np.polyfit(a.index.to_numpy(float), a["std"].to_numpy(), 1)[0] if len(a) >= 4 else np.nan


sl = d.groupby(["route_id", "dir"]).apply(slope, include_groups=False).rename("slope_s_per_fifth")
by_line = by_line.join(sl)
print("\nLINIE O NAJWIEKSZYM ROZRZUCIE (e_std_s):")
print(by_line.sort_values("e_std_s", ascending=False).head(15).round(3))
print("\nLINIE O NAJWIEKSZYM NACHYLENIU:")
print(by_line.sort_values("slope_s_per_fifth", ascending=False).head(10).round(3))
print("udzial linii z dodatnim nachyleniem:", round((by_line["slope_s_per_fifth"] > 0).mean(), 3),
      " liczba linii:", len(by_line))

# 4. wzor godzinowy (bez par o krotkim odstepie)
print("\nWEDLUG GODZINY (h_sched >= 3 min):")
print(d.groupby("hour").apply(summ, include_groups=False).round(3))

# 5. linie o odstepie <= 10 min: godziny szczytu vs poza
fast = by_line.index[by_line["h_sched_med_min"] <= 10]
dd = d.set_index(["route_id", "dir"]).loc[fast].reset_index()
dd["okres"] = np.select([dd["hour"].between(7, 8), dd["hour"].between(15, 17)],
                        ["szczyt_rano", "szczyt_pop"], "poza")
print("\nLINIE O ODSTEPIE <= 10 MIN, wg okresu dnia:")
print(dd.groupby("okres").apply(summ, include_groups=False).round(3))