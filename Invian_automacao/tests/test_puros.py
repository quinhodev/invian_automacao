import pytest

from unidade_panvel import (
    _formatar_coordenada,
    _gerar_sequencial,
    _nome_ja_formatado,
    _normalizar_nome_panvel,
    remover_acentos,
    _contador_por_filial,
    _total_por_filial,
)
from texto import normalizar_espacos
from web_utils import chave


def test_nome_ja_formatado_detecta_padrao():
    assert _nome_ja_formatado("750 - Panvel Roxo MED-TV_43") is True
    assert _nome_ja_formatado("750 - Panvel Canoas MED-TV_43_01") is True
    assert _nome_ja_formatado("Loja 750 Roxo") is False
    assert _nome_ja_formatado("") is False
    assert _nome_ja_formatado(None) is False


def test_normalizar_nome_panvel_monta():
    nome = _normalizar_nome_panvel("750", "Roxo", "MED-TV_43", "")
    assert nome == "750 - Panvel Roxo MED-TV_43"

    nome2 = _normalizar_nome_panvel("972", "Canoas", "MED-TV_43", "_01")
    assert nome2 == "972 - Panvel Canoas MED-TV_43_01"


def test_normalizar_nome_panvel_sem_tag():
    nome = _normalizar_nome_panvel("750", "Roxo", "", "")
    assert nome == "750 - Panvel Roxo"


def test_gerar_sequencial_unico_nao_sufixa():
    _contador_por_filial.clear()
    _total_por_filial.clear()
    _total_por_filial["750"] = 1
    assert _gerar_sequencial("750") == ""


def test_gerar_sequencial_multiplo_sufixa():
    _contador_por_filial.clear()
    _total_por_filial.clear()
    _total_por_filial["750"] = 2
    assert _gerar_sequencial("750") == "_01"
    assert _gerar_sequencial("750") == "_02"


def test_formatar_coordenada_seis_casas():
    assert _formatar_coordenada("-30.02751") == "-30.027510"
    assert _formatar_coordenada("-51.16842") == "-51.168420"
    assert _formatar_coordenada("-30,02751") == "-30.027510"  # vírgula vira ponto


def test_remover_acentos():
    assert remover_acentos("São Paulo") == "Sao Paulo"
    assert remover_acentos("") == ""


def test_chave_normaliza():
    assert chave("Rua e Numero") == chave("rua e número")
    assert chave("  A  B  ") == "a b"
