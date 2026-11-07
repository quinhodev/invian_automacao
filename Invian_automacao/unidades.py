# =============================================================================
# unidades.py — Automação da tela de Unidades (Players)
# =============================================================================
# Responsável por:
#   - Abrir a tela de unidades
#   - Pesquisar e abrir o cadastro de um player
#   - Selecionar o horário correto no combo
#   - Salvar as alterações
#
# Para automatizar outras telas do sistema, crie um novo arquivo seguindo
# este mesmo padrão (ex: campanhas.py, conteudos.py).
# =============================================================================

import re

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

from config import (
    TIMEOUT_ELEMENTO,
    TIMEOUT_NAVEGACAO,
    TIMEOUT_OVERLAY,
    URL_UNIDADES,
)
from horario import (
    gerar_termos_busca_horario,
    horario_corresponde,
)
from navegador import aguardar_carregamento
from texto import normalizar_horario_texto
from web_utils import escolher_linha


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------

def abrir_tela_unidades(pagina: Page) -> None:
    """Navega até a tela de unidades e aguarda o carregamento."""
    pagina.goto(URL_UNIDADES, wait_until="domcontentloaded", timeout=TIMEOUT_NAVEGACAO)
    aguardar_carregamento(pagina)


# ---------------------------------------------------------------------------
# Busca e abertura do player
# ---------------------------------------------------------------------------

def pesquisar_e_abrir_player(pagina: Page, nome_player: str) -> None:
    """
    Pesquisa o player pelo nome e abre o cadastro.

    Escolhe a linha cujo nome é IGUAL ao buscado (a busca por substring antiga
    abria 'Loja 10' ao procurar 'Loja 1', e podia salvar o horário no player errado).

    Lança RuntimeError se o player não for encontrado ou se o nome for ambíguo.
    """
    campo = pagina.locator('input[placeholder="Pesquisar"]:visible').first
    campo.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    campo.click()
    campo.press("Control+A")
    campo.press("Backspace")
    campo.fill(nome_player)
    campo.press("Enter")

    aguardar_carregamento(pagina, 5000)

    linha = escolher_linha(pagina, nome_player, timeout=10_000)
    if linha is None:
        raise RuntimeError(
            f"Player '{nome_player}' não encontrado na tela de unidades. "
            "Confira se o nome está igual ao cadastrado no sistema."
        )

    linha.scroll_into_view_if_needed()
    linha.click()
    pagina.wait_for_selector("text=Informação básica", timeout=20_000)


# ---------------------------------------------------------------------------
# Seleção de horário — utilitários internos
# ---------------------------------------------------------------------------

def _ler_valor_atual_horarios(select_horarios) -> str:
    """Lê o texto atualmente selecionado no campo Horários."""
    for seletor in [
        ".mat-mdc-select-value-text",
        ".mat-select-value-text",
        ".mat-mdc-select-value",
        ".mat-select-value",
        ".mat-mdc-select-min-line",
    ]:
        try:
            valor = select_horarios.locator(seletor).first.inner_text(timeout=2000)
            valor = normalizar_horario_texto(valor)
            if valor:
                return valor
        except Exception:
            pass

    try:
        return normalizar_horario_texto(select_horarios.inner_text(timeout=2000))
    except Exception:
        return ""


def _esperar_overlay_fechar(pagina: Page, timeout_ms: int = 5000) -> bool:
    """Aguarda o menu do mat-select fechar; envia ESC se demorar."""
    tempo = 0
    passo = 250

    while tempo < timeout_ms:
        try:
            if pagina.locator(".cdk-overlay-pane:visible").count() == 0:
                return True
        except Exception:
            return True
        pagina.wait_for_timeout(passo)
        tempo += passo

    try:
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(500)
    except Exception:
        pass

    return False


def _option_esta_desabilitada(opcao) -> bool:
    """Verifica se uma mat-option está desabilitada ou é campo de pesquisa."""
    try:
        if opcao.locator("ngx-mat-select-search, input").count() > 0:
            return True
    except Exception:
        pass

    for attr in ["aria-disabled", "class"]:
        try:
            valor = opcao.get_attribute(attr, timeout=500) or ""
            if attr == "aria-disabled" and valor.lower() == "true":
                return True
            if attr == "class" and "disabled" in valor.lower():
                return True
        except Exception:
            pass

    return False


def _painel_do_overlay(overlay):
    """Retorna o painel rolável do mat-select."""
    for seletor in [".mat-mdc-select-panel", ".mat-select-panel"]:
        try:
            painel = overlay.locator(seletor).first
            painel.wait_for(state="visible", timeout=1500)
            return painel
        except Exception:
            pass
    return overlay


def _clicar_opcao(opcao, pagina: Page) -> None:
    """Clica em uma opção do mat-select e aguarda o menu fechar."""
    opcao.scroll_into_view_if_needed()
    pagina.wait_for_timeout(250)
    opcao.click(timeout=10_000)
    _esperar_overlay_fechar(pagina)


# ---------------------------------------------------------------------------
# Seleção de horário — fluxo principal
# ---------------------------------------------------------------------------

def selecionar_horario(pagina: Page, horario_sistema: str) -> bool:
    """
    Seleciona o horário pelo nome completo no combo, incluindo horários compostos.

    Retorna:
        True  → fez alteração (necessário salvar)
        False → horário já estava correto (não é necessário salvar)

    Lança RuntimeError se o horário não for encontrado.
    """
    horario_sistema = normalizar_horario_texto(horario_sistema)

    if not horario_sistema:
        raise ValueError("Horário vazio. Não é possível selecionar.")

    select_horarios = pagina.get_by_role(
        "combobox",
        name=re.compile(r"^Horários?$", re.IGNORECASE),
    ).first
    select_horarios.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    select_horarios.scroll_into_view_if_needed()

    valor_atual = _ler_valor_atual_horarios(select_horarios)
    if valor_atual and horario_corresponde(valor_atual, horario_sistema):
        print(f"[INFO] Horário já correto: {valor_atual}")
        return False

    select_horarios.click()

    overlay = pagina.locator(".cdk-overlay-pane:visible").last
    overlay.wait_for(state="visible", timeout=TIMEOUT_OVERLAY)
    painel = _painel_do_overlay(overlay)

    # Campo de pesquisa interno do combo (opcional)
    campo_filtro = None
    try:
        campo_filtro = overlay.locator('input[placeholder="Pesquisar"]:visible').first
        campo_filtro.wait_for(state="visible", timeout=3000)
    except PlaywrightTimeoutError:
        campo_filtro = None

    ultimas_opcoes_vistas = []

    for termo in gerar_termos_busca_horario(horario_sistema):
        if campo_filtro is not None:
            try:
                campo_filtro.click()
                campo_filtro.press("Control+A")
                campo_filtro.press("Backspace")
                if termo:
                    campo_filtro.fill(termo)
                pagina.wait_for_timeout(900)
            except Exception:
                pass

        try:
            painel.evaluate("el => { el.scrollTop = 0; }")
        except Exception:
            pass

        opcoes = overlay.locator("mat-option")

        for _ in range(18):
            quantidade = opcoes.count()
            ultimas_opcoes_vistas = []

            for i in range(quantidade):
                opcao = opcoes.nth(i)

                if _option_esta_desabilitada(opcao):
                    continue

                try:
                    texto_opcao = opcao.inner_text(timeout=1000)
                except Exception:
                    continue

                texto_limpo = normalizar_horario_texto(texto_opcao)
                if texto_limpo:
                    ultimas_opcoes_vistas.append(texto_limpo)

                if horario_corresponde(texto_opcao, horario_sistema):
                    _clicar_opcao(opcao, pagina)

                    valor_depois = _ler_valor_atual_horarios(select_horarios)
                    if valor_depois and horario_corresponde(valor_depois, horario_sistema):
                        if valor_atual and horario_corresponde(valor_atual, valor_depois):
                            print("[INFO] Opção selecionada é igual à que já estava.")
                            return False
                        print(f"[OK] Horário selecionado: {valor_depois}")
                        return True

                    raise RuntimeError(
                        f"Cliquei na opção, mas o campo ficou com valor inesperado.\n"
                        f"Esperado: {horario_sistema}\n"
                        f"Campo ficou: {valor_depois or 'não foi possível ler'}"
                    )

            # Scroll para mais opções
            try:
                fim = painel.evaluate(
                    "el => Math.ceil(el.scrollTop + el.clientHeight) >= el.scrollHeight"
                )
                if fim:
                    break
                painel.evaluate("el => { el.scrollTop += el.clientHeight; }")
                pagina.wait_for_timeout(350)
            except Exception:
                break

    try:
        pagina.keyboard.press("Escape")
    except Exception:
        pass

    debug = "\n".join(f"- {o}" for o in ultimas_opcoes_vistas[:12]) or "Nenhuma opção encontrada."
    raise RuntimeError(
        f"Horário não encontrado no sistema: '{horario_sistema}'\n\n"
        f"Últimas opções visíveis:\n{debug}\n\n"
        "Verifique se o nome do horário na planilha está igual ao cadastrado no sistema."
    )


# ---------------------------------------------------------------------------
# Salvar alterações
# ---------------------------------------------------------------------------

def salvar_alteracoes(pagina: Page) -> bool:
    """
    Salva o cadastro se o botão Salvar estiver habilitado.

    Retorna:
        True  → salvou com sucesso
        False → botão desabilitado (sem alterações pendentes)
    """
    botao = pagina.get_by_role(
        "button",
        name=re.compile(r"^Salvar$", re.IGNORECASE),
    ).first
    botao.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    botao.scroll_into_view_if_needed()

    try:
        pagina.keyboard.press("Escape")
    except Exception:
        pass

    for _ in range(30):
        try:
            habilitado = botao.is_enabled(timeout=500)
        except PlaywrightError:
            habilitado = False

        if habilitado:
            # Um único clique: se o clique falhar, o erro sobe (antes o loop clicava de novo
            # e podia salvar duas vezes).
            botao.click(timeout=10_000)
            try:
                pagina.get_by_text(
                    re.compile(r"(Accepted|Sucesso|Salvo|Atualizado)", re.IGNORECASE)
                ).first.wait_for(state="visible", timeout=15_000)
                return True
            except PlaywrightTimeoutError as e:
                raise RuntimeError(
                    "Cliquei em Salvar, mas não encontrei mensagem de confirmação."
                ) from e
        pagina.wait_for_timeout(500)

    print("[INFO] Botão Salvar ficou desabilitado. Nenhuma alteração pendente.")
    return False
