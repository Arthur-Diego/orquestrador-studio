---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 1399
severity: high
author: claude-code
provider_ref:
---

# Issue 002: dragover lê getData(): drop nunca habilita no navegador real

## Review Comment

`lerArrasto` decide pelo CONTEÚDO (`dt.getData(...)`), e `onSceneDragOver`/`onDragOverPhoto` a usam para decidir o `preventDefault()`. No HTML5 o drag data store está em *protected mode* durante `dragenter`/`dragover`: `types` é legível, mas `getData()` devolve `""` em Chrome, Firefox e Safari. Logo `lerArrasto` devolve `null` no `dragover`, o `preventDefault()` nunca acontece, o alvo não vira drop target e o evento `drop` **nunca dispara**. O critério B6 inteiro (arrastar ideia→cena, foto→outra cena, foto→foto, classes `.dragging`/`.dragover`) não funciona em produção.

A suíte não pega porque o `DataTransfer` falso de `ideation-fotos.test.tsx:141` devolve o dado em `getData` sempre — valida um comportamento que o navegador não oferece.

**Correção:** separar as leituras — `aceitaArrasto(dt)` no `dragover`, decidindo só por `dt.types.includes(DND_IDEA) || dt.types.includes(DND_PHOTO)`; manter `lerArrasto` (com `getData`) só no `drop`. Ajustar o fake do teste para devolver `""` em `getData` ao simular `dragover`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
