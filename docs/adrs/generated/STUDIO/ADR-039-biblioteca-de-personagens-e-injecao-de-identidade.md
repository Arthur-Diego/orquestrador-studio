# ADR-039: Biblioteca de Personagens e injeção de identidade nas etapas 3–5

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-07
**ADRs relacionados:** [ADR-004 (fidelidade ao curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-013 (biblioteca global reutilizável)](./ADR-013-biblioteca-global-de-mood-boards-reutilizaveis.md), [ADR-033 (motor de imagem local)](./ADR-033-motor-de-imagem-local-comfyui-flux-como-segunda-ponte-de-ferramenta-externa.md), [ADR-016 (créditos)](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-002 em HIGGSFIELD (Higgsfield só via CLI)](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-037](./ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md), [ADR-038](./ADR-038-protocolo-humano-no-laco-do-chat.md)

## Contexto e Problema

O usuário pediu um recurso capaz de **"acertar o personagem e manter a identidade visual"** entre
as cenas — em foto e vídeo. O curso não ensina isso: a aula 010 manda o aluno escrever as cenas, e
a consistência de personagem fica por conta de repetir descrições à mão. O laboratório
`personagem-anime-lab/` já provou, fora da ferramenta, o fluxo "gerar muitas variações → escolher a
que acertou → reusar como base", incluindo consistência via IPAdapter e re-render em alta.

O problema: trazer isso para dentro do Studio como produto, sem contrariar a fidelidade ao curso
(ADR-004), reusando as pontes que já existem (motor local grátis — ADR-033; Higgsfield — ADR-002) e
sem inflar o núcleo.

## Decision Drivers
- Capacidade nova (personagem consistente) é `[extensão]` (ADR-004): marcada, separada, com ADR.
- Reuso: explorar/fixar no motor **local grátis** (ADR-033); identidade paga (Soul ID) pela ponte
  **oficial** da Higgsfield (ADR-002); a escolha visual é do usuário (ADR-038).
- Não editar a lógica das etapas: a identidade tem de reancorar os prompts **sem** tocar os
  serviços/routers das etapas 3–5.
- Estado em arquivo (ADR-003), fora de `projects/`, reutilizável entre campanhas (ADR-013).

## Decisão

**Uma biblioteca global de Personagens (`studio/characters/`), análoga à de mood boards
(ADR-013), e a injeção do descritor de identidade nos prompts pela camada do chat.**

1. **Ciclo do personagem.** Criar → **explorar** variações no motor local (grátis, seeds fixas) →
   o usuário **fixa** a que acertou (`ui.choose_images`, ADR-038) → o Studio gera o **descritor
   canônico de identidade** (via `prompter`, papel novo `character`: só os traços que não podem
   mudar) → **character sheet** (vistas ancoradas no descritor, local) → **aplicar** a uma campanha
   (`project.json.character`, campo aditivo).
2. **Injeção sem tocar as etapas.** O personagem aplicado é lido pelo chat, que **prepend** o
   descritor à instrução dos prompts de **base** e **storyboard** (não no mood — a vibe é sem
   pessoas, aula 009). Nenhum serviço/router de etapa muda: a identidade viaja pelo campo
   `instruction`/`prompt` que já existe. É o mesmo espírito da ADR-037 (o chat age pela API).
3. **Duas pontes de identidade, as que já existem.** Local: descritor + refs (Redux/IPAdapter no
   motor local, ADR-033), grátis. Pago: **Soul ID** treinado pela ponte oficial da Higgsfield
   (`soul_id_create/list` em `studio/higgsfield.py`, ADR-002) — plano Basic+, gate de login/plano
   no próprio CLI; a confirmação do usuário é pedida antes (ADR-038).
4. **Nota de identidade opcional e local.** A similaridade facial (`character_score`) é delegada ao
   comando `engine faces` do `local_ai_engine` (fora do venv do Studio, como a ADR-033 faz por
   subprocess). Se o comando não existir, o recurso **degrada** com uma mensagem — não falha, e não
   bloqueia o resto. A implementação do comando (insightface/ArcFace) fica como follow-up no motor.
5. **Fronteira e persistência.** `studio/characters/` + a UI co-localizada; o núcleo tocado é
   `studio/app.py` (include + mount `/cfiles`), `studio/higgsfield.py` (Soul ID) e `frontend/` (área
   + link no shell) — com titularidade declarada (ADR-010). Estado em `STUDIO_CHARACTERS`
   (gitignored), fora de `projects/` (ADR-003). Local é grátis: sem cost/débito (ADR-016 intacto).

## Consequências

**Positivas**
- Personagem consistente vira produto: explorar barato (local), fixar por escolha do usuário,
  reaplicar em qualquer campanha, foto e vídeo.
- Zero mudança na lógica das etapas: a identidade reancora os prompts pela camada do chat.
- Ambas as pontes reusadas; nada de terceira integração.

**Negativas / custos**
- A injeção do descritor vale **pelo chat** (a tela de etapa, usada direto, não injeta) — aceitável
  nesta wave; uma injeção no backend da etapa seria mudança de núcleo de etapa, rejeitada aqui.
- A nota de identidade depende de um comando externo ainda não implementado — entregue como gate
  gracioso, não como funcionalidade garantida.
- Soul ID não é exercitável no CI (paga, exige conta) — testado com fake da ponte; a corrida real é
  validação manual, como toda a ADR-002.
- `[extensão]` da ADR-004: character sheet e consistência não são do curso; ficam marcados e
  separados, sugeridos como melhoria — nunca embutidos no que a aula ensina.
