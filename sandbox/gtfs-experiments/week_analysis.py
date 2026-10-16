"""week_analysis.py: pelna analiza zebranych danych (wejscie: data/processed/observed_events.parquet z build_events.py).

Uzycie:
  uv run build_events.py            # najpierw przebuduj zdarzenia na calym tygodniu
  uv run week_analysis.py [linia_pilotowa]          np. uv run week_analysis.py 179
Opcjonalnie: DAYS=2026-10-05,2026-10-06 uv run week_analysis.py   (reczny wybor dni roboczych do analiz)

Wyniki: wydruk na ekran + data/processed/week_report/report.txt + wykresy w .../figures/
"""

import os
import sys
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from gtfs_versions import load_schedule

warnings.filterwarnings("ignore")
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", 300)

HERE = Path(__file__).resolve()
ROOT = next((p for p in HERE.parents if (p / "data" / "raw_A").is_dir()), HERE.parent)
DATA = ROOT / "data" / "raw_A"
PROC = ROOT / "data" / "processed"
OUT = PROC / "week_report"
FIG = OUT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
TZ = "Europe/Warsaw"
PILOT = sys.argv[1] if len(sys.argv) > 1 else "179"
MAXD = 1800  # |opoznienie| powyzej tego = outlier
GAP_S = 120  # przerwa w loggerze uznawana za dziure
MIN_EVENTS_DAY = 500  # dzien z mniejsza liczba zdarzen traktujemy jako smieciowy
DOW = ["pon", "wt", "sr", "czw", "pt", "sob", "nd"]
KEY = {}  # kluczowe liczby do podsumowania na koncu


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, x):
        for s in self.streams:
            s.write(x)

    def flush(self):
        for s in self.streams:
            s.flush()


_report = open(OUT / "report.txt", "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, _report)


def section(name):
    def deco(fn):
        def run():
            print("\n" + "=" * 110 + f"\n{name}\n" + "=" * 110)
            try:
                fn()
            except Exception:
                print("!! BLAD W SEKCJI:", name)
                traceback.print_exc(file=sys.stdout)

        return run

    return deco


def hms(col):
    p = col.astype("string").str.strip().str.split(":", expand=True)
    return pd.to_numeric(p[0]) * 3600 + pd.to_numeric(p[1]) * 60 + pd.to_numeric(p[2])


def iqr(s):
    return s.quantile(0.75) - s.quantile(0.25)


def ks_stat(a, b):
    a, b = np.sort(a), np.sort(b)
    v = np.concatenate([a, b])
    return float(
        np.max(
            np.abs(
                np.searchsorted(a, v, side="right") / len(a)
                - np.searchsorted(b, v, side="right") / len(b)
            )
        )
    )


def plot(name, fn):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 5))
        fn(ax)
        fig.tight_layout()
        FIG.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG / name, dpi=120)
        plt.close(fig)
    except Exception as e:
        print(f"(wykres {name} pominiety: {e})")


def fe_slope(df, y, x, fe, cl):
    d = df[[y, x, cl] + fe].dropna().copy()
    d["_g"] = d.groupby(fe).ngroup()
    d = d[d.groupby("_g")[y].transform("size") >= 3]
    if len(d) < 200:
        return np.nan, np.nan, len(d), 0
    for c in (y, x):
        d[c + "_dm"] = d[c] - d.groupby("_g")[c].transform("mean")
    xx = (d[x + "_dm"] ** 2).sum()
    beta = (d[x + "_dm"] * d[y + "_dm"]).sum() / xx
    u = d[y + "_dm"] - beta * d[x + "_dm"]
    sc = (d[x + "_dm"] * u).groupby(d[cl]).sum()
    se = np.sqrt((sc**2).sum()) / xx
    return beta, se, len(d), d[cl].nunique()


# =====================================================================================
# WCZYTANIE
# =====================================================================================
print("week_analysis.py, linia pilotowa:", PILOT)
try:
    SCHED = load_schedule(DATA / "static")
except FileNotFoundError as e:
    sys.exit(str(e))
print(
    "wersje rozkladu (rozklad kursu po trip_id, kalendarz dnia z najnowszej wersji, ktora go obejmuje):"
)
for v_ in SCHED.versions:
    print("  ", v_)
trips = SCHED.trips
st = SCHED.stop_times
stops = SCHED.stops
# kalendarz efektywny jest juz rozwiniety do par (service_id, date), wiec calendar.txt nie jest potrzebny
CAL = None
CD = SCHED.calendar

st["stop_sequence"] = st["stop_sequence"].astype(int)
st["arr_s"] = hms(st["arrival_time"])
st["dep_s"] = hms(st["departure_time"])
st = st.sort_values(["trip_id", "stop_sequence"]).reset_index(drop=True)
_g = st.groupby("trip_id")
st["frac"] = (_g["stop_sequence"].rank(method="first") - 1) / (
    _g["stop_sequence"].transform("size") - 1
)
tt = pd.DataFrame(
    {"start_s": _g["dep_s"].first(), "end_s": _g["arr_s"].last(), "n_stops": _g.size()}
)
tr = trips.drop_duplicates("trip_id").set_index("trip_id").join(tt)
_dc = next((c for c in ("direction_id", "trip_headsign") if c in tr.columns), None)
tr["dir"] = tr[_dc].fillna("?") if _dc else "0"
HAS_BLOCK = "block_id" in tr.columns and tr["block_id"].notna().any()
if HAS_BLOCK:
    t_ = (
        tr.dropna(subset=["block_id"])
        .reset_index()
        .sort_values(["service_id", "block_id", "start_s"])
    )
    gb_ = t_.groupby(["service_id", "block_id"])
    t_["next_trip"] = gb_["trip_id"].shift(-1)
    t_["blk_idx"] = gb_.cumcount()
    t_["layover_s"] = gb_["start_s"].shift(-1) - t_["end_s"]
    tr = tr.join(t_.set_index("trip_id")[["next_trip", "blk_idx", "layover_s"]])

ev = pd.read_parquet(PROC / "observed_events.parquet")
for c in ("route_id", "trip_id", "stop_id", "vehicle_id"):
    ev[c] = ev[c].astype(str)
for c in ("arr_ok", "dep_ok", "is_first", "is_last"):
    ev[c] = ev[c].fillna(False).astype(bool)
_no_date = ev["service_date"].isna()
if _no_date.any():
    print(
        "pomijam zdarzenia bez daty obslugi (kurs spoza rozkladu lub usluga nieaktywna):",
        int(_no_date.sum()),
        f"({_no_date.mean():.1%})",
    )
    ev = ev[~_no_date].copy()
ev["service_date"] = ev["service_date"].astype(str)
ev["delay"] = ev["arr_delay_s"].astype(float)
_loc = pd.to_datetime(ev["arr_ts"].astype("int64"), unit="s", utc=True).dt.tz_convert(
    TZ
)
ev["hour"] = _loc.dt.hour
cnt_all = ev.groupby("service_date").size()
junk = cnt_all[cnt_all < MIN_EVENTS_DAY].index.tolist()
if junk:
    print(
        "pomijam dni z < %d zdarzeniami (smieciowe daty obslugi):" % MIN_EVENTS_DAY,
        junk,
    )
    ev = ev[~ev["service_date"].isin(junk)].copy()
ev["dow"] = pd.to_datetime(ev["service_date"]).dt.dayofweek
ev["period"] = np.select(
    [ev["hour"].between(7, 8), ev["hour"].between(15, 17)],
    ["szczyt_rano", "szczyt_pop"],
    "poza",
)
ev["dir"] = ev["trip_id"].map(tr["dir"])
if HAS_BLOCK:
    ev["blk_idx"] = ev["trip_id"].map(tr["blk_idx"])

DAYS = sorted(ev["service_date"].unique())
cnt_day = ev.groupby("service_date").size()
_wd = [d for d in DAYS if pd.Timestamp(d).dayofweek < 5]
_med = cnt_day[_wd].median() if _wd else 0
FULL = [d for d in _wd if cnt_day[d] >= 0.7 * _med]
if os.environ.get("DAYS"):
    WORK = [d.strip() for d in os.environ["DAYS"].split(",")]
else:
    WORK = FULL
print(
    "dni w danych:",
    [f"{d} ({DOW[pd.Timestamp(d).dayofweek]}, {cnt_day[d]})" for d in DAYS],
)
print("dni robocze uznane za pelne (>= 70% mediany zdarzen):", WORK)
KEY["dni_w_danych"] = len(DAYS)
KEY["pelne_dni_robocze"] = len(WORK)

good = ev[ev["arr_ok"] & ev["delay"].notna() & (ev["delay"].abs() <= MAXD)].copy()
good["span"] = (good["last_seq"] - good["first_seq"]).astype(float)
good = good[good["span"] > 0].copy()
good["frac"] = (good["stop_sequence"] - good["first_seq"]) / good["span"]
good["fifth"] = np.minimum((good["frac"] * 5).astype(int), 4)
gw = good[good["service_date"].isin(WORK)].copy()
print(
    "zdarzen razem:",
    len(ev),
    " dobrych do analiz (arr_ok, |op| <= 30 min):",
    len(good),
    " w dniach roboczych:",
    len(gw),
)

# obserwacje i pary
obs = (
    good[["service_date", "trip_id", "stop_id", "arr_ts", "delay"]]
    .drop_duplicates(["service_date", "trip_id", "stop_id"])
    .rename(columns={"arr_ts": "t"})
)
obs["t"] = obs["t"].astype(float)
seen = ev[["service_date", "trip_id"]].drop_duplicates()
sch = st[["trip_id", "stop_id", "stop_sequence", "arr_s", "frac"]]
sch = sch[~sch.duplicated(["trip_id", "stop_id"], keep=False)]
sch = sch.merge(tr[["route_id", "dir"]], left_on="trip_id", right_index=True).merge(
    seen, on="trip_id"
)


def build_pairs(keys, hmin, hmax):
    s = sch.sort_values(keys + ["arr_s"]).copy()
    g = s.groupby(keys)
    s["prev_trip"] = g["trip_id"].shift(1)
    s["h_sched"] = s["arr_s"] - g["arr_s"].shift(1)
    p = s.dropna(subset=["prev_trip"])
    p = p[(p["h_sched"] >= hmin) & (p["h_sched"] <= hmax)]
    p = p.merge(obs, on=["service_date", "trip_id", "stop_id"])
    p = p.merge(
        obs.rename(columns={"trip_id": "prev_trip", "t": "t_prev", "delay": "d_prev"}),
        on=["service_date", "prev_trip", "stop_id"],
    )
    p["h_sched"] = p["h_sched"].astype(float)
    p["h_obs"] = p["t"] - p["t_prev"]
    p["e"] = p["h_obs"] - p["h_sched"]
    p["hour"] = pd.to_datetime(p["t"], unit="s", utc=True).dt.tz_convert(TZ).dt.hour
    p["period"] = np.select(
        [p["hour"].between(7, 8), p["hour"].between(15, 17)],
        ["szczyt_rano", "szczyt_pop"],
        "poza",
    )
    p["fifth"] = np.minimum((p["frac"].astype(float) * 5).astype(int), 4)
    return p


HP = build_pairs(
    ["service_date", "route_id", "dir", "stop_id"], 1, 3600
)  # ta sama linia i kierunek
CP = build_pairs(["service_date", "stop_id"], 180, 1800)  # dowolne linie
CP["prev_route"] = CP["prev_trip"].map(tr["route_id"])
CP["same_route"] = CP["route_id"] == CP["prev_route"]
print(
    "pary odstepow ta sama linia:", len(HP), " pary dowolne linie na slupku:", len(CP)
)
HPw = HP[HP["service_date"].isin(WORK)]


# =====================================================================================
@section("1. POKRYCIE I JAKOSC DANYCH, DZIEN PO DNIU")
def s1():
    t = ev.groupby("service_date").agg(
        zdarzen=("trip_id", "size"),
        pojazdow=("vehicle_id", "nunique"),
        kursow=("trip_id", "nunique"),
        linii=("route_id", "nunique"),
        udzial_arr_ok=("arr_ok", "mean"),
        z_rozkladem=("arr_s", lambda s: s.notna().mean()),
        godz_min=("hour", "min"),
        godz_max=("hour", "max"),
    )
    t["dzien"] = [DOW[pd.Timestamp(x).dayofweek] for x in t.index]
    t["pelny_roboczy"] = t.index.isin(FULL)
    print(t.round(3).to_string())
    print("\nZDARZENIA WG DNIA I GODZINY (godzina przyjazdu, czas lokalny):")
    hm = ev.pivot_table(
        index="service_date",
        columns="hour",
        values="trip_id",
        aggfunc="size",
        fill_value=0,
    )
    print(hm.to_string())
    plot(
        "01_zdarzenia_dzien_godzina.png",
        lambda ax: (
            ax.imshow(hm.values, aspect="auto"),
            ax.set_yticks(range(len(hm))),
            ax.set_yticklabels(hm.index),
            ax.set_xticks(range(hm.shape[1])),
            ax.set_xticklabels(hm.columns),
            ax.set_title("zdarzenia: dzien x godzina"),
        ),
    )

    print(
        "\nDZIURY W LOGGERZE (VehiclePositions, odstep miedzy migawkami >", GAP_S, "s):"
    )
    fa = np.sort(
        pd.read_parquet(DATA / "vehicle_positions", columns=["fetched_at"])[
            "fetched_at"
        ]
        .dropna()
        .unique()
    )
    dt = np.diff(fa)
    print("migawek:", len(fa), " mediana kroku [s]:", round(float(np.median(dt)), 1))
    idx = np.where(dt > GAP_S)[0]
    gaps = pd.DataFrame(
        {
            "od": pd.to_datetime(fa[idx], unit="s", utc=True).tz_convert(TZ),
            "do": pd.to_datetime(fa[idx + 1], unit="s", utc=True).tz_convert(TZ),
            "min": dt[idx] / 60,
        }
    )
    print(
        "liczba dziur:",
        len(gaps),
        " laczny czas [h]:",
        round(gaps["min"].sum() / 60, 1),
    )
    print(
        gaps.sort_values("min", ascending=False)
        .head(25)
        .round(1)
        .to_string(index=False)
    )
    ld = pd.to_datetime(fa[:-1], unit="s", utc=True).tz_convert(TZ).strftime("%Y-%m-%d")
    cov = (
        pd.DataFrame({"d": ld, "dt": dt}).query("dt <= @GAP_S").groupby("d")["dt"].sum()
        / 3600
    )
    print("\nGODZINY DZIALANIA LOGGERA WG DATY LOKALNEJ (suma krokow <= %d s):" % GAP_S)
    print(cov.round(1).to_string())


@section("2. ROZKLAD: ILE KURSOW POWINNO JECHAC vs ILE ZOBACZONO")
def s2():
    if CAL is None and CD is None:
        print("brak calendar.txt/calendar_dates.txt")
        return
    rows, mats = [], {}
    obs_trips = ev.groupby("service_date")["trip_id"].apply(set)
    for d in DAYS:
        ymd = d.replace("-", "")
        wd = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ][pd.Timestamp(d).dayofweek]
        act = set()
        if CAL is not None:
            ok = (
                (CAL["start_date"] <= ymd) & (CAL["end_date"] >= ymd) & (CAL[wd] == "1")
            )
            act |= set(CAL.loc[ok, "service_id"])
        exc = 0
        if CD is not None:
            c = CD[CD["date"] == ymd]
            exc = len(c)
            act |= set(c.loc[c["exception_type"] == "1", "service_id"])
            act -= set(c.loc[c["exception_type"] == "2", "service_id"])
        exp = tr[tr["service_id"].isin(act)]
        seen_d = obs_trips.get(d, set())
        rows.append(
            {
                "data": d,
                "dzien": DOW[pd.Timestamp(d).dayofweek],
                "wyjatki_calendar_dates": exc,
                "kursow_wg_rozkladu": len(exp),
                "zaobserwowanych": len(set(exp.index) & seen_d),
                "obserwowane_spoza_rozkladu_dnia": len(seen_d - set(exp.index)),
            }
        )
        h = (exp["start_s"] // 3600).astype(int)
        s_ = pd.Series(exp.index.isin(seen_d), index=exp.index).groupby(h).mean()
        mats[d] = s_
    t = pd.DataFrame(rows).set_index("data")
    t["udzial"] = t["zaobserwowanych"] / t["kursow_wg_rozkladu"]
    print(t.round(3).to_string())
    print(
        "\nUDZIAL ZAOBSERWOWANYCH KURSOW WG GODZINY STARTU WG ROZKLADU (spadek = dziura w danych):"
    )
    print(pd.DataFrame(mats).T.reindex(columns=range(4, 24)).round(2).to_string())
    print(
        "\nkursow spoza rozkladu dnia > 0 sugeruje zla wersje rozkladu lub zle przypisanie daty obslugi."
    )


@section("3. OPOZNIENIA: DZIEN PO DNIU, TYP DNIA, PORA, STABILNOSC MIEDZY DNIAMI")
def s3():
    f = dict(
        n="size",
        mediana="median",
        q25=lambda s: s.quantile(0.25),
        q75=lambda s: s.quantile(0.75),
        p90=lambda s: s.quantile(0.9),
        p95=lambda s: s.quantile(0.95),
        std="std",
    )
    t = good.groupby("service_date")["delay"].agg(**f)
    t["dzien"] = [DOW[pd.Timestamp(x).dayofweek] for x in t.index]
    print(t.round(1).to_string())
    good["typ"] = np.select(
        [good["dow"] < 5, good["dow"] == 5], ["roboczy", "sobota"], "niedziela"
    )
    print("\nWG TYPU DNIA:")
    print(good.groupby("typ")["delay"].agg(**f).round(1).to_string())
    print("\nMEDIANA OPOZNIENIA [s] WG DNIA x PORA:")
    print(
        good.pivot_table(
            index="service_date", columns="period", values="delay", aggfunc="median"
        )
        .round(0)
        .to_string()
    )
    print("\nMEDIANA OPOZNIENIA [s] WG DNIA x GODZINA:")
    hp_ = good.pivot_table(
        index="service_date", columns="hour", values="delay", aggfunc="median"
    ).round(0)
    print(hp_.to_string())
    print(
        "\nSTABILNOSC MIEDZY DNIAMI ROBOCZYMI: statystyka KS rozkladow opoznien (0 = identyczne)"
    )
    rng = np.random.default_rng(0)
    smp = {
        d: rng.choice(
            gw.loc[gw["service_date"] == d, "delay"].to_numpy(),
            size=min(20000, (gw["service_date"] == d).sum()),
            replace=False,
        )
        for d in WORK
    }
    wk = [d for d in WORK if len(smp[d])]
    if len(wk) < len(WORK):
        print(
            "dni robocze bez dobrych zdarzen (pominiete w KS):",
            sorted(set(WORK) - set(wk)),
        )
    ks = pd.DataFrame({a: {b: ks_stat(smp[a], smp[b]) for b in wk} for a in wk})
    print(ks.round(3).to_string())
    KEY["KS_max_miedzy_dniami_roboczymi"] = (
        round(float(ks.values[np.triu_indices(len(wk), 1)].max()), 3)
        if len(wk) > 1
        else None
    )
    top = gw.groupby("route_id").size().sort_values(ascending=False).head(12).index
    print("\nMEDIANA OPOZNIENIA [s] 12 NAJLICZNIEJSZYCH LINII WG DNIA:")
    print(
        gw[gw["route_id"].isin(top)]
        .pivot_table(
            index="route_id", columns="service_date", values="delay", aggfunc="median"
        )
        .round(0)
        .to_string()
    )
    plot(
        "03_mediana_opoznienia_godzina.png",
        lambda ax: (
            [ax.plot(hp_.columns, hp_.loc[d], label=d) for d in hp_.index],
            ax.legend(fontsize=7),
            ax.set_title("mediana opoznienia [s] wg godziny"),
            ax.set_xlabel("godzina"),
        ),
    )


@section("4. OPOZNIENIE I ROZRZUT WZDLUZ TRASY (dryf, ksztalt wzrostu wariancji)")
def s4():
    t = gw.groupby("fifth")["delay"].agg(
        n="size",
        mediana="median",
        srednia="mean",
        std="std",
        p90=lambda s: s.quantile(0.9),
    )
    print("POOLED, dni robocze, piate czesci trasy:")
    print(t.round(1).to_string())
    KEY["dryf_mediana_pierwsza_piata_s"] = round(float(t["mediana"].iloc[0]), 0)
    KEY["dryf_mediana_ostatnia_piata_s"] = round(float(t["mediana"].iloc[-1]), 0)
    KEY["std_opoznienia_ostatnia/pierwsza_piata"] = round(
        float(t["std"].iloc[-1] / t["std"].iloc[0]), 2
    )
    top = gw.groupby("route_id").size().sort_values(ascending=False).head(12).index
    sub = gw[gw["route_id"].isin(top)]
    print("\nMEDIANA wg linii x piata czesc:")
    print(
        sub.pivot_table(
            index="route_id", columns="fifth", values="delay", aggfunc="median"
        )
        .round(0)
        .to_string()
    )
    print("\nODCH. STD wg linii x piata czesc:")
    sd = sub.pivot_table(
        index="route_id", columns="fifth", values="delay", aggfunc="std"
    )
    sd["ostatnia/pierwsza"] = sd[4] / sd[0]
    print(sd.round(2).to_string())
    print(
        "\nSTD OSTATNIEJ / PIERWSZEJ PIATEJ, WG DNIA (stabilnosc faktu stylizowanego):"
    )
    r = sub.groupby(["route_id", "service_date"]).apply(
        lambda g: (
            g.loc[g.fifth == 4, "delay"].std() / g.loc[g.fifth == 0, "delay"].std()
            if (g.fifth == 0).sum() > 20 and (g.fifth == 4).sum() > 20
            else np.nan
        ),
        include_groups=False,
    )
    print(r.unstack("service_date").round(2).to_string())

    print(
        "\nKSZTALT WZROSTU WARIANCJI WZDLUZ TRASY (po numerze przystanku k od poczatku kursu):"
    )
    print(
        "  liniowy: var = a + b*k ; kwadratowy: var = a + b*k + c*k^2 ; wykladnik: var ~ k^p (p=1 liniowy, p>1 szybszy)"
    )
    rows = []
    for (r_, dn), g in gw.groupby(["route_id", "dir"]):
        if len(g) < 1500:
            continue
        a = g.groupby("stop_sequence")["delay"].agg(["var", "size"])
        a = a[a["size"] >= 20].dropna()
        if len(a) < 15:
            continue
        k = (a.index.values - a.index.values.min()).astype(float)
        v = a["var"].values
        ss = ((v - v.mean()) ** 2).sum()
        c1 = np.polyfit(k, v, 1)
        c2 = np.polyfit(k, v, 2)
        m = k >= 1
        rows.append(
            {
                "linia": r_,
                "kier": dn,
                "n": len(g),
                "przystankow": len(a),
                "b_lin": c1[0],
                "R2_lin": 1 - ((v - np.polyval(c1, k)) ** 2).sum() / ss,
                "c_kwadr": c2[0],
                "R2_kwadr": 1 - ((v - np.polyval(c2, k)) ** 2).sum() / ss,
                "wykladnik_p": np.polyfit(np.log(k[m]), np.log(v[m]), 1)[0],
            }
        )
    if rows:
        t2 = pd.DataFrame(rows).sort_values("n", ascending=False)
        print(t2.head(25).round(3).to_string(index=False))
        KEY["mediana_wykladnika_p_wariancji"] = round(
            float(t2["wykladnik_p"].median()), 2
        )
        KEY["udzial_linii_z_c_kwadr>0"] = round(float((t2["c_kwadr"] > 0).mean()), 2)

    def f(ax):
        for d in WORK:
            q = gw[gw["service_date"] == d].groupby("fifth")["delay"].median()
            ax.plot(q.index, q.values, marker="o", label=d)
        ax.set_title("mediana opoznienia wg piatej czesci trasy")
        ax.legend(fontsize=7)

    plot("04_dryf_wzdluz_trasy.png", f)


@section(
    "5. BLAD ODSTEPU sigma_e, NACHYLENIE, WZOR DOBOWY (odstep rozkladowy >= 3 min)"
)
def s5():
    d = HP[HP["h_sched"] >= 180].copy()
    dw = d[d["service_date"].isin(WORK)]

    def summ(g):
        return pd.Series(
            {
                "n": len(g),
                "h_sched_med_min": g["h_sched"].median() / 60,
                "e_std_s": g["e"].std(),
                "e_iqr_s": iqr(g["e"]),
                "near<0.25": (g["h_obs"] < 0.25 * g["h_sched"]).mean(),
                "far>1.75": (g["h_obs"] > 1.75 * g["h_sched"]).mean(),
                "swapped": (g["h_obs"] < 0).mean(),
            }
        )

    def slope(g):
        a = g.groupby("fifth")["e"].agg(["std", "size"])
        a = a[a["size"] >= 20]
        return (
            np.polyfit(a.index.to_numpy(float), a["std"].to_numpy(), 1)[0]
            if len(a) >= 4
            else np.nan
        )

    print("CALOSC (dni robocze):")
    print(summ(dw).round(3).to_string())
    by = (
        dw.groupby(["route_id", "dir"])
        .apply(summ, include_groups=False)
        .query("n >= 300")
    )
    by = by.join(
        dw.groupby(["route_id", "dir"])
        .apply(slope, include_groups=False)
        .rename("slope_s_na_piata")
    )
    print("\nWG LINII I KIERUNKU (n >= 300), po liczbie par:")
    print(by.sort_values("n", ascending=False).head(30).round(3).to_string())
    pos = float((by["slope_s_na_piata"] > 0).mean())
    print(
        "\nudzial linii/kierunkow z dodatnim nachyleniem:",
        round(pos, 3),
        " liczba:",
        by["slope_s_na_piata"].notna().sum(),
    )
    KEY["udzial_dodatniego_slope_sigma_e"] = round(pos, 3)
    KEY["liczba_linii_kierunkow_do_slope"] = int(by["slope_s_na_piata"].notna().sum())

    print("\nNACHYLENIE sigma_e WG DNIA (linie z n >= 150 w danym dniu):")
    sl = (
        d.groupby(["service_date", "route_id", "dir"])
        .apply(lambda g: slope(g) if len(g) >= 150 else np.nan, include_groups=False)
        .unstack("service_date")
    )
    print("udzial dodatnich i liczba linii wg dnia:")
    print(
        pd.DataFrame(
            {
                "udzial_dodatnich": (sl > 0).sum() / sl.notna().sum(),
                "linii": sl.notna().sum(),
            }
        )
        .round(3)
        .T.to_string()
    )
    wcols = [c for c in sl.columns if c in WORK]
    if len(wcols) > 1:
        print(
            "\nKORELACJA NACHYLEN MIEDZY DNIAMI ROBOCZYMI (powtarzalnosc profilu linii):"
        )
        cm = sl[wcols].corr(min_periods=10)
        print(cm.round(2).to_string())
        KEY["srednia_korelacja_slope_miedzy_dniami"] = round(
            float(cm.values[np.triu_indices(len(wcols), 1)].mean()), 2
        )

    print("\nsigma_e [s] WG DNIA x GODZINA (n >= 100):")
    he = d.groupby(["service_date", "hour"])["e"].agg(["std", "size"])
    he = he[he["size"] >= 100]["std"].unstack("hour")
    print(he.round(0).to_string())
    print("\nLINIE O ODSTEPIE <= 10 MIN: sigma_e WG OKRESU I DNIA")
    fast = by.index[by["h_sched_med_min"] <= 10]
    dd = (
        dw.set_index(["route_id", "dir"]).loc[fast].reset_index()
        if len(fast)
        else dw.iloc[0:0]
    )
    if len(dd):
        print(
            dd.groupby("period").apply(summ, include_groups=False).round(3).to_string()
        )
        print(
            dd.groupby(["service_date", "period"])["e"]
            .std()
            .unstack("period")
            .round(0)
            .to_string()
        )
        pp = dd.groupby("period")["e"].std()
        KEY["sigma_e_szczyt_pop_vs_poza_s"] = (
            round(float(pp.get("szczyt_pop", np.nan)), 0),
            round(float(pp.get("poza", np.nan)), 0),
        )
    plot(
        "05_sigma_e_godzina.png",
        lambda ax: (
            [ax.plot(he.columns, he.loc[x], label=x) for x in he.index],
            ax.legend(fontsize=7),
            ax.set_title("sigma_e [s] wg godziny"),
        ),
    )


@section(
    "6. PETLA I LANCUCHY KURSOW: reset opoznienia, krzywa pochlaniania, kalibracja l_min"
)
def s6():
    if not HAS_BLOCK:
        print("brak block_id")
        return
    tv = ev.drop_duplicates(["service_date", "trip_id"])[
        ["service_date", "trip_id", "vehicle_id"]
    ]
    x = tv.assign(next_trip=tv["trip_id"].map(tr["next_trip"])).dropna(
        subset=["next_trip"]
    )
    m = x.merge(
        tv.rename(columns={"trip_id": "next_trip", "vehicle_id": "veh2"}),
        on=["service_date", "next_trip"],
    )
    print(
        "pary kolejnych kursow z bloku, oba zaobserwowane:",
        len(m),
        " ten sam pojazd:",
        round((m["vehicle_id"] == m["veh2"]).mean(), 3),
    )
    KEY["block_id_zgodny_z_pojazdem"] = round(
        float((m["vehicle_id"] == m["veh2"]).mean()), 3
    )

    last = (
        ev[
            ev["is_last"]
            & ev["arr_ok"]
            & ev["delay"].notna()
            & (ev["delay"].abs() <= MAXD)
        ][["service_date", "trip_id", "vehicle_id", "delay", "hour"]]
        .drop_duplicates(["service_date", "trip_id"])
        .rename(columns={"delay": "arr_end"})
    )
    first = (
        ev[
            ev["is_first"]
            & ev["dep_ok"]
            & ev["dep_delay_s"].notna()
            & (ev["dep_delay_s"].abs() <= MAXD)
        ][["service_date", "trip_id", "vehicle_id", "dep_delay_s"]]
        .drop_duplicates(["service_date", "trip_id"])
        .rename(columns={"trip_id": "next_trip", "dep_delay_s": "dep_next"})
    )
    last["next_trip"] = last["trip_id"].map(tr["next_trip"])
    last["layover_s"] = last["trip_id"].map(tr["layover_s"])
    last["route_id"] = last["trip_id"].map(tr["route_id"])
    ch = last.dropna(subset=["next_trip", "layover_s"]).merge(
        first, on=["service_date", "next_trip", "vehicle_id"]
    )
    ch = ch[ch["layover_s"].between(-600, 7200)].copy()
    print(
        "zaobserwowanych par (koniec kursu i odjazd nastepnego z dobra niepewnoscia):",
        len(ch),
    )
    if len(ch) < 100:
        print("za malo par, pomijam")
        return
    print(
        "mediana opoznienia przyjazdu na koniec kursu:",
        ch["arr_end"].median(),
        " mediana odjazdu nastepnego:",
        ch["dep_next"].median(),
    )
    X = (
        1 - ch["dep_next"].median() / ch["arr_end"].median()
        if ch["arr_end"].median() > 0
        else np.nan
    )
    KEY["reset_X_z_median_pooled"] = round(float(X), 2)
    print(
        "X (reset wg median, pooled) =",
        round(float(X), 3),
        " (do porownania: wstepnie 0.85-0.90)",
    )
    print(
        "OLS dep_next ~ arr_end: nachylenie (przenoszenie) =",
        round(float(np.polyfit(ch["arr_end"], ch["dep_next"], 1)[0]), 3),
    )
    KEY["przenoszenie_OLS"] = round(
        float(np.polyfit(ch["arr_end"], ch["dep_next"], 1)[0]), 3
    )

    ch["bin"] = pd.cut(ch["layover_s"] / 60, [-1000, 3, 6, 10, 15, 25, 40, 200])

    def absb(g):
        a, b = g["arr_end"].to_numpy(), g["dep_next"].to_numpy()
        hi = a > 120
        return pd.Series(
            {
                "n": len(g),
                "arr_end_med": np.median(a),
                "dep_next_med": np.median(b),
                "n_arr>120": int(hi.sum()),
                "P(dep>120|arr>120)": (b[hi] > 120).mean() if hi.any() else np.nan,
                "P(dep>120|arr<=120)": (b[~hi] > 120).mean() if (~hi).any() else np.nan,
                "OLS_przenoszenie": np.polyfit(a, b, 1)[0]
                if len(g) >= 30 and a.std() > 0
                else np.nan,
            }
        )

    ab = ch.groupby("bin", observed=True).apply(absb, include_groups=False)
    print("\nKRZYWA POCHLANIANIA wg zapasu na petli [min]:")
    print(ab.round(3).to_string())
    print(
        "\nWG LINII (top 12 po liczbie par): mediana przyjazdu na koniec, mediana odjazdu nastepnego, zapas mediana [min]"
    )
    bl = ch.groupby("route_id").agg(
        n=("arr_end", "size"),
        arr_end_med=("arr_end", "median"),
        dep_next_med=("dep_next", "median"),
        zapas_med_min=("layover_s", lambda s: s.median() / 60),
    )
    print(bl.sort_values("n", ascending=False).head(12).round(1).to_string())

    a, b, lay = (
        ch["arr_end"].to_numpy(),
        ch["dep_next"].to_numpy(),
        ch["layover_s"].to_numpy(),
    )
    res = []
    for lm in range(0, 601, 30):
        z = a + lm - lay
        d0 = np.median(b[z < -300]) if (z < -300).sum() > 50 else np.median(b)
        res.append(
            {
                "l_min_s": lm,
                "delta0_s": d0,
                "MAE_model_s": np.mean(np.abs(b - np.maximum(z, d0))),
            }
        )
    r = pd.DataFrame(res)
    base = float(np.mean(np.abs(b - np.median(b))))
    print(
        "\nKALIBRACJA l_min wg modelu dep_next = max(arr_end + l_min - L, delta0). MAE bez przenoszenia (stala):",
        round(base, 1),
    )
    print(r.round(1).to_string(index=False))
    best = r.loc[r["MAE_model_s"].idxmin()]
    KEY["l_min_najlepszy_s"] = int(best["l_min_s"])
    KEY["MAE_model_vs_stala"] = (round(float(best["MAE_model_s"]), 1), round(base, 1))

    print(
        "\nGROMADZENIE OPOZNIENIA W LANCUCHU: opoznienie przyjazdu wg numeru kursu w bloku x pora (mediana / p90):"
    )
    gb = gw.dropna(subset=["blk_idx"]).copy()
    gb["kurs_w_bloku"] = pd.cut(gb["blk_idx"], [-1, 0, 2, 5, 9, 14, 100])
    print(
        gb.pivot_table(
            index="kurs_w_bloku",
            columns="period",
            values="delay",
            aggfunc="median",
            observed=True,
        )
        .round(0)
        .to_string()
    )
    print(
        gb.pivot_table(
            index="kurs_w_bloku",
            columns="period",
            values="delay",
            aggfunc=lambda s: s.quantile(0.9),
            observed=True,
        )
        .round(0)
        .to_string()
    )
    print("\nOpoznienie odjazdu z pierwszego przystanku wg numeru kursu w bloku:")
    fdep = ev[
        ev["is_first"]
        & ev["dep_ok"]
        & ev["dep_delay_s"].notna()
        & (ev["dep_delay_s"].abs() <= MAXD)
    ].copy()
    if "blk_idx" in fdep:
        fdep["kurs_w_bloku"] = pd.cut(fdep["blk_idx"], [-1, 0, 2, 5, 9, 14, 100])
        print(
            fdep.groupby("kurs_w_bloku", observed=True)["dep_delay_s"]
            .agg(n="size", mediana="median", p90=lambda s: s.quantile(0.9))
            .round(0)
            .to_string()
        )
    f1 = fdep.groupby("route_id")["dep_delay_s"].agg(
        n="size",
        q25=lambda s: s.quantile(0.25),
        mediana="median",
        q75=lambda s: s.quantile(0.75),
    )
    print("\nODJAZD Z PIERWSZEGO PRZYSTANKU wg linii (top 15 po n):")
    print(f1.sort_values("n", ascending=False).head(15).round(0).to_string())

    def f(ax):
        ax.bar(range(len(ab)), ab["OLS_przenoszenie"].values)
        ax.set_xticks(range(len(ab)))
        ax.set_xticklabels([str(i) for i in ab.index], rotation=30, fontsize=7)
        ax.set_title("przenoszenie opoznienia na nastepny kurs wg zapasu [min]")

    plot("06_krzywa_pochlaniania.png", f)


@section(
    "7. SPRZEZENIE OD ODSTEPU gamma: regresja przyrostu bledu odstepu na bledzie odstepu (efekty stale)"
)
def s7():
    h = (
        HP[(HP["h_sched"] >= 180)]
        .sort_values(["service_date", "trip_id", "prev_trip", "stop_sequence"])
        .copy()
    )
    g = h.groupby(["service_date", "trip_id", "prev_trip"])
    h["e_next"] = g["e"].shift(-1)
    h["dseq"] = g["stop_sequence"].shift(-1) - h["stop_sequence"]
    h = h[h["dseq"] == 1].copy()
    h["de"] = h["e_next"] - h["e"]
    h = h[(h["e"].abs() <= 900) & (h["de"].abs() <= 900)]
    h["cl"] = h["service_date"] + "|" + h["trip_id"]
    h["win"] = h["hour"] // 2
    h["pasmo"] = pd.cut(h["h_sched"] / 60, [3, 6, 10, 20, 60]).astype(str)
    print("pary kolejnych odcinkow dla tej samej pary autobusow:", len(h))
    print(
        "model: de = e(s+1) - e(s) = beta * e(s) + FE + blad. beta > 0: luki rosna (zbijanie sie), beta < 0: powrot do rozkladu LUB szum pomiaru."
    )
    print(
        "UWAGA: blad pomiaru czasu (jitter ~5-10 s) w e(s) daje ujemne obciazenie beta. Wnioskuj ostroznie, najlepiej z roznicy miedzy podzbiorami."
    )
    specs = {
        "FE linia,kier,slupek": ["route_id", "dir", "stop_id"],
        "FE linia,kier,slupek,okno2h,dzien": [
            "route_id",
            "dir",
            "stop_id",
            "win",
            "service_date",
        ],
    }
    subsets = {"dni robocze": h[h["service_date"].isin(WORK)]}
    for p_ in ("szczyt_rano", "szczyt_pop", "poza"):
        subsets[f"robocze, {p_}"] = h[
            h["service_date"].isin(WORK) & (h["period"] == p_)
        ]
    for b_ in ["(3, 6]", "(6, 10]", "(10, 20]", "(20, 60]"]:
        subsets[f"robocze, odstep {b_} min"] = h[
            h["service_date"].isin(WORK) & (h["pasmo"] == b_)
        ]
    for d_ in WORK:
        subsets[f"dzien {d_}"] = h[h["service_date"] == d_]
    rows = []
    for sn, sub in subsets.items():
        for fn, fe in specs.items():
            b, se, n, k = fe_slope(sub, "de", "e", fe, "cl")
            rows.append(
                {
                    "podzbior": sn,
                    "specyfikacja": fn,
                    "beta": b,
                    "se_klastrowy": se,
                    "t": b / se if se and se > 0 else np.nan,
                    "n": n,
                    "klastrow": k,
                }
            )
    r = pd.DataFrame(rows)
    print(r.round(4).to_string(index=False))
    m = r[(r["podzbior"] == "dni robocze") & (r["specyfikacja"].str.contains("okno"))]
    if len(m):
        KEY["gamma_beta_FE_okno_dzien"] = (
            round(float(m["beta"].iloc[0]), 4),
            round(float(m["se_klastrowy"].iloc[0]), 4),
        )


@section(
    "8. ZBIJANIE SIE: obserwacja vs model zerowy (permutacja), linie vs linie rozne"
)
def s8():
    d = HP[(HP["h_sched"] >= 180) & (HP["service_date"].isin(WORK))].copy()

    def met(h, hs):
        return pd.Series(
            {
                "n": len(h),
                "near<0.25": (h < 0.25 * hs).mean(),
                "within60s": (h < 60).mean(),
                "swapped": (h < 0).mean(),
                "far>1.75": (h > 1.75 * hs).mean(),
            }
        )

    obs_t = d.groupby("service_date").apply(
        lambda g: met(g["h_obs"], g["h_sched"]), include_groups=False
    )
    print("OBSERWACJA (ta sama linia i kierunek), wg dnia:")
    print(obs_t.round(4).to_string())

    gcode = (
        d.groupby(["service_date", "route_id", "dir", "fifth", "hour"])
        .ngroup()
        .to_numpy()
    )
    srt = np.argsort(gcode, kind="stable")
    rng = np.random.default_rng(1)
    K = 20
    acc = []
    base = d["h_sched"].to_numpy()[srt]
    cur = d["delay"].to_numpy()[srt]
    dprev = d["d_prev"].to_numpy()
    for _ in range(K):
        idx = np.lexsort((rng.random(len(d)), gcode))
        perm = dprev[idx]  # d_prev przetasowane w obrebie grupy
        h = base + cur - perm
        acc.append(
            [
                (h < 0.25 * base).mean(),
                (h < 60).mean(),
                (h < 0).mean(),
                (h > 1.75 * base).mean(),
            ]
        )
    nul = np.mean(acc, axis=0)
    o = met(d["h_obs"], d["h_sched"])
    cmp_ = pd.DataFrame(
        {
            "obserwacja": o[
                ["near<0.25", "within60s", "swapped", "far>1.75"]
            ].to_numpy(),
            "model_zerowy_perm": nul,
        },
        index=["near<0.25", "within60s", "swapped", "far>1.75"],
    )
    cmp_["obs/null"] = cmp_["obserwacja"] / cmp_["model_zerowy_perm"]
    print(
        "\nOBSERWACJA vs MODEL ZEROWY (d_prev tasowane w obrebie dzien x linia x kierunek x piata czesc trasy x godzina):"
    )
    print(cmp_.round(4).to_string())
    print(
        "obs/null > 1 oznacza nadwyzke zblizen (zbijanie ponad przypadek); model zerowy jest przyblizony, traktuj jako wskazowke."
    )
    KEY["zbijanie_obs/null_near"] = round(float(cmp_.loc["near<0.25", "obs/null"]), 2)
    KEY["zbijanie_obs/null_within60"] = round(
        float(cmp_.loc["within60s", "obs/null"]), 2
    )

    c = CP[CP["service_date"].isin(WORK)].copy()
    c["pasmo"] = pd.cut(c["h_sched"] / 60, [3, 5, 10, 20, 30])
    print(
        "\nPARY DOWOLNYCH LINII NA SLUPKU (odstep rozkladowy 3-30 min), ta sama linia vs rozne:"
    )
    print(
        c.groupby("same_route")
        .apply(lambda g: met(g["h_obs"], g["h_sched"]), include_groups=False)
        .round(4)
        .to_string()
    )
    print(
        c.groupby(["pasmo", "same_route"], observed=True)
        .apply(lambda g: met(g["h_obs"], g["h_sched"]), include_groups=False)
        .round(4)
        .to_string()
    )
    cn = c.groupby("stop_id").size()
    byname = (
        c.merge(stops[["stop_id", "stop_name"]], on="stop_id", how="left")
        .groupby("stop_name")
        .apply(lambda g: met(g["h_obs"], g["h_sched"]), include_groups=False)
        .query("n >= 100")
    )
    print("\nSLUPKI (po nazwie) Z NAJWIEKSZA KOMPRESJA within60s (n >= 100):")
    print(
        byname.sort_values("within60s", ascending=False).head(12).round(3).to_string()
    )


@section(
    "9. ZAKLOCENIA WSPOLNE u: korelacja residuow opoznien kolejnych autobusow (ta sama vs rozne linie)"
)
def s9():
    g2 = gw.sort_values(["service_date", "stop_id", "arr_ts"]).copy()
    g2["res"] = g2["delay"] - g2.groupby(["route_id", "stop_id", "period"])[
        "delay"
    ].transform("median")
    gb = g2.groupby(["service_date", "stop_id"])
    g2["res_prev"] = gb["res"].shift(1)
    g2["route_prev"] = gb["route_id"].shift(1)
    g2["gap"] = g2["arr_ts"] - gb["arr_ts"].shift(1)
    x = g2.dropna(subset=["res_prev"])
    x = x[(x["gap"] > 0) & (x["gap"] <= 2400)].copy()
    x["ta_sama_linia"] = x["route_id"] == x["route_prev"]
    x["odstep_s"] = pd.cut(x["gap"], [0, 60, 120, 300, 600, 1200, 2400])
    out = x.groupby(["ta_sama_linia", "odstep_s"], observed=True).apply(
        lambda g: pd.Series({"n": len(g), "corr": g["res"].corr(g["res_prev"])}),
        include_groups=False,
    )
    print(
        "residuum = opoznienie minus mediana (linia, slupek, pora). Korelacja kolejnych przyjazdow na slupku wg odstepu czasowego:"
    )
    print(out.round(3).to_string())
    print(
        "\nkorelacja miedzy roznymi liniami > 0 = zakloceenia wspolne dla linii (skladnik u modelu). Zanik z odstepem = skala czasowa u."
    )
    KEY["korelacja_rozne_linie_odstep<5min"] = round(
        float(
            x[(~x["ta_sama_linia"]) & (x["gap"] <= 300)]["res"].corr(
                x[(~x["ta_sama_linia"]) & (x["gap"] <= 300)]["res_prev"]
            )
        ),
        3,
    )

    def f(ax):
        for k_, g in out.reset_index().groupby("ta_sama_linia"):
            ax.plot(
                range(len(g)),
                g["corr"].values,
                marker="o",
                label="ta sama linia" if k_ else "rozne linie",
            )
            ax.set_xticks(range(len(g)))
            ax.set_xticklabels([str(i) for i in g["odstep_s"]], rotation=30, fontsize=7)
        ax.legend()
        ax.set_title("korelacja residuow wg odstepu czasowego [s]")

    plot("09_korelacja_u.png", f)

    print(
        "\nKORELACJA OPOZNIEN (nie residuow) KOLEJNYCH AUTOBUSOW TEJ SAMEJ LINII, wg linii (jak pilot_stats):"
    )
    e3 = gw.sort_values(["route_id", "stop_id", "service_date", "arr_s"]).copy()
    g3 = e3.groupby(["route_id", "stop_id", "service_date"])
    e3["prev_delay"] = g3["delay"].shift(1)
    e3["gap"] = e3["arr_s"] - g3["arr_s"].shift(1)
    pr = e3[e3["gap"].between(60, 3600)].dropna(subset=["prev_delay"])
    cl = pr.groupby("route_id").apply(
        lambda x: pd.Series(
            {
                "n": len(x),
                "corr": x["delay"].corr(x["prev_delay"]),
                "odstep_med_min": x["gap"].median() / 60,
            }
        ),
        include_groups=False,
    )
    print(
        cl.query("n >= 300")
        .sort_values("n", ascending=False)
        .head(20)
        .round(2)
        .to_string()
    )


@section(
    "10. PRZYROSTY NA ODCINKACH (dryf a_s, ogon eta, niezaleznosc przyrostow) I POSTOJE"
)
def s10():
    e2 = gw.sort_values(["service_date", "trip_id", "stop_sequence"]).copy()
    g = e2.groupby(["service_date", "trip_id"])
    e2["dd"] = g["delay"].diff()
    e2["dseq"] = g["stop_sequence"].diff()
    e2["dd_next"] = g["dd"].shift(-1)
    e2["dseq_next"] = g["dseq"].shift(-1)
    inc = e2[e2["dseq"] == 1].copy()
    f = {
        "n": "size",
        "srednia": "mean",
        "std": "std",
        "p01": lambda s: s.quantile(0.01),
        "p05": lambda s: s.quantile(0.05),
        "mediana": "median",
        "p95": lambda s: s.quantile(0.95),
        "p99": lambda s: s.quantile(0.99),
        "kurtoza": "kurt",
        "udzial_abs_gt_300": lambda s: (s.abs() > 300).mean(),
    }
    print("PRZYROST OPOZNIENIA NA ODCINKU [s], pooled:")
    print(inc["dd"].agg(**f).round(2).to_string())
    KEY["przyrost_odcinka_kurtoza"] = round(float(inc["dd"].kurt()), 1)
    KEY["przyrost_odcinka_std_s"] = round(float(inc["dd"].std()), 1)
    print("\nWG PORY DNIA (a_p):")
    print(inc.groupby("period")["dd"].agg(**f).round(2).to_string())
    print("\nWG PIATEJ CZESCI TRASY:")
    print(inc.groupby("fifth")["dd"].agg(**f).round(2).to_string())
    top = inc.groupby("route_id").size().sort_values(ascending=False).head(12).index
    print("\nWG LINII (top 12):")
    print(
        inc[inc["route_id"].isin(top)]
        .groupby("route_id")["dd"]
        .agg(**f)
        .round(2)
        .to_string()
    )
    pair = e2[(e2["dseq"] == 1) & (e2["dseq_next"] == 1)].dropna(
        subset=["dd", "dd_next"]
    )
    ac = float(pair["dd"].corr(pair["dd_next"]))
    print(
        "\nAUTOKORELACJA PRZYROSTOW w kolejnych odcinkach tego samego kursu:",
        round(ac, 3),
        " n =",
        len(pair),
    )
    print(
        "  ~0: niezalezne przyrosty (model addytywny OK); ok. -0.5: dominuje szum pomiaru czasu; > 0: trwale zaburzenia kursu."
    )
    KEY["autokorelacja_przyrostow"] = round(ac, 3)

    print(
        "\nPOSTOJE NA PRZYSTANKACH POSREDNICH (dep_ts - arr_ts, dolne ograniczenie; niepewnosc <= 15 s):"
    )
    dw = ev[
        (~ev["is_first"])
        & (~ev["is_last"])
        & (ev["arr_unc"] <= 15)
        & (ev["dep_unc"] <= 15)
        & ev["delay"].notna()
        & (ev["delay"].abs() <= MAXD)
        & ev["service_date"].isin(WORK)
    ].copy()
    dw["dwell"] = dw["dep_ts"] - dw["arr_ts"]
    print(
        dw.groupby("period")["dwell"]
        .agg(n="size", mediana="median", p90=lambda s: s.quantile(0.9))
        .round(1)
        .to_string()
    )
    dw["opoznienie_przyj"] = pd.cut(dw["delay"], [-2000, -60, 0, 120, 300, 2000])
    print("\nPOSTOJ wg opoznienia przyjazdu (zalazek skladnika pasazerskiego alpha*N):")
    print(
        dw.groupby("opoznienie_przyj", observed=True)["dwell"]
        .agg(n="size", mediana="median", p90=lambda s: s.quantile(0.9))
        .round(1)
        .to_string()
    )


@section("11. RANKING LINII I KORYTARZ WOKOL LINII PILOTOWEJ (%s)" % PILOT)
def s11():
    d = HPw[HPw["h_sched"] >= 180].copy()
    g = gw.groupby(["route_id", "dir"]).agg(
        zdarzen=("delay", "size"),
        dni=("service_date", "nunique"),
        med_opoznienie=("delay", "median"),
        std_opoznienie=("delay", "std"),
    )
    pr = d.groupby(["route_id", "dir"]).agg(
        par_ge3min=("e", "size"),
        odstep_med_min=("h_sched", lambda s: s.median() / 60),
        e_std_s=("e", "std"),
    )
    g = g.join(pr)
    print(
        "TOP 30 LINII/KIERUNKOW wg liczby zdarzen (dni robocze), kandydaci na pilota i linie walidacyjne:"
    )
    print(g.sort_values("zdarzen", ascending=False).head(30).round(1).to_string())

    sg = st[["trip_id", "stop_id", "stop_sequence"]].copy()
    sg["b"] = sg.groupby("trip_id")["stop_id"].shift(-1)
    sg = (
        sg.dropna(subset=["b"])
        .rename(columns={"stop_id": "a"})
        .merge(tr[["route_id"]], left_on="trip_id", right_index=True)
    )
    pil = sg[sg["route_id"] == PILOT][["a", "b"]].drop_duplicates()
    if pil.empty:
        print("brak odcinkow dla linii", PILOT)
        return
    oth = sg[sg["route_id"] != PILOT][["route_id", "a", "b"]].drop_duplicates()
    sh = (
        oth.merge(pil, on=["a", "b"])
        .groupby("route_id")
        .size()
        .rename("wspolne_odcinki")
        .to_frame()
    )
    sh["udzial_odcinkow_pilota"] = sh["wspolne_odcinki"] / len(pil)
    cnt = gw.groupby("route_id").agg(
        zdarzenia=("delay", "size"), dni=("service_date", "nunique")
    )
    sh = sh.join(cnt)
    sh["rola"] = np.select(
        [sh["udzial_odcinkow_pilota"] >= 0.30, sh["udzial_odcinkow_pilota"] >= 0.05],
        ["korytarz", "czesciowo wspolna (kandydat walidacyjny)"],
        "prawie niezalezna",
    )
    print(
        f"\nlinia pilotowa {PILOT}: skierowanych odcinkow {len(pil)}, zdarzen w dniach roboczych:",
        int((gw["route_id"] == PILOT).sum()),
    )
    print(
        sh.sort_values("wspolne_odcinki", ascending=False).head(20).round(3).to_string()
    )
    print(
        "\nlinie niezalezne od pilota z duza liczba zdarzen (kandydaci na walidacje spoza kalibracji):"
    )
    ind = cnt.drop(
        index=[PILOT] + list(sh.index[sh["udzial_odcinkow_pilota"] >= 0.30]),
        errors="ignore",
    )
    ind = ind.join(sh["udzial_odcinkow_pilota"]).fillna({"udzial_odcinkow_pilota": 0})
    print(ind.sort_values("zdarzenia", ascending=False).head(10).round(3).to_string())
    KEY["korytarz_pilota_linie>=30%"] = list(
        sh.index[sh["udzial_odcinkow_pilota"] >= 0.30]
    )


# =====================================================================================
for fn in (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11):
    fn()

print("\n" + "=" * 110 + "\nKLUCZOWE LICZBY DO PROJEKTU\n" + "=" * 110)
for k, v in KEY.items():
    print(f"  {k}: {v}")
print(
    """
CO Z TEGO WYNIKA DLA PLANU (sprawdz w wydruku powyzej):
  1. Sekcja 1-2: ktore dni sa pelne i bez dziur, to zbior kalibracyjny/walidacyjny (np. 3 pierwsze pelne robocze / reszta). Dziury i dni czesciowe wylacz.
  2. Sekcja 3: jesli KS miedzy dniami roboczymi jest male, dni sa wymienne i pooling jest uzasadniony.
  3. Sekcja 4-5: czy dryf, wzrost rozrzutu i dodatni slope sigma_e powtarzaja sie w kazdym dniu (nie tylko w poniedzialek) i czy kontrola ksztaltu (wykladnik p) wskazuje na wzrost nieliniowy.
  4. Sekcja 6: krzywa pochlaniania i X to centralny wynik; l_min z kalibracji i delta0 wchodza wprost do modelu petli.
  5. Sekcja 7-8: gamma i zbijanie. Wynik zerowy lub ujemny jest wynikiem. Szum pomiaru obciaza beta w dol.
  6. Sekcja 9-10: wariancja i skala czasowa u (korelacja miedzy roznymi liniami), ogon eta (kurtoza), niezaleznosc przyrostow.
  7. Sekcja 11: wybor pilota, korytarza i linii walidacyjnych na podstawie liczby zdarzen z calego tygodnia.
Raport zapisany w: %s
"""
    % (OUT / "report.txt")
)
sys.stdout = sys.__stdout__
_report.close()
