import csv
import json
import math
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError


# URL del microservicio calculadora_matrices.
# En Docker Compose se resuelve por nombre de servicio (http://calculadora:8000);
# corriendo local sin Docker, la calculadora está expuesta en el puerto 8001.
CALC_URL = os.getenv("CALC_URL", "http://localhost:8001")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Un único cliente HTTP reutilizado (mantiene conexiones abiertas entre frames)
    app.state.calc = httpx.AsyncClient(base_url=CALC_URL, timeout=2.0)
    yield
    await app.state.calc.aclose()


# Swagger/OpenAPI solo cuando se pide (ENABLE_DOCS=1)
DOCS = os.getenv("ENABLE_DOCS") == "1"
app = FastAPI(
    title="3D Model & Matrix Transformation API",
    lifespan=lifespan,
    docs_url="/docs" if DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DOCS else None,
)

# Orígenes de confianza: los únicos que pueden leer la API desde un navegador
# y abrir el WebSocket. Con "*" + credenciales cualquier web podía usar el visor.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=[],
)

HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+(:\d{1,5})?$")


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    resp = await call_next(request)
    host = request.headers.get("host", "")
    host = host if HOST_RE.match(host) else "localhost:8000"
    # todo se sirve del mismo origen (three.js incluido); el WebSocket solo al mismo host
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        f"style-src 'self'; img-src 'self' data:; connect-src 'self' ws://{host} wss://{host}; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Cache-Control"] = "no-store"
    if os.getenv("ENABLE_HSTS") == "1":  # solo tiene sentido detrás de HTTPS
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


app.mount("/static", StaticFiles(directory="static"), name="static")


# Ruta al archivo CSV con las coordenadas (debe estar en el mismo directorio o volumen Docker)
CSV_FILE_PATH = Path("modelo_3d.csv")


def cargar_puntos_csv(path: Path) -> list[list[float]]:
    """Lee un archivo CSV con encabezados x,y,z y retorna una lista de vertices [[x, y, z], ...]."""
    puntos = []
    if not path.exists():
        print(f"Advertencia: No se encontró el archivo {path}")
        return puntos

    with open(path, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                puntos.append([
                    float(row["x"]),
                    float(row["y"]),
                    float(row["z"])
                ])
            except (KeyError, ValueError) as e:
                # Omitir filas mal formadas o vacías
                continue
    return puntos


# ---------------------------------------------------------------------------
# Figuras geométricas: todas con la misma cantidad de puntos que el CSV (10.000)
# ---------------------------------------------------------------------------

N_PUNTOS = 10000
RADIO_ESFERA = 6.0
MEDIO_LADO_CUBO = 5.0


def generar_esfera(n: int, r: float) -> list[list[float]]:
    """Esfera de Fibonacci: n puntos distribuidos uniformemente sobre la superficie.
    Cada punto i baja en 'y' de forma pareja y gira el ángulo áureo alrededor del eje Y."""
    angulo_aureo = math.pi * (3 - math.sqrt(5))
    puntos = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n          # de 1 a -1
        radio_y = math.sqrt(1 - y * y)     # radio del círculo a esa altura
        phi = i * angulo_aureo
        puntos.append([r * radio_y * math.cos(phi), r * y, r * radio_y * math.sin(phi)])
    return puntos


def generar_cubo(n: int, l: float) -> list[list[float]]:
    """n puntos sobre las 6 caras de un cubo de lado 2l, repartidos en forma pareja
    con la secuencia de baja discrepancia R2 (sin aleatoriedad, siempre el mismo resultado)."""
    g = 1.32471795724474602596  # número plástico
    a1, a2 = 1 / g, 1 / (g * g)
    puntos = []
    for i in range(n):
        cara, k = i % 6, i // 6
        eje, signo = cara // 2, (1 if cara % 2 == 0 else -1)
        u = ((0.5 + a1 * k) % 1) * 2 - 1
        v = ((0.5 + a2 * k) % 1) * 2 - 1
        punto = [u * l, v * l]
        punto.insert(eje, signo * l)       # fija la coordenada del eje de la cara
        puntos.append(punto)
    return puntos


@lru_cache
def obtener_figura(nombre: str) -> list[list[float]] | None:
    if nombre == "esfera":
        return generar_esfera(N_PUNTOS, RADIO_ESFERA)
    if nombre == "cubo":
        return generar_cubo(N_PUNTOS, MEDIO_LADO_CUBO)
    if nombre == "toroide":
        return cargar_puntos_csv(CSV_FILE_PATH)
    return None


FIGURAS = ["esfera", "cubo", "toroide"]


async def pedir_transformacion(client: httpx.AsyncClient, parametros: dict) -> list[float]:
    """Reenvía los parámetros de movimiento a calculadora_matrices, que construye
    M = T · Rz · Ry · Rx · S y la devuelve en Column-Major (16 floats) para Three.js."""
    response = await client.post("/calc/transformacion", json=parametros)
    response.raise_for_status()
    return response.json()["column_major"]


async def pedir_morph(client: httpx.AsyncClient, t: float, resolucion: int) -> list[list[float]]:
    """La matemática del morph dona -> taza también vive en calculadora_matrices."""
    response = await client.post("/calc/morph", json={"t": t, "resolucion": resolucion})
    response.raise_for_status()
    return response.json()["vertices"]


async def pedir_guardar_figura(client: httpx.AsyncClient, sid: str, figura: dict) -> dict:
    """Guarda la figura en la calculadora a nombre de esta conexión (cookie de sesión propia)."""
    response = await client.post("/figuras", json=figura, headers={"Cookie": f"sid={sid}"})
    response.raise_for_status()
    return response.json()


@app.get("/")
def read_root():
    """Endpoint raíz para verificar disponibilidad del servicio."""
    return {
        "status": "online",
        "message": "API de Modelo 3D activa (las matrices las calcula calculadora_matrices)",
        "endpoints": {
            "figuras": "/api/figuras",
            "figura": "/api/figura/{nombre}",
            "csv_model": "/api/modelo-csv",
            "websocket": "/ws/transform (matriz, {morph}, {guardar})",
            "viewer": "/view"
        }
    }


@app.get("/api/modelo-csv")
def obtener_puntos_modelo():
    """Devuelve los vértices 3D parseados desde el archivo CSV."""
    puntos = cargar_puntos_csv(CSV_FILE_PATH)
    return {
        "total_puntos": len(puntos),
        "vertices": puntos
    }


@app.get("/api/figuras")
def listar_figuras():
    return {"figuras": FIGURAS, "puntos_por_figura": N_PUNTOS}


@app.get("/api/figura/{nombre}")
def obtener_puntos_figura(nombre: str):
    """Devuelve los vértices de una figura: esfera, cubo o toroide."""
    puntos = obtener_figura(nombre)
    if puntos is None:
        raise HTTPException(404, f"figura desconocida. Opciones: {', '.join(FIGURAS)}")
    return {
        "figura": nombre,
        "total_puntos": len(puntos),
        "vertices": puntos
    }


MAX_CONEXIONES_WS = 20
MAX_MENSAJES_POR_SEG = 200
MAX_BYTES_MENSAJE = 1024
MAX_MORPH_POR_SEG = 20      # cada morph calcula hasta 10.000 vértices: se limita aparte
conexiones_ws = 0


class Parametros(BaseModel):
    """Lo único que el visor puede pedir: números finitos y acotados."""
    tx: float = Field(0.0, ge=-1000, le=1000, allow_inf_nan=False)
    ty: float = Field(0.0, ge=-1000, le=1000, allow_inf_nan=False)
    tz: float = Field(0.0, ge=-1000, le=1000, allow_inf_nan=False)
    rx: float = Field(0.0, ge=-1e6, le=1e6, allow_inf_nan=False)
    ry: float = Field(0.0, ge=-1e6, le=1e6, allow_inf_nan=False)
    rz: float = Field(0.0, ge=-1e6, le=1e6, allow_inf_nan=False)
    escala: float = Field(1.0, ge=-100, le=100, allow_inf_nan=False)


NOMBRE_RE = r"^[\w .\-]+$"


class MorphPedido(BaseModel):
    t: float = Field(ge=0, le=1, allow_inf_nan=False)
    resolucion: int = Field(30, ge=4, le=100)


class GuardarPedido(MorphPedido):
    nombre: str = Field(min_length=1, max_length=60, pattern=NOMBRE_RE)


async def atender_mensaje(datos: dict, client: httpx.AsyncClient, sid: str) -> dict:
    """Decide qué pedirle a la calculadora según el mensaje del visor y arma la respuesta."""
    if "morph" in datos:
        pedido = MorphPedido(**datos["morph"])
        vertices = await pedir_morph(client, pedido.t, pedido.resolucion)
        return {"status": "ok", "morph": {"t": pedido.t, "vertices": vertices}}
    if "guardar" in datos:
        pedido = GuardarPedido(**datos["guardar"])
        figura = await pedir_guardar_figura(client, sid, pedido.model_dump())
        return {"status": "ok", "guardada": {"id": figura["id"], "nombre": figura["nombre"]}}
    parametros = Parametros(**datos).model_dump()
    return {"status": "ok", "matrix": await pedir_transformacion(client, parametros)}


async def responder(
    texto: str, client: httpx.AsyncClient, sid: str, morphs: int
) -> tuple[dict, bool]:
    """Procesa un mensaje del visor. Devuelve (respuesta, si_fue_un_morph_o_guardado).
    Entrada no confiable: JSON inválido o fuera de rango responde error sin tumbar el canal."""
    try:
        datos = json.loads(texto)
        if not isinstance(datos, dict):
            raise ValueError("se esperaba un objeto JSON")
        costoso = "morph" in datos or "guardar" in datos
        if costoso and morphs >= MAX_MORPH_POR_SEG:
            return {"status": "error", "detail": "demasiadas peticiones de morph"}, False
        return await atender_mensaje(datos, client, sid), costoso
    except (ValueError, TypeError, ValidationError):
        return {"status": "error", "detail": "parámetros inválidos"}, False
    except httpx.HTTPError as e:
        # Si la calculadora no responde, avisamos al cliente sin cortar el WebSocket
        detalle = f"calculadora no disponible: {e.__class__.__name__}"
        return {"status": "error", "detail": detalle}, False


@app.websocket("/ws/transform")
async def websocket_transform(websocket: WebSocket):
    """Canal WebSocket: recibe parámetros de movimiento y devuelve la matriz 4x4 calculada por calculadora_matrices."""
    global conexiones_ws
    # El navegador SIEMPRE envía Origin; si no es uno de confianza, es una web ajena
    # intentando usar el visor desde el navegador de la víctima (Cross-Site WebSocket Hijacking).
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return
    if conexiones_ws >= MAX_CONEXIONES_WS:
        await websocket.close(code=1013)
        return

    await websocket.accept()
    conexiones_ws += 1
    sid = secrets.token_hex(16)  # las figuras guardadas pertenecen a esta conexión
    ventana, enviados, morphs = time.monotonic(), 0, 0
    try:
        while True:
            texto = await websocket.receive_text()

            ahora = time.monotonic()
            if ahora - ventana >= 1:
                ventana, enviados, morphs = ahora, 0, 0
            enviados += 1
            if enviados > MAX_MENSAJES_POR_SEG or len(texto) > MAX_BYTES_MENSAJE:
                await websocket.close(code=1008)
                return

            respuesta, costoso = await responder(texto, websocket.app.state.calc, sid, morphs)
            morphs += costoso
            await websocket.send_json(respuesta)
    except WebSocketDisconnect:
        print("Cliente WebSocket desconectado")
    finally:
        conexiones_ws -= 1


@app.get("/view", response_class=HTMLResponse)
def serve_viewer():
    """Servidor web directo para ver la interfaz 3D."""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
