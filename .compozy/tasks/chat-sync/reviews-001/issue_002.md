---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T09:16:18Z
status: resolved
file: frontend/src/areas/chat/ChatDock.tsx
line: 22
severity: low
author: claude-code
provider_ref:
---

# Issue 002: scope desconhecido some sem rastro e torna "não sincronizou" indiagnosticável

## Review Comment

`mudancaDoEvento` valida o `scope` contra o enum fechado do Contrato 1 e devolve `null` quando não
reconhece:

```tsx
const scope = ESCOPOS.find((e) => e === ev.scope);
if (!step || !scope) return null;
```

A validação está certa e o teste "evento fora do Contrato 1 (sem step nem scope) some em silêncio"
a cobre. O problema é o **silêncio**, não o descarte.

A ADR-041 que esta frente cria diz que o protocolo "só cresce" e que o cliente tolera o
desconhecido. A consequência prática é que uma versão futura do backend pode emitir um `scope` novo
(a §5 do `_techspec.md` chama o enum de "fechado **nesta versão**") e este dock vai descartá-lo sem
deixar nenhum vestígio no browser. Quando o usuário reportar "não sincronizou", quem investiga não
tem sinal nenhum do lado do cliente: a §7 do `_techspec.md` aponta o transcript
(`events.jsonl`) e `/trace` como o log da feature, mas ambos são do **servidor** e mostrarão o
evento emitido corretamente. O rastro que falta é exatamente o do lado que o engoliu.

Note que `frontend/src/shell/events.ts:101` já faz o oposto no caminho vizinho — o assinante que
lança gera `console.error("[studio] assinante de useStudioChange lançou", …)`. O descarte silencioso
aqui é inconsistente com essa escolha.

**Correção sugerida:** um `console.warn` no ramo de descarte, apenas quando o kind era de fato
`state_changed` (para não ruidar em evento de outro kind), com `step`, `scope` e `tool` para amarrar
o efeito à causa:

```tsx
if (!step || !scope) {
  console.warn("[studio] state_changed fora do Contrato 1, ignorado", ev.step, ev.scope, ev.tool);
  return null;
}
```

Custo: uma linha, nenhum impacto no caminho quente (o ramo só roda em evento malformado), e nenhuma
mudança no contrato. Não usar `console.error`: o descarte é comportamento previsto, não falha.

## Triage

- Decision: `VALID`
- Notes: O descarte silencioso é real e inconsistente com o `console.error` que
  `frontend/src/shell/events.ts:101` já faz no caminho vizinho. Causa raiz: a ADR-041 criada por esta
  frente promete tolerância ao desconhecido, e tolerar sem registrar deixa o cliente sem rastro
  justamente no caso que a ADR prevê (backend mais novo com `scope` novo); o transcript e `/trace`
  citados na §7 do `_techspec.md` são do servidor e mostrariam o evento emitido corretamente.
  Correção aplicada: `console.warn` no ramo de descarte de `mudancaDoEvento`
  (`ChatDock.tsx`), com `step`, `scope` e `tool`. `warn` e não `error` porque o descarte é
  comportamento previsto. O teste "evento fora do Contrato 1 … some em silêncio" continua verde
  (ele afirma ausência de publicação, não ausência de log).
