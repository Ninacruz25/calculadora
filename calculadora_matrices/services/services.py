import math


def sumar(m1: list[list[float]], m2: list[list[float]]) -> list[list[float]]:
    if not m1 or not m2 or not m1[0] or not m2[0]:
        raise ValueError("Las matrices no pueden estar vacías")
    
    filas1, cols1 = len(m1), len(m1[0])
    filas2, cols2 = len(m2), len(m2[0])
    
    if filas1 != filas2 or cols1 != cols2:
        raise ValueError(
            f"No se pueden sumar matrices de distintas dimensiones: ({filas1}x{cols1}) y ({filas2}x{cols2})"
        )
        
    return [[a + b for a, b in zip(fila1, fila2)] for fila1, fila2 in zip(m1, m2)]


def multiplicar(m1: list[list[float]], m2: list[list[float]]) -> list[list[float]]:
    if not m1 or not m2 or not m1[0] or not m2[0]:
        raise ValueError("Las matrices no pueden estar vacías")
    
    filas1, cols1 = len(m1), len(m1[0])
    filas2, cols2 = len(m2), len(m2[0])
    
    if cols1 != filas2:
        raise ValueError(
            f"No se pueden multiplicar: las columnas de la 1ª matriz ({cols1}) "
            f"deben coincidir con las filas de la 2ª matriz ({filas2})"
        )
    
    return [
        [
            sum(m1[i][k] * m2[k][j] for k in range(cols1))
            for j in range(cols2)
        ]
        for i in range(filas1)
    ]


def transponer(m: list[list[float]]) -> list[list[float]]:
    if not m or not m[0]:
        raise ValueError("La matriz no puede estar vacía")
    
    filas, cols = len(m), len(m[0])
    return [[m[i][j] for i in range(filas)] for j in range(cols)]


def determinante(m: list[list[float]]) -> float:
    if not m or not m[0]:
        raise ValueError("La matriz no puede estar vacía")
    
    n = len(m)
    if any(len(fila) != n for fila in m):
        raise ValueError(
            f"La matriz debe ser cuadrada (nxn) para calcular el determinante. Dimensiones actuales: {n}x{len(m[0])}"
        )
    
    if n == 1:
        return float(m[0][0])
    if n == 2:
        return float(m[0][0] * m[1][1] - m[0][1] * m[1][0])
    
    # Eliminación Gaussiana con pivoteo parcial
    mat = [[float(val) for val in fila] for fila in m]
    det = 1.0
    
    for i in range(n):
        max_row = i
        for k in range(i + 1, n):
            if abs(mat[k][i]) > abs(mat[max_row][i]):
                max_row = k
                
        if abs(mat[max_row][i]) < 1e-12:
            return 0.0
        
        if max_row != i:
            mat[i], mat[max_row] = mat[max_row], mat[i]
            det *= -1.0
            
        pivot = mat[i][i]
        det *= pivot
        
        for k in range(i + 1, n):
            factor = mat[k][i] / pivot
            for j in range(i + 1, n):
                mat[k][j] -= factor * mat[i][j]
                
    # Redondear si está muy cerca de un entero para evitar errores de precisión de punto flotante
    return round(det, 6) if abs(det - round(det)) < 1e-9 else round(det, 4)



# ---------------------------------------------------------------------------
# Transformaciones 3D con matrices homogéneas 4x4
# ---------------------------------------------------------------------------

def rotacion_x(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [1, 0, 0, 0],
        [0, math.cos(a), -math.sin(a), 0],
        [0, math.sin(a), math.cos(a), 0],
        [0, 0, 0, 1]
    ]


def rotacion_y(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [math.cos(a), 0, math.sin(a), 0],
        [0, 1, 0, 0],
        [-math.sin(a), 0, math.cos(a), 0],
        [0, 0, 0, 1]
    ]


def rotacion_z(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [math.cos(a), -math.sin(a), 0, 0],
        [math.sin(a), math.cos(a), 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ]


def traslacion(tx: float, ty: float, tz: float) -> list[list[float]]:
    return [
        [1, 0, 0, tx],
        [0, 1, 0, ty],
        [0, 0, 1, tz],
        [0, 0, 0, 1]
    ]


def escalado(s: float) -> list[list[float]]:
    return [
        [s, 0, 0, 0],
        [0, s, 0, 0],
        [0, 0, s, 0],
        [0, 0, 0, 1]
    ]


def transformacion(tx: float, ty: float, tz: float, rx: float, ry: float, rz: float, s: float = 1.0) -> list[list[float]]:
    """Matriz compuesta M = T · Rz · Ry · Rx · S (primero escala, luego rota X, Y, Z y al final traslada)."""
    M = traslacion(tx, ty, tz)
    for m in (rotacion_z(rz), rotacion_y(ry), rotacion_x(rx), escalado(s)):
        M = multiplicar(M, m)
    return M


def column_major(m: list[list[float]]) -> list[float]:
    """Aplana la matriz columna por columna (formato de OpenGL / Three.js) = transpuesta leída por filas."""
    return [valor for fila in transponer(m) for valor in fila]


# ---------------------------------------------------------------------------
# Morph dona -> taza
# Ambas superficies usan el MISMO dominio (u, v) en [0, 2π)², así que sus mallas tienen
# exactamente los mismos vértices y la interpolación punto a punto P(t) = (1-t)·dona + t·taza
# tiene sentido. Los vértices se corresponden por índice (i, j); la taza se arma por partes
# (cuerpo + asa), así que la unión cuerpo/asa NO es continua: es una aproximación visual.
# ---------------------------------------------------------------------------

DONA_RADIO_ANILLO = 2.0   # distancia del centro al tubo
DONA_RADIO_TUBO = 0.7
def punto_dona(u: float, v: float) -> list[float]:
    """Toro: circunferencia de radio R en el plano XY con tubo circular de radio r."""
    R, r = DONA_RADIO_ANILLO, DONA_RADIO_TUBO
    nx, ny = math.cos(u), math.sin(u)          # normal exterior del anillo
    radio = r * math.cos(v)
    return [R * nx + radio * nx, R * ny + radio * ny, r * math.sin(v)]


# Taza: cuerpo de revolución HUECO (fondo, pared exterior, borde, pared interior, piso interior)
# y asa tubular pegada al costado. Los vértices se reparten así sobre el mismo dominio (u, v):
#   u en [0, FRACCION_ASA·2π)  -> asa   (u recorre el asa, v la sección del tubo)
#   u en el resto              -> cuerpo (u recorre el perfil de la pared, v el giro del eje)
TAZA_X0 = -0.7            # eje de la taza (centra el conjunto taza + asa)
TAZA_ALTO = 3.2
TAZA_R_BASE = 1.35        # radio exterior abajo y en la boca: leve conicidad
TAZA_R_BOCA = 1.55
TAZA_PARED = 0.25
TAZA_FONDO = 0.3
TAZA_FRACCION_ASA = 0.22
ASA_RADIO_TUBO = 0.2
ASA_SEMIALTO = 0.9        # el asa nace a +/- esta altura del costado de la taza
ASA_SALIDA = 1.2          # cuánto sobresale del cuerpo


def _perfil_taza() -> list[tuple[float, float]]:
    """Medio corte de la taza como (radio, altura): centro del fondo -> exterior abajo -> borde
    exterior -> borde interior -> piso interior -> centro del piso."""
    h = TAZA_ALTO / 2
    return [
        (0.0, -h), (TAZA_R_BASE, -h), (TAZA_R_BOCA, h),
        (TAZA_R_BOCA - TAZA_PARED, h),
        (TAZA_R_BASE - TAZA_PARED, -h + TAZA_FONDO), (0.0, -h + TAZA_FONDO),
    ]


_PERFIL = _perfil_taza()
_TRAMOS = [math.dist(p, q) for p, q in zip(_PERFIL, _PERFIL[1:], strict=False)]
_LARGO_PERFIL = sum(_TRAMOS)


def _punto_en_perfil(s: float) -> tuple[float, float]:
    """Punto del perfil a la fracción s (0..1) de su longitud."""
    restante = s * _LARGO_PERFIL
    for (p, q), largo in zip(zip(_PERFIL, _PERFIL[1:], strict=False), _TRAMOS, strict=True):
        if restante <= largo:
            f = restante / largo
            return p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])
        restante -= largo
    return _PERFIL[-1]


def _punto_cuerpo(s: float, v: float) -> list[float]:
    s = 0.005 + 0.99 * s       # evita que todo un giro colapse en el centro del fondo
    radio, y = _punto_en_perfil(s)
    return [TAZA_X0 + radio * math.cos(v), y, radio * math.sin(v)]


def _punto_asa(s: float, v: float) -> list[float]:
    """Tubo que sigue media elipse desde el costado de la taza (arriba) hasta el costado (abajo)."""
    a, b = ASA_SALIDA, ASA_SEMIALTO
    theta = math.pi / 2 - math.pi * s
    nx, ny = b * math.cos(theta), a * math.sin(theta)    # normal exterior de la elipse
    norma = math.hypot(nx, ny)
    nx, ny = nx / norma, ny / norma
    cx = TAZA_X0 + (TAZA_R_BASE + TAZA_R_BOCA) / 2 - 0.1 + a * math.cos(theta)
    cy = b * math.sin(theta)
    radio = ASA_RADIO_TUBO * math.cos(v)
    return [cx + radio * nx, cy + radio * ny, ASA_RADIO_TUBO * math.sin(v)]


def punto_taza(u: float, v: float) -> list[float]:
    """Taza con cavidad hueca y asa lateral, sobre el mismo dominio (u, v) que la dona."""
    u_asa = TAZA_FRACCION_ASA * 2 * math.pi
    if u < u_asa:
        return _punto_asa(u / u_asa, v)
    return _punto_cuerpo((u - u_asa) / (2 * math.pi - u_asa), v)


def morph(t: float, resolucion: int) -> list[list[float]]:
    """Vértices de la figura intermedia entre dona (t=0) y taza (t=1).
    Devuelve resolucion² puntos. No guarda nada: misma entrada, misma salida."""
    paso = 2 * math.pi / resolucion
    puntos = []
    for i in range(resolucion):
        for j in range(resolucion):
            u, v = i * paso, j * paso
            d, c = punto_dona(u, v), punto_taza(u, v)
            puntos.append([round((1 - t) * x0 + t * x1, 6) for x0, x1 in zip(d, c, strict=True)])
    return puntos
