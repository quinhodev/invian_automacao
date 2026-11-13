import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

# Adiciona a raiz do pacote ao path para importar unidade_panvel / config
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MOCK_DIR = ROOT / "mock_invian"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mock_url():
    """Sobe um servidor HTTP local servindo mock_invian/ e devolve a URL base."""
    import urllib.request

    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", str(MOCK_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    # Aguarda o servidor ficar pronto (tenta conectar por até 10 s)
    pronto = False
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{base}/index.html", timeout=0.5)
            pronto = True
            break
        except Exception:
            time.sleep(0.1)
    if not pronto:
        proc.terminate()
        raise RuntimeError(f"Servidor mock não ficou pronto em {base}")
    try:
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


@pytest.fixture
def page(mock_url):
    """Cria uma página Chromium nova para cada teste."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()


@pytest.fixture
def panvel_url(monkeypatch, mock_url):
    """
    Aponta unidade_panvel.URL_CRIACAO_UNIDADE para o mock e devolve a URL base.
    Isso faz abrir_tela_criacao_unidade navegar para o simulador em vez do Invian real.
    """
    import unidade_panvel

    url = f"{mock_url}/index.html"
    monkeypatch.setattr(unidade_panvel, "URL_CRIACAO_UNIDADE", url)
    return url
