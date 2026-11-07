# =============================================================================
# web_utils.py — Helpers compartilhados de Playwright (unidades.py / faces.py)
# =============================================================================
# - primeiro_visivel: tenta uma lista de seletores e devolve o 1º visível (ou None).
#   Motivo: um Locator do Playwright NUNCA é falsy, então `if not locator:` nunca
#   dispara — o padrão antigo de "fallback" em faces.py nunca executava.
# - escolher_linha: acha a linha da tabela cujo texto é IGUAL ao nome buscado,
#   evitando abrir "Loja 10" quando se procura "Loja 1".
# =============================================================================

import re
import unicodedata

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

SELETOR_LINHA = "mat-row, .mat-mdc-row, .cdk-row, tr"
SELETOR_CELULA = "mat-cell, .mat-mdc-cell, .cdk-cell, td"


def chave(texto: str) -> str:
    """Normaliza para comparar: sem acento, minúsculo, espaços colapsados."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def primeiro_visivel(raiz, seletores, timeout: int = 3000):
    """Devolve o primeiro locator visível entre `seletores` (ou None)."""
    for seletor in seletores:
        try:
            loc = raiz.locator(seletor).first
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


def escolher_linha(pagina, nome: str, timeout: int = 10_000, log=print):
    """
    Retorna o locator da linha cuja CÉLULA é exatamente `nome` (ignorando
    acento/caixa/espaços). Se não houver exata mas só existir UMA linha parecida,
    usa essa (com aviso). Se houver várias parecidas e nenhuma exata, levanta
    RuntimeError (ambíguo) em vez de clicar na errada. Retorna None se nada achou.
    """
    candidatos = pagina.locator(SELETOR_LINHA).filter(has_text=nome)
    try:
        candidatos.first.wait_for(state="visible", timeout=timeout)
    except PlaywrightTimeoutError:
        return None

    alvo = chave(nome)
    total = candidatos.count()
    for i in range(total):
        linha = candidatos.nth(i)
        try:
            celulas = linha.locator(SELETOR_CELULA).all_inner_texts()
        except PlaywrightError:
            continue
        if any(chave(c) == alvo for c in celulas):
            return linha

    if total == 1:
        log(f"   [AVISO] Só achei correspondência parcial para '{nome}'. Usando a única linha encontrada.")
        return candidatos.first
    if total > 1:
        raise RuntimeError(
            f"'{nome}' é ambíguo: {total} linhas parecidas e nenhuma exatamente igual. "
            "Ajuste o nome na planilha."
        )
    return None
