"""Relevo del visor (modelo-3D) hacia la calculadora, con una calculadora falsa: sin Docker.

Comprueba que el visor NO calcula (solo reenvía), que valida lo que recibe y que se defiende
de abusos (ráfagas, orígenes ajenos, nombres con HTML)."""
import importlib.util
import json
import os
import re
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

VISOR_DIR = Path(__file__).resolve().parents[1] / "modelo-3D"
SID_RE = re.compile(r"^[0-9a-f]{32}$")


class CalculadoraFalsa:
    """Responde valores reconocibles (todo ceros): si el visor calculara solo, se notaría."""

    def __init__(self):
        self.pedidos: list[httpx.Request] = []
        self.caida = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.caida:
            raise httpx.ConnectError("calculadora caída", request=request)
        self.pedidos.append(request)
        cuerpo = json.loads(request.content)
        if request.url.path == "/calc/morph":
            ceros = [[0.0, 0.0, 0.0]] * cuerpo["resolucion"] ** 2
            return httpx.Response(200, json={"vertices": ceros})
        if request.url.path == "/figuras":
            return httpx.Response(200, json={**cuerpo, "id": 7})
        if request.url.path == "/calc/transformacion":
            return httpx.Response(200, json={"column_major": [1.0] * 16})
        return httpx.Response(404)

    def a(self, ruta: str) -> list[httpx.Request]:
        return [p for p in self.pedidos if p.url.path == ruta]


@pytest.fixture(scope="module")
def visor():
    anterior = os.getcwd()
    os.chdir(VISOR_DIR)  # el visor sirve ./static y ./index.html relativos a su carpeta
    try:
        spec = importlib.util.spec_from_file_location("visor_main", VISOR_DIR / "main.py")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        os.chdir(anterior)


@pytest.fixture
def entorno(visor):
    falsa = CalculadoraFalsa()
    with TestClient(visor.app) as cliente:
        visor.app.state.calc = httpx.AsyncClient(
            transport=httpx.MockTransport(falsa), base_url="http://calculadora")
        yield cliente, falsa


def enviar(ws, mensaje) -> dict:
    ws.send_text(mensaje if isinstance(mensaje, str) else json.dumps(mensaje))
    return ws.receive_json()


def test_morph_se_delega_a_la_calculadora(entorno):
    cliente, calc = entorno
    with cliente.websocket_connect("/ws/transform") as ws:
        r = enviar(ws, {"morph": {"t": 0.5, "resolucion": 5}})
    assert r["status"] == "ok" and len(r["morph"]["vertices"]) == 25
    # todo ceros = lo que devolvió la calculadora falsa: el visor no calculó nada
    assert all(v == [0.0, 0.0, 0.0] for v in r["morph"]["vertices"])
    assert json.loads(calc.a("/calc/morph")[0].content) == {"t": 0.5, "resolucion": 5}


@pytest.mark.parametrize("mensaje", [
    {"morph": {"t": 2, "resolucion": 10}},
    {"morph": {"t": -1, "resolucion": 10}},
    {"morph": {"t": 0.5, "resolucion": 101}},
    {"morph": {"t": 0.5, "resolucion": 3}},
    {"morph": "texto"},
    {"morph": None},
    [1, 2, 3],
    "42",
    "no es json",
    '{"morph": {"t": NaN, "resolucion": 10}}',
])
def test_entradas_invalidas_no_llegan_a_la_calculadora_ni_tumban_el_canal(entorno, mensaje):
    cliente, calc = entorno
    with cliente.websocket_connect("/ws/transform") as ws:
        assert enviar(ws, mensaje) == {"status": "error", "detail": "parámetros inválidos"}
        # el canal sigue vivo
        assert enviar(ws, {"morph": {"t": 0, "resolucion": 4}})["status"] == "ok"
    assert len(calc.a("/calc/morph")) == 1


def test_guardar_usa_una_sesion_propia_por_conexion(entorno):
    cliente, calc = entorno
    guardar = {"guardar": {"nombre": "Mi taza", "t": 1, "resolucion": 10}}
    with cliente.websocket_connect("/ws/transform") as ws1:
        r = enviar(ws1, guardar)
    with cliente.websocket_connect("/ws/transform") as ws2:
        enviar(ws2, guardar)
    assert r == {"status": "ok", "guardada": {"id": 7, "nombre": "Mi taza"}}
    sids = [re.search(r"sid=(\w+)", p.headers["cookie"]).group(1) for p in calc.a("/figuras")]
    assert all(SID_RE.match(s) for s in sids) and sids[0] != sids[1]


@pytest.mark.parametrize("nombre", ["<img src=x onerror=alert(1)>", "{{7*7}}", "a" * 61, ""])
def test_nombre_peligroso_no_se_envia_a_guardar(entorno, nombre):
    cliente, calc = entorno
    with cliente.websocket_connect("/ws/transform") as ws:
        r = enviar(ws, {"guardar": {"nombre": nombre, "t": 1, "resolucion": 10}})
    assert r["status"] == "error"
    assert calc.a("/figuras") == []


def test_rafaga_de_morph_se_limita(entorno, visor, monkeypatch):
    cliente, calc = entorno
    monkeypatch.setattr(visor.time, "monotonic", lambda: 1000.0)  # misma ventana de 1 s
    with cliente.websocket_connect("/ws/transform") as ws:
        estados = [enviar(ws, {"morph": {"t": 0.1, "resolucion": 4}})["status"]
                   for _ in range(visor.MAX_MORPH_POR_SEG + 10)]
    assert estados.count("ok") == visor.MAX_MORPH_POR_SEG
    assert len(calc.a("/calc/morph")) == visor.MAX_MORPH_POR_SEG


def test_si_la_calculadora_cae_el_canal_sigue_vivo(entorno):
    cliente, calc = entorno
    with cliente.websocket_connect("/ws/transform") as ws:
        calc.caida = True
        r = enviar(ws, {"morph": {"t": 0.5, "resolucion": 4}})
        assert r["status"] == "error" and "calculadora no disponible" in r["detail"]
        calc.caida = False
        assert enviar(ws, {"morph": {"t": 0.5, "resolucion": 4}})["status"] == "ok"


def test_la_transformacion_de_siempre_sigue_funcionando(entorno):
    cliente, calc = entorno
    with cliente.websocket_connect("/ws/transform") as ws:
        r = enviar(ws, {"tx": 1, "ry": 90, "escala": 2})
    assert r == {"status": "ok", "matrix": [1.0] * 16}
    assert len(calc.a("/calc/transformacion")) == 1


def test_origen_ajeno_es_rechazado(entorno):
    cliente, _ = entorno
    with pytest.raises(WebSocketDisconnect) as e:
        with cliente.websocket_connect("/ws/transform", headers={"origin": "http://evil.example"}):
            pass
    assert e.value.code == 1008
