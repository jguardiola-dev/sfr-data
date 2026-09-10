#!/usr/bin/env python3
"""
sfr-data · motor de datos de SpoilerFreeRecs
- ladder.json   : histograma de rating por ladder (bins de 25) + totales, del volcado diario leaderboard.parquet de aoe2companion
- clans.json.gz : clanes con >= 2 miembros en el ladder 1v1 RM, con sus miembros (pid, nombre, rating, rango, país);
                  el clan y el país se toman del leaderboard si los trae y, si no, de profile.parquet
- sonda         : SOLO diagnóstico (no escribe nada): lista de volcados y esquema + muestra del volcado diario de
                  partidas match-AAAA-MM-DD.parquet, base del futuro civstats.json
Créditos: aoe2companion (Dennis Keil) · Age of Empires II © Microsoft.
"""
import gzip, io, json, sys, urllib.request
from datetime import datetime, timezone, timedelta

UA = "sfr-data/1.1 (+https://github.com/jguardiola-dev/SpoilerFreeRecs)"
DUMP = "https://dump.cdn.aoe2companion.com/"
DUMP_LIST = "https://data.aoe2companion.com/api/dump/list"
LADDERS = ("rm_1v1", "rm_team", "ew_1v1", "ew_team")
LADDER_NUM = {"3": "rm_1v1", "4": "rm_team", "13": "ew_1v1", "14": "ew_team"}   # por si el volcado trae ids numéricos
BIN = 25


def fetch(url, timeout=900):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def columna(nombres, *candidatas):
    """Nombre real de la primera columna candidata que exista (sin distinguir mayúsculas ni guiones bajos)."""
    norm = {c.lower().replace("_", ""): c for c in nombres}
    for c in candidatas:
        k = c.lower().replace("_", "")
        if k in norm:
            return norm[k]
    return None


def abrir_parquet(nombre):
    """Descarga un volcado, imprime tamaño / filas / columnas y devuelve el ParquetFile."""
    import pyarrow.parquet as pq
    raw = fetch(DUMP + nombre)
    pf = pq.ParquetFile(io.BytesIO(raw))
    print(f"ladder: {nombre}: {len(raw) / 1e6:.0f} MB, {pf.metadata.num_rows:,} filas, columnas: {pf.schema_arrow.names}", flush=True)
    return pf


def ladder():
    import numpy as np
    import pandas as pd

    pf = abrir_parquet("leaderboard.parquet")
    nombres = pf.schema_arrow.names
    c_lb = columna(nombres, "leaderboard_id", "leaderboard", "leaderboardId")
    c_pid = columna(nombres, "profile_id", "profileId")
    c_name = columna(nombres, "name")
    c_rating = columna(nombres, "rating")
    c_rank = columna(nombres, "rank")
    c_country = columna(nombres, "country", "countryCode")
    c_clan = columna(nombres, "clan", "clanTag")
    if not (c_lb and c_pid and c_rating):
        raise RuntimeError(f"faltan columnas: leaderboard={c_lb} profile={c_pid} rating={c_rating}")
    cols = [c for c in (c_lb, c_pid, c_name, c_rating, c_rank, c_country, c_clan) if c]
    df = pf.read(columns=cols).to_pandas()
    del pf

    # ladder: acepta 'rm_1v1'… o ids numéricos 3/4/13/14
    lb = df[c_lb].astype(str).str.strip().str.lower().str.replace(r"\.0$", "", regex=True).map(lambda s: LADDER_NUM.get(s, s))
    print("ladder: valores de leaderboard:", lb.value_counts().head(15).to_dict(), flush=True)
    df = df.assign(_lb=lb, _rating=pd.to_numeric(df[c_rating], errors="coerce").fillna(0).astype(int))
    df = df[df["_lb"].isin(LADDERS)]

    out = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bin": BIN, "ladders": {}}
    for nombre in LADDERS:
        r = df.loc[df["_lb"] == nombre, "_rating"].to_numpy()
        if r.size == 0:
            print(f"ladder: {nombre}: sin filas", flush=True)
            continue
        lo = int(r.min() // BIN * BIN)
        hi = int(r.max() // BIN * BIN + BIN)
        bins = np.bincount((r - lo) // BIN, minlength=(hi - lo) // BIN + 1).tolist()
        s = np.sort(r)
        pct = {str(p): int(s[min(s.size - 1, int(s.size * p / 100))]) for p in (10, 25, 50, 75, 90, 95, 99)}
        out["ladders"][nombre] = {"total": int(s.size), "min": lo, "bins": bins, "mediana": int(s[s.size // 2]), "percentiles": pct}
        print(f"ladder: {nombre}: {s.size:,} jugadores, mediana {pct['50']}", flush=True)
    with open("ladder.json", "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    # clanes (1v1 RM): el clan/país vienen del leaderboard o, si no los trae, de profile.parquet
    sub = df[df["_lb"] == "rm_1v1"].copy()
    del df
    sub[c_pid] = pd.to_numeric(sub[c_pid], errors="coerce")
    if not c_clan:
        pfp = abrir_parquet("profile.parquet")
        pn = pfp.schema_arrow.names
        p_pid = columna(pn, "profile_id", "profileId")
        p_clan = columna(pn, "clan", "clanTag")
        p_country = None if c_country else columna(pn, "country", "countryCode")
        if p_pid and p_clan:
            pr = pfp.read(columns=[c for c in (p_pid, p_clan, p_country) if c]).to_pandas()
            pr = pr.rename(columns={p_pid: c_pid, p_clan: "_clan", **({p_country: "_country"} if p_country else {})})
            pr[c_pid] = pd.to_numeric(pr[c_pid], errors="coerce")
            pr = pr.dropna(subset=[c_pid]).drop_duplicates(subset=[c_pid])
            sub = sub.merge(pr, on=c_pid, how="left")
            c_clan = "_clan"
            if p_country:
                c_country = "_country"
        else:
            print("ladder: AVISO: profile.parquet no trae clan; clans.json.gz saldrá vacío", flush=True)
        del pfp
    clans = {}
    if c_clan:
        sub = sub.assign(_c=sub[c_clan].fillna("").astype(str).str.strip())
        sub = sub[(sub["_c"] != "") & sub[c_pid].notna()].sort_values("_rating", ascending=False)
        tabla = pd.DataFrame({
            "tag": sub["_c"],
            "pid": sub[c_pid].astype("int64"),
            "nombre": sub[c_name].fillna("").astype(str) if c_name else "",
            "rating": sub["_rating"],
            "rango": pd.to_numeric(sub[c_rank], errors="coerce").fillna(0).astype(int) if c_rank else 0,
            "pais": sub[c_country].fillna("").astype(str) if c_country else "",
        })
        for tag, g in tabla.groupby("tag", sort=False):
            if len(g) < 2:
                continue
            clans[tag] = [[int(a), b, int(c), int(d), e] for a, b, c, d, e in zip(g["pid"], g["nombre"], g["rating"], g["rango"], g["pais"])]
    with gzip.open("clans.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"generado": out["generado"], "ladder": "rm_1v1", "clans": clans}, f, separators=(",", ":"))
    print(f"ladder: {len(clans):,} clanes con 2+ miembros", flush=True)


def sonda_partidas():
    """Solo diagnóstico: cómo es el volcado diario de partidas del companion. No escribe ningún archivo."""
    import pyarrow.parquet as pq
    try:
        lst = fetch(DUMP_LIST, timeout=60).decode("utf-8", "replace")
        print("sonda: /api/dump/list:", lst[:1500], flush=True)
    except Exception as ex:
        print(f"sonda: /api/dump/list falló: {ex!r}", flush=True)
    for dias in (1, 2, 3):
        fecha = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")
        nombre = f"match-{fecha}.parquet"
        try:
            raw = fetch(DUMP + nombre, timeout=300)
        except Exception as ex:
            print(f"sonda: {nombre} no disponible: {ex!r}", flush=True)
            continue
        pf = pq.ParquetFile(io.BytesIO(raw))
        print(f"sonda: {nombre}: {len(raw) / 1e6:.1f} MB, {pf.metadata.num_rows:,} filas, {pf.metadata.num_row_groups} row groups", flush=True)
        print("sonda: esquema:\n" + str(pf.schema_arrow), flush=True)
        for fila in pf.read_row_group(0).slice(0, 3).to_pylist():
            print("sonda: fila:", json.dumps(fila, default=str, ensure_ascii=False)[:1500], flush=True)
        break


if __name__ == "__main__":
    ok = True
    try:
        ladder()
    except Exception as ex:
        ok = False
        print(f"ladder: ERROR {ex!r}", flush=True)
    try:
        sonda_partidas()
    except Exception as ex:
        print(f"sonda: ERROR {ex!r}", flush=True)
    sys.exit(0 if ok else 1)
