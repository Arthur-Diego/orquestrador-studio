# ADR-042: campos abertos de prompt por foto no storyboard e papel `keyframe` do prompter

**Status:** proposta
**Data:** 2026-09-06
**Task-Id:** ADH-OS-20260906-08
**ADRs relacionados:** [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-018](../STUDIO/ADR-018-varias-imagens-por-cena-galeria-de-keyframes-com-principal.md), [ADR-022](../STUDIO/ADR-022-video-por-foto-no-storyboard-modelo-selecionavel-e-ponte-para-o-downstream.md), [ADR-025](../STUDIO/ADR-025-roteiro-de-storyboard-gerado-por-llm-como-extensao-opt-in-da-etapa-4.md), [ADR-028](../STUDIO/ADR-028-roteiro-por-cena-fotos-inferidas-e-roteiro-antes-da-historia.md), [ADR-035](ADR-035-remocao-do-combo-de-formulas-da-aula-do-storyboard.md), [ADR-037](../STUDIO/ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md), [ADR-038](../STUDIO/ADR-038-protocolo-humano-no-laco-do-chat.md)

Proposta em `docs/domains/storyboard/features/storyboard-cenas-fdd.md` §12 (pendência 1), da Wave
11 · frente F06 `[extensão]`. As três decisões abaixo estão implementadas nesta frente; a ADR fica
como **proposta** até o dono aprovar — é o mesmo estado que o código já cita
(`studio/storyboard/service.py`, "ADR-042 proposta").

## Contexto e Problema

A cena do storyboard já guarda, por foto, a descrição e o prompt de vídeo (ADR-022). O prompt
de IMAGEM só existe em `script.json` (ADR-025/028) e é copiado à mão. O preset de realismo
escolhido por foto nunca é persistido e o cliente anula o default da ação ao mandar `null`.

A mudança em `scenes.json` é aditiva, e ADR-018/022/025 já autorizam acréscimos. Ainda assim a
frente propõe uma ADR, porque três decisões novas passam a valer para além dela:

1. a foto do storyboard passa a carregar **conteúdo autoral do usuário** (prompt de imagem), e não
   só metadado de vídeo;
2. o preset por foto vira contrato persistido de **três estados**;
3. as tools MCP podem aplicar o roteiro às cenas depois de `ui_confirm`, o que precisa ficar
   explicitamente compatível com a ADR-025 ("o servidor nunca escreve").

## Decisão

1. `scenes.json` ganha, por foto e de forma ADITIVA: `image_prompt`, `preset` com três estados
   (chave ausente herda, `null` desliga, id usa) e `origin` com a fonte (`ia`/`manual`/
   `template`), o preset usado e o horário, por campo.
2. O prompter ganha o papel `[extensão]` `keyframe` e a função `keyframe()`, que reusa a ordem
   de briefing e o bloco de rig do roteiro para UMA foto, exposto por
   `POST /api/projects/{pid}/storyboard/image-prompt`. Sem o Claude CLI, o endpoint cai em
   template determinístico (o 409 da ADR-025 continua valendo só para o ROTEIRO).
3. O servidor continua **nunca** escrevendo `scenes.json` a partir do roteiro. As tools MCP
   podem aplicar o roteiro e anexar fotos, sempre depois de `ui_confirm`/`ui_choose_images`
   (ADR-038) ou de `confirm=true` explícito no terminal.
4. Desanexar uma foto de todas as cenas não a desmarca nem a remove de `storyboard/ideas/`.

## Consequências

Positivas: o prompt de imagem passa a ser editável e reaproveitável pela geração local e pela
por cena (F07); o default visual da campanha finalmente chega às gerações. Negativas: o schema
por foto cresce e passa a exigir poda e validação próprias; a distinção "chave ausente ≠ null"
precisa ser preservada em quatro camadas (UI, corpo HTTP, serviço, arquivo).
