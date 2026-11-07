# =============================================================================
# planilha.py — Leitura do Excel e aplicação dos filtros do AutoFiltro
# =============================================================================
# Fluxo:
#   1. Lê a aba com pandas e cria a coluna `_linha_excel` (nº REAL da linha no Excel)
#   2. Recorta a partir da linha inicial
#   3. Aplica o AutoFiltro:
#        a) preferencial: ignora as linhas que o Excel salvou como OCULTAS
#           (funciona para qualquer tipo de filtro: lista, cor, data, texto...)
#        b) fallback: reaplica os filtros de lista em pandas
#
# Correções em relação à versão anterior:
#   - Havia duas cópias quase idênticas da lógica (carregar_planilha e
#     carregar_planilha_com_config); agora existe uma só.
#   - Não depende mais de "monkeypatch" de variáveis globais (planilha.CAMINHO_EXCEL
#     etc.): arquivo/aba/linha_inicial são parâmetros.
#   - `reset_index` fazia o log mostrar a linha errada depois de filtrar; agora
#     `_linha_excel` guarda o número real.
#   - O workbook do openpyxl agora é fechado, e o cabeçalho pode estar em outra linha.
# =============================================================================

import re
from pathlib import Path

import openpyxl
import pandas as pd

from config import ABA_EXCEL, CAMINHO_EXCEL, EXIBIR_COLUNAS, LINHA_INICIAL_EXCEL
from texto import remover_acentos, texto_celula

COL_LINHA = "_linha_excel"


def carregar_planilha(arquivo=None, aba=None, linha_inicial=None, linha_cabecalho: int = 1, log=print) -> pd.DataFrame:
    """
    Carrega a planilha respeitando a linha inicial e o AutoFiltro.

    Retorna um DataFrame com a coluna extra `_linha_excel` (linha real no Excel).
    Levanta FileNotFoundError / ValueError / KeyError com mensagem clara em vez de
    devolver um DataFrame vazio silencioso.
    """
    arquivo = Path(arquivo or CAMINHO_EXCEL)
    aba = aba or ABA_EXCEL
    linha_inicial = LINHA_INICIAL_EXCEL if linha_inicial is None else int(linha_inicial)

    if not arquivo.exists():
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {arquivo}")

    df = pd.read_excel(arquivo, sheet_name=aba, header=linha_cabecalho - 1)
    df.columns = [str(c).strip() for c in df.columns]

    if EXIBIR_COLUNAS:
        log(f"Colunas encontradas na planilha: {df.columns.tolist()}")

    # índice 0 = primeira linha logo abaixo do cabeçalho
    df[COL_LINHA] = df.index + linha_cabecalho + 1

    primeira = max(linha_inicial, linha_cabecalho + 1)
    df = df[df[COL_LINHA] >= primeira]
    log(f"Iniciando a partir da linha {primeira} do Excel ({len(df)} linhas antes do filtro).")

    df = _aplicar_autofiltro(df, arquivo, aba, linha_cabecalho, log)
    log(f"{len(df)} linha(s) serão processadas.")
    return df.reset_index(drop=True)


def carregar_planilha_com_config(arquivo, aba, coluna=None) -> pd.DataFrame:
    """Compatibilidade com o código antigo (o parâmetro `coluna` não é mais necessário)."""
    return carregar_planilha(arquivo, aba)


# ---------------------------------------------------------------------------
# AutoFiltro
# ---------------------------------------------------------------------------

def _aplicar_autofiltro(df, arquivo: Path, aba: str, linha_cabecalho: int, log) -> pd.DataFrame:
    # read_only=False é necessário para enxergar auto_filter e row_dimensions
    wb = openpyxl.load_workbook(arquivo, data_only=True)
    try:
        if aba not in wb.sheetnames:
            return df
        ws = wb[aba]
        auto_filter = ws.auto_filter
        if not auto_filter or not auto_filter.ref:
            log("Nenhum AutoFiltro ativo.")
            return df

        ocultas = {r for r, dim in ws.row_dimensions.items() if dim.hidden}
        filtros = extrair_filtros_autofiltro(ws, linha_cabecalho, log) if not ocultas else {}
    finally:
        wb.close()

    if ocultas:
        antes = len(df)
        df = df[~df[COL_LINHA].isin(ocultas)]
        log(f"[AUTOFILTRO] {len(ocultas)} linha(s) oculta(s) ignorada(s) ({antes} -> {len(df)}).")
        return df

    if filtros:
        antes = len(df)
        df = aplicar_filtros(df, filtros, log)
        log(f"[AUTOFILTRO] Após filtro de lista: {antes} -> {len(df)} linha(s).")
    return df


def extrair_filtros_autofiltro(ws, linha_cabecalho: int = 1, log=print) -> dict:
    """
    Lê os filtros de LISTA do AutoFiltro: { "Coluna": ["valor1", ...] }.
    Filtros por cor/ícone/data são ignorados com aviso.
    """
    auto_filter = ws.auto_filter
    if not auto_filter or not auto_filter.filterColumn:
        return {}

    cabecalho = [
        str(ws.cell(row=linha_cabecalho, column=col).value or "").strip()
        for col in range(1, ws.max_column + 1)
    ]
    col_inicio = _coluna_inicial_autofiltro(auto_filter.ref)

    filtros = {}
    for filter_col in auto_filter.filterColumn:
        idx = col_inicio + filter_col.colId
        if idx >= len(cabecalho):
            continue
        nome_coluna = cabecalho[idx]

        if filter_col.filters and filter_col.filters.filter:
            valores = _valores_filtro(filter_col.filters.filter)
            if valores:
                filtros[nome_coluna] = valores
                log(f"[FILTRO] Filtro detectado em '{nome_coluna}': {valores}")
        else:
            log(f"[AVISO] Coluna '{nome_coluna}' tem filtro que não é de lista (cor/intervalo/data). Será ignorado.")
    return filtros


def _valores_filtro(itens) -> list:
    valores = []
    for f in itens:
        if isinstance(f, str):
            v = f.strip()
        elif getattr(f, "val", None) is not None:
            v = str(f.val).strip()
        else:
            v = str(f).strip()
        if v:
            valores.append(v)
    return valores


def _coluna_inicial_autofiltro(ref: str) -> int:
    """'A1:Z500' -> 0 ; 'C1:F9' -> 2 (índice de coluna base 0)."""
    match = re.match(r"([A-Z]+)", ref or "")
    if not match:
        return 0
    n = 0
    for c in match.group(1):
        n = n * 26 + (ord(c) - ord("A") + 1)
    return n - 1


def _chave_filtro(valor) -> str:
    t = remover_acentos(texto_celula(valor).lower()).strip()
    if re.fullmatch(r"-?\d+\.0+", t):  # 3.0 (pandas) == 3 (filtro do Excel)
        t = t.split(".")[0]
    return t


def aplicar_filtros(df: pd.DataFrame, filtros: dict, log=print) -> pd.DataFrame:
    """Aplica filtros de lista; ignora caixa/acentos e trata 3.0 == 3."""
    mascara = pd.Series(True, index=df.index)
    for coluna, valores in filtros.items():
        if coluna not in df.columns:
            log(f"[AVISO] Coluna de filtro '{coluna}' não encontrada. Ignorando.")
            continue
        aceitos = {_chave_filtro(v) for v in valores}
        mascara &= df[coluna].apply(lambda v, a=aceitos: _chave_filtro(v) in a)
    return df[mascara]
