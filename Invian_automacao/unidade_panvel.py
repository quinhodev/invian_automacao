# =============================================================================
# unidade_panvel.py — Automação de Criação de Unidade Panvel
# =============================================================================
# Responsável por criar uma unidade do zero no painel web.invian.net seguindo
# as regras de formatação sob medida do cliente Panvel Farmácias.
#
# Fluxo (stepper com 5 etapas; todas ficam no DOM, inativas têm atributo inert):
#   1. Abrir tela de criação de unidade
#   2. Clicar em "Adicionar unidade"
#   3. Etapa 1 — Informação Básica -> Próximo
#   4. Etapa 2 — Localização ("lat, long") -> Próximo
#   5. Etapa 3 — Câmeras (pular) -> Próximo
#   6. Etapa 4 — Faces (adicionar 1) -> Próximo
#   7. Etapa 5 — Restrições -> Terminar
#
# Todo helper de formulário procura DENTRO do painel ativo do stepper
# (<div role="tabpanel" class="mat-horizontal-stepper-content-current">),
# nunca na página toda.
#
# Padrão de nomenclatura Panvel:
#   [Filial] - Panvel [Nome] [Tag]_[Seq]
#   Tags: MED-TV_43 (NUC/Tela Padrão), MED-TV_21 (Self-Checkout)
#   Seq: sem sufixo (1 NUC) | _01, _02 (2+ NUCs na mesma filial)
# =============================================================================

import re
import time
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
from web_utils import chave

# ---------------------------------------------------------------------------
# Contador de sequencial por filial (escopo da execução atual)
# ---------------------------------------------------------------------------
_contador_por_filial: dict[str, int] = defaultdict(int)
_total_por_filial: dict[str, int] = defaultdict(int)

# Regex que detecta se o nome já está no padrão Panvel (contém "Panvel" e "MED-TV_N")
_RE_NOME_PANVEL = re.compile(r"MED-TV_\d+")


def _obter(row, coluna: str) -> str:
    """Lê a célula da coluna ignorando acento/caixa/espaços ('Rua e Número' == 'rua e numero')."""
    mapa = {chave(c): c for c in row.index}
    real = mapa.get(chave(coluna))
    return texto_celula(row[real]) if real is not None else ""


def _obter_filial(row) -> str:
    """Devolve o valor da coluna Filial, ou da coluna ID se Filial não existir na planilha."""
    return _obter(row, COLUNA_FILIAL) or _obter(row, COLUNA_ID)


def preparar_sequenciais(df) -> None:
    """Conta quantas linhas (já filtradas) cada filial tem na planilha e zera o contador.

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
    """Devolve o sufixo sequencial para a filial.

    Regras Panvel:
      - filial com 1 unidade na planilha: '' (sem sufixo)
      - filial com 2+ unidades: TODAS recebem sufixo, na ordem: '_01', '_02', ...
    """
    _contador_por_filial[filial] += 1
    if _total_por_filial.get(filial, 1) <= 1:
        return ""
    return f"_{_contador_por_filial[filial]:02d}"


def _formatar_coordenada(valor) -> str:
    """Formata latitude/longitude com exatamente 6 casas decimais.

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
    """Monta o nome padronizado Panvel: [Filial] - Panvel [Nome] [Tag]_[Seq]

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


def _nome_ja_formatado(nome: str) -> bool:
    """True se o nome já está no padrão Panvel (contém 'Panvel' e 'MED-TV_N')."""
    return bool(nome and "Panvel" in nome and _RE_NOME_PANVEL.search(nome))


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------


def abrir_tela_criacao_unidade(pagina: Page) -> None:
    """Navega até a tela de criação de unidade e aguarda o carregamento."""
    pagina.goto(URL_CRIACAO_UNIDADE, wait_until="domcontentloaded", timeout=TIMEOUT_NAVEGACAO)
    aguardar_carregamento(pagina)


def clicar_adicionar_unidade(pagina: Page) -> None:
    """Clica no botão 'Adicionar' para abrir o formulário de criação de unidade.

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
        from web_utils import primeiro_visivel

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
# Helpers de escopo do stepper (painel ativo / modal)
# ---------------------------------------------------------------------------


def _painel_atual(pagina: Page):
    """Devolve o locator do painel ativo do stepper (etapa corrente)."""
    painel = pagina.locator(".mat-horizontal-stepper-content-current").first
    painel.wait_for(state="visible")
    return painel


def _campo(escopo, rotulo: str):
    """Devolve o mat-form-field cujo label é exatamente `rotulo` (aceita '*' no final).

    A busca é restrita a `escopo` (painel atual ou modal). O match é exato,
    ignorando acento/caixa/espaços via web_utils.chave.
    """
    alvo = chave(rotulo)
    alvo_com_asterisco = chave(rotulo + "*")
    candidatos = escopo.locator("mat-form-field")
    total = candidatos.count()
    for i in range(total):
        ff = candidatos.nth(i)
        label_texto = ""
        for tag in ("mat-label", "label"):
            el = ff.locator(tag).first
            try:
                if el.count() > 0:
                    label_texto = el.inner_text().strip()
                    if label_texto:
                        break
            except Exception:
                continue
        if chave(label_texto) == alvo or chave(label_texto) == alvo_com_asterisco:
            return ff
    raise RuntimeError(f'mat-form-field com label "{rotulo}" não encontrado no escopo informado.')


def _preencher_input(escopo, rotulo: str, valor: str) -> None:
    """Preenche o input/textarea do mat-form-field identificado pelo rótulo (dentro de escopo)."""
    campo = _campo(escopo, rotulo)
    input_loc = campo.locator("input, textarea").first
    input_loc.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    input_loc.click()
    input_loc.press("Control+A")
    input_loc.fill(valor)



def _selecionar_opcao(pagina: Page, escopo, rotulo: str, texto: str | None = None) -> str:
    """Abre o mat-select do campo (dentro de escopo) e escolhe uma opção.

    overlay = pagina.locator(".cdk-overlay-pane:visible").last
    coleta overlay.locator("mat-option"); ignora opções que contenham
    input/ngx-mat-select-search ou com aria-disabled="true".

    Se texto for None -> clica na PRIMEIRA opção válida (espera até aparecer ≥1).
    Se texto for informado -> match exato via chave() (parcial só se único);
      clica por índice (opcoes.nth(i)), NUNCA por pagina.locator('mat-option:has-text(...)').
    Em erro, pressiona Escape e levanta RuntimeError listando as opções vistas.
    Espera o overlay fechar no final. Devolve o texto da opção clicada.
    """
    campo = _campo(escopo, rotulo)
    mat_select = campo.locator("mat-select").first
    mat_select.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    mat_select.click()

    # Aguarda o overlay do CDK abrir
    overlay = pagina.locator(".cdk-overlay-pane:visible").last
    overlay.wait_for(state="visible", timeout=TIMEOUT_OVERLAY)
    opcoes = overlay.locator("mat-option")

    def _opcoes_validas():
        validos = []
        total = opcoes.count()
        for i in range(total):
            op = opcoes.nth(i)
            try:
                if not op.is_visible():
                    continue
            except Exception:
                continue
            # Ignora o campo de busca ("Pesquisar") quando está dentro de um mat-option
            if op.locator("input, ngx-mat-select-search").count() > 0:
                continue
            try:
                if op.get_attribute("aria-disabled") == "true":
                    continue
            except Exception:
                pass
            try:
                t = op.inner_text().strip()
            except Exception:
                continue
            if t:
                validos.append((i, t))
        return validos

    alvo = chave(texto) if texto is not None else None

    # Espera até aparecer pelo menos uma opção válida
    validos = []
    inicio = time.time()
    while time.time() - inicio < TIMEOUT_OVERLAY / 1000:
        validos = _opcoes_validas()
        if validos:
            break
        pagina.wait_for_timeout(200)

    if not validos:
        try:
            pagina.keyboard.press("Escape")
        except Exception:
            pass
        raise RuntimeError(
            f'Nenhuma opção válida encontrada no select "{rotulo}" após abri-lo.'
        )

    if texto is None:
        i, txt = validos[0]
    else:
        # Match exato (ignorando acento/caixa)
        exatas = [(i, t) for i, t in validos if chave(t) == alvo]
        if len(exatas) == 1:
            i, txt = exatas[0]
        else:
            # Match parcial só se único
            parciais = [(i, t) for i, t in validos if alvo in chave(t)]
            if len(parciais) == 1:
                i, txt = parciais[0]
            else:
                vistas = [t for _, t in validos]
                try:
                    pagina.keyboard.press("Escape")
                except Exception:
                    pass
                raise RuntimeError(
                    f'Opção "{texto}" não encontrada no select "{rotulo}". '
                    f"Opções vistas: {vistas}"
                )

    opcoes.nth(i).click()
    return txt


def _clicar_proximo(pagina: Page) -> None:
    """Clica no botão 'Próximo' do painel ativo, esperando habilitar até ~6 s."""
    painel = _painel_atual(pagina)
    botao = painel.get_by_role("button", name=re.compile(r"^\s*Próximo\s*$"))
    inicio = time.time()
    clicado = False
    while time.time() - inicio < 6:
        try:
            if botao.count() > 0 and botao.first.is_visible() and botao.first.is_enabled():
                botao.first.click()
                clicado = True
                break
        except Exception:
            pass
        pagina.wait_for_timeout(200)
    if not clicado:
        raise RuntimeError(
            "Botão 'Próximo' não habilitou dentro do tempo esperado (~6 s). "
            "Verifique se todos os campos obrigatórios da etapa foram preenchidos."
        )
    # Aguarda o painel anterior perder a classe "current" (ou ~800 ms) antes de seguir.
    try:
        pagina.wait_for_function(
            "(el) => !el.classList.contains('mat-horizontal-stepper-content-current')",
            arg=painel.element_handle(),
            timeout=800,
        )
    except Exception:
        pagina.wait_for_timeout(800)


def _clicar_terminar(pagina: Page) -> None:
    """Clica no botão 'Terminar' do painel ativo (última etapa: Restrições)."""
    painel = _painel_atual(pagina)
    botao = painel.get_by_role("button", name=re.compile(r"^\s*Terminar\s*$"))
    inicio = time.time()
    clicado = False
    while time.time() - inicio < 6:
        try:
            if botao.count() > 0 and botao.first.is_visible() and botao.first.is_enabled():
                botao.first.click()
                clicado = True
                break
        except Exception:
            pass
        pagina.wait_for_timeout(200)
    if not clicado:
        raise RuntimeError(
            "Botão 'Terminar' não habilitou dentro do tempo esperado (~6 s)."
        )
    try:
        pagina.wait_for_function(
            "(el) => !el.classList.contains('mat-horizontal-stepper-content-current')",
            arg=painel.element_handle(),
            timeout=800,
        )
    except Exception:
        pagina.wait_for_timeout(800)



# ---------------------------------------------------------------------------
# Etapa 1 — Informação Básica
# ---------------------------------------------------------------------------


def preencher_informacao_basica(pagina: Page, row, log=print) -> None:
    """Preenche a Etapa 1 (Informação Básica) dentro do painel ativo do stepper."""
    escopo = _painel_atual(pagina)

    nome_player = _obter(row, COLUNA_NOME_PLAYER)
    filial = _obter_filial(row)

    # Nome: se já estiver no padrão Panvel, usa como está; senão monta.
    if _nome_ja_formatado(nome_player):
        nome_final = nome_player
        log(f"   Nome já formatado (Panvel), usado como está: {nome_final}")
    else:
        # Exige Filial/ID apenas quando é preciso montar o nome.
        if not filial:
            raise RuntimeError(
                "Coluna 'Filial' (ou 'ID') não encontrada/vazia na planilha; "
                "é necessária para montar o nome da unidade."
            )
        tag = (
            TAG_SELF_CHECKOUT
            if ("CHECKOUT" in nome_player.upper() or "SELF" in nome_player.upper())
            else TAG_NUC_PADRAO
        )
        sequencial = _gerar_sequencial(filial)
        nome_final = _normalizar_nome_panvel(filial, nome_player, tag, sequencial)
        log(f"   Nome Panvel gerado: {nome_final}")

    # Nome (input)
    _preencher_input(escopo, "Nome", nome_final)

    # Localização (select): LOCALIZACAO_PADRAO é obrigatória
    if not LOCALIZACAO_PADRAO:
        raise RuntimeError("LOCALIZACAO_PADRAO não definido em config.py.")
    _selecionar_opcao(pagina, escopo, "Localização", LOCALIZACAO_PADRAO)

    # Tipo de elemento (select)
    _selecionar_opcao(pagina, escopo, "Tipo de elemento", TIPO_ELEMENTO_PADRAO)

    # Tipo de unidade (select)
    _selecionar_opcao(pagina, escopo, "Tipo de unidade", TIPO_UNIDADE_PADRAO)

    # Cidade (select, valor da planilha) — obrigatório
    cidade = _obter(row, COLUNA_CIDADE)
    if not cidade:
        raise RuntimeError(
            f"Coluna '{COLUNA_CIDADE}' não encontrada ou vazia na planilha "
            "(obrigatória na Etapa 1)."
        )
    _selecionar_opcao(pagina, escopo, "Cidade", cidade)

    # Endereço (input, coluna "Rua e Número") — obrigatório
    rua = _obter(row, COLUNA_RUA_NUMERO)
    if not rua:
        raise RuntimeError(
            f"Coluna '{COLUNA_RUA_NUMERO}' não encontrada ou vazia na planilha "
            "(obrigatória na Etapa 1)."
        )
    _preencher_input(escopo, "Endereço", rua)

    log("   Etapa 1 (Informação Básica) preenchida.")


# ---------------------------------------------------------------------------
# Etapa 2 — Localização
# ---------------------------------------------------------------------------


def preencher_localizacao(pagina: Page, row, log=print) -> None:
    """Preenche a Etapa 2 (Localização) com 'lat, long' (6 casas, separador ', ')."""
    lat = _formatar_coordenada(_obter(row, COLUNA_LATITUDE))
    lon = _formatar_coordenada(_obter(row, COLUNA_LONGITUDE))

    if not lat or not lon:
        raise RuntimeError("Latitude e/ou Longitude não encontradas ou vazias na planilha.")

    texto = f"{lat}, {lon}"
    _preencher_input(_painel_atual(pagina), "Localização", texto)
    # Tira o foco do campo para disparar a atualização do mapa; NÃO aperta Enter.
    pagina.keyboard.press("Tab")
    pagina.wait_for_timeout(1500)

    log(f"   Etapa 2 (Localização) preenchida: {texto}")


# ---------------------------------------------------------------------------
# Etapa 3 — Câmeras (pular)
# ---------------------------------------------------------------------------


def pular_cameras(pagina: Page, log=print) -> None:
    """Pula a Etapa 3 (Câmeras): apenas avança para a próxima etapa."""
    log("   Etapa Câmeras ignorada")
    _clicar_proximo(pagina)



# ---------------------------------------------------------------------------
# Etapa 4 — Faces
# ---------------------------------------------------------------------------


def vincular_faces(pagina: Page, row, log=print) -> None:
    """Vincula uma face na Etapa 4 (Faces) e avança para a próxima etapa.

    Fluxo no painel atual:
      1. Clica no botão "Adicionar" (abre o modal "Adicionar Face").
      2. No modal: "Tipo de face" -> primeira opção; "Dimensões" -> primeira opção válida.
      3. Clica em "Salvar" dentro do modal.
      4. Confirma o fechamento do modal e avança (Próximo).
    """
    escopo = _painel_atual(pagina)

    # 1. Clica em "Adicionar" dentro do painel atual
    botao_adicionar = escopo.get_by_role("button", name=re.compile(r"^\s*Adicionar\s*$"))
    botao_adicionar.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    botao_adicionar.click()
    log("   Botão 'Adicionar' clicado (modal Adicionar Face).")

    # 2. Modal "Adicionar Face"
    dialog = (
        pagina.locator("mat-dialog-container, .mat-mdc-dialog-container, [role='dialog']")
        .filter(has_text="Adicionar Face")
        .last
    )
    dialog.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)

    # Tipo de face -> primeira opção
    tipo_face = _selecionar_opcao(pagina, dialog, "Tipo de face", texto=None)
    log(f"   Tipo de face escolhido: {tipo_face}")

    # Dimensões -> primeira opção válida (pode demorar a carregar após escolher o tipo de face)
    dimensao = _selecionar_opcao(pagina, dialog, "Dimensões", texto=None)
    log(f"   Dimensão escolhida: {dimensao}")

    # 3. Clica em "Salvar" dentro do modal (um único clique)
    botao_salvar = dialog.get_by_role("button", name=re.compile(r"^\s*Salvar\s*$"))
    botao_salvar.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    botao_salvar.click()

    # 4. Confirma o fechamento do modal (até 15 s)
    try:
        dialog.wait_for(state="hidden", timeout=15_000)
    except PlaywrightTimeoutError:
        raise RuntimeError("Modal de face não fechou após Salvar.")

    # Se possível, confirma o texto "1 faces" no painel
    try:
        escopo.get_by_text(re.compile(r"\b1\s*faces?\b")).first.wait_for(
            state="visible", timeout=3000
        )
    except Exception:
        pass  # não crítico; o fechamento do modal já confirma

    # Avança para a próxima etapa
    _clicar_proximo(pagina)


# ---------------------------------------------------------------------------
# Etapa 5 — Restrições / Finalizar
# ---------------------------------------------------------------------------


def configurar_restricoes(pagina: Page, log=print) -> None:
    """Etapa 5 (Restrições): não há nada a preencher; apenas registra."""
    log("   Restrições: nada a configurar.")



def finalizar_unidade(pagina: Page, log=print) -> bool:
    """Clica em 'Terminar' (Etapa 5) e confirma o sucesso da criação.

    Confirmação (até 20 s): toast com /(Sucesso|Salvo|Criado|Success|Created)/i
    visível, OU o título "Adicionar unidade" sair da tela / a URL mudar.
    Retorna True somente se algo for confirmado; senão False + aviso com o
    texto visível da tela (primeiros 300 chars do body) para diagnóstico.
    """
    _clicar_terminar(pagina)

    url_antes = pagina.url

    # Aguarda confirmação de sucesso (até 20 s)
    inicio = time.time()
    while time.time() - inicio < 20:
        # Toast de sucesso
        try:
            toast = pagina.get_by_text(
                re.compile(r"(Sucesso|Salvo|Criado|Success|Created)", re.IGNORECASE)
            ).first
            if toast.is_visible():
                log("   Unidade criada com sucesso (toast detectado).")
                return True
        except Exception:
            pass

        # O título "Adicionar unidade" saiu da tela
        try:
            titulo = pagina.get_by_text("Adicionar unidade").first
            if titulo.count() > 0 and not titulo.is_visible():
                log("   Unidade criada com sucesso (tela 'Adicionar unidade' fechou).")
                return True
        except Exception:
            pass

        # A URL mudou
        if pagina.url != url_antes:
            log("   Unidade criada com sucesso (URL alterada após Terminar).")
            return True

        pagina.wait_for_timeout(500)

    # Nenhuma confirmação: aviso com o texto visível da tela para diagnóstico
    try:
        corpo = pagina.locator("body").inner_text()[:300]
    except Exception:
        corpo = "(não foi possível ler o corpo da tela)"
    log(
        "   [AVISO] Nenhuma confirmação de criação detectada após 'Terminar'. "
        f"Texto visível da tela (300 chars): {corpo}"
    )
    return False


# ---------------------------------------------------------------------------
# Orquestração completa
# ---------------------------------------------------------------------------


def processar_criacao_unidade_panvel(pagina: Page, row, log=print) -> dict:
    """Executa todo o fluxo de criação de unidade Panvel (5 etapas do stepper).

    Fluxo:
      abrir_tela -> clicar_adicionar_unidade -> preencher_informacao_basica ->
      _clicar_proximo -> preencher_localizacao -> _clicar_proximo ->
      pular_cameras (já clica Próximo) -> vincular_faces (já clica Próximo) ->
      configurar_restricoes -> finalizar_unidade

    Retorna dict padronizado:
      {"success": bool, "skipped": bool, "changed": bool, "message": str}
    """
    try:
        # Validação inicial: Filial/ID, Nome do Player, Latitude e Longitude são obrigatórias.
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
        log("   Botão 'Adicionar' clicado.")

        preencher_informacao_basica(pagina, row, log=log)
        _clicar_proximo(pagina)

        preencher_localizacao(pagina, row, log=log)
        _clicar_proximo(pagina)

        pular_cameras(pagina, log=log)  # já clica em Próximo

        vincular_faces(pagina, row, log=log)  # já clica em Próximo ao final

        configurar_restricoes(pagina, log=log)
        salvou = finalizar_unidade(pagina, log=log)

        return {
            "success": salvou,
            "skipped": False,
            "changed": salvou,
            "message": "unidade criada com sucesso" if salvou else "falha ao finalizar",
        }

    except Exception as e:
        return {
            "success": False,
            "skipped": False,
            "changed": False,
            "message": f"Erro: {e}",
        }

