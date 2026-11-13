# Automação Invian — Guia do Projeto

Automatiza o painel `web.invian.net` a partir de uma planilha Excel:

| Modo | O que faz |
|------|-----------|
| `unidades` | Para cada player da planilha, abre o cadastro e ajusta o **Horário** de funcionamento |
| `faces` | Para cada face, abre ⋮ → Preços e deixa **Anunciantes por dia** (configurável, padrão 12) |
| `ambos` | Executa unidades e depois faces |
| `panvel` | **Cria unidade Panvel do zero** (Aba 1–4 + Salvar) seguindo nomenclatura padrão |

## Estrutura

```
main.py                 # Entrada: GUI (padrão) ou --cli
core.py                 # Motor único (login → fases → linhas → relatório CSV)
processos.py            # O que fazer com UMA linha (unidades / faces / panvel)
config.py               # URLs, colunas, timeouts, valor de anunciantes, HEADLESS, tags Panvel
planilha.py             # Excel + AutoFiltro (linhas ocultas ou filtros de lista)
texto.py / horario.py   # Normalização e comparação de horários
navegador.py / login.py # Playwright e autenticação
unidades.py / faces.py  # Automação de cada tela (edição)
unidade_panvel.py       # Automação de CRIAÇÃO de unidade Panvel (abas 1–4)
web_utils.py            # Helpers: primeiro_visivel(), escolher_linha() (match exato)
skills/                 # Registro de skills (wrappers finos sobre processos.py)
gui/                    # Diálogo de configuração + runner em thread
tools/                  # Grafo de conhecimento (documentação navegável do fluxo)
.agents/                # Pipeline de exemplo usando o registro de skills
```

## Como usar

### 1. Instalação

```bash
pip install -r requirements.txt
playwright install
```

### 2. Interface Gráfica (padrão)

```bash
python main.py
```

A GUI permite configurar:
- **Tipo de automação**: Unidades / Faces / Ambos / Panvel
- **Arquivo Excel** e **Aba da planilha**
- **Linha inicial** (onde começam os dados)
- **Coluna de nome** (player/face/unidade) e **Coluna de horário** (quando aplicável)
- **Quantidade de Anunciantes por Dia** (modo Faces/Ambos — padrão 12)
- **Headless** (navegador invisível)
- **Credenciais** (ou use variáveis de ambiente)

### 3. Linha de Comando (CLI)

```bash
# Unidades (Horários) — padrão
python main.py --cli

# Faces (Anunciantes por dia) — valor padrão 12
python main.py --cli --modo faces --coluna "Nome da Face"

# Ambos em sequência
python main.py --cli --modo ambos --coluna "Nome do Player" --coluna-horario "Horário de Funcionamento" --anunciantes 15

# Panvel — Criação de unidade
python main.py --cli --modo panvel --arquivo dados.xlsx --aba Planilha1 --linha 2

# Headless (invisível)
python main.py --cli --modo panvel --headless
```

**Argumentos CLI:**

| Argumento | Descrição |
|-----------|-----------|
| `--cli` | Executa sem GUI |
| `--modo` | `unidades`, `faces`, `ambos`, `panvel` (padrão: `unidades`) |
| `--arquivo` | Caminho do arquivo Excel |
| `--aba` | Nome da aba da planilha |
| `--linha` | Linha inicial dos dados (1 = cabeçalho) |
| `--coluna` | Coluna com nome do player/face |
| `--coluna-horario` | Coluna com horário (obrigatório para unidades/ambos) |
| `--anunciantes` | Quantidade de anunciantes por dia (faces/ambos, padrão: 12) |
| `--cabecalho` | Linha do cabeçalho na planilha (padrão: 1) |
| `--headless` / `--visible` | Modo do navegador |

### 4. Credenciais

Defina variáveis de ambiente ou digite na GUI/terminal:

```bash
export INVIAN_EMAIL="seu@email.com"
export INVIAN_SENHA="suasenha"
```

---

## Planilha e AutoFiltro

- Cabeçalho na linha 1 (a GUI detecta outra linha e repassa — ex.: linha 6 no `teste.xlsx`).
- Aplique o filtro no Excel e **salve e feche** o arquivo. As linhas que o Excel salvou como **ocultas** são ignoradas (vale para filtro de lista, cor, data, etc.).
- Se nenhuma linha estiver oculta, os filtros de lista são reaplicados em pandas.
- Linha com **horário vazio** é pulada (não vira mais "Fixo" automaticamente).
- Colunas aceitas com nomes flexíveis (sem diferenciar maiúsculas/acentos).

### Colunas necessárias por modo

| Modo | Colunas obrigatórias |
|------|---------------------|
| `unidades` | `Nome do Player`, `Horário de Funcionamento` |
| `faces` | `Nome da Face` (ou `Face`, `Unidade`, `Tipo de Face`, `Nome`) |
| `ambos` | União das anteriores |
| `panvel` | `ID`, `Filial`, `Nome do Player`, `Rua e Número`, `Cidade`, `Estado`, `Latitude`, `Longitude` |

---

## Regras de Nomenclatura Panvel (modo `panvel`)

O robô monta o nome da unidade no formato:

```
[Filial] - Panvel [Nome] [Tag]_[Seq]
```

| Tipo de mídia | Tag | Quando aplica |
|---------------|-----|---------------|
| Tela Padrão / NUC de Sinalização | `MED-TV_43` | Nome **não** contém "CHECKOUT" nem "SELF" |
| Tela de Self-Checkout | `MED-TV_21` | Nome contém "CHECKOUT" ou "SELF" |

**Sequencial por filial:**
- 1 unidade na filial: **sem sufixo** → `750 - Panvel Roxo MED-TV_43`
- 2+ unidades na filial: **todas** recebem sufixo `_01`, `_02`... → `972 - Panvel Canoas MED-TV_43_01`, `_02`

**Geolocalização:** Latitude/Longitude sempre com **6 casas decimais** (ex.: `-30.027510`, `-51.168420`).

---

## Fluxo da Automação Panvel (modo `panvel`)

1. **Abre tela de criação** → `https://web.invian.net/settings/inventory/units/create`
2. **Clica "Adicionar unidade"** → abre formulário multi-abas
3. **Aba 1 — Informação Básica**: preenche Nome (formato Panvel), Filial, Endereço, Cidade, Estado
4. **Aba 2 — Localização**: preenche Latitude/Longitude (6 casas decimais) → clica "Confirmar Ponto no Mapa"
5. **Aba 3 — Faces**: clica "Adicionar Face" → preenche Tag da Face com o nome do player
6. **Aba 4 — Restrições**: marca checkbox de restrições (se houver)
7. **Salvar**: clica botão "Salvar/Finalizar" → aguarda toast de sucesso

---

## Saídas

- `relatorios/relatorio_AAAAMMDD_HHMMSS.csv` — status por linha:
  - `alterado` — mudança aplicada
  - `ja_correto` — já estava certo, nada feito
  - `pulado` — linha ignorada (ex.: horário vazio, player vazio)
  - `erro` — falha (ver mensagem e print)
- `erros/erro_<fase>_L<linha>_*.png` — screenshot da tela quando uma linha falha

---

## Nova automação (template)

Para adicionar uma nova tela (ex.: campanhas):

1. Crie `campanhas.py` seguindo o padrão de `unidades.py` / `faces.py` / `unidade_panvel.py`
2. Adicione `processar_linha_campanhas` em `processos.py`
3. Inclua a fase em `core.py` (`_rodar_fase` + `MODOS` + `_resolver_colunas`)
4. (Opcional) Crie skill em `skills/campanhas_skill.py`
5. Atualize `gui/config_dialog.py` e `main.py` (CLI)

---

## Testes

Executar a suíte de testes (dentro de `Invian_automacao/`):

```bash
# Instalar dependências de dev
pip install -r requirements-dev.txt
playwright install chromium

# Rodar todos os testes
python -m pytest tests -q
```

Os testes usam um simulador local (`mock_invian/index.html`) em vez do Invian real,
cobrindo: funções puras, fluxo completo no mock (sucesso, erro, idempotência, dry-run)
e validação de preflight.

## Preflight (modo panvel)

Antes de abrir o navegador, `preflight.validar_panvel()` valida a planilha e levanta
`ValueError` listando **todos** os problemas (cada um com o número da linha real do Excel):

- Colunas ausentes: Nome do Player, Rua e Número, Cidade, Latitude, Longitude e (Filial ou ID)
- Por linha: nome/rua/cidade vazios; latitude/longitude vazias, não numéricas ou fora de range
- Linhas repetidas (mesmo Nome do Player + mesma Filial/ID)
- `LOCALIZACAO_PADRAO` vazio => apenas aviso (não é erro)

## Dry-run (modo panvel)

Simula a criação sem clicar em "Terminar":

**CLI:**
```bash
python main.py --cli --modo panvel --arquivo dados.xlsx --aba Planilha1 --linha 2 --dry-run
```

**GUI:** marque o checkbox "Simular (não clicar em Terminar)" (visível apenas no modo Panvel).

Em dry-run o robô preenche todas as 5 etapas até Restrições, tira um screenshot em
`erros/dryrun_L<linha>.png` e NÃO clica em Terminar. O status no log/relatório é `dryrun`.

## Requisitos

```
pandas
openpyxl
playwright
```

Para desenvolvimento/testes:
```
pytest
pytest-playwright
```

Python 3.10+ recomendado.
