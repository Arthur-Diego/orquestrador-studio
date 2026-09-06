# PRD: chat-navigate — o assistente leva a tela junto

Task-Id: ADH-OS-20260906-10
Card: #88 https://trello.com/c/YNf9Rcwj
Wave: 11 (frente F08, sub-wave 2; depende de F03 chat-sync e F04 mcp-pick-shape, ambas integradas)
TechSpec normativa: `_techspec.md` (cópia do FDD aprovado em lote,
`docs/domains/chat/features/chat-navigate-fdd.md`)

> Este `_prd.md` existe apenas como adaptação de interface do pipeline SDD. **A fonte de verdade
> normativa é o `_techspec.md`.** Em qualquer divergência, o `_techspec.md` vence.

## Problema

O assistente conduz a campanha inteira pelas tools `mcp__studio__*` (ADR-040), mas não consegue
levar a tela junto. O único jeito de trocar de etapa a partir do chat é o widget `open`
(`ui.open_screen`), que **bloqueia o turno** e exige dois cliques do usuário ("Abrir a tela" e
"Concluí"). O laço `open → done` previsto no ADR-038 nunca fecha sozinho, porque nenhuma tela
publica conclusão. O relato do dono: ele confirma as fotos de referência no chat e a tela continua
na etapa 1.

Somam-se quatro defeitos de contorno: (1) `ui.open_screen` envia `params` que o `AskCard` ignora e
o registro da tool não expõe; (2) `ui_choose_images` e `ui_form` existem como helpers e **não**
estão registradas como tools; (3) `navigate` do shell só sabe montar `#/<pid>/<view>`, então
`ui_open("moodboards")` gera `#/<pid>/moodboards`, que a guarda do roteador descarta em silêncio;
(4) alvo não pronto joga o usuário no overview sem nenhuma explicação — numa navegação automática
isso ficaria pior, a tela mudaria sozinha para o lugar errado.

## Requisitos funcionais

- **RF1.** Existe uma tool `ui_navigate(target, reason)` **não bloqueante** que pede ao browser para
  trocar de tela. O turno do agente não espera resposta (usa `/emit`, nunca `/ask`).
- **RF2.** O dock decide se navega. Duas guardas antes de agir: o evento é ao vivo (`seq` acima da
  marca d'água de replay) e o toggle "seguir o assistente" está ligado.
- **RF3.** A decisão de prontidão é sempre **posterior** ao refresh do guia: o dock invalida o guia
  (`invalidarGuia`, contrato de F03) e espera o agregado voltar, com teto de 1500 ms.
- **RF4.** "Pronto" são duas checagens distintas e explícitas: **navegável** = etapa no catálogo
  `/api/steps` com `status === "ready"`; **liberada** = guia daquela etapa com `status !== "blocked"`.
  Nenhuma prontidão é calculada no cliente (ADR-010 item a) — só se comparam campos que o backend
  mandou.
- **RF5.** Nenhuma navegação recusada é silenciosa: para todo alvo recusado sai exatamente um cartão
  `notify` no transcript com o motivo, e o hash **não** muda.
- **RF6.** O usuário pode desligar a navegação automática a qualquer momento (toggle ligado por
  padrão, persistido em `localStorage`). Com o toggle desligado, nenhum evento do chat altera
  `location.hash`; o cartão vira um botão "Ir agora".
- **RF7.** Um `open` pendente de tela opt-in (`refs`, `mood`, `base`) fecha sozinho quando a etapa
  alvo **transita** para `done` no guia; um `open` cuja etapa **já estava** `done` no nascimento do
  `ask` nunca é auto-respondido.
- **RF8.** `navigate` do shell passa a montar também as áreas globais `moodboards[/<mbid>]`,
  `creditos` e `characters`, sem alterar a gramática do hash e sem mudar o resultado de nenhuma
  chamada existente. **Este contrato é consumido pela frente F12.**
- **RF9.** `ui_open` expõe `params` no registro da tool, e o dock entrega esses `params` ao shell por
  um barramento de intenção sticky de um disparo.
- **RF10.** `ui_choose_images` e `ui_form` passam a existir como tools registradas.
- **RF11.** Eventos `navigate` vindos de replay (`GET /events`) ou com `seq` já executado nunca
  navegam: viram cartão histórico. Cada `seq` é executado no máximo uma vez.
- **RF12.** Zero rota HTTP nova e zero modelo Pydantic novo: `frontend/src/api/schema.ts` e
  `frontend/openapi.json` ficam byte a byte iguais.

## Não-objetivos

- Navegar para **outra campanha** (`ui_navigate` age sempre na campanha ativa do shell).
- Query string no hash ou qualquer outra mudança de gramática de rota.
- Fazer alguma tela **consumir** `params` nesta frente: o canal é publicado e testado; os
  consumidores são F11/F12 e as etapas.
- Publicação de conclusão pelas telas (o `done` automático é derivado do guia).
- Novo endpoint HTTP, novo modelo Pydantic, regeneração de `schema.ts`.
- Botão Parar, rótulos de tool, markdown na bolha (F01/F02) e `state_changed` em si (F03).

## Restrições do repositório (não negociáveis)

- ADR-004: o que o curso não ensina é `[extensão]` e fica marcado como tal no código.
- ADR-038: o agente pergunta, o browser decide; escolha visual e gasto continuam humanos, **sem
  exceção**. A flexibilização desta wave (o `done` derivado do guia) entra como seção
  "Adendo (Wave 11)" **dentro do ADR-038** — não se cria ADR novo.
- ADR-010 item a: prontidão de etapa vem sempre do guia do backend.
- ADR-010 item b / ADR-031 / ADR-032: tocar `frontend/` ou `studio/web/` exige declarar a branch
  `feature/adh-os-20260906-10-chat-navigate` em `TITULARES_DO_NUCLEO`
  (`tests/test_adr010_fronteira_nucleo.py`), no TOPO do dict, preservando TODAS as entradas
  existentes com suas tuplas.
- Toda tool nova registrada em `studio/mcp/server.py` PRECISA de entrada em
  `studio/chat/mudancas.py::TOOL_STEPS` (`None` para as que não mudam artefato) — o teste de drift
  por AST em `tests/test_chat_mudancas.py` reprova sem isso.
- Qualquer mudança em `frontend/` exige `make frontend-build` e commit de `studio/web/dist/`.
- ADR-008: testes sem rede e sem navegador. Vitest sem `--watch`.
- Cenários de `scripts/qa/cenarios/` **não** se editam.
- Commits: `feat(chat): <descrição em pt-BR> [extensão]` com trailer `Task-Id: ADH-OS-20260906-10`.

## Critérios de aceite

Os 15 critérios da seção 9 do `_techspec.md`. Os critérios 14 e 15 são `[cross-feature]` e só são
verificáveis no estado integrado da wave — ficam registrados como pendência da integração, não são
implementáveis nesta frente.
