# =============================================================================
# processos.py — O que fazer com UMA linha da planilha (fonte única de verdade)
# =============================================================================
# Usado por core.py (CLI/GUI) e pelas skills. Antes a mesma lógica existia
# duplicada em main.py, gui/automation_runner.py e skills/*.
#
# Cada função abre a tela necessária por conta própria, então uma linha que falhou
# nunca "contamina" a próxima. Retorna sempre um dict:
#   success (bool) | skipped (bool) | changed (bool) | message (str)
# =============================================================================

from config import COLUNA_HORARIO, COLUNA_PLAYER, COLUNAS_FACE, VALOR_ANUNCIANTES_POR_DIA
from horario import mapear_horario
from texto import texto_celula


def obter_nome_player(row, coluna_player=None) -> str:
    coluna = coluna_player or COLUNA_PLAYER
    return texto_celula(row[coluna]) if coluna in row.index else ""


def obter_nome_face(row, coluna=None) -> str:
    for col in ([coluna] if coluna else COLUNAS_FACE):
        if col in row.index:
            valor = texto_celula(row[col])
            if valor:
                return valor
    return ""


def processar_linha_unidades(pagina, row, coluna_player=None, log=print, coluna_horario=None) -> dict:
    from unidades import (
        abrir_tela_unidades,
        pesquisar_e_abrir_player,
        salvar_alteracoes,
        selecionar_horario,
    )

    nome = obter_nome_player(row, coluna_player)
    if not nome:
        return {"success": True, "skipped": True, "message": "player vazio"}

    horario_excel = texto_celula(row[coluna_horario or COLUNA_HORARIO])
    if not horario_excel:
        # Antes: horário vazio virava "Fixo" e sobrescrevia o cadastro sem avisar.
        return {"success": True, "skipped": True, "message": "horário vazio na planilha (nada alterado)"}

    horario = mapear_horario(horario_excel)
    log(f"   Horário esperado: {horario}")

    abrir_tela_unidades(pagina)
    pesquisar_e_abrir_player(pagina, nome)

    if not selecionar_horario(pagina, horario):
        return {"success": True, "changed": False, "message": "horário já estava correto"}
    if salvar_alteracoes(pagina):
        return {"success": True, "changed": True, "message": "horário atualizado e salvo"}
    return {"success": True, "changed": False, "message": "sem alteração pendente"}


def processar_linha_faces(pagina, row, coluna_face=None, log=print, coluna_horario=None, valor_anunciantes=None) -> dict:
    from faces import processar_face

    nome = obter_nome_face(row, coluna_face)
    if not nome:
        return {"success": True, "skipped": True, "message": "nome da face não encontrado"}

    valor = valor_anunciantes if valor_anunciantes is not None else VALOR_ANUNCIANTES_POR_DIA
    r = processar_face(pagina, nome, valor, log=log)
    return {
        "success": r["success"],
        "changed": r.get("changed", False),
        "message": r["message"],
        "evidence": r.get("evidence", []),
    }


def processar_linha_panvel(pagina, row, coluna=None, log=print, coluna_horario=None, dry_run=False) -> dict:
    from unidade_panvel import processar_criacao_unidade_panvel

    # O contador de sequencial (_01, _02) é preparado UMA vez por execução em core.py
    # (preparar_sequenciais); aqui NÃO pode ser zerado a cada linha.
    nome = obter_nome_player(row, coluna)
    if not nome:
        return {"success": True, "skipped": True, "message": "nome do player vazio"}

    log(f"   Criando unidade Panvel para: {nome}")
    r = processar_criacao_unidade_panvel(pagina, row, log=log, dry_run=dry_run)
    return {
        "success": r["success"],
        "skipped": r.get("skipped", False),
        "changed": r.get("changed", False),
        "dryrun": r.get("dryrun", False),
        "message": r["message"],
    }
