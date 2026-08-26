# FDD: shell profissional do Studio (OS-013)

Domínio: `studio` · Task-Id: `OS-013` · Wave: 2 · Data: 2026-08-25
Modo: **batch** — Gate 1 (spec) pré-aprovado em lote pelo dono do produto
(`waves/wave-2.md` §"Decisões do lote" #4). Todo ponto que exigiria entrevista foi decidido
aqui e está rotulado `[auto-aceito: …]`.
Spec normativa: `docs/domains/studio/waves/wave-2.md` §"Feature: shell (OS-013)".
Terreno: `docs/domains/studio/recon-wave-2.md` · API consumida:
`docs/domains/studio/waves/wave-2-api-transversal.md` · HLD: `docs/domains/studio/hld.md`.

---

## 1. Problema e objetivo

O shell atual (`studio/web/`, 38 + 77 + 72 linhas) é um esqueleto: menu sem estado por etapa,
sem visão da campanha, sem roteamento por URL, formulário de criação de projeto solto na
sidebar e nenhum lugar onde o usuário veja **onde está, o que falta e para onde ir**. O dono do
produto pediu duas coisas: "a ferramenta o mais profissional possível" e "criar campanhas o
mais rápido possível, com todos os passos claros e explicativos".

Objetivo desta feature: transformar o shell em um **painel de condução da campanha** — estado
real por etapa vindo do guia do backend, progresso da campanha, visão geral navegável, guia por
etapa hierarquizado, wizard rápido de campanha e roteamento por URL —, mantendo intactos o
contrato de plugin e todas as classes CSS que as 11 telas de etapa já usam.

Fora de escopo (outras frentes da wave 2): os `guide.py` das 11 etapas (OS-014…OS-019), textos
de fidelidade dentro das telas de etapa, qualquer arquivo em `studio/etapas/`, `app.py`,
`steps.py`.

## 2. Usuário e valor

Usuário único: o operador que produz uma campanha de vídeo seguindo o curso. Valor:
- abrir o Studio e, em um olhar, saber a etapa atual, o que já está pronto e o que falta;
- criar uma campanha nova em um formulário só, com o formato escolhido pelo destino (aula 007);
- voltar exatamente para onde parou (URL compartilhável + "Continuar de onde parei");
- ler, dentro de cada etapa, o que a aula manda fazer sem sair da tela.

## 3. Critérios de aceite

| # | Critério | Verificação |
| --- | --- | --- |
| A1 | A sidebar lista as 11 etapas com status real (`todo/blocked/in_progress/done/unknown`), ícone e cor por status e mini-progresso quando `in_progress` | print da visão geral; `GET /guide` alimenta o menu |
| A2 | O topo do main mostra nome da campanha, produto, formato, `done/total` + barra de progresso e "Continuar de onde parei" que abre `current` | print; clique navega para a etapa `current` |
| A3 | `#/<pid>/overview` é a tela padrão ao abrir/trocar de projeto e mostra 11 cards (título, aula, status, `missing` resumido, `next_action`, "Abrir") | print; teste de string em `tests/test_api.py` |
| A4 | O painel de guia por etapa é colapsável, com status + "faltando" **sempre visíveis** e seções hierarquizadas (o que fazer / entradas / saídas / validações / checklist / próxima ação) | print de 4 etapas; `Studio.ui.guide` |
| A5 | Wizard "Nova campanha" em modal (nome, produto, vibe opcional rotulada "(será encontrada na etapa 2)", formato por destino) cria via `POST /api/projects` + `PATCH aspect_ratio` | print do wizard; teste de string |
| A6 | Edição rápida da campanha (nome, produto, vibe, formato) via `PATCH /api/projects/{pid}` | mesmo modal em modo edição |
| A7 | Roteamento por hash `#/<pid>/<step>` e `#/<pid>/overview`, com `localStorage` como fallback; `destroy()` chamado ao trocar de tela | navegação por URL; back/forward do browser |
| A8 | O menu e o topo são atualizados depois de cada `ctx.guide()` de uma etapa | ação numa etapa reflete no menu sem reload |
| A9 | Painel "Como o Studio segue o curso" (texto da auditoria §4.3) acessível na visão geral, colapsado | print |
| A10 | Tema claro/escuro impecável (automático + alternador manual), responsivo ≤900px (sidebar vira topo), foco visível | prints claro/escuro 1440×900 |
| A11 | Todas as classes usadas pelos `view.html` atuais continuam funcionando; nenhuma função de `Studio.ui` removida ou renomeada | suíte verde + smoke visual das etapas |
| A12 | `make verify` verde (ruff + pytest ≥ 415 + novos); strings fixadas por teste preservadas | evidência no PR |

`[cross-feature]` A13: com os 11 `guide.py` mergeados, a visão geral mostra 11 cards com status
real no projeto `2026-08-wave-teste` e nenhuma etapa `unknown` — **só verificável no estado
integrado (W5)**.

## 4. Fluxo principal

1. O usuário abre `/`. `app.js` carrega `/api/steps`, `/api/projects` e resolve a rota do hash
   (ou do `localStorage`, ou o primeiro projeto).
2. Sem projeto: a tela mostra o estado vazio com o botão "Nova campanha" e o painel "Como o
   Studio segue o curso".
3. Com projeto: `GET /api/projects/{pid}` (nome, produto, formato, `progress`, `current`) e
   `GET /api/projects/{pid}/guide` (11 guias) alimentam **menu + topo + visão geral** de uma vez.
4. A visão geral é a tela padrão: 11 cards com status, o que falta e a próxima ação; "Abrir"
   navega para `#/<pid>/<step>`.
5. Ao entrar numa etapa, `app.js` chama `destroy()` da anterior, injeta o `view.html`, carrega o
   `view.js` (uma vez) e instancia a tela; o `view.js` chama `Studio.ui.renderGuide("<id>")`.
6. Cada `ctx.guide()` da etapa devolve o guia daquela etapa; o shell aproveita a resposta para
   atualizar o item do menu e recarrega o agregado para o topo (debounce).
7. "Continuar de onde parei" navega para `current`; trocar de projeto volta para a visão geral.

Fluxos alternativos: etapa `soon` (não navegável, marcada "em breve"); `view.html`/`view.js`
indisponível (mensagem no `#main` + toast, sem quebrar o shell); guia indisponível (card e
painel degradam para "sem guia", nunca somem); projeto inexistente no hash (cai para o primeiro
projeto e reescreve o hash).

## 5. Contratos

Esta feature **não publica** contrato HTTP novo — é 100 % consumidora. Não há coleção Postman
nova: as rotas consumidas são as do preparo, já cobertas por `tests/test_api.py`
`[auto-aceito: sem Postman próprio, a frente não expõe endpoint]`.

**Consome (backend, preparo):**

| Rota | Uso no shell |
| --- | --- |
| `GET /api/steps` | ordem, título, aula, `status ready\|soon` do menu |
| `GET /api/projects` | seletor de projeto |
| `POST /api/projects` | wizard (nome, produto, vibe opcional) |
| `GET /api/projects/{pid}` | topo: nome, produto, `aspect_ratio`, `progress`, `current` |
| `PATCH /api/projects/{pid}` | wizard (`aspect_ratio`) e edição rápida da campanha |
| `GET /api/projects/{pid}/guide` | menu (status por etapa), barra de progresso, visão geral |
| `GET /api/projects/{pid}/guide/{step}` | painel de guia da etapa (via `Studio.ui.renderGuide`) |
| `GET /steps/{id}/view.{html,js}` | carregamento da tela da etapa |

**Publica (contrato de frontend, consumido pelos 11 plugins — não pode quebrar):**

```js
Studio.register(id, ctx => ({ init, onProject, destroy }))
Studio.ctx = { $, api, toast, pid(), project(), files(rel), guide() }
Studio.go(stepId)                       // navega para a etapa (agora escreve o hash)
Studio.ui.{esc, chip, hfChip, drop, upload, confirmCost, poll, guide, renderGuide}
```

Extensões aditivas de `Studio.ui` nesta feature (nenhuma remoção, nenhuma renomeação):

| Novo | Contrato |
| --- | --- |
| `chip(text, kind)` | passa a aceitar também `ok\|warn\|fail\|todo\|info\|done\|mode`; `mode` continua o default |
| `Studio.ui.STATUS_KIND` | mapa `status → kind` do chip (usado pelo menu e pela visão geral) |
| `Studio.ui.modal(opts)` | modal acessível (foco preso, `Esc` fecha, clique no backdrop fecha) |
| `Studio.ui.fmtPct(x)` | `0.42 → "42%"` |
| `Studio.ui.guide(el, g)` | mesma assinatura; render novo (colapsável, resumo sempre visível) |
| `Studio.ui.renderGuide(id, el)` | mesma assinatura; passa a devolver o guia **e** avisar o shell (`Studio.onGuide`) |

Classes CSS preservadas (contrato implícito com os 11 `view.html`): `stephead`, `eyebrow`,
`lede`, `panel`, `panel-head`, `grid2`, `row`, `wrap`, `col`, `inline`, `chip` (+`ok`/`warn`/
`mode`), `status`, `progress`/`bar`, `log`, `fine`, `gallery`, `card` (+`sel`/`term`/`src`),
`drop` (+`over`), `prompt`, `prompts`, `cli`, `palette`, `empty`, `hidden`, `mono`,
`button.primary`, `button.ghost`, `button.link`, `guide*`.

## 6. Regras de negócio

| # | Regra | Origem |
| --- | --- | --- |
| R1 | O status por etapa **nunca** é calculado no frontend: vem do guia do backend (leitura pura de arquivos) | ADR-003, decisão do lote #1 |
| R2 | A vibe é opcional na criação e rotulada "(será encontrada na etapa 2)" | aula 009, G2 da auditoria |
| R3 | O formato é escolhido pelo **destino** (16:9 YouTube, 9:16 Reels/TikTok, 1:1 feed), default 16:9, marcado `[extensão]` | aula 007, G3 da auditoria |
| R4 | `unknown` é um estado de primeira classe (etapa sem `guide.py`): mostra "sem guia" e continua navegável | contrato do guia |
| R5 | Nenhum estado novo em `project.json`; o progresso é derivado | decisão do lote #1 |
| R6 | O painel "Como o Studio segue o curso" usa o texto literal da auditoria §4.3 | ADR-004 |
| R7 | O shell nunca edita plugins; os plugins nunca editam `studio/web/*` | HLD v1.2 / ADR-010 |

## 7. Erros e degradação

| Situação | Comportamento |
| --- | --- |
| `GET /guide` falha ou demora | menu e cards caem para o catálogo (`/api/steps`) sem status; nenhum erro fatal |
| `guide/{step}` falha | painel mostra "Não foi possível carregar o guia: <detail>"; a tela da etapa continua utilizável |
| `view.html`/`view.js` 404 | `#main` mostra o erro e o toast repete; o shell segue navegável |
| projeto do hash não existe | cai para o primeiro projeto e reescreve o hash |
| nenhum projeto | estado vazio com CTA "Nova campanha" |
| `POST /api/projects` 409 (nome repetido) | toast com o `detail` da API; o modal continua aberto com os dados |
| `PATCH` 422 (`aspect_ratio` inválido) | toast com o `detail`; nada é alterado |

## 8. Observabilidade

Ferramenta local de usuário único: sem métrica nem log estruturado (HLD §Observabilidade).
Erros de rede viram `toast` + mensagem na área afetada; o console fica limpo (critério do smoke
visual: nenhum erro de console). `[auto-aceito: sem telemetria — ADR-001, ferramenta local]`

## 9. Testes

Continuam sem navegador no CI (ADR-008): asserts HTTP/strings em `tests/test_api.py` e
`tests/test_steps_and_config.py` — `index.html` serve `ui.js`/`ui.css`/`app.js` e `/static/*`
responde 200; strings-chave da visão geral, do wizard e do painel do curso; classes CSS que os
`view.html` usam existem em `style.css`/`ui.css`; funções de `Studio.ui` presentes em `ui.js`.

A verificação **visual** (Playwright 1440×900, claro e escuro, visão geral + wizard + 4 etapas)
é ferramenta do desenvolvedor/orquestrador, roda fora do CI e fica registrada por prints no PR
(decisão do lote #2).

## 10. Decisões automáticas (modo batch)

1. `[auto-aceito: visão geral é a tela padrão ao abrir um projeto]` — em vez da última etapa
   visitada. A última etapa continua acessível pelo hash e por "Continuar de onde parei".
2. `[auto-aceito: alternador de tema explícito]` claro/escuro/sistema em `localStorage`
   (`studio.theme`), além do `prefers-color-scheme`. Sem isso não dá para provar os dois temas
   em print de forma determinística.
3. `[auto-aceito: wizard em modal]` em vez do formulário na sidebar — a sidebar fica só com
   marca, seletor e as 11 etapas.
4. `[auto-aceito: PATCH de aspect_ratio sempre]` na criação (inclusive `16:9`), para o projeto
   nascer com o formato explícito em `project.json`.
5. `[auto-aceito: estado colapsado do guia por etapa em localStorage]` (`studio.guide.<step>`),
   aberto por padrão.
6. `[auto-aceito: sem framework, sem CDN]` além do Google Fonts já usado (ADR-001).
7. `[auto-aceito: hash canônico `#/<pid>/<view>`]` com `localStorage` só como fallback quando o
   hash está vazio ou inválido.
8. `[auto-aceito: o agregado do guia é recarregado com debounce de 400 ms]` após `ctx.guide()`,
   para uma etapa que chama o guia várias vezes seguidas não disparar N requisições.
9. `[auto-aceito: sem Postman e sem ADR novo]` — a feature não cria contrato HTTP nem contraria
   decisão vigente; o HLD sobe para v1.3 com o parágrafo do shell.

## 11. Arquivos previstos

| Arquivo | Ação |
| --- | --- |
| `studio/web/index.html` | reescrito (sidebar, topbar, modal, tema) |
| `studio/web/app.js` | reescrito (roteador, estado do guia, visão geral, wizard) |
| `studio/web/style.css` | reescrito (design system; todas as classes antigas preservadas) |
| `studio/web/ui.js` | estendido (chips semânticos, modal, painel de guia colapsável) |
| `studio/web/ui.css` | estendido (painel de guia, cards da visão geral, modal) |
| `tests/test_api.py` | testes de string do shell |
| `tests/test_steps_and_config.py` | estáticos do shell servidos |
| `docs/domains/studio/hld.md` | v1.3 + parágrafo do shell |
| `docs/domains/studio/diagrams/mermaid/shell-navegacao.md` | novo |
| `docs/domains/studio/features/shell-fdd.md` | este arquivo |

9 arquivos de código/doc, 1 fluxo principal, 0 contratos publicados — pela regra do Passo 6 a
contagem de arquivos (>8) puxaria para SDD, mas o disparo da wave fixou **implementação
direta**; registrado como override aplicado. `[auto-aceito: implementação direta por override
do orquestrador]`

## 12. Pendências para a integração (W5)

- A13 (`[cross-feature]`): 11 cards sem `unknown` só depois dos `guide.py` das frentes
  OS-014…OS-019.
- Smoke visual das 11 telas com `<section id="guide">` no `view.html`: enquanto as frentes de
  etapa não mergeiam, o shell renderiza o painel do guia via `renderGuide` no `#guide` — as
  telas atuais ainda não têm esse `<section>`, então o painel só aparece nas etapas já migradas.
- Contagem de requisições após troca de tela (critério 3 da wave) depende do `destroy()` de
  cada plugin, entregue pelas frentes de etapa.
