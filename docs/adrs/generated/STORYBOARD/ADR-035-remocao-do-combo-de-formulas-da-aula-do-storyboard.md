# ADR-035: Remoção do combo de fórmulas da aula (`#sbPreset`) do Storyboard

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-02 (reconcilia o antigo PR #103 / ADH-OS-20260831-16)
**ADRs relacionados:** [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-015](../STUDIO/ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-031](../STUDIO/ADR-031-frontend-em-react-vite-com-etapa-de-build-e-dist-versionado.md), [ADR-032](../STUDIO/ADR-032-plugin-de-ui-da-etapa-em-ui-index-tsx-descoberto-por-import-meta-glob.md)

## Contexto e Problema

A etapa 4 (Storyboard) publicava um **combo de fórmulas da aula** (`PRESETS` no
`studio/storyboard/service.py`, exposto na chave `presets` de `GET .../storyboard/instructions`
e renderizado como o `<select id="sbPreset">` "— fórmulas da aula —"). Eram atalhos prontos
tipo *"Make the climber even smaller and more realistic"*. **A pedido do dono do produto**, esse
atalho deve sair: a instrução é escrita à mão pelo operador, sem fórmula pré-pronta.

Esta decisão reconcilia o antigo PR #103 (ADH-OS-20260831-16), que fazia a mesma remoção mas foi
escrito **antes do corte React (Wave 10)** — ele editava o vanilla `view.html`/`view.js`, que a
E10 removeu, e reivindicava o número **ADR-033**, já ocupado pelo motor de imagem local
(ADR-033). Por isso a remoção foi **reimplementada na versão React** e o ADR **renumerado para 035**.

## Decisão

Remover o combo de fórmulas da aula do Storyboard:

1. **Backend** (`studio/storyboard/service.py`): apagar a constante `PRESETS` e a chave `"presets"`
   do retorno de `presets()`. As demais chaves (`kinds`, `suffix`, `counts`, `models`, `arc`,
   `upscale_note`) permanecem.
2. **Frontend** (`studio/etapas/storyboard/ui/`): remover o `<select id="sbPreset">` do
   `Ideation.tsx`, o campo `presets` do default de `meta` e o tipo `PresetMeta`/campo `presets` de
   `InstructionsMeta` (`types.ts`). O `sbText` (instrução à mão) e os `kinds` seguem.
3. **Testes**: remover os testes que exercitavam a chave publicada `presets`
   (`test_published_presets_round_trip_through_the_validator`,
   `test_every_published_preset_is_accepted_by_the_validator`, o mock `presets` do vitest), e
   afirmar `"presets" not in presets()`.

**Não confundir** com o preset de **REALISMO** (`REALISM_PRESETS` / `/api/prompter/presets`), que é
outra feature e **permanece intacto**.

## Fidelidade ao curso (ADR-004)

O combo era uma conveniência de UI, não um passo que a aula 010 exige — a aula manda escrever a
instrução. Removê-lo a pedido do dono não afasta a etapa do que a aula ensina; a regra de "uma
instrução por vez" (validador) e os `kinds` da aula continuam.

## Consequências

- A tela fica mais simples; a instrução é sempre autoral. Um atalho a menos para manter.
- Contrato `GET .../storyboard/instructions` perde a chave `presets` (consumidores que a liam
  precisam parar — no repo, só a própria tela lia, já ajustada).
- `schema.ts` inalterado (a chave não era tipada); `studio/web/dist/` rebuildado (UI mudou), com
  titularidade de núcleo declarada em `tests/test_adr010_fronteira_nucleo.py`.
