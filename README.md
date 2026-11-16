# Calculadora de matrices + visor 3D

Dos servicios FastAPI orquestados con Docker Compose. El visor 3D **no calcula**:
delega la matemática a la calculadora y mueve el objeto con la matriz que ésta devuelve.

## Estructura

```
calculadora_matrices/   API de matrices (capas: main -> services -> repository) + UI web
modelo-3D/              Visor 3D (three.js servido localmente) y relevo por WebSocket
tests_unitarias/        Pruebas pytest sin Docker (morph dona→taza, figuras guardadas)
test_e2e/               Pruebas Playwright (humo, visor, morph, regresión de seguridad)
n8n/                    Workflows de n8n (docker-compose.n8n.yaml en la raíz)
evidencias/             Reportes y capturas de ZAP, Burp y OWASP
docs/                   Guías y reporte de evidencias
docker-compose.yaml     Levanta calculadora y visor
pyproject.toml          Configuración de Ruff y pytest
```

## Cómo levantarlo

```bash
docker compose up --build
```

| Servicio | URL |
|---|---|
| Calculadora | http://localhost:8001 (docs en `/docs`) |
| Visor 3D | http://localhost:8000/view |

Con n8n (http://localhost:5678):

```bash
docker compose -f docker-compose.yaml -f docker-compose.n8n.yaml up --build
```

## Morph dona → taza

La dona y la taza son superficies paramétricas sobre el **mismo dominio (u, v)**, así que sus mallas
tienen los mismos vértices y el morph es `P(t) = (1-t)·dona + t·taza`.

| Dónde | Qué |
|---|---|
| `POST /calc/morph` | `{t: 0..1, resolucion: 4..100}` -> `resolucion²` vértices (sin estado) |
| `POST /figuras`, `GET /figuras` | Guardar/listar figuras con nombre; guardar es idempotente por nombre |
| WebSocket `/ws/transform` | El visor envía `{morph: {...}}` o `{guardar: {...}}`; modelo-3D solo relaya a la calculadora |
| Visor -> "Dona → Taza" | Slider y etiqueta con el nombre de la figura |

## Calidad

```bash
pip install -r requirements-dev.txt
playwright install chromium   # solo para los E2E
ruff check .            # análisis estático (config en pyproject.toml)
pytest tests_unitarias  # sin Docker
pytest test_e2e         # E2E (requiere los servicios arriba)
```

## Seguridad

Los hallazgos de ZAP, Burp y la revisión manual, junto con sus mitigaciones, están en
`evidencias/`. Los puertos se publican solo en `127.0.0.1`.
