# PRD: Presets de realismo no prompter (Wave 9 · sub-wave 1 · PROVEDORA)

Task-Id `ADH-OS-20260830-01` · Card <https://trello.com/c/T53Hnvlv> · Domínio `studio`
(serviço transversal `studio/common/prompter.py` + `studio/common/settings.py` + telas
mood/base/storyboard).

Spec normativa completa: `_techspec.md` (o FDD v1.1, aprovado no gate em lote W3).
**Em qualquer divergência, `_techspec.md` vence** — em especial a seção 0 (amendas do gate),
que sobrepõe o corpo original do documento.

## Problema

Hoje o realismo dos prompts do Studio depende do texto livre dos papéis `ROLES` e do que o
Claude decide na hora. Não existe forma de fixar um "look" coerente e repetível (rig de
câmera + lente + formato + abertura, luz dominante, color grade, vocabulário de fidelidade,
negativos anti-IA) nem de configurá-lo por projeto. Esse conhecimento existe validado numa
skill externa (`~/.claude/skills/generate_realistic_prompt_images/`) que **não pode ser
dependência de runtime** do repositório.

## Objetivo

Transcrever esse conhecimento para dentro do código como um **catálogo de presets de
realismo** e ligá-lo ao prompter de forma **estritamente aditiva e opt-in**:

1. `REALISM_PRESETS` em `studio/common/prompter.py` — 5 rigs com rig/luz/grade/fidelidade/negativos.
2. Parâmetro opcional `preset` em `from_brief`/`from_images`/`fallback_template`.
3. Resolução de preset default **por ação** em `studio/common/settings.py`, no padrão ADR-016
   (projeto → global → código), sobre um registro extensível de ações.
4. `GET /api/prompter/presets` + rotas de configuração, em `studio/creditos/router.py`.
5. Campo `preset` aditivo nos 3 endpoints de geração de prompt que já existem, com seletor
   `[extensão]` nas telas das etapas 2, 3 e 4.

## Restrição de fidelidade ao curso (CLAUDE.md, gates IRREVOGÁVEIS)

Nenhuma aula do curso ensina presets de realismo: **toda a feature é `[extensão]`** (ADR-004),
marcada como tal no código e na UI. Por isso o gate W3 fixou o comportamento **opt-in**:

> **Com o body atual (sem o campo `preset`) e sem override configurado, o texto enviado ao
> Claude CLI e a resposta devolvida são byte-idênticos aos de `develop@7162c41`.**

Este é o requisito de maior prioridade do trabalho. Qualquer task que quebre essa invariante
está errada, ainda que passe nos próprios testes.

## Papel na wave: PROVEDORA (contrato congelado)

A feature `storyboard-roteiro-llm` (sub-wave 2) consome, e **só** consome, o que está na
seção 5 do `_techspec.md`:

- o dict `REALISM_PRESETS` e a função `prompter.preset_block(preset_id)`;
- o endpoint `GET /api/prompter/presets` (shape de `presets[]` e de `defaults{}`);
- a resolução `settings.preset_default_for(kind, pid)` para **qualquer chave registrada**,
  incluindo a chave pontuada oficial `storyboard.script` — que a **consumidora** registra em
  `settings.PRESET_ACTIONS` com default `documentary-street`.

Nada disso pode ser renomeado, e o registro de ações precisa ser extensível por quem chega
depois, sem editar o código desta frente. Ver amendas A1/A2 da seção 0 do `_techspec.md`.

## Fora de escopo

- Papel `script` do prompter e endpoints de roteiro (feature da sub-wave 2).
- Qualquer edição em `studio/app.py`, `studio/steps.py`, `studio/web/*` (ADR-010).
- Alterar `ROLES`, `PROMPT_FORMAT`, `STYLE_VARIANTS`, `MOOD_GUARDS`, `enforce_mood_rules`,
  `split_sections`, `provenance`.
- Edição de preset default na tela "Créditos & Custos" (P2 do gate: fica para frente de shell).
- Ajuste automático de aspect ratio por preset; perfis por modelo alvo (Midjourney/Flux/GPT-Image).
- ADR nova: o gate (P3) dispensou — a marca `[extensão]` basta.

## Usuários e valor

Usuário único do Studio (app local). Nas telas das etapas 2 (mood), 3 (base) e 4
(vídeo/motion) ele passa a poder escolher um "look" fechado e coerente antes de gerar o
prompt, com opção "(sem preset)" sempre disponível, e pode fixar o preset preferido por
projeto ou global via API.

## Requisitos não-funcionais

- Sem chamada externa nova: preset só muda o texto do prompt já enviado ao Claude CLI.
- `GET /api/prompter/presets` lê dict em memória (< 50 ms).
- Testes sem rede e sem navegador (fakes de `BIN`/`subprocess.run`, padrão do repo).
- Escrita de config por `common.atomic.write_json_atomic`.
- `config.json` existentes (global e de projeto) seguem válidos sem migração.
- `make verify` (ruff + pytest) verde ao final.

## Critérios de aceite

Os 12 critérios numerados da **seção 9 do `_techspec.md`** (com o critério 5 já na redação
opt-in do gate W3). Cada task recebe o subconjunto que fecha.
