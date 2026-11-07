# skills/faces_skill.py — Skills: Faces (Preços / Anunciantes por dia)
from playwright.sync_api import Page
import pandas as pd

from skills import skill


@skill(
    name="abrir_tela_faces",
    description="Navega para a tela de Faces (Definições → Inventário → Faces).",
    requires_auth=True,
    depends_on=["login"],
)
def abrir_tela_faces_skill(pagina: Page, **kwargs) -> None:
    from faces import abrir_tela_faces

    abrir_tela_faces(pagina)


@skill(
    name="processar_face",
    description="Processa uma face: abre Preços e ajusta 'Anunciantes por dia'.",
    requires_auth=True,
    depends_on=["login"],
)
def processar_face_skill(pagina: Page, row: pd.Series, coluna_face: str | None = None, **kwargs) -> dict:
    from processos import processar_linha_faces

    return processar_linha_faces(pagina, row, coluna_face)
