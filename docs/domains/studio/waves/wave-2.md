# Wave 2 — Guia por etapa, shell profissional e fidelidade ao roteiro

Data: 2026-08-25 · Orquestração: `/dd-parallel` (W0–W5) · Task-Ids: `ADH-OS-20260825-06` (preparo) e `OS-013` … `OS-019`
Terreno: `docs/domains/studio/recon-wave-2.md` · Auditorias de fidelidade: `wave-2-auditoria-etapas-{1-3,4-6,7-11}.md`

## Objetivo

1. **Fidelidade ao roteiro**: corrigir tudo que as auditorias apontaram como desvio de processo, falta, texto de tela enganoso ou extensão sem marca, nas 11 etapas.
2. **Guia por etapa**: cada tela diz o que a aula manda fazer, quais entradas faltam, quais validações passam/falham e qual é a próxima ação — calculado pelo backend lendo os artefatos do projeto (ADR-003).
3. **Shell profissional**: navegação com estado por etapa, progresso da campanha, visão geral (dashboard), wizard rápido de campanha, componentes compartilhados (`Studio.ui`), roteamento por URL, sem timers órfãos.

Pedido do dono do produto: "criar campanhas o mais rápido possível, com todos os passos claros e explicativos; nas telas, o que fazer, o que está faltando e todas as validações possíveis".

## Contrato transversal: o guia (`studio/common/guide.py`)

Cada plugin pode exportar `studio/etapas/<id>/guide.py` com `def guide(pid: str) -> dict`, **puro** (só lê arquivos do projeto; nunca cria/regrava artefatos; nunca chama CLI/ffprobe). O núcleo descobre o módulo em `discover()` (chave `guide`, opcional) e expõe:

- `GET /api/projects/{pid}/guide` → `{steps: [Guide…], done: int, total: int, progress: float, current: <id da primeira etapa não concluída>}`
- `GET /api/projects/{pid}/guide/{step}` → `Guide`

```json
{
  "id": "base", "n": 3, "title": "Imagem base", "aula": "009",
  "status": "todo|blocked|in_progress|done",
  "progress": 0.0,
  "what": "O que fazer nesta etapa (3–6 frases, pt-BR, fiel à aula)",
  "checklist": ["Checklist de qualidade da aula, em bullets"],
  "inputs":  [{"id": "refs_selected", "label": "≥ 1 referência escolhida", "status": "ok|fail", "detail": "…", "fix": "Volte à etapa 1 e salve a seleção", "step": "refs"}],
  "outputs": [{"id": "base_final", "label": "base/base_final.png", "status": "ok|todo", "detail": "…"}],
  "validations": [{"id": "upscale_2x", "label": "Upscale 2x (aula 009)", "status": "ok|warn|fail|todo", "detail": "…", "fix": "…"}],
  "missing": ["labels de inputs/outputs não ok"],
  "next_action": "Frase única com a próxima ação recomendada",
  "next_step": "storyboard"
}
```

Regras de derivação (em `guide.py` comum, `build()`): `inputs` com `fail` → `blocked`; nenhum `output` ok → `todo`; todos os `outputs` ok → `done`; senão `in_progress`. `progress` = outputs ok / outputs. `validations` nunca bloqueiam (`warn`/`fail` viram itens em "atenção"). Etapas sem `guide.py` recebem um guia genérico a partir de `META` (`status: "unknown"`).

Helpers: `Guide(meta)`, `.input(id, label, ok, detail=None, fix=None, step=None)`, `.output(...)`, `.check(id, label, status, detail=None, fix=None)`, `.text(what, checklist)`, `.build(next_step=...)`; `exists(pid, rel)`, `read_json(pid, rel)`, `count_files(pid, rel, exts)`.

## Contrato transversal: `Studio.ui` (`studio/web/ui.js` + `ui.css`)

Carregado pelo `index.html` antes dos plugins. API mínima entregue pelo preparo (a frente `shell` pode estender, nunca remover):

- `Studio.ui.esc(s)`; `chip(text, kind)`; `hfChip(el)` (usa `/api/higgsfield/status` cacheado 60 s pelo backend); `drop(el, onFiles)`; `upload(url, files, field="files")`; `confirmCost(costFn, label)`; `poll(fn, ms) → {stop()}` (toda instância de plugin expõe `destroy()` que para os polls; `app.js` chama `destroy()` ao trocar de tela); `guide(el, guideObj)` renderiza o painel padrão (o que fazer / entradas / saídas / validações / próxima ação); `renderGuide(stepId)` busca e renderiza no `#guide` da tela.
- Convenção de tela: todo `view.html` começa com `<header class="stephead">` (mantém `Etapa N · aula X`) seguido de `<section id="guide" class="guide"></section>`; `view.js` chama `Studio.ui.renderGuide("<id>")` em `onProject()` e após cada ação que muda artefatos.

## Núcleo (preparo)

- `GET /api/projects/{pid}` → `project.json` + `{progress, current}`; `PATCH /api/projects/{pid}` `{name?, product?, vibe?, aspect_ratio?, brand?}` (`vibe` passa a ser opcional na criação — a aula 009 encontra a vibe na etapa 2; `aspect_ratio` `[extensão]` default `16:9`, escolhido pelo destino — aula 007).
- `GET /api/higgsfield/status` com cache de 60 s (`?refresh=1` força).
- `PROJECT_LAYOUT` completo (`base, storyboard, shots, animate, publish, prospect, mood/vibe`).
- HLD studio v1.2: regra "só o preparo/shell edita `app.py`, `index.html`, `app.js`, `steps.py`"; seção do guia e do `Studio.ui`.

---

## Features e contratos

### Feature: shell (OS-013) — núcleo web
**Provides**
- `studio/web/{index.html, app.js, style.css, ui.js, ui.css}` redesenhados: menu com estado por etapa (todo/blocked/in_progress/done + progresso), barra de progresso da campanha, painel de guia por etapa (`Studio.ui.guide`), visão geral da campanha (`#/overview`: cards das 11 etapas com status, faltas e atalho), wizard "Nova campanha" (nome, produto, vibe opcional, formato por destino), roteamento por hash (`#/<pid>/<step>`), `destroy()` nas trocas de tela, tema claro/escuro, responsivo.
- Painel inicial "Como o Studio segue o curso" (texto da auditoria §4.3).
**Consumes**
- `GET /api/projects/{pid}/guide` ← preparo
- `Studio.ui` contrato ← preparo
**Cross-feature:** com os 11 `guide.py` mergeados, a visão geral mostra 11 cards com status real no projeto `2026-08-wave-teste`; nenhuma etapa mostra `unknown`.

### Feature: refs+mood (OS-014) — etapas 1–2 · aula 009
**Provides** `studio/etapas/{refs,mood}/guide.py`; correções R1–R5, M1–M5, M8, M10, G8, G10 da auditoria 1–3 (marca validada nos termos; fonte Explore; textos; `notes` por card `[extensão]` ou remoção; **remover "no product/no text/no logos" forçado** no mood e corrigir atribuição "(aula 009)" em tela/HLD/FDD/teste; CLI do mood usa imagens de vibe/grid como referência; campo "prompt copiado do Explore"; `_refs_summary` fora do prompt de mood; `palette.json` marcado `[extensão]`; "Ultimate"); mood grava `project.vibe` no `select` via `PATCH /api/projects/{pid}`.
**Consumes** `Studio.ui`, `guide.py` comum, `PATCH /api/projects/{pid}` ← preparo.

### Feature: base (OS-015) — etapa 3 · aula 009
**Provides** `studio/etapas/base/guide.py`; correções B1–B6, B10, B11 (prompt de situação via `prompter.from_images("base", …)` com referência + mood, template só como fallback; separar "instrução ao bot (sessão sem viés)" de "prompt para gerar"; exigir `mood/selected/`; prompts editáveis; `count=3` no rótulo; validação do upscale ≈2×; "no people" opcional; dever de casa no checklist).
**Consumes** `Studio.ui`, `guide.py` comum ← preparo; `common/prompter.py` (já em develop).

### Feature: storyboard+shots (OS-016) — etapas 4–5 · aulas 010, 011 (+013)
**Provides** `studio/etapas/{storyboard,shots}/guide.py`; correções 4.1–4.6, 5.1–5.8 (botões "Gerar 4/1" renomeados; `source_id` no CLI; estrutura começo/descoberta/ação/desfecho; heurística de instrução única relaxada; `gpt_image_2` `[extensão]`; upscale visível/avisado por frame; "usar como base da cena"; bloco de câmera no `edit`; `shots/storyboard.md`; placeholders da aula; marcas `[extensão]` em 16:9/2k/RED; nota da aula 013 no painel do produto).
**Consumes** `Studio.ui`, `guide.py` comum ← preparo.

### Feature: animate (OS-017) — etapa 6 · aula 012
**Provides** `studio/etapas/animate/guide.py`; correções 6.1–6.8 (**start/end gravado e enviado ao CLI**, end = próximo shot por padrão, aceita `edit/last_frames`; `veo3_1_lite` `[extensão]` fora da ordem padrão; nota Kling 2.6/2.5 Turbo → 3.0; dica Creative Engine; paralelismo na UI; sugestão de adaptar a ideia após 6 falhas; 16:9/pro `[extensão]` com override; Seedance sugerido no modo elaborado).
**Consumes** `Studio.ui`, `guide.py` comum ← preparo; `edit/last_frames/*.png` ← edit (já em develop).

### Feature: music+edit (OS-018) — etapas 7–8 · aulas 013, 014
**Provides** `studio/etapas/{music,edit}/guide.py`; correções 7.1–7.4, 7.7, 8.1–8.5, 8.9, 8.10 (**passo "assistir a história inteira"**: `audio/rough_sequence.mp4` concat dos takes liked sem música + decisão "falta cena?"; licença opcional/`[extensão]`; "3 a 5" removido; quadro preto opcional (`black_dur=0` padrão); master exige trilha (409); zoom por clipe; loudnorm `[extensão]`/opcional; régua de impactos na timeline; textos literais).
**Consumes** `Studio.ui`, `guide.py` comum ← preparo; `animate/takes.json`, `shots/storyboard.json` (já em develop).
**Nota:** a cena do produto permanece na etapa 5 (mesmo artefato) — ADR-010 registra o desvio de ordem (aula 013).

### Feature: export+publish+prospect (OS-019) — etapas 9–11 · aulas 014, 015, 001/016
**Provides** `studio/etapas/{export,publish,prospect}/guide.py`; correções 9.1–9.2, 9.5, 10.1–10.4, 11.1–11.5, 11.8, 11.9 (**portfólio global**: `GET /api/portfolio` = projetos distintos com post registrado; gate de prospect consome isso; comunidade ABRAhub como rede + checklist; textos; QA/thumb/1:1 `[extensão]`; **teaser só após `replied`** (422); `post_ref` obrigatório; tabela do pitch com valores por etapa, total e 50 % off; lembretes literais; segmentos da aula; sugestão de offset no impacto).
**Consumes** `Studio.ui`, `guide.py` comum ← preparo; `edit/master.mp4`, `export/*.mp4` (já em develop).
**Cross-feature:** `prospect.gate` lê o portfólio global; teste com 2 projetos.

## Grafo e sub-waves

```
preparo ─┬─ shell (OS-013)
         ├─ refs+mood (OS-014)
         ├─ base (OS-015)
         ├─ storyboard+shots (OS-016)
         ├─ animate (OS-017)
         ├─ music+edit (OS-018)
         └─ export+publish+prospect (OS-019)
```

Sub-wave 0 = preparo (PR único, mergeado antes de tudo). Sub-wave 1 = as 7 frentes em paralelo (arquivos disjuntos: `studio/web/*` só na shell; cada frente só nas pastas das suas etapas + `docs/domains/<etapa>/` + `tests/test_<etapa>_*`). Integração W5 em ordem: shell → refs+mood → base → storyboard+shots → animate → music+edit → export+publish+prospect (ordem do curso, para o smoke visual seguir o pipeline).

## Critérios cross-feature (cobrados na W5)

1. `GET /api/projects/2026-08-wave-teste/guide` devolve 11 etapas sem `unknown`, com `done`/`in_progress` coerentes com os artefatos existentes.
2. Smoke visual (Playwright, script do orquestrador): as 11 telas renderizam com o painel de guia, sem erro de JS, claro e escuro.
3. Todo plugin expõe `destroy()` e nenhum timer sobrevive à troca de tela (teste HTTP não cobre; verificado no smoke por contagem de requisições após navegação).
4. `pytest` ≥ 392 + novos, `ruff` limpo; strings fixadas por teste preservadas (recon §Atenção).

## Decisões do lote (auto-aceites do orquestrador)

1. Guia calculado no backend por leitura pura de arquivos; nenhum estado novo em `project.json` além de `vibe` (já existia) e `aspect_ratio` `[extensão]`.
2. Testes de UI continuam por asserts HTTP/strings (ADR-008); o smoke Playwright é ferramenta do orquestrador fora do CI.
3. Extensões recomendadas pelas auditorias entram marcadas `[extensão]` (autorização do dono do produto nesta wave: "tome todas as decisões recomendadas"); as que a auditoria mandou só **mencionar** (mood board de filme, leads globais) ficam como texto no guia.
4. Gate 1 (specs em lote) pré-aprovado pelo dono do produto; cada frente escreve o FDD em modo batch e implementa em seguida; auto-aceites consolidados na retro.
5. Frentes de etapa nunca editam `studio/web/*`, `app.py`, `steps.py`; a shell nunca edita plugins.
6. Trello indisponível (board inexistente): PR + final report são o registro.
