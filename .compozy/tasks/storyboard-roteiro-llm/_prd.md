# PRD: Roteiro por LLM na etapa 4 (Wave 9 · sub-wave 2 · CONSUMIDORA)

Card da wave <https://trello.com/c/T53Hnvlv> · Domínio `storyboard` (etapa 4, aula 010)
Base: `develop@29a10a3` (a provedora `prompter-presets-realismo` JÁ está integrada).

Spec normativa completa: `_techspec.md` (o FDD v1.1, aprovado no gate em lote W3).
**Em qualquer divergência, `_techspec.md` vence** — em especial a **seção 0 (amendas)**, que
sobrepõe o corpo original do documento e traz o contrato real da provedora lido do código.

## Problema

A aula 010 manda o aluno escrever a história em ~5 cenas à mão, e o Studio hoje só oferece
caixas de texto vazias com um "momento do arco" sugerido (`SCENE_ARC`). O levantamento do
curso (Wave 9) identificou a lacuna: quem trava na escrita fica parado na etapa 4, mesmo já
tendo imagem base, mood aplicado e produto/vibe definidos — todo o insumo de que um roteiro
precisa. Além disso, quando o usuário escreve as cenas, ele ainda precisa inventar do zero o
prompt de imagem de cada uma, sem o rigor do "briefing de diretor de fotografia".

## Objetivo

Oferecer, como `[extensão]` **opt-in**, a geração de um roteiro completo pelo Claude CLI
(mesmo canal grátis do prompt de vídeo), aplicando o preset de realismo da feature irmã:

1. Papel `script` em `prompter.ROLES` + `prompter.script(...)` (aditivos) — N cenas com
   `text` pt-BR e `image_prompt` em inglês no formato briefing de DP, com o rig do preset.
2. Job assíncrono `POST .../storyboard/script/generate` + `GET .../storyboard/script/job`
   (padrão ADR-006: thread + `JobRegistry` próprio + polling), **sem `confirmCost`**
   (Claude CLI é assinatura local, zero crédito Higgsfield).
3. `GET .../storyboard/script` com a última sugestão persistida em `storyboard/script.json`
   (200 `{"script": null}` quando nunca houve geração) + campos aditivos no status da etapa.
4. Bloco `[extensão]` no painel de cenas: preset de realismo, nº de cenas, aspect ratio
   (leitura), progresso do job, sugestão por cena e aplicação **opt-in** às cenas.

## Restrição de fidelidade ao curso (CLAUDE.md, gates IRREVOGÁVEIS)

Esta feature CONTRARIA um texto explícito do repositório — a docstring de
`studio/storyboard/service.py:12` diz "nada de roteiro por LLM". Por isso:

- a feature inteira é `[extensão]` (ADR-004), marcada no código e na UI;
- exige **ADR-025**, aprovada no gate W3 e criada no fechamento da frente (amenda A7);
- o método da aula continua sendo o caminho PADRÃO: o texto gerado é **sugestão editável**.

> **Invariante suprema desta feature:** nenhum caminho de código do SERVIDOR escreve em
> `storyboard/scenes.json`. A sugestão vive em arquivo próprio (`script.json`) e só chega
> às cenas pelo `PUT /api/projects/{pid}/storyboard/scenes` que já existe, disparado pelo
> usuário — preenchendo cenas vazias sem confirmação e substituindo texto preenchido
> **apenas** após confirmação explícita que diz quantos textos serão sobrescritos.

## Segunda invariante: nada de estrutura nova em `scenes.json`

O schema da cena é o do ADR-018/022 (`{id,n,text,images,primary,videos,photos}`). O
`image_prompt` por cena vive **só** em `script.json` e é copiado pelo usuário. Nenhuma task
pode acrescentar campo em `scenes.json` nem tocar `save_scenes`/`_normalize`.

## Usuários e cenário

Usuário único, local (ADR-001), já na etapa 4 com `base/base_final.png` presente. Claude CLI
é dependência **opcional**: sem ele no PATH, `script/generate` responde 409 com mensagem que
aponta o modo manual da aula — **não existe fallback determinístico** para roteiro (decisão
da seção 6 do `_techspec.md`; um template geraria N cenas iguais, ou seja, inventaria).

## Escopo

- `prompter`: papel `script`, função `script(...)`, output spec e parser próprios
  (`_parse`/`PROMPT_FORMAT`/`split_sections`/`provenance` **intocados**).
- Serviço da etapa 4: `_script_registry`, `script_generate`, `script_status`, `load_script`,
  persistência atômica de `storyboard/script.json`, campos aditivos no `status`, registro da
  ação `storyboard.script` em `settings.PRESET_ACTIONS` (amenda A2).
- Rotas aditivas no router da etapa 4 (nenhuma rota existente muda).
- UI da etapa 4: bloco `[extensão]` reusando `realismPresetField`/`realismPresetOf` que a
  provedora já deixou no `view.js` (amenda A5), com o prefixo `realism` obrigatório nos ids
  (amenda A4 — no storyboard, "preset" já é fórmula da aula).
- Testes com fake do Claude CLI (monkeypatch de `prompter.BIN`/`subprocess.run`, padrão de
  `tests/test_prompter.py`, ADR-008: sem rede, sem navegador).

## Fora de escopo

- Gerar imagem ou vídeo a partir dos prompts (o usuário usa os fluxos que já existem).
- Endpoint novo de escrita em `scenes.json`; mudança de schema; regeneração por cena
  individual; versionamento do `script.json` anterior; tradução de cenas já escritas.
- Definir ou editar presets de realismo (é da provedora) e qualquer edição em
  `studio/common/settings.py`, `app.py`, `steps.py` ou `studio/web/*` (ADR-010).
- `gpt_image_2` como alvo do roteiro (gate W3 P3 — v1 só `nano_banana_2`).

## Sucesso

- Os 12 critérios da seção 9 do `_techspec.md` verdes, com destaque para o critério 3
  `[cross-feature]` (amenda A9), que precisa de teste automatizado provando que o rig do
  preset escolhido aparece **literalmente** no `image_prompt` de **cada** cena gerada.
- `make verify` (ruff + pytest, sem rede) verde; baseline desta worktree = 1092 testes.
- Nenhuma chamada a `hf.*` e nenhum `record_generation` em todo o fluxo (zero crédito).
