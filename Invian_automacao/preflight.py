# =============================================================================
# preflight.py — Validação da planilha ANTES de abrir o navegador (modo panvel)
# =============================================================================
# Chamado por core.executar_automacao DEPOIS de carregar a planilha e ANTES de
# criar o navegador. Levanta ValueError listando TODOS os problemas, cada um
# com o número da linha real do Excel (coluna _linha_excel).
# =============================================================================

from config import (
    COLUNA_CIDADE,
    COLUNA_FILIAL,
    COLUNA_ID,
    COLUNA_LATITUDE,
    COLUNA_LONGITUDE,
    COLUNA_NOME_PLAYER,
    COLUNA_RUA_NUMERO,
    LOCALIZACAO_PADRAO,
)
from planilha import COL_LINHA
from texto import texto_celula
from web_utils import chave


def _col_real(df, nome: str):
    """Acha a coluna real do DataFrame ignorando acento/caixa/espaços."""
    mapa = {chave(c): c for c in df.columns}
    return mapa.get(chave(nome))


def _numero(valor: str):
    """Converte texto para float (vírgula -> ponto). Devolve None se não numérico."""
    if not valor:
        return None
    try:
        return float(valor.replace(",", "."))
    except ValueError:
        return None


def validar_panvel(df, log=print) -> None:
    """Valida o DataFrame para o modo "panvel" ANTES de criar o navegador.

    Levanta ValueError listando TODOS os problemas encontrados, cada qual com o
    número da linha real do Excel (coluna _linha_excel).

    Problemas verificados:
      - colunas ausentes: Nome do Player, Rua e Número, Cidade, Latitude,
        Longitude e (Filial ou ID)
      - por linha: nome, rua ou cidade vazios; latitude/longitude vazias, não
        numéricas, fora de -90..90 / -180..180
      - linhas repetidas (mesmo Nome do Player + mesma Filial/ID)

    LOCALIZACAO_PADRAO vazio => apenas log de AVISO (não é erro).
    """
    problemas = []

    # --- Colunas ausentes ---------------------------------------------------
    col_nome = _col_real(df, COLUNA_NOME_PLAYER)
    col_rua = _col_real(df, COLUNA_RUA_NUMERO)
    col_cidade = _col_real(df, COLUNA_CIDADE)
    col_lat = _col_real(df, COLUNA_LATITUDE)
    col_lon = _col_real(df, COLUNA_LONGITUDE)
    col_filial = _col_real(df, COLUNA_FILIAL) or _col_real(df, COLUNA_ID)

    faltando = []
    if col_nome is None:
        faltando.append(COLUNA_NOME_PLAYER)
    if col_rua is None:
        faltando.append(COLUNA_RUA_NUMERO)
    if col_cidade is None:
        faltando.append(COLUNA_CIDADE)
    if col_lat is None:
        faltando.append(COLUNA_LATITUDE)
    if col_lon is None:
        faltando.append(COLUNA_LONGITUDE)
    if col_filial is None:
        faltando.append(f"{COLUNA_FILIAL} (ou {COLUNA_ID})")
    if faltando:
        problemas.append(
            "Coluna(s) ausente(s) na planilha: " + ", ".join(faltando)
        )

    # LOCALIZACAO_PADRAO vazio => apenas aviso (não é erro; item 1d trata no select)
    if not LOCALIZACAO_PADRAO:
        log(
            "   [AVISO] LOCALIZACAO_PADRAO vazio em config.py: será usada a 1ª opção "
            "do select 'Localização' (não é erro)."
        )

    # Se faltam colunas essenciais, não há como validar linha a linha; levanta agora.
    if problemas:
        raise ValueError("\n".join(problemas))

    # --- Por linha ----------------------------------------------------------
    nomes_vistos = set()
    for _, row in df.iterrows():
        linha = int(row[COL_LINHA])

        nome = texto_celula(row[col_nome]) if col_nome else ""
        rua = texto_celula(row[col_rua]) if col_rua else ""
        cidade = texto_celula(row[col_cidade]) if col_cidade else ""
        lat_raw = texto_celula(row[col_lat]) if col_lat else ""
        lon_raw = texto_celula(row[col_lon]) if col_lon else ""
        filial = texto_celula(row[col_filial]) if col_filial else ""

        if not nome:
            problemas.append(f"Linha {linha}: 'Nome do Player' vazio.")
        if not rua:
            problemas.append(f"Linha {linha}: 'Rua e Número' vazio.")
        if not cidade:
            problemas.append(f"Linha {linha}: 'Cidade' vazio.")

        lat = _numero(lat_raw)
        if not lat_raw:
            problemas.append(f"Linha {linha}: 'Latitude' vazio.")
        elif lat is None:
            problemas.append(f"Linha {linha}: 'Latitude' não numérica ('{lat_raw}').")
        elif lat < -90 or lat > 90:
            problemas.append(f"Linha {linha}: 'Latitude' fora de -90..90 ({lat}).")

        lon = _numero(lon_raw)
        if not lon_raw:
            problemas.append(f"Linha {linha}: 'Longitude' vazio.")
        elif lon is None:
            problemas.append(f"Linha {linha}: 'Longitude' não numérica ('{lon_raw}').")
        elif lon < -180 or lon > 180:
            problemas.append(f"Linha {linha}: 'Longitude' fora de -180..180 ({lon}).")

        # Linhas repetidas: mesmo Nome do Player + mesma Filial/ID
        chave_duplicata = (chave(nome), chave(filial))
        if chave_duplicata in nomes_vistos:
            problemas.append(
                f"Linha {linha}: linha repetida (Nome do Player='{nome}' + "
                f"Filial/ID='{filial}')."
            )
        nomes_vistos.add(chave_duplicata)

    if problemas:
        raise ValueError("\n".join(problemas))