# =============================================================================
# login.py — Autenticação no sistema Invian
# =============================================================================
# Responsável por:
#   - Obter credenciais (variável de ambiente ou input interativo)
#   - Preencher formulário de login
#   - Confirmar que o login foi bem-sucedido
# =============================================================================

import os
import re
from getpass import getpass

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from config import TEXTO_LOGIN_OK, TIMEOUT_LOGIN, URL_HOME


# ---------------------------------------------------------------------------
# Credenciais
# ---------------------------------------------------------------------------

def obter_credenciais() -> tuple[str, str]:
    """
    Retorna (email, senha).

    Prioridade:
        1. Variáveis de ambiente INVIAN_EMAIL e INVIAN_SENHA
        2. Input interativo no terminal
    """
    email = os.getenv("INVIAN_EMAIL", "").strip()
    senha = os.getenv("INVIAN_SENHA", "")  # sem strip: espaços podem fazer parte da senha

    if not email:
        email = input("E-mail Invian: ").strip()

    if not senha:
        senha = getpass("Senha Invian: ")

    if not email or not senha:
        raise ValueError("E-mail e senha são obrigatórios para fazer login.")

    return email, senha


# ---------------------------------------------------------------------------
# Interação com o formulário
# ---------------------------------------------------------------------------

def _preencher_campo(pagina: Page, seletores: list, valor: str, nome: str) -> None:
    """Tenta cada seletor da lista até encontrar o campo visível e preenchê-lo."""
    ultimo_erro = None
    for seletor in seletores:
        try:
            campo = pagina.locator(seletor).first
            campo.wait_for(state="visible", timeout=7000)
            campo.fill(valor)
            return
        except Exception as e:
            ultimo_erro = e
    raise RuntimeError(f"Campo '{nome}' não encontrado. Último erro: {ultimo_erro}")


def _clicar_botao_login(pagina: Page) -> None:
    """Clica no botão de login usando estratégias progressivas."""
    # Estratégia 1: role semântico
    try:
        botao = pagina.get_by_role(
            "button",
            name=re.compile(r"(sign in|iniciar sessão|entrar)", re.IGNORECASE),
        ).first
        botao.wait_for(state="visible", timeout=7000)
        botao.click()
        return
    except Exception:
        pass

    # Estratégia 2: seletores de texto
    for seletor in [
        'button:has-text("sign in")',
        'button:has-text("Sign in")',
        'button:has-text("Iniciar sessão")',
        'button:has-text("Entrar")',
    ]:
        try:
            botao = pagina.locator(seletor).first
            botao.wait_for(state="visible", timeout=7000)
            botao.click()
            return
        except Exception:
            pass

    raise RuntimeError("Botão de login não encontrado.")


# ---------------------------------------------------------------------------
# Fluxo de login
# ---------------------------------------------------------------------------

def fazer_login(pagina: Page, email: str | None = None, senha: str | None = None) -> None:
    """
    Navega até a tela de login, preenche credenciais e confirma o acesso.

    Se `email`/`senha` não forem informados, usa obter_credenciais() (variável de
    ambiente ou terminal). A GUI passa as credenciais digitadas diretamente —
    antes elas eram lidas do formulário mas nunca chegavam aqui, e o `input()`
    do terminal travava a thread da GUI.

    Lança RuntimeError se o login não for confirmado.
    """
    if not email or not senha:
        email, senha = obter_credenciais()

    pagina.goto(URL_HOME, wait_until="domcontentloaded", timeout=TIMEOUT_LOGIN)

    seletores_email = [
        'input[type="email"]',
        'input[formcontrolname="email"]',
        'input[name="email"]',
        'xpath=/html/body/app-root/layout/empty-layout/div/div/app-sign-in'
        '/div/div/div/form/mat-form-field[1]/div[1]/div[2]/div/input',
    ]
    seletores_senha = [
        'input[type="password"]',
        'input[formcontrolname="password"]',
        'input[name="password"]',
        'xpath=/html/body/app-root/layout/empty-layout/div/div/app-sign-in'
        '/div/div/div/form/mat-form-field[2]/div[1]/div[2]/div[1]/input',
    ]

    _preencher_campo(pagina, seletores_email, email, "e-mail")
    _preencher_campo(pagina, seletores_senha, senha, "senha")
    _clicar_botao_login(pagina)

    try:
        pagina.wait_for_selector(f"text={TEXTO_LOGIN_OK}", timeout=TIMEOUT_LOGIN)
        print("[OK] Login concluido!")
    except PlaywrightTimeoutError as e:
        raise RuntimeError(
            "Login não confirmado. Verifique e-mail, senha ou se a tela mudou "
            f"(esperava ver o texto '{TEXTO_LOGIN_OK}' — ajuste TEXTO_LOGIN_OK em config.py "
            "se a conta estiver em outro idioma)."
        ) from e
