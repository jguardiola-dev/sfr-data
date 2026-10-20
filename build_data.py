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
                                  "participantes", "url", ["enlaces"], ["logo", "logo_oscuro"], ["detalle"],
                                  ["ganador", "finalista"]}]}
                     «detalle» (opcional): "torneos/<slug>.json" si hay ficha de detalle de ese torneo (ver más abajo).
                     «enlaces» (opcional, del infobox): {"web","discord","twitch","youtube","x","bracket","reglamento"}
                     (reglamento = el «rulebook»/handbook del organizador: PDF, Google Drive…), cada uno solo si
                     Liquipedia lo da y es una URL https válida (los identificadores sueltos se completan: twitch.tv/…, x.com/…).
                     ganador/finalista solo si Liquipedia los da (la app los esconde: sin spoilers); varios jugadores se unen
                     con « & ». Orden: en_curso (por fin), proximo (por inicio), terminado (el más reciente primero).
                     «logo» / «logo_oscuro» (opcionales; ver torneos_logos()): {"archivo":"logos/torneos/<x>.png" (ruta
                     relativa a la raíz de la rama data), "fuente": URL de la página File: de Liquipedia Commons, "credito":
                     texto para mostrar, ["licencia"]: la de la ficha del archivo tal cual («fairuse», «fairuselogo», «pd»…)}.
                     logo = image (o «allmode», sirve para los dos temas) o, si no hay, icon; logo_oscuro solo si el infobox
                     da una variante distinta para tema oscuro (imagedark/icondark). Los logos son marcas de sus dueños, NO
                     van con la CC BY-SA de los datos: la app debe enseñar «credito» (o enlazar «fuente») junto al logo.
                     Si Liquipedia falla o no sale ningún torneo, se conserva el torneos.json anterior (rama data).
                     Prueba sin red: python build_data.py --probar (muestra en pruebas/). Solo este paso: python build_data.py torneos
- torneos_historico.json  el mismo esquema que torneos.json, pero con TODOS los torneos que da {{TournamentsList}} para los
                     años de torneos_anios() (el año en curso y el siguiente; en enero, también el anterior), sin recortar a
                     la ventana: «ventana» = {"desde":"AAAA-01-01","hasta":"AAAA-12-31"}. Mismo orden. Lo escribe torneos().
- logos/torneos/*.png     logos de torneo: PNG de 96 px de alto como mucho (384 de ancho), descargados UNA vez de Liquipedia
                     Commons (no se enlazan: Liquipedia pide no hacer hotlink). Nombre = archivo de Liquipedia en minúsculas +
                     sha1[:8] del archivo (clave de caché: un logo nuevo en la wiki cambia el hash y se baja otra vez). Los
                     que ya no usa ningún torneo de torneos.json/torneos_historico.json se borran. Carpeta en la rama data.
- torneos/<slug>.json  detalle de los torneos importantes (S y A del histórico; B en curso o próximos; C en curso), de su página de
                     Liquipedia (action=parse; ver torneos_detalle()). slug = ruta de la página en minúsculas con «-»
                     («Warlords/5» → warlords-5). Lo enlaza el campo «detalle» de torneos.json/torneos_historico.json. Esquema (v3; v2 = sin «tablas» ni
                     «jornadas»; v1 = sin «cuadros»):
                     {"v":3, "url", "nombre", "tier", "inicio", "fin", "obtenido":ISO, "estado_al_obtener",
                      "formato":[{"texto","nivel"}] (lista de la sección Format; nivel = sangría, 0 = primera),
                      "calendario":[{"texto","nivel","desde":"AAAA-MM-DD"|null,["hasta"]}] (sección Schedule),
                      "mapas":["Arabia"…],
                      "premios":{"total_usd":número|null, "puestos":[{"puesto":"5-8","desde":5,"hasta":8,["usd"],["otros":[…]]}]},
                      "participantes":[{"nombre",["pais"] (ISO2),["grupo"] (Invited, Qualifier #1…),["sembrado"]} |
                                       {"nombre","tipo":"equipo",["jugadores":[{"nombre",["pais"]}]]}],
                      "fases":[{"nombre","nivel" (1 = fase, 2 = grupo/subfase),["tipo":"grupos|bracket|partidos"],
                                ["rondas":[{"nombre","bo"}]],
                                ["cuadros":[{"rondas":[{"nombre",["bo"],"partidos":[{"j1","j2",["p1","p2"],["ganador":1|2]}]}]}]]}]
                               (subsecciones de Results, o Results misma si el cuadro va sin subsección). «cuadros»: solo
                               en tipo bracket, uno por fila de encabezados (superior, inferior…), las rondas en columnas
                               de izquierda a derecha y los partidos de arriba abajo; j1/j2 = {"nombre",["pais"]} o null
                               (TBD); p1/p2 = marcador como texto («4», «W», «FF»). SPOILER: quién llega a cada ronda,
                               marcadores y ganador (la app los esconde hasta que el usuario pide el resultado).
                               ["tablas":[{"nombre",["tras"],"filas":[{["pos"],"nombre",["pais"],["partidos"],["juegos"],
                                          ["dif"],["puntos"],["zona":"sube|sigue|baja"]}]}]] clasificación de la fase (la
                               «grouptable» de Liquipedia, tal como está: «partidos» = «6-0-0» o «2-1», «juegos» = «18-4»,
                               «dif» = «+14», «puntos» = 18; «tras» = la jornada a la que corresponde, «Week 9», si la
                               tabla tiene varias); ["jornadas":[{"nombre","partidos":[{"j1","j2",["p1","p2"],
                               ["ganador":1|2],["fecha":ISO UTC],["bo"]}]}]] los partidos por jornada o ronda (las
                               «matchlist»: Round 1, Week 3…), con su fecha y su Bo.
                      "resultados":{"puestos":[{"puesto","desde","hasta","jugadores":[…]}]}}
                     SIN SPOILERS: quién quedó en qué puesto va SOLO en «resultados» y «cuadros» (la app los esconde); «premios» nunca
                     lleva nombres. Los partidos no se repiten aquí: están en partidos.json (torneo_url). Como mucho
                     TORNEOS_DETALLE_POR_NOCHE páginas por noche, los torneos EN CURSO primero; en curso se renueva
                     cada noche, próximo cada 3 días, terminado una vez tras acabar. Lo anterior se conserva si una página falla.
                     Prueba sin red: python build_data.py --probar detalle. Solo este paso: python build_data.py detalle
- streamers.json     imagen de perfil pública de canales de Twitch (API Helix; ver streamers()). Esquema (v1):
                     {"v":1, "generado":ISO, "fuente":"Twitch (imagen de perfil pública, solo para dar crédito y enlazar al canal)",
                      "canales":{"<login>":{"nombre", "avatar_url" (https://static-cdn.jtvnw.net/…), "url":"https://twitch.tv/<login>"}},
                      "creadores":{"<creador de build orders>":"<login>"} (solo los que Twitch conoce; ver STREAMERS_CREADORES),
                      "en_directo":["<login>"…] (top de AoE II en Twitch a la hora del build, por espectadores)}
                     Canales = creadores + top 20 en directo + streams de partidos.json + enlaces.twitch de torneos.json + los
                     del streamers.json anterior (tope 100). Solo se guarda la URL del avatar (CDN de Twitch), no la imagen.
                     Necesita TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET en el entorno (secretos de Actions); sin ellos, ::notice
                     y se conserva el anterior; si Twitch falla o no sale ningún canal, también se conserva el anterior.
                     Prueba sin red: python build_data.py --probar streamers. Solo este paso: python build_data.py streamers
- noticias.json      titulares recientes de AoE II de la web oficial (API REST pública de ageofempires.com, juegos AoE II DE/HD).
                     Solo titular, fecha, fuente, enlace, categoría y miniatura; nunca el cuerpo. Ver noticias(). Esquema (v1):
                     {"v":1, "generado":ISO, "fuentes":[{"nombre","url"}],
                      "noticias":[{"titulo", "fecha":"AAAA-MM-DDTHH:MM:SSZ", "fuente", "url", ["categoria"], ["imagen"], ["portada"]}]}
                     Como mucho NOTICIAS_MAX, la más reciente primero. «imagen» = URL de la miniatura 288x162 del CDN de la web.
                     «portada» = "noticias/<sha1[:12]>.jpg": la imagen destacada pasada a JPEG 16:9 (NOTICIAS_PORTADA_W x
                     NOTICIAS_PORTADA_H) con Pillow, ruta relativa a la raíz de la rama data (la web sirve WebP y Java no lo lee).
- noticias/*.jpg     portadas de noticias.json (ver noticias_portadas()): bajadas UNA vez del CDN de la web (nombre = sha1 de la
                     URL de origen) y borradas cuando ya no las usa ninguna noticia. Carpeta en la rama data.
                     Si la web falla o no sale ninguna noticia, se conserva el noticias.json anterior (rama data).
                     Prueba sin red: python build_data.py --probar [noticias]. Solo este paso: python build_data.py noticias
- partidos.json      partidos de torneos de AoE II según el «match ticker» de Liquipedia: terminados de las últimas 24 h, en curso
                     y próximos 7 días. Ver partidos(). Se regenera también cada 2 h (.github/workflows/partidos.yml). Esquema (v1):
                     {"v":1, "generado":ISO, "ventana":{"desde","hasta"} (ISO UTC),
                      "fuente":{"nombre":"Liquipedia","url","licencia":"CC BY-SA 3.0","licencia_url","atribucion","generado"},
                      "partidos":[{"torneo", "torneo_url", ["fase"], "inicio":"AAAA-MM-DDTHH:MM:SSZ" (UTC),
                                   "estado":"proximo|en_curso|terminado", "j1", "j2", ["j1_pais", "j2_pais"] (ISO2, solo
                                   jugador individual), ["formato":"Bo3"…], ["stream"] (https://www.twitch.tv/… o canal de
                                   YouTube /live; solo si no ha terminado), ["resultado":"2-1"|"W-L"…], ["ganador"]}]}
                     torneo_url = la misma forma que «url» en torneos.json (para cruzarlos). j1/j2: jugador, equipo (nombre
                     completo) o «A & B»; «TBD» si falta uno (si faltan los dos, el partido no sale). resultado y ganador
                     van SOLO en esos campos (la app los esconde: sin spoilers); en empate no hay ganador. en_curso = sin
                     terminar y empezado hace <= PARTIDOS_EN_CURSO_MAX_H h (más viejo = nadie lo cerró en la wiki: fuera).
                     Orden: en_curso y proximo por inicio, terminado el más reciente primero.
                     Si Liquipedia falla, el ticker viene vacío o con error, o nada cae en la ventana y el anterior tenía
                     partidos, se conserva el partidos.json anterior (rama data) con aviso ::warning::.
                     Prueba sin red: python build_data.py --probar [partidos]. Solo este paso: python build_data.py partidos
Fuente: volcados diarios de aoe2companion (https://www.aoe2companion.com/more/api).
Torneos y partidos: Liquipedia (https://liquipedia.net/ageofempires/), CC BY-SA 3.0; torneos.json y partidos.json se
publican con la misma licencia.
Logos de torneo: Liquipedia Commons; cada logo es marca de su titular (licencia de su ficha, casi siempre «fair use»).
Avatares: Twitch (URL pública del CDN de Twitch, enlazando al canal).
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
# bolsa en USD, lugar, participantes, ganador y finalista, y ≈5 action=query (50 títulos cada una) con el wikitexto de todos
# los torneos de la tabla (los de la ventana primero) para sacar del infobox organizador, formato, moneda local, enlaces y el
# nombre del logo (ver torneos_logos()). Contenido CC BY-SA 3.0.
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
TORNEOS_HISTORICO = "torneos_historico.json"
LQ_API_COMMONS = "/commons/api.php"     # los archivos (logos) viven en Liquipedia Commons: ahí está su ficha {{FileInfo}}
LOGOS_DIR = os.path.join("logos", "torneos")
LOGOS_ALTO = 96                 # alto máximo del PNG publicado
LOGOS_ANCHO_MAX = 384           # ancho máximo (logos apaisados: 4:1)
LOGOS_MAX_BYTES = 2_000_000     # una miniatura de 96 px nunca pesa esto: si lo pesa, no se baja
LOGOS_MAX_PIXELES = 4_000_000   # tope para Pillow (bomba de descompresión)
LOGOS_MAX_DESCARGAS = 80        # logos nuevos por noche (2,5 s cada uno); los que falten bajan la noche siguiente
LOGOS_LICENCIAS = {"fairuse": "uso legítimo (fair use)", "fairuselogo": "logo, uso legítimo (fair use)",
                   "permission": "con permiso del titular", "copyright": "con copyright", "cc-by-sa": "CC BY-SA",
                   "cc-by-sa-3.0": "CC BY-SA 3.0", "cc-by-sa-4.0": "CC BY-SA 4.0", "cc-by": "CC BY", "cc0": "CC0",
                   "pd": "dominio público", "publicdomain": "dominio público"}
TIPOS_TIER = {"qualifier": "Qualifier", "weekly": "Weekly", "monthly": "Monthly", "showmatch": "Showmatch", "ffa": "FFA",
              "biweekly": "Biweekly", "charity": "Charity"}


class Liquipedia:
    """Cliente mínimo de la API MediaWiki de Liquipedia: conexión HTTPS reutilizada, gzip y esperas entre peticiones."""

    # las esperas son de la clase, no de cada cliente: torneos() y partidos() en la misma ejecución comparten el ritmo
    # (el action=parse de partidos espera 30 s desde el de torneos)
    _ultima = None
    _ultima_parse = None

    def __init__(self, api=LQ_API):
        import http.client
        self._hc = http.client
        self.api = api              # /ageofempires/api.php; /commons/api.php para las fichas de los archivos (mismo host y ritmo)
        self.con = None
        self.peticiones = 0
        self.descargas = 0

    @classmethod
    def _esperar(cls, parse):
        t = time.monotonic()
        espera = max((cls._ultima + LQ_ESPERA_S - t) if cls._ultima is not None else 0,
                     (cls._ultima_parse + LQ_ESPERA_PARSE_S - t) if parse and cls._ultima_parse is not None else 0, 0)
        if espera > 0:
            time.sleep(espera)

    def get(self, params, intentos=2):
        import urllib.parse
        parse = params.get("action") == "parse"
        ruta = self.api + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion="2"))
        for i in range(intentos):
            self._esperar(parse)
            Liquipedia._ultima = time.monotonic()
            if parse:
                Liquipedia._ultima_parse = Liquipedia._ultima
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
                log(f"liquipedia: petición {params.get('action')} {i + 1}/{intentos}: {ex!r}")
                try:
                    self.con.close()
                except Exception:
                    pass
                self.con = None
                if i == intentos - 1:
                    raise

    def descargar(self, url, max_bytes=LOGOS_MAX_BYTES):
        """Un archivo de imagen de https://liquipedia.net/commons/images/… (no es HTML de páginas: es el fichero que la API
        da en imageinfo), por la misma conexión y con el mismo ritmo que las peticiones a la API. Un intento; None si falla."""
        import urllib.parse
        u = urllib.parse.urlsplit(url or "")
        if u.scheme != "https" or u.hostname != LQ_HOST or not u.path.startswith("/commons/images/"):
            log(f"liquipedia: descarga rechazada (no es de {LQ_HOST}/commons/images/): {url!r}")
            return None
        self._esperar(False)
        Liquipedia._ultima = time.monotonic()
        self.descargas += 1
        try:
            if self.con is None:
                self.con = self._hc.HTTPSConnection(LQ_HOST, timeout=60)
            self.con.request("GET", u.path + (("?" + u.query) if u.query else ""),
                             headers={"User-Agent": LQ_UA, "Accept-Encoding": "gzip", "Accept": "image/*"})
            r = self.con.getresponse()
            raw = r.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise RuntimeError(f"más de {max_bytes} bytes")
            r.read()
            if (r.getheader("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
            if r.status != 200:
                raise RuntimeError(f"HTTP {r.status}")
            return raw
        except Exception as ex:
            log(f"liquipedia: descarga {url}: {ex!r}")
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None
            return None

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
            self.modo_icono = None  # dentro de un <span class="league-icon-small-image [lightmode|darkmode]">

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            cls = a.get("class") or ""
            if self.celda is not None and tag == "span" and "league-icon-small-image" in cls.split():
                self.modo_icono = "oscuro" if "darkmode" in cls.split() else "claro"
            if self.celda is not None and tag == "img" and self.modo_icono and a.get("src"):
                self.celda.setdefault("iconos", []).append((self.modo_icono, a["src"]))
                self.modo_icono = None
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
            for modo, src in (x for c in celdas[:i_t] for x in c.get("iconos", [])):
                nombre_icono = logos_de_src(src)
                if nombre_icono and ("icono_" + modo) not in fila:
                    fila["icono_" + modo] = nombre_icono
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
    enlaces = torneos_enlaces(ib)
    if enlaces:
        t["enlaces"] = enlaces


# parámetro del infobox → (clave en «enlaces», prefijo para un identificador suelto; None = solo URL completa). Prefijos
# como los de Module:Links de Liquipedia (twitter → x.com). Solo el primero de cada uno (twitch, no twitch2).
TORNEOS_ENLACES = (("website", "web", None), ("web", "web", None), ("discord", "discord", "https://discord.gg/"),
                   ("twitch", "twitch", "https://www.twitch.tv/"), ("youtube", "youtube", "https://www.youtube.com/"),
                   ("twitter", "x", "https://x.com/"), ("x", "x", "https://x.com/"), ("bracket", "bracket", None),
                   ("rulebook", "reglamento", None), ("rules", "reglamento", None), ("handbook", "reglamento", None))


def url_https_ok(url):
    """URL https con host y sin espacios ni comillas/ángulos (va tal cual a la app)."""
    import re, urllib.parse
    if not url or re.search(r"[\s<>\"'\\]", url):
        return False
    try:
        u = urllib.parse.urlsplit(url)
        return (u.scheme == "https" and u.username is None
                and re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", u.hostname or "") is not None)
    except ValueError:
        return False


def torneos_enlaces(ib):
    """Enlaces del torneo desde el infobox: {"web","discord","twitch","youtube","x","bracket","reglamento"} (solo los que haya, solo
    https válidas). Un identificador suelto (twitch=beingesports, youtube=@x, discord=AbC123) se completa con el prefijo."""
    import re
    out = {}
    for param, clave, prefijo in TORNEOS_ENLACES:
        if clave in out:
            continue
        v = re.sub(r"<!--.*?-->", "", ib.get(param) or "", flags=re.S).strip()
        m = re.fullmatch(r"\[(\S+)(?:\s[^\]]*)?\]", v)        # [https://… texto] → la URL
        v = m.group(1) if m else v
        if not v:
            continue
        if re.match(r"^https?://", v, re.I):
            url = v
        elif prefijo and re.fullmatch(r"@?[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.@\-]+)*", v):
            url = prefijo + v
        else:
            continue
        if url_https_ok(url):
            out[clave] = url
    return out


def torneos_estado(t, hoy):
    ini = date.fromisoformat(t["inicio"])
    fin = date.fromisoformat(t["fin"]) if t.get("fin") else ini
    if fin < hoy:
        return "terminado"
    if ini > hoy:
        return "proximo"
    return "en_curso"


def torneos_en_ventana(filas, hoy, todo=False):
    """Torneos cuyas fechas tocan la ventana [hoy - PASADO, hoy + FUTURO] (todo=True: todos los que traiga la tabla), sin
    duplicados (misma URL o mismo nombre y fecha)."""
    desde, hasta = hoy - timedelta(days=TORNEOS_DIAS_PASADO), hoy + timedelta(days=TORNEOS_DIAS_FUTURO)
    if todo:
        desde, hasta = date.min, date.max
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


def torneos_componer(filas, infoboxes, hoy, previo=None, todo=False):
    """Lista final ordenada. infoboxes: {título: params}; si falta el de un torneo, organizador y formato se toman del
    torneos.json anterior (misma URL). El logo del anterior se copia siempre (torneos_logos lo rehace si puede)."""
    previos = {t.get("url"): t for t in (previo or {}).get("torneos", []) if t.get("url")}
    out = []
    for f in torneos_en_ventana(filas, hoy, todo):
        titulo = f.pop("titulo", None)
        ib = infoboxes.get(titulo) if titulo else None
        if ib:
            torneos_enriquecer(f, ib)
        elif f.get("url") in previos:
            for k in ("organizador", "formato", "formato_texto", "bolsa_local", "moneda_local", "enlaces"):
                if previos[f["url"]].get(k) is not None and f.get(k) is None:
                    f[k] = previos[f["url"]][k]
        f["fin"] = f.get("fin") or f["inicio"]
        f["estado"] = torneos_estado(f, hoy)
        f["moneda"] = "USD" if f.get("bolsa") is not None else None
        t = {k: f.get(k) for k in ("nombre", "tier", "tipo", "inicio", "fin", "estado", "bolsa", "moneda")}
        if f.get("bolsa_local") is not None:
            t.update(bolsa_local=f["bolsa_local"], moneda_local=f["moneda_local"])
        t.update({k: f.get(k) for k in ("formato", "formato_texto", "organizador", "lugar", "participantes", "url")})
        if f.get("enlaces"):
            t["enlaces"] = f["enlaces"]
        for k in ("ganador", "finalista"):
            if f.get(k):
                t[k] = f[k]
        for k in ("logo", "logo_oscuro"):
            if previos.get(f.get("url"), {}).get(k):
                t[k] = previos[f["url"]][k]
        out.append(t)
    en_curso = sorted((t for t in out if t["estado"] == "en_curso"), key=lambda t: (t["fin"], t["nombre"].lower()))
    proximos = sorted((t for t in out if t["estado"] == "proximo"), key=lambda t: (t["inicio"], t["nombre"].lower()))
    terminados = sorted((t for t in out if t["estado"] == "terminado"), key=lambda t: (t["fin"], t["inicio"]), reverse=True)
    return en_curso + proximos + terminados


def torneos_salida(lista, hoy, todo=False):
    g = ahora()
    if todo:
        anios = torneos_anios(hoy)
        ventana = {"desde": f"{anios[0]}-01-01", "hasta": f"{anios[-1]}-12-31"}
    else:
        ventana = {"desde": (hoy - timedelta(days=TORNEOS_DIAS_PASADO)).isoformat(),
                   "hasta": (hoy + timedelta(days=TORNEOS_DIAS_FUTURO)).isoformat()}
    return {"v": 1, "generado": g, "hoy": hoy.isoformat(), "ventana": ventana,
            "fuente": {"nombre": "Liquipedia", "url": "https://liquipedia.net/ageofempires/", "licencia": "CC BY-SA 3.0",
                       "licencia_url": "https://creativecommons.org/licenses/by-sa/3.0/",
                       "atribucion": "Datos de torneos de Liquipedia (liquipedia.net/ageofempires), licencia CC BY-SA 3.0. "
                                     "Este archivo se distribuye con la misma licencia.",
                       "generado": g},
            "torneos": lista}


def torneos_infoboxes_logos(lq, filas, infob):
    """{url del torneo: infobox para los logos} (ver logos_respaldo): para los que no nombran logo en su infobox ni tienen
    icono en la lista, una consulta más (50 títulos) con la página superior y la de la serie. Nunca lanza."""
    import urllib.parse
    faltan = [f for f in filas if f.get("url") and not logos_de_infobox(infob.get(f.get("titulo")) or {})[0]
              and not (f.get("icono_claro") or f.get("icono_oscuro"))]
    extra = {}
    titulos = []
    for f in faltan:
        ruta = urllib.parse.unquote(f["url"].split("/ageofempires/", 1)[-1]).replace("_", " ")
        if "/" in ruta:
            titulos.append(ruta.rsplit("/", 1)[0])
        serie = wiki_limpiar((infob.get(f.get("titulo")) or {}).get("series", ""))
        if serie:
            titulos.append(serie)
    titulos = [x for x in dict.fromkeys(titulos) if x not in infob][:4 * LQ_TITULOS_POR_QUERY]
    if titulos:
        try:
            extra = torneos_infoboxes(lq, titulos)
        except Exception as ex:
            log(f"logos: sin páginas de serie ({ex!r})")
    out, origenes = {}, defaultdict(int)
    for f in filas:
        if not f.get("url"):
            continue
        ib = infob.get(f.get("titulo")) or {}
        ruta = urllib.parse.unquote(f["url"].split("/ageofempires/", 1)[-1]).replace("_", " ")
        superior = extra.get(ruta.rsplit("/", 1)[0]) or infob.get(ruta.rsplit("/", 1)[0]) if "/" in ruta else None
        serie = wiki_limpiar(ib.get("series", ""))
        r, origen = logos_respaldo(f, ib, superior, extra.get(serie) or infob.get(serie) if serie else None)
        if r:
            out[f["url"]] = r
        origenes[origen or ("propio" if logos_de_infobox(r or {})[0] else "ninguno")] += 1
    log(f"logos: origen del logo por torneo {dict(origenes)} ({len(titulos)} páginas de serie o superiores pedidas)")
    return out


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


# ----------------------------------------------------------------------------- logos de torneos (Liquipedia Commons)
# El infobox de cada torneo nombra su logo: image (o «allmode», vale para los dos temas), imagedark (variante para tema
# oscuro) e icon/icondark como respaldo. Liquipedia pide no enlazar sus imágenes (no hotlink): cada logo se DESCARGA una sola
# vez (la miniatura de 96 px de alto que la API da en imageinfo con iiurlheight, no el original), se normaliza a PNG con
# Pillow y se publica en la rama data, en logos/torneos/<nombre>-<sha1[:8]>.png. Clave de caché = nombre + hash del archivo:
# si el archivo ya está (recuperado de la rama data), no se vuelve a bajar; si Liquipedia sube una versión nueva, cambia el
# hash y se baja la nueva. Los que ya no use ningún torneo se borran. Por noche: imageinfo (50 títulos por petición) en la
# wiki de AoE, la ficha {{FileInfo}} en Commons (50 por petición: ahí están licencia, autor y copyright; el extmetadata de
# Liquipedia solo trae DateTime y ObjectName) y como mucho LOGOS_MAX_DESCARGAS descargas, al mismo ritmo (1 cada 2,5 s).
# Carpeta en la rama data y no assets de una release: son pocos archivos pequeños (≈5-15 KB), la app ya lee la rama data
# por raw, la rama se rehace con un commit huérfano cada noche (no crece la historia) y una release añadiría otra ruta de
# descarga, límites de subida de GitHub y nombres planos.
def logos_nombre(v):
    """Valor de image=/imagedark=/icon= del infobox → nombre de archivo («The Bastion lightmode.png») o None."""
    import re
    v = wiki_limpiar(v)
    v = re.sub(r"^(?:file|image|archivo)\s*:\s*", "", v, flags=re.I).replace("_", " ").strip()
    if not v or not re.search(r"\.(png|jpe?g|gif|webp|svg)$", v, re.I) or re.search(r"[\[\]{}|<>#]", v):
        return None
    return v[0].upper() + v[1:]          # MediaWiki pone en mayúscula la primera letra del título


LOGOS_ICONOS_IGNORADOS = ("logo filler", "age of empires default", "aoe2 icon")


def logos_de_src(src):
    """src de una miniatura de Liquipedia («/commons/images/thumb/9/9b/Rusaoc_cup_icon.png/50px-Rusaoc_cup_icon.png» o
    «/commons/images/4/44/X.png») → nombre del archivo («Rusaoc cup icon.png»), o None si es el relleno «sin logo», el
    icono del juego o una bandera («Ar hd.png»: el icono por defecto de un torneo nacional)."""
    import re, urllib.parse
    m = re.match(r"^/commons/images/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", src or "")
    if not m:
        return None
    nombre = logos_nombre(urllib.parse.unquote(m.group(1)))
    if not nombre or re.search(r" hd\.png$", nombre, re.I) or nombre.lower().startswith(LOGOS_ICONOS_IGNORADOS):
        return None
    return nombre


def logos_respaldo(fila, ib, superior, serie):
    """El infobox para los logos de un torneo: el suyo si nombra logo; si no, el icono que la lista de torneos de
    Liquipedia le pone (que ya hereda el de su serie), el de la página superior («T90 Titans League/6» para la Bronze
    League) o el de la serie del infobox (|series=). Devuelve (infobox, origen) con origen None, «lista», «superior» o
    «serie»; ({}, None) si nada nombra un logo (en Liquipedia ese torneo no tiene logo: lleva el relleno gris)."""
    if logos_de_infobox(ib or {})[0]:
        return ib, None
    if fila.get("icono_claro") or fila.get("icono_oscuro"):
        return {"image": fila.get("icono_claro") or "", "imagedark": fila.get("icono_oscuro") or ""}, "lista"
    for origen, otro in (("superior", superior), ("serie", serie)):
        if otro and logos_de_infobox(otro)[0]:
            return otro, origen
    return ib or {}, None


def logos_de_infobox(ib):
    """(logo, logo_oscuro) del infobox: image/imagedark; si no hay image, icon/icondark. El oscuro solo si es distinto."""
    claro = logos_nombre(ib.get("image", ""))
    oscuro = logos_nombre(ib.get("imagedark", "")) if claro else None
    if not claro:
        claro = logos_nombre(ib.get("icon", ""))
        oscuro = logos_nombre(ib.get("icondark", "")) if claro else None
    if not claro:
        claro, oscuro = logos_nombre(ib.get("imagedark", "")) or logos_nombre(ib.get("icondark", "")), None
    return claro, (oscuro if oscuro != claro else None)


def _titulos_origen(q):
    """{título final: título pedido} de los «normalized» y «redirects» de una respuesta de action=query."""
    origen = {}
    for r in (q.get("normalized") or []) + (q.get("redirects") or []):
        origen[r["to"]] = origen.get(r["from"], r["from"])
    return origen


def _sin_prefijo(t):
    return t.split(":", 1)[1] if ":" in t else t


def logos_imageinfo_paginas(paginas, origen=None):
    """Páginas de prop=imageinfo → {nombre sin «File:»: imageinfo}. OJO: los archivos de Commons vienen con missing:true y
    known:true (no existen en la wiki de AoE, sí en el repositorio compartido): vale lo que tenga imageinfo."""
    out = {}
    for p in paginas:
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        for t in {p["title"], (origen or {}).get(p["title"], p["title"])}:
            out[_sin_prefijo(t)] = ii
    return out


def logos_fichas_paginas(paginas, origen=None):
    """Páginas de prop=revisions de Commons → {nombre: parámetros de {{FileInfo}}} (license, author, copyright, source…)."""
    out = {}
    for p in paginas:
        revs = p.get("revisions") or []
        if not revs:
            continue
        texto = revs[0].get("slots", {}).get("main", {}).get("content", "")
        ficha = wiki_infobox(texto.replace("{{FileInfo", "{{Infobox", 1)) if "{{FileInfo" in texto else {}
        for t in {p["title"], (origen or {}).get(p["title"], p["title"])}:
            out[_sin_prefijo(t)] = ficha
    return out


def _consultar_por_lotes(lq, nombres, params, lector):
    out = {}
    nombres = list(dict.fromkeys(nombres))
    for k in range(0, len(nombres), LQ_TITULOS_POR_QUERY):
        lote = nombres[k:k + LQ_TITULOS_POR_QUERY]
        d = lq.get(dict(params, titles="|".join("File:" + n for n in lote)))
        q = d.get("query", {})
        out.update(lector(q.get("pages", []), _titulos_origen(q)))
    return out


def _texto_html(v):
    import html as _h, re
    return " ".join(_h.unescape(re.sub(r"<[^>]+>", " ", str(v or ""))).split())


def logos_credito(ii, ficha, torneo):
    """(crédito, licencia) de un logo. Licencia: LicenseShortName del extmetadata si lo trae; si no, «license» de la ficha
    {{FileInfo}} de Commons (en Liquipedia casi siempre fairuse/fairuselogo). Titular: «copyright» de la ficha, o Artist del
    extmetadata, o el organizador del torneo. «author» de la ficha (o Credit) es quien hizo/subió el archivo a la wiki.
    Los logos son marcas de sus dueños: no van con la CC BY-SA del texto de Liquipedia."""
    ext = (ii or {}).get("extmetadata") or {}
    ficha = ficha or {}
    lic = _texto_html((ext.get("LicenseShortName") or {}).get("value")) or wiki_limpiar(ficha.get("license", ""))
    titular = (wiki_limpiar(ficha.get("copyright", "")) or _texto_html((ext.get("Artist") or {}).get("value"))
               or torneo.get("organizador") or "su titular")
    autor = wiki_limpiar(ficha.get("author", "")) or _texto_html((ext.get("Credit") or {}).get("value"))
    lic_txt = LOGOS_LICENCIAS.get(lic.lower().replace(" ", ""), lic) if lic else "no indicada"
    credito = f"Logo de {torneo.get('nombre')} © {titular}. "
    credito += (f"Archivo de {autor} en Liquipedia Commons" if autor and autor != titular else "Vía Liquipedia Commons")
    credito += f"; licencia: {lic_txt}" + ("." if lic.lower().startswith("cc") else "; no es CC BY-SA.")
    return credito[:300], (lic or None)


def logos_ruta(nombre, sha1):
    """logos/torneos/<nombre en minúsculas, solo [a-z0-9-]>-<sha1[:8]>.png (con «/», que es como va en el JSON)."""
    import re, unicodedata
    base = nombre.rsplit(".", 1)[0]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60] or "logo"
    return f"{LOGOS_DIR.replace(os.sep, '/')}/{base}-{(sha1 or 'sinhash')[:8]}.png"


def logos_png(raw):
    """Bytes de imagen → PNG de LOGOS_ALTO px de alto como mucho (y LOGOS_ANCHO_MAX de ancho), RGBA, sin metadatos."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = LOGOS_MAX_PIXELES
    im = Image.open(io.BytesIO(raw))
    if im.width * im.height > LOGOS_MAX_PIXELES:
        raise ValueError(f"imagen enorme {im.width}x{im.height}")
    im.seek(0)
    im = im.convert("RGBA")
    im.thumbnail((LOGOS_ANCHO_MAX, LOGOS_ALTO), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    # paleta de 256 colores con alfa: a 96 px apenas se nota y pesa ≈4 veces menos; se queda el más pequeño
    pal = io.BytesIO()
    im.quantize(256, method=Image.Quantize.FASTOCTREE).save(pal, "PNG", optimize=True)
    return min(out.getvalue(), pal.getvalue(), key=len)


def logos_asignar(listas, infob, info, fichas, descargar, max_descargas=LOGOS_MAX_DESCARGAS):
    """Pone «logo» (y «logo_oscuro») a los torneos de las listas (el orden de las listas es la prioridad de descarga).
    infob: {url del torneo: infobox}; info: {archivo: imageinfo}; fichas: {archivo: FileInfo}; descargar(url) → bytes|None.
    Devuelve (torneos con logo, descargas, bytes nuevos). Un logo que falla deja al torneo sin él (o con el anterior)."""
    hechos, bajados, nbytes, con_logo = {}, 0, 0, set()
    for lista in listas:
        for t in lista:
            ib = infob.get(t.get("url"))
            if not ib:
                continue
            t.pop("logo", None)
            t.pop("logo_oscuro", None)
            for campo, nombre in zip(("logo", "logo_oscuro"), logos_de_infobox(ib)):
                ii = info.get(nombre) if nombre else None
                if not ii:
                    continue
                if nombre not in hechos:
                    hechos[nombre] = None
                    ruta = logos_ruta(nombre, ii.get("sha1"))
                    if not os.path.exists(ruta):
                        url = ii.get("thumburl") or (ii.get("url") if 0 < (ii.get("size") or 0) <= LOGOS_MAX_BYTES else None)
                        if not url or bajados >= max_descargas:
                            hechos.pop(nombre)          # sin cupo: queda para la noche siguiente
                            continue
                        bajados += 1
                        raw = descargar(url)
                        if not raw:
                            continue
                        try:
                            png = logos_png(raw)
                        except Exception as ex:
                            log(f"logos: {nombre}: imagen ilegible ({ex!r})")
                            continue
                        os.makedirs(os.path.dirname(ruta), exist_ok=True)
                        with open(ruta, "wb") as f:
                            f.write(png)
                        nbytes += len(png)
                    hechos[nombre] = (ruta, ii.get("descriptionurl"))
                if not hechos.get(nombre):
                    continue
                ruta, fuente = hechos[nombre]
                credito, lic = logos_credito(ii, fichas.get(nombre), t)
                logo = {"archivo": ruta, "fuente": fuente if url_https_ok(fuente) else None, "credito": credito}
                if lic:
                    logo["licencia"] = lic
                t[campo] = logo
            if t.get("logo_oscuro") and not t.get("logo"):
                t["logo"] = t.pop("logo_oscuro")
            if t.get("logo"):
                con_logo.add(t.get("url"))
    return len(con_logo), bajados, nbytes


def logos_validar(listas):
    """Quita «logo»/«logo_oscuro» cuyo PNG no esté en disco (p. ej. copiado del JSON anterior y luego perdido)."""
    for lista in listas:
        for t in lista:
            for c in ("logo", "logo_oscuro"):
                if t.get(c) and not os.path.exists(t[c].get("archivo") or ""):
                    t.pop(c)
            if t.get("logo_oscuro") and not t.get("logo"):
                t["logo"] = t.pop("logo_oscuro")


def logos_podar(listas):
    """Borra de logos/torneos los PNG que ya no usa ningún torneo. Devuelve (archivos que quedan, bytes)."""
    usados = {os.path.normpath(t[c]["archivo"]) for lista in listas for t in lista for c in ("logo", "logo_oscuro") if t.get(c)}
    quedan, nbytes = 0, 0
    if not os.path.isdir(LOGOS_DIR):
        return 0, 0
    for a in os.listdir(LOGOS_DIR):
        ruta = os.path.join(LOGOS_DIR, a)
        if os.path.normpath(ruta) not in usados:
            os.remove(ruta)
        else:
            quedan += 1
            nbytes += os.path.getsize(ruta)
    return quedan, nbytes


def torneos_logos(lq, listas, infob):
    """Logos de los torneos de las listas (ver el bloque de arriba). infob: {url del torneo: infobox}. Nunca lanza: si algo
    falla, los torneos se quedan como estaban (con el logo copiado del JSON anterior, si lo había)."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("::warning title=logos::falta Pillow (pip install pillow): torneos sin logos nuevos", flush=True)
        return
    nombres = [n for lista in listas for t in lista for n in logos_de_infobox(infob.get(t.get("url")) or {}) if n]
    if not nombres:
        return
    lqc = Liquipedia(LQ_API_COMMONS)
    try:
        info = _consultar_por_lotes(lq, nombres, {"action": "query", "prop": "imageinfo", "redirects": "1",
                                                  "iiprop": "url|size|mime|sha1|extmetadata", "iiurlheight": str(LOGOS_ALTO)},
                                    logos_imageinfo_paginas)
        try:
            fichas = _consultar_por_lotes(lqc, list(info), {"action": "query", "prop": "revisions", "rvprop": "content",
                                                            "rvslots": "main", "redirects": "1"}, logos_fichas_paginas)
        except Exception as ex:
            log(f"logos: sin fichas de Commons ({ex!r}): crédito sin licencia")
            fichas = {}
        n, bajados, nbytes = logos_asignar(listas, infob, info, fichas, lq.descargar)
        log(f"logos: {len(set(nombres))} archivos en los infoboxes, {len(info)} con imageinfo, {n} torneos con logo; "
            f"{bajados} descargas ({nbytes / 1024:.0f} KB nuevos); {lqc.peticiones} peticiones a Commons")
    except Exception as ex:
        print(f"::warning title=logos::no se pudieron poner los logos ({ex!r})", flush=True)
    finally:
        lqc.cerrar()


def torneos():
    """torneos.json (ventana) y torneos_historico.json (todo lo que da la tabla) desde Liquipedia, con logos (esquema en la
    cabecera, normas arriba). Si algo falla o no sale ningún torneo en la ventana, no se escribe nada: se quedan los
    anteriores (recuperados de la rama data) con aviso ::warning:: en el resumen; el paso no rompe el build."""
    hoy = datetime.now(timezone.utc).date()
    previo = leer_json("torneos.json", None)
    previo_h = leer_json(TORNEOS_HISTORICO, None)
    lq = Liquipedia()
    filas, infob = [], {}
    try:
        d = lq.get({"action": "parse", "title": "Age_of_Empires_II/Tournaments", "contentmodel": "wikitext", "prop": "text",
                    "text": torneos_wikitexto(hoy), "disablelimitreport": "1", "disableeditsection": "1"})
        filas = torneos_tabla(d.get("parse", {}).get("text", ""))
        log(f"torneos: años {torneos_anios(hoy)}: {len(filas)} filas")
        if not filas:
            raise RuntimeError("ninguna fila en la tabla de TournamentsList")
        # infoboxes: primero los de la ventana, luego el resto del histórico (50 por petición)
        candidatos = torneos_en_ventana(filas, hoy) + torneos_en_ventana(filas, hoy, todo=True)
        try:
            infob = torneos_infoboxes(lq, [c["titulo"] for c in candidatos if c.get("titulo")])
        except Exception as ex:
            print(f"::warning title=torneos::sin infoboxes ({ex!r}): organizador y formato, del torneos.json anterior", flush=True)
        lista = torneos_componer(filas, infob, hoy, previo)
        if not lista:
            raise RuntimeError(f"{len(filas)} filas pero ninguna en la ventana")
        historico = torneos_componer(filas, infob, hoy, previo_h or previo, todo=True)
        ib_url = torneos_infoboxes_logos(lq, filas, infob)
        torneos_logos(lq, [lista, historico], ib_url)
    except Exception as ex:
        print(f"::warning title=torneos::Liquipedia no respondió bien ({ex!r}): se conserva el torneos.json anterior", flush=True)
        return
    finally:
        lq.cerrar()
    logos_validar([lista, historico])
    escribir_json("torneos.json", torneos_salida(lista, hoy))
    escribir_json(TORNEOS_HISTORICO, torneos_salida(historico, hoy, todo=True))
    n_logos, kb = logos_podar([lista, historico])
    cuenta = defaultdict(int)
    for t in lista:
        cuenta[t["estado"]] += 1
    log(f"torneos: {len(lista)} torneos ({dict(cuenta)}), {sum(1 for t in lista if t.get('logo'))} con logo; histórico "
        f"{len(historico)} ({sum(1 for t in historico if t.get('logo'))} con logo); {len({id(v) for v in infob.values()})} "
        f"infoboxes; logos/torneos: {n_logos} PNG, {kb / 1024:.0f} KB; {lq.peticiones} peticiones y {lq.descargas} "
        f"descargas a Liquipedia")


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
        for k in ("ganador", "finalista", "enlaces"):
            if k not in esperado and k in t:
                fallos.append(f"{esperado['nombre']}: {k} no debería estar")
    for nombre in m.get("fuera", []):
        if any(x["nombre"] == nombre for x in lista):
            fallos.append(f"{nombre} no debería salir")
    for ib, esp in (({"website": "http://inseguro.com", "twitch": "a b", "discord": "javascript:alert(1)", "twitter": "@x_y"},
                     {"x": "https://x.com/@x_y"}),
                    ({"web": "[https://ejemplo.org/torneo Web]", "youtube": "channel/UC1234567890abcdefghijkl", "twitch2": "otro",
                      "bracket": "https://challonge.com/abc", "x": "https://x.com/org"},
                     {"web": "https://ejemplo.org/torneo", "youtube": "https://www.youtube.com/channel/UC1234567890abcdefghijkl",
                      "bracket": "https://challonge.com/abc", "x": "https://x.com/org"}),
                    ({"website": "https://<script>.com", "discord": ""}, {}),
                    ({"rulebook": "https://christianamdi.com/tournaments/warlords5/handbook.pdf", "rules": "https://otro.org/r"},
                     {"reglamento": "https://christianamdi.com/tournaments/warlords5/handbook.pdf"}),
                    ({"rulebook": "reglas.pdf", "rules": "[https://drive.google.com/file/d/abc/view Rules]"},
                     {"reglamento": "https://drive.google.com/file/d/abc/view"})):
        if torneos_enlaces(ib) != esp:
            fallos.append(f"enlaces {ib} → {torneos_enlaces(ib)}, se esperaba {esp}")
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


def logos_probar():
    """Prueba sin red: infoboxes, imageinfo y fichas de muestra; las «descargas» son imágenes generadas con Pillow en memoria
    y los PNG van a una carpeta temporal."""
    global LOGOS_DIR
    import copy, shutil, tempfile
    from PIL import Image
    m = leer_json(os.path.join("pruebas", "logos_muestra.json"))
    fallos = []
    info = logos_imageinfo_paginas(m["imageinfo"]["query"]["pages"], _titulos_origen(m["imageinfo"]["query"]))
    fichas = logos_fichas_paginas(m["fichas"]["query"]["pages"])
    if "Nope nope.png" in info:
        fallos.append("un archivo sin imageinfo no debería estar")
    if "Chilean Cup 2026 allmode.webp" not in info:
        fallos.append("missing:true + known:true con imageinfo debería contar")
    pedidas = []

    def descargar(url):
        pedidas.append(url)
        if url in m["rotas"]:
            return b"esto no es una imagen"
        im = Image.new("RGBA", (1000, 250), (200, 30, 30, 255))      # 4:1 → 384x96
        b = io.BytesIO()
        im.save(b, "PNG")
        return b.getvalue()

    dir_antes, tmp = LOGOS_DIR, tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        os.chdir(tmp)
        LOGOS_DIR = os.path.join("logos", "torneos")
        lista = copy.deepcopy(m["torneos"])
        n, bajados, nbytes = logos_asignar([lista], m["infoboxes"], info, fichas, descargar)
        logos_validar([lista])
        for t in lista:
            esp = m["esperado"][t["nombre"]]
            got = {k: t[k] for k in ("logo", "logo_oscuro") if k in t}
            if got != esp:
                fallos.append(f"{t['nombre']}: {json.dumps(got, ensure_ascii=False)}")
            for k in got:
                with Image.open(got[k]["archivo"]) as im:
                    if im.format != "PNG" or im.height > LOGOS_ALTO or im.width > LOGOS_ANCHO_MAX:
                        fallos.append(f"{got[k]['archivo']}: {im.format} {im.size}")
                    if t["nombre"] == "The Bastion: Season 2" and im.size != (384, 96):
                        fallos.append(f"redimensionado: {im.size}, se esperaba (384, 96)")
        if n != 3 or bajados != 5:
            fallos.append(f"con logo {n} (se esperaban 3), descargas {bajados} (se esperaban 5)")
        # segunda pasada: todo en caché, ninguna descarga; y tope de descargas
        antes = len(pedidas)
        lista2 = copy.deepcopy(m["torneos"])
        logos_asignar([lista2], m["infoboxes"], info, fichas, descargar)
        if len(pedidas) - antes != 1:            # solo la rota se reintenta (no se guardó)
            fallos.append(f"caché: {len(pedidas) - antes} descargas en la segunda pasada, se esperaba 1 (la rota)")
        shutil.rmtree(LOGOS_DIR)
        lista3 = copy.deepcopy(m["torneos"])
        _, b3, _ = logos_asignar([lista3], m["infoboxes"], info, fichas, descargar, max_descargas=1)
        logos_validar([lista3])
        if b3 != 1 or sum(1 for t in lista3 if t.get("logo")) != 1:
            fallos.append(f"tope: {b3} descargas, {sum(1 for t in lista3 if t.get('logo'))} con logo")
        os.makedirs(LOGOS_DIR, exist_ok=True)
        open(os.path.join(LOGOS_DIR, "huerfano-00000000.png"), "wb").write(b"x")
        quedan, _ = logos_podar([lista3])
        if quedan != 1 or os.path.exists(os.path.join(LOGOS_DIR, "huerfano-00000000.png")):
            fallos.append(f"podar: quedan {quedan}")
    finally:
        os.chdir(cwd)
        LOGOS_DIR = dir_antes
        shutil.rmtree(tmp, ignore_errors=True)
    for v, esp in {"File:the_bastion lightmode.png": "The bastion lightmode.png", "<!--x.png-->": None, "": None,
                   "[[File:x.png]]": "X.png", "nombre sin extension": None, "a|b.png": None}.items():
        if logos_nombre(v) != esp:
            fallos.append(f"logos_nombre({v!r}) = {logos_nombre(v)!r}, se esperaba {esp!r}")
    for ib, esp in (({"image": "A allmode.png", "imagedark": "A allmode.png"}, ("A allmode.png", None)),
                    ({"imagedark": "Solo oscuro.png"}, ("Solo oscuro.png", None)),
                    ({"image": "", "icon": "I.png", "icondark": "Id.png"}, ("I.png", "Id.png")), ({}, (None, None))):
        if logos_de_infobox(ib) != esp:
            fallos.append(f"logos_de_infobox({ib}) = {logos_de_infobox(ib)}, se esperaba {esp}")
    for src, esp in {"/commons/images/thumb/9/9b/Rusaoc_cup_icon.png/50px-Rusaoc_cup_icon.png": "Rusaoc cup icon.png",
                     "/commons/images/4/44/Logo_filler_event.png": None,
                     "/commons/images/thumb/a/a5/Ar_hd.png/50px-Ar_hd.png": None,
                     "/commons/images/thumb/3/35/Age_of_Empires_default_allmode.png/68px-Age_of_Empires_default_allmode.png": None,
                     "/commons/images/thumb/1/1a/Chilean_Cup_2026_allmode.webp/42px-Chilean_Cup_2026_allmode.webp.png":
                         "Chilean Cup 2026 allmode.webp",
                     "https://evil.com/x.png": None, "": None}.items():
        if logos_de_src(src) != esp:
            fallos.append(f"logos_de_src({src!r}) = {logos_de_src(src)!r}, se esperaba {esp!r}")
    con = {"image": "Propio.png"}
    for fila, ib, sup, serie, esp in (({}, con, None, None, (con, None)),
                                     ({"icono_claro": "Lista.png"}, {"image": ""}, None, {"image": "Serie.png"},
                                      ({"image": "Lista.png", "imagedark": ""}, "lista")),
                                     ({}, {"series": "S"}, {"image": "Sup.png"}, {"image": "Serie.png"}, ({"image": "Sup.png"}, "superior")),
                                     ({}, {"series": "S"}, None, {"image": "Serie.png"}, ({"image": "Serie.png"}, "serie")),
                                     ({}, {"image": "<!--x.png-->"}, None, None, ({"image": "<!--x.png-->"}, None))):
        if logos_respaldo(fila, ib, sup, serie) != esp:
            fallos.append(f"logos_respaldo({fila}, {ib}) = {logos_respaldo(fila, ib, sup, serie)}, se esperaba {esp}")
    iconos = [(f["nombre"], f.get("icono_claro"), f.get("icono_oscuro")) for f in torneos_tabla(m["lista_html"])]
    if iconos != [("Rusaoc Cup 192", "Rusaoc cup icon.png", None),
                  ("The Bastion", "The Bastion logo lightmode.png", "The Bastion logo darkmode.png"), ("CNZS Invitational 8", None, None)]:
        fallos.append(f"iconos de la lista: {iconos}")
    if logos_ruta("Ñandú Cup – 2026 allmode.png", "abcdef0123") != "logos/torneos/nandu-cup-2026-allmode-abcdef01.png":
        fallos.append(f"ruta: {logos_ruta('Ñandú Cup – 2026 allmode.png', 'abcdef0123')}")
    try:
        logos_png(b"<html>no</html>")
        fallos.append("logos_png debería fallar con algo que no es imagen")
    except Exception:
        pass
    for f in fallos:
        log("FALLO", f)
    log(f"logos --probar: {len(fallos)} fallos")
    return not fallos


# ----------------------------------------------------------------------------- detalle de torneos importantes (Liquipedia)
# Para que la vista «Torneos» de la app no necesite Liquipedia: de los torneos de torneos_historico.json de tier S y A (y los
# B en curso o próximos) se pide su página con action=parse (API MediaWiki, 1 cada 30 s) y se saca: formato (lista de la
# sección «Format»), calendario («Schedule»), mapas («Map Pool»), reparto del premio por puesto («Prize Pool»),
# participantes (nombre, país, equipo/jugadores, grupo de entrada: invitado, clasificatoria, sembrado…) y fases (títulos de
# «Results» con sus rondas y Bo). Los puestos ya conocidos (quién quedó qué) van SOLO en «resultados» (la app los esconde).
# Los partidos no se repiten: ya están en partidos.json (torneo_url). Ritmo: como mucho TORNEOS_DETALLE_POR_NOCHE páginas
# y TORNEOS_DETALLE_TIEMPO_S por noche (≈7,5 min); lo que no cabe, la noche siguiente. Cada página se vuelve a pedir solo si
# toca: en curso, cada noche; próximo, cada 3 días (cada noche si empieza en 2 días); terminado, una vez más al acabar y ya
# nunca. Las que aún no se tienen van antes que las renovaciones. Lo ya obtenido se conserva (rama data).
# Contenido CC BY-SA 3.0, como torneos.json.
TORNEOS_DETALLE_DIR = "torneos"
DETALLE_VERSION = 3             # v3: «tablas» y «jornadas»; v2: «cuadros». Un detalle de versión anterior se vuelve a pedir
TORNEOS_DETALLE_POR_NOCHE = 20  # ≈31 s cada una (action=parse: <= 1 cada 30 s): ≈10 min por noche
TORNEOS_DETALLE_TIEMPO_S = 11 * 60
DETALLE_TABLAS_MAX = 16         # clasificaciones por página (grupos)
DETALLE_FILAS_MAX = 40          # filas por clasificación
DETALLE_JORNADAS_MAX_PARTIDOS = 400   # partidos de «jornadas» por página (una liga de 10 a doble vuelta: 90)
TORNEOS_DETALLE_MUESTRA = os.path.join("pruebas", "torneo_detalle_muestra.json")
TORNEOS_CUADROS_MUESTRA = os.path.join("pruebas", "torneo_cuadros_muestra.json")
TORNEOS_TABLAS_MUESTRA = os.path.join("pruebas", "torneo_tablas_muestra.json")
MESES_LARGOS = {m: i + 1 for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                                "september", "october", "november", "december"))}


def _html_texto(v):
    import html as _h, re
    v = re.sub(r"<sup\b.*?</sup>", "", v or "", flags=re.S)
    return " ".join(_h.unescape(re.sub(r"<[^>]+>", " ", v)).replace("​", "").split()).strip()


def detalle_slug(url):
    """URL de Liquipedia → nombre de archivo: «Warlords/5/Qualifier/1» → «warlords-5-qualifier-1»."""
    import re, unicodedata, urllib.parse
    t = urllib.parse.unquote(url.split("/ageofempires/", 1)[-1])
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:100] or "torneo"


def detalle_titulo(url):
    import urllib.parse
    return urllib.parse.unquote(url.split("/ageofempires/", 1)[-1]).replace(" ", "_")


def detalle_secciones(html_txt):
    """[(nivel, id, título, html hasta el siguiente encabezado de nivel <= al suyo)] de los h2/h3/h4 de la página."""
    import re
    hs = [(int(m.group(1)), m.group(2), _html_texto(m.group(3)), m.start())
          for m in re.finditer(r'<h([234]) id="([^"]+)"[^>]*>(.*?)</h\1>', html_txt or "", re.S)]
    out = []
    for k, (nivel, ident, titulo, ini) in enumerate(hs):
        fin = next((h[3] for h in hs[k + 1:] if h[0] <= nivel), len(html_txt))
        out.append((nivel, ident, titulo, html_txt[ini:fin]))
    return out


def detalle_seccion(secciones, *ids):
    for nivel, ident, titulo, cuerpo in secciones:
        if ident.lower() in ids:
            return cuerpo
    return ""


def detalle_lista(cuerpo):
    """Elementos <li> de una sección, en orden, con su nivel de anidamiento: [{"texto", "nivel"}] (nivel 0 = primero).
    Solo las listas antes de la primera tabla o subsección (lo que es texto de la sección)."""
    import re
    cuerpo = re.split(r'<table|<div class="mw-heading|<div class="table2', cuerpo, maxsplit=1)[0]
    out, nivel = [], -1
    for m in re.finditer(r"<(/?)(ul|ol|li)\b[^>]*>", cuerpo):
        cierre, tag = m.group(1), m.group(2)
        if tag in ("ul", "ol"):
            nivel += -1 if cierre else 1
        elif not cierre:
            resto = cuerpo[m.end():]
            fin = re.search(r"<(?:/?li|ul|ol)\b", resto)
            texto = _html_texto(resto[:fin.start()] if fin else resto)
            if texto:
                out.append({"texto": texto[:200], "nivel": max(nivel, 0)})
    return out[:60]


def detalle_fechas(texto, anio_base, mes_base=1):
    """«May 7th - 10th, starting…» → ("AAAA-05-07", "AAAA-05-10"); «November 25: WB Ro8» → (fecha, None); sin fecha → (None,
    None). El año es el del inicio del torneo (si el mes es muy anterior al de inicio, el siguiente)."""
    import re
    pat = r"\b(" + "|".join(m[:3] for m in MESES_LARGOS) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b"
    m = re.search(pat, texto, re.I)
    if not m:
        return None, None

    def iso(mes, dia):
        a = anio_base + (1 if mes < mes_base - 6 else 0)
        try:
            return date(a, mes, dia).isoformat()
        except ValueError:
            return None
    mes = MESES_EN[m.group(1)[:3].lower()]
    desde = iso(mes, int(m.group(2)))
    resto = texto[m.end():]
    m2 = re.match(r"\s*[-–]\s*(?:" + pat + r"|(\d{1,2})(?:st|nd|rd|th)?\b)", resto, re.I)
    hasta = None
    if m2:
        if m2.group(1):
            hasta = iso(MESES_EN[m2.group(1)[:3].lower()], int(m2.group(2)))
        elif m2.group(3):
            hasta = iso(mes, int(m2.group(3)))
    return desde, hasta


def detalle_calendario(cuerpo, inicio):
    try:
        d0 = date.fromisoformat(inicio)
        anio, mes = d0.year, d0.month
    except (TypeError, ValueError):
        anio, mes = datetime.now(timezone.utc).year, 1
    out = []
    for e in detalle_lista(cuerpo):
        desde, hasta = detalle_fechas(e["texto"], anio, mes)
        f = {"texto": e["texto"], "nivel": e["nivel"], "desde": desde}
        if hasta:
            f["hasta"] = hasta
        out.append(f)
    return out


def detalle_jugador(trozo):
    """Primer jugador/equipo de un trozo de HTML: {"nombre", ["pais"]} o None (TBD/vacío)."""
    import re
    m = re.search(r'<span class="name"[^>]*>(.*?)</span>', trozo, re.S)
    nombre = _html_texto(m.group(1)) if m else ""
    if not nombre or nombre.upper() in ("TBD", "TBA", "BYE"):
        return None
    out = {"nombre": nombre[:60]}
    f = re.search(r'<span class="flag"><img [^>]*src="([^"]+)"', trozo[:m.start()] if m else trozo)
    pais = partidos_pais(f.group(1)) if f else None
    if pais:
        out["pais"] = pais
    return out


def detalle_participantes(cuerpo):
    """Participantes: tablas participantTable (jugador o equipo por casilla, con el grupo de entrada del título de la fila)
    o tarjetas de equipo (team-participant-card, con sus jugadores). Sin repetidos (la vista «Show Seedings» repite)."""
    import re
    out, vistos = [], set()
    if "team-participant-card" in cuerpo:
        for card in re.split(r'<div class="general-collapsible[^"]*team-participant-card"', cuerpo)[1:]:
            partes = re.split(r'team-participant-card&#95;&#95;member"', card)
            eq = detalle_jugador(partes[0])
            if not eq or eq["nombre"] in vistos:
                continue
            vistos.add(eq["nombre"])
            eq.pop("pais", None)
            jug = [j for j in (detalle_jugador(p) for p in partes[1:]) if j]
            out.append(dict(eq, tipo="equipo", **({"jugadores": jug} if jug else {})))
        return out
    grupo = None
    for m in re.finditer(r'<div class="participantTable-title">(.*?)</div>|<div class="participantTable-entry[^"]*"[^>]*>', cuerpo, re.S):
        if m.group(1) is not None:
            g = re.sub(r"\(\d+\)|[¹²³⁴⁵⁶⁷⁸⁹⁰*]", "", _html_texto(m.group(1))).strip()
            grupo = None if g.lower() in ("participants", "participantes", "") else g
            continue
        fin = cuerpo.find('<div class="participantTable-entry', m.end())
        j = detalle_jugador(cuerpo[m.end():fin if fin > 0 else m.end() + 4000])
        if not j or j["nombre"] in vistos:
            continue
        vistos.add(j["nombre"])
        if grupo:
            j["grupo"] = grupo
            s = re.search(r"seed\w*\s*#?\s*(\d+)", grupo, re.I)
            if s:
                j["sembrado"] = int(s.group(1))
        out.append(j)
    return out


def detalle_premios(cuerpo):
    """Tabla «Prize Pool» (prizepooltable-placement) → (puestos [{"puesto","desde","hasta",["usd"],["otros"]}], resultados
    [{"puesto","desde","hasta","jugadores":[…]}]: solo los puestos con nombres ya conocidos) y el total en USD si lo dice."""
    import re
    total = None
    m = re.search(r"\$([\d,]+(?:\.\d+)?)\s*(?:&#160;|\s)*<abbr title=\"United States Dollar\">USD</abbr> are spread", cuerpo)
    if m:
        total = torneos_dinero(m.group(1))
    tabla = re.search(r'<table class="[^"]*prizepooltable-placement[^"]*">(.*?)</table>', cuerpo, re.S)
    if not tabla:
        return [], [], total
    filas = re.findall(r"<tr[^>]*>(.*?)</tr>", tabla.group(1), re.S)
    cab = [_html_texto(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", filas[0], re.S)] if filas else []
    otras = [c for c in cab[2:] if "USD" not in c]
    puestos, resultados = [], []
    for f in filas[1:]:
        celdas = re.findall(r"<td([^>]*)>(.*?)</td>", f, re.S)
        lugar = next((c for a, c in celdas if "prizepooltable-place" in a), None)
        equipo = [c for a, c in celdas if "prizepooltable-col-team" in a]
        if lugar is not None:
            txt = _html_texto(lugar).replace("–", "-")
            r = re.match(r"(\d+)(?:\s*-\s*(\d+))?", txt)
            if not r:
                continue
            p = {"puesto": txt, "desde": int(r.group(1)), "hasta": int(r.group(2) or r.group(1))}
            resto = [c for a, c in celdas if "prizepooltable-place" not in a and "prizepooltable-col-team" not in a]
            vals = [_html_texto(c) for c in resto]
            usd = next((torneos_dinero(v) for v in vals if v.startswith("$")), None)
            if usd is not None:
                p["usd"] = usd
            extra = [f"{cab_}: {v}" for cab_, v in zip(otras, [v for v in vals if not v.startswith("$")]) if v and cab_]
            if extra:
                p["otros"] = extra[:4]
            puestos.append(p)
            resultados.append({"puesto": p["puesto"], "desde": p["desde"], "hasta": p["hasta"], "jugadores": []})
        if resultados:
            for c in equipo:
                j = detalle_jugador(c)
                if j:
                    resultados[-1]["jugadores"].append(j["nombre"])
    return puestos[:64], [r for r in resultados if r["jugadores"]][:64], total


# Cuadros de eliminatorias: el HTML de Liquipedia (Module:Brackets) es un árbol anidado. Dentro de cada «brkts-bracket», una
# fila de encabezados (brkts-round-header: una por columna, «Quarterfinals (Bo7)») va seguida de su cuerpo (brkts-round-body);
# un cuadro con superior e inferior trae dos parejas. En el cuerpo, cada brkts-round-body contiene sus rondas anteriores
# (brkts-round-lower) y su partido (brkts-round-center › brkts-match): la columna de un partido = profundidad máxima −
# su profundidad. Los «brkts-popup» (detalle de cada partida: civs, mapas) no se leen.
DETALLE_CUADRO_MAX_PARTIDOS = 256


class _Nodo:
    __slots__ = ("tag", "attrs", "hijos", "padre")

    def __init__(self, tag, attrs, padre):
        self.tag, self.attrs, self.hijos, self.padre = tag, dict(attrs), [], padre

    def clases(self):
        return (self.attrs.get("class") or "").split()

    def tiene(self, clase):
        return clase in self.clases()

    def texto(self):
        return "".join(h.texto() if isinstance(h, _Nodo) else h for h in self.hijos)

    def buscar(self, clase, parar=None):
        """Descendientes con esa clase, en orden del documento (sin entrar en los que tengan la clase «parar»)."""
        out = []
        for h in self.hijos:
            if isinstance(h, _Nodo):
                if parar and h.tiene(parar):
                    continue
                if h.tiene(clase):
                    out.append(h)
                out.extend(h.buscar(clase, parar))
        return out

    def imgs(self):
        for h in self.hijos:
            if isinstance(h, _Nodo):
                if h.tag == "img":
                    yield h
                yield from h.imgs()


def _arbol_html(html_txt):
    """HTML → árbol de _Nodo (html.parser de la biblioteca estándar; tolera etiquetas sin cerrar)."""
    from html.parser import HTMLParser
    vacias = {"img", "br", "hr", "meta", "link", "input", "wbr", "source", "col", "area", "base", "embed", "param", "track"}

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.raiz = _Nodo("raiz", [], None)
            self.cur = self.raiz

        def handle_starttag(self, tag, attrs):
            n = _Nodo(tag, attrs, self.cur)
            self.cur.hijos.append(n)
            if tag not in vacias:
                self.cur = n

        def handle_startendtag(self, tag, attrs):
            self.cur.hijos.append(_Nodo(tag, attrs, self.cur))

        def handle_endtag(self, tag):
            x = self.cur
            while x is not None and x.tag != tag:
                x = x.padre
            if x is not None and x.padre is not None:
                self.cur = x.padre

        def handle_data(self, d):
            self.cur.hijos.append(d)

    p = _P()
    p.feed(html_txt or "")
    p.close()
    return p.raiz


def _cuadro_lado(entrada):
    """Un lado de un partido (brkts-opponent-entry) → ({"nombre",["pais"]} o None si TBD/vacío, marcador o None, ¿ganó?)."""
    import re
    nombres = [" ".join(n.texto().split()) for n in entrada.buscar("name")]
    nombre = " ".join((entrada.attrs.get("aria-label") or "").split()) or " & ".join(x for x in nombres if x)
    marcador = "".join(" ".join(m.texto().split()) for m in entrada.buscar("brkts-opponent-score-inner")).strip()
    marcador = marcador if re.fullmatch(r"\d{1,3}|[WLDF]|FF", marcador) else None
    gano = entrada.tiene("brkts-opponent-win") or bool(entrada.buscar("brkts-opponent-win"))
    if not nombre or nombre.upper() in ("TBD", "TBA", "BYE"):
        return None, marcador, gano
    lado = {"nombre": nombre[:60]}
    if len(nombres) <= 1:                           # bandera solo de un jugador suelto (un equipo no tiene país)
        img = next((i for i in entrada.imgs() if i.padre is not None and i.padre.tiene("flag")), None)
        pais = partidos_pais(img.attrs.get("src")) if img is not None else None
        if pais:
            lado["pais"] = pais
    return lado, marcador, gano


def _encabezado(cab):
    """Texto principal de un brkts-header (sin sus variantes cortas brkts-header-option)."""
    propio = "".join(h if isinstance(h, str) else ("" if h.tiene("brkts-header-option") else h.texto()) for h in cab.hijos)
    if not propio.strip():
        op = cab.buscar("brkts-header-option")
        propio = op[0].texto() if op else ""
    return _html_texto(propio)


def detalle_cuadros(html_fase):
    """HTML de una fase → [{"rondas":[{"nombre",["bo"],"partidos":[{"j1","j2",["p1","p2"],["ganador":1|2]}]}]}] (un cuadro por
    fila de encabezados: superior, inferior…; la gran final va en el superior). j1/j2 = {"nombre",["pais"]} o null (TBD).
    SPOILER: quién está en las rondas después de la primera, los marcadores y «ganador» delatan resultados (la app los
    esconde). [] si no se entiende."""
    import re
    raiz = _arbol_html(html_fase)
    cuadros, total = [], 0
    for b in raiz.buscar("brkts-bracket"):
        pares = []                                   # (encabezados, cuerpo) en orden del documento
        for cab in b.buscar("brkts-round-header", parar="brkts-popup"):
            hermanos = [h for h in cab.padre.hijos if isinstance(h, _Nodo)]
            k = next(n for n, h in enumerate(hermanos) if h is cab)
            cuerpo = hermanos[k + 1] if k + 1 < len(hermanos) else None
            if cuerpo is not None and cuerpo.tiene("brkts-round-body"):
                pares.append(([_encabezado(h) for h in cab.buscar("brkts-header")], cuerpo))
        cuerpos = {id(c) for _, c in pares}
        for encabezados, cuerpo in pares:
            partidos = []                            # (profundidad, partido), en orden del documento: de arriba abajo
            for m in cuerpo.buscar("brkts-match", parar="brkts-popup"):
                prof, x = 0, m.padre
                while x is not None and x is not cuerpo and id(x) not in cuerpos:
                    if x.tiene("brkts-round-body"):
                        prof += 1
                    x = x.padre
                if x is not cuerpo:                  # de un cuadro anidado (el inferior): va en el suyo
                    continue
                entradas = m.buscar("brkts-opponent-entry", parar="brkts-popup")
                if len(entradas) != 2:
                    continue
                (j1, p1, g1), (j2, p2, g2) = _cuadro_lado(entradas[0]), _cuadro_lado(entradas[1])
                pa = {"j1": j1, "j2": j2}
                if p1 is not None and p2 is not None:
                    pa["p1"], pa["p2"] = p1, p2
                if g1 != g2:
                    pa["ganador"] = 1 if g1 else 2
                partidos.append((prof, pa))
            if not partidos:
                continue
            maxp = max(p for p, _ in partidos)
            rondas = []
            for col in range(maxp + 1):
                enc = encabezados[col] if col < len(encabezados) else ""
                bo = re.search(r"\(\s*Bo\s*(\d+)\s*\)", enc)
                nombre = re.sub(r"\(\s*Bo\s*\d+\s*\)", "", enc).strip() or f"Round {col + 1}"
                rondas.append({"nombre": nombre[:60], **({"bo": int(bo.group(1))} if bo else {}),
                               "partidos": [pa for p, pa in partidos if maxp - p == col]})
            total += len(partidos)
            if total > DETALLE_CUADRO_MAX_PARTIDOS:
                return cuadros
            cuadros.append({"rondas": rondas})
    return cuadros[:8]


def _rondas_de(propio):
    """Encabezados de ronda de un trozo de HTML («Semifinals (Bo5)» → {"nombre","bo"}), sin repetir. Liquipedia pone en cada
    encabezado el texto largo y, dentro, sus variantes cortas (brkts-header-option: «UB Round 1», «UBR1»): solo el largo."""
    import re
    rondas, vistas = [], set()
    for h in re.findall(r'class="brkts-header(?:\s[^"]*)?"[^>]*>(.*?)(?:<div|</div>)', propio, re.S):
        t = _html_texto(h)
        b = re.search(r"\(\s*Bo\s*(\d+)\s*\)", t)
        nombre = re.sub(r"\(\s*Bo\s*\d+\s*\)", "", t).strip()
        if nombre and nombre not in vistas:
            vistas.add(nombre)
            rondas.append({"nombre": nombre[:60], **({"bo": int(b.group(1))} if b else {})})
    return rondas


def _fase(titulo, nivel, propio, completo=None):
    """Una fase. propio = su HTML hasta la siguiente cabecera (cualquiera); completo = hasta la siguiente h2-h4 (incluye
    las h5 de dentro, «Round 1»… de una liga), de donde salen «tablas» y «jornadas»."""
    tipo = "grupos" if "grouptable" in propio else ("bracket" if "brkts-bracket" in propio else
                                                     ("partidos" if "brkts-match" in propio else None))
    f = {"nombre": titulo[:80], "nivel": nivel}
    if tipo:
        f["tipo"] = tipo
    rondas = _rondas_de(propio)
    if rondas:
        f["rondas"] = rondas[:20]
    if tipo == "bracket":
        try:
            cuadros = detalle_cuadros(propio)
        except Exception as ex:                    # un HTML raro no tumba la ficha: sin cuadro (la app enlaza a Liquipedia)
            log(f"detalle: cuadro de {titulo!r} ilegible ({ex!r})")
            cuadros = []
        if cuadros:
            f["cuadros"] = cuadros
    completo = propio if completo is None else completo
    try:
        tablas = detalle_tablas(completo)
        if tablas:
            f["tablas"] = tablas
        jornadas = detalle_jornadas(completo)
        if jornadas:
            f["jornadas"] = jornadas
    except Exception as ex:                        # un HTML raro no tumba la ficha: sin tabla ni jornadas
        log(f"detalle: tablas o jornadas de {titulo!r} ilegibles ({ex!r})")
    return f


def detalle_fases(secciones):
    """Subsecciones de «Results» (h3/h4) con sus rondas de bracket («Semifinals (Bo5)» → {"nombre","bo"}), su tipo y, si son
    un cuadro, sus partidos («cuadros», ver detalle_cuadros). Si «Results» trae un cuadro sin subsección (torneos pequeños),
    sale como una fase con el título de la sección."""
    import re
    out, dentro, nivel_res = [], False, None
    for nivel, ident, titulo, cuerpo in secciones:
        completo = cuerpo[:10] + re.split(r'<h[234][\s>]', cuerpo[10:], maxsplit=1)[0]      # hasta la siguiente h2-h4
        if ident.lower() in ("results", "resultados"):
            dentro, nivel_res = True, nivel
            propio = cuerpo[:10] + re.split(r'<div class="mw-heading', cuerpo[10:], maxsplit=1)[0]
            if "brkts-bracket" in propio or "grouptable" in completo or "brkts-matchlist" in completo:
                out.append(_fase(titulo, 1, propio, completo))
            continue
        if not dentro:
            continue
        if nivel <= nivel_res:
            break
        propio = cuerpo[:10] + re.split(r'<div class="mw-heading', cuerpo[10:], maxsplit=1)[0] if nivel < 4 else cuerpo
        out.append(_fase(titulo, nivel - nivel_res, propio, completo))
    return out[:30]


# Clasificaciones y jornadas (v3). La «grouptable» de Liquipedia (Module:GroupTableLeague) es una tabla por grupo o liga: el
# título en el primer <th> («Group A», «League Stage»), una fila por puesto (<th> con el puesto y la clase bg-up/stayup/down
# que pinta quién pasa o baja, una casilla «grouptableslot» con bandera y nombre y luego las cifras: partidos «6-0-0» o
# «2-1», juegos «18-4», diferencia «+14» y puntos «18p», no siempre todas). Si la tabla se puede ver «tras» cada jornada
# (desplegable «Week 1… Week 9»), cada fila lleva data-toggle-area-content="N" y la que se enseña por defecto es la del
# toggle-area-N que la envuelve: solo esa se guarda. Las «matchlist» (Module:MatchGroup) son las listas de partidos de cada
# jornada o grupo: título y, por partido, los dos lados (aria-label = nombre; bandera), marcadores, ganador
# (brkts-matchlist-slot-winner) y, en su ventanita (brkts-popup), la fecha (timer-object data-timestamp) y el Bo.
DETALLE_ZONAS = {"bg-up": "sube", "bg-stayup": "sube", "bg-stay": "sigue", "bg-staydown": "baja", "bg-down": "baja",
                 "bg-drop": "baja"}


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def detalle_tablas(html_txt):
    """HTML de una fase → [{"nombre",["tras"],"filas":[{"pos","nombre",["pais"],["partidos"],["juegos"],["dif"],["puntos"],
    ["zona"]}]}] (esquema en la cabecera). Tolerante: columnas leídas por su forma, no por su posición; [] si no hay."""
    import re
    html_txt = html_txt or ""
    out = []
    for m in re.finditer(r'<table class="[^"]*\bgrouptable\b[^"]*"[^>]*>(.*?)</table>', html_txt, re.S):
        cuerpo = m.group(1)
        previo = re.findall(r'toggle-area toggle-area-(\d+)"', html_txt[max(0, m.start() - 600):m.start()])
        areas = sorted({int(a) for a in re.findall(r'data-toggle-area-content="(\d+)"', cuerpo)})
        area = int(previo[-1]) if previo and int(previo[-1]) in areas else (areas[-1] if areas else None)
        th0 = re.search(r"<th[^>]*>(.*?)</th>", cuerpo, re.S)
        cab = th0.group(1) if th0 else ""
        nombre = _html_texto(re.split(r'<div class="dropdown-box', cab, maxsplit=1)[0])
        t = {"nombre": nombre[:60] or "Standings"}
        if area is not None and len(areas) > 1:
            boton = re.search(r'data-toggle-area-btn="%d"[^>]*>(.*?)</div>' % area, cab, re.S)
            if boton and _html_texto(boton.group(1)):
                t["tras"] = _html_texto(boton.group(1))[:30]
        filas = []
        for fm in re.finditer(r"<tr([^>]*)>(.*?)</tr>", cuerpo, re.S):
            attrs, fila = fm.group(1), fm.group(2)
            a = re.search(r'data-toggle-area-content="(\d+)"', attrs)
            if area is not None and (not a or int(a.group(1)) != area):
                continue
            slot = re.search(r'<td class="grouptableslot[^"]*"[^>]*>(.*?)</td>', fila, re.S)
            if not slot:
                continue
            th = re.search(r'<th([^>]*)>(.*?)</th>', fila[:slot.start()], re.S)
            pos = _num(re.sub(r"\D", "", _html_texto(th.group(2)))) if th else None
            # sin puesto (empatados sin desempatar, o el grupo aún sin empezar): como en Liquipedia, sin número
            nombre_j = re.sub(r"\s*[▲▼]\d*\s*$", "", _html_texto(slot.group(1)))   # sin «▲1» (subió un puesto)
            if not nombre_j or nombre_j.upper() in ("TBD", "TBA"):
                continue
            f = {"pos": pos, "nombre": nombre_j[:60]} if pos else {"nombre": nombre_j[:60]}
            bandera = re.search(r'<span class="flag"><img [^>]*src="([^"]+)"', slot.group(1))
            pais = partidos_pais(bandera.group(1)) if bandera else None
            if pais:
                f["pais"] = pais
            ccls = re.search(r'class="([^"]*)"', th.group(1)) if th else None
            zona = next((DETALLE_ZONAS[c] for c in (ccls.group(1).split() if ccls else []) if c in DETALLE_ZONAS), None)
            if zona:
                f["zona"] = zona
            valores = [_html_texto(v) for v in re.findall(r"<td[^>]*>(.*?)</td>", fila[slot.end():], re.S)]
            registros = []
            for v in valores:
                if re.fullmatch(r"-?\d+p", v):
                    f["puntos"] = int(v[:-1])
                elif re.fullmatch(r"[+\-−]\d+|0", v):
                    f["dif"] = v.replace("−", "-")
                elif re.fullmatch(r"\d+-\d+(?:-\d+)?", v):
                    registros.append(v)
            if registros:
                f["partidos"] = registros[0]
            if len(registros) > 1:
                f["juegos"] = registros[1]
            filas.append(f)
            if len(filas) >= DETALLE_FILAS_MAX:
                break
        if filas:
            t["filas"] = filas
            out.append(t)
        if len(out) >= DETALLE_TABLAS_MAX:
            break
    return out


def _matchlist_lado(celda):
    """Casilla de un lado de una matchlist → {"nombre",["pais"]} o None (TBD/vacío)."""
    equipo = celda.buscar("team-name")
    nombres = [" ".join(n.texto().split()) for n in celda.buscar("name")]
    # equipo: el nombre del equipo que juega («Onimaru Capybaras»), no el de su organización (aria-label: «Onimaru Esports»)
    nombre = (" ".join(equipo[0].texto().split()) if equipo else " & ".join(x for x in nombres if x)) or         " ".join((celda.attrs.get("aria-label") or "").split())
    if not nombre or nombre.upper() in ("TBD", "TBA", "BYE"):
        return None
    lado = {"nombre": nombre[:60]}
    if len(nombres) <= 1 and not equipo:
        img = next((i for i in celda.imgs() if i.padre is not None and i.padre.tiene("flag")), None)
        pais = partidos_pais(img.attrs.get("src")) if img is not None else None
        if pais:
            lado["pais"] = pais
    return lado


def detalle_jornadas(html_txt):
    """HTML de una fase → [{"nombre","partidos":[{"j1","j2",["p1","p2"],["ganador"],["fecha"],["bo"]}]}] de sus «matchlist»
    (esquema en la cabecera). [] si no hay."""
    import re
    if "brkts-matchlist" not in (html_txt or ""):
        return []
    raiz = _arbol_html(html_txt)
    out, total = [], 0
    marcador_ok = r"\d{1,3}|[WLDF]|FF"
    for ml in raiz.buscar("brkts-matchlist"):
        if "general-collapsible" not in ml.clases():
            continue
        tit = ml.buscar("general-collapsible-default-title") or ml.buscar("brkts-matchlist-title")
        nombre = _html_texto(tit[0].texto()) if tit else ""
        partidos = []
        for m in ml.buscar("brkts-matchlist-match"):
            celdas = m.buscar("brkts-matchlist-cell", parar="brkts-popup")
            lados = [c for c in celdas if c.tiene("brkts-matchlist-opponent")]
            marcas = [c for c in celdas if c.tiene("brkts-matchlist-score")]
            if len(lados) != 2:
                continue
            pa = {"j1": _matchlist_lado(lados[0]), "j2": _matchlist_lado(lados[1])}
            if len(marcas) == 2:
                p1, p2 = (" ".join(x.texto().split()) for x in marcas)
                if re.fullmatch(marcador_ok, p1) and re.fullmatch(marcador_ok, p2):
                    pa["p1"], pa["p2"] = p1, p2
            g1, g2 = (c.tiene("brkts-matchlist-slot-winner") for c in lados)
            if g1 != g2:
                pa["ganador"] = 1 if g1 else 2
            reloj = m.buscar("timer-object")
            ts = _num(reloj[0].attrs.get("data-timestamp")) if reloj else None
            if ts and 946684800 < ts < 4102444800:          # 2000-2100: lo demás es un valor raro
                pa["fecha"] = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            bo = re.search(r"\(\s*Bo\s*(\d+)\s*\)", "".join(x.texto() for x in m.buscar("match-info-header-scoreholder-lower")))
            if bo:
                pa["bo"] = int(bo.group(1))
            partidos.append(pa)
            total += 1
            if total >= DETALLE_JORNADAS_MAX_PARTIDOS:
                break
        if partidos:
            out.append({"nombre": (nombre or f"Round {len(out) + 1}")[:60], "partidos": partidos})
        if total >= DETALLE_JORNADAS_MAX_PARTIDOS:
            break
    return out


def detalle_mapas(cuerpo):
    """Mapas de «Map Pool»: textos de los enlaces de sus tablas (las cabeceras a veces son categorías: Open, Closed…)."""
    import re
    tablas = "".join(re.findall(r"<table.*?</table>", cuerpo, re.S))
    return list(dict.fromkeys(t for t in (_html_texto(x) for x in re.findall(r"<a [^>]*>(.*?)</a>", tablas, re.S))
                              if t and len(t) <= 40))[:40]


def detalle_componer(html_txt, t, obtenido):
    """HTML de action=parse de la página de un torneo → detalle (esquema en la cabecera)."""
    sec = detalle_secciones(html_txt)
    puestos, resultados, total = detalle_premios(detalle_seccion(sec, "prize_pool", "prizepool"))
    d = {"v": DETALLE_VERSION, "url": t["url"], "nombre": t["nombre"], "tier": t.get("tier"), "inicio": t.get("inicio"), "fin": t.get("fin"),
         "obtenido": obtenido, "estado_al_obtener": t.get("estado"),
         "formato": detalle_lista(detalle_seccion(sec, "format")),
         "calendario": detalle_calendario(detalle_seccion(sec, "schedule"), t.get("inicio")),
         "mapas": detalle_mapas(detalle_seccion(sec, "map_pool")),
         "premios": {"total_usd": total if total is not None else t.get("bolsa"), "puestos": puestos},
         "participantes": detalle_participantes(detalle_seccion(sec, "participants")),
         "fases": detalle_fases(sec),
         "resultados": {"puestos": resultados}}
    return d


def detalle_candidatos(historico, hoy):
    """Torneos con detalle: S y A (todos los del histórico), B en curso o próximos y C en curso (no semanales ni
    showmatches). Orden de prioridad: en curso, próximos
    (el que empieza antes primero), terminados (el más reciente primero); dentro, primero los que no son clasificatorias ni
    showmatches."""
    def clave(t):
        est = {"en_curso": 0, "proximo": 1, "terminado": 2}[t["estado"]]
        menor = 1 if t.get("tipo") in ("Qualifier", "Showmatch") else 0
        fecha = t["inicio"] if est < 2 else t["fin"]
        orden = date.fromisoformat(fecha).toordinal()
        return (est, menor, orden if est < 2 else -orden, {"S": 0, "A": 1}.get(t.get("tier"), 2))
    menores = ("Weekly", "Biweekly", "Monthly", "Showmatch")
    c = [t for t in historico if t.get("url") and t.get("inicio") and
         (t.get("tier") in ("S", "A") or (t.get("tier") == "B" and t.get("estado") in ("en_curso", "proximo")) or
          (t.get("tier") == "C" and t.get("estado") == "en_curso" and t.get("tipo") not in menores))]
    return sorted(c, key=clave)


def detalle_cola(candidatos, ahora_dt):
    """[(torneo, ruta, detalle previo)] de las páginas que toca pedir: primero los torneos EN CURSO (nuevos o renovaciones:
    son los que la app enseña con los resultados del día), luego las que aún no se tienen (para que el histórico se
    complete en pocas noches) y al final las demás renovaciones, cada grupo en el orden de prioridad de los candidatos."""
    en_curso, nuevos, renovar = [], [], []
    for t in candidatos:
        ruta = os.path.join(TORNEOS_DETALLE_DIR, detalle_slug(t["url"]) + ".json")
        previo = leer_json(ruta, None)
        if detalle_toca(t, previo, ahora_dt):
            (en_curso if t.get("estado") == "en_curso" else renovar if previo else nuevos).append((t, ruta, previo))
    return en_curso + nuevos + renovar


def detalle_toca(t, previo, ahora_dt):
    """¿Hay que volver a pedir la página? previo = detalle guardado o None."""
    if not previo or not previo.get("obtenido") or (previo.get("v") or 1) < DETALLE_VERSION:
        return True                     # sin detalle, o de un esquema anterior (v1 no traía «cuadros»): se rehace
    try:
        edad_h = (ahora_dt - datetime.fromisoformat(previo["obtenido"])).total_seconds() / 3600
    except ValueError:
        return True
    hoy = ahora_dt.date()
    if t["estado"] == "en_curso":
        return edad_h >= 20
    if t["estado"] == "proximo":
        cerca = date.fromisoformat(t["inicio"]) - hoy <= timedelta(days=2)
        return edad_h >= (20 if cerca else 72)
    # terminado: una vez más tras acabar (con los puestos finales) y ya nunca
    return previo.get("estado_al_obtener") != "terminado" and hoy >= date.fromisoformat(t["fin"]) + timedelta(days=1)


def torneos_detalle():
    """torneos/<slug>.json de los torneos importantes de torneos_historico.json (ver el bloque de arriba). Nunca lanza;
    lo que falla se queda como estaba."""
    import time as _t
    hist = leer_json(TORNEOS_HISTORICO, None)
    if not hist or not hist.get("torneos"):
        log("detalle: sin torneos_historico.json")
        return
    ahora_dt = datetime.now(timezone.utc)
    candidatos = detalle_candidatos(hist["torneos"], ahora_dt.date())
    lq = Liquipedia()
    t0, hechos, fallos = _t.monotonic(), 0, 0
    try:
        for t, ruta, previo in detalle_cola(candidatos, ahora_dt):
            if hechos + fallos >= TORNEOS_DETALLE_POR_NOCHE or _t.monotonic() - t0 > TORNEOS_DETALLE_TIEMPO_S - LQ_ESPERA_PARSE_S:
                break
            try:
                d = lq.get({"action": "parse", "page": detalle_titulo(t["url"]), "prop": "text", "redirects": "1",
                            "disablelimitreport": "1", "disableeditsection": "1"}, intentos=1)
                html_txt = (d.get("parse") or {}).get("text") or ""
                if not html_txt:
                    raise RuntimeError("página vacía o inexistente")
                det = detalle_componer(html_txt, t, ahora())
                if not (det["participantes"] or det["premios"]["puestos"] or det["formato"]) and previo:
                    raise RuntimeError("sin nada legible: se conserva el anterior")
                escribir_json(ruta, det)
                hechos += 1
            except Exception as ex:
                fallos += 1
                log(f"detalle: {t['url']}: {ex!r}")
    finally:
        lq.cerrar()
    # fuera los de torneos que ya no están en el histórico
    validos = {detalle_slug(t["url"]) + ".json" for t in hist["torneos"] if t.get("url")}
    quedan = 0
    if os.path.isdir(TORNEOS_DETALLE_DIR):
        for a in os.listdir(TORNEOS_DETALLE_DIR):
            if a.endswith(".json") and a not in validos:
                os.remove(os.path.join(TORNEOS_DETALLE_DIR, a))
            else:
                quedan += 1
    pend = sum(1 for t in candidatos if detalle_toca(t, leer_json(os.path.join(TORNEOS_DETALLE_DIR, detalle_slug(t["url"]) + ".json"), None), ahora_dt))
    log(f"detalle: {len(candidatos)} candidatos, {hechos} páginas nuevas o renovadas, {fallos} fallos, {pend} pendientes "
        f"para otra noche; {quedan} archivos en {TORNEOS_DETALLE_DIR}/; {_t.monotonic() - t0:.0f} s")
    if fallos:
        print(f"::warning title=detalle::{fallos} páginas de torneo no se pudieron leer (se conserva lo anterior)", flush=True)


def detalle():
    """Paso «detalle» del build: páginas de los torneos importantes y la marca «detalle» en torneos.json/torneos_historico.json."""
    torneos_detalle()
    torneos_marcar_detalle()


def torneos_marcar_detalle():
    """Añade «detalle»: "torneos/<slug>.json" a los torneos de torneos.json y torneos_historico.json que lo tengan."""
    for ruta in ("torneos.json", TORNEOS_HISTORICO):
        d = leer_json(ruta, None)
        if not d:
            continue
        cambia = False
        for t in d.get("torneos", []):
            arch = f"{TORNEOS_DETALLE_DIR}/{detalle_slug(t['url'])}.json" if t.get("url") else None
            if arch and os.path.exists(arch):
                cambia |= t.get("detalle") != arch
                t["detalle"] = arch
            elif t.pop("detalle", None):
                cambia = True
        if cambia:
            escribir_json(ruta, d)


def detalle_probar():
    """Prueba sin red: HTML real recortado de 3 páginas (action=parse) con los resultados esperados."""
    m = leer_json(TORNEOS_DETALLE_MUESTRA)
    fallos = []
    for caso in m["casos"]:
        d = detalle_componer(caso["html"], caso["torneo"], "2026-10-19T05:00:00+00:00")
        for k, esp in caso["esperado"].items():
            if k == "n_participantes":
                if len(d["participantes"]) != esp:
                    fallos.append(f"{caso['torneo']['nombre']}: {len(d['participantes'])} participantes, se esperaban {esp}")
                continue
            v = d
            for p in k.split("."):
                v = v[int(p)] if isinstance(v, list) and p.isdigit() else (v.get(p) if isinstance(v, dict) else None)
            if v != esp:
                fallos.append(f"{caso['torneo']['nombre']}: {k} = {json.dumps(v, ensure_ascii=False)}, se esperaba {json.dumps(esp, ensure_ascii=False)}")
        if any("jugadores" in p for p in d["premios"]["puestos"]):
            fallos.append(f"{caso['torneo']['nombre']}: jugadores dentro de premios (spoiler)")
        log(f"  {caso['torneo']['nombre']}: {len(d['participantes'])} participantes, {len(d['premios']['puestos'])} puestos con "
            f"premio, {len(d['resultados']['puestos'])} con resultado, {len(d['fases'])} fases, {len(d['calendario'])} líneas de calendario")
    for txt, esp in {"May 7th - 10th, starting at 15:00": ("2026-05-07", "2026-05-10"), "November 25: WB Ro8": ("2026-11-25", None),
                     "August 10th - September 16th: Round Robin": ("2026-08-10", "2026-09-16"), "Group Stage:": (None, None),
                     "Feb 30": (None, None)}.items():
        if detalle_fechas(txt, 2026, 5) != esp:
            fallos.append(f"fechas {txt!r} → {detalle_fechas(txt, 2026, 5)}, se esperaba {esp}")
    if detalle_fechas("January 3: Final", 2026, 11) != ("2027-01-03", None):
        fallos.append(f"cambio de año: {detalle_fechas('January 3: Final', 2026, 11)}")
    if detalle_slug("https://liquipedia.net/ageofempires/Svenska_TG-ligan/2026/H%C3%B6st") != "svenska-tg-ligan-2026-host":
        fallos.append(f"slug: {detalle_slug('https://liquipedia.net/ageofempires/Svenska_TG-ligan/2026/H%C3%B6st')}")
    ahora_dt = datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)
    base = {"url": "u", "inicio": "2026-10-01", "fin": "2026-10-30", "estado": "en_curso"}
    for t, previo, esp in ((base, None, True), (base, {"obtenido": "2026-10-18T05:00:00+00:00"}, True),
                           (base, {"v": 3, "obtenido": "2026-10-19T01:00:00+00:00"}, False),
                           (base, {"v": 2, "obtenido": "2026-10-19T01:00:00+00:00"}, True),      # v2: sin tablas ni jornadas
                           (dict(base, estado="proximo", inicio="2026-11-20"), {"v": 3, "obtenido": "2026-10-17T05:00:00+00:00"}, False),
                           (dict(base, estado="proximo", inicio="2026-10-20"), {"obtenido": "2026-10-18T05:00:00+00:00"}, True),
                           (dict(base, estado="terminado", fin="2026-10-17"), {"obtenido": "2026-10-17T05:00:00+00:00", "estado_al_obtener": "en_curso"}, True),
                           (dict(base, estado="terminado", fin="2026-10-17"), {"obtenido": "2026-10-18T05:00:00+00:00", "estado_al_obtener": "terminado"}, True),
                           (dict(base, estado="terminado", fin="2026-10-17"), {"v": 3, "obtenido": "2026-10-18T05:00:00+00:00", "estado_al_obtener": "terminado"}, False)):
        if detalle_toca(t, previo, ahora_dt) != esp:
            fallos.append(f"toca {t['estado']} {previo} → {not esp}")
    hist = [{"url": "a", "tier": "S", "estado": "terminado", "inicio": "2026-01-01", "fin": "2026-01-05"},
            {"url": "b", "tier": "B", "estado": "terminado", "inicio": "2026-09-01", "fin": "2026-09-05"},
            {"url": "c", "tier": "B", "estado": "en_curso", "inicio": "2026-10-01", "fin": "2026-10-30"},
            {"url": "d", "tier": "A", "estado": "proximo", "inicio": "2026-12-01", "fin": "2026-12-05", "tipo": "Qualifier"},
            {"url": "e", "tier": "S", "estado": "proximo", "inicio": "2026-12-10", "fin": "2026-12-15"},
            {"url": "f", "tier": "C", "estado": "en_curso", "inicio": "2026-10-01", "fin": "2026-10-30"},
            {"url": "g", "tier": "C", "estado": "en_curso", "inicio": "2026-10-01", "fin": "2026-10-30", "tipo": "Weekly"},
            {"url": "h", "tier": "C", "estado": "proximo", "inicio": "2026-12-01", "fin": "2026-12-05"}]
    orden = [t["url"] for t in detalle_candidatos(hist, ahora_dt.date())]
    if orden != ["c", "f", "e", "d", "a"]:          # C solo en curso y no semanal
        fallos.append(f"candidatos {orden}, se esperaba ['c', 'f', 'e', 'd', 'a']")
    # cola: los en curso primero (c, renovación de hace un día, y f, nuevo); luego los que aún no tienen detalle; luego
    # las demás renovaciones
    global TORNEOS_DETALLE_DIR
    import shutil, tempfile
    dir_antes, tmp = TORNEOS_DETALLE_DIR, tempfile.mkdtemp()
    try:
        TORNEOS_DETALLE_DIR = tmp
        escribir_json(os.path.join(tmp, "c.json"), {"obtenido": "2026-10-18T05:00:00+00:00", "estado_al_obtener": "en_curso"})
        cola = [t["url"] for t, _, _ in detalle_cola(detalle_candidatos(hist, ahora_dt.date()), ahora_dt)]
        if cola != ["c", "f", "e", "d", "a"]:
            fallos.append(f"cola {cola}, se esperaba ['c', 'f', 'e', 'd', 'a']")
        escribir_json(os.path.join(tmp, "a.json"), {"v": DETALLE_VERSION, "obtenido": "2026-01-07T05:00:00+00:00",
                                                    "estado_al_obtener": "en_curso"})
        cola = [t["url"] for t, _, _ in detalle_cola(detalle_candidatos(hist, ahora_dt.date()), ahora_dt)]
        if cola != ["c", "f", "e", "d", "a"]:       # a (terminado) toca una vez más: renovación, al final
            fallos.append(f"cola con renovación {cola}, se esperaba ['c', 'f', 'e', 'd', 'a']")
    finally:
        TORNEOS_DETALLE_DIR = dir_antes
        shutil.rmtree(tmp, ignore_errors=True)
    # cuadros de eliminatorias: HTML real recortado (sencilla, doble eliminación 1v1 y 3v3)
    mc = leer_json(TORNEOS_CUADROS_MUESTRA)
    for caso in mc["casos"]:
        c = detalle_cuadros(caso["html"])
        if c != caso["esperado"]:
            fallos.append(f"cuadros de {caso['url']}: {json.dumps(c, ensure_ascii=False)[:300]}")
    w = detalle_cuadros(mc["casos"][0]["html"])
    final = w[0]["rondas"][-1] if w else {}
    if [r["nombre"] for r in (w[0]["rondas"] if w else [])] != ["Round of 12", "Quarterfinals", "Semifinals", "Final"] or             final.get("bo") != 9 or final.get("partidos") != [{"j1": {"nombre": "Liereyy", "pais": "AT"}, "j2": {"nombre": "ACCM", "pais": "VN"},
                                                               "p1": "5", "p2": "3", "ganador": 1}]:
        fallos.append(f"cuadro de Warlords 5: {json.dumps(w, ensure_ascii=False)[:300]}")
    r = detalle_cuadros(mc["casos"][1]["html"])
    if len(r) != 2 or r[0]["rondas"][-1]["nombre"] != "Grand Final" or r[1]["rondas"][0]["nombre"] != "Lower Bracket Round 1":
        fallos.append(f"doble eliminación: {[[x['nombre'] for x in c['rondas']] for c in r]}")
    for raro in ("", "<div class=\"brkts-bracket\"><div class=\"brkts-round-header\">", "<p>sin cuadro</p>"):
        if detalle_cuadros(raro) != []:
            fallos.append(f"cuadro de {raro!r} no vacío")
    # clasificaciones y jornadas (v3): HTML real recortado de DS_League (liga 1v1), The League (por equipos, tabla «tras»
    # cada semana) y un grupo de la Chilean Cup sin empezar (sin puestos)
    mt = leer_json(TORNEOS_TABLAS_MUESTRA)
    for caso in mt["casos"]:
        tablas, jornadas = detalle_tablas(caso["html"]), detalle_jornadas(caso["html"])
        if tablas != caso["tablas"] or jornadas != caso["jornadas"]:
            fallos.append(f"tablas/jornadas de {caso['url']} {caso['seccion']}: {json.dumps(tablas, ensure_ascii=False)[:200]} "
                          f"{json.dumps(jornadas, ensure_ascii=False)[:200]}")
    ds = detalle_tablas(mt["casos"][0]["html"])
    if not ds or ds[0]["filas"][0] != {"pos": 1, "nombre": "Ciskhan", "pais": "FR", "zona": "sube", "dif": "+14", "puntos": 18,
                                       "partidos": "6-0-0", "juegos": "18-4"} or len(ds[0]["filas"]) != 10 or "tras" in ds[0]:
        fallos.append(f"tabla de DS_League: {json.dumps(ds, ensure_ascii=False)[:300]}")
    jd = detalle_jornadas(mt["casos"][1]["html"])
    if [j["nombre"] for j in jd] != [f"Round {i}" for i in range(1, 10)] or jd[0]["partidos"][0] != {
            "j1": {"nombre": "Ciskhan", "pais": "FR"}, "j2": {"nombre": "VarVarus", "pais": "AR"}, "p1": "3", "p2": "0",
            "ganador": 1, "fecha": "2026-08-19T22:00:00Z", "bo": 5}:
        fallos.append(f"jornadas de DS_League: {json.dumps(jd[:1], ensure_ascii=False)[:300]}")
    tl = detalle_tablas(mt["casos"][2]["html"])
    if not tl or tl[0].get("tras") != "Week 9" or len(tl[0]["filas"]) != 9 or any("\u25b2" in f["nombre"] or "\u25bc" in f["nombre"] for f in tl[0]["filas"]):
        fallos.append(f"tabla de The League (semana por defecto, sin ▲▼): {json.dumps(tl, ensure_ascii=False)[:300]}")
    gc = detalle_tablas(mt["casos"][3]["html"])
    if not gc or any("pos" in f for f in gc[0]["filas"]) or len(gc[0]["filas"]) != 4:
        fallos.append(f"grupo sin empezar: {json.dumps(gc, ensure_ascii=False)[:300]}")
    for raro in ("", "<table class=\"grouptable\"><tr><th>1.</th></tr></table>", "<div class=\"brkts-matchlist\"></div>"):
        if detalle_tablas(raro) != [] or detalle_jornadas(raro) != []:
            fallos.append(f"tablas/jornadas de {raro!r} no vacías")
    for f in fallos:
        log("FALLO", f)
    log(f"detalle --probar: {len(m['casos'])} páginas, {len(mc['casos'])} cuadros y {len(mt['casos'])} tablas/jornadas, "
        f"{len(fallos)} fallos")
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
NOTICIAS_DIR = "noticias"                 # portadas JPEG en la rama data (noticias/<sha1[:12]>.jpg)
NOTICIAS_PORTADA_W, NOTICIAS_PORTADA_H = 576, 324   # 16:9, el doble de la tarjeta de la app (nítida a 125-200 %)
NOTICIAS_PORTADA_CALIDAD = 82
NOTICIAS_PORTADA_MAX_BYTES = 6_000_000    # una imagen destacada más grande no se baja
NOTICIAS_PORTADA_MAX_PIXELES = 40_000_000 # tope para Pillow (bomba de descompresión)


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


def noticias_imagen_grande(media):
    """La versión de la imagen destacada para la portada: «medium_large» (768 de ancho) → «large» → «medium»; nunca el original."""
    tam = (media.get("media_details") or {}).get("sizes") or {}
    for k in ("medium_large", "large", "medium"):
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


def noticias_portada_ruta(url):
    """noticias/<sha1 de la URL de origen[:12]>.jpg (con «/», como va en el JSON): la misma imagen, el mismo archivo."""
    import hashlib
    return f"{NOTICIAS_DIR}/{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}.jpg"


def noticias_portada_jpg(raw):
    """Bytes de imagen (WebP, PNG, JPEG…) → JPEG RGB 16:9 de NOTICIAS_PORTADA_W x NOTICIAS_PORTADA_H (recorte centrado), sin
    metadatos. Lanza si no es una imagen o es enorme."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = NOTICIAS_PORTADA_MAX_PIXELES
    im = Image.open(io.BytesIO(raw))
    if im.width * im.height > NOTICIAS_PORTADA_MAX_PIXELES:
        raise ValueError(f"imagen enorme {im.width}x{im.height}")
    im.seek(0)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        fondo = Image.new("RGB", im.size, (255, 255, 255))
        fondo.paste(im, mask=im.getchannel("A"))
        im = fondo
    else:
        im = im.convert("RGB")
    w, h = im.size                              # recorte centrado a 16:9 y, después, a su tamaño
    if w * 9 > h * 16:
        nw = h * 16 // 9
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    elif w * 9 < h * 16:
        nh = w * 9 // 16
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((NOTICIAS_PORTADA_W, NOTICIAS_PORTADA_H), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=NOTICIAS_PORTADA_CALIDAD, optimize=True, progressive=True)
    return out.getvalue()


def noticias_descargar(url):
    """Una imagen del CDN de la web (solo https de AOE_HOSTS_IMG y como mucho NOTICIAS_PORTADA_MAX_BYTES), o None."""
    if not noticias_url_ok(url, AOE_HOSTS_IMG):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sfr-data (aoe2radar; +https://github.com/jguardiola-dev/sfr-data)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read(NOTICIAS_PORTADA_MAX_BYTES + 1)
        if len(raw) > NOTICIAS_PORTADA_MAX_BYTES:
            log(f"noticias: portada demasiado grande ({url})")
            return None
        time.sleep(0.5)                         # sin prisa con el CDN
        return raw
    except Exception as ex:
        log(f"noticias: portada {url}: {ex!r}")
        return None


def noticias_portadas(lista, origenes, descargar, previo=None):
    """Pone «portada» a cada noticia: la imagen de origenes[url de la noticia] (la grande) o, si no, su «imagen», pasada a JPEG
    en noticias/ (si el archivo ya está, no se baja). Si una descarga falla, se queda la portada del noticias.json anterior
    (misma URL) si su archivo sigue en disco. Después borra de noticias/ los JPEG que no usa nadie. Nunca lanza por una
    imagen: esa noticia sale sin portada. Devuelve (con portada, descargas, bytes nuevos)."""
    previos = {n.get("url"): n.get("portada") for n in (previo or {}).get("noticias", []) if n.get("url")}
    bajadas = nbytes = 0
    for n in lista:
        n.pop("portada", None)
        fuente = origenes.get(n["url"]) or n.get("imagen")
        if fuente and noticias_url_ok(fuente, AOE_HOSTS_IMG):
            ruta = noticias_portada_ruta(fuente)
            if not os.path.exists(ruta):
                raw = descargar(fuente)
                bajadas += 1
                if raw:
                    try:
                        jpg = noticias_portada_jpg(raw)
                        os.makedirs(os.path.dirname(ruta), exist_ok=True)
                        with open(ruta, "wb") as f:
                            f.write(jpg)
                        nbytes += len(jpg)
                    except Exception as ex:
                        log(f"noticias: portada ilegible ({fuente}): {ex!r}")
            if os.path.exists(ruta):
                n["portada"] = ruta
                continue
        ant = previos.get(n["url"])
        if ant and os.path.exists(ant):
            n["portada"] = ant
    usadas = {os.path.normpath(n["portada"]) for n in lista if n.get("portada")}
    if os.path.isdir(NOTICIAS_DIR):
        for a in os.listdir(NOTICIAS_DIR):
            ruta = os.path.join(NOTICIAS_DIR, a)
            if os.path.normpath(ruta) not in usadas:
                os.remove(ruta)
    return sum(1 for n in lista if n.get("portada")), bajadas, nbytes


def noticias():
    """noticias.json: titulares de AoE II de la web oficial (esquema en la cabecera, normas arriba). Si la fuente falla o no da
    ninguna noticia, no se escribe: se queda el anterior (recuperado de la rama data) con aviso ::warning::. Si solo fallan
    categorías o miniaturas, se publica igual y esos campos salen del noticias.json anterior (misma URL) o se omiten."""
    previo = leer_json("noticias.json", None)
    web = WebAoE()
    categorias, medios, grandes = {}, {}, {}
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
                grandes = {m["id"]: noticias_imagen_grande(m) for m in d if noticias_imagen_grande(m)}
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
    portadas = "sin portadas"
    try:
        import PIL  # noqa: F401
        origenes = {p.get("link"): grandes.get(p.get("featured_media")) for p in posts if grandes.get(p.get("featured_media"))}
        con, bajadas, nbytes = noticias_portadas(lista, origenes, noticias_descargar, previo)
        portadas = f"{con} con portada ({bajadas} descargas, {nbytes / 1024:.0f} KB nuevos)"
    except ImportError:
        print("::warning title=noticias::falta Pillow (pip install pillow): noticias sin portada", flush=True)
    except Exception as ex:
        print(f"::warning title=noticias::portadas ({ex!r}): se publican sin las que fallaron", flush=True)
    escribir_json("noticias.json", noticias_salida(lista, [NOTICIAS_FUENTE]))
    log(f"noticias: {len(lista)} noticias (la más reciente {lista[0]['fecha'][:10]}); "
        f"{sum('imagen' in n for n in lista)} con imagen, {portadas}; {web.peticiones} peticiones a ageofempires.com")


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
    if any(set(n) - {"titulo", "fecha", "fuente", "url", "categoria", "imagen", "portada"} for n in lista):
        fallos.append("campos de más en alguna noticia")
    grandes = {x["id"]: noticias_imagen_grande(x) for x in m["medios"] if noticias_imagen_grande(x)}
    if any(not noticias_url_ok(u, AOE_HOSTS_IMG) for u in grandes.values()):
        fallos.append("una imagen grande que no es del CDN de la web")
    fallos += noticias_portadas_probar(lista)
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


def noticias_portadas_probar(lista):
    """Portadas sin red: las «descargas» son imágenes WebP/PNG generadas con Pillow en memoria, en una carpeta temporal.
    Devuelve la lista de fallos."""
    import copy, shutil, tempfile
    from PIL import Image
    fallos, pedidas = [], []
    lista = copy.deepcopy(lista)
    con_imagen = [n for n in lista if n.get("imagen")]
    if len(con_imagen) < 2:
        return ["la muestra necesita al menos 2 noticias con imagen"]
    rota = con_imagen[1]["imagen"]

    def descargar(url):
        pedidas.append(url)
        if url == rota:
            return b"<html>esto no es una imagen</html>"
        im = Image.new("RGBA", (800, 600), (30, 90, 200, 255))      # 4:3 con alfa → recorte a 16:9, fondo blanco
        b = io.BytesIO()
        im.save(b, "WEBP" if len(pedidas) % 2 else "PNG")
        return b.getvalue()

    tmp, cwd = tempfile.mkdtemp(), os.getcwd()
    try:
        os.chdir(tmp)
        con, bajadas, _ = noticias_portadas(lista, {}, descargar)
        if bajadas != len(con_imagen) or con != len(con_imagen) - 1:
            fallos.append(f"portadas: {con} con portada y {bajadas} descargas, se esperaban {len(con_imagen) - 1} y {len(con_imagen)}")
        for n in lista:
            p = n.get("portada")
            if n.get("imagen") == rota or not n.get("imagen"):
                if p:
                    fallos.append(f"{n['url']}: no debería tener portada")
                continue
            if p != noticias_portada_ruta(n["imagen"]):
                fallos.append(f"{n['url']}: portada {p!r}")
                continue
            with Image.open(p) as im:
                if im.format != "JPEG" or im.size != (NOTICIAS_PORTADA_W, NOTICIAS_PORTADA_H) or im.mode != "RGB":
                    fallos.append(f"{p}: {im.format} {im.size} {im.mode}")
        # segunda pasada: en caché (solo se reintenta la rota); una portada anterior se hereda si su descarga falla
        antes = len(pedidas)
        previo = {"noticias": copy.deepcopy(lista)}
        lista2 = copy.deepcopy(lista)
        noticias_portadas(lista2, {}, descargar, previo)
        if len(pedidas) - antes != 1:
            fallos.append(f"caché: {len(pedidas) - antes} descargas en la segunda pasada, se esperaba 1 (la rota)")
        sin_red = copy.deepcopy(lista)
        for n in sin_red:
            if n.get("imagen"):
                n["imagen"] = n["imagen"] + "?nueva"                   # otra URL: no está en caché y la descarga falla
        noticias_portadas(sin_red, {}, lambda url: None, previo)
        if [n.get("portada") for n in sin_red] != [n.get("portada") for n in lista]:
            fallos.append("si la descarga falla no se hereda la portada anterior")
        # la grande manda sobre la miniatura; y lo que no usa nadie se borra
        n0 = con_imagen[0]
        lista3 = [dict(n0)]
        noticias_portadas(lista3, {n0["url"]: n0["imagen"].replace(".webp", "-768x432.webp")}, descargar)
        if lista3[0].get("portada") != noticias_portada_ruta(n0["imagen"].replace(".webp", "-768x432.webp")):
            fallos.append(f"origen grande: {lista3[0].get('portada')!r}")
        if sorted(os.listdir(NOTICIAS_DIR)) != [os.path.basename(lista3[0]["portada"])]:
            fallos.append(f"podar: quedan {sorted(os.listdir(NOTICIAS_DIR))}")
        if noticias_portadas([{"url": "https://www.ageofempires.com/x", "imagen": "https://evil.example.com/x.webp"}], {}, descargar)[1] != 0:
            fallos.append("una imagen de fuera del CDN no se baja")
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        noticias_portada_jpg(b"<html>no</html>")
        fallos.append("noticias_portada_jpg debería fallar con algo que no es una imagen")
    except Exception:
        pass
    if not noticias_portada_ruta("https://cdn.ageofempires.com/a.webp").startswith("noticias/") or \
            noticias_portada_ruta("https://cdn.ageofempires.com/a.webp") != noticias_portada_ruta("https://cdn.ageofempires.com/a.webp"):
        fallos.append("ruta de portada")
    return fallos


# ----------------------------------------------------------------------------- partidos (Liquipedia)
# Próximos partidos, en curso y resultados recientes de AoE II, con las mismas normas de la API de Liquipedia que torneos
# (cliente Liquipedia de arriba). Fuente: el «match ticker» de la wiki, el mismo módulo que pinta la página
# «Liquipedia:Upcoming and ongoing matches» ({{#invoke:Lua|invoke|module=MatchTicker/Custom|fn=mainPage|…}}, que consulta
# LiquipediaDB en el servidor). En vez de pedir la página (todos los juegos de AoE, límite 50) se manda un solo action=parse
# con dos llamadas al módulo filtradas por game=Age of Empires II: type=upcoming (sin terminar: en curso y próximos) y
# type=recent (terminados, del más reciente al más antiguo). 1 petición por ejecución; ni HTML fuera de la API ni
# LiquipediaDB directa. El HTML del ticker trae fecha (timestamp UNIX), rivales con bandera, marcador, Bo-N, torneo con su
# sección y, a veces, botón de stream (Special:Stream/twitch/<canal>). Contenido CC BY-SA 3.0.
PARTIDOS_LIMITE_PROXIMOS = 80    # partidos sin terminar que devuelve el ticker (hoy ≈15 de AoE II; aviso si se llena)
PARTIDOS_LIMITE_RECIENTES = 100  # terminados (ordenados del más reciente): hacen falta los de 24 h (≈40 un domingo)
PARTIDOS_HORAS_PASADO = 24       # terminados de las últimas 24 h
PARTIDOS_DIAS_FUTURO = 7         # próximos 7 días
PARTIDOS_EN_CURSO_MAX_H = 12     # sin terminar y empezado hace más de 12 h = nadie lo cerró en la wiki: fuera
PARTIDOS_MUESTRA = os.path.join("pruebas", "partidos_muestra.json")
PARTIDOS_GAME = "Age of Empires II"
PARTIDOS_FASES_VACIAS = {"results", "resultados"}    # ancla genérica de la página: no es una fase


def partidos_wikitexto():
    def ticker(clase, tipo, limite):
        return (f'<div class="{clase}">{{{{#invoke:Lua|invoke|module=MatchTicker/Custom|fn=mainPage|type={tipo}'
                f'|limit={limite}|filterbuttons-game={PARTIDOS_GAME}}}}}</div>')
    return "\n".join((ticker("sfr-proximos", "upcoming", PARTIDOS_LIMITE_PROXIMOS),
                      ticker("sfr-recientes", "recent", PARTIDOS_LIMITE_RECIENTES)))


def partidos_pais(src):
    """Bandera de Liquipedia → ISO 3166-1 alfa-2 en mayúsculas («/…/Se_hd.png» → "SE"; «Uk_hd.png» → "GB")."""
    import re
    m = re.search(r"/([A-Za-z]{2})_hd\.png", src or "")
    if not m:
        return None
    c = m.group(1).upper()
    if c in ("EU", "UN"):                 # banderas que no son de un país
        return None
    return {"UK": "GB", "EN": "GB", "SC": "GB", "WA": "GB"}.get(c, c)      # Inglaterra, Escocia, Gales → GB


def partidos_stream(href):
    """Botón de stream del ticker → URL directa. Twitch: twitch.tv/<canal>. YouTube solo si es un id de canal (UC…);
    el resto (vídeos, otras plataformas) no se publica: resolverlo exigiría abrir Special:Stream, que es HTML."""
    import re, urllib.parse
    m = re.search(r"/Special:Stream/([a-z]+)/([^?#]+)", href or "")
    if not m:
        return None
    plataforma, canal = m.group(1), urllib.parse.unquote(m.group(2))
    if plataforma == "twitch" and re.fullmatch(r"[A-Za-z0-9_]{2,40}", canal):
        return "https://www.twitch.tv/" + canal.lower()
    if plataforma == "youtube" and re.fullmatch(r"UC[A-Za-z0-9_-]{22}", canal):
        return f"https://www.youtube.com/channel/{canal}/live"
    return None


def partidos_html(html_txt):
    """HTML de action=parse → {"proximos": [bloques], "recientes": [bloques], "errores": [sección]} (sin filtrar).
    Bloque: {"ts", "terminado", "rivales":[{"nombres":[…], "paises":[…], "equipo":bool, "gana":bool}], "marcador":[…],
             "bo", "torneo_txt", "href", "streams":[…]}."""
    from html.parser import HTMLParser
    VACIAS = {"img", "br", "hr", "input", "meta", "link", "wbr", "source"}

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.secciones = {"proximos": [], "recientes": []}
            self.errores = []
            self.seccion = None
            self.pila = []        # [(tag, papel)]
            self.m = None         # partido en curso
            self.txt = None       # texto que se está recogiendo: (papel, [trozos])
            self.titulo = None    # title del enlace dentro del nombre

        def handle_starttag(self, tag, attrs):
            a = {k: (v or "") for k, v in attrs}
            cls = a.get("class", "").split()
            papel = None
            if tag == "div" and "sfr-proximos" in cls:
                self.seccion, papel = "proximos", "seccion"
            elif tag == "div" and "sfr-recientes" in cls:
                self.seccion, papel = "recientes", "seccion"
            elif self.seccion and ("error" in cls or "scribunto-error" in cls):
                if self.seccion not in self.errores:
                    self.errores.append(self.seccion)
            elif self.seccion and tag == "div" and "match-info" in cls:
                self.m = {"ts": None, "terminado": self.seccion == "recientes", "rivales": [], "marcador": [], "bo": None,
                          "torneo_txt": None, "href": None, "streams": []}
                self.secciones[self.seccion].append(self.m)
            elif self.m is not None:
                if tag == "span" and "timer-object" in cls and a.get("data-timestamp", "").isdigit():
                    self.m["ts"] = int(a["data-timestamp"])
                    if a.get("data-finished"):
                        self.m["terminado"] = True
                elif tag == "div" and "match-info-header-opponent" in cls:
                    self.m["rivales"].append({"nombres": [], "paises": [], "equipo": False,
                                              "gana": "match-info-header-winner" in cls})
                elif tag == "div" and "block-team" in cls and self.m["rivales"]:
                    self.m["rivales"][-1]["equipo"] = True
                elif tag == "div" and "block-player" in cls and self.m["rivales"]:
                    self.m["rivales"][-1]["paises"].append(None)
                    self.m["rivales"][-1]["nombres"].append(None)
                elif tag == "img" and self.pila and self.pila[-1][1] == "bandera" and self.m["rivales"]:
                    r = self.m["rivales"][-1]
                    if r["paises"]:
                        r["paises"][-1] = partidos_pais(a.get("src"))
                elif tag == "span" and "flag" in cls:
                    papel = "bandera"
                elif tag == "span" and "name" in cls and self.m["rivales"]:
                    papel = "nombre"
                elif tag == "span" and "match-info-header-scoreholder-score" in cls:
                    papel = "marcador"
                elif tag == "span" and "match-info-header-scoreholder-lower" in cls:
                    papel = "bo"
                elif tag == "span" and "match-info-tournament-name" in cls:
                    papel = "torneo"
                elif tag == "a" and any(p == "torneo" for _, p in self.pila) and not self.m["href"]:
                    self.m["href"] = a.get("href")
                elif tag == "a" and "/Special:Stream/" in a.get("href", ""):
                    self.m["streams"].append(a["href"])
                elif tag == "a" and self.txt and self.txt[0] == "nombre" and a.get("title"):
                    self.titulo = a["title"].replace(" (page does not exist)", "").strip()     # equipos: nombre completo («Team Ceepki», «Canada») en vez del corto
                if papel in ("nombre", "marcador", "bo", "torneo"):
                    self.txt, self.titulo = (papel, []), None
            if tag not in VACIAS:
                self.pila.append((tag, papel))

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag not in VACIAS:
                self.handle_endtag(tag)

        def handle_endtag(self, tag):
            if tag in VACIAS or not any(t == tag for t, _ in self.pila):
                return
            while self.pila:
                t, papel = self.pila.pop()
                self._cerrar(papel)
                if t == tag:
                    break

        def _cerrar(self, papel):
            if papel == "seccion":
                self.seccion, self.m = None, None
                return
            if not papel or not self.txt or self.txt[0] != papel or self.m is None:
                return
            texto = " ".join("".join(self.txt[1]).split())
            self.txt = None
            if papel == "nombre":
                r = self.m["rivales"][-1]
                if r["nombres"] and r["nombres"][-1] is None:
                    r["nombres"][-1] = texto
                else:                       # equipo (block-team): un solo nombre, sin país
                    r["nombres"].append(self.titulo if r["equipo"] and self.titulo else texto)
                    r["paises"].append(None)
            elif papel == "marcador":
                self.m["marcador"].append(texto)
            elif papel == "bo":
                self.m["bo"] = texto
            elif papel == "torneo":
                self.m["torneo_txt"] = texto

        def handle_data(self, data):
            if self.txt is not None:
                self.txt[1].append(data)

    p = P()
    p.feed(html_txt or "")
    p.close()
    return {"proximos": p.secciones["proximos"], "recientes": p.secciones["recientes"], "errores": p.errores}


def partidos_iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def partidos_lado(r):
    """Rival del ticker → (texto, país ISO2 | None). Varios jugadores (2v2 sin equipo) se unen con « & »."""
    nombres = [n for n in r["nombres"] if n]
    if not nombres:
        return "TBD", None
    pais = r["paises"][0] if len(nombres) == 1 and not r["equipo"] and r["paises"] else None
    return " & ".join(nombres), pais


def partidos_componer(secciones, ahora_dt):
    """Bloques del ticker → lista final en la ventana (terminados 24 h, en curso, próximos 7 días), sin duplicados y ordenada:
    en_curso (por inicio), proximo (por inicio), terminado (el más reciente primero)."""
    import re, urllib.parse
    t_ahora = ahora_dt.timestamp()
    desde = t_ahora - PARTIDOS_HORAS_PASADO * 3600
    hasta = t_ahora + PARTIDOS_DIAS_FUTURO * 86400
    out, vistos = [], set()
    for b in secciones.get("proximos", []) + secciones.get("recientes", []):
        try:
            if b.get("ts") is None or len(b.get("rivales") or []) != 2 or not b.get("href"):
                continue
            ts = b["ts"]
            if b["terminado"]:
                if not desde <= ts <= t_ahora + 3600:
                    continue
                estado = "terminado"
            elif ts <= t_ahora:
                if ts < t_ahora - PARTIDOS_EN_CURSO_MAX_H * 3600:
                    continue
                estado = "en_curso"
            elif ts <= hasta:
                estado = "proximo"
            else:
                continue
            (j1, p1), (j2, p2) = partidos_lado(b["rivales"][0]), partidos_lado(b["rivales"][1])
            if j1 == "TBD" and j2 == "TBD":
                continue
            ruta, _, ancla = b["href"].partition("#")
            if not ruta.startswith("/ageofempires/") or "redlink=1" in ruta or "action=edit" in ruta:
                continue
            fase = " ".join(urllib.parse.unquote(ancla).replace("_", " ").split()) or None
            if fase and fase.lower() in PARTIDOS_FASES_VACIAS:
                fase = None
            texto = b.get("torneo_txt") or urllib.parse.unquote(ruta.split("/ageofempires/", 1)[1]).replace("_", " ")
            torneo = texto[:-len(" - " + fase)] if fase and texto.endswith(" - " + fase) else texto
            p = {"torneo": torneo, "torneo_url": LQ_BASE + ruta}
            if fase:
                p["fase"] = fase
            p.update(inicio=partidos_iso(ts), estado=estado, j1=j1, j2=j2)
            if p1:
                p["j1_pais"] = p1
            if p2:
                p["j2_pais"] = p2
            bo = re.search(r"\bBo\s*(\d{1,2})\b", b.get("bo") or "", re.I)
            if bo:
                p["formato"] = f"Bo{int(bo.group(1))}"
            stream = next((s for s in map(partidos_stream, b.get("streams") or []) if s), None)
            if stream and estado != "terminado":
                p["stream"] = stream
            marcador = b.get("marcador") or []
            if estado != "proximo" and len(marcador) == 2 and all(re.fullmatch(r"\d{1,2}|W|L|FF|DQ|D", x) for x in marcador):
                p["resultado"] = f"{marcador[0]}-{marcador[1]}"
            ganan = [i for i, r in enumerate(b["rivales"]) if r.get("gana")]
            if estado == "terminado" and len(ganan) == 1:        # empate o sin dato: sin ganador
                p["ganador"] = (j1, j2)[ganan[0]]
            clave = (p["torneo_url"], p["inicio"], j1, j2)
            if clave in vistos:
                continue
            vistos.add(clave)
            out.append(p)
        except Exception as ex:
            log(f"partidos: bloque ilegible: {ex!r}")
    orden = {"en_curso": 0, "proximo": 1}
    vivos = sorted((p for p in out if p["estado"] != "terminado"),
                   key=lambda p: (orden[p["estado"]], p["inicio"], p["torneo"].lower()))
    term = sorted((p for p in out if p["estado"] == "terminado"), key=lambda p: p["inicio"], reverse=True)
    return vivos + term


def partidos_salida(lista, ahora_dt):
    g = ahora()
    return {"v": 1, "generado": g,
            "ventana": {"desde": partidos_iso(ahora_dt.timestamp() - PARTIDOS_HORAS_PASADO * 3600),
                        "hasta": partidos_iso(ahora_dt.timestamp() + PARTIDOS_DIAS_FUTURO * 86400)},
            "fuente": {"nombre": "Liquipedia", "url": "https://liquipedia.net/ageofempires/Liquipedia:Upcoming_and_ongoing_matches",
                       "licencia": "CC BY-SA 3.0", "licencia_url": "https://creativecommons.org/licenses/by-sa/3.0/",
                       "atribucion": "Partidos de Liquipedia (liquipedia.net/ageofempires), licencia CC BY-SA 3.0. "
                                     "Este archivo se distribuye con la misma licencia.",
                       "generado": g},
            "partidos": lista}


def partidos():
    """partidos.json desde el ticker de Liquipedia (esquema en la cabecera, normas arriba). Si la petición falla, alguna
    sección viene con error de Lua o el ticker no trae ningún partido, no se escribe: se queda el anterior (rama data) con
    aviso ::warning::. Si el ticker responde pero nada cae en la ventana y el anterior tenía partidos, tampoco se escribe
    (nunca se publica vacío encima de datos); el paso no rompe el build."""
    ahora_dt = datetime.now(timezone.utc)
    previo = leer_json("partidos.json", None)
    lq = Liquipedia()
    try:
        d = lq.get({"action": "parse", "title": "Liquipedia:Upcoming and ongoing matches", "contentmodel": "wikitext",
                    "prop": "text", "text": partidos_wikitexto(), "disablelimitreport": "1", "disableeditsection": "1"})
        sec = partidos_html(d.get("parse", {}).get("text", ""))
        if sec["errores"]:
            raise RuntimeError(f"error de Lua en {sec['errores']}")
        if not sec["proximos"] and not sec["recientes"]:
            raise RuntimeError("el ticker no trae ningún partido")
        # ticker lleno y su último partido aún dentro de la ventana → puede faltar alguno (se publica igual)
        t0 = ahora_dt.timestamp()
        for k, lim, dentro in (("proximos", PARTIDOS_LIMITE_PROXIMOS, lambda ts: ts <= t0 + PARTIDOS_DIAS_FUTURO * 86400),
                               ("recientes", PARTIDOS_LIMITE_RECIENTES, lambda ts: ts >= t0 - PARTIDOS_HORAS_PASADO * 3600)):
            tss = [b["ts"] for b in sec[k] if b.get("ts") is not None]
            if len(sec[k]) >= lim and tss and dentro(tss[-1]):
                print(f"::warning title=partidos::el ticker «{k}» llegó al límite ({lim}) dentro de la ventana: "
                      "puede faltar algún partido", flush=True)
        lista = partidos_componer(sec, ahora_dt)
        if not lista and (previo or {}).get("partidos"):
            raise RuntimeError(f"{len(sec['proximos'])}+{len(sec['recientes'])} bloques pero ninguno en la ventana")
    except Exception as ex:
        print(f"::warning title=partidos::Liquipedia no respondió bien ({ex!r}): se conserva el partidos.json anterior", flush=True)
        return
    finally:
        lq.cerrar()
    escribir_json("partidos.json", partidos_salida(lista, ahora_dt))
    cuenta = defaultdict(int)
    for p in lista:
        cuenta[p["estado"]] += 1
    log(f"partidos: {len(lista)} partidos ({dict(cuenta)}) de {len(sec['proximos'])}+{len(sec['recientes'])} bloques; "
        f"{lq.peticiones} peticiones a Liquipedia")


def partidos_probar():
    """Prueba sin red: HTML del ticker guardado (recortado) con una hora fija, y casos límite."""
    m = leer_json(PARTIDOS_MUESTRA)
    ahora_dt = datetime.fromisoformat(m["ahora"].replace("Z", "+00:00"))
    sec = partidos_html(m["html"])
    lista = partidos_componer(sec, ahora_dt)
    fallos = []
    if sec["errores"]:
        fallos.append(f"errores inesperados: {sec['errores']}")
    for esperado in m["esperado"]:
        p = next((x for x in lista if x["j1"] == esperado["j1"] and x["j2"] == esperado["j2"]), None)
        if p is None:
            fallos.append(f"falta {esperado['j1']} vs {esperado['j2']}")
            continue
        for k, v in esperado.items():
            if p.get(k) != v:
                fallos.append(f"{esperado['j1']} vs {esperado['j2']}: {k} = {p.get(k)!r}, se esperaba {v!r}")
        for k in ("fase", "j1_pais", "j2_pais", "formato", "stream", "resultado", "ganador"):
            if k not in esperado and k in p:
                fallos.append(f"{esperado['j1']} vs {esperado['j2']}: {k} no debería estar")
    for j1, j2 in m.get("fuera", []):
        if any(x["j1"] == j1 and x["j2"] == j2 for x in lista):
            fallos.append(f"{j1} vs {j2} no debería salir")
    if len(lista) != m["total"]:
        fallos.append(f"{len(lista)} partidos, se esperaban {m['total']}")
    orden = [p["estado"] for p in lista]
    if orden != sorted(orden, key=["en_curso", "proximo", "terminado"].index):
        fallos.append(f"orden de estados: {orden}")
    for est, rev in (("proximo", False), ("terminado", True)):
        ini = [p["inicio"] for p in lista if p["estado"] == est]
        if ini != sorted(ini, reverse=rev):
            fallos.append(f"orden de {est}: {ini}")
    if any(set(p) - {"torneo", "torneo_url", "fase", "inicio", "estado", "j1", "j2", "j1_pais", "j2_pais", "formato",
                     "stream", "resultado", "ganador"} for p in lista):
        fallos.append("campos de más en algún partido")
    if any(not p["inicio"].endswith("Z") for p in lista):
        fallos.append("alguna hora no va en UTC con Z")
    if len({(p["torneo_url"], p["inicio"], p["j1"], p["j2"]) for p in lista}) != len(lista):
        fallos.append("hay partidos duplicados")
    vacio = partidos_html("<p>nada</p>")
    if vacio["proximos"] or vacio["recientes"] or partidos_componer(vacio, ahora_dt) != []:
        fallos.append("HTML sin ticker debería dar [] (y partidos() no escribe)")
    err = partidos_html('<div class="sfr-proximos"><strong class="error"><span class="scribunto-error">Lua error</span></strong></div>')
    if err["errores"] != ["proximos"]:
        fallos.append(f"error de Lua no detectado: {err['errores']}")
    for href, esp in {"/ageofempires/Special:Stream/twitch/Paradox303": "https://www.twitch.tv/paradox303",
                      "/ageofempires/Special:Stream/youtube/UCabcdefghijklmnopqrstuv": "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv/live",
                      "/ageofempires/Special:Stream/youtube/dQw4w9WgXcQ": None, "/ageofempires/Special:Stream/kick/x": None,
                      "/ageofempires/Special:Stream/twitch/a%22b": None}.items():
        if partidos_stream(href) != esp:
            fallos.append(f"stream {href} → {partidos_stream(href)}, se esperaba {esp}")
    for src, esp in {"/commons/images/thumb/0/02/Se_hd.png/36px-Se_hd.png": "SE", "/x/Uk_hd.png": "GB", "/x/En_hd.png": "GB",
                     "/x/Eu_hd.png": None, "/x/Flag.png": None}.items():
        if partidos_pais(src) != esp:
            fallos.append(f"país {src} → {partidos_pais(src)}, se esperaba {esp}")
    for p in lista:
        log(f"  {p['estado']:9} {p['inicio']}  {p.get('formato') or '-':4} {p['j1']} vs {p['j2']}  · {p['torneo']}"
            f"{' · ' + p['fase'] if p.get('fase') else ''}")
    for f in fallos:
        log("FALLO", f)
    log(f"partidos --probar: {len(lista)} partidos, {len(fallos)} fallos")
    return not fallos


# ----------------------------------------------------------------------------- streamers (Twitch Helix)
# Imagen de perfil pública de los canales de Twitch que enseña la app: los creadores de las build orders (lista fija), el top
# de directos de AoE II en este momento y los canales que salen en partidos.json (stream) y torneos.json (enlaces.twitch).
# API Helix (https://dev.twitch.tv/docs/api/reference): exige una app de desarrollador de Twitch y un token de aplicación
# (client_credentials). Las credenciales van SOLO en variables de entorno (secretos de GitHub Actions TWITCH_CLIENT_ID y
# TWITCH_CLIENT_SECRET), nunca en el repo ni en la app; si faltan, el paso se salta con ::notice. Por noche: 1 token,
# 1 Get Games (ids de la categoría, por nombre: no se fija un id a ciegas), 1 Get Streams (top 20 de AoE II) y 1 Get Users
# (hasta 100 logins). Las imágenes se sirven desde el CDN de Twitch (static-cdn.jtvnw.net) y Twitch permite mostrarlas
# enlazando al canal: se guarda solo la URL, no se descargan.
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_HELIX = "https://api.twitch.tv/helix/"
TWITCH_JUEGOS = ("Age of Empires II", "Age of Empires II: Definitive Edition")   # categorías de Twitch (Get Games por nombre)
TWITCH_TOP_DIRECTOS = 20
TWITCH_MAX_LOGINS = 100         # máximo de Get Users por petición
TWITCH_HOST_AVATAR = "static-cdn.jtvnw.net"
STREAMERS_MUESTRA = os.path.join("pruebas", "streamers_muestra.json")
# creador de build orders (clave en la app) → login de Twitch. Comprobados en el infobox de su página de jugador de
# Liquipedia (parámetro twitch=) el 2026-10-19, salvo los marcados DUDOSO (sin página en Liquipedia: se usa el nombre tal
# cual; si Twitch no lo conoce, Get Users no lo devuelve y el creador sale sin avatar).
STREAMERS_CREADORES = {
    "survivalist": "survivalistaoe2de",
    "hera": "hera",
    "sitaux": "sitaux",
    "st4rk": "st4rk_",
    "dragonstar": "dragonstar_aoe",     # página «The Dragonstar»
    "liereyy": "liereyy",
    "tatoh": "tatohaoe",
    "sebastian": "sebastian2002",
    "morleygames": "morleygames",       # DUDOSO
    "daut": "daut",
    "ciskhan": "ciskhan_",
    "red_phosphorus": "red_phosphorus",  # DUDOSO
    "ganji": "ganji__",
}


def twitch_login(v):
    """Login de Twitch de una URL (https://www.twitch.tv/<login>[/…]) o de un login suelto; None si no lo parece."""
    import re, urllib.parse
    v = (v or "").strip()
    if "/" in v:
        try:
            u = urllib.parse.urlsplit(v)
        except ValueError:
            return None
        if (u.hostname or "").lower() not in ("twitch.tv", "www.twitch.tv", "m.twitch.tv"):
            return None
        v = u.path.strip("/").split("/")[0]
    v = v.lower()
    return v if re.fullmatch(r"[a-z0-9_]{3,25}", v) else None


def streamers_logins(creadores, en_directo, partidos_json, torneos_json, previo):
    """Logins a pedir, en orden de prioridad y sin repetir (tope TWITCH_MAX_LOGINS): creadores, top de directos, streams de
    partidos.json, enlaces.twitch de torneos.json y, si queda sitio, los del streamers.json anterior (para refrescarlos)."""
    out = []

    def poner(v):
        login = twitch_login(v)
        if login and login not in out and len(out) < TWITCH_MAX_LOGINS:
            out.append(login)

    for v in creadores.values():
        poner(v)
    for v in en_directo:
        poner(v)
    for p in (partidos_json or {}).get("partidos", []):
        poner(p.get("stream") if "twitch.tv/" in (p.get("stream") or "") else None)
    for t in (torneos_json or {}).get("torneos", []):
        poner((t.get("enlaces") or {}).get("twitch"))
    for v in ((previo or {}).get("canales") or {}):
        poner(v)
    return out


def streamers_componer(usuarios, creadores):
    """Respuesta «data» de Get Users → ({login: {"nombre","avatar_url","url"}}, {creador: login} de los que existen).
    Solo avatares https de static-cdn.jtvnw.net (si no, el canal no sale)."""
    import urllib.parse
    canales = {}
    for u in usuarios or []:
        login = twitch_login(u.get("login"))
        avatar = u.get("profile_image_url") or ""
        try:
            host = urllib.parse.urlsplit(avatar).hostname
        except ValueError:
            host = None
        if not login or not url_https_ok(avatar) or host != TWITCH_HOST_AVATAR:
            continue
        nombre = " ".join(str(u.get("display_name") or "").split())[:40] or login
        canales[login] = {"nombre": nombre, "avatar_url": avatar, "url": f"https://twitch.tv/{login}"}
    return dict(sorted(canales.items())), {c: l for c, l in creadores.items() if l in canales}


def streamers_salida(canales, creadores, en_directo):
    return {"v": 1, "generado": ahora(),
            "fuente": "Twitch (imagen de perfil pública, solo para dar crédito y enlazar al canal)",
            "canales": canales, "creadores": creadores, "en_directo": [l for l in en_directo if l in canales]}


def _twitch(url, cabeceras=None, datos=None, timeout=30):
    req = urllib.request.Request(url, data=datos, headers=dict({"User-Agent": UA, "Accept": "application/json"},
                                                               **(cabeceras or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def streamers():
    """streamers.json (esquema en la cabecera, normas arriba). Sin credenciales: ::notice y nada. Si Twitch falla o no sale
    ningún canal, se conserva el streamers.json anterior (rama data) con ::warning::."""
    import urllib.parse
    cid, secreto = os.environ.get("TWITCH_CLIENT_ID", "").strip(), os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
    if not cid or not secreto:
        print("::notice title=streamers::sin TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET: se salta (se conserva el streamers.json anterior)",
              flush=True)
        return
    previo = leer_json("streamers.json", None)
    try:
        tok = _twitch(TWITCH_TOKEN_URL, datos=urllib.parse.urlencode(
            {"client_id": cid, "client_secret": secreto, "grant_type": "client_credentials"}).encode())
        cab = {"Client-Id": cid, "Authorization": "Bearer " + tok["access_token"]}
        en_directo = []
        try:
            juegos = _twitch(TWITCH_HELIX + "games?" + urllib.parse.urlencode([("name", n) for n in TWITCH_JUEGOS]), cab)
            ids = [g["id"] for g in juegos.get("data", []) if g.get("id")]
            log(f"streamers: categorías de Twitch: {[(g.get('id'), g.get('name')) for g in juegos.get('data', [])]}")
            if ids:
                st = _twitch(TWITCH_HELIX + "streams?" + urllib.parse.urlencode(
                    [("game_id", i) for i in ids] + [("first", TWITCH_TOP_DIRECTOS), ("type", "live")]), cab)
                en_directo = [s.get("user_login") for s in sorted(st.get("data", []), key=lambda s: -(s.get("viewer_count") or 0))]
                en_directo = [l for l in (twitch_login(x) for x in en_directo) if l]
        except Exception as ex:
            log(f"streamers: sin top de directos ({ex!r})")
        logins = streamers_logins(STREAMERS_CREADORES, en_directo, leer_json("partidos.json", None),
                                  leer_json("torneos.json", None), previo)
        us = _twitch(TWITCH_HELIX + "users?" + urllib.parse.urlencode([("login", l) for l in logins]), cab)
        canales, creadores = streamers_componer(us.get("data", []), STREAMERS_CREADORES)
        if not canales:
            raise RuntimeError(f"Get Users no devolvió ningún canal válido de {len(logins)} logins")
    except Exception as ex:
        # el mensaje nunca lleva el secreto ni el token (urllib no los pone en sus excepciones)
        print(f"::warning title=streamers::Twitch no respondió bien ({type(ex).__name__}: {ex}): se conserva el streamers.json anterior",
              flush=True)
        return
    escribir_json("streamers.json", streamers_salida(canales, creadores, en_directo))
    faltan = sorted(set(STREAMERS_CREADORES) - set(creadores))
    log(f"streamers: {len(canales)} canales de {len(logins)} logins; {len(en_directo)} en directo; creadores sin canal: {faltan}")


def streamers_probar():
    """Prueba sin red: respuestas Helix de ejemplo (inventadas, con la forma real de Get Streams y Get Users)."""
    m = leer_json(STREAMERS_MUESTRA)
    fallos = []
    en_directo = [twitch_login(s["user_login"]) for s in m["streams"]["data"]]
    logins = streamers_logins(m["creadores"], en_directo, m["partidos"], m["torneos"], m["previo"])
    if logins != m["esperado_logins"]:
        fallos.append(f"logins {logins}, se esperaba {m['esperado_logins']}")
    canales, creadores = streamers_componer(m["users"]["data"], m["creadores"])
    if canales != m["esperado_canales"]:
        fallos.append(f"canales {json.dumps(canales, ensure_ascii=False)}")
    if creadores != m["esperado_creadores"]:
        fallos.append(f"creadores {creadores}, se esperaba {m['esperado_creadores']}")
    many = streamers_logins({f"c{i}": f"canal_{i:03d}" for i in range(150)}, [], None, None, None)
    if len(many) != TWITCH_MAX_LOGINS:
        fallos.append(f"tope de logins: {len(many)}")
    for v, esp in {"https://www.twitch.tv/Hera": "hera", "https://twitch.tv/daut/videos": "daut", "st4rk_": "st4rk_",
                   "https://www.youtube.com/@hera": None, "https://evil.com/twitch.tv/x": None, "a b": None, "": None,
                   "javascript:alert(1)": None}.items():
        if twitch_login(v) != esp:
            fallos.append(f"twitch_login({v!r}) = {twitch_login(v)!r}, se esperaba {esp!r}")
    sal = streamers_salida(canales, creadores, en_directo)
    if set(sal) != {"v", "generado", "fuente", "canales", "creadores", "en_directo"} or sal["v"] != 1:
        fallos.append(f"salida: claves {sorted(sal)}")
    for f in fallos:
        log("FALLO", f)
    log(f"streamers --probar: {len(canales)} canales, {len(fallos)} fallos")
    return not fallos


if __name__ == "__main__":
    if "--probar" in sys.argv:          # sin red: torneos, noticias y partidos (o solo los nombrados: --probar noticias)
        pruebas = {"torneos": torneos_probar, "logos": logos_probar, "detalle": detalle_probar, "noticias": noticias_probar, "partidos": partidos_probar,
                   "streamers": streamers_probar}
        pedidas = [a for a in sys.argv[1:] if a in pruebas] or list(pruebas)
        resultados = [pruebas[a]() for a in pedidas]
        sys.exit(0 if all(resultados) else 1)
    pasos = (("ladder", ladder), ("civstats", civstats), ("mapas", mapas), ("torneos", torneos), ("detalle", detalle),
             ("noticias", noticias), ("partidos", partidos), ("streamers", streamers), ("perfiles", perfiles))
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
