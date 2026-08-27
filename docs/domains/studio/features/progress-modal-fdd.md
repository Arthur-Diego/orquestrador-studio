### FDD: progress-modal — modal de progresso para ações de LLM e processamentos em sequência

Task-Id: ADH-OS-20260827-06 · Domínio: studio (shell) · Base: `develop@2f3a4f1`
Pedido do dono do produto (27/08/2026): "toda interação com o claude-cli ou que gere algum tipo de
ação externa para gerar algo usando LLM, abra um modal com os passos mostrando o que está sendo
feito e progredindo" + "não vi o modal aparecendo quando as chamadas ao modelo ou algum
processamento em sequência".

### 0. Princípio: progresso HONESTO (nada de barra falsa)

Duas naturezas de ação no app:
- **Jobs** (geração paga Higgsfield / render ffmpeg / scrape): já são assíncronos com
  `{state, done, total, log:[…]}` (`studio/common/jobs.py`) e já são pollados. → o modal mostra os
  passos REAIS do `log` + estado + `done/total`.
- **Chamadas síncronas ao Claude** (`prompter` → `claude -p`, bloqueante, até 180 s): não têm
  sub-passos. → o modal mostra as FASES reais ("preparando referência + mood", "consultando o
  Claude (<modelo>)", "formatando no padrão do bot", "pronto") com **cronômetro ao vivo**; o texto
  descreve o que está de fato acontecendo, sem inventar porcentagem.

### 1. Componentes novos no shell (`studio/web/ui.js` + `ui.css` — ADR-010)

`Studio.ui.progress({ title, subtitle?, steps? })` → abre um `.modal` (reusa a base do `modal()`)
e devolve um handle:
- `.step(label)` — adiciona um passo com spinner (marca o anterior como ✓);
- `.ok(label?)` — marca o passo atual como ✓ (e adiciona um passo final se `label`);
- `.fail(msg)` — marca o passo atual como ✗ e mostra o erro (botão "Fechar");
- `.note(html)` — área livre (ex.: mostrar o resultado);
- `.close()` — fecha; cronômetro (`mm:ss`) atualizado enquanto aberto.
- Sem foco-trap novo: reusar o comportamento do `modal()` (Esc/backdrop/✕). Enquanto uma ação está
  em curso, o modal não deve ser fechável por engano (sem ✕ até terminar; ou ✕ só cancela a UI, não
  o job — deixar claro). Decisão: manter ✕ desabilitado até `ok`/`fail`.

`Studio.ui.progressJob({ title, subtitle?, start, jobUrl, done?, label? })` → helper sobre
`progress` + `poll`:
- chama `start()` (dispara o POST que cria o job), abre o `progress`, e `poll(jobUrl)` renderizando
  cada linha nova de `log` como passo e `done/total` como progresso; resolve quando
  `state ∈ {done,error,idle-com-resultado}`; `fail` em `state==="error"` (mostra `error`).
- retorna uma Promise que resolve com o job final (ou rejeita no erro).

### 2. Onde ligar

**A) Chamadas ao Claude (síncronas) → `Studio.ui.progress`** (fases + cronômetro):
todos os botões que POSTam num endpoint que chama o `prompter` (Claude):
- etapa 2 mood: "Gerar prompt" (`POST …/mood/prompts/generate`)
- etapa 3 base: "Gerar prompt" e "Gerar sem viés" (`POST …/base/prompts/generate`)
- moodboard: "Gerar prompt" (`POST …/moodboards/{mbid}/prompt/generate`)
- etapa 4 storyboard: "Montar instrução" (`POST …/storyboard/instructions`) — se chamar o bot
- etapa 5 shots / etapa 6 animate / etapa 7 music: os geradores de prompt/instrução que usam o bot
Fases padrão para o modo `images`: `["Preparando referência + mood (N imagens)", "Consultando o
Claude (<modelo>)…", "Formatando no padrão do bot", "Pronto"]`; no modo `template` o modal quase
não aparece (é instantâneo) — pode pular o modal quando `mode==="template"`.

**B) Jobs (processamento em sequência) → `Studio.ui.progressJob`** (log real):
- etapa 1 refs: scrape (`…/refs/job`)
- etapa 2 mood: geração CLI (`…/mood/generate` + `…/mood/job`)
- etapa 3 base: geração CLI (`…/base/generate` + `…/base/job`)
- etapa 5 shots: `…/shots/generate` + `…/shots/job` (e product)
- etapa 6 animate: `…/animate/generate` + `…/animate/job`
- etapa 7 music: `…/music/generate` + `…/music/generate/job`; "Assistir a história" (`…/music/story/render` + `…/music/story/job`)
- etapa 8 edit: render (`…/edit/render` + `…/edit/render/job`)
- etapa 9 export: render (`…/export/render` + `…/export/job`)
- etapa 11 prospect: teaser (`…/prospect/leads/{id}/teaser` + `…/prospect/job`)
Manter o `confirmCost` antes das gerações pagas (o modal de progresso abre DEPOIS da confirmação).
Onde já existe polling próprio da view, trocar pelo `progressJob` (fonte única) — sem quebrar os
testes de substring que checam classes/handlers.

### 3. Backend (mínimo)

Não é obrigatório mudar o backend — o modal usa o que já existe (`log`, `state`, `done/total`) e as
fases client-side das chamadas síncronas. **Melhoria opcional** (se barato): garantir que os jobs de
geração/render anexem ao menos 2–3 linhas de `log` legíveis (ex.: "preparando", "chamando CLI/ffmpeg",
"baixando/encodando", "pronto") para o modal ter passos reais — sem inventar. Não converter as
chamadas síncronas do Claude em jobs nesta feature (fora de escopo; as fases client-side bastam).

### 4. Acessibilidade e bordas

- `role="dialog"`, `aria-live="polite"` na lista de passos.
- Erro do Claude/CLI (timeout, indisponível) → `fail(msg)` com a mensagem real da API; nunca deixa o
  modal travado "carregando".
- Se a ação for instantânea (`template`), não piscar o modal.
- Um modal por vez; abrir um novo fecha o anterior.
- Sem scroll horizontal; dark+light; usa os tokens do catálogo.

### 5. Testes

- `tests/test_api.py`: `Studio.ui.progress` e `Studio.ui.progressJob` existem no `ui.js`; os views
  ligam o progresso nas ações de LLM/job (checar substrings, ex.: `ui.progress(` / `ui.progressJob(`
  nos `view.js` relevantes). Não reduzir o baseline; ajustar asserts que fixavam o antigo `loading`
  se for o caso (na mesma PR, justificando).
- Não há runner de JS: a prova de comportamento é o smoke Playwright abaixo.

### 6. Verificação (antes da PR)

- `make verify` verde.
- Smoke Playwright (server real, Claude disponível): 
  1. etapa 2/3/moodboard "Gerar prompt" → o **modal aparece** com as fases e some com o prompt pronto;
  2. um job (ex.: `edit/render` com fixtures via ffmpeg, ou `export`) → o modal aparece e mostra as
     linhas de `log` progredindo até "pronto".
  Capturar prints (modal LLM + modal job) fora do git.

### 7. Fora de escopo

- Converter as chamadas síncronas do Claude em jobs com eventos server-side (evolução futura).
- Cancelar um job em andamento pelo modal (só fechar a UI; o job segue no backend).
