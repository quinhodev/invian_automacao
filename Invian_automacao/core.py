# =============================================================================
# core.py — Motor único da automação (usado pelo CLI e pela GUI)
# =============================================================================
# Antes existiam DOIS motores quase iguais (main.rodar_automacao_cli e
# gui/automation_runner), e eles divergiam: o CLI continuava após erro numa linha,
# a GUI abortava tudo. Agora:
#   - erro em uma linha NÃO derruba as outras (registra, tira print e segue)
#   - navegador fechado/desconectado aborta a execução com mensagem clara
#   - botão "Parar" é respeitado entre linhas
#   - sempre gera relatório CSV (mesmo se parar/abortar no meio)
#   - cada tela é aberta dentro da função da linha (sem navegar duas vezes)
# =============================================================================

import csv
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

import config as cfg
from login import fazer_login
from navegador import criar_contexto, criar_navegador, criar_pagina
from planilha import COL_LINHA, carregar_planilha
from web_utils import chave
from processos import (
    obter_nome_face,
    obter_nome_player,
    processar_linha_faces,
    processar_linha_panvel,
    processar_linha_unidades,
)

MODOS = ("unidades", "faces", "ambos", "panvel")
PASTA_BASE = Path(__file__).parent
PASTA_ERROS = PASTA_BASE / "erros"
PASTA_RELATORIOS = PASTA_BASE / "relatorios"


def _achar(df, candidatas):
    """Acha a coluna real do DataFrame ignorando maiúsculas/minúsculas e acentos."""
    mapa = {chave(c): c for c in df.columns}
    for cand in candidatas:
        if cand and chave(cand) in mapa:
            return mapa[chave(cand)]
    return None


def _resolver_colunas(df, modo, coluna, coluna_horario):
    """
    Resolve os nomes reais das colunas (aceita 'Horário de funcionamento' no lugar de
    'Horário de Funcionamento' etc.). Retorna (col_nome, col_horario) ou levanta
    ValueError dizendo o que faltou e quais colunas existem.
    """
    col_nome, col_horario, faltando = None, None, []

    if modo in ("unidades", "ambos"):
        col_nome = _achar(df, [coluna or cfg.COLUNA_PLAYER])
        col_horario = _achar(df, [coluna_horario or cfg.COLUNA_HORARIO])
        if col_nome is None:
            faltando.append(coluna or cfg.COLUNA_PLAYER)
        if col_horario is None:
            faltando.append(coluna_horario or cfg.COLUNA_HORARIO)
    if modo in ("faces", "ambos") and col_nome is None:
        col_nome = _achar(df, [coluna] if coluna else cfg.COLUNAS_FACE)
        if col_nome is None:
            faltando.append(coluna or " ou ".join(cfg.COLUNAS_FACE))
    if modo == "panvel" and col_nome is None:
        col_nome = _achar(df, [coluna] if coluna else [cfg.COLUNA_NOME_PLAYER])
        if col_nome is None:
            faltando.append(coluna or cfg.COLUNA_NOME_PLAYER)

    if faltando:
        raise ValueError(
            f"Coluna(s) não encontrada(s) na planilha: {faltando}. "
            f"Colunas disponíveis: {[c for c in df.columns if c != COL_LINHA]}. "
            "Escolha as colunas na GUI ou use --coluna / --coluna-horario no CLI."
        )
    return col_nome, col_horario


def _tirar_print(pagina, fase, linha, log):
    try:
        PASTA_ERROS.mkdir(exist_ok=True)
        destino = PASTA_ERROS / f"erro_{fase}_L{linha}_{datetime.now():%H%M%S}.png"
        pagina.screenshot(path=str(destino))
        log(f"   [PRINT] Print do erro: {destino.name}")
    except Exception:
        pass


def _salvar_relatorio(resultados, log):
    if not resultados:
        return None
    PASTA_RELATORIOS.mkdir(exist_ok=True)
    destino = PASTA_RELATORIOS / f"relatorio_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["linha_excel", "fase", "nome", "status", "mensagem"], delimiter=";")
        w.writeheader()
        w.writerows(resultados)
    log(f"[RELATORIO] Relatório salvo em: {destino}")
    return destino


def _status(res):
    if res.get("skipped"):
        return "pulado"
    if not res.get("success"):
        return "erro"
    return "alterado" if res.get("changed") else "ja_correto"


def _rodar_fase(pagina, navegador, df, fase, coluna, col_horario, log, parar, resultados, valor_anunciantes=None):
    """Processa todas as linhas de uma fase. Retorna False se o navegador morreu."""
    if fase == "unidades":
        funcao, obter_nome = processar_linha_unidades, lambda r: obter_nome_player(r, coluna)
    elif fase == "panvel":
        funcao, obter_nome = processar_linha_panvel, lambda r: obter_nome_player(r, coluna)
    else:
        funcao, obter_nome = processar_linha_faces, lambda r: obter_nome_face(r, coluna)

    log("=" * 50)
    log(f"FASE: {fase.upper()} ({len(df)} linha(s))")
    log("=" * 50)

    for _, row in df.iterrows():
        if parar is not None and parar.is_set():
            raise InterruptedError("Parado pelo usuário")

        linha = int(row[COL_LINHA])
        nome = obter_nome(row)
        log(f"\nLinha {linha}: {nome or '(vazio)'}")

        try:
            if fase == "faces":
                res = funcao(pagina, row, coluna, log, col_horario, valor_anunciantes=valor_anunciantes)
            else:
                res = funcao(pagina, row, coluna, log, col_horario)
        except Exception as e:
            res = {"success": False, "message": f"Erro: {e}"}
            _tirar_print(pagina, fase, linha, log)

        status = _status(res)
        icone = {"alterado": "[OK]", "ja_correto": "[INFO]", "pulado": "[SKIP]", "erro": "[ERRO]"}[status]
        log(f"   {icone} {res.get('message', '')}")
        resultados.append(
            {"linha_excel": linha, "fase": fase, "nome": nome, "status": status,
             "mensagem": str(res.get("message", "")).replace("\n", " ")[:300]}
        )

        if pagina.is_closed() or not navegador.is_connected():
            log("[ERRO] Navegador fechado. Encerrando automação.")
            return False
    return True


def executar_automacao(
    modo="unidades",
    arquivo=None,
    aba=None,
    linha_inicial=None,
    headless=None,
    coluna=None,
    coluna_horario=None,
    email=None,
    senha=None,
    linha_cabecalho=1,
    valor_anunciantes=None,
    log=print,
    parar=None,
) -> dict:
    """
    Roda a automação completa. `parar` é um threading.Event opcional.

    `valor_anunciantes` define a quantidade de anunciantes por dia usada na fase
    "faces" (quando informado, sobrescreve o VALOR_ANUNCIANTES_POR_DIA do config.py).

    Retorna: {"contagem": {status: n}, "relatorio": Path|None,
              "interrompido": bool, "navegador_fechou": bool}
    Levanta exceção só para problemas de configuração/login (arquivo, coluna, senha).
    """
    if modo not in MODOS:
        raise ValueError(f"Modo inválido: {modo}. Use um de {MODOS}.")

    arquivo = arquivo or cfg.CAMINHO_EXCEL
    aba = aba or cfg.ABA_EXCEL

    df = carregar_planilha(arquivo, aba, linha_inicial, linha_cabecalho, log=log)
    col_nome, col_horario = _resolver_colunas(df, modo, coluna, coluna_horario)
    log(f"Colunas usadas -> nome: '{col_nome}'" + (f" | horario: '{col_horario}'" if col_horario else ""))
    if df.empty:
        log("Planilha sem linhas para processar. Encerrando.")
        return {"contagem": {}, "relatorio": None, "interrompido": False, "navegador_fechou": False}

    fases = ["unidades", "faces"] if modo == "ambos" else [modo]
    resultados, interrompido, navegador_fechou = [], False, False

    if "panvel" in fases:
        from unidade_panvel import preparar_sequenciais
        preparar_sequenciais(df)

    with sync_playwright() as pw:
        navegador = criar_navegador(pw, headless)
        try:
            pagina = criar_pagina(criar_contexto(navegador))
            log("Fazendo login...")
            fazer_login(pagina, email, senha)
            log("Login realizado com sucesso")

            try:
                for fase in fases:
                    if not _rodar_fase(pagina, navegador, df, fase, col_nome, col_horario, log, parar, resultados, valor_anunciantes=valor_anunciantes):
                        navegador_fechou = True
                        break
            except InterruptedError:
                interrompido = True
                log("[PARADO] Automação interrompida pelo usuário.")
        finally:
            try:
                if navegador.is_connected():
                    navegador.close()
            except Exception:
                pass
            relatorio = _salvar_relatorio(resultados, log)

    contagem = {}
    for r in resultados:
        contagem[r["status"]] = contagem.get(r["status"], 0) + 1
    log("\nResumo: " + (", ".join(f"{k}={v}" for k, v in sorted(contagem.items())) or "nenhuma linha processada"))
    log("Automação finalizada.")
    return {
        "contagem": contagem,
        "relatorio": relatorio,
        "interrompido": interrompido,
        "navegador_fechou": navegador_fechou,
    }
