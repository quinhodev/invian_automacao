# =============================================================================
# faces.py — Automação da tela de Faces (Preços / Anunciantes por dia)
# =============================================================================
# Fluxo por face:
#   Faces → linha da face → menu ⋮ → "Preços" → campo "Anunciantes por dia" → Salvar
#
# Correções em relação à versão anterior:
#   - Os "fallbacks" nunca rodavam: um Locator do Playwright nunca é falsy, então
#     `if not linha:` / `if not botao_salvar:` jamais disparavam. Agora usa
#     primeiro_visivel(), que devolve None de verdade.
#   - wait_for_selector("text=Sucesso, text=Salvo, ...") NÃO é sintaxe válida de
#     seletor (a vírgula virava parte do texto) → sempre estourava 15 s. Agora usa
#     get_by_text(regex).
#   - "Salvar" era procurado na página inteira (podia clicar no Salvar errado);
#     agora é procurado dentro do modal.
#   - A opção do mat-select era achada por substring (12 casava com 112/120);
#     agora é exata.
#   - Depois de alterar, o valor é relido para confirmar que o campo aceitou.
#   - Linha da face escolhida por igualdade (Loja 1 ≠ Loja 10).
# =============================================================================

import re

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from config import (
    TIMEOUT_ELEMENTO,
    TIMEOUT_NAVEGACAO,
    URL_FACES,
    VALOR_ANUNCIANTES_POR_DIA,
)
from navegador import aguardar_carregamento
from web_utils import SELETOR_LINHA, escolher_linha, primeiro_visivel

SEL_MODAL = "mat-dialog-container, .mat-mdc-dialog-container, [role='dialog']"
RE_SUCESSO = re.compile(r"(Sucesso|Salvo|Atualizado|Success|Saved|Accepted)", re.IGNORECASE)

SEL_BOTAO_MENU = [
    'button:has(mat-icon:has-text("more_vert"))',
    'button:has(mat-icon:has-text("more_horiz"))',
    'button[aria-label*="Mais" i]',
    'button[aria-label*="Ações" i]',
    'button[aria-label*="Menu" i]',
    "button.mat-mdc-menu-trigger",
    "button.mat-menu-trigger",
    'button:has-text("⋮")',
]

SEL_ITEM_PRECOS = [
    '[role="menuitem"]:has-text("Preços")',
    'button.mat-mdc-menu-item:has-text("Preços")',
    'mat-menu-item:has-text("Preços")',
    'button:has-text("Preços")',
]

SEL_CAMPO_ANUNCIANTES = [
    'mat-form-field:has-text("Anunciantes por dia") input',
    'mat-form-field:has-text("Anunciantes por dia") mat-select',
    'input[formcontrolname*="anunciante" i]',
    'mat-select[formcontrolname*="anunciante" i]',
    'input[placeholder*="Anunciante" i]',
]


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------

def abrir_tela_faces(pagina: Page) -> None:
    """Navega até a tela de Faces e aguarda a tabela carregar."""
    pagina.goto(URL_FACES, wait_until="domcontentloaded", timeout=TIMEOUT_NAVEGACAO)
    aguardar_carregamento(pagina)
    for texto in ("text=Unidade", "text=Tipo de face"):
        try:
            pagina.wait_for_selector(texto, timeout=TIMEOUT_ELEMENTO)
            return
        except PlaywrightTimeoutError:
            continue  # a tabela pode carregar de outro jeito; segue mesmo assim


# ---------------------------------------------------------------------------
# Menu ⋮ → Preços
# ---------------------------------------------------------------------------

def _modal_precos(pagina: Page):
    """Devolve o locator do modal 'Preços' (ou do <body>, se não for um dialog padrão)."""
    modal = pagina.locator(SEL_MODAL).filter(
        has_text=re.compile("Anunciantes por dia", re.IGNORECASE)
    ).last
    try:
        modal.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
        return modal
    except PlaywrightTimeoutError:
        # Lança TimeoutError se o texto realmente não existir → "modal não abriu"
        pagina.get_by_text("Anunciantes por dia").first.wait_for(
            state="visible", timeout=TIMEOUT_ELEMENTO
        )
        return pagina.locator("body")


def _pesquisar_face(pagina: Page, nome_face: str, log=print) -> None:
    """Digite o nome no campo de busca da tela de Faces (se existir) para filtrar a tabela.

    Sem isso, a tabela pode estar paginada e a face não aparecer nas linhas visíveis.
    """
    seletores_busca = [
        'input[placeholder*="Pesquisar" i]:visible',
        'input[placeholder*="Buscar" i]:visible',
        'input[placeholder*="Filtrar" i]:visible',
        'input[formcontrolname*="pesquisar" i]:visible',
        'input[formcontrolname*="buscar" i]:visible',
        'input[formcontrolname*="nome" i]:visible',
    ]
    for seletor in seletores_busca:
        try:
            campo = pagina.locator(seletor).first
            campo.wait_for(state="visible", timeout=3000)
            campo.click()
            campo.press("Control+A")
            campo.press("Backspace")
            campo.fill(nome_face)
            campo.press("Enter")
            log(f"   [BUSCA] Pesquisado '{nome_face}' no campo de busca.")
            aguardar_carregamento(pagina, 5000)
            return
        except Exception:
            continue
    # Nenhum campo de busca encontrado — segue sem filtrar (tabela pequena?)
    log(f"   [AVISO] Nenhum campo de busca encontrado na tela de Faces; procurando na tabela completa.")


def clicar_menu_precos_da_face(pagina: Page, nome_face: str, log=print) -> None:
    """Localiza a linha da face, abre o menu ⋮ e clica em 'Preços'."""
    _pesquisar_face(pagina, nome_face, log=log)
    linha = escolher_linha(pagina, nome_face, timeout=TIMEOUT_ELEMENTO, log=log)
    if linha is None:
        # Debug: lista as linhas visíveis para ajudar a diagnosticar
        try:
            linhas_visiveis = pagina.locator(SELETOR_LINHA).all_inner_texts()
            resumo = "\n".join(f"   - {t[:120]}" for t in linhas_visiveis[:10])
        except Exception:
            resumo = "(não foi possível ler linhas visíveis)"
        raise RuntimeError(
            f"Face '{nome_face}' não encontrada na tela de Faces. "
            "Confira se o nome está igual ao cadastrado no sistema.\n"
            f"Linhas visíveis na tabela:\n{resumo}"
        )
    linha.scroll_into_view_if_needed()

    botao_menu = primeiro_visivel(linha, SEL_BOTAO_MENU)
    if botao_menu is None and linha.locator("button").count() > 0:
        botao_menu = linha.locator("button").last  # ações costumam ficar no fim da linha
    if botao_menu is None:
        raise RuntimeError(f"Botão de menu (⋮) não encontrado na linha da face '{nome_face}'.")
    botao_menu.click()

    overlay = pagina.locator(".cdk-overlay-container")
    item = primeiro_visivel(overlay, SEL_ITEM_PRECOS, timeout=3000)
    if item is None:
        item = primeiro_visivel(pagina, SEL_ITEM_PRECOS, timeout=2000)
    if item is None:
        raise RuntimeError(f"Opção 'Preços' não encontrada no menu da face '{nome_face}'.")
    item.click()

    try:
        _modal_precos(pagina)
    except PlaywrightTimeoutError:
        raise RuntimeError("Modal 'Preços' não abriu após clicar na opção.")


# ---------------------------------------------------------------------------
# Campo "Anunciantes por dia"
# ---------------------------------------------------------------------------

def _localizar_campo(pagina: Page, modal):
    """Localiza o input/mat-select de 'Anunciantes por dia' dentro da modal.

    Tenta várias estratégias porque o Angular Material pode renderizar como
    input simples ou mat-select, e o texto do label pode estar em elementos
    filhos do mat-form-field.
    """
    # Estratégia 1: seletores diretos por CSS
    seletores_diretos = [
        # Baseado no HTML real do Invian: <input matinput type="number">
        'mat-mdc-form-field input[matinput]',
        'mat-mdc-form-field input[type="number"]',
        'mat-form-field:has-text("Anunciantes por dia") input',
        'mat-form-field:has-text("Anunciantes por dia") mat-select',
        'input[formcontrolname*="anunciante" i]',
        'mat-select[formcontrolname*="anunciante" i]',
        'input[placeholder*="Anunciante" i]',
    ]
    for seletor in seletores_diretos:
        try:
            loc = modal.locator(seletor).first
            loc.wait_for(state="visible", timeout=2000)
            return loc
        except Exception:
            continue

    # Estratégia 2: acha o rótulo pelo texto e sobe até o mat-form-field pai,
    # depois desce para input ou mat-select
    try:
        rotulo = modal.get_by_text(re.compile(r"Anunciantes\s+por\s+dia", re.I)).first
        rotulo.wait_for(state="visible", timeout=3000)
        campo = rotulo.locator(
            "xpath=ancestor::mat-form-field[1]//input | "
            "ancestor::mat-form-field[1]//mat-select | "
            "ancestor::div[contains(@class,'mat-mdc-text-field-wrapper')]//input | "
            "ancestor::div[contains(@class,'mat-mdc-select')]//input"
        ).first
        campo.wait_for(state="visible", timeout=3000)
        return campo
    except Exception:
        pass

    # Estratégia 3: busca por label semântico do Angular Material
    try:
        campo = modal.get_by_label(re.compile(r"Anunciantes\s+por\s+dia", re.I)).first
        campo.wait_for(state="visible", timeout=2000)
        return campo
    except Exception:
        pass

    return None


def _ler_valor(campo):
    """Lê o valor numérico atual do campo (input ou mat-select).

    Retorna (valor|None, tag). Tenta múltiplas estratégias antes de desistir.
    """
    tag = campo.evaluate("el => el.tagName.toLowerCase()")

    # --- input simples -------------------------------------------------
    if tag == "input":
        for metodo in (
            lambda: campo.input_value(),
            lambda: campo.get_attribute("value") or "",
            lambda: campo.inner_text() or "",
        ):
            try:
                texto = metodo()
            except Exception:
                texto = ""
            m = re.search(r"\d+", texto or "")
            if m:
                return int(m.group()), tag
        return None, tag

    # --- mat-select ----------------------------------------------------
    # Tenta ler o valor exibido no select (texto visível ou atributo)
    candidatos_texto = [
        lambda: campo.inner_text(),
        lambda: campo.locator(".mat-mdc-select-value-text").first.inner_text(timeout=1500),
        lambda: campo.locator(".mat-select-value-text").first.inner_text(timeout=1500),
        lambda: campo.locator(".mat-mdc-select-value").first.inner_text(timeout=1500),
        lambda: campo.get_attribute("value") or "",
    ]
    for metodo in candidatos_texto:
        try:
            texto = metodo()
        except Exception:
            texto = ""
        m = re.search(r"\d+", texto or "")
        if m:
            return int(m.group()), tag

    return None, tag


def verificar_e_ajustar_anunciantes_por_dia(
    pagina: Page, valor_desejado: int = VALOR_ANUNCIANTES_POR_DIA
) -> dict:
    """
    Na modal "Preços" aberta, verifica/ajusta "Anunciantes por dia".

    Retorna dict: success, changed, message, valor_anterior, valor_atual.
    message ∈ {"estava certo, nada a fazer", "alterado com sucesso",
               "alterado (confirmação visual não detectada)", "Erro: ..."}
    """
    resultado = {
        "success": False,
        "changed": False,
        "message": "",
        "valor_anterior": None,
        "valor_atual": None,
    }

    try:
        modal = _modal_precos(pagina)
        campo = _localizar_campo(pagina, modal)
        if campo is None:
            raise RuntimeError("Campo 'Anunciantes por dia' não encontrado na modal de Preços.")

        valor_atual, tag = _ler_valor(campo)
        if valor_atual is None:
            raise RuntimeError("Não foi possível ler o valor atual de 'Anunciantes por dia'.")
        resultado["valor_anterior"] = valor_atual
        resultado["valor_atual"] = valor_atual

        if valor_atual == valor_desejado:
            resultado.update(success=True, message="estava certo, nada a fazer")
            return resultado

        # --- alterar ---
        if tag == "input":
            campo.click()
            campo.press("Control+A")
            campo.fill(str(valor_desejado))
            campo.press("Tab")
        else:  # mat-select: opção EXATA (12 não pode casar com 112 ou 120)
            campo.click()
            padrao = re.compile(rf"^\s*{valor_desejado}\s*$")
            opcao = pagina.get_by_role("option", name=padrao).first
            try:
                opcao.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
            except PlaywrightTimeoutError:
                opcao = pagina.locator("mat-option").filter(has_text=padrao).first
                opcao.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
            opcao.click()
        pagina.wait_for_timeout(500)

        # --- confirmar que o campo aceitou o valor ---
        valor_novo, _ = _ler_valor(campo)
        if valor_novo != valor_desejado:
            raise RuntimeError(
                f"O campo ficou com {valor_novo} depois de tentar definir {valor_desejado}."
            )

        # --- salvar (dentro do modal) ---
        botao_salvar = primeiro_visivel(
            modal,
            ['button:has-text("Salvar")', 'button:has-text("Save")'],
        )
        if botao_salvar is None:
            raise RuntimeError("Botão 'Salvar' não encontrado na modal de Preços.")
        botao_salvar.scroll_into_view_if_needed()
        botao_salvar.click()

        confirmado = False
        try:
            pagina.get_by_text(RE_SUCESSO).first.wait_for(state="visible", timeout=8000)
            confirmado = True
        except PlaywrightTimeoutError:
            try:
                modal.wait_for(state="hidden", timeout=7000)  # modal fechou = salvou
                confirmado = True
            except PlaywrightTimeoutError:
                pass

        resultado.update(
            success=True,
            changed=True,
            valor_atual=valor_desejado,
            message="alterado com sucesso" if confirmado else "alterado (confirmação visual não detectada)",
        )
        return resultado

    except Exception as e:
        resultado.update(success=False, message=f"Erro: {e}")
        return resultado


def fechar_modal_precos_se_aberta(pagina: Page) -> None:
    """Fecha o modal de Preços se ainda estiver aberto (Escape)."""
    try:
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(300)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fluxo completo por face
# ---------------------------------------------------------------------------

def processar_face(
    pagina: Page,
    nome_face: str,
    valor_anunciantes: int = VALOR_ANUNCIANTES_POR_DIA,
    log=print,
) -> dict:
    """
    Abre a tela de Faces, abre Preços da face e ajusta "Anunciantes por dia".
    Sempre começa navegando para a tela (cada linha é independente da anterior).
    """
    evidencias = []
    try:
        abrir_tela_faces(pagina)
        evidencias.append("Tela de Faces carregada.")

        clicar_menu_precos_da_face(pagina, nome_face, log=log)
        evidencias.append(f"Modal 'Preços' aberta para face '{nome_face}'.")

        r = verificar_e_ajustar_anunciantes_por_dia(pagina, valor_anunciantes)
        evidencias.append(f"Anunciantes por dia: {r['message']} (valor: {r['valor_atual']})")
        r["evidence"] = evidencias
        return r
    except Exception as e:
        evidencias.append(f"Erro: {e}")
        return {
            "success": False,
            "changed": False,
            "message": f"Erro: {e}",
            "valor_anterior": None,
            "valor_atual": None,
            "evidence": evidencias,
        }
    finally:
        fechar_modal_precos_se_aberta(pagina)
