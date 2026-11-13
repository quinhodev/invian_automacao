with open('c:/Users/MarcosSouza/OneDrive - The LED/Documentos/DOC/invian_auto2/Invian_automacao_corrigido/HANDOFF.md', 'w', encoding='utf-8') as f:
    f.write("""# HANDOFF — Criação de Unidade Panvel Robusta

Branch: `feat/criacao-unidade-robusta`
Commit: `Último commit desta branch`
Link: (será preenchido após push)

---

## O que foi alterado — arquivo por arquivo

### `Invian_automacao/unidade_panvel.py` (robustecido)
- `finalizar_unidade`: captura `url_antes` ANTES de `_clicar_terminar`; sucesso = toast `/(Sucesso|Salvo|Criado|Success|Created)/i` visível OU (URL mudou E título "Adicionar unidade" não visível); erro visível => `False` imediato com log do texto.
- `_nome_final(row, log)`: nome calculado uma única vez por linha.
- Idempotência: antes de clicar em "Adicionar unidade", pesquisa o nome final na lista; conta como existente só se alguma célula tiver texto igual.
- Localização (Etapa 1): se `LOCALIZACAO_PADRAO` vazio, escolhe a 1ª opção válida e loga aviso; sem `RuntimeError`.
- `_selecionar_opcao`: digita texto no campo de busca do overlay e espera ~200 ms; após clicar, espera `mat-option` sumir.
- `_clicar_proximo` / `_clicar_terminar`: captura `painel.element_handle()` ANTES do clique; polling 100 ms; fallback 300 ms.
- `_campo`: `RuntimeError` lista os rótulos vistos no escopo.
- `_diagnostico(pagina)`: etapa atual do stepper + primeiros 300 chars de texto visível.
- `processar_criacao_unidade_panvel`: exige Filial/ID só quando o nome NÃO está no padrão Panvel; aceita `dry_run`.

### `Invian_automacao/preflight.py` (novo)
- `validar_panvel(df, log)`: chamado por `core.executar_automacao` depois de carregar a planilha e antes de criar o navegador. Levanta `ValueError` com todos os problemas.

### Modo `--dry-run` (novo)
- CLI: flag `--dry-run`; GUI: checkbox "Simular (não clicar em Terminar)" só no modo Panvel.
- Propagado: `main` → `core.executar_automacao(dry_run)` → `_rodar_fase` → `processar_linha_panvel` → `processar_criacao_unidade_panvel(dry_run)`.
- Em dry-run: preenche até Restrições, screenshot em `erros/dryrun_L<linha>.png`, NÃO clica em Terminar.
- `core._status`: `res.get("dryrun")` => status `"dryrun"` (ícone `[DRY]` no log e no CSV).

### `Invian_automacao/core.py`
- Adicionado parâmetro `dry_run` em `executar_automacao` e `_rodar_fase`.
- Preflight chamado antes de criar navegador.

### `Invian_automacao/processos.py`
- `processar_linha_panvel` aceita e propaga `dry_run`; retorna campo `dryrun`.

### `Invian_automacao/main.py`
- CLI: adicionado `--dry-run`.

### `Invian_automacao/gui/config_dialog.py`
- Frame "Simulação (Panvel)" com checkbox "Simular (não clicar em Terminar)" visível só no modo Panvel.

### `Invian_automacao/gui/automation_runner.py`
- Propaga `dry_run` para `executar_automacao`.

### `Invian_automacao/mock_invian/index.html` (atualizado)
- Simulador local com query params: `?erro=1`, `?existe=<nome>`, `?parecida=<nome>`.

### Testes (`Invian_automacao/tests/`)
- `conftest.py`: sobe servidor HTTP local, aguarda ficar pronto.
- `test_puros.py`: funções puras.
- `test_preflight.py`: 16 testes.
- `test_fluxo_mock.py`: 5 testes de fluxo.

### `.gitignore`
- Adicionado `.env`, `*.xlsx`, `relatorios/`, `erros/`, `compile_output.txt`.

### `Invian_automacao/README.md`
- Seções "Testes", "Preflight (modo panvel)", "Dry-run (modo panvel)" adicionadas.

### `Invian_automacao/CHANGELOG.md`
- Nova seção v2.4 documentando todas as alterações.

---

## Verificação — resultado

| Verificação | Resultado |
|---|---|
| `python -m py_compile` (todos os .py alterados) | OK, sem avisos |
| `python -m pytest tests -q` | 31 passed |

---

## Não testado
- Execução contra o `web.invian.net` real. Seletores baseiam-se na descrição da tela real.

---

## Pendências / dúvidas para o Marcos
1. Definir `LOCALIZACAO_PADRAO` em `config.py` (atualmente `""` → usa 1ª opção com aviso).
2. Validar seletores dos selects e botões em tela real.
3. Confirmar overlay do mat-select e campo Pesquisar.

---

## Decisões tomadas pelo agente (por conta própria)
- Manteve `config.py` inalterado; `LOCALIZACAO_PADRAO=""` propositalmente usa 1ª opção com aviso.
- Renomeou `salvar_unidade` → `finalizar_unidade`; `configurar_restricoes` só log.
- `finalizar_unidade` retorna `False` quando não há confirmação.
- `_selecionar_opcao` clica por índice (`opcoes.nth(i)`).
- Waits fixos otimizados: 300ms, 200ms, fallback 300ms.
- Não commitar `.env`, `*.xlsx`, `relatorios/`, `erros/`, `compile_output.txt`, `__pycache__`.
""")
print("OK")