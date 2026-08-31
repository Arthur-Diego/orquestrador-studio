# ADR-028: Roteiro do storyboard lê as fotos escolhidas da galeria do painel 01

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260831-14
**ADRs relacionados:** [ADR-025](./ADR-025-roteiro-de-storyboard-gerado-por-llm-como-extensao-opt-in-da-etapa-4.md), [ADR-027](./ADR-027-multishot-do-painel-01-gera-pontos-de-vista-reais.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-018](./ADR-018-varias-imagens-por-cena-galeria-de-keyframes-com-principal.md)

## Contexto e Problema

O roteiro por LLM (`[extensão]` ADR-025) propõe N cenas para a campanha a partir de um **contexto
visual** que o serviço monta e o Claude lê com a ferramenta `Read`. Até aqui esse contexto era
**a imagem base da etapa 3 + até 3 frames do mood aplicado** (`_script_images`).

O fluxo do painel 01 do storyboard, porém, é: o **multishot da base** (ADR-027) gera pontos de vista
reais → o usuário **importa** esses resultados para a **galeria de ideias** → **escolhe** as fotos que
vão virar cena (`select_ideas`, copiadas para `storyboard/ideas/`). Essas fotos escolhidas são a
melhor pista visual disponível de *como a história já está sendo imaginada em quadros* — e o roteiro
as **ignorava por completo**. O Card `xhtT5B24` pede exatamente essa costura: *multishot da base →
galeria → criar roteiro a partir dessas fotos*. O motor do roteiro (ADR-025) e o multishot (ADR-027)
já existiam; faltava **ligar a galeria ao roteiro**.

## Decisão

Incluir as **ideias escolhidas na galeria** (`storyboard/ideas/`) no contexto visual do roteiro,
**depois da base** e **antes do mood**, sem reescrever o motor:

1. **Serviço (`_script_images`):** a ordem de prioridade passa a ser `base → ideias escolhidas (até
   `SCRIPT_IDEA_IMAGES` = 3) → frames do mood (até `SCRIPT_MOOD_IMAGES` = 3)`, tudo cortado no teto
   `prompter.MAX_IMAGES` (4). O helper novo `_selected_idea_paths` lê `candidates.json`, filtra as
   selecionadas e reaproveita `_visible` para **excluir marcações** (`role:"annotation"`, inpaint) —
   o mesmo invariante da galeria pública (`list_ideas`, FDD §6). A base é sempre a 1ª, então nunca é
   empurrada para fora; ideias e mood disputam as vagas restantes nessa ordem.

2. **Prompter (`script`):** a frase que apresenta as imagens ao Claude deixa de citar só "base + mood"
   e passa a descrever a nova ordem — *"the base image comes first, then any chosen storyboard shots,
   then mood frames"* — mantendo o pedido de fidelidade a produto/paleta/luz. Nenhuma mudança de
   assinatura: `script` continua recebendo uma lista genérica de caminhos.

3. **UI (painel "Roteiro por Claude"):** um campo de LEITURA novo (`#sbScriptIdeas`) mostra quantas
   fotos escolhidas da galeria entram no contexto ("nenhuma — escolha na galeria" quando zero). É a
   *costura visível* pedida no card: o usuário vê que gerar o roteiro **a partir das fotos** depende
   de tê-las escolhido no painel 01. O valor vem do `selected` do `status` (nenhuma rota nova).

## Restrições respeitadas

- **Opt-in e não destrutivo (ADR-025):** o roteiro continua sendo sugestão editável; nada é escrito
  em `scenes.json` sem o clique do usuário. Sem ideias escolhidas o comportamento é **idêntico ao de
  antes** (base + mood) — quem não usa a galeria não sente diferença.
- **Fidelidade da aula (ADR-004):** o `#sbPreset` (fórmulas da aula) e o caminho manual do painel 02
  seguem intocados. A costura só enriquece o contexto do `[extensão]` roteiro.
- **Núcleo intocado (ADR-010):** mudanças só no serviço da etapa, no prompter comum e no plugin
  (`view.html`/`view.js`); nada em `app.py`/`index.html`/`app.js`/`steps.py`.
- **Marcação nunca vira ideia (inpaint, FDD §6):** `_selected_idea_paths` usa `_visible`, então
  anotações jamais entram no contexto do roteiro.

## Consequências

- O roteiro passa a ser fiel também às fotos que o usuário já escolheu como quadros — fecha o fluxo
  *multishot → galeria → roteiro* do Card `xhtT5B24`.
- **Contrato de contexto observável:** a lista de imagens enviada ao `prompter.script` passa a
  conter, quando houver, os caminhos sob `storyboard/ideas/` entre a base e o mood. Coberto por
  `test_script_context_includes_selected_gallery_ideas_after_base_before_mood`,
  `test_script_caps_gallery_ideas_and_never_drops_the_base` e
  `test_script_context_ignores_unselected_ideas_and_annotations`.
- Teto de imagens inalterado (`MAX_IMAGES` = 4): com muitas ideias, o mood cede a vez (as ideias têm
  prioridade), mas a base nunca sai.
