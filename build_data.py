#!/usr/bin/env python3
"""
sfr-data · motor de datos de SpoilerFreeRecs
- ladder.json   : histograma de rating por ladder (bins de 25) + totales (del volcado diario de aoe2companion)
- clans.json.gz : clanes con >= 2 miembros en el ladder 1v1 RM, con sus miembros (pid, nombre, rating, rango, país)
- civstats.json : winrate / pick rate por civ x mapa x tramo de ELO x modo (de los volcados semanales de aoestats)
Créditos: aoe2companion (Dennis Keil) · aoestats (jerbot) · Age of Empires II © Microsoft.
"""
import gzip, io, json, os, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

UA = "sfr-data/1.0 (+https://github.com/jguardiola-dev/SpoilerFreeRecs)"
COMPANION_DUMP = "https://dump.cdn.aoe2companion.com/leaderboard.parquet"
AOESTATS_LIST = "https://aoestats.io/api/db_dumps"
LADDERS = {3: "rm_1v1", 4: "rm_team", 13: "ew_1v1", 14: "ew_team"}
BIN = 25

def fetch(url, binary=True, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read() if binary else r.read().decode("utf-8")

def ladder():
    import pandas as pd
    print("ladder: descargando leaderboard.parquet…", flush=True)
    raw = fetch(COMPANION_DUMP)
    df = pd.read_parquet(io.BytesIO(raw))
    print(f"ladder: {len(df):,} filas, columnas: {list(df.columns)[:12]}…", flush=True)
    df["leaderboard_id"] = pd.to_numeric(df["leaderboard_id"], errors="coerce")
    df = df[df["leaderboard_id"].isin(LADDERS.keys())].copy()
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0).astype(int)
    out = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bin": BIN, "ladders": {}}
    for lid, nombre in LADDERS.items():
        sub = df[df["leaderboard_id"] == lid]
        if sub.empty:
            continue
        ratings = sub["rating"].to_numpy()
        lo = int(ratings.min() // BIN * BIN)
        hi = int(ratings.max() // BIN * BIN + BIN)
        bins = [0] * ((hi - lo) // BIN + 1)
        for r in ratings:
            bins[min(len(bins) - 1, (int(r) - lo) // BIN)] += 1
        s = sorted(ratings)
        pct = {p: int(s[min(len(s) - 1, int(len(s) * p / 100))]) for p in (10, 25, 50, 75, 90, 95, 99)}
        out["ladders"][nombre] = {"total": int(len(s)), "min": lo, "bins": bins, "mediana": int(s[len(s) // 2]), "percentiles": pct}
        print(f"ladder: {nombre}: {len(s):,} jugadores, mediana {pct[50]}", flush=True)
    with open("ladder.json", "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    # clanes (ladder 1v1 RM): tag -> miembros
    sub = df[df["leaderboard_id"] == 3].copy()
    col_clan = "clan" if "clan" in sub.columns else None
    clans = {}
    if col_clan:
        sub[col_clan] = sub[col_clan].fillna("").astype(str).str.strip()
        sub = sub[sub[col_clan] != ""]
        cols = {c: c for c in ("profile_id", "name", "rating", "rank", "country") if c in sub.columns}
        for tag, g in sub.groupby(col_clan):
            if len(g) < 2:
                continue
            g = g.sort_values("rating", ascending=False)
            miembros = []
            for _, r in g.iterrows():
                miembros.append([int(r["profile_id"]), str(r["name"]), int(r["rating"]), int(r["rank"]) if "rank" in cols and str(r["rank"]) not in ("nan", "") else 0,
                                 str(r["country"]) if "country" in cols else ""])
            clans[tag] = miembros
    with gzip.open("clans.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"generado": out["generado"], "ladder": "rm_1v1", "clans": clans}, f, separators=(",", ":"))
    print(f"ladder: {len(clans):,} clanes con 2+ miembros", flush=True)

def civstats():
    """Últimas ~8 semanas de aoestats: winrate/pickrate por civ x mapa x tramo x modo."""
    import pandas as pd
    lst = json.loads(fetch(AOESTATS_LIST, binary=False))
    dumps = lst if isinstance(lst, list) else lst.get("db_dumps") or lst.get("dumps") or lst.get("results") or []
    # cada entrada trae rutas a players/matches parquet; nos quedamos con las 8 más recientes
    def url_de(d, k):
        v = d.get(k) or d.get(k + "_url") or d.get(k + "Url")
        if not v:
            return None
        return v if v.startswith("http") else "https://aoestats.io" + v
    dumps = sorted(dumps, key=lambda d: str(d.get("start_date") or d.get("date_range") or d.get("id") or ""), reverse=True)[:8]
    tramos = [(0, 800), (800, 1000), (1000, 1200), (1200, 1400), (1400, 1600), (1600, 1800), (1800, 2000), (2000, 9999)]
    def tramo(e):
        for lo, hi in tramos:
            if lo <= e < hi:
                return f"{lo}-{hi if hi < 9999 else '+'}"
        return "?"
    agg = defaultdict(lambda: [0, 0])   # (modo, mapa, tramo, civ) -> [partidas, victorias]
    total_partidas = 0
    for d in dumps:
        mu, pu = url_de(d, "matches"), url_de(d, "players")
        if not mu or not pu:
            print("civstats: entrada sin rutas:", list(d.keys()), flush=True)
            continue
        print("civstats:", d.get("start_date") or d.get("date_range"), flush=True)
        m = pd.read_parquet(io.BytesIO(fetch(mu)))
        p = pd.read_parquet(io.BytesIO(fetch(pu)))
        m = m[m.get("mirror", False) == False] if "mirror" in m.columns else m
        modo = m["leaderboard"].astype(str) if "leaderboard" in m.columns else pd.Series(["?"] * len(m))
        m = m.assign(modo=modo.map(lambda s: "1v1" if "1v1" in s.lower() else ("team" if "team" in s.lower() else s)))
        m = m[["game_id", "map", "avg_elo", "modo"]]
        p = p[["game_id", "civ", "winner"]] if "winner" in p.columns else p[["game_id", "civ", "won"]].rename(columns={"won": "winner"})
        j = p.merge(m, on="game_id", how="inner")
        total_partidas += len(m)
        for row in j.itertuples(index=False):
            k = (row.modo, str(row.map), tramo(float(row.avg_elo) if row.avg_elo == row.avg_elo else 0), str(row.civ))
            a = agg[k]
            a[0] += 1
            if bool(row.winner):
                a[1] += 1
    filas = []
    for (modo, mapa, tr, civ), (n, w) in agg.items():
        if n >= 20:
            filas.append([modo, mapa, tr, civ, n, w])
    out = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "semanas": len(dumps), "partidas": int(total_partidas),
           "tramos": [f"{lo}-{hi if hi < 9999 else '+'}" for lo, hi in tramos], "filas": filas,
           "credito": "aoestats.io (jerbot) · Age of Empires II © Microsoft"}
    with open("civstats.json", "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"civstats: {len(filas):,} combinaciones, {total_partidas:,} partidas", flush=True)

if __name__ == "__main__":
    ok = True
    for nombre, fn in (("ladder", ladder), ("civstats", civstats)):
        try:
            fn()
        except Exception as ex:
            ok = False
            print(f"{nombre}: ERROR {ex!r}", flush=True)
    sys.exit(0 if ok else 1)
