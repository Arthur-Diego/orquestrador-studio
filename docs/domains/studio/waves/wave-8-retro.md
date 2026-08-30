# Wave 8 — Retro (Studio de vídeo: editor estável + legendas com karaokê)

**Fechada em:** 2026-08-30 · **Recon:** `../recon-wave-8.md` · **Contratos:** `wave-8.md` · **Card:** <https://trello.com/c/6Eg28v10>
· **Modo:** dd-parallel com delegação total do dono (gate em lote e merges pelo orquestrador).

## Resultado

| Frente | PR | Caminho | Testes | Entrega |
|---|---|---|---|---|
| docs · specs da wave | **#83** | — | CI | recon, `wave-8.md` (contrato congelado), grafo Mermaid, 3 FDDs em batch, listas `DD ·` no Trello |
| B · legendas-backend | **#84** | SDD (5 tasks, 5/5) | 965 passed | `studio/edit/captions/` (proportional/align/whisper-1 lazy/fake), `POST /captions/generate`, narração (`edit/narration/`), `normalize_caption_extra`, burn-in karaokê (PNG por palavra, fallback ffconcat > 200 inputs), **ADR-024**, +9 requests Postman |
| A · editor-estavel | **#85** | SDD (6 tasks, 6/6) | 973 passed · smoke Playwright 21/21 | render incremental (`commit`→`renderDirty`, 0 `renderRoot` em edição), timeline 345 px com `ui.tlHeight/leftW/rightW`, exclusão total (música, último clipe, SFX por referência), MP4 na VÍDEO 2 (`overlayPool`), `moveToTrack` V1↔V2, efeitos em qualquer camada (`EFFECT_APPLIES`, `LAYER_HOOKS`), sidebar ocultável, etapa 7 = "Studio de vídeo" |
| C · legendas-frontend | **#86** | direta | 976 passed · smoke Playwright 32/32 | modal "Gerar legendas" (roteiro/áudio, preset, chunk, cor, posição), karaokê no preview (`paintKaraoke` só troca cor), bloco Legenda nas propriedades, `words` deslocadas ao mover |
| integração da wave | **#87** (este) | direta | verify 976 passed + QA `edit` 56/56 (1024×768, light/dark) | `C-EDIT-18/42/43` reescritos para o comportamento novo (modal; último clipe e ripple podem esvaziar a montagem), `duplicateSelection` persistindo em `etrack.items`, 2 asserções Postman defasadas (etapa 5 / n=7), header do editor quebra linha e a altura aplicada da timeline respeita o espaço da viewport (`fitTimeline`, preferência persistida intacta) em 1024×768, auditoria do QA ignora conteúdo de containers roláveis na horizontal, retro |

Ordem real de integração: docs → **B → A → C** (A ∥ B sem dependência; B ficou pronta antes, A rebaseou sobre B: único
contato foi o ramo `caption` de `editor.py`, resolvido como "os dois blocos ficam", exatamente como o FDD de A previu).

## Critérios cross-feature (W2) — evidência no estado integrado

- **C ← A** (spans dentro da camada reconciliada, `paintKaraoke` sobrevive a mover/trim sem `renderRoot`): smoke de C mostra
  `#edStage/#edTimeline/#edProps/#edPanel` como os mesmos nós antes e depois de gerar/mover; cor do span muda no Play.
- **C ← B** (itens do modal sobrevivem a `PUT /timeline` + reload): smoke de C (F5 → `words/mode/hi` no GET) e testes
  `test_captions_*` de B.
- **B → render** (N PNGs = N palavras, N `overlay … enable=between`): teste de burn-in de B + render real de 6 s medido.
  Reexecutado na integração pela suíte completa (`make verify`) deste PR.

## Auto-aceites revisados (auditoria do lote)

- A: pool de overlay por `item.id`; `clip_fx` não migra no `moveToTrack`; multi-seleção segue o primeiro alvo; só os 14
  efeitos de `EFFECTS` (Flash/Spin são transições); chaves `ui.*` ausentes em vez de default gravado.
- B: geração síncrona (job fica para quando passar de 30 s); chave em runtime; gravador próprio de narração (o `ingest`
  só grava em `candidates/`); janela da palavra vai até a próxima; 5 tasks em vez de 10 linhas do build order.
- C: um toast só (o shell tem uma linha); `--vtx4` no lugar do inexistente `--vmut`; `paintKaraoke` só no fim de
  `renderPreview` (loopTick/seekTo passam por lá).

## Incidentes e regras novas

- **Frente que termina o turno "aguardando monitor" é stall** (regra da Wave 16 confirmada): B parou assim com o run SDD
  ainda em voo; retomada por mensagem exigindo espera síncrona em `result.json`. → Já está em `ambiente.md`; o prompt de
  disparo passa a dizer explicitamente "espere o run com `until` bloqueante".
- **PR rebaseado sobre spec removida**: B commitou o FDD na branch (contra a regra) e o removeu depois; o rebase sobre o
  #83 gerou conflito add/add + modify/delete no mesmo arquivo. → Regra: frente nunca commita `docs/domains/**/features`,
  `recon-*` ou `waves/*`; se o runner SDD fizer isso, reverter no mesmo commit, não num commit posterior.
- **Docs mergeadas antes das frentes** evitou que três PRs carregassem as mesmas specs. → Regra: o orquestrador abre o PR
  de specs logo após o gate em lote e o integra antes do primeiro PR de frente.
- **Revisão independente dentro da frente achou 6 defeitos reais em A** (overlay maior que o palco, scroll desfeito a cada
  edição…) e o smoke de C achou 1 (trocar para `bloco` não removia os spans). → Manter a rodada de revisão + smoke real
  como parte do fechamento da frente, não da integração.
- **Cenário de QA que afirma comportamento antigo é dívida da wave, não do QA**: `C-EDIT-42/43` (barrar exclusão do
  último clipe) e `C-EDIT-18` (toast do `#capGen`) quebraram porque a wave mudou a spec de propósito. → Regra: a frente
  que muda comportamento coberto por `scripts/qa/cenarios/*` lista os cenários afetados no final report; a integração
  os reescreve no mesmo PR (não a frente, porque `scripts/qa` é artefato compartilhado).
- **Timeline mais alta em viewport baixo** (1024×768) fez o player vazar sob a timeline: a altura preferida (345 px) passa a ser limitada
  pelo espaço disponível em `fit()` (`fitTimeline`), sem alterar a preferência gravada. → Regra: mudança de altura fixa em layout flex exige checar o QA na viewport mínima.
- **Lixo de ferramenta em doc** (`</content>`/`</invoke>` no fim do FDD do editor, vindo do runner SDD de B) → C limpou;
  regra: `git diff` do PR não pode conter tags de tool.

## Limites e pendências que seguem

- **Whisper real nunca exercitado** (sem `OPENAI_API_KEY` no ambiente): `OpenAITranscribe` coberto só por SDK falso.
  Primeira chamada real pode revelar desvio de formato; o fallback `estimate` mantém a UI funcional.
- Custo do whisper fora do livro-caixa (ADR-016) e transcrição assíncrona (ADR-006) — declarados na ADR-024.
- Critérios 14/15 de A (MP4 real na V2 tocando com desvio ≤ 0,3 s; mover pelos três caminhos) exigem `.mp4` real na
  campanha (mídia é gitignored): revisados por leitura, não por execução.
- Slider de intensidade de efeito empilha o estado já alterado no primeiro Ctrl+Z (padrão pré-existente de `propsSpeed`).
- 422 do Pydantic (enum de `mode`/`hi`/`chunk`) vem como lista, o do serviço como string; a UI trata os dois.
- Docs do `edit` ainda dizem "Etapa 8" em `prd.md`/`edit-fdd.md`/`edit-fluxo.md` (pré ADR-015); `docs/adrs/README.md`
  indexa ADR-024/030 mas ADR-016..023 continuam fora.
- Promoção `develop → main` (release) — decisão do dono.
