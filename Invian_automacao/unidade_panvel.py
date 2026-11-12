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
from pathlib import Path

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
from web_utils import chave, escolher_linha, SELETOR_CELULA

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


def _nome_final(row, log=print) -> str:
    """Calcula o nome final da unidade, uma única vez por linha.

    Se o Nome do Player já estiver no padrão Panvel, usa como está.
    Senão monta com _normalizar_nome_panvel + _gerar_sequencial (que só pode
    rodar UMA vez por linha, incrementando o contador da filial).
    """
    nome_player = _obter(row, COLUNA_NOME_PLAYER)
    if _nome_ja_formatado(nome_player):
        log(f"   Nome já formatado (Panvel), usado como está: {nome_player}")
        return nome_player
    filial = _obter_filial(row)
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
    nome = _normalizar_nome_panvel(filial, nome_player, tag, sequencial)
    log(f"   Nome Panvel gerado: {nome}")
    return nome


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
    rotulos_vistos = []
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
        rotulos_vistos.append(label_texto)
        if chave(label_texto) == alvo or chave(label_texto) == alvo_com_asterisco:
            return ff
    raise RuntimeError(
        f'mat-form-field com label "{rotulo}" não encontrado no escopo informado. '
        f"Rótulos vistos: {rotulos_vistos}"
    )


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
    Se texto for informado e o overlay tiver campo de busca (input:visible),
    digita o texto e espera ~600 ms ANTES de coletar as opções.
    Match exato via chave() (parcial só se único);
      clica por índice (opcoes.nth(i)), NUNCA por pagina.locator('mat-option:has-text(...)').
    Em erro, pressiona Escape e levanta RuntimeError listando as opções vistas.
    Depois de opcoes.nth(i).click(), espera a primeira mat-option sumir (overlay fechou).
    NÃO espera .cdk-overlay-pane sumir (o modal da face também é um pane).
    Devolve o texto da opção clicada.
    """
    campo = _campo(escopo, rotulo)
    mat_select = campo.locator("mat-select").first
    mat_select.wait_for(state="visible", timeout=TIMEOUT_ELEMENTO)
    mat_select.click()

    # Aguarda o overlay do CDK abrir
    overlay = pagina.locator(".cdk-overlay-pane:visible").last
    overlay.wait_for(state="visible", timeout=TIMEOUT_OVERLAY)

    # Se houver campo de busca no overlay e texto informado, digita e aguarda
    # ~600 ms para o filtro das opções ser aplicado antes de coletar.
    if texto is not None:
        busca = overlay.locator("input:visible").first
        try:
            if busca.count() > 0 and busca.is_visible():
                busca.click()
                busca.press("Control+A")
                busca.fill(texto)
                pagina.wait_for_timeout(600)
        except Exception:
            pass

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
    # Após clicar na opção, espera a primeira mat-option sumir (overlay fechou).
    # NÃO esperar .cdk-overlay-pane sumir: o modal da face também é um pane.
    try:
        pagina.locator("mat-option").first.wait_for(state="hidden", timeout=TIMEOUT_OVERLAY)
    except Exception:
        pagina.wait_for_timeout(800)
    return txt


def _clicar_proximo(pagina: Page) -> None:
    """Clica no botão 'Próximo' do painel ativo, esperando habilitar até ~6 s."""
    painel = _painel_atual(pagina)
    # Captura o handle ANTES do clique: o wait_for_function deve comparar com
    # o painel que existia antes, não com o novo painel renderizado depois.
    painel_handle = painel.element_handle()
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
            arg=painel_handle,
            timeout=800,
        )
    except Exception:
        pagina.wait_for_timeout(800)


def _clicar_terminar(pagina: Page) -> None:
    """Clica no botão 'Terminar' do painel ativo (última etapa: Restrições)."""
    painel = _painel_atual(pagina)
    # Captura o handle ANTES do clique: o wait_for_function deve comparar com
    # o painel que existia antes, não com o novo painel renderizado depois.
    painel_handle = painel.element_handle()
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
            arg=painel_handle,
            timeout=800,
        )
    except Exception:
        pagina.wait_for_timeout(800)



# ---------------------------------------------------------------------------
# Etapa 1 — Informação Básica
# ---------------------------------------------------------------------------


def preencher_informacao_basica(pagina: Page, row, log=print, nome_final=None) -> None:
    """Preenche a Etapa 1 (Informação Básica) dentro do painel ativo do stepper.

    Se `nome_final` for fornecido (calculado uma vez pelo chamador), é usado
    diretamente; senão, é calculado aqui (compatibilidade com chamadas diretas).
    """
    escopo = _painel_atual(pagina)

    nome_player = _obter(row, COLUNA_NOME_PLAYER)

    # Nome: usa o fornecido ou calcula uma vez (já formatado Panvel ou monta).
    if nome_final is None:
        if _nome_ja_formatado(nome_player):
            nome_final = nome_player
            log(f"   Nome já formatado (Panvel), usado como está: {nome_final}")
        else:
            # Exige Filial/ID apenas quando é preciso montar o nome.
            filial = _obter_filial(row)
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
    else:
        log(f"   Nome da unidade: {nome_final}")

    # Nome (input)
    _preencher_input(escopo, "Nome", nome_final)

    # Localização (select): se LOCALIZACAO_PADRAO vazio, usa a 1ª opção válida.
    if LOCALIZACAO_PADRAO:
        _selecionar_opcao(pagina, escopo, "Localização", LOCALIZACAO_PADRAO)
    else:
        escolhida = _selecionar_opcao(pagina, escopo, "Localização", texto=None)
        log(f"   [AVISO] LOCALIZACAO_PADRAO vazio: usada a 1ª opção: {escolhida}")

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



def _diagnostico(pagina: Page) -> str:
    """Devolve a etapa atual do stepper e os primeiros 300 caracteres de texto
    visível do painel atual/modal, para anexar ao "message" de exceção."""
    partes = []
    try:
        passo = pagina.locator(".mat-horizontal-stepper-content-current").first
        if passo.count() > 0:
            texto_passo = passo.inner_text()[:200].replace("\n", " | ")
            partes.append(f"etapa_atual={texto_passo}")
    except Exception:
        pass
    try:
        escopo = pagina.locator(".mat-horizontal-stepper-content-current").first
        if escopo.count() > 0:
            corpo = escopo.inner_text()[:300]
        else:
            corpo = pagina.locator("body").inner_text()[:300]
    except Exception:
        corpo = "(não foi possível ler a tela)"
    partes.append(f"texto_visível={corpo}")
    return " | ".join(partes)


def finalizar_unidade(pagina: Page, log=print, dry_run: bool = False) -> bool:
    """Clica em 'Terminar' (Etapa 5) e confirma o sucesso da criação.

    `url_antes` é capturado ANTES de chamar _clicar_terminar.
    Sucesso = toast /(Sucesso|Salvo|Criado|Success|Created)/i visível
      OU (URL mudou E o título "Adicionar unidade" não está mais visível).
    Se aparecer mensagem de erro (/(Erro|Error|Falha|inválid|obrigatóri)/i visível),
    retorna False imediatamente, logando o texto.
    Em dry-run, não clica em Terminar e retorna True.
    """
    if dry_run:
        log("   [DRY-RUN] 'Terminar' NÃO será clicado.")
        return True

    url_antes = pagina.url
    _clicar_terminar(pagina)

    # Aguarda confirmação de sucesso (até 20 s)
    inicio = time.time()
    while time.time() - inicio < 20:
        # Mensagem de erro -> falha imediata
        try:
            erro = pagina.get_by_text(
                re.compile(r"(Erro|Error|Falha|inválid|obrigatóri)", re.IGNORECASE)
            ).first
            if erro.is_visible():
                texto = erro.inner_text()[:300]
                log(f"   [ERRO] Mensagem de erro ao finalizar: {texto}")
                return False
        except Exception:
            pass

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

        # URL mudou E o título "Adicionar unidade" não está mais visível
        try:
            url_mudou = pagina.url != url_antes
            titulo = pagina.get_by_text("Adicionar unidade").first
            titulo_visivel = titulo.count() > 0 and titulo.is_visible()
            if url_mudou and not titulo_visivel:
                log("   Unidade criada com sucesso (URL alterada após Terminar).")
                return True
        except Exception:
            pass

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


def processar_criacao_unidade_panvel(pagina: Page, row, log=print, dry_run: bool = False) -> dict:
    """Executa todo o fluxo de criação de unidade Panvel (5 etapas do stepper).

    Fluxo:
      abrir_tela -> (idempotência) -> clicar_adicionar_unidade ->
      preencher_informacao_basica(nome_final=...) -> _clicar_proximo ->
      preencher_localizacao -> _clicar_proximo -> pular_cameras ->
      vincular_faces -> configurar_restricoes -> finalizar_unidade(dry_run)

    Retorna dict padronizado:
      {"success": bool, "skipped": bool, "changed": bool, "dryrun": bool, "message": str}
    """
    try:
        nome_player = _obter(row, COLUNA_NOME_PLAYER)
        if not nome_player:
            return {
                "success": False,
                "skipped": False,
                "changed": False,
                "message": "Coluna 'Nome do Player' ausente ou vazia na planilha.",
            }

        # Nome calculado uma única vez por linha.
        nome_final = _nome_final(row, log=log)

        # Filial/ID exigido SOMENTE quando o nome NÃO está no padrão Panvel.
        if not _nome_ja_formatado(nome_player):
            if not _obter_filial(row):
                return {
                    "success": False,
                    "skipped": False,
                    "changed": False,
                    "message": "Coluna 'Filial' (ou 'ID') ausente ou vazia na planilha.",
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

        try:
            linha_excel = int(row.get("_linha_excel", 0))
        except Exception:
            linha_excel = 0

        abrir_tela_criacao_unidade(pagina)
        log("   Tela de criação de unidade aberta.")

        # --- Idempotência: pesquisar o nome final na lista ANTES de clicar em Adicionar ---
        try:
            pagina.locator('input[placeholder="Pesquisar"]').first.wait_for(
                state="visible", timeout=TIMEOUT_ELEMENTO
            )
        except PlaywrightTimeoutError:
            pass
        try:
            campo_pesquisa = pagina.locator('input[placeholder="Pesquisar"]').first
            campo_pesquisa.click()
            campo_pesquisa.fill(nome_final)
            campo_pesquisa.press("Enter")
        except Exception:
            pass
        pagina.wait_for_timeout(1000)

        linha_existente = None
        try:
            linha_existente = escolher_linha(pagina, nome_final, timeout=4000, log=log)
        except RuntimeError as e:
            # Ambiguidade (várias parecidas, nenhuma exata) = "não existe igual": segue criando.
            log(f"   [AVISO] {e}")
            linha_existente = None

        if linha_existente is not None:
            # Só conta como existente se alguma CÉLULA tiver texto IGUAL ao nome.
            try:
                celulas = linha_existente.locator(SELETOR_CELULA).all_inner_texts()
            except Exception:
                celulas = []
            if any(chave(c) == chave(nome_final) for c in celulas):
                log("   [IDEMPOTENCIA] Unidade já existe na lista (nada criado).")
                return {
                    "success": True,
                    "skipped": True,
                    "changed": False,
                    "message": "unidade já existe (nada criado)",
                }
            # correspondência parcial não conta: segue criando

        clicar_adicionar_unidade(pagina)
        log("   Botão 'Adicionar' clicado.")

        preencher_informacao_basica(pagina, row, log=log, nome_final=nome_final)
        _clicar_proximo(pagina)

        preencher_localizacao(pagina, row, log=log)
        _clicar_proximo(pagina)

        pular_cameras(pagina, log=log)  # já clica em Próximo

        vincular_faces(pagina, row, log=log)  # já clica em Próximo ao final

        configurar_restricoes(pagina, log=log)
        salvou = finalizar_unidade(pagina, log=log, dry_run=dry_run)

        if dry_run:
            # Screenshot do estado até Restrições (Terminar NÃO clicado).
            try:
                PASTA_ERROS = Path(__file__).resolve().parent.parent / "erros"
                PASTA_ERROS.mkdir(exist_ok=True)
                destino = PASTA_ERROS / f"dryrun_L{linha_excel}.png"
                pagina.screenshot(path=str(destino))
                log(f"   [DRY-RUN] Screenshot: {destino.name}")
            except Exception:
                pass
            return {
                "success": True,
                "skipped": False,
                "changed": False,
                "dryrun": True,
                "message": "dry-run: preenchido até Restrições (Terminar NÃO clicado)",
            }

        return {
            "success": salvou,
            "skipped": False,
            "changed": salvou,
            "message": "unidade criada com sucesso" if salvou else "falha ao finalizar",
        }

    except Exception as e:
        diag = _diagnostico(pagina)
        return {
            "success": False,
            "skipped": False,
            "changed": False,
            "message": f"Erro: {e} | {diag}",
        }

