## v2.4 — Robustez da criação de unidade Panvel: preflight, dry-run e testes

### `Invian_automacao/unidade_panvel.py`
- `finalizar_unidade`: captura `url_antes` ANTES de `_clicar_terminar`; sucesso = toast
  `/(Sucesso|Salvo|Criado|Success|Created)/i` visível OU (URL mudou E título "Adicionar
  unidade" não visível); erro visível => `False` imediato com log do texto.
- `_nome_final(row, log)`: nome calculado uma única vez por linha (usa `_nome_ja_formatado`;
  senão monta com `_normalizar_nome_panvel` + `_gerar_sequencial` que roda 1 vez por linha).
- Idempotência: antes de clicar em "Adicionar unidade", pesquisa o nome final na lista
  (campo "Pesquisar" + `escolher_linha` com timeout 4s); conta como existente só se alguma
  célula tiver texto igual ao nome; correspondência parcial não conta.
- Localização (Etapa 1): se `LOCALIZACAO_PADRAO` vazio, escolhe a 1ª opção válida e loga
  aviso; sem `RuntimeError`.
- `_selecionar_opcao`: digita texto no campo de busca do overlay e espera ~600 ms antes de
  coletar opções; após clicar na opção, espera `mat-option` sumir (não espera o pane sumir).
- `_clicar_proximo` / `_clicar_terminar`: captura `painel.element_handle()` ANTES do clique
  para o `wait_for_function`.
- `_campo`: `RuntimeError` lista os rótulos vistos no escopo quando não encontra o rótulo.
- `_diagnostico(pagina)`: etapa atual do stepper + primeiros 300 chars de texto visível,
  anexado ao `message` do `except`.
- `processar_criacao_unidade_panvel`: exige Filial/ID só quando o nome NÃO está no padrão Panvel.

### `Invian_automacao/preflight.py` (novo)
- `validar_panvel(df, log)`: chamado por `core.executar_automacao` depois de carregar a
  planilha e antes de criar o navegador (modo panvel). Levanta `ValueError` com todos os
  problemas (colunas ausentes, campos vazios/fora de range, duplicatas), cada um com o
  número da linha real do Excel (`_linha_excel`). `LOCALIZACAO_PADRAO` vazio => apenas aviso.

### Modo `--dry-run`
- CLI: flag `--dry-run`; GUI: checkbox "Simular (não clicar em Terminar)" (só no modo Panvel).
- Propagado: `main` → `core.executar_automacao(dry_run)` → `_rodar_fase` →
  `processar_linha_panvel` → `processar_criacao_unidade_panvel(dry_run)`.
- Em dry-run: preenche até Restrições, screenshot em `erros/dryrun_L<linha>.png`, NÃO clica
  em Terminar. Retorna `{"success": True, "changed": False, "dryrun": True, ...}`.
- `core._status`: `res.get("dryrun")` => status `"dryrun"` (ícone no log e no CSV).

### Testes (`Invian_automacao/tests/`)
- `conftest.py`, `test_puros.py`, `test_fluxo_mock.py`, `test_preflight.py`,
  `mock_invian/index.html` (simulador local com query params `?erro=1`, `?existe=`,
  `?parecida=`).
- `test_localizacao_vazia_usa_primeira_opcao`: `LOCALIZACAO_PADRAO` vazio => usa "Interna",
  `success True`.
- `test_erro_1_sucesso_false_menos_8s`: `?erro=1` => erro ao Terminar, `success False` < 8s.
- `test_existe_skipped_true`: `?existe=<nome>` => idempotência detecta, `skipped True`,
  `window.__terminar == 0`.
- `test_parecida_nao_conta_existente`: `?parecida=<nome>` => correspondência parcial não
  conta, segue criando.
- `test_dry_run`: `dryrun True`, `success True`, `window.__terminar == 0`, screenshot gerado.
- `test_preflight.py`: um teste por problema de validação (colunas ausentes, campos vazios,
  não numéricos, fora de range, duplicatas, LOCALIZACAO_PADRAO vazio).

### `.gitignore`
- Adicionado `.env`, `*.xlsx`, `relatorios/`, `erros/`, `compile_output.txt`.

### `Invian_automacao/unidade_panvel.py` (continuação da v2.3)

### `Invian_automacao/unidade_panvel.py`
- Reescrito com helpers de escopo: `_painel_atual`, `_campo`, `_preencher_input`, `_selecionar_opcao`, `_clicar_proximo`, `_clicar_terminar`. Toda busca de campo ocorre dentro do painel ativo do stepper (`.mat-horizontal-stepper-content-current`), nunca na página toda.
- Etapa 1 (Informação Básica): nome já formatado (Panvel + `MED-TV_\d+`) mantido; `LOCALIZACAO_PADRAO` obrigatória; Cidade e Endereço obrigatórios com `RuntimeError` explícito.
- Etapa 2 (Localização): preenche "lat, long" (6 casas, separador `, `), `Tab` sem Enter; removida busca por "Confirmar Ponto".
- Etapa 3 (Câmeras): nova `pular_cameras()` (log + Próximo).
- Etapa 4 (Faces): `vincular_faces()` reescrito — botão "Adicionar" no painel, modal "Adicionar Face", Tipo de face + Dimensões (primeira opção válida), Salvar (um clique), espera fechamento do modal (15 s) e "1 faces".
- Etapa 5 (Restrições): `configurar_restricoes()` apenas log; `salvar_unidade()` renomeado para `finalizar_unidade()`, clica "Terminar" e confirma sucesso (toast / fechamento da tela / mudança de URL, até 20 s); retorna `False` com aviso de diagnóstico se não confirmar.
- `processar_criacao_unidade_panvel`: fluxo completo Abrir → Adicionar → Etapa1 → Próximo → Etapa2 → Próximo → Câmeras → Faces → Restrições → Terminar.
- Removidos: `_clicar_aba`, `_preencher_campo_texto`, `salvar_unidade`, `faceTag`, `btn-add-face`.

### `Invian_automacao/config.py`
- Sem alterações (já continha `LOCALIZACAO_PADRAO`, `TIPO_ELEMENTO_PADRAO`, `TIPO_UNIDADE_PADRAO`).

### `HANDOFF.md` (raiz)
- Reescrito com Branch/Commit/Link, alterações, verificação, não testado, pendências e decisões do agente.

---

# Correções e melhorias

## v2.2 — Ajustes na criação de unidade Panvel (Aba 1)

### `config.py`
- **`URL_CRIACAO_UNIDADE`** corrigida: agora aponta para
  `https://web.invian.net/settings/inventory/units` (tela da lista de unidades),
  em vez de `/units/create` (que não existia).
- Adicionadas: `LOCALIZACAO_PADRAO = ""` (TODO: definir valor), `TIPO_ELEMENTO_PADRAO = "Digital"`,
  `TIPO_UNIDADE_PADRAO = "Painel LED"`.

### `unidade_panvel.py`
- **`clicar_adicionar_unidade`**: espera `input[placeholder="Pesquisar"]:visible`, depois
  `get_by_role("button", name=/^\s*Adicionar\s*$/)` com fallbacks
  (`button:has(mat-icon[data-mat-icon-name="plus"])`, `button.mat-mdc-unelevated-button:has-text("Adicionar")`).
  Erro claro se não achar.
- **`_obter_filial(row)`**: retorna `COLUNA_FILIAL` ou `COLUNA_ID` como fallback. Usado na
  validação de `processar_criacao_unidade_panvel` (remove lista de alternativas improvisada)
  e em `preparar_sequenciais`.
- **Helpers por rótulo do mat-form-field**: `_campo`, `_preencher_input`, `_selecionar_opcao`,
  `_clicar_proximo`. Substituem `_preencher_campo_texto` e `_clicar_aba`.
- **Aba 1 (Informação Básica)** preenche: Nome (input), Localização (select, `LOCALIZACAO_PADRAO`),
  Tipo de elemento (select, `TIPO_ELEMENTO_PADRAO`), Tipo de unidade (select, `TIPO_UNIDADE_PADRAO`),
  Cidade (select, valor da planilha), Endereço (input, coluna "Rua e Número").
  Remove Filial e Estado do formulário. Nome já formatado (contém `MED-TV_\d+` e "Panvel")
  é usado como está, sem chamar `_gerar_sequencial`.
- **Fluxo**: Aba1 → Próximo → Aba2 → Próximo → Aba3 → Próximo → Aba4 → Salvar.
  Abas 2–4 mantidas com `# TODO: seletores não validados`.

### `.gitignore`
- Adicionado `.env`.


---

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
