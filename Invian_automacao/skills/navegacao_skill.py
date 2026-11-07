# =============================================================================
# skills/navegacao_skill.py — Skills: Navegação e Preparação do Ambiente
# =============================================================================
# Skills para navegador, contexto, e abertura de telas.
# Parte do framework Superpowers: skills composáveis.
# =============================================================================

from playwright.sync_api import Browser, BrowserContext, Page
from skills import registry, skill


@skill(
    name="criar_navegador",
    description="Inicializa o navegador Playwright (Edge ou Chromium).",
    requires_auth=False,
    depends_on=[],
)
def criar_navegador_skill(pw, headless=None, **kwargs) -> Browser:
    """Cria o navegador (Edge → Chromium). `headless=None` usa config.HEADLESS."""
    from navegador import criar_navegador
    browser = criar_navegador(pw, headless)
    print("[OK] [skill:criar_navegador] Evidência: browser conectado =", browser.is_connected())
    return browser


@skill(
    name="criar_contexto",
    description="Cria o contexto do navegador com locale pt-BR.",
    requires_auth=False,
    depends_on=["criar_navegador"],
)
def criar_contexto_skill(navegador: Browser, **kwargs) -> BrowserContext:
    from navegador import criar_contexto
    contexto = criar_contexto(navegador)
    print("[OK] [skill:criar_contexto] Evidência: contexto criado.")
    return contexto


@skill(
    name="criar_pagina",
    description="Cria uma nova aba de página no navegador.",
    requires_auth=False,
    depends_on=["criar_contexto"],
)
def criar_pagina_skill(contexto: BrowserContext, **kwargs) -> Page:
    from navegador import criar_pagina
    pagina = criar_pagina(contexto)
    print("[OK] [skill:criar_pagina] Evidência: página criada.")
    return pagina


@skill(
    name="abrir_tela_unidades",
    description="Navega para a tela de Unidades (players) no sistema.",
    requires_auth=True,
    depends_on=["login"],
)
def abrir_tela_unidades_skill(pagina: Page, **kwargs) -> None:
    from unidades import abrir_tela_unidades
    abrir_tela_unidades(pagina)
    print("[OK] [skill:abrir_tela_unidades] Evidência: navegado para tela de unidades.")