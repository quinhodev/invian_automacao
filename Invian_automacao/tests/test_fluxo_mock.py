import os
import time

import pandas as pd
import pytest
from pathlib import Path

from unidade_panvel import (
    processar_criacao_unidade_panvel,
    _contador_por_filial,
    _total_por_filial,
)

PASTA_ERROS = str(Path(__file__).resolve().parent.parent / "erros")

NOME_PLAYER = "Loja Teste"
FILIAL = "750"
NOME_FINAL = f"{FILIAL} - Panvel {NOME_PLAYER} MED-TV_43"


def _row(linha=2, nome=NOME_PLAYER, filial=FILIAL):
    return pd.Series({
        "Nome do Player": nome,
        "Filial": filial,
        "Rua e Número": "Rua X, 100",
        "Cidade": "Porto Alegre",
        "Latitude": "-30.02751",
        "Longitude": "-51.16842",
        "_linha_excel": linha,
    })


@pytest.fixture(autouse=True)
def reset_sequenciais():
    """Zera os contadores de sequencial entre testes para nomes determinísticos."""
    _contador_por_filial.clear()
    _total_por_filial.clear()
    _total_por_filial[FILIAL] = 1  # 1 unidade na filial => sequencial vazio


def _executar(page, url, row, dry_run=False):
    page.goto(url, wait_until="domcontentloaded")
    t0 = time.time()
    res = processar_criacao_unidade_panvel(page, row, log=print, dry_run=dry_run)
    dur = time.time() - t0
    return res, dur


def test_localizacao_vazia_usa_primeira_opcao(page, panvel_url):
    """LOCALIZACAO_PADRAO vazio => usa a 1ª opção ('Interna') e cria com sucesso."""
    res, _ = _executar(page, panvel_url, _row())
    assert res["success"] is True
    assert res["skipped"] is False
    valor = page.evaluate("document.getElementById('f-localizacao').value")
    assert valor == "Interna", f"esperado 'Interna', obtido {valor!r}"
    terminar = page.evaluate("window.__terminar")
    assert terminar == 1


def test_erro_1_sucesso_false_menos_8s(page, panvel_url):
    """?erro=1 => Terminar exibe 'Erro ao salvar unidade', form continua, success False em < 8s."""
    res, dur = _executar(page, panvel_url + "?erro=1", _row())
    assert res["success"] is False
    assert dur < 8, f"demorou {dur:.2f}s"
    erro_visivel = page.evaluate("document.getElementById('erro-msg').style.display !== 'none'")
    assert erro_visivel is True, "mensagem de erro não apareceu"
    terminar = page.evaluate("window.__terminar")
    assert terminar == 1


def test_existe_skipped_true(page, panvel_url):
    """?existe=<nome> => idempotência detecta unidade igual, skipped True, Terminar não clicado."""
    res, _ = _executar(page, panvel_url + f"?existe={NOME_FINAL}", _row())
    assert res["success"] is True
    assert res["skipped"] is True
    assert "já existe" in res["message"]
    terminar = page.evaluate("window.__terminar")
    assert terminar == 0


def test_parecida_nao_conta_existente(page, panvel_url):
    """?parecida=<nome> => linha '_X' é correspondência parcial, NÃO conta como existente, segue criando."""
    res, _ = _executar(page, panvel_url + f"?parecida={NOME_FINAL}", _row())
    assert res["success"] is True
    assert res["skipped"] is False
    terminar = page.evaluate("window.__terminar")
    assert terminar == 1


def test_dry_run(page, panvel_url):
    """dry-run => preenche até Restrições, não clica Terminar, dryrun True, screenshot gerado."""
    res, _ = _executar(page, panvel_url, _row(), dry_run=True)
    assert res["dryrun"] is True
    assert res["success"] is True
    assert res["changed"] is False
    assert "Terminar NÃO clicado" in res["message"]
    terminar = page.evaluate("window.__terminar")
    assert terminar == 0
    esperado = os.path.join(PASTA_ERROS, "dryrun_L2.png")
    assert os.path.exists(esperado), f"screenshot não gerado: {esperado}"
