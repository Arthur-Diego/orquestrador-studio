# ADR-011: A cena do produto permanece na etapa 5, decidida na etapa 7

**Status:** Aceito
**Data:** 2026-08-25
**Módulo:** MUSIC
**ADRs relacionados:** [ADR-003](../STUDIO/ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-009](ADR-009-deteccao-de-batidas-com-numpy-e-ffmpeg.md), [ADR-010](../STUDIO/ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e problema

A aula 013 tem uma ordem explícita: primeiro pôr **todas as cenas em ordem na timeline, sem cortar nada**, assistir a sequência inteira e decidir se *"a história está fechada ou se falta alguma cena"* — é aí que *"fica claro quando é necessário criar um encerramento mais forte ou mais comercial"* (a cena extra do produto; no exemplo do plano, a lata na geladeira congelada). Só depois vem a trilha.

A implementação da wave 1 pôs a criação da cena do produto na **etapa 5** (`shots/service.py`, `product_scene`), onde ficam todas as imagens finais por cena, e a etapa 7 nem mostrava a sequência bruta. A auditoria de fidelidade (`wave-2-auditoria-etapas-7-11.md`, itens 7.1 e 7.2) classificou isso como **desvio de ordem** registrado apenas no FDD, sem ADR — o que o gate 4 do `CLAUDE.md` proíbe.

Havia duas leituras possíveis: mover a criação da cena do produto para dentro da etapa 7 (fiel ao momento da aula) ou mantê-la na etapa 5 (fiel ao artefato e ao pipeline de geração de imagem).

## Decisão

**A cena do produto continua sendo criada na etapa 5** (`shots/storyboard.json → product_scene`, imagens em `shots/produto/`), e a **decisão** sobre ela passa a acontecer na etapa 7, onde a aula a coloca:

1. A etapa 7 ganha o passo 0 — `audio/rough_sequence.mp4`, concat dos takes com *like* na ordem do storyboard, **sem música e sem corte nenhum** — e a pergunta da aula, gravada em `audio/story_check.json` `{closed, note, decided}`.
2. Quando a resposta é "falta cena", a tela leva o usuário de volta às etapas 5 (criar a cena do produto) e 6 (animá-la), com atalhos diretos.
3. O guia da etapa 7 avisa quando `product_scene` é nulo (*"a aula manda que o comercial termine mostrando o produto"*); o guia da etapa 8 avisa quando a cena do produto não é o último clipe.
4. O passo 0 **não** grava `edit/timeline.json`: a aula é explícita em que ali ainda não se edita. Ele reusa `edit.initial_timeline()` em leitura e `render.build_filtergraph(target="rough", out=…)`; usar `edit.get_timeline()` seria criar a montagem antes da trilha, exatamente o que a aula proíbe.

## Alternativas consideradas

1. **Mover a criação da cena do produto para a etapa 7**: fiel ao instante da aula, mas duplicaria em `music` todo o pipeline de imagem da etapa 5 (referência, prompts, candidatas, upscale, seleção) e quebraria o contrato `shots/storyboard.json`, consumido pelas etapas 6 e 8. Rejeitada: o artefato é o mesmo, muda só o momento em que a falta dele fica evidente.
2. **Deixar como estava e só documentar no FDD**: é o estado que a auditoria reprovou — desvio de ordem sem registro e sem nada na tela que reproduzisse o passo mais importante da aula ("enxergar a história como um todo").
3. **Gerar a sequência bruta na etapa 8 e linkar da 7**: a etapa 8 grava timeline ao ler; qualquer atalho para ela cria a montagem antes da trilha e viola a regra central da aula 013.

## Consequências

- Positivas: a ordem da aula fica visível na tela (assistir → decidir → escolher a trilha) sem duplicar pipeline de imagem; a decisão vira artefato (`story_check.json`) e entra no guia e no progresso da etapa; `shots/storyboard.json` continua a única fonte da ordem das cenas.
- Negativas: a criação da cena do produto continua fisicamente em outra tela — o usuário navega 7 → 5 → 6 → 7. Os atalhos e o aviso do guia reduzem o custo, mas o desvio de lugar permanece e está registrado aqui.
- O render da sequência bruta gasta CPU (concat completo em 1080p, job em thread — ADR-006) e depende do ffmpeg; sem ffmpeg o passo 0 mostra o aviso e a etapa segue.
