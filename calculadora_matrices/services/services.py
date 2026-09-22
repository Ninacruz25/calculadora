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

