from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException
from models.models import MatrixCreate
from repository.repository import MatrixRepository
from services import services

app = FastAPI()

repo = MatrixRepository()

@app.get("/")
def home():
    return FileResponse("./web/index.html")

@app.post("/matrices")
def crear_matriz(payload: MatrixCreate):
    return repo.crear(payload.model_dump())

@app.post("/operaciones/sumar")
def sumar_matrices(id1: int, id2: int): 
    m1, m2 = repo.obtener(id1), repo.obtener(id2)     
    if not m1 or not m2:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.sumar(m1["datos"], m2["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.post("/operaciones/multiplicar")
def multiplicar_matrices(id1: int, id2: int): 
    m1, m2 = repo.obtener(id1), repo.obtener(id2)     
    if not m1 or not m2:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.multiplicar(m1["datos"], m2["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.post("/operaciones/transponer")
def transponer_matriz(id: int): 
    m = repo.obtener(id)     
    if not m:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.transponer(m["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.post("/operaciones/determinante")
def determinante_matriz(id: int): 
    m = repo.obtener(id)     
    if not m:         
        raise HTTPException(404, "matriz no encontrada")     
    try:         
        return {"resultado": services.determinante(m["datos"])} 
    except ValueError as e:         
        raise HTTPException(400, str(e))

@app.get("/matrices")
def listar_matrices():
    return repo.listar()

    