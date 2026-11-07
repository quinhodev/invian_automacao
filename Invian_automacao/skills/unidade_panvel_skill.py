# skills/unidade_panvel_skill.py — Skill: Criação de Unidade Panvel
from playwright.sync_api import Page
import pandas as pd

from skills import skill


@skill(
    name="abrir_tela_criacao_unidade",
    description="Navega para a tela de criação de unidade no sistema Invian.",
    requires_auth=True,
    depends_on=["login"],
)
def abrir_tela_criacao_unidade_skill(pagina: Page, **kwargs) -> None:
    from unidade_panvel import abrir_tela_criacao_unidade

    abrir_tela_criacao_unidade(pagina)
    print("[OK] [skill:abrir_tela_criacao_unidade] Evidência: tela de criação de unidade aberta.")


@skill(
    name="processar_linha_panvel",
    description="Processa uma linha: cria unidade Panvel preenchendo Abas 1 a 4 e salvando.",
    requires_auth=True,
    depends_on=["login"],
)
def processar_linha_panvel_skill(pagina: Page, row: pd.Series, coluna: str | None = None, **kwargs) -> dict:
    from processos import processar_linha_panvel

    return processar_linha_panvel(pagina, row, coluna)