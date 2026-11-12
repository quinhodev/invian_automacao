# HANDOFF — Criação de Unidade Panvel (Aba 1)

Branch: `fix/criacao-unidade-aba1`
Commit: `6e324734412b1ecb4b916be85351726a9d5c42bd`
Link: https://github.com/quinhodev/invian_automacao/commit/6e324734412b1ecb4b916be85351726a9d5c42bd

---

## O que foi alterado — arquivo por arquivo

### `Invian_automacao/unidade_panvel.py` (reescrito)
- Novo `_painel_atual(pagina)`: painel ativo do stepper (`.mat-horizontal-stepper-content-current`); todo helper busca DENTRO dele, nunca na página toda.
- Novo `_campo(escopo, rotulo)`: mat-form-field pelo label exato (aceita "*"), match exato via `web_utils.chave`.
- Novo `_preencher_input(escopo, rotulo, valor)`: click, Ctrl+A, fill.
- Novo `_selecionar_opcao(pagina, escopo, rotulo, texto=None)`: abre mat-select; overlay `.cdk-overlay-pane:visible`.last; ignora campo de busca dentro de mat-option e `aria-disabled="true"`; `texto=None` → primeira opção válida; `texto` informado → match exato (parcial só se único) por índice; erro → Escape + RuntimeError listando opções; espera o overlay fechar.
- Novo `_clicar_proximo(pagina)` / `_clicar_terminar(pagina)`: espera habilitar ~6 s, `RuntimeError` se não habilitar, espera o painel sair do "current" (~800 ms).
- Etapa 1 (`preencher_informacao_basica`): nome já formatado (Panvel + `MED-TV_\d+`) é mantido; senão monta com `_gerar_sequencial` (Filial/ID exigido só então). `LOCALIZACAO_PADRAO` obrigatória (`RuntimeError` se vazia). Cidade e Endereço obrigatórios (`RuntimeError` explícito).
- Etapa 2 (`preencher_localizacao`): "lat, long" com 6 casas, separador `", "`; `Tab` (sem Enter); sem busca por "Confirmar Ponto".
- Etapa 3 (`pular_cameras`): log + Próximo.
- Etapa 4 (`vincular_faces`): botão "Adicionar" no painel → modal "Adicionar Face" → Tipo de face (1ª opção) → Dimensões (1ª válida) → Salvar (1 clique) → espera modal fechar (15 s) + "1 faces" → Próximo.
- Etapa 5 (`configurar_restricoes` apenas log; `finalizar_unidade` substitui `salvar_unidade`): clica "Terminar"; confirma toast `/(Sucesso|Salvo|Criado|Success|Created)/i` ou fechamento da tela / mudança de URL (até 20 s); senão `False` + aviso com 300 chars do `body`.
- `processar_criacao_unidade_panvel`: fluxo `abrir_tela → clicar_adicionar_unidade → Etapa1 → Próximo → Etapa2 → Próximo → pular_cameras → vincular_faces → Restrições → finalizar_unidade`. Latitude/Longitude obrigatórias; log "Botão 'Adicionar' clicado".
- Removidos: `_clicar_aba`, `_preencher_campo_texto`, `salvar_unidade`, `faceTag`, `btn-add-face`, fill com nome do player, busca por "Confirmar Ponto".

### `Invian_automacao/config.py`
- Sem alterações funcionais: já continha `LOCALIZACAO_PADRAO = ""`, `TIPO_ELEMENTO_PADRAO = "Digital"`, `TIPO_UNIDADE_PADRAO = "Painel LED"` e as colunas usadas.

### `HANDOFF.md` / `CHANGELOG.md`
- Reescrito; nova seção v2.3 no CHANGELOG.

---

## Verificação — resultado

| Verificação | Resultado |
|---|---|
| `python -m py_compile config.py unidade_panvel.py` | OK, sem avisos |
| `import config, unidade_panvel` a partir de `Invian_automacao/` | OK |
| `_obter_filial` (com Filial / fallback ID / vazio) | OK |
| detecção de nome já formatado | OK |
| `_normalizar_nome_panvel` | OK |
| `_formatar_coordenada` (6 casas, vírgula→ponto) | OK |
| montagem "lat, long" (6 casas, separador `, `) | OK |

---

## Não testado
- Execução contra o `web.invian.net` real (não há navegador/acesso neste ambiente). Seletores do stepper/modal baseiam-se na descrição da tela real fornecida pelo usuário.

---

## Pendências / dúvidas para o Marcos
1. Definir `LOCALIZACAO_PADRAO` em `config.py` (atualmente `""` → gera `RuntimeError` claro na Etapa 1).
2. Validar os seletores dos selects ("Localização", "Tipo de elemento", "Tipo de unidade", "Cidade", "Tipo de face", "Dimensões") e dos botões "Próximo"/"Terminar"/"Salvar"/"Adicionar" em tela real.
3. Confirmar se o overlay do mat-select usa `.cdk-overlay-pane` e se o campo "Pesquisar" fica dentro de um `mat-option` (ngx-mat-select-search), conforme descrito.

---

## Decisões tomadas pelo agente (por conta própria)
- Manteve `config.py` inalterado (constantes já existiam); `LOCALIZACAO_PADRAO=""` propositalmente gera `RuntimeError` para forçar a definição pelo usuário.
- Renomeou `salvar_unidade` → `finalizar_unidade`; `configurar_restricoes` agora só registra log ("nada a configurar").
- `finalizar_unidade` retorna `False` (não `True`) quando não há confirmação de sucesso, com aviso de diagnóstico.
- `_selecionar_opcao` clica por índice (`opcoes.nth(i)`), nunca por `:has-text`, e devolve o texto da opção escolhida.
- Não commitar `.env`, `*.xlsx`, `relatorios/`, `erros/` nem artefatos (`compile_output.txt`, `__pycache__`).
