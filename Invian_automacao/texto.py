# =============================================================================
# texto.py — Funções de limpeza e normalização de texto
# =============================================================================
# Centraliza toda a manipulação de strings usada pelo projeto.
# Não depende de nenhum outro módulo interno.
# =============================================================================

import re
import unicodedata


# ---------------------------------------------------------------------------
# Conversão básica
# ---------------------------------------------------------------------------

def texto_celula(valor) -> str:
    """Converte valor vindo do Excel (ou qualquer fonte) para texto limpo."""
    try:
        import pandas as pd
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor).strip()

    if texto.lower() in {"nan", "nat", "none"}:
        return ""

    return texto


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------

def remover_acentos(texto: str) -> str:
    """Remove acentos e diacríticos de um texto."""
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_espacos(texto: str) -> str:
    """Normaliza espaços em branco e separadores | no texto."""
    texto = texto_celula(texto)
    texto = re.sub(r"\s*\|\s*", " | ", texto)
    texto = re.sub(r"(?:\s*\|\s*){2,}", " | ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().strip("|").strip()


def limpar_quebras_excel(texto: str) -> str:
    """
    Converte quebras de linha reais e códigos escapados do Excel em separador |.

    Exemplo de entrada:  'Dom de 07:00 a 19:00_x000D_ Seg, Ter...'
    Exemplo de saída:    'Dom de 07:00 a 19:00 | Seg, Ter...'
    """
    texto = texto_celula(texto)

    # Quebras reais
    texto = texto.replace("\r\n", " | ").replace("\n", " | ").replace("\r", " | ")

    # Códigos XML/Excel de quebra de linha ou tabulação
    texto = re.sub(r"_x005[fF]_x000[dD]_", " | ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"_x000[dD]_", " | ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"_x000[aA]_", " | ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"_x0009_",    " ",   texto, flags=re.IGNORECASE)

    # Literais \r \n escapados como string
    texto = texto.replace("\\r\\n", " | ").replace("\\n", " | ").replace("\\r", " | ")

    return normalizar_espacos(texto)


# ---------------------------------------------------------------------------
# Padronização de horas e intervalos
# ---------------------------------------------------------------------------

def padronizar_horas_no_texto(texto: str) -> str:
    """Padroniza 7:00, 07h00, 7h e 07:00:00 para 07:00."""

    def repl(m):
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"

    texto = re.sub(r"\b(\d{1,2})\s*h\s*(\d{2})\b", repl, texto, flags=re.IGNORECASE)
    # "7h" / "22h" sozinhos -> 07:00 / 22:00
    texto = re.sub(r"\b(\d{1,2})\s*h\b(?!\s*\d)", lambda m: f"{int(m.group(1)):02d}:00", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b", repl, texto)
    return texto


def padronizar_intervalos(texto: str) -> str:
    """
    Padroniza 'das 07:00 às 22:30' e '07:00-22:30' -> 'de 07:00 a 22:30'.

    O separador só é trocado quando está ENTRE dois horários. A versão antiga
    trocava qualquer ' as ' / ' - ' antes de uma hora (ex.: 'Qua as 07:00')
    e não tratava '07:00-22:00' sem espaços.
    """
    texto = re.sub(r"\b(das|do)\s+(\d{2}:\d{2})", r"de \2", texto, flags=re.IGNORECASE)
    texto = re.sub(
        r"(\d{2}:\d{2})\s*(?:às|as|até|ate|-)\s*(\d{2}:\d{2})",
        r"\1 a \2",
        texto,
        flags=re.IGNORECASE,
    )
    return texto


# ---------------------------------------------------------------------------
# Pipeline completo de normalização
# ---------------------------------------------------------------------------

def normalizar_horario_texto(texto: str) -> str:
    """Limpa e padroniza o texto do horário sem perder os dias da semana."""
    texto = limpar_quebras_excel(texto)
    texto = texto.replace("–", "-").replace("—", "-")
    texto = padronizar_horas_no_texto(texto)
    texto = padronizar_intervalos(texto)
    return normalizar_espacos(texto)


def normalizar_para_comparar(texto: str) -> str:
    """Normaliza para comparação: sem acento, minúsculo, espaços uniformes."""
    texto = normalizar_horario_texto(texto)
    texto = remover_acentos(texto.lower())
    texto = re.sub(r"[;,]", " ", texto)
    texto = re.sub(r"\s*\|\s*", " | ", texto)
    texto = re.sub(r"(?:\s*\|\s*){2,}", " | ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().strip("|").strip()
