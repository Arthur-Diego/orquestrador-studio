# PRD: Legendas com karaokê — backend (Wave 8 · frente B)

Task-Id `ADH-OS-20260829-39` · Card <https://trello.com/c/bzh7UKVT> · Domínio `edit` (etapa 7).
Spec normativa completa: `_techspec.md` (o FDD aprovado em lote). Este PRD é o resumo de produto;
**em qualquer divergência, `_techspec.md` vence**.

## Problema

O editor completo da etapa 7 (ADR-030) já tem a faixa `t_cap` de legendas, mas o botão "Gerar"
só mostra um toast: não existe transcrição nem geração de legenda no servidor. O usuário precisa
digitar legenda a legenda e não tem como sincronizar com a fala.

## Objetivo

Entregar a **parte servidor** da legenda automática: um pacote `studio/edit/captions/` que produz
itens prontos para `t_cap` a partir de (a) um roteiro colado (timing proporcional determinístico)
ou (b) um arquivo de áudio/vídeo (timing real por palavra via OpenAI `whisper-1`, ou fake sem
chave), mais a normalização aditiva dos campos `words/mode/hi/chunk` no `PUT /timeline`, o upload
de narração e o burn-in karaokê (um PNG por palavra) no `master.mp4`.

Tudo é `[extensão]` aprovada pelo dono do produto (CLAUDE.md, regras 2 e 4): a aula 014 monta no
CapCut sem legendas.

## Fora de escopo

- Toda a UI (modal "Gerar legendas", spans de karaokê, propriedades) — é a frente C, em paralelo.
- Roteiro por LLM, TTS, tradução, diarização.
- Persistir o resultado do `generate` no servidor (o `PUT /timeline` já salva).
- Registrar custo do whisper no livro-caixa (ADR-016) e job assíncrono de transcrição.

## Usuários e valor

O usuário do Studio (single-user, app local) cola o roteiro ou sobe a narração e recebe legendas
já fatiadas em janelas de uma linha, com tempo por palavra, prontas para inserir na timeline e
queimar no master.

## Requisitos funcionais (contrato HTTP CONGELADO — não negociável)

Prefixo `/api/projects/{pid}/edit`:

1. `POST /captions/generate` — `{source:"script"|"audio", text?, file?, start, duration?, mode,
   chunk, hi, position, style}` → `200 {source:"estimate"|"whisper", word_count, total_s,
   warning?, items:[...]}`. Cada item já no shape de `editor.tracks[t_cap].items[]`, com
   `words[].start_s/end_s` em segundos ABSOLUTOS da timeline. O servidor **não persiste**.
   Erros: `422` com `detail` string **iniciada pelo nome do campo** (`"text: obrigatório em
   script"`, `"file: …"`, `"hi: …"`, `"mode: …"`); `404` arquivo inexistente; `409` sem ffmpeg;
   `502` `ProviderError` do whisper (nunca cai em `estimate` silencioso quando `source=audio`
   sem `text`).
2. `POST /captions/narration/upload` — multipart `files[]` → `{added, files:[{file, duration}]}`,
   grava em `edit/narration/`. `GET /captions/narration` → `[{file, name, duration}]`.
3. `PUT /timeline` (existente) — item de `caption` aceita `mode`, `hi`, `chunk`, `words`; itens
   sem esses campos continuam **byte-idênticos** (retrocompat). `words` inválidas são descartadas
   (nunca 422); `mode` inválido vira `bloco`.
4. `POST /render` (existente) — legenda `karaoke` gera um PNG por palavra, `linha` um por item,
   `bloco` como hoje.

Constantes compartilhadas com o front (frente C espelha em `view.js`; não divergir):
`WPS = 2.4`; regra do **centro** da palavra (`a <= (start_s+end_s)/2 < b`);
`CAPTION_MODES = ("karaoke","linha","bloco")`; `HI_COLORS = ["#C8F751","#57E2F0","#F2B544","#A78BFA"]`;
`CHUNK_OPTS = [0, 6, 4, 2]`.

## Regras de negócio inegociáveis

- **Nosso texto, tempo ouvido.** Com `source=audio` e `text`, o texto exibido é sempre o colado
  pelo usuário; a transcrição só fornece o tempo. Invariante: `[w.w for w in words] == text.split()`.
- **Política assimétrica de falha.** `words()` (temos o texto) cai em `proportional` com `warning`;
  `transcribe_text()` (não temos texto) levanta `ProviderError` → 502.
- **Determinismo sem rede.** Sem `OPENAI_API_KEY`, tudo responde `source:"estimate"`. A suíte roda
  sem `openai` importado (ADR-008): nenhum teste faz rede, jamais.
- **Retrocompat total.** `PUT /timeline` sem os campos novos = saída byte-idêntica; render sem
  `words` = mesmos PNGs e mesmo filtergraph de hoje. O backbone da aula (clipes, pretos, música,
  SFX, fade, loudnorm) não muda.

## Restrições

- Python 3.12 / FastAPI, sem banco (ADR-003: estado em arquivo).
- `openai>=1.40` entra **só** em `requirements.txt`, com import lazy dentro dos métodos.
- **Não há `OPENAI_API_KEY` neste ambiente**: implementar `OpenAITranscribe` conforme a spec e
  validar apenas com `FakeTranscribe`/`proportional` e testes com SDK falso em `sys.modules`.
- Arquivos que esta frente PODE tocar: `studio/edit/captions/**` (novo), `studio/etapas/edit/router.py`
  (rotas aditivas), `studio/edit/burnin.py`, `studio/edit/render.py` (aditivo, spec `kind:"concat"`),
  `studio/edit/editor.py` (**só** o helper novo `normalize_caption_extra` + uma linha de chamada no
  ramo `caption` de `normalize_item` — mudança mínima e contígua, a frente A edita o mesmo ramo em
  paralelo), `requirements.txt`, `docs/adrs/generated/STUDIO/ADR-024-*.md`, `docs/adrs/mapping.md`,
  `docs/adrs/README.md`, `docs/domains/edit/postman/`, `docs/domains/edit/features/editor-video-completo-fdd.md`
  (nota), e testes (`tests/test_edit_captions.py` novo; funções novas com prefixo `test_captions_`
  em `tests/test_edit_api.py`, `tests/test_edit_editor.py`, `tests/test_edit_service.py`).
- **NÃO tocar**: `studio/etapas/edit/view.js`, `view.html`, `studio/steps.py`, `studio/settings.py`,
  `studio/web/ui.*`, `studio/app.py`.

## Critérios de sucesso

Os 17 critérios funcionais da seção 9 do `_techspec.md`, verificados por `make verify`
(ruff + pytest) verde, sem rede e sem navegador, mais a coleção Postman do domínio `edit`
com a pasta "captions [extensão]".
