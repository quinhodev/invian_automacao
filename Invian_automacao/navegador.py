# =============================================================================
# navegador.py — Inicialização e configuração do navegador (Playwright)
# =============================================================================
# Responsável por criar o navegador e o contexto de página.
# Para adicionar suporte a outro navegador (Firefox, Safari), edite aqui.
# =============================================================================

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    Error as PlaywrightError,
)

from config import HEADLESS, TIMEOUT_PADRAO


# ---------------------------------------------------------------------------
# Criação do navegador
# ---------------------------------------------------------------------------

def criar_navegador(pw, headless=None) -> Browser:
    """
    Tenta abrir o Microsoft Edge; se não encontrar, usa o Chromium padrão.

    `headless=None` usa o valor de config.HEADLESS (antes estava fixo em False,
    então a opção Headless da GUI/CLI era ignorada).
    """
    if headless is None:
        headless = HEADLESS
    try:
        return pw.chromium.launch(headless=headless, channel="msedge")
    except PlaywrightError:
        print("Microsoft Edge não encontrado. Abrindo Chromium padrão.")
        return pw.chromium.launch(headless=headless)


def criar_contexto(navegador: Browser) -> BrowserContext:
    """Cria o contexto do navegador com locale pt-BR."""
    return navegador.new_context(locale="pt-BR")


def criar_pagina(contexto: BrowserContext) -> Page:
    """Cria uma nova aba e aplica o timeout padrão."""
    pagina = contexto.new_page()
    pagina.set_default_timeout(TIMEOUT_PADRAO)
    return pagina


# ---------------------------------------------------------------------------
# Utilitários de navegação
# ---------------------------------------------------------------------------

def aguardar_carregamento(pagina: Page, timeout: int = 15_000) -> None:
    """Aguarda a rede ficar ociosa; ignora timeout silenciosamente."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    try:
        pagina.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass
