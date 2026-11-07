# =============================================================================
# .agents/main_agent.py — Pipeline "agêntico" usando o registro de skills
# =============================================================================
# Antes: `from .config import ...` (módulo inexistente → ImportError), o código
# tratava o dict retornado por execute_skill como se fosse o navegador/página, e
# chamava processar_linha com row=None. Agora usa registry.call() (devolve o valor
# real) e percorre as linhas da planilha.
#
# Uso:  python .agents/main_agent.py
# =============================================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from planilha import carregar_planilha  # noqa: E402
from skills import discover_skills, registry  # noqa: E402


def run_agentic_pipeline(arquivo=None, aba=None, linha_inicial=None) -> dict:
    discover_skills()
    df = carregar_planilha(arquivo, aba, linha_inicial)
    evidencias, alteradas = [], 0

    with sync_playwright() as pw:
        navegador = registry.call("criar_navegador", pw=pw)
        try:
            contexto = registry.call("criar_contexto", navegador=navegador)
            pagina = registry.call("criar_pagina", contexto=contexto)
            registry.call("login", pagina=pagina)
            for _, row in df.iterrows():
                registry.call("abrir_tela_unidades", pagina=pagina)
                res = registry.call("processar_linha", pagina=pagina, row=row)
                alteradas += 1 if res.get("changed") else 0
                evidencias.append(f"Linha {row['_linha_excel']}: {res.get('message')}")
        finally:
            navegador.close()

    return {"success": True, "alteradas": alteradas, "evidence": evidencias}


if __name__ == "__main__":
    print(run_agentic_pipeline())
