---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T15:02:13Z
status: resolved
file: tests/test_chat_css_feedback.py
line: 32
severity: low
author: claude-code
provider_ref:
---

# Issue 005: a guarda de `chat.css` deixou de provar "sem alterar nenhuma regra existente"

## Review Comment

T-CSS-02 do `_tests.md` afirma duas coisas: *"o bloco novo fica no **fim** de `chat.css`, **sem
alterar nenhuma regra existente**"*. A guarda atual só prova a primeira metade.

`_prefixo()` (`tests/test_chat_css_feedback.py:32-40`) corta o arquivo no MARCADOR e as asserções
sobre esse prefixo são: (a) a string `PRECEDENTE` (uma única regra,
`@media (prefers-reduced-motion: reduce) { .chat-tab-dot.st-running { animation: none; } }`) ainda
está lá, e (b) nenhuma das 5 classes de `CLASSES_NOVAS` aparece acima do marcador. Isso não detecta
alteração, reordenação ou remoção de **qualquer outra** das ~250 linhas anteriores de `chat.css`.
A versão anterior (contagem de linhas + `sha256` do arquivo) detectava.

Não há violação real neste diff — `git diff origin/develop...HEAD -- frontend/src/areas/chat/chat.css`
é `40 insertions(+), 0 deletions(-)`, tudo depois do marcador. O problema é o poder de detecção
futuro: uma rodada de `cy-fix-reviews` ou um rebase que reescreva uma regra acima do marcador passa
verde.

O afrouxamento tem justificativa legítima (o `sha256` do arquivo inteiro reprovaria a cada frente
vizinha da Wave 11 que acrescenta regras próprias — a F01 acrescentou `.chat-md*`), mas a
justificativa não obriga a perder as duas metades: dá para fixar o `sha256` **do prefixo até o
marcador tal como estava no merge-base** (as frentes vizinhas acrescentam blocos próprios, não
reescrevem os já existentes), ou, mais barato e estável, asseverar que o conjunto de seletores
acima do marcador é um SUPERSET do conjunto do baseline de `develop`, o que continua tolerando
acréscimos e volta a acusar edição/remoção.

Prioridade baixa: nada está errado hoje; é dívida de guarda.

## Triage

- Decision: `UNREVIEWED`
- Notes:

## Resolução (F02, antes do PR)

A metade 'sem alterar regra existente' voltou como asserção sobre SOBRESCRITA, que é o dano real: `test_css_02_nenhuma_regra_existente_foi_alterada` extrai os seletores de primeiro nível do prefixo e do bloco novo e reprova em qualquer interseção — um seletor repetido depois do marcador alteraria a regra de cima pela cascata sem tocar na linha dela. Sem voltar ao pin de sha256, que reprovava por frente vizinha.
