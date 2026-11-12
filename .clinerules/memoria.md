---
# Memória do projeto Invian_automacao (OBRIGATÓRIO)
No INÍCIO de toda tarefa: ler HANDOFF.md e a seção mais recente do Invian_automacao/CHANGELOG.md.
Regras fixas:
- NÃO invente seletores; use só os descritos no prompt/HANDOFF.md. Desconhecido = TODO + erro claro.
- Formulário de criação de unidade: 5 etapas (Informação básica, Localização, Câmeras, Faces,
  Restrições). Procurar elementos DENTRO do painel atual (.mat-horizontal-stepper-content-current)
  ou do modal. O último botão é "Terminar".
- Antes de dar uma tarefa por pronta: rodar `python -m pytest tests -q` (dentro de Invian_automacao).
- Nunca commitar .env, *.xlsx, relatorios/, erros/.
- Não rodar a automação contra o Invian real.
No FIM de toda tarefa: reescrever HANDOFF.md (Branch/Último commit; O que foi alterado; Verificação;
Não testado; Pendências/dúvidas para o Marcos; Decisões que o agente tomou por conta própria),
commit e push.
---