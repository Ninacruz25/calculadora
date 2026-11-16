"""Pruebas del morph dona -> taza (servicio y API de la calculadora), sin Docker."""
import math

import pytest
from fastapi.testclient import TestClient

import main
from services import services

client = TestClient(main.app)


def plano(puntos):
    return [c for p in puntos for c in p]


# --- Matemática -----------------------------------------------------------

def test_t0_es_exactamente_la_dona():
    puntos = services.morph(0, 20)
    esperado = [services.punto_dona(i * 2 * math.pi / 20, j * 2 * math.pi / 20)
                for i in range(20) for j in range(20)]
    assert plano(puntos) == pytest.approx(plano(esperado), abs=1e-5)


def test_t1_es_exactamente_la_taza():
    puntos = services.morph(1, 20)
    esperado = [services.punto_taza(i * 2 * math.pi / 20, j * 2 * math.pi / 20)
                for i in range(20) for j in range(20)]
    assert plano(puntos) == pytest.approx(plano(esperado), abs=1e-5)


def test_punto_medio_es_el_promedio_de_dona_y_taza():
    dona, taza, medio = (services.morph(t, 12) for t in (0, 1, 0.5))
    for d, c, m in zip(dona, taza, medio, strict=True):
        esperado = [(a + b) / 2 for a, b in zip(d, c, strict=True)]
        assert m == pytest.approx(esperado, abs=1e-5)


@pytest.mark.parametrize("t", [0, 0.25, 0.5, 1])
@pytest.mark.parametrize("resolucion", [4, 7, 30])
def test_las_mallas_tienen_los_mismos_vertices_y_son_finitos(t, resolucion):
    puntos = services.morph(t, resolucion)
    assert len(puntos) == resolucion ** 2
    assert all(len(p) == 3 and all(math.isfinite(c) for c in p) for p in puntos)


def test_la_taza_no_es_la_dona():
    # Si ambas fórmulas coincidieran, el morph sería una animación vacía
    assert services.morph(0, 10) != services.morph(1, 10)


def _taza():
    return services.morph(1, 100)


def test_la_taza_tiene_cavidad_hueca():
    # Una taza es hueca: sobre el piso interior no hay material cerca del eje
    cerca_del_eje = [p for p in _taza()
                     if math.hypot(p[0] - services.TAZA_X0, p[2]) < 0.8
                     and -services.TAZA_ALTO / 2 + services.TAZA_FONDO + 0.05 < p[1]]
    assert cerca_del_eje == []


def test_la_taza_tiene_fondo_y_borde_a_la_altura_esperada():
    ys = [p[1] for p in _taza()]
    assert min(ys) == pytest.approx(-services.TAZA_ALTO / 2, abs=0.05)
    assert max(ys) == pytest.approx(services.TAZA_ALTO / 2, abs=0.05)


def test_la_taza_tiene_asa_fuera_del_cuerpo():
    x_max_cuerpo = services.TAZA_X0 + services.TAZA_R_BOCA
    asa = [p for p in _taza() if p[0] > x_max_cuerpo + 0.3]
    assert len(asa) > 500      # el asa lleva su parte de los vértices


def test_morph_es_determinista():
    assert services.morph(0.3, 15) == services.morph(0.3, 15)


# --- API ------------------------------------------------------------------

def test_endpoint_devuelve_resolucion_al_cuadrado_vertices():
    r = client.post("/calc/morph", json={"t": 0.5, "resolucion": 10})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total_puntos"] == 100 == len(cuerpo["vertices"])
    assert cuerpo["t"] == 0.5


@pytest.mark.parametrize("cuerpo", [
    {"t": -0.1, "resolucion": 10},
    {"t": 1.1, "resolucion": 10},
    {"t": 0.5, "resolucion": 101},     # tope: evita calcular millones de puntos
    {"t": 0.5, "resolucion": 3},
    {"t": 0.5, "resolucion": 1_000_000},
    {"t": "abc", "resolucion": 10},
    {"resolucion": 10},
])
def test_endpoint_rechaza_entradas_fuera_de_rango(cuerpo):
    assert client.post("/calc/morph", json=cuerpo).status_code == 422


def test_endpoint_rechaza_nan_e_infinito_en_el_cuerpo_crudo():
    for crudo in (b'{"t": NaN, "resolucion": 10}', b'{"t": Infinity, "resolucion": 10}'):
        r = client.post("/calc/morph", content=crudo, headers={"Content-Type": "application/json"})
        assert r.status_code == 422


def test_endpoint_resolucion_maxima_responde():
    r = client.post("/calc/morph", json={"t": 1, "resolucion": 100})
    assert r.status_code == 200 and r.json()["total_puntos"] == 10000


# --- Guardar figuras ------------------------------------------------------

def nuevo_cliente() -> TestClient:
    return TestClient(main.app)  # cookie jar propio = sesión propia


def test_guardar_figura_y_listarla():
    c = nuevo_cliente()
    r = c.post("/figuras", json={"nombre": "Mi taza", "t": 1, "resolucion": 30})
    assert r.status_code == 200
    assert [f["nombre"] for f in c.get("/figuras").json()] == ["Mi taza"]


def test_guardar_es_idempotente_por_nombre():
    c = nuevo_cliente()
    primera = c.post("/figuras", json={"nombre": "A", "t": 0.2, "resolucion": 30}).json()
    segunda = c.post("/figuras", json={"nombre": "A", "t": 0.9, "resolucion": 30}).json()
    assert primera["id"] == segunda["id"]
    guardadas = c.get("/figuras").json()
    assert len(guardadas) == 1 and guardadas[0]["t"] == 0.9


def test_las_figuras_son_privadas_por_sesion():
    a, b = nuevo_cliente(), nuevo_cliente()
    a.post("/figuras", json={"nombre": "secreta", "t": 0.5, "resolucion": 30})
    assert b.get("/figuras").json() == []


@pytest.mark.parametrize("nombre", [
    "<script>alert(1)</script>", "a/../../etc", "x" * 61, "", "nombre\ncon salto", "{{7*7}}",
])
def test_nombre_invalido_se_rechaza(nombre):
    r = nuevo_cliente().post("/figuras", json={"nombre": nombre, "t": 0.5, "resolucion": 30})
    assert r.status_code == 422


def test_limite_de_figuras_por_sesion():
    c = nuevo_cliente()
    def guardar(nombre: str) -> int:
        return c.post("/figuras", json={"nombre": nombre, "t": 0, "resolucion": 4}).status_code

    assert all(guardar(f"f{i}") == 200 for i in range(100))
    assert guardar("una-mas") == 429
    assert guardar("f0") == 200  # volver a guardar una existente es actualización
