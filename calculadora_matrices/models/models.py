# models.py

import math

from pydantic import BaseModel, Field, field_validator

# Límites de entrada: sin ellos un solo POST puede agotar CPU o memoria (DoS)
MAX_DIM = 50            # filas y columnas máximas por matriz
MAX_CADENA = 10         # matrices máximas en multiplicar-cadena
MAX_VALOR = 1e12        # |x| máximo: evita inf/NaN al multiplicar
MAX_NOMBRE = 60


def validar_matriz(v: list[list[float]]) -> list[list[float]]:
    """Rectangular, no vacía, de tamaño acotado y con números finitos."""
    if not v or not v[0]:
        raise ValueError("la matriz no puede estar vacía")
    if len(v) > MAX_DIM or len(v[0]) > MAX_DIM:
        raise ValueError(f"la matriz no puede superar {MAX_DIM}x{MAX_DIM}")
    if len({len(fila) for fila in v}) != 1:
        raise ValueError("todas las filas deben tener el mismo largo")
    for fila in v:
        for x in fila:
            if not math.isfinite(x) or abs(x) > MAX_VALOR:
                raise ValueError(f"los valores deben ser finitos y de magnitud <= {MAX_VALOR:g}")
    return v


class MatrixCreate(BaseModel):
    nombre: str = Field(max_length=MAX_NOMBRE)
    datos: list[list[float]]

    @field_validator("datos")
    @classmethod
    def datos_validos(cls, v):
        return validar_matriz(v)

class MatrixOut(MatrixCreate):
    id: int

# Modelos para operaciones sin estado (las matrices viajan en el body, no se guardan)

class DosMatrices(BaseModel):
    m1: list[list[float]]
    m2: list[list[float]]

    @field_validator("m1", "m2")
    @classmethod
    def matriz_valida(cls, v):
        return validar_matriz(v)

class UnaMatriz(BaseModel):
    m: list[list[float]]

    @field_validator("m")
    @classmethod
    def matriz_valida(cls, v):
        return validar_matriz(v)

# Rangos de la transformación 3D (finitos y acotados)
_traslacion = Field(0.0, ge=-1e6, le=1e6, allow_inf_nan=False)
_angulo = Field(0.0, ge=-1e6, le=1e6, allow_inf_nan=False)

class Transformacion(BaseModel):
    tx: float = _traslacion
    ty: float = _traslacion
    tz: float = _traslacion
    rx: float = _angulo  # grados
    ry: float = _angulo
    rz: float = _angulo
    escala: float = Field(1.0, ge=-1e6, le=1e6, allow_inf_nan=False)

class CadenaMatrices(BaseModel):
    matrices: list[list[list[float]]]
    transponer: bool = False

    @field_validator("matrices")
    @classmethod
    def cadena_valida(cls, v):
        if not v:
            raise ValueError("se requiere al menos una matriz")
        if len(v) > MAX_CADENA:
            raise ValueError(f"la cadena no puede tener más de {MAX_CADENA} matrices")
        for m in v:
            validar_matriz(m)
        return v


# Morph dona -> taza
MAX_RESOLUCION = 100    # resolucion² puntos: 100 -> 10.000 vértices, máximo por petición
MIN_RESOLUCION = 4


class Morph(BaseModel):
    t: float = Field(ge=0, le=1, allow_inf_nan=False, description="0 = dona, 1 = taza")
    resolucion: int = Field(30, ge=MIN_RESOLUCION, le=MAX_RESOLUCION,
                            description="Puntos por lado; la malla tiene resolucion² vértices")


class FiguraCreate(Morph):
    # Solo letras, números, espacio, punto, guion y guion bajo: el nombre se muestra en el
    # visor y puede llegar a un agente, así que no se admiten símbolos de marcado.
    nombre: str = Field(min_length=1, max_length=MAX_NOMBRE, pattern=r"^[\w .\-]+$")
