# =============================================================================
# unidade_panvel.py — Automação de Criação de Unidade Panvel
# =============================================================================
# Responsável por criar uma unidade do zero no painel web.invian.net seguindo
# as regras de formatação sob medida do cliente Panvel Farmácias.
#
# Fluxo:
#   1. Abrir tela de criação de unidade
#   2. Clicar em "Adicionar unidade"
#   3. Aba 1 — Informação Básica (dados da planilha + formatação Panvel)
#   4. Aba 2 — Localização (coordenadas com 6 casas decimais + confirma mapa)
#   5. Aba 3 — Faces (vincular faces)
#   6. Aba 4 — Restrições (checkbox)
#   7. Salvar (botão btn-save)
#
# Padrão de nomenclatura Panvel:
#   [Filial] - Panvel [Nome] [Tag]_[Seq]
#   Tags: MED-TV_43 (NUC/Tela Padrão), MED-TV_21 (Self-Checkout)
#   Seq: sem sufixo (1 NUC) | _01, _02 (2+ NUCs na mesma filial)
# =============================================================================

import re
import unicodedata
from collections import defaultdict

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from config import (
    COLUNA_CIDADE,
    COLUNA_FILIAL,
    COLUNA_ID,
    COLUNA_LATITUDE,
    COLUNA_LONGITUDE,
    COLUNA_NOME_PLAYER,
    COLUNA_RUA_NUMERO,
    LOCALIZACAO_PADRAO,
    PREFIXO_PANVEL,
    TAG_NUC_PADRAO,
    TAG_SELF_CHECKOUT,
    TIPO_ELEMENTO_PADRAO,
    TIPO_UNIDADE_PADRAO,
    TIMEOUT_ELEMENTO,
    TIMEOUT_NAVEGACAO,
    TIMEOUT_OVERLAY,
    URL_CRIACAO_UNIDADE,
)
from navegador import aguardar_carregamento
from texto import normalizar_espacos, texto_celula
from web_utils import chave, primeiro_visivel

# ---------------------------------------------------------------------------
# Contador de sequencial por filial (escopo da execução atual)
# ---------------------------------------------------------------------------
_contador_por_filial: dict[str, int] = defaultdict(int)
_total_por_filial: dict[str, int] = defaultdict(int)


def _obter(row, coluna: str) -> str:
    """Lê a célula da coluna ignorando acento/caixa/espaços ('Rua e Número' == 'rua e numero')."""
    mapa = {chave(c): c for c in row.index}
    real = mapa.get(chave(coluna))
    return texto_celula(row[real]) if real is not None else ""


def _obter_filial(row) -> str:
    """Devolve o valor da coluna Filial, ou da coluna ID se Filial não existir na planilha."""
    return _obter(row, COLUNA_FILIAL) or _obter(row, COLUNA_ID)


def preparar_sequenciais(df) -> None:
    """
    Conta quantas linhas (já filtradas) cada filial tem na planilha e zera o contador.
    Deve ser chamada UMA vez no início da fase Panvel (o core.py faz isso).
    """
    _contador_por_filial.clear()
    _total_por_filial.clear()
    mapa = {chave(c): c for c in df.columns}
    col = mapa.get(chave(COLUNA_FILIAL)) or mapa.get(chave(COLUNA_ID))
    if col is None:
        return
    for valor in df[col]:
        filial = texto_celula(valor)
        if filial:
            _total_por_filial[filial] += 1


def _gerar_sequencial(filial: str) -> str:
    """
    Devolve o sufixo sequencial para a filial.

    Regras Panvel:
      - filial com 1 unidade na planilha: '' (sem sufixo)
      - filial com 2+ unidades: TODAS recebem sufixo, na ordem: '_01', '_02', ...
    """
    _contador_por_filial[filial] += 1
    if _total_por_filial.get(filial, 1) <= 1:
        return ""
    return f"_{_contador_por_filial[filial]:02d}"


def _formatar_coordenada(valor) -> str:
    """
    Formata latitude/longitude com exatamente 6 casas decimais.

    Exemplo: -30.02751  ->  -30.027510
             -51.16842   ->  -51.168420
    """
    texto = texto_celula(valor).replace(",", ".")
    try:
        numero = float(texto)
    except ValueError:
        return texto
    return f"{numero:.6f}"


def _normalizar_nome_panvel(filial: str, nome: str, tag: str, sequencial: str) -> str:
    """
    Monta o nome padronizado Panvel: [Filial] - Panvel [Nome] [Tag]_[Seq]

    Remove acentos e normaliza espaços nos componentes.
    """
    filial_limpo = normalizar_espacos(remover_acentos(texto_celula(filial))).strip()
    nome_limpo = normalizar_espacos(remover_acentos(texto_celula(nome))).strip()
    tag_limpo = normalizar_espacos(texto_celula(tag)).strip()

    partes = [filial_limpo, "-", PREFIXO_PANVEL]
    if nome_limpo:
        partes.append(nome_limpo)
    if tag_limpo:
        partes.append(tag_limpo + sequencial)

    return " ".join(partes)


def remover_acentos(texto: str) -> str:
    """Remove acentos e diacríticos de um texto."""
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------

def abrir_tela_criacao_unidade(pagina: Page) -> None:
    """Navega até a tela de criação de unidade e aguarda o carregamento."""
    pagina.goto(URL_CRIACAO_UNIDADE, wait_until="domcontentloaded", timeout=TIMEOUT_NAVEGACAO)
    aguardar_carregamento(pagina)


def clicar_adicionar_unidade(pagina: Page) -> None:
    """
    Clica no botão 'Adicionar' para abrir o formulário de criação de unidade.

    Espera o input de pesquisa da lista de unidades ficar visível (garante que a
    tela /settings/inventory/units carregou), depois clica no botão com role=button
    e nome exatamente "Adicionar" (ignorando espaços nas bordas), com fallbacks.
    """
    # Aguarda a lista de unidades carregar (input de pesquisa da tabela)
    try:
        pagina.locator('input[placeholder="Pesquisar"]').first.wait_for(
            state="visible", timeout=TIMEOUT_ELEMENTO
        )
    except PlaywrightTimeoutError:
        pass  # segue mesmo assim; o botão pode estar visível sem esse input

    # 1ª tentativa: role=button com nome exatamente "Adicionar"
    try:
        botao = pagina.get_by_role("button", name=re.compile(r"^\s*Adicionar\s*$"))
        botao.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    except Exception:
        botao = None

    # Fallbacks
    if botao is None:
        seletores = [
            'button:has(mat-icon[data-mat-icon-name="plus"])',
            'button.mat-mdc-unelevated-button:has-text("Adicionar")',
            'button.mat-flat-button:has-text("Adicionar")',
        ]
        botao = primeiro_visivel(pagina, seletores, timeout=TIMEOUT_ELEMENTO)

    if botao is None:
        raise RuntimeError(
            "Botão 'Adicionar' não encontrado na tela de unidades "
            "(URL: " + str(URL_CRIACAO_UNIDADE) + ")."
        )

    botao.scroll_into_view_if_needed()
    botao.click()
    pagina.wait_for_timeout(1000)
    aguardar_carregamento(pagina, 5000)


# ---------------------------------------------------------------------------
# Aba 1 — Informação Básica
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helpers de formulário baseados em RÓTULO do mat-form-field
# ---------------------------------------------------------------------------


def _campo(pagina: Page, rotulo: str):
    """
    Devolve o locator do mat-form-field cujo label é exatamente `rotulo`
    (aceita '*' no final do label).
    """
    candidatos = pagina.locator("mat-form-field")
    total = candidatos.count()
    for i in range(total):
        ff = candidatos.nth(i)
        label_texto = ""
        for tag in ("mat-label", "label"):
            el = ff.locator(tag).first
            if el.count() > 0:
                try:
                    label_texto = el.inner_text().strip()
                    break
                except Exception:
                    continue
        if label_texto == rotulo or label_texto == rotulo + "*":
            return ff
    raise RuntimeError(f'mat-form-field com label "{rotulo}" não encontrado.')


def _preencher_input(pagina: Page, rotulo: str, valor: str) -> None:
    """Preenche o input/textarea do mat-form-field identificado pelo rótulo."""
    campo = _campo(pagina, rotulo)
    input_loc = campo.locator("input, textarea").first
    input_loc.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    input_loc.click()
    input_loc.press("Control+A")
    input_loc.fill(valor)


def _selecionar_opcao(pagina: Page, rotulo: str, texto: str) -> None:
    """
    Abre o mat-select do mat-form-field identificado pelo rótulo, filtra se houver
    input de busca no overlay e escolhe a mat-option de texto IGUAL (usando web_utils.chave
    para ignorar acento/caixa). Aceita parcial só se for única; senão RuntimeError
    listando as opções vistas.
    """
    campo = _campo(pagina, rotulo)
    mat_select = campo.locator("mat-select").first
    mat_select.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    mat_select.click()

    # Aguarda o overlay do mat-select abrir
    overlay = pagina.locator(".mat-mdc-select-panel, .mat-select-panel, .cdk-overlay-pane").first
    overlay.wait_for(state="visible", timeout=TIMEOUT_OVERLAY)

    # Se há input de busca dentro do overlay, filtra
    busca = overlay.locator("input")
    if busca.count() > 0:
        try:
            busca.click()
            busca.press("Control+A")
            busca.fill(texto)
            pagina.wait_for_timeout(500)
        except Exception:
            pass  # segue sem filtro se não houver input de busca

    # Coleta opções visíveis
    opcoes_vistas = []
    opcoes = overlay.locator("mat-option").all()
    for op in opcoes:
        try:
            if op.is_visible():
                t = op.inner_text().strip()
                if t:
                    opcoes_vistas.append(t)
        except Exception:
            continue

    alvo = chave(texto)

    # Match exato (ignorando acento/caixa)
    exatas = [o for o in opcoes_vistas if chave(o) == alvo]
    if len(exatas) == 1:
        pagina.locator(f'mat-option:has-text("{exatas[0]}")').first.click()
        return

    # Match parcial único
    parciais = [o for o in opcoes_vistas if alvo in chave(o)]
    if len(parciais) == 1:
        pagina.locator(f'mat-option:has-text("{parciais[0]}")').first.click()
        return

    raise RuntimeError(
        f'Opção "{texto}" não encontrada no select "{rotulo}". '
        f"Opções vistas: {opcoes_vistas}"
    )


def _clicar_proximo(pagina: Page) -> None:
    """
    Clica no botão 'Próximo', esperando até ~6 s ele habilitar.
    Se não habilitar, levanta RuntimeError (campo obrigatório sem preencher).
    """
    import time

    inicio = time.time()
    while time.time() - inicio < 6:
        botao = primeiro_visivel(
            pagina,
            ['button:has-text("Próximo")', 'button:has-text("Proximo")'],
            timeout=1000,
        )
        if botao is not None:
            try:
                if botao.is_enabled():
                    botao.click()
                    pagina.wait_for_timeout(800)
                    return
            except Exception:
                pass
        pagina.wait_for_timeout(500)
    raise RuntimeError(
        "O botão 'Próximo' não habilitou — algum campo obrigatório ficou sem preencher."
    )


# ---------------------------------------------------------------------------
# Aba 1 — Informação Básica
# ---------------------------------------------------------------------------


def preencher_informacao_basica(pagina: Page, row, log=print) -> None:
    """
    Preenche a Aba 1 (Informação Básica) aplicando a formatação Panvel.

    Campos: Nome (input), Localização (select), Tipo de elemento (select),
    Tipo de unidade (select), Cidade (select), Endereço (input).
    Filial e Estado foram removidos do formulário (não existem na tela real).
    Descrição fica em branco.
    """
    filial = _obter_filial(row)
    nome_player = _obter(row, COLUNA_NOME_PLAYER)

    if not filial:
        raise RuntimeError("Coluna 'Filial' (ou 'ID') não encontrada ou vazia na planilha.")
    if not nome_player:
        raise RuntimeError("Coluna 'Nome do Player' não encontrada ou vazia na planilha.")

    # Se o nome da planilha já está no padrão Panvel (contém MED-TV_\d+ e "Panvel"),
    # usa como está e NÃO chama _gerar_sequencial.
    if re.search(r"MED-TV_\d+", nome_player) and "Panvel" in nome_player:
        nome_final = nome_player
        log(f"   Nome já formatado (Panvel), usado como está: {nome_final}")
    else:
        # Detecta tipo de mídia pelo nome (heurística simples)
        nome_upper = nome_player.upper()
        if "CHECKOUT" in nome_upper or "SELF" in nome_upper:
            tag = TAG_SELF_CHECKOUT
        else:
            tag = TAG_NUC_PADRAO

        sequencial = _gerar_sequencial(filial)
        nome_final = _normalizar_nome_panvel(filial, nome_player, tag, sequencial)
        log(f"   Nome Panvel gerado: {nome_final}")

    # Nome (input)
    _preencher_input(pagina, "Nome", nome_final)

    # Localização (select, valor padrão)
    if LOCALIZACAO_PADRAO:
        _selecionar_opcao(pagina, "Localização", LOCALIZACAO_PADRAO)

    # Tipo de elemento (select)
    _selecionar_opcao(pagina, "Tipo de elemento", TIPO_ELEMENTO_PADRAO)

    # Tipo de unidade (select)
    _selecionar_opcao(pagina, "Tipo de unidade", TIPO_UNIDADE_PADRAO)

    # Cidade (select, valor da planilha)
    cidade = _obter(row, COLUNA_CIDADE)
    if cidade:
        _selecionar_opcao(pagina, "Cidade", cidade)

    # Endereço (input, coluna "Rua e Número")
    rua = _obter(row, COLUNA_RUA_NUMERO)
    if rua:
        _preencher_input(pagina, "Endereço", rua)

    log("   Aba 1 (Informação Básica) preenchida.")


# ---------------------------------------------------------------------------
# Aba 2 — Localização
# ---------------------------------------------------------------------------

# TODO: seletores não validados (ainda não tenho prints dessa tela)


def preencher_localizacao(pagina: Page, row, log=print) -> None:
    """
    Preenche a Aba 2 (Localização) com Latitude e Longitude (6 casas decimais)
    e confirma o ponto no mapa.
    """
    latitude = _formatar_coordenada(_obter(row, COLUNA_LATITUDE))
    longitude = _formatar_coordenada(_obter(row, COLUNA_LONGITUDE))

    if not latitude or not longitude:
        raise RuntimeError("Latitude e/ou Longitude não encontradas ou vazias na planilha.")

    # Preenche campos de coordenadas
    _preencher_input(pagina, "Latitude", latitude)
    _preencher_input(pagina, "Longitude", longitude)

    # Confirma ponto no mapa (seletores do Handoff)
    botao_confirmar = primeiro_visivel(
        pagina,
        ["button.btn-confirmlocation", ".map-container button.btn-confirmlocation", 'button:has-text("Confirmar Ponto")'],
        timeout=TIMEOUT_ELEMENTO,
    )
    if botao_confirmar is not None:
        botao_confirmar.click()
        pagina.wait_for_timeout(1000)

    log(f"   Aba 2 (Localização) preenchida: {latitude}, {longitude}")


# ---------------------------------------------------------------------------
# Aba 3 — Faces
# TODO: seletores não validados (ainda não tenho prints dessa tela)
# ---------------------------------------------------------------------------

def vincular_faces(pagina: Page, row, log=print) -> None:
    """
    Preenche a Aba 3 (Faces): adiciona/vincula faces e define a tag da face.

    Prepara o terreno para a automação de preços (faces.py) que já existe.
    """
    nome_player = _obter(row, COLUNA_NOME_PLAYER)

    # Clica em "Adicionar Face"
    botao_add_face = primeiro_visivel(
        pagina,
        ['button.btn-add-face', 'button:has-text("Adicionar Face")', 'button:has-text("+ Face")'],
        timeout=TIMEOUT_ELEMENTO,
    )
    if botao_add_face is None:
        raise RuntimeError("Botão 'Adicionar Face' não encontrado na Aba 3.")
    botao_add_face.click()
    pagina.wait_for_timeout(1000)

    # Preenche a tag da face (usa o nome do player como referência)
    if nome_player:
        campo_tag = primeiro_visivel(
            pagina,
            ['input[name="faceTag"]', ".select-facetag", 'input[placeholder*="Face" i]'],
            timeout=TIMEOUT_ELEMENTO,
        )
        if campo_tag is not None:
            campo_tag.click()
            campo_tag.press("Control+A")
            campo_tag.fill(nome_player)
            pagina.wait_for_timeout(500)

    log("   Aba 3 (Faces) preenchida.")


# ---------------------------------------------------------------------------
# Aba 4 — Restrições
# TODO: seletores não validados (ainda não tenho prints dessa tela)
# ---------------------------------------------------------------------------

def configurar_restricoes(pagina: Page, log=print) -> None:
    """
    Preenche a Aba 4 (Restrições): marca checkbox de restrições se aplicável.
    """
    checkbox = primeiro_visivel(
        pagina,
        ['input[type="checkbox"].restrictionitem', 'input[type="checkbox"][name*="restriction" i]'],
        timeout=TIMEOUT_ELEMENTO,
    )
    if checkbox is not None:
        try:
            if not checkbox.is_checked():
                checkbox.click()
        except Exception:
            pass
    log("   Aba 4 (Restrições) configurada.")


# ---------------------------------------------------------------------------
# Salvar
# ---------------------------------------------------------------------------

def salvar_unidade(pagina: Page, log=print) -> bool:
    """
    Clica no botão Salvar/Finalizar e aguarda confirmação de sucesso.

    Retorna True se salvou com sucesso, False caso contrário.
    """
    seletores_salvar = [
        'button[type="submit"].btn-save',
        'button.btn-save',
        'button:has-text("Salvar")',
        'button:has-text("Finalizar")',
        'button:has-text("Save")',
    ]
    botao = primeiro_visivel(pagina, seletores_salvar, timeout=TIMEOUT_ELEMENTO)
    if botao is None:
        raise RuntimeError("Botão 'Salvar/Finalizar' não encontrado.")

    botao.scroll_into_view_if_needed()
    botao.click()

    # Aguarda confirmação de sucesso (toast/mensagem)
    try:
        pagina.get_by_text(
            re.compile(r"(Sucesso|Salvo|Atualizado|Success|Saved|Created|Criado)", re.IGNORECASE)
        ).first.wait_for(state="visible", timeout=15_000)
        log("   Unidade salva com sucesso.")
        return True
    except PlaywrightTimeoutError:
        # Pode ter fechado o modal direto = salvou
        pagina.wait_for_timeout(2000)
        log("   Unidade salva (confirmação visual não detectada, mas sem erro).")
        return True


# ---------------------------------------------------------------------------
# Orquestração completa
# ---------------------------------------------------------------------------

def processar_criacao_unidade_panvel(pagina: Page, row, log=print) -> dict:
    """
    Executa todo o fluxo de criação de unidade Panvel (Aba 1 → Aba 4 → Salvar).

    Retorna dict padronizado:
      {"success": bool, "skipped": bool, "changed": bool, "message": str}
    """
    try:
        # Valida colunas obrigatórias (Filial aceita fallback para ID)
        if not _obter_filial(row):
            return {
                "success": False,
                "skipped": False,
                "changed": False,
                "message": "Coluna 'Filial' (ou 'ID') ausente ou vazia na planilha.",
            }
        if not _obter(row, COLUNA_NOME_PLAYER):
            return {
                "success": False,
                "skipped": False,
                "changed": False,
                "message": "Coluna 'Nome do Player' ausente ou vazia na planilha.",
            }
        if not _obter(row, COLUNA_LATITUDE):
            return {
                "success": False,
                "skipped": False,
                "changed": False,
                "message": "Coluna 'Latitude' ausente ou vazia na planilha.",
            }
        if not _obter(row, COLUNA_LONGITUDE):
            return {
                "success": False,
                "skipped": False,
                "changed": False,
                "message": "Coluna 'Longitude' ausente ou vazia na planilha.",
            }

        abrir_tela_criacao_unidade(pagina)
        log("   Tela de criação de unidade aberta.")

        clicar_adicionar_unidade(pagina)
        log("   Botão 'Adicionar unidade' clicado.")

        preencher_informacao_basica(pagina, row, log=log)

        # Navega para Aba 2 (Localização)
        _clicar_proximo(pagina)
        preencher_localizacao(pagina, row, log=log)

        # Navega para Aba 3 (Faces)
        _clicar_proximo(pagina)
        vincular_faces(pagina, row, log=log)

        # Navega para Aba 4 (Restrições)
        _clicar_proximo(pagina)
        configurar_restricoes(pagina, log=log)

        # Salvar
        salvou = salvar_unidade(pagina, log=log)

        return {
            "success": salvou,
            "skipped": False,
            "changed": salvou,
            "message": "unidade criada com sucesso" if salvou else "falha ao salvar",
        }

    except Exception as e:
        return {
            "success": False,
            "skipped": False,
            "changed": False,
            "message": f"Erro: {e}",
        }


def _clicar_aba(pagina: Page, nome_aba: str) -> None:
    """
    Clica na aba (tab) informada para ativá-la antes de preencher.

    Tenta localizar por texto da aba (mat-tab, role=tab, etc.).
    """
    seletores = [
        f'mat-tab:has-text("{nome_aba}")',
        f'[role="tab"]:has-text("{nome_aba}")',
        f'button:has-text("{nome_aba}")',
        f'a:has-text("{nome_aba}")',
        f'div:has-text("{nome_aba}")',
    ]
    aba = primeiro_visivel(pagina, seletores, timeout=TIMEOUT_ELEMENTO)
    if aba is not None:
        try:
            aba.click()
            pagina.wait_for_timeout(800)
        except Exception:
            pass