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
- torneos.json       torneos de AoE II de Liquipedia: en curso, próximos (hasta TORNEOS_DIAS_FUTURO días) y terminados
                     (últimos TORNEOS_DIAS_PASADO días). Ver torneos(). Esquema (v1):
                     {"v":1, "generado":ISO, "hoy":"AAAA-MM-DD", "ventana":{"desde","hasta"},
                      "fuente":{"nombre":"Liquipedia","url","licencia":"CC BY-SA 3.0","licencia_url","atribucion","generado"},
                      "torneos":[{"nombre", "tier":"S|A|B|C|Misc|null", "tipo":"Qualifier|Weekly|Monthly|Showmatch|FFA|null",
                                  "inicio":"AAAA-MM-DD", "fin":"AAAA-MM-DD", "estado":"en_curso|proximo|terminado",
                                  "bolsa":número|null, "moneda":"USD"|null, ["bolsa_local", "moneda_local"],
                                  "formato":"1v1|2v2|3v3|4v4|mixto|FFA|equipos|null", "formato_texto", "organizador", "lugar",
                                  "participantes", "url", ["ganador", "finalista"]}]}
                     ganador/finalista solo si Liquipedia los da (la app los esconde: sin spoilers); varios jugadores se unen
                     con « & ». Orden: en_curso (por fin), proximo (por inicio), terminado (el más reciente primero).
                     Si Liquipedia falla o no sale ningún torneo, se conserva el torneos.json anterior (rama data).
                     Prueba sin red: python build_data.py --probar (muestra en pruebas/). Solo este paso: python build_data.py torneos
- noticias.json      titulares recientes de AoE II de la web oficial (API REST pública de ageofempires.com, juegos AoE II DE/HD).
                     Solo titular, fecha, fuente, enlace, categoría y miniatura; nunca el cuerpo. Ver noticias(). Esquema (v1):
                     {"v":1, "generado":ISO, "fuentes":[{"nombre","url"}],
                      "noticias":[{"titulo", "fecha":"AAAA-MM-DDTHH:MM:SSZ", "fuente", "url", ["categoria"], ["imagen"]}]}
                     Como mucho NOTICIAS_MAX, la más reciente primero. «imagen» = URL de la miniatura 288x162 del CDN de la web.
                     Si la web falla o no sale ninguna noticia, se conserva el noticias.json anterior (rama data).
                     Prueba sin red: python build_data.py --probar [noticias]. Solo este paso: python build_data.py noticias
Fuente: volcados diarios de aoe2companion (https://www.aoe2companion.com/more/api).
Torneos: Liquipedia (https://liquipedia.net/ageofempires/), CC BY-SA 3.0; torneos.json se publica con la misma licencia.
Noticias: titulares y enlaces de https://www.ageofempires.com/news/ (World's Edge / Microsoft); los artículos no se copian.
Créditos: aoe2companion (Dennis Keil) · Liquipedia · Age of Empires II © Microsoft.
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
MAPAS_JUGADORES = 40            # jugadores más recientes por ladder cuyas partidas enseñan las imágenes de mapa (lotes de 10: 4 llamadas por ladder)
MAPAS_LOTE = 10                 # profile_ids por llamada a /matches (desde 2026-09-28 el companion exige profile_ids: 422 sin ellos)
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
def mapas_jugadores():
    """Por ladder de MAPAS_LADDERS, los MAPAS_JUGADORES con la partida más reciente (leaderboard.parquet, lastMatchTime);
    sin esa columna, los mejores por rango. Son los que juegan ahora: sus partidas traen los mapas en rotación."""
    import pandas as pd
    pf = abrir_parquet(fetch(DUMP + "leaderboard.parquet"), "mapas: leaderboard.parquet")
    nombres = pf.schema.names
    c_lb = columna(nombres, "leaderboard_id", "leaderboard", "leaderboardId")
    c_pid = columna(nombres, "profile_id", "profileId")
    c_rank = columna(nombres, "rank")
    c_last = columna(nombres, "lastMatchTime", "last_match_time", "lastMatch")
    df = tabla_texto(pf.read(columns=[c for c in (c_lb, c_pid, c_rank, c_last) if c])).to_pandas()
    out = {}
    for lb in MAPAS_LADDERS:
        sub = df[df[c_lb] == lb].dropna(subset=[c_pid])
        if c_last:
            sub = sub.assign(_u=a_fecha_utc(sub[c_last])).sort_values("_u", ascending=False)
        elif c_rank:
            sub = sub.assign(_r=pd.to_numeric(sub[c_rank], errors="coerce")).sort_values("_r")
        out[lb] = sorted(int(x) for x in sub[c_pid].head(MAPAS_JUGADORES))
    return out


def mapas():
    """mapas.json: imagen de cada mapa (URL del CDN del companion), aprendida de las partidas de unos pocos jugadores
    activos por ladder (/matches?profile_ids=<lote>). Se acumula con lo ya publicado, así los mapas nuevos entran solos en
    cuanto se juegan. Se escribe siempre (la publicación borra de la rama data lo que no se escribe); si no sale ninguna
    llamada, aviso en el resumen de la ejecución: el paso no rompe el job (continue-on-error) y antes fallaba en silencio."""
    previo = leer_json("mapas.json", {}) or {}
    conocidos = dict(previo.get("mapas", {}))
    nuevos = llamadas = buenas = 0
    try:
        por_ladder = mapas_jugadores()
    except Exception as ex:
        log(f"mapas: no se pudo elegir jugadores: {ex!r}")
        por_ladder = {}
    for lb, pids in por_ladder.items():
        for k in range(0, len(pids), MAPAS_LOTE):
            lote = ",".join(str(p) for p in pids[k:k + MAPAS_LOTE])
            if llamadas:
                time.sleep(1)
            llamadas += 1
            try:
                raw = fetch(f"{API}/matches?profile_ids={lote}&per_page=100", timeout=60)
                if raw is None:
                    continue
                partidas = json.loads(raw.decode("utf-8")).get("matches", [])
                buenas += 1
            except Exception as ex:
                log(f"mapas: {lb} lote {k // MAPAS_LOTE + 1}: {ex!r}")
                continue
            for m in partidas:
                url = m.get("mapImageUrl") or m.get("map_image_url")
                if not isinstance(url, str) or not url.startswith("http"):
                    continue
                for clave in (m.get("map"), m.get("mapName") or m.get("map_name")):
                    if isinstance(clave, str) and clave.strip():
                        k2 = clave.strip().lower()
                        if conocidos.get(k2) != url:
                            conocidos[k2] = url
                            nuevos += 1
    if buenas == 0:
        print(f"::warning title=mapas::ninguna llamada a /matches salió bien ({llamadas} intentos): mapas.json se publica con lo ya conocido", flush=True)
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


def chispas_incremental(por_dia, deltas, alcance, hechos=()):
    """Noche sin consolidación: la publicada + los días nuevos. Sin publicada: se siembra con los deltas previos + los días leídos.
    hechos: días ya procesados por el motor; si alguno posterior a la publicada no está en por_dia (una noche publicó el índice pero
    no las chispas), a la chispa le falta ese día: deja de ser «completo» hasta la próxima consolidación."""
    previas, hasta, completo = chispas_previas()   # una parcial sigue parcial hasta que la reescriba una consolidación
    if previas is not None and completo and any(d > (hasta or "") and d not in por_dia for d in hechos):
        log("perfiles: chispas: a la publicada le falta algún día; pasa a parcial hasta la próxima consolidación"); completo = False
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
        else: chispas_incremental(por_dia, deltas_previos, alcance, hechos)
    except Exception as ex:
        log(f"perfiles: chispas: ERROR {ex!r}")
    estado.update({"v": 2, "shards": PERFILES_SHARDS, "grupos": PERFILES_GRUPOS, "dias": sorted(hechos), "deltas": sorted(deltas),
                   "hasta": max(hechos), "desde": min(hechos), "alcance": len(alcance), "generado": ahora(), "motor": UA,
                   "civs": CIVS_DIC, "mapas": MAPAS_DIC})
    escribir_json(os.path.join(PERFILES_DIR, "index.json"), estado)
    log(f"perfiles: cobertura {estado['desde']} → {estado['hasta']} ({len(hechos)} días); base hasta {estado.get('base_hasta')}; deltas {len(deltas)}; {len(alcance):,} jugadores")


# ----------------------------------------------------------------------------- torneos (Liquipedia)
# Normas de la API de Liquipedia (https://liquipedia.net/api-terms-of-use): solo la API MediaWiki (sin clave; LiquipediaDB la
# exige y no se usa), nada de HTML de páginas fuera de la API, User-Agent propio con contacto, gzip, una conexión reutilizada,
# action=parse como mucho 1 cada 30 s y el resto 1 cada 2 s. Por noche: 1 action=parse de {{TournamentsList|game=Age of
# Empires II|year=…}} (la misma plantilla de la página «Age_of_Empires_II/Tournaments/AAAA-AA»), que ya trae tier, fechas,
# bolsa en USD, lugar, participantes, ganador y finalista, y 1 o 2 action=query (50 títulos cada una) con el wikitexto de los
# torneos de la ventana para sacar del infobox organizador, formato y moneda local. Contenido CC BY-SA 3.0.
LQ_HOST = "liquipedia.net"
LQ_API = "/ageofempires/api.php"
LQ_BASE = "https://liquipedia.net"
LQ_UA = "aoe2radar-sfr-data (https://github.com/jguardiola-dev/aoe2radar)"
LQ_ESPERA_PARSE_S = 31          # action=parse: <= 1 cada 30 s
LQ_ESPERA_S = 2.5               # resto de peticiones: <= 1 cada 2 s
LQ_TITULOS_POR_QUERY = 50       # máximo de la API para usuarios anónimos
TORNEOS_DIAS_PASADO = 30
TORNEOS_DIAS_FUTURO = 60
TORNEOS_MUESTRA = os.path.join("pruebas", "torneos_muestra.json")
MESES_EN = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
TIPOS_TIER = {"qualifier": "Qualifier", "weekly": "Weekly", "monthly": "Monthly", "showmatch": "Showmatch", "ffa": "FFA",
              "biweekly": "Biweekly", "charity": "Charity"}


class Liquipedia:
    """Cliente mínimo de la API MediaWiki de Liquipedia: conexión HTTPS reutilizada, gzip y esperas entre peticiones."""

    def __init__(self):
        import http.client
        self._hc = http.client
        self.con = None
        self.ultima = 0.0
        self.ultima_parse = 0.0
        self.peticiones = 0

    def _esperar(self, parse):
        if not self.peticiones:
            return
        t = time.monotonic()
        espera = max(self.ultima + LQ_ESPERA_S - t, (self.ultima_parse + LQ_ESPERA_PARSE_S - t) if parse and self.ultima_parse else 0, 0)
        if espera > 0:
            time.sleep(espera)

    def get(self, params, intentos=2):
        import urllib.parse
        parse = params.get("action") == "parse"
        ruta = LQ_API + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion="2"))
        for i in range(intentos):
            self._esperar(parse)
            self.ultima = time.monotonic()
            if parse:
                self.ultima_parse = self.ultima
            self.peticiones += 1
            try:
                if self.con is None:
                    self.con = self._hc.HTTPSConnection(LQ_HOST, timeout=60)
                self.con.request("GET", ruta, headers={"User-Agent": LQ_UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
                r = self.con.getresponse()
                raw = r.read()
                if (r.getheader("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                d = json.loads(raw.decode("utf-8"))
                if "error" in d:
                    err = d["error"]
                    if err.get("code") == "missingtitle":
                        return d          # página inexistente: no se reintenta
                    raise RuntimeError(f"API: {err.get('code')}: {err.get('info')}")
                return d
            except Exception as ex:
                log(f"torneos: petición {params.get('action')} {i + 1}/{intentos}: {ex!r}")
                try:
                    self.con.close()
                except Exception:
                    pass
                self.con = None
                if i == intentos - 1:
                    raise

    def cerrar(self):
        if self.con is not None:
            self.con.close()


def torneos_anios(hoy):
    """Años que pedir a {{TournamentsList|year=}}, que filtra por el año de la fecha de FIN: los de la ventana y siempre el
    siguiente (una liga en curso que acaba el año que viene solo sale ahí)."""
    a0 = (hoy - timedelta(days=TORNEOS_DIAS_PASADO)).year
    a1 = (hoy + timedelta(days=TORNEOS_DIAS_FUTURO)).year
    return list(range(a0, max(a1, hoy.year + 1) + 1))


def torneos_wikitexto(hoy):
    """Lo mismo que la página «Age_of_Empires_II/Tournaments/AAAA-AA», pero con los años justos y en un solo action=parse."""
    return "\n".join(f"{{{{TournamentsList|onlyTierTypeIfBoth=false|game=Age of Empires II|year={a}}}}}" for a in torneos_anios(hoy))


def _fecha_partes(txt):
    """«Nov 30, 2026» / «Nov 30» / «30, 2026» / «30» → (mes|None, día|None, año|None); None si no se entiende."""
    import re
    m = re.match(r"^\s*(?:([A-Za-z]{3})[a-z]*\.?\s+)?(\d{1,2})?\s*,?\s*(\d{4})?\s*$", txt)
    if not m or not (m.group(1) or m.group(2) or m.group(3)):
        return None
    mes = MESES_EN.get(m.group(1).lower()[:3]) if m.group(1) else None
    if m.group(1) and mes is None:
        return None
    return mes, int(m.group(2)) if m.group(2) else None, int(m.group(3)) if m.group(3) else None


def torneos_fechas(txt):
    """Columna Date de Liquipedia → (inicio, fin) en ISO, o (None, None). Formatos vistos: «Oct 17, 2026»,
    «Nov 30 – Dec 20, 2026», «Oct 05–31, 2026», «Nov 28, 2025 – Jan 01, 2026». Lo que no entiende (TBA, «Oct 2026») da None."""
    import re
    txt = (txt or "").replace("\xa0", " ").strip()
    trozos = [t for t in re.split(r"\s*[–—\-]\s*", txt) if t.strip()]
    if not trozos or len(trozos) > 2:
        return None, None
    a = _fecha_partes(trozos[0])
    b = _fecha_partes(trozos[1]) if len(trozos) == 2 else a
    if not a or not b:
        return None, None
    m1, d1, y1 = a
    m2, d2, y2 = b
    y2 = y2 or y1
    m2 = m2 or m1
    y1 = y1 or y2
    m1 = m1 or m2
    if not (y1 and m1 and d1 and y2 and m2 and d2):
        return None, None
    try:
        ini, fin = date(y1, m1, d1), date(y2, m2, d2)
        if fin < ini and not a[2]:
            ini = date(y1 - 1, m1, d1)      # «Dec 28 – Jan 03, 2027»: el inicio es del año anterior
    except ValueError:
        return None, None
    return ini.isoformat(), fin.isoformat()


def torneos_tier(txt):
    """«S-Tier» → ("S", None); «Qualifier (A)» → ("A", "Qualifier"); «Weekly (M.)» / «Misc» → ("Misc", …)."""
    import re
    txt = " ".join((txt or "").replace("\xa0", " ").split())
    if not txt:
        return None, None
    m = re.match(r"^(.*?)\s*\((.*?)\)$", txt)
    tipo_txt, letra = (m.group(1), m.group(2)) if m else ("", txt)
    tipo = TIPOS_TIER.get(tipo_txt.strip().lower(), tipo_txt.strip() or None)
    letra = letra.strip().rstrip(".")
    tier = "Misc" if letra.lower().startswith("m") else (letra.split("-")[0].strip().upper() or None)
    return tier, tipo


def torneos_dinero(txt):
    import re
    s = re.sub(r"[^\d.]", "", (txt or "").replace(",", ""))
    try:
        v = float(s) if s else None
    except ValueError:
        return None
    if v is None or v <= 0:
        return None
    return int(v) if v == int(v) else round(v, 2)


def torneos_tabla(html_txt):
    """Filas de la tabla «tournaments-listing» (HTML de action=parse). Tolerante: busca las columnas por su clase
    (column__tournament, column__placement) y no por posición fija; una fila ilegible se salta."""
    import urllib.parse
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.filas, self.fila, self.celda = [], None, None
            self.pila = []          # etiquetas abiertas dentro de la celda: (tag, es_nombre)

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            cls = a.get("class") or ""
            if tag == "tr":
                self.fila = [] if "row--body" in cls else None
            elif tag == "td" and self.fila is not None:
                self.celda = {"texto": "", "trozos": [], "enlaces": [], "nombres": [], "cls": cls}
                self.pila = []
            elif self.celda is not None and tag not in ("img", "br", "wbr", "hr", "input", "meta"):
                es_nombre = tag == "span" and "name" in cls.split()
                self.pila.append(es_nombre)
                if es_nombre:
                    self.celda["nombres"].append("")
                if tag == "a" and a.get("href"):
                    self.celda["enlaces"].append(a["href"])

        def handle_endtag(self, tag):
            if tag == "td" and self.celda is not None and self.fila is not None:
                self.fila.append(self.celda)
                self.celda = None
            elif tag == "tr" and self.fila is not None:
                if self.fila:
                    self.filas.append(self.fila)
                self.fila = None
            elif self.celda is not None and self.pila and tag not in ("img", "br", "wbr", "hr", "input", "meta"):
                self.pila.pop()

        def handle_data(self, data):
            if self.celda is not None:
                self.celda["texto"] += data
                self.celda["trozos"].append(data)
                if any(self.pila) and self.celda["nombres"]:
                    self.celda["nombres"][-1] += data

    p = P()
    p.feed(html_txt or "")
    out = []
    for celdas in p.filas:
        try:
            t = [" ".join(c["texto"].replace("\xa0", " ").split()) for c in celdas]
            i_t = next((i for i, c in enumerate(celdas) if "column__tournament" in c["cls"]), None)
            if i_t is None or len(celdas) < i_t + 3:
                continue
            href = next((h for h in celdas[i_t]["enlaces"] if h.startswith("/ageofempires/")), None)
            titulo = url = None
            if href and "redlink=1" not in href and "action=edit" not in href:
                ruta = href.split("#")[0]
                titulo = urllib.parse.unquote(ruta.split("/ageofempires/", 1)[1]).replace("_", " ")
                url = LQ_BASE + ruta
            tier, tipo = torneos_tier(t[0])
            ini, fin = torneos_fechas(t[i_t + 1])
            fila = {"nombre": t[i_t], "titulo": titulo, "url": url, "tier": tier, "tipo": tipo, "inicio": ini, "fin": fin,
                    "bolsa": torneos_dinero(t[i_t + 2]), "lugar": None, "participantes": None}
            resto = [(c, x) for c, x in zip(celdas[i_t + 3:], t[i_t + 3:]) if "column__placement" not in c["cls"]]
            if resto:      # varios lugares («World» + «Hamburg») vienen en spans separados
                lugares = [" ".join(x.split()) for x in resto[0][0]["trozos"]]
                fila["lugar"] = ", ".join(dict.fromkeys(x for x in lugares if x)) or None
            if len(resto) > 1 and resto[1][1].isdigit():
                fila["participantes"] = int(resto[1][1])
            plac = [c for c in celdas if "column__placement" in c["cls"]]
            for clave, c in zip(("ganador", "finalista"), plac):
                nombres = [" ".join(x.split()) for x in c["nombres"]]
                nombres = [x for x in nombres if x and x.upper() not in ("TBD", "TBA")]
                if nombres:
                    fila[clave] = " & ".join(nombres)
            out.append(fila)
        except Exception as ex:
            log(f"torneos: fila ilegible: {ex!r}")
    return out


def wiki_limpiar(v):
    """Valor de parámetro de plantilla → texto plano: quita comentarios, enlaces [[a|b]], {{!}}, plantillas y etiquetas."""
    import re
    v = re.sub(r"<!--.*?-->", "", v or "", flags=re.S)
    v = v.replace("{{!}}", "|")
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", v)
    for _ in range(3):
        v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"<[^>]+>", "", v)
    return " ".join(v.split()).strip()


def wiki_infobox(texto):
    """Parámetros del primer {{Infobox …}} del wikitexto (separa por «|» de primer nivel, respetando {{ }} y [[ ]])."""
    texto = texto or ""
    i = texto.find("{{Infobox")
    if i < 0:
        return {}
    prof, j, trozos, ini = 0, i, [], i + 2
    while j < len(texto):
        par = texto[j:j + 2]
        if par in ("{{", "[["):
            prof += 1
            j += 2
            continue
        if par in ("}}", "]]"):
            prof -= 1
            if prof == 0:
                trozos.append(texto[ini:j])
                break
            j += 2
            continue
        if texto[j] == "|" and prof == 1:
            trozos.append(texto[ini:j])
            ini = j + 1
        j += 1
    out = {}
    for t in trozos[1:]:
        if "=" in t:
            k, v = t.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


def torneos_formato(fmt):
    """«1v1, Single Elimination» → "1v1"; «1v1, 2v2, 4v4» → "mixto"; «FFA» → "FFA"; «Team» → "equipos"; nada → None."""
    import re
    modos = list(dict.fromkeys(f"{x}v{y}" for x, y in re.findall(r"\b(\d)\s*v\s*(\d)\b", fmt or "", re.I)))
    if len(modos) > 1:
        return "mixto"
    if modos:
        return modos[0]
    if re.search(r"\bffa\b|free[- ]for[- ]all", fmt or "", re.I):
        return "FFA"
    if re.search(r"\bteam", fmt or "", re.I):
        return "equipos"
    return None


def torneos_enriquecer(t, ib):
    """Completa un torneo con su infobox: organizador, formato, moneda local, y fechas y bolsa si la tabla no las dio."""
    import re
    orgs = [wiki_limpiar(ib[k]) for k in sorted(ib, key=lambda k: (len(k), k)) if re.fullmatch(r"organizer\d*", k)]
    orgs = [o for o in orgs if o]
    if orgs:
        t["organizador"] = ", ".join(dict.fromkeys(orgs))
    fmt = wiki_limpiar(ib.get("format", ""))
    if fmt:
        t["formato_texto"] = fmt
        t["formato"] = torneos_formato(fmt)
    if not t.get("formato"):
        t["formato"] = torneos_formato(wiki_limpiar(ib.get("mode", ""))) or torneos_formato(t.get("nombre"))
    for k_iso, k_ib in (("inicio", "sdate"), ("fin", "edate")):
        v = wiki_limpiar(ib.get(k_ib, ""))
        if not t.get(k_iso) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            t[k_iso] = v
    if t.get("bolsa") is None:
        t["bolsa"] = torneos_dinero(wiki_limpiar(ib.get("prizepoolusd", "")))
    local, moneda = torneos_dinero(wiki_limpiar(ib.get("prizepool", ""))), wiki_limpiar(ib.get("localcurrency", "")).upper()
    if local and moneda and moneda != "USD":
        t["bolsa_local"], t["moneda_local"] = local, moneda


def torneos_estado(t, hoy):
    ini = date.fromisoformat(t["inicio"])
    fin = date.fromisoformat(t["fin"]) if t.get("fin") else ini
    if fin < hoy:
        return "terminado"
    if ini > hoy:
        return "proximo"
    return "en_curso"


def torneos_en_ventana(filas, hoy):
    """Torneos cuyas fechas tocan la ventana [hoy - PASADO, hoy + FUTURO], sin duplicados (misma URL o mismo nombre y fecha)."""
    desde, hasta = hoy - timedelta(days=TORNEOS_DIAS_PASADO), hoy + timedelta(days=TORNEOS_DIAS_FUTURO)
    out, vistos, sin_fecha = [], set(), 0
    for f in filas:
        if not f.get("inicio"):
            sin_fecha += 1
            continue
        ini = date.fromisoformat(f["inicio"])
        fin = date.fromisoformat(f["fin"]) if f.get("fin") else ini
        if fin < desde or ini > hasta:
            continue
        clave = f.get("url") or (f["nombre"], f["inicio"])
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append(dict(f))
    if sin_fecha:
        log(f"torneos: {sin_fecha} filas sin fecha legible (fuera)")
    return out


def torneos_componer(filas, infoboxes, hoy, previo=None):
    """Lista final ordenada. infoboxes: {título: params}; si falta el de un torneo, organizador y formato se toman del
    torneos.json anterior (misma URL)."""
    previos = {t.get("url"): t for t in (previo or {}).get("torneos", []) if t.get("url")}
    out = []
    for f in torneos_en_ventana(filas, hoy):
        titulo = f.pop("titulo", None)
        ib = infoboxes.get(titulo) if titulo else None
        if ib:
            torneos_enriquecer(f, ib)
        elif f.get("url") in previos:
            for k in ("organizador", "formato", "formato_texto", "bolsa_local", "moneda_local"):
                if previos[f["url"]].get(k) is not None and f.get(k) is None:
                    f[k] = previos[f["url"]][k]
        f["fin"] = f.get("fin") or f["inicio"]
        f["estado"] = torneos_estado(f, hoy)
        f["moneda"] = "USD" if f.get("bolsa") is not None else None
        t = {k: f.get(k) for k in ("nombre", "tier", "tipo", "inicio", "fin", "estado", "bolsa", "moneda")}
        if f.get("bolsa_local") is not None:
            t.update(bolsa_local=f["bolsa_local"], moneda_local=f["moneda_local"])
        t.update({k: f.get(k) for k in ("formato", "formato_texto", "organizador", "lugar", "participantes", "url")})
        for k in ("ganador", "finalista"):
            if f.get(k):
                t[k] = f[k]
        out.append(t)
    en_curso = sorted((t for t in out if t["estado"] == "en_curso"), key=lambda t: (t["fin"], t["nombre"].lower()))
    proximos = sorted((t for t in out if t["estado"] == "proximo"), key=lambda t: (t["inicio"], t["nombre"].lower()))
    terminados = sorted((t for t in out if t["estado"] == "terminado"), key=lambda t: (t["fin"], t["inicio"]), reverse=True)
    return en_curso + proximos + terminados


def torneos_salida(lista, hoy):
    g = ahora()
    return {"v": 1, "generado": g, "hoy": hoy.isoformat(),
            "ventana": {"desde": (hoy - timedelta(days=TORNEOS_DIAS_PASADO)).isoformat(),
                        "hasta": (hoy + timedelta(days=TORNEOS_DIAS_FUTURO)).isoformat()},
            "fuente": {"nombre": "Liquipedia", "url": "https://liquipedia.net/ageofempires/", "licencia": "CC BY-SA 3.0",
                       "licencia_url": "https://creativecommons.org/licenses/by-sa/3.0/",
                       "atribucion": "Datos de torneos de Liquipedia (liquipedia.net/ageofempires), licencia CC BY-SA 3.0. "
                                     "Este archivo se distribuye con la misma licencia.",
                       "generado": g},
            "torneos": lista}


def torneos_infoboxes(lq, titulos):
    """Wikitexto de los torneos (action=query, 50 títulos por petición) → {título como sale en la tabla: params del infobox}."""
    out = {}
    titulos = list(dict.fromkeys(titulos))
    for k in range(0, len(titulos), LQ_TITULOS_POR_QUERY):
        lote = titulos[k:k + LQ_TITULOS_POR_QUERY]
        d = lq.get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "redirects": "1",
                    "titles": "|".join(lote)})
        q = d.get("query", {})
        origen = {}       # título final → título pedido (deshace normalización y redirecciones)
        for r in (q.get("normalized") or []) + (q.get("redirects") or []):
            origen[r["to"]] = origen.get(r["from"], r["from"])
        for p in q.get("pages", []):
            revs = p.get("revisions") or []
            if not revs:
                continue
            ib = wiki_infobox(revs[0].get("slots", {}).get("main", {}).get("content", ""))
            out[p["title"]] = ib
            if p["title"] in origen:
                out[origen[p["title"]]] = ib
    return out


def torneos():
    """torneos.json desde Liquipedia (esquema en la cabecera, normas arriba). Si algo falla o no sale ningún torneo, no se
    escribe: se queda el anterior (recuperado de la rama data) con aviso ::warning:: en el resumen; el paso no rompe el build."""
    hoy = datetime.now(timezone.utc).date()
    previo = leer_json("torneos.json", None)
    lq = Liquipedia()
    filas, infob = [], {}
    try:
        d = lq.get({"action": "parse", "title": "Age_of_Empires_II/Tournaments", "contentmodel": "wikitext", "prop": "text",
                    "text": torneos_wikitexto(hoy), "disablelimitreport": "1", "disableeditsection": "1"})
        filas = torneos_tabla(d.get("parse", {}).get("text", ""))
        log(f"torneos: años {torneos_anios(hoy)}: {len(filas)} filas")
        if not filas:
            raise RuntimeError("ninguna fila en la tabla de TournamentsList")
        candidatos = torneos_en_ventana(filas, hoy)
        try:
            infob = torneos_infoboxes(lq, [c["titulo"] for c in candidatos if c.get("titulo")])
        except Exception as ex:
            print(f"::warning title=torneos::sin infoboxes ({ex!r}): organizador y formato, del torneos.json anterior", flush=True)
        lista = torneos_componer(filas, infob, hoy, previo)
        if not lista:
            raise RuntimeError(f"{len(filas)} filas pero ninguna en la ventana")
    except Exception as ex:
        print(f"::warning title=torneos::Liquipedia no respondió bien ({ex!r}): se conserva el torneos.json anterior", flush=True)
        return
    finally:
        lq.cerrar()
    escribir_json("torneos.json", torneos_salida(lista, hoy))
    cuenta = defaultdict(int)
    for t in lista:
        cuenta[t["estado"]] += 1
    log(f"torneos: {len(lista)} torneos ({dict(cuenta)}); {len({id(v) for v in infob.values()})} infoboxes; {lq.peticiones} peticiones a Liquipedia")


def torneos_probar():
    """Prueba sin red: muestra guardada (HTML de action=parse recortado + wikitexto de infoboxes) con una fecha fija."""
    m = leer_json(TORNEOS_MUESTRA)
    hoy = date.fromisoformat(m["hoy"])
    filas = torneos_tabla(m["html"])
    infob = {titulo: wiki_infobox(texto) for titulo, texto in m["wikitexto"].items()}
    lista = torneos_componer(filas, infob, hoy)
    fallos = []
    for esperado in m["esperado"]:
        t = next((x for x in lista if x["nombre"] == esperado["nombre"]), None)
        if t is None:
            fallos.append(f"falta {esperado['nombre']}")
            continue
        for k, v in esperado.items():
            if t.get(k) != v:
                fallos.append(f"{esperado['nombre']}: {k} = {t.get(k)!r}, se esperaba {v!r}")
        for k in ("ganador", "finalista"):
            if k not in esperado and k in t:
                fallos.append(f"{esperado['nombre']}: {k} no debería estar")
    for nombre in m.get("fuera", []):
        if any(x["nombre"] == nombre for x in lista):
            fallos.append(f"{nombre} no debería salir")
    casos = {"Oct 17, 2026": ("2026-10-17", "2026-10-17"), "Nov 30 – Dec 20, 2026": ("2026-11-30", "2026-12-20"),
             "Oct 05–31, 2026": ("2026-10-05", "2026-10-31"), "Nov 28, 2025 – Jan 01, 2026": ("2025-11-28", "2026-01-01"),
             "Dec 28 – Jan 03, 2027": ("2026-12-28", "2027-01-03"), "TBA": (None, None), "Oct 2026": (None, None), "": (None, None)}
    for txt, esp in casos.items():
        if torneos_fechas(txt) != esp:
            fallos.append(f"fechas {txt!r} → {torneos_fechas(txt)}, se esperaba {esp}")
    for txt, esp in {"S-Tier": ("S", None), "Qualifier\xa0(A)": ("A", "Qualifier"), "Weekly (M.)": ("Misc", "Weekly"),
                     "Misc": ("Misc", None), "C-Tier": ("C", None), "": (None, None)}.items():
        if torneos_tier(txt) != esp:
            fallos.append(f"tier {txt!r} → {torneos_tier(txt)}, se esperaba {esp}")
    for d, esp in ((date(2026, 10, 18), [2026, 2027]), (date(2027, 1, 10), [2026, 2027, 2028]), (date(2027, 12, 20), [2027, 2028])):
        if torneos_anios(d) != esp:
            fallos.append(f"años {d}: {torneos_anios(d)}, se esperaba {esp}")
    for txt, esp in {"1v1, Single Elimination": "1v1", "1v1, 2v2, 4v4": "mixto", "3v3 Round Robin": "3v3", "FFA": "FFA",
                     "Team": "equipos", "": None, "CBA 4v4 Tournament": "4v4"}.items():
        if torneos_formato(txt) != esp:
            fallos.append(f"formato {txt!r} → {torneos_formato(txt)}, se esperaba {esp}")
    if torneos_tabla("<p>nada</p>") != [] or torneos_tabla("") != []:
        fallos.append("HTML sin tabla debería dar []")
    for t in lista:
        log(f"  {t['estado']:9} {t['inicio']} → {t['fin']}  {t['tier'] or '-':4} {t['nombre']}")
    for f in fallos:
        log("FALLO", f)
    log(f"torneos --probar: {len(lista)} torneos, {len(fallos)} fallos")
    return not fallos


# ----------------------------------------------------------------------------- noticias (ageofempires.com)
# Fuente: la API REST pública de WordPress de https://www.ageofempires.com (la misma que anuncia la web con
# <link rel="https://api.w.org/">). Se prefiere al RSS (/news/feed/) porque el RSS solo trae 5 entradas de todos los juegos,
# va con retraso y lleva el cuerpo entero de cada artículo, que aquí no se quiere. robots.txt no existe (404) y los términos
# de la web (Microsoft Services Agreement) no impiden enlazar titulares; solo se guardan titular, fecha, categoría, enlace y
# la URL de la miniatura (288x162 del CDN de la web), nunca el texto. Filtro por la taxonomía «game» de la web:
# 218 = «Age of Empires II DE», 29 = «Age of Empires II HD». Por noche: 3 peticiones (entradas, categorías, miniaturas),
# una conexión, gzip, User-Agent con contacto y 2,5 s entre peticiones.
# Liquipedia no se usa aquí: la wiki de AoE no tiene noticias y «Recent changes» es ruido de ediciones; los torneos ya van
# en torneos.json.
AOE_HOST = "www.ageofempires.com"
AOE_API = "/wp-json/wp/v2/"
AOE_ESPERA_S = 2.5
AOE_GAMES_AOE2 = (218, 29)
AOE_HOSTS_OK = {"www.ageofempires.com", "ageofempires.com"}
AOE_HOSTS_IMG = {"cdn.ageofempires.com", "www.ageofempires.com"}
NOTICIAS_MAX = 30
NOTICIAS_MUESTRA = os.path.join("pruebas", "noticias_muestra.json")
NOTICIAS_FUENTE = {"nombre": "Age of Empires (web oficial)", "url": "https://www.ageofempires.com/news/"}


class WebAoE:
    """Cliente mínimo de la API REST de ageofempires.com: conexión HTTPS reutilizada, gzip y espera entre peticiones."""

    def __init__(self):
        import http.client
        self._hc = http.client
        self.con = None
        self.ultima = 0.0
        self.peticiones = 0

    def get(self, ruta, params, intentos=2):
        import urllib.parse
        url = AOE_API + ruta + "?" + urllib.parse.urlencode(params)
        for i in range(intentos):
            if self.peticiones:
                espera = self.ultima + AOE_ESPERA_S - time.monotonic()
                if espera > 0:
                    time.sleep(espera)
            self.ultima = time.monotonic()
            self.peticiones += 1
            try:
                if self.con is None:
                    self.con = self._hc.HTTPSConnection(AOE_HOST, timeout=60)
                self.con.request("GET", url, headers={"User-Agent": LQ_UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
                r = self.con.getresponse()
                raw = r.read()
                if (r.getheader("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(raw.decode("utf-8"))
            except Exception as ex:
                log(f"noticias: petición {ruta} {i + 1}/{intentos}: {ex!r}")
                try:
                    self.con.close()
                except Exception:
                    pass
                self.con = None
                if i == intentos - 1:
                    raise
                time.sleep(5)

    def cerrar(self):
        if self.con is not None:
            self.con.close()


def noticias_texto(v):
    """HTML de WordPress → texto plano: entidades (&#8211;), etiquetas fuera y espacios raros (NBSP, \\u202f) normalizados."""
    import html, re
    v = re.sub(r"<[^>]+>", "", v or "")
    v = html.unescape(v)
    return " ".join(v.replace(" ", " ").replace("\xa0", " ").split()).strip()


def noticias_url_ok(url, hosts):
    import urllib.parse
    try:
        u = urllib.parse.urlsplit(url or "")
    except ValueError:
        return False
    return u.scheme == "https" and u.hostname in hosts


def noticias_imagen(media):
    """Miniatura pequeña de un adjunto: «medium» (288x162) → «thumbnail» (150x150) → «medium_large»; nunca el original."""
    tam = (media.get("media_details") or {}).get("sizes") or {}
    for k in ("medium", "thumbnail", "medium_large"):
        url = (tam.get(k) or {}).get("source_url")
        if noticias_url_ok(url, AOE_HOSTS_IMG):
            return url
    return None


def noticias_componer(posts, categorias, medios, previo=None):
    """Entradas de la API → lista de noticias (más reciente primero, sin duplicados, máx. NOTICIAS_MAX).
    categorias: {id: nombre}; medios: {id: url miniatura}. Si no hay categorías o miniaturas (petición caída: dict vacío),
    se toman las del noticias.json anterior con la misma URL."""
    previos = {n.get("url"): n for n in (previo or {}).get("noticias", []) if n.get("url")}
    out, vistos = [], set()
    for p in posts:
        try:
            if p.get("status", "publish") != "publish":
                continue
            if p.get("game") is not None and not set(p["game"]) & set(AOE_GAMES_AOE2):
                continue
            titulo = noticias_texto((p.get("title") or {}).get("rendered"))
            url = p.get("link")
            fecha = datetime.fromisoformat(p["date_gmt"]).replace(tzinfo=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            if not titulo or not noticias_url_ok(url, AOE_HOSTS_OK) or url in vistos:
                continue
            vistos.add(url)
            n = {"titulo": titulo, "fecha": fecha, "fuente": NOTICIAS_FUENTE["nombre"], "url": url}
            noms = [categorias[c] for c in p.get("categories") or [] if categorias.get(c)]
            cat = next((c for c in noms if c.lower() != "general"), noms[0] if noms else None)
            img = medios.get(p.get("featured_media")) if p.get("featured_media") else None
            ant = previos.get(url, {})
            if not categorias:
                cat = ant.get("categoria")
            if not medios:
                img = ant.get("imagen")
            if cat:
                n["categoria"] = cat
            if img:
                n["imagen"] = img
            out.append(n)
        except Exception as ex:
            log(f"noticias: entrada ilegible ({p.get('id')}): {ex!r}")
    out.sort(key=lambda n: n["fecha"], reverse=True)
    return out[:NOTICIAS_MAX]


def noticias_salida(lista, fuentes):
    return {"v": 1, "generado": ahora(), "fuentes": fuentes, "noticias": lista}


def noticias():
    """noticias.json: titulares de AoE II de la web oficial (esquema en la cabecera, normas arriba). Si la fuente falla o no da
    ninguna noticia, no se escribe: se queda el anterior (recuperado de la rama data) con aviso ::warning::. Si solo fallan
    categorías o miniaturas, se publica igual y esos campos salen del noticias.json anterior (misma URL) o se omiten."""
    previo = leer_json("noticias.json", None)
    web = WebAoE()
    categorias, medios = {}, {}
    try:
        posts = web.get("posts", {"game": ",".join(map(str, AOE_GAMES_AOE2)), "per_page": NOTICIAS_MAX, "orderby": "date",
                                  "order": "desc", "_fields": "id,date_gmt,link,title,categories,featured_media,game,status"})
        if not isinstance(posts, list) or not posts:
            raise RuntimeError("la API no devolvió ninguna entrada")
        try:
            ids = sorted({c for p in posts for c in p.get("categories") or []})
            if ids:
                d = web.get("categories", {"include": ",".join(map(str, ids)), "per_page": 100, "_fields": "id,name"})
                categorias = {c["id"]: noticias_texto(c.get("name")) for c in d}
        except Exception as ex:
            print(f"::warning title=noticias::sin categorías ({ex!r}): se toman del noticias.json anterior", flush=True)
        try:
            ids = sorted({p["featured_media"] for p in posts if p.get("featured_media")})
            if ids:
                d = web.get("media", {"include": ",".join(map(str, ids)), "per_page": 100, "_fields": "id,media_details"})
                medios = {m["id"]: noticias_imagen(m) for m in d if noticias_imagen(m)}
        except Exception as ex:
            print(f"::warning title=noticias::sin miniaturas ({ex!r}): se toman del noticias.json anterior", flush=True)
        lista = noticias_componer(posts, categorias, medios, previo)
        if not lista:
            raise RuntimeError(f"{len(posts)} entradas pero ninguna válida")
    except Exception as ex:
        print(f"::warning title=noticias::ageofempires.com no respondió bien ({ex!r}): se conserva el noticias.json anterior", flush=True)
        return
    finally:
        web.cerrar()
    escribir_json("noticias.json", noticias_salida(lista, [NOTICIAS_FUENTE]))
    log(f"noticias: {len(lista)} noticias (la más reciente {lista[0]['fecha'][:10]}); "
        f"{sum('imagen' in n for n in lista)} con imagen; {web.peticiones} peticiones a ageofempires.com")


def noticias_probar():
    """Prueba sin red: respuestas guardadas de la API (sin cuerpos) y casos límite."""
    m = leer_json(NOTICIAS_MUESTRA)
    categorias = {c["id"]: noticias_texto(c["name"]) for c in m["categorias"]}
    medios = {x["id"]: noticias_imagen(x) for x in m["medios"] if noticias_imagen(x)}
    lista = noticias_componer(m["posts"], categorias, medios)
    fallos = []
    for esperado in m["esperado"]:
        n = next((x for x in lista if x["url"] == esperado["url"]), None)
        if n is None:
            fallos.append(f"falta {esperado['url']}")
            continue
        for k, v in esperado.items():
            if n.get(k) != v:
                fallos.append(f"{esperado['url']}: {k} = {n.get(k)!r}, se esperaba {v!r}")
        for k in ("categoria", "imagen"):
            if k not in esperado and k in n:
                fallos.append(f"{esperado['url']}: {k} no debería estar")
    for url in m.get("fuera", []):
        if any(x["url"] == url for x in lista):
            fallos.append(f"{url} no debería salir")
    if len(lista) != m["total"]:
        fallos.append(f"{len(lista)} noticias, se esperaban {m['total']}")
    if [n["fecha"] for n in lista] != sorted((n["fecha"] for n in lista), reverse=True):
        fallos.append("orden: no va de la más reciente a la más antigua")
    if len({n["url"] for n in lista}) != len(lista):
        fallos.append("hay URLs duplicadas")
    if any(set(n) - {"titulo", "fecha", "fuente", "url", "categoria", "imagen"} for n in lista):
        fallos.append("campos de más en alguna noticia")
    # categorías y miniaturas caídas: se heredan del noticias.json anterior por URL
    previo = noticias_salida(lista, [NOTICIAS_FUENTE])
    sin = noticias_componer(m["posts"], {}, {}, previo)
    if [(n.get("categoria"), n.get("imagen")) for n in sin] != [(n.get("categoria"), n.get("imagen")) for n in lista]:
        fallos.append("sin categorías/miniaturas no se heredan del noticias.json anterior")
    if noticias_componer([], categorias, medios) != []:
        fallos.append("sin entradas debería dar [] (y noticias() no escribe)")
    for txt, esp in {"Update&nbsp;185872 &#8211; Notes": "Update 185872 – Notes", "Celebrating Age <em>2026</em>": "Celebrating Age 2026",
                     "  ": "", None: ""}.items():
        if noticias_texto(txt) != esp:
            fallos.append(f"texto {txt!r} → {noticias_texto(txt)!r}, se esperaba {esp!r}")
    for n in lista:
        log(f"  {n['fecha'][:10]}  {n.get('categoria') or '-':40.40} {n['titulo']}")
    for f in fallos:
        log("FALLO", f)
    log(f"noticias --probar: {len(lista)} noticias, {len(fallos)} fallos")
    return not fallos


if __name__ == "__main__":
    if "--probar" in sys.argv:          # sin red: torneos y noticias (o solo los nombrados: --probar noticias)
        pruebas = {"torneos": torneos_probar, "noticias": noticias_probar}
        pedidas = [a for a in sys.argv[1:] if a in pruebas] or list(pruebas)
        resultados = [pruebas[a]() for a in pedidas]
        sys.exit(0 if all(resultados) else 1)
    pasos = (("ladder", ladder), ("civstats", civstats), ("mapas", mapas), ("torneos", torneos), ("noticias", noticias),
             ("perfiles", perfiles))
    pedidos = [a for a in sys.argv[1:] if not a.startswith("-")]     # sin argumentos, todos (el build nocturno)
    ok = True
    for nombre, fn in pasos:
        if pedidos and nombre not in pedidos:
            continue
        try:
            fn()
        except Exception as ex:
            ok = False
            import traceback
            traceback.print_exc()
            log(f"{nombre}: ERROR {ex!r}")
    sys.exit(0 if ok else 1)
