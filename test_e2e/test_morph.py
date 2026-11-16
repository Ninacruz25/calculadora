"""E2E del morph dona -> taza en el visor (requiere `docker compose up`)."""
from playwright.sync_api import Page, expect


def abrir_morph(page: Page, visor_url: str) -> None:
    page.goto(visor_url)
    expect(page.locator("#ws-status")).to_have_text("Conectado")
    page.locator("#figura").select_option("morph")
    expect(page.locator("#point-count")).to_have_text("10000")


def test_slider_lleva_de_dona_a_taza(page: Page, visor_url: str) -> None:
    abrir_morph(page, visor_url)
    expect(page.locator("#figura-etiqueta")).to_have_text("Dona")

    page.locator("#morph-t").fill("1")
    expect(page.locator("#figura-etiqueta")).to_have_text("Taza")
    expect(page.locator("#point-count")).to_have_text("10000")  # no se pierden puntos

    page.locator("#morph-t").fill("0.5")
    expect(page.locator("#figura-etiqueta")).to_have_text("Dona → Taza 50%")


def test_guardar_figura_muestra_su_nombre_como_texto(page: Page, visor_url: str) -> None:
    abrir_morph(page, visor_url)
    page.locator("#morph-t").fill("1")
    page.locator("#figura-nombre").fill("Taza de prueba")
    page.locator("#figura-guardar").click()
    expect(page.locator("#figura-etiqueta")).to_have_text("Taza de prueba")


def test_nombre_con_html_no_se_guarda(page: Page, visor_url: str) -> None:
    abrir_morph(page, visor_url)
    page.locator("#figura-nombre").fill("<img src=x onerror=alert(1)>")
    page.locator("#figura-guardar").click()
    expect(page.locator("#ws-status")).to_have_text("parámetros inválidos")
    expect(page.locator("#figura-etiqueta img")).to_have_count(0)
