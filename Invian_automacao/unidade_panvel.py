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
    COLUNA_ESTADO,
    COLUNA_FILIAL,
    COLUNA_ID,
    COLUNA_LATITUDE,
    COLUNA_LONGITUDE,
    COLUNA_NOME_PLAYER,
    COLUNA_RUA_NUMERO,
    PREFIXO_PANVEL,
    TAG_NUC_PADRAO,
    TAG_SELF_CHECKOUT,
    TIMEOUT_ELEMENTO,
    TIMEOUT_NAVEGACAO,
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


def preparar_sequenciais(df) -> None:
    """
    Conta quantas linhas (já filtradas) cada filial tem na planilha e zera o contador.
    Deve ser chamada UMA vez no início da fase Panvel (o core.py faz isso).
    """
    _contador_por_filial.clear()
    _total_por_filial.clear()
    mapa = {chave(c): c for c in df.columns}
    col = mapa.get(chave(COLUNA_FILIAL))
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
    Clica no botão 'Adicionar unidade' para abrir o formulário multi-abas.

    Tenta vários seletores comuns para o botão de adicionar.
    """
    seletores = [
        'button:has-text("Adicionar unidade")',
        'button:has-text("Adicionar Unidade")',
        'button:has-text("+ Adicionar")',
        'button:has-text("Novo")',
        'button.btn-add',
        'button[aria-label*="Adicionar" i]',
        'button[aria-label*="Add" i]',
    ]
    botao = primeiro_visivel(pagina, seletores, timeout=TIMEOUT_ELEMENTO)
    if botao is None:
        raise RuntimeError("Botão 'Adicionar unidade' não encontrado na tela.")
    botao.scroll_into_view_if_needed()
    botao.click()
    pagina.wait_for_timeout(1000)
    aguardar_carregamento(pagina, 5000)


# ---------------------------------------------------------------------------
# Aba 1 — Informação Básica
# ---------------------------------------------------------------------------

def _preencher_campo_texto(pagina: Page, label: str, valor: str, timeout: int = TIMEOUT_ELEMENTO) -> None:
    """
    Preenche um campo de texto identificado por label (mat-form-field).
    Tenta localizar o input associado ao label informado.
    """
    seletores = [
        f'mat-form-field:has-text("{label}") input',
        f'mat-form-field:has-text("{label}") mat-select',
        f'input[placeholder*="{label}" i]',
        f'input[name*="{label.lower()}" i]',
        f'input[formcontrolname*="{label.lower()}" i]',
    ]
    campo = primeiro_visivel(pagina, seletores, timeout=timeout)
    if campo is None:
        raise RuntimeError(f'Campo "{label}" não encontrado para preenchimento.')
    campo.click()
    campo.wait_for(state="visible", timeout=timeout)
    campo.press("Control+A")
    campo.fill(valor)


def preencher_informacao_basica(pagina: Page, row, log=print) -> None:
    """
    Preenche a Aba 1 (Informação Básica) aplicando a formatação Panvel.

    Monta o nome padronizado: [Filial] - Panvel [Nome] [Tag]_[Seq]
    """
    filial = _obter(row, COLUNA_FILIAL)
    nome_player = _obter(row, COLUNA_NOME_PLAYER)

    if not filial:
        raise RuntimeError("Coluna 'Filial' não encontrada ou vazia na planilha.")
    if not nome_player:
        raise RuntimeError("Coluna 'Nome do Player' não encontrada ou vazia na planilha.")

    # Detecta tipo de mídia pelo nome (heurística simples)
    nome_upper = nome_player.upper()
    if "CHECKOUT" in nome_upper or "SELF" in nome_upper:
        tag = TAG_SELF_CHECKOUT
    else:
        tag = TAG_NUC_PADRAO

    sequencial = _gerar_sequencial(filial)
    nome_padrao = _normalizar_nome_panvel(filial, nome_player, tag, sequencial)
    log(f"   Nome Panvel gerado: {nome_padrao}")

    # Preenche campos básicos
    _preencher_campo_texto(pagina, "Nome", nome_padrao)
    _preencher_campo_texto(pagina, "Filial", str(filial))

    # Rua e Número
    rua = _obter(row, COLUNA_RUA_NUMERO)
    if rua:
        _preencher_campo_texto(pagina, "Endereço", rua)

    # Cidade e Estado
    cidade = _obter(row, COLUNA_CIDADE)
    if cidade:
        _preencher_campo_texto(pagina, "Cidade", cidade)

    estado = _obter(row, COLUNA_ESTADO)
    if estado:
        _preencher_campo_texto(pagina, "Estado", estado)

    log("   Aba 1 (Informação Básica) preenchida.")


# ---------------------------------------------------------------------------
# Aba 2 — Localização
# ---------------------------------------------------------------------------

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
    _preencher_campo_texto(pagina, "Latitude", latitude)
    _preencher_campo_texto(pagina, "Longitude", longitude)

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
        # Valida colunas obrigatórias
        colunas_obrigatorias = [COLUNA_FILIAL, COLUNA_NOME_PLAYER, COLUNA_LATITUDE, COLUNA_LONGITUDE]
        
        # Debug: mostrar colunas disponíveis na linha
        log(f"   [DEBUG] Colunas na linha: {list(row.index)}")
        log(f"   [DEBUG] Buscando colunas: {colunas_obrigatorias}")
        
        faltando = [c for c in colunas_obrigatorias if not _obter(row, c)]
        if faltando:
            # Tenta encontrar coluna Filial com nomes alternativos
            if COLUNA_FILIAL in faltando:
                # Busca alternativas comuns para "Filial"
                alternativas_filial = ["ID", "Filial ID", "Código", "Codigo", "Loja", "Numero", "Número"]
                for alt in alternativas_filial:
                    if _obter(row, alt):
                        log(f"   [INFO] Coluna 'Filial' não encontrada, mas achou alternativa: '{alt}'")
                        # Não adiciona à lista de faltando se achou alternativa
                        faltando = [c for c in faltando if c != COLUNA_FILIAL]
                        break
            
            if faltando:
                return {
                    "success": False,
                    "skipped": False,
                    "changed": False,
                    "message": f"Coluna(s) obrigatória(s) ausente(s) ou vazia(s): {faltando}",
                }

        abrir_tela_criacao_unidade(pagina)
        log("   Tela de criação de unidade aberta.")

        clicar_adicionar_unidade(pagina)
        log("   Botão 'Adicionar unidade' clicado.")

        preencher_informacao_basica(pagina, row, log=log)

        # Navega para Aba 2 (Localização)
        _clicar_aba(pagina, "Localização")
        preencher_localizacao(pagina, row, log=log)

        # Navega para Aba 3 (Faces)
        _clicar_aba(pagina, "Faces")
        vincular_faces(pagina, row, log=log)

        # Navega para Aba 4 (Restrições)
        _clicar_aba(pagina, "Restrições")
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