# skills/processing_skill.py — Skill: processar uma linha (Unidades/Horário)
# Delegamos para processos.py: a lógica existe em um lugar só.
from playwright.sync_api import Page
import pandas as pd

from skills import skill


@skill(
    name="processar_linha",
    description="Processa uma linha: pesquisa player, seleciona horário, salva.",
    requires_auth=True,
    depends_on=["login"],
)
def processar_linha_skill(pagina: Page, row: pd.Series, coluna_player: str | None = None, **kwargs) -> dict:
    from processos import processar_linha_unidades

    return processar_linha_unidades(pagina, row, coluna_player)
