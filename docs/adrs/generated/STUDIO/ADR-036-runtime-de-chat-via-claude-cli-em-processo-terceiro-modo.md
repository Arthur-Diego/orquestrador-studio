# ADR-036: Runtime de chat via CLI `claude` em processo — o terceiro modo de falar com o Claude

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-04
**ADRs relacionados:** [ADR-001 (single-process, loopback)](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-003 (persistência em arquivos)](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004 (fidelidade ao curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006 (jobs em thread + polling)](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008 (testes sem rede)](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-034 (execução de skill do Claude CLI)](./ADR-034-execucao-de-skill-do-claude-cli-com-escrita-em-disco.md), [ADR-037](./ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md), [ADR-040](./ADR-040-agente-sem-tools-nativas-e-isolado-das-configuracoes-do-usuario.md)

## Contexto e Problema

O Studio já fala com o Claude por dois caminhos, ambos com a **assinatura do usuário** (`claude -p`,
nunca chave de API): o bot de prompts (`common/prompter.py`, pergunta curta somente-leitura) e o
runner de skill (`common/skill_runner.py`, corrida longa que escreve no disco — ADR-034). A ADR-034
já previu: *"se um terceiro modo de chamada aparecer, esta decisão deve ser revisitada"*.

Ele apareceu. O produto agora quer um **assistente de chat** multi-turno que conduz a criação de
conteúdo do início ao fim, executa as ações das etapas e mantém contexto entre turnos. Nem o
`prompter` (uma pergunta, 6 turnos, só `Read`) nem o `skill_runner` (uma corrida, sem multi-turno,
sem streaming ao vivo, sem tools de ação) servem.

O plano original propunha o **Claude Agent SDK** (Python) rodando dentro do processo. A análise do
código retirou o risco central que justificava o SDK: o SDK sobe o mesmo `claude -p` por baixo, e
`claude -p` com a assinatura **já é fato provado em produção** (prompter e skill_runner). O que
sobra do SDK é conveniência (parsing de stream, resume), não uma capacidade indisponível de outra
forma — ao custo de uma dependência nova e da incógnita de spawnar dentro do asyncio.

## Decision Drivers
- Preservar a regra de que a ponte com o modelo é o **CLI local com a assinatura** (ADR-034/ADR-002).
- Single-process (ADR-001): nada de segundo runtime.
- Multi-turno com contexto, streaming ao vivo e tools de ação.
- Testável sem `claude` real (ADR-008).
- Não introduzir dependência pesada sem necessidade.

## Decisão

**Um turno = um subprocess `claude -p` de vida curta, com stream-json, dentro do processo do
Studio** (`studio/chat/runtime.py`). Sem SDK: o mecanismo é o mesmo já comprovado pelo
`skill_runner`, estendido para multi-turno e streaming.

1. **Multi-turno por `--resume`.** A aba tem um `session_id` (UUID canônico). O primeiro turno usa
   `--session-id <sid>` (cria a conversa); os seguintes `--resume <sid>` (continuam com contexto).
   O Claude guarda o histórico da sessão; o Studio não reenvia o transcript.
2. **Streaming por `--output-format stream-json --verbose`.** Cada linha do stdout é normalizada
   (`normalize_event`, função **pura**) em eventos do protocolo do WebSocket (`assistant_text`,
   `tool_call`, `tool_result`, `result`, `system`, `notify`, `ask`, `raw`) e transmitida ao browser,
   além de persistida no transcript. Eventos de controle do CLI (ex.: `rate_limit_event`) são
   descartados.
3. **A ponte com o modelo continua sendo a assinatura.** Nunca `ANTHROPIC_API_KEY`, nunca
   `api.anthropic.com` direto — como ADR-034. O modelo é `STUDIO_CHAT_MODEL` (vazio = default do
   usuário), env própria (não reusa `STUDIO_PROMPTER_MODEL`/`STUDIO_SKILL_MODEL`).
4. **Single-process (ADR-001).** O WebSocket `/ws/chat/{id}` e o runtime vivem no `uvicorn` do
   Studio; o subprocess `claude` é filho de vida curta, não um servidor.
5. **Persistência (ADR-003).** Abas e transcript em `STATE_DIR/chats/<id>/` (`meta.json` +
   `events.jsonl`), fora do git e de `projects/`.
6. **Fakeável (ADR-008).** `line_source(argv, cwd)` é injetável: os testes passam linhas canônicas
   e nunca chamam o `claude`. `normalize_event`/`build_argv` são puros.

O Agent SDK fica registrado como **otimização futura opcional** (troca de `line_source`), não como
dependência da Onda A.

## Consequências

**Positivas**
- Zero dependência nova para o runtime; reusa um mecanismo já em produção (ADR-034).
- Um turno morto não derruba o servidor; falha vira `result{is_error}` na tela.
- `normalize_event` puro dá cobertura de teste real sem `claude`.

**Negativas / custos**
- Um processo `claude` por turno tem custo de partida (carrega CLAUDE.md do projeto). Aceitável na
  Onda A; a redução de contexto por turno é trabalho da Onda E.
- Sem deltas de texto (blocos inteiros por mensagem), até adotarmos `--include-partial-messages`.
- O CI nunca exercita o `claude` real (ADR-008); a corrida ponta a ponta é validação manual
  registrada na PR — feita na Onda A (o turno real chamou `projects`→`guide`→`guide_step`).
