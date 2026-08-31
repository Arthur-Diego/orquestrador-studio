# ADR-028: Gate único de login do CLI Higgsfield (`hf.require_cli`)

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** HIGGSFIELD
**Task-Id:** ADH-OS-20260831-14
**ADRs relacionados:** [ADR-002](./ADR-002-integracao-higgsfield-somente-via-cli-oficial.md) (Higgsfield só via CLI oficial), ADR-004 (fidelidade — troca de ferramenta, não de processo), ADR-006 (jobs/polling), ADR-008 (CLI sempre fake nos testes), ADR-016 (custo antes de gerar + livro-caixa)

## Contexto e Problema

A checagem de "o CLI da Higgsfield está pronto para gerar?" estava **reimplementada em cada
etapa**, com comportamentos divergentes — o sintoma que o dono relatou: *"em alguns passos a
ferramenta exige login, enquanto os mesmos/outros passos já funcionam sem pedir"*.

Mapa da inconsistência (antes):

- **Cinco cópias locais** do gate, com o mesmo nome mas contratos diferentes:
  `music._require_cli` (checava binário **+ login** ✅), `storyboard/service._cli_ready` e
  `storyboard/router._cli_ready` (binário + login ✅), `animate/router._cli_ready`
  (**só binário** ❌ — o mesmo nome, mas "esquecia" o login) e `export/service.start_reframe`
  (login inline, só no generate).
- **mood, animate e moodboards-multishot** não checavam login na geração: deslogado, o erro
  estourava lá no subprocess do CLI, virando um 409/500 genérico em vez de um aviso claro.
- **Mensagens diferentes** para a mesma condição ("sem login (higgsfield auth login)", "não
  autenticado", "faça login no CLI…").
- **Custo vs. geração:** algumas rotas barravam login já no `/cost`; outras deixavam o `/cost`
  responder com `total=null` e só barravam no `/generate`.

## Decisão

Criar **um gate central** em `studio/higgsfield.py` e aplicá-lo de forma consistente:

- `hf.require_cli()` — levanta `hf.CliUnavailable` quando o CLI está **ausente** OU **deslogado**.
  A exceção carrega `installed: bool` para o frontend distinguir "instale" de "faça login".
- Mensagens únicas: `hf.NO_CLI_MSG` ("CLI da Higgsfield não instalado") e `hf.NO_LOGIN_MSG`
  ("Faça login no Higgsfield (higgsfield auth login)… Você também pode gerar na UI do Higgsfield e
  importar aqui.").
- Um `@app.exception_handler(hf.CliUnavailable)` mapeia a exceção para **409** com
  `{"detail", "installed"}`, sem cada rota reescrever o `raise HTTPException`.

**Onde o gate DURO de login se aplica — a regra de consistência:**

- **Geração paga** (`/*/generate`, `/export/reframe`, `/multishot/generate`, storyboard ideação/
  ângulos/vídeo): **sempre** `require_cli()` antes de gastar. Fecha os buracos de mood, animate e
  moodboards-multishot.
- **Custo** (`/*/cost`): caminho **SUAVE** — só exige o binário (`hf.available()`), nunca barra
  login com 409. Devolve a estimativa ou `total=null` quando o CLI não estima; a UI mostra o aviso
  padrão "faça login" sem 500. Preserva a decisão `base-cli-generation` (a tela trata `total=null`).
- **Importar do histórico** (`/*/import/history`): caminho **SUAVE** — só o binário. É o escape do
  usuário deslogado ("gere na UI e importe aqui"), então não barra login; uma falha do CLI vira 502.

As cinco cópias locais passam a delegar em `hf.require_cli()` (o `storyboard/service` reembala como
`Precondition` para casar com a matriz de erros da etapa).

## Consequências

- **Fidelidade (ADR-004):** troca de implementação, não de processo — o método do curso não muda;
  o que muda é *onde e como* o app avisa que falta login. Registrado aqui por ser desvio de
  comportamento observável (rotas que antes não pediam login agora pedem, na geração).
- **ADR-002:** nada de novo caminho para a Higgsfield — o gate só olha `hf.available()`/`status()`,
  ambos já vindos do CLI oficial.
- **ADR-016:** custo/livro-caixa intactos — o gate roda **antes** de `hf.cost`/`hf.generate`; a
  ordem projeto-404 → CLI-409 é preservada em cada rota.
- **UX consistente:** a mesma condição gera a mesma mensagem e o mesmo 409 em toda etapa; o
  `installed` deixa o frontend escolher entre "instale o CLI" e "faça login".
- **Testes:** novos testes do helper (`test_require_cli_*` no bridge) e do gate unificado de
  geração (mood); o teste do histórico do storyboard passa a documentar o caminho suave (login não
  barra o import). Suíte verde.

## Nota de diagnóstico (ambiente)

No ambiente onde o CLI `higgsfield`/`hf` não está no PATH, **todas** as rotas pagas respondem 409
por `NO_CLI_MSG` — isso é esperado e não é o bug. O bug de código era a **divergência** entre rotas
quando o CLI existe mas está deslogado; é isso que este ADR unifica.
