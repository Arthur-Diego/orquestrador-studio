# ADR-023: Modelo default da transição start/end passa a ser a Kling 3.0 `[extensão]`

**Status:** Aceito
**Data:** 2026-08-29
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260829-37
**Substitui:** [ADR-021](ADR-021-video-preview-por-cena-no-storyboard-e-mapa-de-modelos-kling.md) — **parcialmente**, só a parte de MODELO da transição start/end (§Decisão 4). O resto da ADR-021 (vídeo-preview por cena no storyboard, rotas, JobRegistry por cena, campos aditivos de `scenes.json`, Kling 2.6 na cena) continua vigente.
**ADRs relacionados:** [ADR-002](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-016](ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-021](ADR-021-video-preview-por-cena-no-storyboard-e-mapa-de-modelos-kling.md), [ADR-022](ADR-022-video-por-foto-no-storyboard-modelo-selecionavel-e-ponte-para-o-downstream.md)

## Contexto e Problema

A **ADR-021** (wave 7) mapeou a transição **start/end** da aula 012 para a **Kling 3.0 Turbo**
(`kling3_0_turbo`), no lugar do "Kling 2.5 Turbo" da aula — que **não existe** no CLI da Higgsfield.
A escolha foi feita pelo custo medido (`generate cost`: 5 s = 7,5 créditos) **sem conferir o catálogo
de parâmetros do modelo**.

O QA da rodada 2026-08-29 (apontamento **AP-18**, card <https://trello.com/c/lUy1wmEI>) mostrou que o
mapa é **impossível de executar pelo CLI**. O catálogo real (`higgsfield model get <id> --json`) diz:

| modelo | parâmetros declarados |
| --- | --- |
| `kling3_0_turbo` | `aspect_ratio, duration, prompt, resolution, start_image` |
| `kling3_0` | `aspect_ratio, duration, end_image, mode, prompt, sound, start_image` |
| `kling2_6` | `aspect_ratio, duration, prompt, sound, start_image` |

A `kling3_0_turbo` **não declara `end_image` nem `mode`**. Uma transição start/end é, por definição,
`start_image` + `end_image`: gerar a transição da aula com a 3.0 Turbo é impossível. Enquanto a ponte
(`studio/higgsfield.py`) mandava tudo ao CLI, o `--end-image` era silenciosamente ignorado (saía um
image-to-video simples do frame inicial, cobrado igual); com a ponte filtrando por
`hf.model_params` (ADH-OS-20260829-34), a geração passa a ser **recusada** com "não aceita
`end_image`" — ou seja, o default da ADR-021 deixa o caminho start/end **inoperante**.

Somado a isso, o QA registrou (**C-ANIMATE-35**) que o modal da etapa 5 nem oferecia o modelo de
transição: o `<select>` era montado só a partir de `plan.model_order` (a ordem de progressão por
falhas), que não contém o modelo de transição.

## Motivadores da Decisão

- **A transição da aula precisa acontecer** (ADR-004, gate 1): o modo start/end é o que a aula 012
  ensina para transições. Um default que o CLI recusa é o mesmo que não ter o modo.
- **Ponte só via CLI oficial** (ADR-002): o catálogo do `model get` é a fonte de verdade dos
  parâmetros aceitos; não há caminho alternativo para injetar `end_image`.
- **Mesma família, menor mudança** (correção mínima): `kling3_0` é o Kling que declara
  `end_image` **e** `mode` — é a troca de id mais próxima do que a ADR-021 decidiu, sem tocar no
  método da etapa.
- **Custo antes de gastar** (ADR-016): a diferença de crédito é conhecida, medida e visível na tela
  de custos antes de gerar.

## Decisão

**1. A transição start/end passa a usar `kling3_0` (Kling 3.0).** A cena continua em `kling2_6`
(Kling 2.6) — a ADR-021 não muda nesse ponto. Concretamente:

- `studio/common/settings.py`: `DEFAULTS["storyboard.video.transition"] = {"model": "kling3_0", "variant": "5s"}`
  (era `kling3_0_turbo`). `storyboard.video.scene` e `animate.video` continuam `kling2_6`.
- `studio/animate/service.py`: `TRANSITION_MODEL = "kling3_0"`; `model_for_mode("start_end")` devolve
  `kling3_0`; `LESSON_MODEL_NOTE` passa a dizer por que a 3.0 Turbo saiu.
- `accepted_models()` continua aceitando `kling3_0_turbo`: ele segue no catálogo de preços, é
  ofertável no seletor do storyboard (ADR-022) e é o modelo gravado em takes antigos.

**2. Regra permanente: o modelo de transição PRECISA declarar `end_image`.** Qualquer troca futura
do default de `storyboard.video.transition` / `TRANSITION_MODEL` é válida apenas se o catálogo do
CLI (`hf.model_params(<id>)`, alimentado por `higgsfield model get --json`) listar `end_image` para
aquele id. É a mesma checagem que a ponte aplica em tempo de execução (ADH-OS-20260829-34): param
essencial (`prompt`, `start_image`, `end_image`) que o modelo não declara vira erro explícito, nunca
um clipe silenciosamente errado.

**3. A tela da etapa 5 expõe o modelo do modo.** O `<select>` do modal "Gerar take N"
(`studio/etapas/animate/view.js`) passa a incluir e pré-selecionar `plan.transition_model` no modo
start/end e `plan.scene_model` nos modos simples/elaborado, em vez de só `plan.model_order` (que
segue sendo a ordem de progressão por falhas). Trocar o modo no modal troca o modelo, sem ida ao
servidor. O backend já expunha `scene_model` / `transition_model` desde a ADR-021.

**4. A tabela de custos NÃO muda.** `pricing.CATALOG` continua listando `kling3_0_turbo`
(5 s = 7,5 / 10 s = 15) — ele só perdeu o papel de default de transição.

## Opções Consideradas

1. **`kling3_0` como transição** (escolhida): mesma família, declara `start_image` + `end_image` +
   `mode`, custo conhecido (5 s = 10, 10 s = 20 créditos). Custa **+2,5 créditos em 5 s** frente à
   3.0 Turbo, e é o único jeito de a transição sair do CLI.
2. **Manter a 3.0 Turbo e cair para image-to-video simples quando houver `end`:** entrega um clipe
   que não é a transição da aula, cobrando igual — desvio silencioso do método (proibido pelo gate 4
   do `CLAUDE.md`).
3. **`seedance_2_0` como transição:** também declara `end_image`, mas é o modelo de *movimento
   complexo* da aula e o clipe mais caro do catálogo (22,5 créditos) — trocaria o método e o custo.
4. **Esperar a Higgsfield publicar um turbo com `end_image`:** deixaria o modo start/end quebrado por
   tempo indeterminado. Se isso acontecer, volta a ser **troca de config** (defaults + CATALOG), não
   de código.

## Consequências

- **Custo sobe na transição:** 10 créditos por clipe de 5 s (20 em 10 s), contra 7,5 (15) da 3.0
  Turbo — **+33%** por transição. É o preço de a transição existir de verdade. O livro-caixa
  (ADR-016) e a confirmação de custo antes de gerar continuam iguais; a mudança aparece na tela de
  custos e no modal.
- **Regra de validação:** o modelo de transição precisa declarar `end_image` no catálogo do CLI,
  verificado por `hf.model_params`. Um id sem `end_image` no papel de transição é defeito, não
  preferência.
- **Retrocompatibilidade:** takes e vídeos gerados antes com `kling3_0_turbo` continuam válidos e
  legíveis (o id segue no `pricing.CATALOG` e em `accepted_models()`); nada é migrado.
- **ADR-021 fica parcialmente substituída:** só o §Decisão 4 na parte "transição → Kling 3.0 Turbo".
  A ADR-021 recebeu nota no topo apontando para cá; nada foi apagado dela.
- **QA pina a decisão:** `C-ANIMATE-35` (etapa 5, modal start/end) e `C-STORYBOARD-29` (etapa 4,
  modal "Gerar animação") leem o modelo da API (`plan.transition_model` /
  `video_model_defaults.start_end`) e falham se a UI parar de oferecer o modelo do modo.

## Referências

- Card do apontamento: <https://trello.com/c/lUy1wmEI> (AP-18) · relatório
  `docs/qa/reports/2026-08-29-smoke/relatorio.md`
- `docs/adrs/generated/STUDIO/ADR-021-*.md` — decisão substituída em parte (§Decisão 4)
- `studio/common/settings.py` — default `storyboard.video.transition`
- `studio/animate/service.py` — `TRANSITION_MODEL`, `model_for_mode`, `accepted_models`, `LESSON_MODEL_NOTE`
- `studio/storyboard/service.py` — `video_model(pid, mode)` (resolve pelo `settings`)
- `studio/etapas/animate/view.js` — `modelosDoModo`/`modelSelect` (modelo por modo no modal)
- `studio/higgsfield.py` — `model_params` / `adapt_params` (ADH-OS-20260829-34), a validação que
  torna a regra executável
- `scripts/qa/cenarios/animate.py` (C-ANIMATE-35) e `scripts/qa/cenarios/storyboard.py` (C-STORYBOARD-29)
