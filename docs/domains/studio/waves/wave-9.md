# Wave 9 — Lacunas do levantamento do curso (studio/storyboard/base/refs)

Data: 2026-08-30 · Base: `develop` @ `7162c41` · Card da wave: https://trello.com/c/T53Hnvlv

Objetivo: fechar as lacunas identificadas na comparação levantamento-do-curso × código,
**sem mudar a estrutura existente** (restrição do dono: só adicionar; ajustar apenas o
necessário para coerência com o passo a passo do curso).

## Contratos entre features

### Feature: prompter-presets-realismo
**Provides**:
- Catálogo de presets de realismo em `studio/common/prompter.py` (novo dict `REALISM_PRESETS`),
  contendo ao menos `documentary-street` (default) e `arri-natural-narrative`, cada um com
  rig (câmera+lente+abertura+formato), luz, grade e vocabulário de fidelidade — estrutura
  derivada da skill `/generate_realistic_prompt_images` (rig presets, aberturas, negativos).
- Ação de configuração por padrão ADR-016 em `studio/common/settings.py` (preset default por
  ação, override projeto → global → código).
- Endpoint `GET /api/prompter/presets` (lista id, nome, descrição de uma linha, rig) para a
  UI montar seletores.
- Parâmetro opcional `preset` aceito por `prompter.from_brief`/`from_images` (aditivo,
  default preserva comportamento atual).
**Consumes**: — (nenhum; candidata imediata)

### Feature: base-clean-marca
**Provides**:
- Novo `kind="clean"` na etapa 3 (`studio/base/service.py` KINDS) — remoção de marca/logo/
  texto por prompt no `nano_banana_2`, com contagem default própria e ação de custo dedicada.
- Endpoints da etapa base estendidos de forma aditiva (mesmo padrão do `kind="label"`).
**Consumes**: — (candidata imediata)

### Feature: inpaint-marcacao
**Provides**:
- Componente de canvas de marcação na SPA (novo `studio/web/annotate.js`, modal reutilizável
  no padrão de `web/multishot.js`): rabisco sobre a imagem → PNG anotado salvo no projeto.
- Modo de edição "área marcada" no storyboard: imagem anotada entra como `image_reference`
  extra no `nano_banana_2` com instrução fixa de editar somente a região marcada
  (aproximação de inpaint; **não** usa máscara — CLI não suporta; ADR-002 preservado).
**Consumes**: — (candidata imediata)

### Feature: refs-import-url
**Provides**:
- Import de pin/board do Pinterest por URL na etapa 1: novo endpoint
  `POST /api/projects/{pid}/refs/import/url` (aceita URL de pin ou de board), reusando o
  Playwright existente (`studio/refs/pinterest.py`) e o dedupe por SHA-1.
**Consumes**: — (candidata imediata)

### Feature: storyboard-roteiro-llm
**Provides**:
- Novo papel `script` no prompter: gera roteiro completo de vídeo publicitário (cenas com
  título, descrição, objetivo narrativo e prompt de imagem por cena) a partir das imagens
  base + mood + produto, seguindo o formato "briefing de diretor de fotografia" da skill
  `/generate_realistic_prompt_images`.
- Endpoints aditivos na etapa 4: `POST .../storyboard/script/generate` (job assíncrono via
  claude CLI) e `GET .../storyboard/script`, pré-preenchendo `storyboard/scenes.json` como
  **sugestão editável** (nunca sobrescreve cenas já editadas sem confirmação na UI).
- Controles na tela da etapa 4 para os parâmetros da skill: preset de realismo/rig, modelo
  alvo, aspect ratio (herdado do projeto), nº de cenas.
**Consumes**:
- Catálogo `REALISM_PRESETS` + `GET /api/prompter/presets` ← provido por
  **prompter-presets-realismo**.
- [cross-feature] Critério de aceitação: o seletor de preset da tela do roteiro lista os
  presets reais do endpoint e o preset escolhido aparece aplicado no prompt de cada cena
  gerada (teste de handoff na W5, estado integrado).

## Grafo e sub-waves

- Sub-wave 1 (paralelas, sem dependências): `prompter-presets-realismo`,
  `base-clean-marca`, `inpaint-marcacao`, `refs-import-url`.
- Sub-wave 2: `storyboard-roteiro-llm` (depende de prompter-presets-realismo; também evita
  conflito de arquivo em `storyboard/` com inpaint-marcacao).

| Feature | Provides (resumo) | Consumes | Sub-wave |
|---|---|---|---|
| prompter-presets-realismo | REALISM_PRESETS + GET /api/prompter/presets + param `preset` | — | 1 |
| base-clean-marca | kind="clean" na etapa 3 | — | 1 |
| inpaint-marcacao | canvas annotate.js + edição "área marcada" | — | 1 |
| refs-import-url | POST refs/import/url (pin/board) | — | 1 |
| storyboard-roteiro-llm | papel `script` + endpoints script/* + UI de parâmetros | presets ← prompter-presets-realismo | 2 |

Ordem de integração (W5): provedoras antes de consumidoras; dentro da sub-wave 1, ordem
livre — sugerida: prompter-presets → base-clean → refs-import-url → inpaint-marcacao →
(sub-wave 2) storyboard-roteiro-llm.

## Gate W3 — aprovação em lote (2026-08-30)

Specs aprovadas em lote por delegação explícita do dono nesta wave ("tome todas as decisões
recomendadas sem me consultar"). FDDs: prompter-presets-realismo (studio), base-clean-marca
(base), inpaint-marcacao e storyboard-roteiro-llm (storyboard), refs-import-url (refs).

Resolução das pendências que subiram ao gate:

1. **prompter-presets P1 (default ativo × opt-in)**: default de código `null` (opt-in) para
   mood/base/motion — fidelidade à aula (ADR-004) preservada byte a byte. O "deixar por
   padrão" do levantamento do dono (passo 5.1) vale para o roteiro: a ação
   `storyboard.script` nasce com preset default `documentary-street`.
2. **prompter-presets P2**: nesta wave, configuração de preset default só via API; edição na
   tela "Créditos & Custos" tocaria núcleo `web/*` (ADR-010) e fica para frente de shell futura.
3. **prompter-presets P3**: com opt-in em mood/base/motion, marca `[extensão]` basta; o
   default ativo de `storyboard.script` é registrado na ADR-025 (da feature de roteiro).
4. **base-clean (fonte do passo 4.3)**: confirmada — levantamento do dono nesta sessão
   ("4.3 retirar marca (caso exista)… pedir para retirar ou modificar"). Aprovado `[extensão]`.
5. **inpaint P1**: `record_generation` apenas no modo novo `edit_area`; estender aos kinds
   antigos muda comportamento observável — candidato futuro, fora desta wave.
6. **inpaint P2/P3**: divergência documental com `storyboard-fdd.md` §3 aprovada — nota
   aditiva no FDD base no fechamento da frente; `[extensão]` concedida; sem ADR nova.
7. **roteiro P1**: ADR-025 aprovada (nasce no fechamento da frente, esqueleto na seção 12 do FDD).
8. **roteiro P2 — CONTRATO DO HANDOFF**: chave de settings oficial = `storyboard.script`
   (preset default `documentary-street`). Provedora e consumidora implementam exatamente
   essa chave; divergência na W5 reconcilia no contrato daqui.
9. **roteiro P3**: seletor de modelo alvo v1 só com Nano Banana Pro (`nano_banana_2`);
   GPT-Image fica fora (reversível).

## Resultado da integração (W5, 2026-08-31)

| Feature | PR | Estado |
|---|---|---|
| refs-import-url | #88 | mergeado |
| inpaint-marcacao | #89 | mergeado |
| prompter-presets-realismo | #90 | mergeado (1 conflito de teste resolvido no rebase) |
| base-clean-marca | #91 | mergeado (2 conflitos de teste resolvidos no rebase) |
| storyboard-roteiro-llm | #92 | mergeado (fix pós-update: 409 de concorrência antes do 409 de CLI) |

Critério `[cross-feature]` do handoff comprovado no estado integrado (CI verde + runtime real:
5 cenas com o rig do `documentary-street`). ADR-025 criada pela frente do roteiro.
Retro: `wave-9-retro.md`.
