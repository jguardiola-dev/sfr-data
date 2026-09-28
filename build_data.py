#!/usr/bin/env python3
"""
sfr-data 1.2 · motor de datos de SpoilerFreeRecs (aoe2radar)

Salidas en la raíz del repo:
- ladder.json        campanas de rating por ladder (bins de 25). «ladders» = todos los jugadores; «activos» = solo los que
                     tienen >= 10 partidas en ese ladder y una en los últimos 28 días. Total, mediana y percentiles.
- clans.json.gz      clanes con >= 2 miembros en 1v1 RM: [pid, nombre, rating, rango, país]. Clan y país de profile.parquet.
- dispersion.json.gz rejilla rating 1v1 × rating equipos (parejas RM y EW), para todos y para activos, con recta y correlación.
- civstats/          estadísticas de civs a partir de los volcados DIARIOS de partidas del companion:
    dias/AAAA-MM-DD.json.gz   resumen de un día: civs por modo×mapa×tramo, matchups 1v1 por tramo (y por mapa×tramo), mapas, contadores
    ventanas/vN.json.gz       suma de los últimos N días (7, 30, 90, 365) y vparche.json.gz = solo el parche actual;
                              «matchups» = todos los mapas; «matchups_mapa» = por mapa (1v1, mapas con >= MIN_PARTIDAS_CIV)
    tendencias.json.gz        winrate por mes y civ (13 meses); por mapa (12 mapas más jugados por modo); por tramo de ELO; por mapa×tramo (modos 1v1)
    estado.json               días procesados y parches vistos
En la release «perfiles» (ver perfiles()): index.json, paquetes y deltas, elo_ayer.json.gz / elo-AAAA-MM-DD.json.gz (v2: + rango y
última partida 1v1), muestra_ayer.json.gz (v2: 1.000 por tramo + «tramos_anteayer») y chispas.json.gz (1.6: últimos ratings 1v1).
Fuente: volcados diarios de aoe2companion (https://www.aoe2companion.com/more/api).
Créditos: aoe2companion (Dennis Keil) · Age of Empires II © Microsoft.
"""
import gzip, io, json, os, sys, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

UA = "sfr-data/1.6.0 (+https://github.com/jguardiola-dev/aoe2radar)"
DUMP = "https://dump.cdn.aoe2companion.com/"
BIN = 25
LADDERS = ("rm_1v1", "rm_team", "ew_1v1", "ew_team")
LADDER_NUM = {"3": "rm_1v1", "4": "rm_team", "13": "ew_1v1", "14": "ew_team"}
PAREJAS = {"rm": ("rm_1v1", "rm_team"), "ew": ("ew_1v1", "ew_team")}
ACTIVO_MIN_PARTIDAS = 1      # «activo» = al menos una partida en el ladder y una en los últimos 28 días (convención habitual en la comunidad; el companion no publica percentiles)
ACTIVO_DIAS = 28

DIR_CIV = "civstats"
DIR_DIAS = os.path.join(DIR_CIV, "dias")
DIR_VENT = os.path.join(DIR_CIV, "ventanas")
DIAS_HISTORICO = 365            # cuántos días hacia atrás se rellenan
# perfiles precalculados (release «perfiles» del repo): registro de partidas del último año por jugador, en 256 paquetes por pid
PERFILES_SHARDS = 256           # paquetes por jugador (pid % 256): GitHub limita a ~500 subidas por hora, así que 256 paquetes (≈5 MB al año) es el máximo práctico por consolidación
PERFILES_GRUPOS = 16            # los deltas diarios van por grupo de paquetes (shard % 16): 16 archivos pequeños por día
PERFILES_CONSOLIDAR_DIAS = 7    # los paquetes base se reescriben cuando hay 7 deltas (una vez por semana); entre medias, solo deltas
LADDERS_IDX = ["rm_1v1", "rm_team", "ew_1v1", "ew_team", "dm_1v1", "dm_team"]
PERFILES_DIAS = 365
PERFILES_DIAS_POR_NOCHE = 45    # relleno hacia atrás: cada ejecución entran 45 días más hasta cubrir el año (y siempre el día nuevo)
PERFILES_ACTIVO_DIAS = 28       # alcance: todo jugador con partida en los últimos 28 días en cualquier ladder (≈100.000); por debajo de eso nadie lo busca
PERFILES_TOP_1V1 = 40000        # nivel 1 (año completo): top 40.000 1v1 + top 20.000 equipos; el resto de activos, 90 días (PERFILES_DIAS_RESTO)
PERFILES_TOP_TEAM = 20000
PERFILES_DIAS_RESTO = 365       # formato compacto + deltas: el año completo para todos los activos
PERFILES_RELEASE = "perfiles"
ELO_TOP_1V1 = 40000             # elo_ayer / índice de nombres: más amplio que los perfiles (barato): top 40.000 1v1 + top 20.000 equipos
ELO_TOP_TEAM = 20000
MUESTRA_POR_TRAMO = 1000        # partidas 1v1 RM al azar por tramo de ELO del volcado de ayer (Al azar por ELO y Guess the ELO sin API); 300 hasta la 1.3
PERFILES_DIR = "perfiles"
REPO = os.environ.get("GITHUB_REPOSITORY", "jguardiola-dev/sfr-data")
DIAS_RETENCION = 400            # los resúmenes diarios más antiguos se borran
DIAS_MAX_POR_EJECUCION = 400
TIEMPO_MAX_S = 200 * 60         # presupuesto de tiempo para procesar días en una ejecución
VENTANAS = (7, 30, 90, 365)
MESES_TENDENCIAS = 13
MAPAS_TENDENCIAS = 12          # tendencias por mapa solo para los mapas más jugados de cada modo
TRAMOS = [(0, 800), (800, 1000), (1000, 1200), (1200, 1400), (1400, 1600), (1600, 1800), (1800, 2000), (2000, 99999)]
MIN_DURACION_S = 120            # partidas más cortas = abandonos: fuera del winrate
MIN_PARTIDAS_CIV = 20           # matchups por mapa solo de los mapas con al menos estas partidas en la ventana (el mismo umbral que el combo de mapas de la app: CalculoStats.MIN_PARTIDAS_CIV)
MM_RELLENO_POR_NOCHE = 30       # días antiguos (sin matchups por mapa) que se vuelven a resumir cada ejecución, del más reciente al más viejo
MODOS_FUENTE = {"rm_1v1", "rm_team", "ew_1v1", "ew_team", "dm_1v1", "dm_team"}
EQUIPOS_RM = {4: "rm_2v2", 6: "rm_3v3", 8: "rm_4v4"}
NOMBRES_MAPA_FIJOS = {"megarandom": "MegaRandom", "kotd": "King of the Desert", "socotra": "Socotra", "mega-random": "MegaRandom"}
API = "https://data.aoe2companion.com/api"
MAPAS_PAGINAS = 4               # páginas de partidas recientes por ladder para aprender las imágenes de mapa (pocas llamadas al día)
MAPAS_LADDERS = ("rm_1v1", "rm_team", "ew_1v1")


# ----------------------------------------------------------------------------- utilidades
def log(*a):
    print(*a, flush=True)


def fetch(url, timeout=900, intentos=3):
    """Descarga con reintentos. Devuelve None si el archivo no existe (404)."""
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                return None
            if i == intentos - 1:
                raise
        except Exception:
            if i == intentos - 1:
                raise
        time.sleep(5 * (i + 1))


def columna(nombres, *candidatas):
    norm = {c.lower().replace("_", ""): c for c in nombres}
    for c in candidatas:
        k = c.lower().replace("_", "")
        if k in norm:
            return norm[k]
    return None


def abrir_parquet(raw, etiqueta):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(io.BytesIO(raw))
    log(f"{etiqueta}: {len(raw) / 1e6:.1f} MB, {pf.metadata.num_rows:,} filas, columnas: {pf.schema_arrow.names}")
    return pf


def tabla_texto(tabla):
    """Las columnas binary del volcado pasan a string."""
    import pyarrow as pa, pyarrow.compute as pc
    for i, campo in enumerate(tabla.schema):
        if pa.types.is_binary(campo.type) or pa.types.is_large_binary(campo.type):
            tabla = tabla.set_column(i, campo.name, pc.cast(tabla.column(i), pa.string()))
    return tabla


def a_fecha_utc(serie):
    """lastMatchTime puede venir como timestamp, epoch (s o ms) o texto."""
    import pandas as pd
    if pd.api.types.is_datetime64_any_dtype(serie):
        s = pd.to_datetime(serie, utc=True, errors="coerce")
    elif pd.api.types.is_numeric_dtype(serie):
        v = pd.to_numeric(serie, errors="coerce")
        unidad = "ms" if v.max() > 1e11 else "s"
        s = pd.to_datetime(v, unit=unidad, utc=True, errors="coerce")
    else:
        s = pd.to_datetime(serie, utc=True, errors="coerce")
    return s


def histograma(r):
    import numpy as np
    r = np.asarray(r, dtype="int64")
    if r.size == 0:
        return None
    lo = int(r.min() // BIN * BIN)
    hi = int(r.max() // BIN * BIN + BIN)
    bins = np.bincount((r - lo) // BIN, minlength=(hi - lo) // BIN + 1).tolist()
    s = np.sort(r)
    pct = {str(p): int(s[min(s.size - 1, int(s.size * p / 100))]) for p in (10, 25, 50, 75, 90, 95, 99)}
    return {"total": int(s.size), "min": lo, "bins": bins, "mediana": int(s[s.size // 2]), "percentiles": pct}


def escribir_json(ruta, obj):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    if ruta.endswith(".gz"):
        with gzip.open(ruta, "wt", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    else:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)


def leer_json(ruta, defecto=None):
    if not os.path.exists(ruta):
        return defecto
    if ruta.endswith(".gz"):
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------- ladder, clanes, dispersión
def ladder():
    import numpy as np
    import pandas as pd

    pf = abrir_parquet(fetch(DUMP + "leaderboard.parquet"), "ladder: leaderboard.parquet")
    nombres = pf.schema_arrow.names
    c_lb = columna(nombres, "leaderboard_id", "leaderboard", "leaderboardId")
    c_pid = columna(nombres, "profile_id", "profileId")
    c_name = columna(nombres, "name")
    c_rating = columna(nombres, "rating")
    c_rank = columna(nombres, "rank")
    c_country = columna(nombres, "country", "countryCode")
    c_clan = columna(nombres, "clan", "clanTag")
    c_games = columna(nombres, "games")
    c_last = columna(nombres, "lastMatchTime", "last_match_time", "lastMatch")
    if not (c_lb and c_pid and c_rating):
        raise RuntimeError(f"faltan columnas: leaderboard={c_lb} profile={c_pid} rating={c_rating}")
    cols = [c for c in (c_lb, c_pid, c_name, c_rating, c_rank, c_country, c_clan, c_games, c_last) if c]
    df = pf.read(columns=cols).to_pandas()
    del pf

    lb = df[c_lb].astype(str).str.strip().str.lower().str.replace(r"\.0$", "", regex=True).map(lambda s: LADDER_NUM.get(s, s))
    log("ladder: valores de leaderboard:", lb.value_counts().head(15).to_dict())
    df = df.assign(_lb=lb, _rating=pd.to_numeric(df[c_rating], errors="coerce").fillna(0).astype(int))
    df = df[df["_lb"].isin(LADDERS)].copy()
    df[c_pid] = pd.to_numeric(df[c_pid], errors="coerce")
    df = df.dropna(subset=[c_pid])
    df[c_pid] = df[c_pid].astype("int64")

    # activos: >= 10 partidas en ese ladder y una en los últimos 28 días
    if c_games and c_last:
        partidas = pd.to_numeric(df[c_games], errors="coerce").fillna(0)
        ultima = a_fecha_utc(df[c_last])
        limite = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=ACTIVO_DIAS)
        df["_activo"] = ((partidas >= ACTIVO_MIN_PARTIDAS) & (ultima >= limite)).fillna(False).astype(bool)
        log(f"ladder: activos {int(df['_activo'].sum()):,} de {len(df):,} filas (última partida legible en {int(ultima.notna().sum()):,})")
    else:
        df["_activo"] = True
        log("ladder: AVISO sin columnas games/lastMatchTime: «activos» = todos")

    out = {"generado": ahora(), "bin": BIN, "activos_def": {"min_partidas": ACTIVO_MIN_PARTIDAS, "dias": ACTIVO_DIAS}, "ladders": {}, "activos": {}}
    for nombre in LADDERS:
        sub = df[df["_lb"] == nombre]
        h = histograma(sub["_rating"].to_numpy())
        ha = histograma(sub.loc[sub["_activo"], "_rating"].to_numpy())
        if h is None:
            log(f"ladder: {nombre}: sin filas")
            continue
        out["ladders"][nombre] = h
        if ha is not None:
            out["activos"][nombre] = ha
        log(f"ladder: {nombre}: {h['total']:,} jugadores (mediana {h['mediana']}), activos {ha['total'] if ha else 0:,} (mediana {ha['mediana'] if ha else '-'})")
    escribir_json("ladder.json", out)

    # dispersión: rating 1v1 × rating equipos por jugador
    disp = {"generado": out["generado"], "bin": BIN, "activos_def": out["activos_def"], "parejas": {}}
    for clave, (lx, ly) in PAREJAS.items():
        a = df.loc[df["_lb"] == lx, [c_pid, "_rating", "_activo"]].rename(columns={"_rating": "x", "_activo": "ax"})
        b = df.loc[df["_lb"] == ly, [c_pid, "_rating", "_activo"]].rename(columns={"_rating": "y", "_activo": "ay"})
        j = a.merge(b, on=c_pid, how="inner")
        j = j[(j["x"] > 0) & (j["y"] > 0)]
        if len(j) < 100:
            log(f"dispersion: {clave}: solo {len(j)} jugadores en ambos ladders, se omite")
            continue
        pareja = {"x": lx, "y": ly}
        for etiqueta, sel in (("todos", j), ("activos", j[j["ax"] & j["ay"]])):
            if len(sel) < 100:
                continue
            x = sel["x"].to_numpy(dtype="int64"); y = sel["y"].to_numpy(dtype="int64")
            mx, my = int(x.min() // BIN * BIN), int(y.min() // BIN * BIN)
            ix = (x - mx) // BIN; iy = (y - my) // BIN
            celdas = pd.DataFrame({"i": ix, "j": iy}).value_counts().reset_index(name="n")
            a1, b1 = np.polyfit(x, y, 1)
            r = float(np.corrcoef(x, y)[0, 1])
            pareja[etiqueta] = {"n": int(len(sel)), "min_x": mx, "min_y": my,
                                "celdas": [[int(i), int(k), int(n)] for i, k, n in zip(celdas["i"], celdas["j"], celdas["n"])],
                                "recta": {"a": round(float(a1), 5), "b": round(float(b1), 2), "r": round(r, 4)}}
            log(f"dispersion: {clave} {etiqueta}: {len(sel):,} jugadores, {len(celdas):,} celdas, y = {a1:.3f}·x + {b1:.0f}, r = {r:.3f}")
        disp["parejas"][clave] = pareja
    escribir_json("dispersion.json.gz", disp)

    # clanes (1v1 RM): clan y país del leaderboard o, si no los trae, de profile.parquet
    sub = df[df["_lb"] == "rm_1v1"].copy()
    del df
    if not c_clan:
        pfp = abrir_parquet(fetch(DUMP + "profile.parquet"), "ladder: profile.parquet")
        pn = pfp.schema_arrow.names
        p_pid = columna(pn, "profile_id", "profileId")
        p_clan = columna(pn, "clan", "clanTag")
        p_country = None if c_country else columna(pn, "country", "countryCode")
        if p_pid and p_clan:
            pr = pfp.read(columns=[c for c in (p_pid, p_clan, p_country) if c]).to_pandas()
            pr = pr.rename(columns={p_pid: c_pid, p_clan: "_clan", **({p_country: "_country"} if p_country else {})})
            pr[c_pid] = pd.to_numeric(pr[c_pid], errors="coerce")
            pr = pr.dropna(subset=[c_pid]).drop_duplicates(subset=[c_pid])
            pr[c_pid] = pr[c_pid].astype("int64")
            sub = sub.merge(pr, on=c_pid, how="left")
            c_clan = "_clan"
            if p_country:
                c_country = "_country"
        else:
            log("ladder: AVISO: profile.parquet no trae clan; clans.json.gz saldrá vacío")
        del pfp
    clans = {}
    if c_clan:
        sub = sub.assign(_c=sub[c_clan].fillna("").astype(str).str.strip())
        sub = sub[sub["_c"] != ""].sort_values("_rating", ascending=False)
        tabla = pd.DataFrame({
            "tag": sub["_c"], "pid": sub[c_pid].astype("int64"),
            "nombre": sub[c_name].fillna("").astype(str) if c_name else "",
            "rating": sub["_rating"],
            "rango": pd.to_numeric(sub[c_rank], errors="coerce").fillna(0).astype(int) if c_rank else 0,
            "pais": sub[c_country].fillna("").astype(str) if c_country else "",
        })
        for tag, g in tabla.groupby("tag", sort=False):
            if len(g) < 2:
                continue
            clans[tag] = [[int(a), b, int(c), int(d), e] for a, b, c, d, e in zip(g["pid"], g["nombre"], g["rating"], g["rango"], g["pais"])]
    escribir_json("clans.json.gz", {"generado": out["generado"], "ladder": "rm_1v1", "clans": clans})
    log(f"ladder: {len(clans):,} clanes con 2+ miembros")


# ----------------------------------------------------------------------------- civstats
def tramo_de(rating):
    if rating != rating:   # NaN
        return "?"
    for lo, hi in TRAMOS:
        if lo <= rating < hi:
            return f"{lo}-{hi}" if hi < 99999 else f"{lo}+"
    return "?"


def nombre_mapa(clave):
    k = clave
    for pref in ("rm_", "cm_", "ew_", "dm_"):
        if k.startswith(pref):
            k = k[len(pref):]
            break
    if k in NOMBRES_MAPA_FIJOS:
        return NOMBRES_MAPA_FIJOS[k]
    return " ".join(p.capitalize() for p in k.replace("_", "-").split("-"))


# ----------------------------------------------------------------------------- mapas
def mapas():
    """mapas.json: imagen de cada mapa (URL del CDN del companion), aprendida de unas pocas páginas de partidas recientes.
    Se acumula con lo ya publicado, así los mapas nuevos entran solos en cuanto se juegan."""
    previo = leer_json("mapas.json", {}) or {}
    conocidos = dict(previo.get("mapas", {}))
    nuevos = 0
    for lb in MAPAS_LADDERS:
        for pag in range(1, MAPAS_PAGINAS + 1):
            try:
                raw = fetch(f"{API}/matches?leaderboard_ids={lb}&page={pag}&per_page=50", timeout=60)
                if raw is None:
                    break
                partidas = json.loads(raw.decode("utf-8")).get("matches", [])
            except Exception as ex:
                log(f"mapas: {lb} página {pag}: {ex!r}")
                break
            for m in partidas:
                url = m.get("mapImageUrl") or m.get("map_image_url")
                if not isinstance(url, str) or not url.startswith("http"):
                    continue
                for clave in (m.get("map"), m.get("mapName") or m.get("map_name")):
                    if isinstance(clave, str) and clave.strip():
                        k = clave.strip().lower()
                        if conocidos.get(k) != url:
                            conocidos[k] = url
                            nuevos += 1
            if len(partidas) < 50:
                break
            time.sleep(1)
    escribir_json("mapas.json", {"generado": ahora(), "mapas": dict(sorted(conocidos.items())), "credito": "aoe2companion.com (Dennis Keil) · Age of Empires II © Microsoft"})
    log(f"mapas: {len(conocidos)} entradas ({nuevos} nuevas o cambiadas)")


def resumir_dia(fecha, raw):
    """Resumen de un volcado diario de partidas (una fila por jugador y partida)."""
    import numpy as np
    import pandas as pd

    pf = abrir_parquet(raw, f"civstats: match-{fecha}.parquet")
    nombres = set(pf.schema_arrow.names)
    deseadas = ["matchId", "started", "finished", "leaderboard", "map", "patch", "rating", "won", "civ", "status", "team"]
    cols = [c for c in deseadas if c in nombres]
    for obligatoria in ("matchId", "started", "finished", "leaderboard", "map", "rating", "won", "civ"):
        if obligatoria not in nombres:
            raise RuntimeError(f"match-{fecha}.parquet sin columna {obligatoria}")
    df = tabla_texto(pf.read(columns=cols)).to_pandas()
    del pf
    if "status" in df.columns:
        df = df[df["status"].fillna("player") == "player"]
    df = df[df["leaderboard"].isin(MODOS_FUENTE)].copy()
    df = df[df["civ"].fillna("unknown") != "unknown"]
    df["won"] = df["won"].astype("boolean").fillna(False).astype(bool)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df.loc[df["rating"] <= 0, "rating"] = np.nan
    df["patch"] = pd.to_numeric(df["patch"], errors="coerce") if "patch" in df.columns else np.nan

    g = df.groupby("matchId", sort=False)
    m = pd.DataFrame({
        "n": g.size(),
        "lb": g["leaderboard"].first(),
        "mapa": g["map"].first(),
        "parche": g["patch"].first(),
        "ini": g["started"].first(),
        "fin": g["finished"].first(),
        "ncivs": g["civ"].nunique(),
        "gan": g["won"].max(),
        "rating": g["rating"].mean(),
    })
    m["dur"] = (pd.to_datetime(m["fin"], utc=True) - pd.to_datetime(m["ini"], utc=True)).dt.total_seconds()

    def modo_de(lb, n):
        if lb.endswith("_1v1"):
            return lb if n == 2 else None
        if lb == "rm_team":
            return EQUIPOS_RM.get(n)
        return lb if n in (4, 6, 8) else None   # ew_team, dm_team
    m["modo"] = [modo_de(lb, n) for lb, n in zip(m["lb"], m["n"])]
    m = m[m["modo"].notna()].copy()
    m["espejo"] = m["ncivs"] <= 1
    m["corto"] = m["dur"].fillna(0) < MIN_DURACION_S
    m["valida"] = m["gan"] & ~m["espejo"] & ~m["corto"]
    m["tramo"] = [tramo_de(r) for r in m["rating"]]

    parche = int(m["parche"].mode().iloc[0]) if m["parche"].notna().any() else None
    modos = {}
    for modo, gm in m.groupby("modo"):
        modos[modo] = {"partidas": int(gm["valida"].sum()), "abandonos": int(gm["corto"].sum()), "espejos": int(gm["espejo"].sum()),
                       "sin_resultado": int((~gm["gan"]).sum())}
    v = m[m["valida"]]
    mapas = [[modo, mapa, int(n)] for (modo, mapa), n in v.groupby(["modo", "mapa"]).size().items()]

    filas = df.merge(v[["modo", "mapa", "tramo", "dur"]], left_on="matchId", right_index=True, how="inner")
    agg = filas.groupby(["modo", "mapa", "tramo", "civ"]).agg(n=("won", "size"), w=("won", "sum"), d=("dur", "sum"))
    civs = [[modo, mapa, tramo, civ, int(n), int(w), int(d)] for (modo, mapa, tramo, civ), n, w, d in
            zip(agg.index, agg["n"], agg["w"], agg["d"])]

    matchups, matchups_mapa = matchups_de(filas)

    total = sum(x["partidas"] for x in modos.values())
    log(f"civstats: {fecha}: parche {parche}, {total:,} partidas válidas, {len(civs):,} filas civ, {len(matchups):,} matchups ({len(matchups_mapa):,} por mapa), modos {sorted(modos)}")
    return {"fecha": fecha, "parche": parche, "modos": modos, "mapas": mapas, "civs": civs, "matchups": matchups, "matchups_mapa": matchups_mapa}


def matchups_de(filas):
    """Matchups 1v1 de las filas válidas de un día (una por jugador y partida, con modo, mapa y tramo de la partida):
    [modo, tramo, civA, civB, n, winsA] con todos los mapas y [modo, mapa, tramo, civA, civB, n, winsA] por mapa
    (aquí sin umbral: el de MIN_PARTIDAS_CIV se aplica al sumar la ventana, que es donde se sabe cuánto se jugó el mapa)."""
    uno = filas[filas["modo"].str.endswith("_1v1")].sort_values(["matchId", "civ"])
    uno = uno.assign(pos=uno.groupby("matchId").cumcount())
    a = uno[uno["pos"] == 0][["matchId", "modo", "mapa", "tramo", "civ", "won"]].rename(columns={"civ": "ca", "won": "wa"})
    b = uno[uno["pos"] == 1][["matchId", "civ"]].rename(columns={"civ": "cb"})
    par = a.merge(b, on="matchId")
    mu = par.groupby(["modo", "tramo", "ca", "cb"]).agg(n=("wa", "size"), wa=("wa", "sum"))
    matchups = [[modo, tramo, ca, cb, int(n), int(wa)] for (modo, tramo, ca, cb), n, wa in zip(mu.index, mu["n"], mu["wa"])]
    mm = par.groupby(["modo", "mapa", "tramo", "ca", "cb"]).agg(n=("wa", "size"), wa=("wa", "sum"))
    matchups_mapa = [[modo, mapa, tramo, ca, cb, int(n), int(wa)] for (modo, mapa, tramo, ca, cb), n, wa in zip(mm.index, mm["n"], mm["wa"])]
    return matchups, matchups_mapa


def ruta_dia(fecha):
    return os.path.join(DIR_DIAS, f"{fecha}.json.gz")


def procesar_dias(estado):
    """Descarga y resume los días que falten (hasta ayer). Devuelve cuántos días nuevos hay."""
    hechos = set(estado.get("dias", []))
    hoy = datetime.now(timezone.utc).date()
    pendientes = []
    for k in range(DIAS_HISTORICO, 0, -1):
        d = (hoy - timedelta(days=k)).isoformat()
        if d not in hechos:
            pendientes.append(d)
    inicio = time.time()
    nuevos = 0
    if not pendientes:
        log("civstats: sin días pendientes")
    else:
        log(f"civstats: {len(pendientes)} días pendientes ({pendientes[0]} → {pendientes[-1]})")
    for d in pendientes:
        if nuevos >= DIAS_MAX_POR_EJECUCION or time.time() - inicio > TIEMPO_MAX_S:
            log("civstats: tope de esta ejecución alcanzado; el resto queda para la siguiente")
            break
        raw = fetch(DUMP + f"match-{d}.parquet", timeout=300)
        if raw is None:
            log(f"civstats: match-{d}.parquet aún no existe")
            continue
        try:
            res = resumir_dia(d, raw)
        except Exception as ex:
            log(f"civstats: {d}: ERROR {ex!r}")
            continue
        escribir_json(ruta_dia(d), res)
        hechos.add(d)
        estado["dias"] = sorted(hechos)
        estado["dias_mm"] = sorted(set(estado.get("dias_mm", [])) | {d})
        parches = estado.setdefault("parches", {})
        if res["parche"] is not None:
            p = parches.setdefault(str(res["parche"]), {"desde": d, "hasta": d, "dias": 0})
            p["desde"] = min(p["desde"], d); p["hasta"] = max(p["hasta"], d); p["dias"] += 1
        nuevos += 1
    return nuevos + rellenar_matchups_mapa(estado, inicio)


def rellenar_matchups_mapa(estado, inicio):
    """Los días resumidos antes de la 1.5.4 no traen «matchups_mapa»: se vuelven a resumir poco a poco (MM_RELLENO_POR_NOCHE
    por ejecución, del más reciente al más viejo, dentro del mismo presupuesto de tiempo). Al resumen publicado del día solo
    se le AÑADE la clave «matchups_mapa»: el resto (modos, mapas, civs, matchups, parche) queda tal cual, aunque el volcado
    de hoy dé cifras algo distintas (el companion lo retoca); los parches ya contados no se tocan. Una ventana publica
    matchups por mapa cuando todos sus días los tienen o ya no tienen volcado (ver sumar). Días cuyo volcado ya no existe:
    se anotan en «dias_mm_sin_volcado» y no se reintentan. Un error de red corta el relleno (sigue la noche siguiente)."""
    con = set(estado.get("dias_mm", []))
    sin_volcado = set(estado.get("dias_mm_sin_volcado", []))
    faltan = sorted(set(estado.get("dias", [])) - con - sin_volcado, reverse=True)
    if not faltan:
        return 0
    log(f"civstats: {len(faltan)} días sin matchups por mapa; se rellenan hasta {MM_RELLENO_POR_NOCHE} en esta ejecución")
    hechos = 0
    for d in faltan[:MM_RELLENO_POR_NOCHE]:
        if time.time() - inicio > TIEMPO_MAX_S:
            log("civstats: tope de tiempo alcanzado en el relleno; el resto queda para la siguiente")
            break
        try:
            raw = fetch(DUMP + f"match-{d}.parquet", timeout=300)
        except Exception as ex:   # sin esto, un fallo de red tras los reintentos mataba civstats() antes de podar/ventanas/estado
            log(f"civstats: relleno {d}: ERROR de descarga {ex!r}; el resto queda para la siguiente ejecución")
            break
        if raw is None:
            log(f"civstats: relleno: match-{d}.parquet ya no existe; ese día se queda sin matchups por mapa")
            sin_volcado.add(d)
            estado["dias_mm_sin_volcado"] = sorted(sin_volcado)
            continue
        try:
            res = resumir_dia(d, raw)
        except Exception as ex:
            log(f"civstats: relleno {d}: ERROR {ex!r}")
            continue
        try:
            viejo = leer_json(ruta_dia(d))
        except Exception as ex:   # un .gz dañado no debe parar el relleno ni la noche
            log(f"civstats: relleno {d}: resumen publicado ilegible ({ex!r}); no se toca")
            continue
        if not viejo:
            log(f"civstats: relleno {d}: no se pudo leer el resumen publicado; no se toca")
            continue
        if res["matchups"] != viejo.get("matchups"):
            log(f"civstats: relleno {d}: el volcado de hoy da otros matchups que el resumen publicado; se deja el publicado")
        viejo["matchups_mapa"] = res["matchups_mapa"]
        escribir_json(ruta_dia(d), viejo)
        con.add(d)
        estado["dias_mm"] = sorted(con)
        hechos += 1
    return hechos


def podar(estado):
    limite = (datetime.now(timezone.utc).date() - timedelta(days=DIAS_RETENCION)).isoformat()
    viejos = [d for d in estado.get("dias", []) if d < limite]
    for d in viejos:
        try:
            os.remove(ruta_dia(d))
        except OSError:
            pass
    if viejos:
        estado["dias"] = [d for d in estado["dias"] if d >= limite]
        for k in ("dias_mm", "dias_mm_sin_volcado"):
            if k in estado:
                estado[k] = [d for d in estado[k] if d >= limite]
        log(f"civstats: podados {len(viejos)} días anteriores a {limite}")


def cargar_dias(fechas):
    for d in fechas:
        r = leer_json(ruta_dia(d))
        if r:
            yield r


def sumar(resumenes, etiqueta, desde, hasta, parche=None, sin_volcado_mm=frozenset()):
    modos = defaultdict(lambda: {"partidas": 0, "abandonos": 0, "espejos": 0, "sin_resultado": 0})
    mapas = defaultdict(int)
    civs = defaultdict(lambda: [0, 0, 0])
    matchups = defaultdict(lambda: [0, 0])
    matchups_mapa = defaultdict(lambda: [0, 0])
    dias = 0
    dias_mm = 0
    for r in resumenes:
        dias += 1
        for modo, c in r["modos"].items():
            for k, v in c.items():
                modos[modo][k] += v
        for modo, mapa, n in r["mapas"]:
            mapas[(modo, mapa)] += n
        for modo, mapa, tramo, civ, n, w, d in r["civs"]:
            x = civs[(modo, mapa, tramo, civ)]; x[0] += n; x[1] += w; x[2] += d
        for modo, tramo, ca, cb, n, wa in r["matchups"]:
            x = matchups[(modo, tramo, ca, cb)]; x[0] += n; x[1] += wa
        if "matchups_mapa" in r or r.get("fecha") in sin_volcado_mm:
            dias_mm += 1
            for modo, mapa, tramo, ca, cb, n, wa in r.get("matchups_mapa", []):
                x = matchups_mapa[(modo, mapa, tramo, ca, cb)]; x[0] += n; x[1] += wa
    claves_mapa = sorted({mapa for _, mapa in mapas})
    out = {
        "ventana": etiqueta, "desde": desde, "hasta": hasta, "dias": dias, "parche": parche, "generado": ahora(),
        "tramos": [f"{lo}-{hi}" if hi < 99999 else f"{lo}+" for lo, hi in TRAMOS],
        "min_duracion_s": MIN_DURACION_S,
        "modos": dict(modos),
        "nombres_mapas": {k: nombre_mapa(k) for k in claves_mapa},
        "mapas": [[modo, mapa, n] for (modo, mapa), n in sorted(mapas.items())],
        "civs": [[modo, mapa, tramo, civ, n, w, d] for (modo, mapa, tramo, civ), (n, w, d) in sorted(civs.items())],
        "matchups": [[modo, tramo, ca, cb, n, wa] for (modo, tramo, ca, cb), (n, wa) in sorted(matchups.items())],
        "credito": "Datos: aoe2companion.com (Dennis Keil) · Age of Empires II © Microsoft",
    }
    # por mapa: solo si TODOS los días de la ventana los traen (si no, la matriz de un mapa sería de menos días que el
    # resto de la ventana; la app usa entonces el agregado y lo dice); solo 1v1 y mapas con >= MIN_PARTIDAS_CIV partidas.
    # Excepción (decisión de Opus): los días cuyo volcado ya no existe (sin_volcado_mm) cuentan como cubiertos: mejor una
    # matriz por mapa con algún día de menos que ninguna durante un año (v365 no se completaría nunca).
    if dias and dias_mm == dias:
        out["matchups_mapa"] = [[modo, mapa, tramo, ca, cb, n, wa] for (modo, mapa, tramo, ca, cb), (n, wa) in sorted(matchups_mapa.items())
                                if modo.endswith("_1v1") and mapas[(modo, mapa)] >= MIN_PARTIDAS_CIV]
    elif dias_mm:
        log(f"civstats: ventana {etiqueta}: {dias_mm}/{dias} días con matchups por mapa; aún no se publican")
    return out


def ventanas_y_tendencias(estado):
    dias = estado.get("dias", [])
    if not dias:
        log("civstats: sin días procesados, no hay ventanas")
        return
    ultimo = dias[-1]
    ultimo_d = date.fromisoformat(ultimo)
    sin_mm = frozenset(estado.get("dias_mm_sin_volcado", []))
    for n in VENTANAS:
        desde = (ultimo_d - timedelta(days=n - 1)).isoformat()
        sel = [d for d in dias if d >= desde]
        v = sumar(cargar_dias(sel), str(n), sel[0], ultimo, sin_volcado_mm=sin_mm)
        escribir_json(os.path.join(DIR_VENT, f"v{n}.json.gz"), v)
        log(f"civstats: ventana {n}: {v['dias']} días, {sum(x['partidas'] for x in v['modos'].values()):,} partidas, {len(v['civs']):,} filas civ")
    # parche actual: los últimos días consecutivos con el mismo parche
    parche = None
    sel = []
    for r in cargar_dias(reversed(dias[-DIAS_HISTORICO:])):   # de uno en uno, del más nuevo hacia atrás: sin cargar el año entero en memoria
        if parche is None:
            parche = r["parche"]
        if r["parche"] != parche:
            break
        sel.append(r["fecha"])
    sel.sort()
    if sel:
        v = sumar(cargar_dias(sel), "parche", sel[0], sel[-1], parche, sin_volcado_mm=sin_mm)
        escribir_json(os.path.join(DIR_VENT, "vparche.json.gz"), v)
        log(f"civstats: parche actual {parche}: {v['dias']} días desde {sel[0]}")
        estado["parche_actual"] = parche
    # tendencias: modo × civ por mes (13 meses), modo × mapa × civ por mes (los 12 mapas más jugados de cada modo)
    por_mes = defaultdict(lambda: [0, 0])
    por_mes_mapa = defaultdict(lambda: [0, 0])
    por_mes_tramo = defaultdict(lambda: [0, 0])
    por_mes_mt = defaultdict(lambda: [0, 0])
    partidas_mes = defaultdict(int)
    partidas_mapa = defaultdict(int)
    meses = set()
    primer_mes = (ultimo_d.replace(day=1) - timedelta(days=31 * (MESES_TENDENCIAS - 1))).strftime("%Y-%m")
    for r in cargar_dias([d for d in dias if d[:7] >= primer_mes]):
        mes = r["fecha"][:7]
        meses.add(mes)
        for modo, c in r["modos"].items():
            partidas_mes[(modo, mes)] += c["partidas"]
        for modo, mapa, tramo, civ, n, w, d in r["civs"]:
            x = por_mes[(modo, civ, mes)]; x[0] += n; x[1] += w
            y = por_mes_mapa[(modo, mapa, civ, mes)]; y[0] += n; y[1] += w
            partidas_mapa[(modo, mapa)] += n
            z2 = por_mes_tramo[(modo, tramo, civ, mes)]; z2[0] += n; z2[1] += w
            if modo.endswith("_1v1"):
                z3 = por_mes_mt[(modo, mapa, tramo, civ, mes)]; z3[0] += n; z3[1] += w
    top_mapas = {}
    for (modo, mapa), n in partidas_mapa.items():
        top_mapas.setdefault(modo, []).append((n, mapa))
    permitidos = set()
    for modo, lista in top_mapas.items():
        for n, mapa in sorted(lista, reverse=True)[:MAPAS_TENDENCIAS]:
            permitidos.add((modo, mapa))
    t = {"generado": ahora(), "meses": sorted(meses), "hasta": ultimo,
         "partidas": [[modo, mes, n] for (modo, mes), n in sorted(partidas_mes.items())],
         "filas": [[modo, civ, mes, n, w] for (modo, civ, mes), (n, w) in sorted(por_mes.items())],
         "filas_mapa": [[modo, mapa, civ, mes, n, w] for (modo, mapa, civ, mes), (n, w) in sorted(por_mes_mapa.items()) if (modo, mapa) in permitidos],
         "filas_tramo": [[modo, tramo, civ, mes, n, w] for (modo, tramo, civ, mes), (n, w) in sorted(por_mes_tramo.items())],
         "filas_mt": [[modo, mapa, tramo, civ, mes, n, w] for (modo, mapa, tramo, civ, mes), (n, w) in sorted(por_mes_mt.items()) if (modo, mapa) in permitidos and n >= 10]}
    escribir_json(os.path.join(DIR_CIV, "tendencias.json.gz"), t)
    log(f"civstats: tendencias: {len(meses)} meses, {len(t['filas']):,} filas; por mapa {len(t['filas_mapa']):,}; por tramo {len(t['filas_tramo']):,}; mapa×tramo {len(t['filas_mt']):,}")


def civstats():
    os.makedirs(DIR_DIAS, exist_ok=True)
    os.makedirs(DIR_VENT, exist_ok=True)
    estado = leer_json(os.path.join(DIR_CIV, "estado.json"), {}) or {}
    nuevos = procesar_dias(estado)
    podar(estado)
    version_estado = estado.get("motor")
    if nuevos or version_estado != UA or not os.path.exists(os.path.join(DIR_VENT, "v30.json.gz")):   # también al cambiar de versión del motor: los resúmenes se regeneran
        ventanas_y_tendencias(estado)
        estado["motor"] = UA
    estado["generado"] = ahora()
    estado["ultimo"] = estado["dias"][-1] if estado.get("dias") else None
    estado["activos_def"] = {"min_partidas": ACTIVO_MIN_PARTIDAS, "dias": ACTIVO_DIAS}
    escribir_json(os.path.join(DIR_CIV, "estado.json"), estado)
    log(f"civstats: {len(estado.get('dias', []))} días en el repo, último {estado['ultimo']}, {nuevos} nuevos")


# ============================================================================================
# PERFILES PRECALCULADOS — registro de partidas por jugador (último año), publicado como assets de la
# release «perfiles». La app abre un perfil bajando un paquete (~1 MB) en vez de 20 llamadas a la API.
# Formato del paquete: {"generado", "hasta", "desde", "jugadores": {pid: {"n": nombre, "c": país,
#   "m": [[matchId, inicio_s, fin_s, ladder, mapa, [[pid, nombre, civ, equipo, rating, diff, won], ...]], ...]}}}
# ============================================================================================
PERFILES_NIVEL1 = set()
perfiles_alcance_cache = set()


def perfiles_shard_de(pid):
    return int(pid) % PERFILES_SHARDS


def perfiles_url_asset(nombre):
    return f"https://github.com/{REPO}/releases/download/{PERFILES_RELEASE}/{nombre}"


def perfiles_cargar_shard(i):
    ruta = os.path.join(PERFILES_DIR, f"shard-{i:03d}.json.gz")
    if os.path.exists(ruta):
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            return json.load(f)
    try:
        raw = fetch(perfiles_url_asset(f"shard-{i:03d}.json.gz"), timeout=120, intentos=2)
    except Exception as ex:
        log(f"perfiles: shard {i}: {ex!r}")
        raw = None
    if raw is None:
        return {"jugadores": {}}
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def perfiles_escribir_shard(i, datos):
    os.makedirs(PERFILES_DIR, exist_ok=True)
    ruta = os.path.join(PERFILES_DIR, f"shard-{i:03d}.json.gz")
    with gzip.open(ruta, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))


def perfiles_alcance():
    """Los pids con partida en los últimos PERFILES_ACTIVO_DIAS días en cualquier ladder (leaderboard.parquet, lastMatchTime).
    Si el volcado no trae la fecha, respaldo por rango: top 40.000 1v1 + top 20.000 equipos."""
    import pandas as pd
    pf = abrir_parquet(fetch(DUMP + "leaderboard.parquet"), "perfiles: leaderboard.parquet")
    nombres = pf.schema.names
    c_lb = columna(nombres, "leaderboard_id", "leaderboard", "leaderboardId")
    c_pid = columna(nombres, "profile_id", "profileId")
    c_rank = columna(nombres, "rank")
    c_last = columna(nombres, "lastMatchTime", "last_match_time", "lastMatch")
    cols = [c for c in (c_lb, c_pid, c_rank, c_last) if c]
    df = tabla_texto(pf.read(columns=cols)).to_pandas()
    alcance = set()
    nivel1 = set()
    for lb, tope in (("rm_1v1", PERFILES_TOP_1V1), ("rm_team", PERFILES_TOP_TEAM)):
        sub = df[(df[c_lb] == lb) & (pd.to_numeric(df[c_rank], errors="coerce") <= tope)]
        nivel1.update(int(x) for x in sub[c_pid].dropna())
    PERFILES_NIVEL1.clear(); PERFILES_NIVEL1.update(nivel1)
    if c_last:
        limite = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=PERFILES_ACTIVO_DIAS)
        ultima = a_fecha_utc(df[c_last])
        sub = df[ultima >= limite]
        alcance.update(int(x) for x in sub[c_pid].dropna())
        alcance.update(nivel1)
        log(f"perfiles: alcance {len(alcance):,} jugadores activos (partida en los últimos {PERFILES_ACTIVO_DIAS} días, cualquier ladder); nivel 1 (año completo): {len(nivel1):,}; el resto, {PERFILES_DIAS_RESTO} días")
    else:
        for lb, tope in (("rm_1v1", PERFILES_TOP_1V1), ("rm_team", PERFILES_TOP_TEAM)):
            sub = df[(df[c_lb] == lb) & (pd.to_numeric(df[c_rank], errors="coerce") <= tope)]
            alcance.update(int(x) for x in sub[c_pid].dropna())
        log(f"perfiles: alcance {len(alcance):,} jugadores (sin lastMatchTime: top {PERFILES_TOP_1V1:,} 1v1 + top {PERFILES_TOP_TEAM:,} equipos)")
    return alcance


def perfiles_nombres(pids):
    """pid → (nombre, país) desde profile.parquet, solo para los pids pedidos."""
    import pandas as pd
    pf = abrir_parquet(fetch(DUMP + "profile.parquet"), "perfiles: profile.parquet")
    nombres = pf.schema.names
    c_pid = columna(nombres, "profile_id", "profileId")
    c_name = columna(nombres, "name")
    c_country = columna(nombres, "country", "countryCode")
    cols = [c for c in (c_pid, c_name, c_country) if c]
    df = tabla_texto(pf.read(columns=cols)).to_pandas()
    df = df[df[c_pid].isin(list(pids))]
    out = {}
    for pid, nombre, pais in zip(df[c_pid], df[c_name] if c_name else [""] * len(df), df[c_country] if c_country else [""] * len(df)):
        out[int(pid)] = (str(nombre or ""), str(pais or "").lower())
    return out


def perfiles_dia(fecha, raw, alcance):
    """Partidas del día en las que juega alguien del alcance, con todos sus jugadores. Devuelve {pid_del_alcance: [partida, ...]}."""
    import pandas as pd, numpy as np
    pf = abrir_parquet(raw, f"perfiles: match-{fecha}.parquet")
    nombres = pf.schema.names
    cols = [c for c in ("matchId", "started", "finished", "leaderboard", "map", "profileId", "rating", "ratingDiff", "team", "status", "won", "civ", "slot", "color") if c in nombres]
    df = tabla_texto(pf.read(columns=cols)).to_pandas()
    if "status" in df.columns:
        df = df[df["status"].fillna("player") == "player"]
    df = df[df["leaderboard"].isin(MODOS_FUENTE)]
    df["profileId"] = pd.to_numeric(df["profileId"], errors="coerce")
    df = df[df["profileId"].notna()]
    df["profileId"] = df["profileId"].astype("int64")
    ids_partidas = set(df[df["profileId"].isin(list(alcance))]["matchId"])
    df = df[df["matchId"].isin(list(ids_partidas))]
    por_partida = {}
    for r in df.itertuples(index=False):
        d = r._asdict()
        p = por_partida.setdefault(d["matchId"], {"ini": d["started"], "fin": d["finished"], "lb": d["leaderboard"], "mapa": d["map"], "j": []})
        won = d.get("won")
        won_i = -1 if won is None or (isinstance(won, float) and np.isnan(won)) else (1 if bool(won) else 0)
        rating = d.get("rating"); rating = 0 if rating is None or (isinstance(rating, float) and np.isnan(rating)) else int(rating)
        diff = d.get("ratingDiff"); diff = 0 if diff is None or (isinstance(diff, float) and np.isnan(diff)) else int(diff)
        team = d.get("team"); team = 0 if team is None or (isinstance(team, float) and np.isnan(team)) else int(team)
        slot = d.get("color", d.get("slot")); slot = 0 if slot is None or (isinstance(slot, float) and np.isnan(slot)) else int(slot)   # color si el volcado lo trae; si no, slot (en ranked coinciden)
        p["j"].append([int(d["profileId"]), civ_idx(d.get("civ") or ""), team, rating, diff, won_i, slot])
    def epoch(v):
        try:
            ts = pd.Timestamp(v)
            if pd.isna(ts): return 0
            return int(ts.timestamp())
        except Exception:
            return 0
    salida = {}
    for mid, p in por_partida.items():
        lb = LADDERS_IDX.index(p["lb"]) if p["lb"] in LADDERS_IDX else -1
        fila = [int(mid), epoch(p["ini"]), epoch(p["fin"]), lb, mapa_idx(p["mapa"] or ""), p["j"]]
        for j in p["j"]:
            if j[0] in alcance:
                salida.setdefault(j[0], []).append(fila)
    return salida


# diccionarios globales de civs y mapas (índices estables dentro de una publicación; se escriben en index.json)
CIVS_DIC, MAPAS_DIC = [], []
def _txt(v):
    """Texto limpio para los diccionarios: un NaN o un None (columna vacía) se convierte en «», nunca en NaN (JSON inválido)."""
    if v is None: return ""
    if isinstance(v, float): return ""
    return str(v)
def civ_idx(c):
    c = _txt(c)
    if c not in CIVS_DIC: CIVS_DIC.append(c)
    return CIVS_DIC.index(c)
def mapa_idx(m):
    m = _txt(m)
    if m not in MAPAS_DIC: MAPAS_DIC.append(m)
    return MAPAS_DIC.index(m)


ELO_AYER_CAMPOS = ["elo_1v1", "partidas_1v1", "elo_eq", "partidas_eq", "nombre", "pais", "rango_1v1", "ultima_1v1_s"]


def perfiles_elo_ayer(fecha):
    """elo_ayer.json.gz: pid → [elo 1v1, partidas 1v1, elo equipos, partidas equipos, nombre, país, rango 1v1, última partida 1v1]
    para el top 40.000 / 20.000 y todos los activos (forma por resta, índice de nombres, «Al azar» y Guess the ELO sin el ladder en vivo).
    v2 (1.4): las posiciones 6 (rango en rm_1v1, 0 si no tiene) y 7 (última partida en rm_1v1, epoch en segundos, 0 si no se sabe) se
    AÑADEN al final: la app 1.3 lee solo las seis primeras y no mira la longitud, así que sigue leyendo lo mismo."""
    import pandas as pd
    pf = abrir_parquet(fetch(DUMP + "leaderboard.parquet"), "perfiles: leaderboard.parquet (elo_ayer)")
    nombres = pf.schema.names
    c_lb = columna(nombres, "leaderboard_id", "leaderboard", "leaderboardId"); c_pid = columna(nombres, "profile_id", "profileId")
    c_rank = columna(nombres, "rank"); c_rating = columna(nombres, "rating"); c_games = columna(nombres, "games"); c_name = columna(nombres, "name"); c_country = columna(nombres, "country", "countryCode")
    c_last = columna(nombres, "lastMatchTime", "last_match_time", "lastMatch")
    if not c_last: log("perfiles: elo_ayer: AVISO sin columna de última partida; «ultima_1v1_s» saldrá a 0")
    # para la tarjeta del hover (chispas.json.gz, «x»): pico, ganadas y perdidas en rm_1v1, si el volcado las trae
    c_max = columna(nombres, "maxRating", "max_rating", "highestRating", "ratingMax", "peakRating")
    c_wins = columna(nombres, "wins", "win", "totalWins"); c_losses = columna(nombres, "losses", "loss", "totalLosses")
    log(f"perfiles: elo_ayer: columnas para la tarjeta: pico={c_max} ganadas={c_wins} perdidas={c_losses}")
    CHISPAS_EXTRA.clear()
    cols = [c for c in (c_lb, c_pid, c_rank, c_rating, c_games, c_name, c_country, c_last, c_max, c_wins, c_losses) if c]
    df = tabla_texto(pf.read(columns=cols)).to_pandas()
    out = {}
    activos = perfiles_alcance_cache if perfiles_alcance_cache else None
    for lb, tope, i_r, i_g in (("rm_1v1", ELO_TOP_1V1, 0, 1), ("rm_team", ELO_TOP_TEAM, 2, 3)):
        sub = df[df[c_lb] == lb]
        if activos is not None: sub = sub[sub[c_pid].isin(list(activos)) | (pd.to_numeric(sub[c_rank], errors="coerce") <= tope)]   # todos los activos (nombres para la app) + el top
        else: sub = sub[pd.to_numeric(sub[c_rank], errors="coerce") <= tope]
        es_1v1 = lb == "rm_1v1"
        rangos = pd.to_numeric(sub[c_rank], errors="coerce").fillna(0).astype("int64").tolist() if (es_1v1 and c_rank) else None
        ultimas = None
        if es_1v1 and c_last:
            u = a_fecha_utc(sub[c_last])
            ultimas = [0 if pd.isna(x) else int(x.timestamp()) for x in u]
        for k, r in enumerate(sub.itertuples(index=False)):
            d = r._asdict(); pid = int(d[c_pid])
            e = out.setdefault(pid, [0, 0, 0, 0, "", "", 0, 0])
            e[i_r] = int(d[c_rating]) if d.get(c_rating) is not None and not pd.isna(d[c_rating]) else 0
            e[i_g] = int(d[c_games]) if c_games and d.get(c_games) is not None and not pd.isna(d[c_games]) else 0
            if c_name and d.get(c_name): e[4] = str(d[c_name])
            if c_country and d.get(c_country): e[5] = str(d[c_country]).lower()
            if rangos is not None: e[6] = max(0, int(rangos[k]))
            if ultimas is not None: e[7] = max(0, ultimas[k])
            if es_1v1 and (c_max or c_wins or c_losses):
                CHISPAS_EXTRA[pid] = [_entero(d.get(c_max)) if c_max else -1, _entero(d.get(c_wins)) if c_wins else -1, _entero(d.get(c_losses)) if c_losses else -1]
    datos = {"v": 2, "campos": ELO_AYER_CAMPOS, "fecha": fecha, "generado": ahora(), "j": {str(k): v for k, v in out.items()}}
    for nombre in ("elo_ayer.json.gz", f"elo-{fecha}.json.gz"):
        with gzip.open(os.path.join(PERFILES_DIR, nombre), "wt", encoding="utf-8", compresslevel=6) as f:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    log(f"perfiles: elo_ayer: {len(out):,} jugadores")


def perfiles_muestra(fecha, raw, nombres):
    """muestra_ayer.json.gz: hasta MUESTRA_POR_TRAMO partidas 1v1 RM al azar por tramo de ELO (200 puntos) del volcado de ayer: mapa, civs, jugadores, ELO y resultado.
    Más la de anteayer en una clave aparte (ver anteayer_muestra)."""
    import pandas as pd, random
    pf = abrir_parquet(raw, f"perfiles: match-{fecha}.parquet (muestra)")
    cols = [c for c in ("matchId", "started", "finished", "leaderboard", "map", "profileId", "rating", "team", "status", "won", "civ") if c in pf.schema.names]
    df = tabla_texto(pf.read(columns=cols)).to_pandas()
    if "status" in df.columns: df = df[df["status"].fillna("player") == "player"]
    df = df[df["leaderboard"] == "rm_1v1"]
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    g = df.groupby("matchId")
    partidas = []
    for mid, grp in g:
        if len(grp) != 2 or grp["rating"].isna().any() or grp["won"].isna().any(): continue
        media = grp["rating"].mean(); tramo = int(min(2400, max(0, media // 200 * 200)))
        ini = pd.Timestamp(grp["started"].iloc[0]); fin = pd.Timestamp(grp["finished"].iloc[0])
        if pd.isna(ini) or pd.isna(fin) or (fin - ini).total_seconds() < 300: continue
        js = []
        for r in grp.itertuples(index=False):
            d = r._asdict(); pid = int(d["profileId"]); nn = nombres.get(pid, ("", ""))
            js.append([pid, nn[0], _txt(d.get("civ")), int(d["rating"]), 1 if bool(d["won"]) else 0])   # _txt: un NaN de pandas es «verdadero» y colaba NaN en el JSON
        partidas.append((tramo, [int(mid), int(ini.timestamp()), int(fin.timestamp()), _txt(grp["map"].iloc[0]), js]))
    random.seed(fecha)
    por_tramo = {}
    for tramo, fila in partidas: por_tramo.setdefault(tramo, []).append(fila)
    salida = {"v": 2, "fecha": fecha, "generado": ahora(), "tramos": {}}
    for tramo, lista in por_tramo.items():
        random.shuffle(lista); salida["tramos"][str(tramo)] = lista[:MUESTRA_POR_TRAMO]
    anteayer_muestra(salida)
    with gzip.open(os.path.join(PERFILES_DIR, "muestra_ayer.json.gz"), "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)   # un NaN sería JSON inválido: mejor fallar con log
    log(f"perfiles: muestra de {fecha}: {sum(len(v) for v in salida['tramos'].values()):,} partidas en {len(salida['tramos'])} tramos"
        + (f"; anteayer ({salida['fecha_anteayer']}): {sum(len(v) for v in salida['tramos_anteayer'].values()):,}" if "tramos_anteayer" in salida else "; sin anteayer"))


def anteayer_muestra(salida):
    """v2 (1.4): la muestra de anteayer va en «tramos_anteayer» (+ «fecha_anteayer»), sacada de la muestra publicada la noche
    anterior (su «tramos», o su «tramos_anteayer» si esta es una repetición del mismo día): ni un volcado ni una llamada más.
    «tramos» sigue siendo solo ayer: la app 1.3 lee solo esa clave y sigue viendo «partidas de ayer». Si falta una noche, la
    clave no sale (la app nueva se queda con ayer)."""
    fecha = salida["fecha"]
    anteayer = (date.fromisoformat(fecha) - timedelta(days=1)).isoformat()
    try:
        previa = perfiles_leer_gz("muestra_ayer.json.gz")
    except Exception as ex:   # una copia ilegible no debe tumbar la muestra de ayer
        log(f"perfiles: muestra de anteayer: la publicada no se lee ({ex!r})"); previa = None
    if not isinstance(previa, dict): return
    if previa.get("fecha") == anteayer: tramos = previa.get("tramos")
    elif previa.get("fecha") == fecha and previa.get("fecha_anteayer") == anteayer: tramos = previa.get("tramos_anteayer")
    else:
        log(f"perfiles: muestra de anteayer: la publicada es de {previa.get('fecha')}, no de {anteayer}; sin anteayer"); return
    if not isinstance(tramos, dict): return
    de_ayer = {f[0] for lista in salida["tramos"].values() for f in lista}   # una partida que cruza la medianoche no sale dos veces
    salida["fecha_anteayer"] = anteayer
    salida["tramos_anteayer"] = {str(k): [f for f in lista if f[0] not in de_ayer][:MUESTRA_POR_TRAMO] for k, lista in tramos.items()}


def perfiles_escribir_gz(ruta, datos):
    with gzip.open(ruta, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))


# ----------------------------------------------------------------------------- chispas (tarjeta del hover sin API)
# chispas.json.gz (release «perfiles», 1.4): los últimos CHISPAS_N ratings 1v1 RM de cada jugador del alcance, del más viejo al
# más nuevo, para la mini gráfica de la tarjeta del hover de la app (que hoy pide /profiles y dos páginas de /matches por tarjeta).
#   {"v": 1, "fecha": último día incluido, "generado", "n": CHISPAS_N, "completo": bool,
#    "j": {pid: [rating más viejo, dif, dif, ...]},          (codificado por diferencias: r[i] = r[i-1] + dif; comprime mucho mejor)
#    "x": {pid: [pico, ganadas, perdidas]}}                   (rm_1v1 del leaderboard; -1 si el volcado no trae esa columna; solo si trae alguna)
# «completo» = sale de la base entera (noches de consolidación): una chispa corta es de verdad «pocos 1v1». Entre medias, la de la
# noche anterior + los días nuevos; si no hay anterior (primera noche), se siembra con los deltas y sale completo=false (la app
# entonces tira de la API como hoy para quien tenga menos puntos de los que necesita). Sin volcados ni llamadas extra.
CHISPAS_N = 25                  # la tarjeta quita las 10 más recientes (sin spoilers) y pinta si le quedan 4 o más
CHISPAS_ARCHIVO = "chispas.json.gz"
CHISPAS_EXTRA = {}              # pid → [pico, ganadas, perdidas] de rm_1v1 (lo rellena perfiles_elo_ayer)


def _entero(v):
    try:
        if v is None or v != v: return -1   # None o NaN
        return int(v)
    except Exception:
        return -1


def chispa_puntos(pid, partidas):
    """(inicio_s, matchId, rating) de las partidas 1v1 RM (dos jugadores) de pid con rating conocido."""
    pid = int(pid); out = []
    for f in partidas:
        if f[3] != 0 or len(f[5]) != 2: continue   # ladderIdx 0 = rm_1v1 (LADDERS_IDX)
        for j in f[5]:
            if j[0] == pid and j[3] > 0: out.append((f[1], f[0], j[3])); break
    return out


def chispa_codificar(ratings):
    return [ratings[0]] + [b - a for a, b in zip(ratings, ratings[1:])] if ratings else []


def chispa_decodificar(cod):
    out = []
    for i, v in enumerate(cod): out.append(v if i == 0 else out[-1] + v)
    return out


def chispas_de_base(jug):
    """{pid: [ratings, del más viejo al más nuevo]} desde los paquetes base ya fundidos (partidas de cada pid, de la más nueva a la más vieja)."""
    out = {}
    for pid, partidas in jug.items():
        pts = sorted(chispa_puntos(pid, partidas))[-CHISPAS_N:]
        if pts: out[str(pid)] = [r for _, _, r in pts]
    return out


def chispas_sumar(previas, por_dia, dias):
    """Añade a {pid: [ratings]} las partidas de los días dados (en orden) y recorta a CHISPAS_N."""
    for d in sorted(dias):
        for pid, partidas in por_dia[d].items():
            pts = sorted(chispa_puntos(pid, partidas))
            if not pts: continue
            lista = previas.setdefault(str(pid), [])
            lista.extend(r for _, _, r in pts)
            del lista[:-CHISPAS_N]
    return previas


def chispas_previas():
    """(ratings por pid, último día incluido, completo) de la chispas.json.gz publicada, o (None, None, False) si no hay o no se entiende."""
    try:
        previa = perfiles_leer_gz(CHISPAS_ARCHIVO)
    except Exception as ex:
        log(f"perfiles: chispas: la publicada no se lee ({ex!r})"); return None, None, False
    if not isinstance(previa, dict) or previa.get("v") != 1 or not isinstance(previa.get("j"), dict): return None, None, False
    return {pid: chispa_decodificar(c) for pid, c in previa["j"].items()}, previa.get("fecha"), bool(previa.get("completo"))


def chispas_escribir(ratings, fecha, completo, alcance):
    j = {pid: chispa_codificar(r) for pid, r in ratings.items() if r and int(pid) in alcance}
    datos = {"v": 1, "fecha": fecha, "generado": ahora(), "n": CHISPAS_N, "completo": bool(completo), "j": j}
    if CHISPAS_EXTRA:
        datos["x"] = {str(pid): x for pid, x in CHISPAS_EXTRA.items() if str(pid) in j}
    perfiles_escribir_gz(os.path.join(PERFILES_DIR, CHISPAS_ARCHIVO), datos)
    log(f"perfiles: chispas hasta {fecha}: {len(j):,} jugadores ({'completo' if completo else 'parcial'}), "
        f"{sum(len(v) for v in j.values()):,} puntos, extra {len(datos.get('x', {})):,}; "
        f"{os.path.getsize(os.path.join(PERFILES_DIR, CHISPAS_ARCHIVO)) / 1e6:.2f} MB")


def chispas_incremental(por_dia, deltas, alcance):
    """Noche sin consolidación: la publicada + los días nuevos. Sin publicada: se siembra con los deltas previos + los días leídos."""
    previas, hasta, completo = chispas_previas()   # una parcial sigue parcial hasta que la reescriba una consolidación
    if previas is None:
        completo = False; previas = {}; hasta = ""
        sembrados = {}
        for fecha in sorted(deltas):
            dia = {}
            for g in range(PERFILES_GRUPOS):
                dj = perfiles_leer_gz(f"delta-{fecha}-g{g}.json.gz")
                if dj: dia.update(dj.get("j", {}))
            sembrados[fecha] = dia
        chispas_sumar(previas, sembrados, sembrados.keys())
        log(f"perfiles: chispas: sin publicada; sembradas con {len(sembrados)} deltas (parcial hasta la próxima consolidación)")
    nuevos = [d for d in por_dia if d > (hasta or "")]
    chispas_sumar(previas, por_dia, nuevos)
    fecha = max([hasta or ""] + nuevos) or None
    chispas_escribir(previas, fecha, completo, alcance)


PERFILES_BASE_TAG = None   # release de la base actual (del índice), para leer los paquetes al consolidar


def perfiles_leer_gz(nombre):
    """Lee un archivo de la carpeta local o de la release (los paquetes base, de su release propia). None si no existe."""
    for ruta in (os.path.join(PERFILES_DIR, "base", nombre), os.path.join(PERFILES_DIR, nombre)):
        if os.path.exists(ruta):
            with gzip.open(ruta, "rt", encoding="utf-8") as f:
                return json.load(f)
    tag = PERFILES_BASE_TAG if nombre.startswith("shard-") and PERFILES_BASE_TAG else PERFILES_RELEASE
    try:
        raw = fetch(f"https://github.com/{REPO}/releases/download/{tag}/{nombre}", timeout=120, intentos=2)
    except Exception as ex:
        log(f"perfiles: {nombre}: {ex!r}"); raw = None
    if raw is None: return None
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def perfiles():
    """Base semanal + deltas diarios, formato compacto (v2).
    index.json: {"v":2, "shards", "grupos", "base_hasta", "deltas":[fechas], "dias":[...], "desde", "civs":[...], "mapas":[...], ...}
    Paquete base:  shard-NNNN.json.gz = {"j": {pid: [partida, ...]}}; delta: delta-AAAA-MM-DD-gG.json.gz = {"j": {pid: [partida, ...]}} (shard % grupos == G)
    Partida: [matchId, inicio_s, fin_s, ladderIdx, mapaIdx, [[pid, civIdx, equipo, rating, diff, won, slot/color], ...]]"""
    global perfiles_alcance_cache
    os.makedirs(PERFILES_DIR, exist_ok=True)
    estado = leer_json(os.path.join(PERFILES_DIR, "index.json"), {}) or {}
    if not estado:
        try:
            raw = fetch(perfiles_url_asset("index.json"), timeout=60, intentos=2)
            if raw: estado = json.loads(raw.decode("utf-8"))
        except Exception:
            estado = {}
    if estado.get("v") != 2:   # formato antiguo o nada: la base se construye de cero
        estado = {"v": 2, "dias": [], "deltas": [], "civs": [], "mapas": []}
    CIVS_DIC[:] = [_txt(x) for x in estado.get("civs", [])]; MAPAS_DIC[:] = [_txt(x) for x in estado.get("mapas", [])]   # sanea un NaN heredado sin mover los índices
    global PERFILES_BASE_TAG
    PERFILES_BASE_TAG = estado.get("base_release")
    hechos = set(estado.get("dias", []))
    deltas = list(estado.get("deltas", []))
    hoy = datetime.now(timezone.utc).date()
    ayer = (hoy - timedelta(days=1)).isoformat()
    candidatos = [(hoy - timedelta(days=k)).isoformat() for k in range(1, PERFILES_DIAS + 1)]
    pendientes = [d for d in candidatos if d not in hechos]
    nuevos_recientes = [d for d in pendientes if d > (estado.get("base_hasta") or "")][:PERFILES_DIAS_POR_NOCHE]   # días posteriores a la base (van a deltas o, si son muchos, a la base)
    relleno = [] if nuevos_recientes else [d for d in pendientes][:PERFILES_DIAS_POR_NOCHE]   # relleno hacia atrás (reescribe la base); una cosa por ejecución para acotar memoria
    alcance = perfiles_alcance(); perfiles_alcance_cache = alcance
    try:
        perfiles_elo_ayer(ayer)
    except Exception as ex:
        log(f"perfiles: elo_ayer: ERROR {ex!r}")
    consolidar = bool(relleno) or (len(deltas) + len(nuevos_recientes) >= PERFILES_CONSOLIDAR_DIAS) or not estado.get("base_hasta")
    log(f"perfiles: pendientes {len(pendientes)} (recientes {len(nuevos_recientes)}, relleno {len(relleno)}); deltas previos {len(deltas)}; consolidar={consolidar}")
    # 1) leer los volcados que tocan
    por_dia = {}   # fecha → {pid: [partida...]}
    raw_reciente = None
    inicio = time.time()
    for d in (nuevos_recientes + relleno):
        if time.time() - inicio > 90 * 60:
            log("perfiles: tope de tiempo; el resto queda para la siguiente ejecución"); break
        raw = fetch(DUMP + f"match-{d}.parquet", timeout=300)
        if raw is None:
            log(f"perfiles: match-{d}.parquet no existe"); hechos.add(d); continue
        try:
            por_dia[d] = perfiles_dia(d, raw, alcance)
        except Exception as ex:
            log(f"perfiles: {d}: ERROR {ex!r}"); continue
        if d == ayer: raw_reciente = (d, raw)
        log(f"perfiles: {d}: {sum(len(v) for v in por_dia[d].values()):,} filas para {len(por_dia[d]):,} jugadores")
    # muestra de ayer (siempre del volcado de ayer)
    if raw_reciente is None:
        raw_ayer = fetch(DUMP + f"match-{ayer}.parquet", timeout=300)
        if raw_ayer is not None: raw_reciente = (ayer, raw_ayer)
    if raw_reciente is not None:
        try:
            pf_m = abrir_parquet(raw_reciente[1], "perfiles: muestra (pids)")
            df_m = tabla_texto(pf_m.read(columns=[c for c in ("leaderboard", "profileId") if c in pf_m.schema.names])).to_pandas()
            pids_m = set(int(x) for x in df_m[df_m["leaderboard"] == "rm_1v1"]["profileId"].dropna())
            perfiles_muestra(raw_reciente[0], raw_reciente[1], perfiles_nombres(pids_m))
        except Exception as ex:
            log(f"perfiles: muestra: ERROR {ex!r}")
    if not por_dia:
        log("perfiles: sin días nuevos"); return
    limite = int((datetime.now(timezone.utc) - timedelta(days=PERFILES_DIAS)).timestamp())
    def shard_de(pid): return int(pid) % PERFILES_SHARDS
    deltas_previos = list(deltas)
    chispas_base = {}   # consolidación: la chispa de cada jugador sale de su año entero
    if consolidar:
        # 2a) reescribir la base: base anterior + deltas previos + días leídos, por paquete
        nuevos = {}   # shard → {pid: [partidas]}
        for d, por_pid in por_dia.items():
            for pid, partidas in por_pid.items():
                nuevos.setdefault(shard_de(pid), {}).setdefault(str(pid), []).extend(partidas)
        for fecha in deltas:   # los deltas se funden en la base y desaparecen
            for g in range(PERFILES_GRUPOS):
                dj = perfiles_leer_gz(f"delta-{fecha}-g{g}.json.gz")
                if not dj: continue
                for pid, partidas in dj.get("j", {}).items():
                    nuevos.setdefault(shard_de(pid), {}).setdefault(pid, []).extend(partidas)
        for i in range(PERFILES_SHARDS):
            base = perfiles_leer_gz(f"shard-{i:04d}.json.gz") or {"j": {}}
            jug = base.setdefault("j", {})
            for pid, partidas in nuevos.get(i, {}).items():
                entrada = jug.setdefault(pid, [])
                vistos = {f[0] for f in entrada}
                for f in partidas:
                    if f[0] not in vistos: entrada.append(f); vistos.add(f[0])
            for pid in list(jug.keys()):
                if int(pid) not in alcance: del jug[pid]; continue
                m = [f for f in jug[pid] if f[1] >= limite]; m.sort(key=lambda f: -f[1]); jug[pid] = m
                if not m: del jug[pid]
            try: chispas_base.update(chispas_de_base(jug))
            except Exception as ex: log(f"perfiles: chispas del paquete {i}: ERROR {ex!r}")
            perfiles_escribir_gz(os.path.join(PERFILES_DIR, f"shard-{i:04d}.json.gz"), {"v": 2, "j": jug})
        for fecha in deltas:   # marcar los deltas viejos para borrarlos de la release
            for g in range(PERFILES_GRUPOS):
                open(os.path.join(PERFILES_DIR, f"BORRAR-delta-{fecha}-g{g}.json.gz"), "w").close()
        deltas = []
        estado["base_hasta"] = max(hechos | set(por_dia.keys()))
        estado["base_release_anterior"] = estado.get("base_release")
        estado["base_release"] = "perfiles-base-" + estado["base_hasta"] + "-" + datetime.now(timezone.utc).strftime("%H%M")
        os.makedirs(os.path.join(PERFILES_DIR, "base"), exist_ok=True)
        for f in os.listdir(PERFILES_DIR):
            if f.startswith("shard-") and f.endswith(".json.gz"): os.replace(os.path.join(PERFILES_DIR, f), os.path.join(PERFILES_DIR, "base", f))
        with open(os.path.join(PERFILES_DIR, "BASE_TAG"), "w") as f: f.write(estado["base_release"])
        log(f"perfiles: base consolidada ({PERFILES_SHARDS} paquetes) → release {estado['base_release']}")
    else:
        # 2b) solo deltas: un archivo por grupo y día
        for d, por_pid in por_dia.items():
            grupos = {}
            for pid, partidas in por_pid.items():
                grupos.setdefault(shard_de(pid) % PERFILES_GRUPOS, {})[str(pid)] = partidas
            for g in range(PERFILES_GRUPOS):
                perfiles_escribir_gz(os.path.join(PERFILES_DIR, f"delta-{d}-g{g}.json.gz"), {"v": 2, "j": grupos.get(g, {})})
            deltas.append(d)
        log(f"perfiles: deltas escritos: {sorted(por_dia.keys())}")
    hechos |= set(por_dia.keys())
    try:   # chispas.json.gz: un fallo aquí no debe impedir publicar el índice (la app sigue con la de la noche anterior o la API)
        if consolidar: chispas_escribir(chispas_base, max(hechos), True, alcance)
        else: chispas_incremental(por_dia, deltas_previos, alcance)
    except Exception as ex:
        log(f"perfiles: chispas: ERROR {ex!r}")
    estado.update({"v": 2, "shards": PERFILES_SHARDS, "grupos": PERFILES_GRUPOS, "dias": sorted(hechos), "deltas": sorted(deltas),
                   "hasta": max(hechos), "desde": min(hechos), "alcance": len(alcance), "generado": ahora(), "motor": UA,
                   "civs": CIVS_DIC, "mapas": MAPAS_DIC})
    escribir_json(os.path.join(PERFILES_DIR, "index.json"), estado)
    log(f"perfiles: cobertura {estado['desde']} → {estado['hasta']} ({len(hechos)} días); base hasta {estado.get('base_hasta')}; deltas {len(deltas)}; {len(alcance):,} jugadores")


if __name__ == "__main__":
    ok = True
    for nombre, fn in (("ladder", ladder), ("civstats", civstats), ("mapas", mapas), ("perfiles", perfiles)):
        try:
            fn()
        except Exception as ex:
            ok = False
            import traceback
            traceback.print_exc()
            log(f"{nombre}: ERROR {ex!r}")
    sys.exit(0 if ok else 1)
