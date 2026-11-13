import pandas as pd
import pytest
from preflight import validar_panvel


def _df(rows):
    """Constrói um DataFrame com a coluna real do Excel (_linha_excel)."""
    df = pd.DataFrame(rows)
    df["_linha_excel"] = list(range(2, 2 + len(rows)))
    return df


def _valido():
    return _df([{
        "Nome do Player": "Player 1",
        "Rua e Número": "Rua X, 100",
        "Cidade": "Porto Alegre",
        "Latitude": "-30.03",
        "Longitude": "-51.17",
        "Filial": "750",
    }])


def test_valido_nao_levanta_erro():
    validar_panvel(_valido())


def test_coluna_nome_ausente():
    df = _df([{"Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "Nome do Player" in str(exc.value)


def test_coluna_rua_ausente():
    df = _df([{"Nome do Player": "P", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "Rua e Número" in str(exc.value)


def test_coluna_cidade_ausente():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "Cidade" in str(exc.value)


def test_coluna_latitude_ausente():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "Latitude" in str(exc.value)


def test_coluna_longitude_ausente():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "Longitude" in str(exc.value)


def test_coluna_filial_id_ausente():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "Filial" in str(exc.value) or "ID" in str(exc.value)


def test_linha_nome_vazio():
    df = _df([{"Nome do Player": "", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    msg = str(exc.value)
    assert "Nome do Player" in msg and "Linha 2" in msg


def test_linha_rua_vazio():
    df = _df([{"Nome do Player": "P", "Rua e Número": "", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    msg = str(exc.value)
    assert "Rua e Número" in msg and "Linha 2" in msg


def test_linha_cidade_vazio():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    msg = str(exc.value)
    assert "Cidade" in msg and "Linha 2" in msg


def test_linha_latitude_vazia():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    msg = str(exc.value)
    assert "Latitude" in msg and "Linha 2" in msg


def test_linha_latitude_nao_numerica():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "abc", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "não numérica" in str(exc.value) and "Linha 2" in str(exc.value)


def test_linha_latitude_fora_range():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-91.0", "Longitude": "-51.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "fora de -90..90" in str(exc.value) and "Linha 2" in str(exc.value)


def test_linha_longitude_vazia():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    msg = str(exc.value)
    assert "Longitude" in msg and "Linha 2" in msg


def test_linha_longitude_nao_numerica():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "xyz", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "não numérica" in str(exc.value) and "Linha 2" in str(exc.value)


def test_linha_longitude_fora_range():
    df = _df([{"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "200.0", "Filial": "1"}])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "fora de -180..180" in str(exc.value) and "Linha 2" in str(exc.value)


def test_linha_repetida_mesmo_nome_e_filial():
    df = _df([
        {"Nome do Player": "P", "Rua e Número": "Rua X", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"},
        {"Nome do Player": "P", "Rua e Número": "Rua Y", "Cidade": "POA", "Latitude": "-30.0", "Longitude": "-51.0", "Filial": "1"},
    ])
    with pytest.raises(ValueError) as exc:
        validar_panvel(df)
    assert "repetida" in str(exc.value) and "Linha 3" in str(exc.value)


def test_localizacao_padrao_vazio_nao_erro(monkeypatch):
    import config
    monkeypatch.setattr(config, "LOCALIZACAO_PADRAO", "")
    # Não deve levantar ValueError (apenas log de aviso)
    validar_panvel(_valido())
