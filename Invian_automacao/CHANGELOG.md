# Correções e melhorias

## Novas Funcionalidades (v2.1)

### Modo Panvel — Criação de Unidade
- **Novo arquivo `unidade_panvel.py`**: automação completa de criação de unidade no painel Invian
  - Aba 1 (Informação Básica): preenche Nome no formato `[Filial] - Panvel [Nome] [Tag]_[Seq]`, Filial, Endereço, Cidade, Estado
  - Aba 2 (Localização): preenche Latitude/Longitude com 6 casas decimais + clica "Confirmar Ponto no Mapa"
  - Aba 3 (Faces): clica "Adicionar Face" + preenche Tag da Face
  - Aba 4 (Restrições): marca checkbox de restrições
  - Salvar: botão "Salvar/Finalizar" com aguardo de toast de sucesso
- **Regras de nomenclatura Panvel implementadas**:
  - Tag `MED-TV_43` para NUC/Tela Padrão (nome não contém "CHECKOUT"/"SELF")
  - Tag `MED-TV_21` para Self-Checkout (nome contém "CHECKOUT" ou "SELF")
  - Sequencial por filial: 1 unidade = sem sufixo; 2+ unidades = todas com `_01`, `_02`...
  - Coordenadas formatadas com exatamente 6 casas decimais
- **Novo modo `panvel`** integrado em `core.py`, `processos.py`, `config.py`, `main.py`, `gui/config_dialog.py`
- **Skill `unidade_panvel_skill.py`** registrada no framework (skills descobertas automaticamente)

### Melhoria GUI — Anunciantes por Dia configurável
- **Campo "Quantidade" (Spinbox 1–999)** no modo Faces / Ambos
- Valor padrão 12 mantido (compatibilidade total)
- Passado via `valor_anunciantes` em `core.py` → `processos.py` → `faces.py`
- CLI: novo argumento `--anunciantes`

### Correções de bugs no Panvel
- **Contador de sequencial por filial**: agora conta TODAS as linhas da planilha filtrada **antes** de iniciar a fase (função `preparar_sequenciais` em `core.py`), garantindo que filiais com 2+ unidades recebam sufixo `_01`, `_02` em TODAS as linhas, não só a partir da segunda.
- **Leitura de colunas flexível** (`_obter`): ignora acentos/maiúsculas/espaços (`"Rua e Número"` == `"rua e numero"`).

---

# Correções e melhorias

## Bugs que quebravam a execução
1. **GUI / modo Unidades: NameError** — `gui/automation_runner.py` usava `COLUNA_PLAYER`, `carregar_planilha_com_config` e `texto_celula` sem importar. (O `fix_runner.py` tentou corrigir, mas só trocou o import.)
2. **Login da GUI nunca recebia a senha digitada** — e/mail/senha eram lidos do formulário e descartados; `fazer_login` caía no `input()` do terminal dentro da thread da GUI. Agora `fazer_login(pagina, email, senha)`.
3. **Botão "Parar" nascia desabilitado e nunca era habilitado.**
4. **Tkinter mexido de outra thread** (log e messagebox direto da thread de trabalho). Agora fila + `root.after`.
5. **`faces.py`: fallbacks nunca rodavam** — Locator do Playwright nunca é falsy, então `if not linha/botao/campo:` jamais disparava.
6. **`faces.py`: `wait_for_selector("text=Sucesso, text=Salvo, ...")`** não é seletor válido → sempre 15 s de espera.
7. **`.agents/main_agent.py`**: `from .config` (inexistente), usava o dict de `execute_skill` como se fosse o navegador, e `processar_linha` com `row=None`.
8. **`skills/__init__.py`**: `execute_skill` descartava o retorno do handler.
9. **`config_dialog`: `lambda: ...(str(e))`** — `e` some ao sair do `except`; o erro de leitura da planilha nunca aparecia.

## Bugs que faziam o robô fazer a coisa errada
10. **Player/face errado**: busca por substring abria "Loja 10" ao procurar "Loja 1". Agora match exato (`escolher_linha`), ambíguo → erro.
11. **`horario_corresponde` com falso positivo**: string vazia casava com tudo; "Dom de 07:00 a 22:00" casava com o composto "Seg… | Dom…" → robô achava que já estava certo e não salvava.
12. **Horário vazio virava "Fixo"** e sobrescrevia o cadastro. Agora a linha é pulada.
13. **`HEADLESS` ignorado**: `navegador.py` tinha `headless=False` fixo (GUI, CLI e config).
14. **GUI abortava tudo no 1º erro** (CLI continuava). Agora igual nos dois: erro registra, tira print e segue.
15. **Número de linha errado nos logs** depois de filtrar (`reset_index`). Agora coluna `_linha_excel`.
16. **Aba padrão (ONSIGN) perdida na GUI** — "Carregando..." sobrescrevia o valor.
17. **Cabeçalho detectado pela GUI não chegava ao carregador** (colunas na GUI ≠ colunas lidas).
18. **`--linha 0` / `or`** tratava 0 como "não informado".
19. **Salvar poderia clicar duas vezes**; **"Salvar" de Faces era procurado na página toda**; **opção `12` casava com `112`/`120`**; sucesso era declarado sem confirmar. Agora: escopo no modal, opção exata, valor relido, confirmação por toast ou fechamento do modal.
20. **Normalização de horas**: `07:00-22:00`, `7h`, `22h` não eram tratados; `" as "` antes de hora era trocado indevidamente.
21. Faces: abria a tela duas vezes por linha (main + `processar_face`).
22. Número de filtros numéricos (`3.0` vs `3`) não casava no AutoFiltro.

## Estrutura / manutenção
- **Um motor só** (`core.py`) para CLI e GUI (antes eram dois, divergentes) + `processos.py` com a lógica de cada linha (antes duplicada em 4 lugares).
- `planilha.py`: duas cópias de ~80 linhas viraram uma; sem monkeypatch de globais; workbook fechado; AutoFiltro por linhas ocultas (qualquer tipo de filtro).
- **Relatório CSV** e **print de erro** por linha.
- Skills: registro idempotente, `registry.call()`, código morto removido, wrappers finos.
- Grafo: aresta duplicada removida; `input_pesquisa` agora pertence à tela de Unidades.
- Removidos: `fix_*.py` (scripts descartáveis com caminho absoluto do seu PC), `__pycache__`, `.git` do pacote. Adicionados `.gitignore`, `requirements.txt`.
- `config.py`: `COLUNAS_FACE`, `VALOR_ANUNCIANTES_POR_DIA`, `TEXTO_LOGIN_OK`.

## Não testado
Seletores contra o Invian real (sem acesso/navegador no ambiente de análise). Testados: normalização/comparação de horários, leitura de planilha (sem filtro, lista, linhas ocultas, cabeçalho deslocado), registro de skills, runner/GUI-events, grafo, compilação.

---
## Atualização 2 (teste.xlsx e janela)
- **Janela da GUI**: conteúdo com barra de rolagem lateral e roda do mouse, botões Iniciar/Cancelar fixos no rodapé, janela se ajusta à tela (máx. 90% da altura) e textos longos quebram linha.
- **Campo de colunas sumia**: ao reaparecer, ele era empacotado depois do Log (fora da vista). Agora fica logo abaixo de "Aba da Planilha".
- **Colunas do arquivo**: a GUI agora tem as listas "Nome do player/face" e "Horário de funcionamento"; o nome da coluna casa sem diferenciar maiúsculas/acentos (`Horário de funcionamento` ≠ `Horário de Funcionamento` do config.py antes causava erro).
- **Cabeçalho deslocado** (relatório exportado com 5 linhas antes da tabela): detectado na GUI (linha 6 no teste.xlsx) e repassado ao motor; linha inicial é elevada para a 1ª linha de dados. CLI: `--cabecalho 6 --coluna Unidade --coluna-horario "Horário de funcionamento"`.
- **Formatos de horário do teste.xlsx**: `07:00 - 23:00` → `Todos os dias de 07:00 a 23:00`; `07:00 - 23:00 | Dom 07:00 - 20:00` → `Seg, Ter, Qua, Qui, Sex, Sáb de 07:00 a 23:00 | Dom de 07:00 a 20:00`.
