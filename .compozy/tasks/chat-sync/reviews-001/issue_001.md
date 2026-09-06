---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T09:16:18Z
status: resolved
file: frontend/src/areas/characters/CharactersArea.tsx
line: 123
severity: medium
author: claude-code
provider_ref:
---

# Issue 001: CharacterDetail não assina o barramento e repete o defeito do card #87

## Review Comment

`CharactersArea` assina `useStudioChange("characters", …)` corretamente (linha ~52), mas o
componente `CharacterDetail` (linha 123), que é o que fica na tela enquanto o usuário trabalha um
personagem, **não assina nada**. E ele é justamente a tela que mostra o artefato que as tools de
personagem produzem.

O mecanismo de refresh de `CharacterDetail` é um poll condicionado a `busy`:

```tsx
useEffect(() => {
  if (!busy) return;                       // <- só polla se a PRÓPRIA tela disparou
  timer.current = window.setInterval(async () => { … }, 2000);
```

`busy` só vira `true` quando o usuário clica em explorar/gerar ficha **nessa tela**. Se o
`character_explore` ou o `character_sheet` for disparado **pelo chat** — que é exatamente o cenário
desta feature — `busy` continua `false`, o poll nunca liga, e nem `carregar()` nem `setJob` rodam.
O `character_wait` termina, o `state_changed {pid: null, step: "characters", scope: "candidates"}`
chega, `CharactersArea` recarrega a **lista** por trás, e a ficha aberta continua exibindo o estado
velho até o usuário voltar e entrar de novo.

Esse é o mesmo defeito do card #87 ("a grade só aparece ao sair e voltar"), uma tela mais fundo. A
§11 do `_techspec.md` (ordem 6) lista literalmente só `CharactersArea.tsx`, então a task_04 cumpriu
a letra da spec — mas a §2 declara o objetivo como "a tela da etapa correspondente, se estiver
montada, recarrega seus dados sem intervenção do usuário", e a ficha do personagem montada não
recarrega.

**Correção sugerida:** assinar o barramento também em `CharacterDetail`, reusando o `carregar()` que
já existe e religando o poll quando o job voltar `running` — o mesmo padrão que a tela de refs usa
(`studio/etapas/refs/ui/index.tsx:222-239`):

```tsx
useStudioChange("characters", () => {
  void (async () => {
    await carregar();
    const j = (await api(`/api/characters/${cid}/job`).catch(() => null)) as Job | null;
    setJob(j);
    if (j?.state === "running") setBusy(true);   // religa o poll que já existe
  })().catch(() => { /* aviso do chat é best-effort */ });
});
```

Cuidado ao aplicar: `CharacterDetail` não tem campo de texto recarregável em edição além de `brief`
— **não** sobrescrever `brief` (é o buffer que o usuário digita, §10 Risco 5 do `_techspec.md`).

## Triage

- Decision: `VALID`
- Notes: Confirmado no código. `CharacterDetail` (`CharactersArea.tsx:123`) tem `carregar()` e um
  `setInterval` de 2 s, mas o poll é guardado por `if (!busy) return` e `busy` só vira `true` em
  `explorar()`/`gerarSheet()` — as duas ações da PRÓPRIA tela. Job disparado pelo chat deixa a ficha
  congelada. Causa raiz: a §11 (ordem 6) do `_techspec.md` lista só `CharactersArea.tsx`, e a task_04
  cumpriu a letra; a §2 pede que "a tela da etapa correspondente, se estiver montada, recarregue".
  Correção aplicada: `useStudioChange("characters", …)` também em `CharacterDetail`, reusando
  `carregar()` e religando o poll existente com `setBusy(true)` quando `GET /api/characters/{cid}/job`
  volta `running`. `brief` deixado de fora (buffer editável, §10 Risco 5). Teste novo
  `frontend/src/areas/characters/CharactersArea.test.tsx` com 3 casos (lista recarrega, ficha
  recarrega, ficha religa o poll) — o segundo falha sem a correção.
