MAX_MATRICES_POR_DUENO = 100
MAX_MATRICES_TOTAL = 10000


class LimiteExcedido(Exception):
    pass


class MatrixRepository:
    """Almacén en memoria. Cada matriz pertenece a un dueño (sesión): nadie ve las de otro."""

    def __init__(self):
        self._data: dict[int, dict] = {}
        self._dueno: dict[int, str] = {}
        self._next_id = 1

    def crear(self, dueno: str, matriz: dict) -> dict:
        if len(self._data) >= MAX_MATRICES_TOTAL:
            raise LimiteExcedido("servicio saturado")
        if sum(1 for d in self._dueno.values() if d == dueno) >= MAX_MATRICES_POR_DUENO:
            raise LimiteExcedido(f"máximo {MAX_MATRICES_POR_DUENO} matrices por sesión")
        matriz["id"] = self._next_id
        self._data[self._next_id] = matriz
        self._dueno[self._next_id] = dueno
        self._next_id += 1
        return matriz

    def obtener(self, dueno: str, id: int) -> dict | None:
        # Una matriz ajena responde igual que una inexistente (no revela que existe)
        if self._dueno.get(id) != dueno:
            return None
        return self._data.get(id)

    def listar(self, dueno: str) -> list[dict]:
        return [m for i, m in self._data.items() if self._dueno[i] == dueno]


class FiguraRepository:
    """Figuras guardadas (nombre + parámetros del morph) por dueño. Guardar es idempotente:
    repetir el mismo nombre actualiza la figura en vez de duplicarla."""

    def __init__(self):
        self._por_dueno: dict[str, dict[str, dict]] = {}
        self._next_id = 1

    def guardar(self, dueno: str, figura: dict) -> dict:
        propias = self._por_dueno.setdefault(dueno, {})
        existente = propias.get(figura["nombre"])
        if existente is None:
            if sum(len(f) for f in self._por_dueno.values()) >= MAX_MATRICES_TOTAL:
                raise LimiteExcedido("servicio saturado")
            if len(propias) >= MAX_MATRICES_POR_DUENO:
                raise LimiteExcedido(f"máximo {MAX_MATRICES_POR_DUENO} figuras por sesión")
            figura = {**figura, "id": self._next_id}
            self._next_id += 1
        else:
            figura = {**figura, "id": existente["id"]}
        propias[figura["nombre"]] = figura
        return figura

    def listar(self, dueno: str) -> list[dict]:
        return list(self._por_dueno.get(dueno, {}).values())
