# =============================================================================
# config.py — Configurações e constantes globais do projeto
# =============================================================================
# Altere aqui as configurações sem precisar tocar nos outros arquivos.
# =============================================================================

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
CAMINHO_EXCEL = Path(__file__).with_name("bancodeDados.xlsx")

# ---------------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------------
ABA_EXCEL = "ONSIGN"

COLUNA_PLAYER   = "Nome do Player"
COLUNA_HORARIO  = "Horário de Funcionamento"

# Colunas candidatas para o nome da Face (modo "faces"), em ordem de prioridade.
COLUNAS_FACE = ["Nome da Face", "Face", "Unidade", "Tipo de Face", "Nome"]

# Valor que a automação de Faces deve deixar em "Anunciantes por dia".
VALOR_ANUNCIANTES_POR_DIA = 12

# ---------------------------------------------------------------------------
# Colunas esperadas na planilha para criação de unidade Panvel
# ---------------------------------------------------------------------------
COLUNA_ID           = "ID"
COLUNA_FILIAL       = "Filial"
COLUNA_NOME_PLAYER  = "Nome do Player"
COLUNA_RUA_NUMERO   = "Rua e Número"
COLUNA_CIDADE       = "Cidade"
COLUNA_ESTADO       = "Estado"
COLUNA_LATITUDE     = "Latitude"
COLUNA_LONGITUDE    = "Longitude"

# ---------------------------------------------------------------------------
# Regras de nomenclatura Panvel
# ---------------------------------------------------------------------------
# Tags por tipo de mídia
TAG_NUC_PADRAO = "MED-TV_43"   # Tela Padrão / NUC de Sinalização
TAG_SELF_CHECKOUT = "MED-TV_21"  # Tela de Self-Checkout

# Prefixo do nome padronizado Panvel
PREFIXO_PANVEL = "Panvel"

# ---------------------------------------------------------------------------
# Linha inicial
# ---------------------------------------------------------------------------
# Número da linha do Excel onde a automação começa (linha 1 = cabeçalho).
# Exemplo: 24 → começa na linha 24 da planilha.
LINHA_INICIAL_EXCEL = 150

# ---------------------------------------------------------------------------
# Navegador
# ---------------------------------------------------------------------------
# True  → navegador roda em segundo plano (invisível)
# False → navegador abre na tela (visível, útil para depuração)
HEADLESS = False

# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
# True  → exibe a lista de colunas da planilha ao iniciar
# False → oculta essa listagem
EXIBIR_COLUNAS = False

# ---------------------------------------------------------------------------
# URLs do sistema
# ---------------------------------------------------------------------------
URL_HOME            = "https://web.invian.net/home"
URL_UNIDADES        = "https://web.invian.net/settings/inventory/units"
URL_FACES           = "https://web.invian.net/settings/inventory/faces"
URL_CRIACAO_UNIDADE = "https://web.invian.net/settings/inventory/units"

# ---------------------------------------------------------------------------
# Padrões de criação de unidade (Aba 1 — Informação Básica)
# ---------------------------------------------------------------------------
# LOCALIZACAO_PADRAO: valor a ser selecionado no campo "Localização" (select).
# TODO: definir o valor exato com o usuário (ex.: uma cidade/filial padrão).
LOCALIZACAO_PADRAO = ""

# Tipo de elemento padrão para o select "Tipo de elemento".
TIPO_ELEMENTO_PADRAO = "Digital"

# Tipo de unidade padrão para o select "Tipo de unidade".
TIPO_UNIDADE_PADRAO = "Painel LED"

# ---------------------------------------------------------------------------
# Timeouts (em milissegundos)
# ---------------------------------------------------------------------------
TIMEOUT_PADRAO    = 15_000   # timeout padrão do Playwright
TIMEOUT_LOGIN     = 60_000   # aguarda tela de login carregar
TIMEOUT_NAVEGACAO = 60_000   # aguarda navegação de página
TIMEOUT_ELEMENTO  = 15_000   # aguarda elemento aparecer
TIMEOUT_OVERLAY   = 10_000   # aguarda overlay do mat-select

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
# Texto que só aparece depois de logado (depende do idioma da conta).
TEXTO_LOGIN_OK = "Definições"
