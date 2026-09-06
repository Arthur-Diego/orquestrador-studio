---
status: pending
title: Frontend — padrão visual da campanha e herança de preset por foto
type: frontend
complexity: high
---

# Task 4: Frontend — padrão visual da campanha e herança de preset por foto

## Overview

Fecha o card #98: nasce o bloco "Padrão visual da campanha" no topo da etapa 4, que grava as cinco
ações de preset de uma vez pelas rotas `preset-config` **já existentes** (nenhuma rota nova), e o
`RealismField` por foto passa a ter herança explícita. Corrige o defeito que anula o default
configurado: `genVideoPrompt` deixa de mandar `preset: null` sempre e passa a **omitir** o campo
quando a foto herda. É a task 8 e 9 da Build Order (§11).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O bloco `#sbCampaignPreset` ("Padrão visual da campanha") MUST ficar no topo da etapa 4, ler
  `GET /api/prompter/presets?pid=<pid>` e mostrar o valor resolvido.
- Quando as ações do conjunto resolvem para presets **diferentes**, o seletor MUST exibir
  "(misto)"; escolher um valor MUST nivelar todas.
- Escolher um preset MUST disparar, em série, `PUT /api/projects/{pid}/prompter/preset-config
  {kind, preset}` para cada `kind` do conjunto `["storyboard.script", "storyboard.keyframe",
  "storyboard.angles", "motion", "base"]` (mais `"mood"` quando a caixa "aplicar também ao mood
  board" estiver marcada). Escolher "(herdar do global)" MUST disparar
  `DELETE /api/projects/{pid}/prompter/preset-config/{kind}` para os mesmos `kind`.
- **Nenhuma rota nova.** As rotas de escrita já existem e são tipadas em `schema.ts`.
- Falha parcial MUST reportar **quais `kind` falharam** e recarregar o estado real do servidor.
  Sem retry automático.
- O `RealismField` (por foto e o do roteiro) MUST passar a ter três opções distintas:
  "(padrão da campanha: X)" com valor **vazio** (herda, é o default), "(sem preset)" com valor
  `off`, e cada preset do catálogo.
- `PhotoMeta.preset` MUST virar três estados no cliente e MUST ser persistido em
  `photos[img].preset` por `buildPayload`, e relido por `seedPhotos` (hoje devolve `null` sempre).
- `genVideoPrompt` MUST **omitir** a chave `preset` do corpo quando a foto herda, mandar
  `preset: null` quando o usuário escolheu "(sem preset)" e mandar o id quando escolheu um
  (critérios C2 e C3). Este é o ponto exato onde o default hoje é anulado.
- A tela MUST gravar o preset resolvido devolvido pela resposta em
  `photos[img].origin.<campo>.preset`.
- O bloco MUST ser espelhado na etapa 3 (`studio/etapas/base/ui/index.tsx`) — leitura e escrita do
  mesmo padrão, sem duplicar lógica de negócio.
- **Contrato de DOM congelado**: `scripts/qa/cenarios/storyboard.py` NÃO pode ser editado. Nada
  nesta task pode alterar `.sb-pick`, a ação primária do `PickerModal`, o botão "Sem imagem",
  `.sbVidPrompt`, `.sbVidPromptBox` ou `.sbVidPromptText`.
- O vitest existente `studio/etapas/storyboard/ui/storyboard.test.tsx` **pode** ser ajustado (não é
  oráculo congelado): a asserção de `.sbRealismPreset` ganha a opção nova. As asserções de ordem
  dos painéis e de `.sbVidPromptText` continuam válidas e MUST continuar passando.
- `studio/etapas/storyboard/ui/Angles.tsx` MUST permanecer **intocado** (é de F07).
</requirements>

## Subtasks

- [ ] 4.1 Criar o bloco `#sbCampaignPreset` no topo da etapa 4, lendo `GET /api/prompter/presets`.
- [ ] 4.2 Implementar o estado "(misto)" e o nivelamento ao escolher.
- [ ] 4.3 Implementar a escrita em série dos cinco `kind` (e `mood` opcional) e o `DELETE` para
      "(herdar do global)".
- [ ] 4.4 Implementar o relatório de falha parcial por `kind` e a recarga do estado real.
- [ ] 4.5 Dar ao `RealismField` as três opções de herança, com o vazio como default.
- [ ] 4.6 Passar `PhotoMeta.preset` a três estados em `types.ts`, `buildPayload` e `seedPhotos`.
- [ ] 4.7 Corrigir `genVideoPrompt` para omitir/`null`/id conforme o estado.
- [ ] 4.8 Gravar o preset resolvido da resposta em `origin.<campo>.preset`.
- [ ] 4.9 Espelhar o bloco na etapa 3 (`studio/etapas/base/ui/index.tsx`).
- [ ] 4.10 Escrever `studio/etapas/storyboard/ui/ideation-preset.test.tsx` com os casos abaixo e
      ajustar a asserção de `.sbRealismPreset` em `storyboard.test.tsx`.
- [ ] 4.11 (**OPCIONAL — só se sobrar tempo**) C5: coluna "preset" por ação no painel
      Créditos › Modelos default (`frontend/src/areas/creditos/CreditosArea.tsx` +
      `CreditosArea.test.tsx`), gravando o default **global** pela rota existente
      `PUT /api/prompter/preset-config`. Pode sair do PR sem prejuízo.

## Implementation Details

Arquivos a modificar: `studio/etapas/storyboard/ui/Ideation.tsx`,
`studio/etapas/storyboard/ui/types.ts`, `studio/etapas/storyboard/ui/storyboard.test.tsx`,
`studio/etapas/base/ui/index.tsx`; criar `studio/etapas/storyboard/ui/ideation-preset.test.tsx`.
Opcional: `frontend/src/areas/creditos/CreditosArea.tsx` + teste.

Fluxo completo em `_techspec.md` §4 (fluxo principal 3) e contratos consumidos em §5.8. A
semântica de três estados que precisa sobreviver de ponta a ponta está no objetivo "Três estados
de preset preservados" (§2) e na invariante 6 (§6).

**Não criar rota nova.** As quatro rotas de preset já existem e estão tipadas em
`frontend/src/api/schema.ts`. Esta task não deve rodar `make frontend-schema`.

Pontos exatos do código (levantados nesta worktree):

- `studio/creditos/router.py`: `_preset_defaults(pid)` :136-144 **itera todas as chaves de
  `settings.PRESET_ACTIONS`** — por isso as duas chaves novas registradas na task_01 aparecem
  automaticamente em `defaults` (critério C6). `GET /api/prompter/presets` :154-161 (404 por
  `project_dir(pid)` :160; devolve `{"presets", "defaults"}`) · `PUT /api/prompter/preset-config`
  (global) :169-174 · **`PUT /api/projects/{pid}/prompter/preset-config` :177-184** ·
  **`DELETE /api/projects/{pid}/prompter/preset-config/{kind}` :187-194**.
- `studio/common/settings.py` (**somente leitura**): `preset_default_for` :241-265 devolve
  `{kind, preset, source}` com `source ∈ {"project","global","code"}` — é o `source` que o bloco
  mostra; `resolve_preset` :268-280.
- `studio/etapas/storyboard/ui/Ideation.tsx`: `SCRIPT_ACTION = "storyboard.script"` :35 ·
  `seedPhotos` :98-113 (**devolve `preset: null` sempre** — é o bug a corrigir) ·
  `buildPayload` :116-134 (**não envia `preset`** — outro lado do mesmo bug) ·
  `resolveScriptPreset` :269-275 (usa só `storyboard.script`) · `scriptDefaults` lido no boot
  :278-355 · `persist` :386-391 · **`genVideoPrompt` :515-543**, com
  `const preset = m.preset ? m.preset : null;` :519 e `preset` no corpo :525 — **é aqui que o
  default da campanha é anulado hoje** · `RealismField` usado no painel 02 :1081 e no
  `AnimateModal` :1888.
- **`RealismField` :1534-1558**: hoje só tem `<option value="">(sem preset)</option>` mais o
  catálogo. A mudança é: `value=""` passa a significar **herda** com o rótulo
  "(padrão da campanha: X)", e nasce `value="off"` com o rótulo "(sem preset)". A classe
  `sbRealismPreset` e o `aria-label` MUST ser preservados (o vitest existente os afirma).
- `studio/etapas/storyboard/ui/types.ts`: `PhotoMeta` :63-70 tem `preset: string | null`, onde
  `null` hoje significa "seletor intocado". Passa a precisar de três estados distintos.
  `SbStatus` :28-38 já tem `script_cli?` e `script_preset_default?`.

`make frontend-build` e o commit de `studio/web/dist/` ficam para a task_07 (fechamento), para não
gerar três bundles conflitantes ao longo da cadeia de frontend.

### Relevant Files

- `studio/etapas/storyboard/ui/Ideation.tsx` — `RealismField`, `PhotoRow`, `AnimateModal`,
  `genVideoPrompt`, `buildPayload`, `seedPhotos`, `scriptDefaults`, `resolveScriptPreset`, o bloco
  `STYLE`. É o arquivo central da frente.
- `studio/etapas/storyboard/ui/types.ts` — `PhotoMeta.preset`, `PhotoEntry`, `Scene`.
- `studio/creditos/router.py` — **somente leitura**: as quatro rotas de preset-config.
- `studio/common/settings.py` — **somente leitura**: `preset_default_for` (projeto → global →
  código) e `resolve_preset` (três estados).
- `studio/etapas/base/ui/index.tsx` — já lê os defaults de preset; recebe o espelho do bloco.
- `frontend/src/api/` — `api()` e os hooks TanStack Query; nenhum hook deriva prontidão de etapa.

### Dependent Files

- `studio/etapas/storyboard/ui/Ideation.tsx` — as tasks 05 e 06 continuam editando o **mesmo**
  arquivo; por isso a cadeia é serializada.
- `studio/web/dist/` — rebuildado na task_07.

### Related ADRs

- ADR-035 — "preset global" nesta feature é **exclusivamente** o preset de REALISMO; reintroduzir
  o combo de fórmulas da aula (`#sbPreset`) é proibido.
- ADR-016 — modelo/preset default por ação, resolvido projeto → global → código.
- ADR-004 — o preset é `[extensão]` opt-in; o default de código continua `None`.
- ADR-042 (a criar na task_07) — item 1 da Decisão (preset por foto como contrato de três estados).

## Deliverables

- Bloco "Padrão visual da campanha" gravando as cinco ações em um clique, com "(misto)" e falha
  parcial por `kind`.
- `RealismField` com herança explícita e três opções.
- `photos[img].preset` persistido e relido; `genVideoPrompt` omitindo o campo na herança.
- Espelho do bloco na etapa 3.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Não há `_tests.md` — casos completos abaixo. Vitest com jsdom, sem rede (fetch fingido).

- [ ] O bloco `#sbCampaignPreset` renderiza com o valor resolvido de
      `GET /api/prompter/presets?pid=`.
- [ ] Quando os cinco `kind` resolvem para presets diferentes, o seletor mostra "(misto)".
- [ ] Escolher um preset dispara **cinco** `PUT .../prompter/preset-config`, um por `kind`, com o
      `kind` correto em cada corpo (critério C1).
- [ ] Com a caixa "aplicar também ao mood board" marcada, dispara **seis**.
- [ ] Escolher "(herdar do global)" dispara cinco `DELETE .../preset-config/{kind}`.
- [ ] Falha em dois dos cinco `PUT` mostra a mensagem citando **os dois `kind`** e refaz o
      `GET /api/prompter/presets`.
- [ ] `RealismField` renderiza as três opções, com "(padrão da campanha: X)" selecionada por
      default e valor vazio.
- [ ] Com a foto herdando, `genVideoPrompt` POSTa um corpo que **não contém** a chave `preset`
      (asserção sobre `Object.keys` do corpo, não sobre o valor) — critério C2.
- [ ] Com "(sem preset)" escolhido na foto, o corpo contém `preset: null` — critério C3.
- [ ] Com um id escolhido na foto, o corpo contém esse id.
- [ ] O preset resolvido devolvido na resposta é gravado em `origin.video_prompt.preset` no
      payload do `PUT /scenes` seguinte.
- [ ] `buildPayload` envia `photos[img].preset` nos três estados (chave ausente / `null` / id) e
      `seedPhotos` relê os três corretamente de um `GET /scenes` (critério C4 no cliente).
- [ ] O vitest existente de ordem dos painéis e de `.sbVidPromptText` continua passando sem
      alteração de comportamento.
- [ ] O bloco espelhado aparece na etapa 3 e grava pelos mesmos `kind`.
- [ ] (opcional C5) A coluna "preset" aparece no painel Créditos e grava o default global pela
      rota existente (critério C7).

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde (typecheck + lint + vitest).
- `scripts/qa/cenarios/storyboard.py` **não** foi editado (`git diff` vazio para o arquivo).
- `studio/etapas/storyboard/ui/Angles.tsx` **não** foi editado.
- Nenhuma rota nova; `frontend/src/api/schema.ts` **não** muda nesta task.
