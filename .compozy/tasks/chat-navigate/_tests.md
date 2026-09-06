# Contrato de testes — chat-navigate

Derivado da seção 9 do `_techspec.md`. Cada caso é atribuído a **exatamente uma** task.
Sem rede, sem navegador, sem subprocess real do `claude` (ADR-008). Vitest sem `--watch`;
pytest com `-x -q` na área antes da suíte inteira.

## Unidade — backend (pytest, `tests/test_mcp_ui.py`)

- **UT-01** `ui.navigate(cli, "mood", reason="x")` com `STUDIO_CHAT_ID=cid` posta em
  `/api/chats/cid/emit` o corpo `{"event": {"kind": "navigate", "target": "mood",
  "reason": "x"}}` e devolve uma `str` não vazia contendo `mood`.
- **UT-02** `ui.navigate(cli, "mood")` **sem** `STUDIO_CHAT_ID` não posta nada
  (`cli.posts == []`) e devolve a string de degradação
  `"Sem interface de chat aqui: peça ao usuário para abrir a tela manualmente."`.
- **UT-03** `ui.navigate` com `reason` omitido posta `reason: ""` (o campo existe sempre no evento).
- **UT-04** `ui.navigate` quando o POST levanta exceção devolve a MESMA string de sucesso e não
  propaga a exceção (matriz de erros E2/A12: `_emit` engole).
- **UT-05** `ui.open_screen(cli, "storyboard", params={"scene": "cena02"})` posta um `ask` cujo
  `payload["params"] == {"scene": "cena02"}`; sem `params`, o payload traz `{}` (comportamento
  atual preservado).

## Unidade — backend (pytest, `tests/test_mcp_server_registry.py`, arquivo NOVO)

- **UT-06** `build_server(FakeClient())` expõe, no `list_tools()`, as tools `ui_navigate`,
  `ui_choose_images` e `ui_form` (as três precisam estar registradas).
- **UT-07** O schema de entrada de `ui_navigate` tem as propriedades `target` (obrigatória) e
  `reason` (opcional).
- **UT-08** O schema de entrada de `ui_open` expõe a propriedade `params`.
- **UT-09** Toda tool registrada no servidor tem entrada em `studio/chat/mudancas.py::TOOL_STEPS`
  (guarda de drift já existente em `tests/test_chat_mudancas.py` — este caso só confirma que as
  tools novas `ui_navigate`, `ui_choose_images`, `ui_form` estão classificadas como `None`, porque
  interação com o humano não muda artefato de tela).

## Unidade — frontend puro (vitest, `frontend/src/areas/chat/navigate.test.ts`, arquivo NOVO)

A decisão de navegação é uma função pura, testada sem React e sem rede.

- **UT-10** Alvo de etapa navegável (`/api/steps` com `status: "ready"`) e guia da etapa com
  `status: "todo"` → decisão `navegar`.
- **UT-11** Alvo com guia `status: "blocked"` → decisão `recusar`, com texto contendo até 3 itens
  de `missing`, no formato `Não abri a etapa <título>: <item>; <item>.`
- **UT-12** Alvo `soon` no catálogo → decisão `recusar` com o texto
  `A tela da etapa "<alvo>" ainda não existe nesta versão do Studio.`
- **UT-13** Alvo fora do catálogo (id desconhecido) → mesma recusa de UT-12.
- **UT-14** Alvo global (`moodboards`, `moodboards/mb123`, `creditos`, `characters`) → decisão
  `navegar` **sem consultar o guia**, mesmo com `guideAll` nulo.
- **UT-15** `target` com `/` fora das áreas globais (ex.: `p1/mood`) → decisão `recusar`.
- **UT-16** `target` vazio, só espaços, ou não string → decisão `recusar` com o texto de pedido
  inválido.
- **UT-17** `pid === null` e alvo de etapa → decisão `recusar` com
  `Abra uma campanha antes de pedir para eu trocar de tela.`
- **UT-18** `pid === null` e alvo global → decisão `navegar` (área global não precisa de campanha).
- **UT-19** Guia indisponível (`guideAll === null`) e etapa navegável no catálogo → decisão
  `navegar`, sem `notify` (E8: o guia é informativo).
- **UT-20** `overview` é sempre navegável quando há `pid`.

## Unidade — roteador do shell (vitest, `frontend/src/shell/router.test.ts`)

- **UT-21** `navigate("moodboards/mb123")` produz `location.hash === "#/moodboards/mb123"`.
- **UT-22** `navigate("moodboards")` produz `"#/moodboards"`; `navigate("creditos")` produz
  `"#/creditos"`; `navigate("characters")` produz `"#/characters"`;
  `navigate("characters/c1")` produz `"#/characters/c1"`.
- **UT-23** `navigate("creditos/qualquer-coisa")` produz `"#/creditos"` (sub-rota ignorada, a área
  não tem sub-tela).
- **UT-24** `navigate("mood")` continua produzindo `"#/<pid>/mood"` e `navigate("overview")`
  continua produzindo `"#/<pid>/overview"` — nenhuma chamada existente muda de resultado.
- **UT-25** `navigate("moodboards")` sem campanha nenhuma (`pidRef` nulo) navega assim mesmo
  (a guarda `if (!p) return` de hoje só vale para alvo de campanha).
- **UT-26** `navigate` para área global com `opts.replace` usa `history.replaceState` e não empurra
  entrada nova no histórico.
- **UT-27** A resolução de rota das áreas globais (`parseHash` + o efeito) continua igual: os casos
  já cobertos pelo arquivo permanecem verdes.

## Unidade — barramento de intenção (vitest, `frontend/src/shell/events.test.ts`)

- **UT-28** `emitNavIntent({pid, target: "storyboard", params: {scene: "cena02"}})` seguido de
  `useNavIntent("storyboard", cb)` chama `cb` uma vez com a intenção.
- **UT-29** Uma segunda chamada de `useNavIntent("storyboard", cb2)` **não** chama `cb2`: consumir
  limpa (sticky de um disparo).
- **UT-30** `useNavIntent("mood", cb)` com intenção retida de `storyboard` não consome nada e deixa
  a intenção intacta para o consumidor certo.
- **UT-31** Publicar duas intenções antes de qualquer consumo mantém só a última.
- **UT-32** Os casos existentes de `emitStudioChange`/`useStudioChange` (F03) continuam verdes: o
  arquivo só cresce.

## Componente — dock (vitest, `frontend/src/areas/chat/ChatDock.test.tsx`, arquivo NOVO)

Com `QueryClient` real e WebSocket falso; `navigate` e o `POST /emit` observados por spy.

- **CT-01** Evento `navigate` ao vivo, toggle ligado, etapa navegável e liberada: `navigate(target)`
  é chamado **exatamente uma vez**, e a chamada acontece **depois** de o refresh do guia terminar
  (ordem verificada por spy).
- **CT-02** Mesmo evento com o toggle desligado: `navigate` não é chamado, `location.hash` não muda,
  e o cartão renderiza o botão "Ir agora".
- **CT-03** Clicar em "Ir agora" navega pelo mesmo caminho de decisão (etapa bloqueada continua
  sendo recusada).
- **CT-04** Alvo com guia `blocked`: `navigate` não é chamado e sai exatamente um
  `POST /api/chats/<cid>/emit` com `kind: "notify"`, `level: "warn"` e texto contendo os itens de
  `missing`.
- **CT-05** Alvo `soon`/desconhecido: `navigate` não é chamado, sai um `notify` e o hash não muda.
- **CT-06** Evento `navigate` vindo do replay (`GET /events`, sem passar pelo socket) nunca navega:
  vira cartão histórico.
- **CT-07** O mesmo `seq` entregue duas vezes pelo socket navega **uma só vez** (idempotência).
- **CT-08** O toggle persiste em `localStorage` na chave `studio.chat.follow` e nasce **ligado**
  quando a chave não existe.
- **CT-09** Guia lento: passados 1500 ms sem o agregado voltar, a decisão sai com o cache atual
  (teto respeitado, a UI não trava).
- **CT-10** `ask` de widget `open` com `params` não vazio: ao navegar, publica a intenção no
  barramento (`emitNavIntent`) com `pid`, `target`, `params` e `askId`.
- **CT-11** `open` pendente de `refs` cujo guia estava `todo` e passa a `done`: o dock envia
  `answer(askId, {done: true, auto: true})` **uma única vez**, e o cartão passa a dizer
  "Concluído automaticamente".
- **CT-12** `open` de `refs` cuja etapa **já estava** `done` quando o cartão nasceu: nenhum `answer`
  é enviado, nunca.
- **CT-13** `open` de `target` fora do opt-in (`{refs, mood, base}`), por exemplo `storyboard`, que
  transita para `done`: nenhum `answer` automático — os botões manuais continuam.
- **CT-14** O cartão do evento `navigate` mostra o `reason` quando ele existe.

## Guardas do repositório

- **GT-01** `tests/test_adr010_fronteira_nucleo.py` passa com
  `feature/adh-os-20260906-10-chat-navigate` registrada em `TITULARES_DO_NUCLEO` com os prefixos
  `frontend/` e `studio/web/`, e com TODAS as entradas anteriores preservadas.
- **GT-02** `tests/test_chat_mudancas.py` (drift por AST) passa com as tools novas classificadas.
- **GT-03** `git diff develop...HEAD --stat` mostra `frontend/src/api/schema.ts` e
  `frontend/openapi.json` **inalterados** (I6 do `_techspec.md`).
- **GT-04** `git status --porcelain -- studio/web/dist` vazio após `make frontend-build`.
- **GT-05** `make verify` e `make frontend-verify` verdes com output real.
- **GT-06** ADR-038 contém a seção "Adendo (Wave 11)" e `studio/chat/prompts/sistema.md` contém a
  regra "após uma `*_pick` bem-sucedida, chame `ui_navigate(next_step)`".

## Fora do alcance automatizado (pendências da integração)

- **XT-01** `[cross-feature]` QA manual no estado integrado: escolher as referências pelo chat
  (`refs_pick`), o guia é invalidado e a tela vai para `mood` sem nenhum clique.
- **XT-02** `[cross-feature]` `ui_navigate("moodboards/<mbid>")` abre o editor do board (critério de
  F12, verificável só depois da integração das duas frentes).
