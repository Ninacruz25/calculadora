import os
import re
import secrets

from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from models.models import (MatrixCreate, DosMatrices, UnaMatriz, CadenaMatrices, Transformacion,
                           Morph, FiguraCreate)
from repository.repository import MatrixRepository, FiguraRepository, LimiteExcedido
from services import services

# Swagger/OpenAPI solo cuando se pide (ENABLE_DOCS=1): no exponer el mapa de la API por defecto
DOCS = os.getenv("ENABLE_DOCS") == "1"
app = FastAPI(
    docs_url="/docs" if DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DOCS else None,
)

repo = MatrixRepository()
figuras = FiguraRepository()

# CSP estricta para scripts; los estilos en línea (style="...") siguen permitidos.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
       "form-action 'self'; frame-ancestors 'none'")
SID_RE = re.compile(r"^[0-9a-f]{32}$")


@app.middleware("http")
async def sesion_y_cabeceras(request: Request, call_next):
    # Cada navegador recibe una sesión opaca; las matrices quedan atadas a ella
    sid = request.cookies.get("sid", "")
    nueva = not SID_RE.match(sid)
    if nueva:
        sid = secrets.token_hex(16)
    request.state.sid = sid
    resp = await call_next(request)
    if nueva:
        resp.set_cookie("sid", sid, httponly=True, samesite="strict",
                        secure=os.getenv("COOKIE_SECURE") == "1")
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Cache-Control"] = "no-store"
    if os.getenv("ENABLE_HSTS") == "1":  # solo tiene sentido detrás de HTTPS
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(RequestValidationError)
async def validacion(request: Request, exc: RequestValidationError):
    # Sin "input": el valor rechazado (p. ej. NaN) no se devuelve al cliente ni rompe el JSON
    return JSONResponse(
        {"detail": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]}, status_code=422)


app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.get("/")
def home():
    return FileResponse("./web/index.html")

@app.post("/matrices")
def crear_matriz(payload: MatrixCreate, request: Request):
    try:
        return repo.crear(request.state.sid, payload.model_dump())
    except LimiteExcedido as e:
        raise HTTPException(429, str(e))

@app.post("/operaciones/sumar")
def sumar_matrices(id1: int, id2: int, request: Request): 
    m1, m2 = repo.obtener(request.state.sid, id1), repo.obtener(request.state.sid, id2)     
    if not m1 or not m2:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.sumar(m1["datos"], m2["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.post("/operaciones/multiplicar")
def multiplicar_matrices(id1: int, id2: int, request: Request): 
    m1, m2 = repo.obtener(request.state.sid, id1), repo.obtener(request.state.sid, id2)     
    if not m1 or not m2:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.multiplicar(m1["datos"], m2["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.post("/operaciones/transponer")
def transponer_matriz(id: int, request: Request): 
    m = repo.obtener(request.state.sid, id)     
    if not m:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.transponer(m["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.post("/operaciones/determinante")
def determinante_matriz(id: int, request: Request): 
    m = repo.obtener(request.state.sid, id)     
    if not m:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.determinante(m["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.get("/matrices")
def listar_matrices(request: Request):
    return repo.listar(request.state.sid)

# Operaciones sin estado: reciben las matrices en el body y no las guardan.
# Pensadas para que otros servicios (p. ej. modelo-3D) consuman la calculadora.

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/calc/sumar")
def calc_sumar(p: DosMatrices):
    try:
        return {"resultado": services.sumar(p.m1, p.m2)}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/calc/multiplicar")
def calc_multiplicar(p: DosMatrices):
    try:
        return {"resultado": services.multiplicar(p.m1, p.m2)}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/calc/transponer")
def calc_transponer(p: UnaMatriz):
    try:
        return {"resultado": services.transponer(p.m)}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/calc/determinante")
def calc_determinante(p: UnaMatriz):
    try:
        return {"resultado": services.determinante(p.m)}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/calc/transformacion")
def calc_transformacion(p: Transformacion):
    """Construye M = T · Rz · Ry · Rx · S a partir de traslación, rotación (grados) y escala.
    Devuelve M por filas y aplanada en Column-Major (formato que usa Three.js)."""
    M = services.transformacion(p.tx, p.ty, p.tz, p.rx, p.ry, p.rz, p.escala)
    return {
        "resultado": M,
        "column_major": services.column_major(M)
    }

@app.post("/calc/multiplicar-cadena")
def calc_multiplicar_cadena(p: CadenaMatrices):
    """Calcula A @ B @ C ... en una sola llamada; opcionalmente transpone el resultado."""
    try:
        resultado = p.matrices[0]
        for m in p.matrices[1:]:
            resultado = services.multiplicar(resultado, m)
        if p.transponer:
            resultado = services.transponer(resultado)
        return {"resultado": resultado}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/calc/morph")
def calc_morph(p: Morph):
    """Vértices de la figura intermedia entre una dona (t=0) y una taza (t=1).
    Devuelve resolucion² puntos; no guarda estado."""
    vertices = services.morph(p.t, p.resolucion)
    return {"t": p.t, "total_puntos": len(vertices), "vertices": vertices}


@app.post("/figuras")
def guardar_figura(payload: FiguraCreate, request: Request):
    """Guarda una figura con nombre. Idempotente: el mismo nombre actualiza la anterior."""
    try:
        return figuras.guardar(request.state.sid, payload.model_dump())
    except LimiteExcedido as e:
        raise HTTPException(429, str(e)) from None


@app.get("/figuras")
def listar_figuras(request: Request):
    return figuras.listar(request.state.sid)
