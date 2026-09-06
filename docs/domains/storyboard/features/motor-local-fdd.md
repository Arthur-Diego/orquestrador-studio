# FDD: motor-local `[extensão]`

- **Versão**: 1.0 · 2026-09-05
- **Task-Id**: ADH-OS-20260905-01
- **PRD**: `.compozy/tasks/storyboard-motor-local/_prd.md`
- **Recon**: `docs/domains/storyboard/recon-solo-motor-local.md`
- **Domínio**: storyboard (etapa 4)
- **Aprovação**: total do usuário (modo auto-aceite). Ajuste explícito: **manter a Higgsfield**;
  o motor local é opção **adicional**, nunca substituto.

### 1. Contexto e motivação técnica
Hoje toda geração da etapa 4 passa pelo CLI pago da Higgsfield (`studio/higgsfield.py`), e o
"inpaint" (`kind edit_area`) é uma aproximação: manda a foto rabiscada como referência ao modelo
pago e pede por texto para mudar só na região — *"nunca inpaint real"* (ADR-002/ADR-004), porque
o CLI não aceita máscara. A skill `kling-storyboard-video` já faz, **fora** da ferramenta, geração
Flux local (grátis) e **inpaint real por máscara** via ComfyUI. Esta feature traz esses dois
caminhos para dentro da tela do Storyboard como **opção adicional**, com o desenho da máscara num
modal do próprio sistema (headless — sem abrir a UI do ComfyUI).

### 2. Objetivos técnicos
1. Ponte de motor local `studio/localengine.py` (análoga a `higgsfield.py`), fakeável nos testes.
2. Geração local de keyframes (subprocess `engine image`, Flux schnell/dev) como caminho grátis.
3. Inpaint real por máscara headless via HTTP do ComfyUI (grafo `InpaintModelConditioning` Flux).
4. Modal `MaskEditor.tsx` (pintar máscara binária, instrução, ProgressModal, antes/depois, iterar).
5. Gate de saúde (409 quando engine/ComfyUI offline). Resultados como candidatos `source:"local"`.
6. Zero regressão no caminho pago (Higgsfield, `edit`, `multishot`, `edit_area`).

### 3. Escopo e exclusões
**Inclui**: rotas `/storyboard/local/{status,generate,job,inpaint}`; módulo `localengine.py`; UI de
motor local no `Ideation.tsx` + `MaskEditor.tsx`; ADR-033; marcação `[extensão]` em todo o código.
**Exclui**: substituir Higgsfield ou aposentar o `edit_area` (ambos ficam); animação (etapa 5);
upscale local; qualquer edição da lógica de backend das outras etapas; cost-confirm/débito de
crédito (local é grátis).

### 4. Fluxos detalhados e diagramas
**F1 — Geração local de keyframes**
1. UI verifica `GET /local/status`; se `ready:false`, desabilita e mostra o motivo.
2. Usuário escreve prompt (inglês, aula 007), escolhe `count` (4|1) e modelo (schnell|dev) → `POST /local/generate`.
3. Backend abre job (`_local_registry`, key=pid, mode=`generate`); em thread, roda
   `localengine.generate_image` `count` vezes e ingere cada PNG como candidato `source:"local"`,
   meta `{local_kind:"keyframe_local", model}` (o prompt vira o campo `prompt` do candidato; a meta
   usa `local_kind` para não colidir com o `kind:"image"` da mídia). UI faz poll em `GET /local/job`.
4. Resultados aparecem na galeria de ideias (fluxo de seleção inalterado).

**F2 — Inpaint real por máscara**
1. Usuário escolhe a fonte (candidato ou base) → abre `MaskEditor` (imagem ao fundo + overlay).
2. Pinta a máscara (pincel/borracha/undo/limpar), escreve a instrução, escolhe qualidade
   (dev≈3-4min | schnell≈40s) → **Rodar (grátis)**.
3. UI exporta **máscara binária** (branco=mudar, preto=preserva) na resolução natural e envia
   `POST /local/inpaint` (multipart: `mask`, `instruction`, `source_id?`, `model`, `steps?`,
   `guidance?`, `denoise?`).
4. Backend abre job (mode=`inpaint`); em thread: resolve a imagem-fonte, chama
   `localengine.inpaint(base_bytes, mask_bytes, instruction, ...)` → sobe base+máscara ao ComfyUI
   (`/upload/image`), monta o grafo Flux inpaint, roda, baixa o resultado; ingere como candidato
   `source:"local"`, meta `{local_kind:"inpaint_local", parent, model}` (a instrução vira o `prompt`
   do candidato). O job expõe `result`/`result_id` (o candidato gerado) para o antes/depois da UI.
5. UI mostra antes/depois. **Aceitar** (fica na galeria) ou **Refinar**: reabre o `MaskEditor`
   com o resultado como nova fonte (itera sobre a própria saída, grátis).

**Grafo ComfyUI (headless)**: `UnetLoaderGGUF(flux1-dev|schnell-Q5) + DualCLIPLoaderGGUF +
VAELoader(ae) + LoadImage(base) + LoadImage(mask)→ImageToMask(channel=red) +
InpaintModelConditioning(pixels=base, mask, noise_mask=true) → FluxGuidance(guid) → BasicGuider +
RandomNoise + KSamplerSelect(euler) + BasicScheduler(simple, steps, denoise) →
SamplerCustomAdvanced(latent=Inpaint.slot2) → VAEDecode → SaveImage`. Máscara via `ImageToMask`
(determinístico) em vez de depender do canal alfa do clipspace: pintado (branco→red=255)=mask 1.0
= região regenerada; resto preservado.

### 5. Contratos públicos (endpoints)
Base: `/api/projects/{pid}/storyboard/local`. Todos 404 se o projeto não existe.

- `GET /status` → `200 {engine_installed, comfy_up, ready, detail, gen_models:[{id,label,default}],
  inpaint_models:[{id,label,default}]}` (duas listas: geração e inpaint têm catálogos distintos).
  Nunca 5xx: motor offline é `ready:false` com `detail`, não erro.
- `POST /generate` → `200 {state,done,total,added,error,log,mode:"generate",result,result_id}` (forma
  de job; start-de-job devolve 200, convenção do studio — igual à ideação paga).
  Body `{prompt:str, count:int=4, model:str="flux-schnell", steps?:int, seed?:int, scene?:str}`.
  `409` se motor offline (gate) ou job local em andamento; `422` prompt vazio / count ∉ {1,4} /
  modelo desconhecido; `403`/precondição se base ausente NÃO se aplica (generate não exige base).
  > **Campo `scene` (aditivo, wave 11 · `storyboard-geracao-por-cena`, card ADH-OS-20260906-09).**
  > Ausente ou `null` = o comportamento descrito aqui, byte a byte (ingestão em
  > `storyboard/candidates/`, galeria de ideação do painel 01b). Com `scene="cenaNN"` (presente em
  > `storyboard/scenes.json`) ou `scene="product"`, a ingestão vai para
  > `storyboard/<scene>/candidates/` e o resultado aparece na galeria da cena
  > (`GET .../angles/scenes/{scene}/candidates`). A cena é validada ANTES do gate do motor:
  > fora do regex `^cena\d{2}$` → `422`; ausente do `scenes.json` → `404`; `scenes.json`
  > inexistente → `409`. Nenhum registro de job novo (ADR-006): o job local continua por `pid`.
- `GET /job` → `200` estado do job local (mesmo formato de `job_status`, + `mode`, `result`,
  `result_id` e — wave 11 — `scene`: o id da cena de destino, `null` nos jobs de ideação).
- `POST /inpaint` → `200` job (multipart). Campos: `mask` (file PNG), `instruction` (form),
  `source_id?` (form), `model` (form="flux-dev"), `steps?`,`guidance?`,`denoise?` (form).
  `409` motor offline / job em andamento; `422` instrução vazia / máscara inválida / fonte
  inexistente / modelo desconhecido.

Convenção de erro do studio preservada: `EngineUnavailable`→409 (com `detail`), `Invalid`→422,
`Precondition`→409. Resultados servíveis por `/files/{pid}/storyboard/candidates/<file>`.

### 6. Erros, exceções e fallback
- **Motor offline** (engine ausente ou ComfyUI não responde): `require()` levanta
  `EngineUnavailable(detail, installed)` → 409; a UI mostra "suba o ComfyUI local" e desabilita os
  botões locais (Higgsfield segue funcionando).
- **Timeout/erro do ComfyUI**: job vai a `state:"error"` com `error`; nada é ingerido; UI mostra o
  erro e mantém a fonte. Sem crédito gasto (é grátis).
- **Máscara vazia / inválida**: 422 antes de tocar o ComfyUI (validação Pillow).
- **Dedupe**: `ingest_bytes` devolve None se o resultado for idêntico a um candidato existente
  (SHA-1) — `added` não incrementa; UI avisa "sem mudança".
- **Higgsfield offline** não afeta o caminho local e vice-versa (pontes independentes).

### 7. Observabilidade
- `log.info("local_job", {...})` com `pid`, `mode`, `model` e o `count` (generate) ou `parent`
  (inpaint); desde a wave 11 o `generate` carrega também `scene` (`None` na ideação). O gate/health
  não gera log de nível info.
- Sem livro-caixa (grátis): registra apenas evento informativo `settings.record_generation` com
  custo zero? **Não** — para não poluir o livro-caixa de créditos pagos; apenas `log.info`.

### 8. Dependências e compatibilidade
- **Externas (novas)**: binário `engine` (local-ai-engine) e um ComfyUI local no ar com os modelos
  Flux GGUF (`flux1-dev-Q5_K_S.gguf`, `flux1-schnell-Q5_K_S.gguf`, `ae.safetensors`, encoders).
  Tratadas como ferramenta externa local (como o CLI da Higgsfield) — gate de saúde cobre ausência.
- **Config** (env, lidas no `localengine.py`, NÃO em `config.py` que é núcleo):
  `STUDIO_LOCAL_ENGINE_BIN` (default `which engine` ou `~/.local/bin/engine`),
  `STUDIO_COMFY_URL` (default `http://127.0.0.1:8188`),
  `STUDIO_LOCAL_ENGINE_PRESET` (default `thumbnail`),
  `STUDIO_LOCAL_ENGINE_TIMEOUT` (default 1200).
- **Fronteira do núcleo (ADR-010/032)**: a feature precisa regenerar `frontend/src/api/schema.ts`
  (rotas novas mudam o `/openapi.json`; guarda de drift do CI) e reconstruir `studio/web/dist/`
  (bundle versionado). Ambos são prefixos de núcleo → a branch **declara titularidade** em
  `tests/test_adr010_fronteira_nucleo.py::TITULARES_DO_NUCLEO` com recorte mínimo
  `("frontend/", "studio/web/")`, citando este card e o ADR-033. Registro auditável no PR.
- **Compat**: nenhuma rota/modelo existente muda; `edit_area` e o `Annotate.tsx` permanecem.

### 9. Critérios de aceite técnicos
1. `GET /local/status` responde 200 com `ready` refletindo engine+ComfyUI; offline → `ready:false`
   sem 5xx. (evidência: teste com fakes)
2. `POST /local/generate` com fake engine ingere `count` candidatos `source:"local"`,
   `local_kind=="keyframe_local"`; job termina `state:"done"`, `added==count`. (teste)
3. `POST /local/inpaint` com fake ComfyClient sobe base+máscara, monta o grafo esperado
   (nós-chave: `InpaintModelConditioning`, `ImageToMask`, `FluxGuidance`) e ingere 1 candidato
   `local_kind=="inpaint_local"`, `parent==source_id|base`. (teste)
4. Motor offline → 409 em generate/inpaint; a UI desabilita os botões locais. (teste + verificação)
5. Caminho pago Higgsfield (`edit`/`multishot`/`edit_area`) inalterado: suíte existente verde. (`make verify`)
6. `MaskEditor.tsx`: pinta → exporta máscara binária correta (branco na região, resolução natural);
   iterar reusa o resultado como fonte. (`MaskEditor.test.tsx`)
7. `make verify` (ruff+pytest) e `make frontend-verify` (typecheck+lint+vitest) verdes; `schema.ts`
   e `dist/` regenerados e sem drift.
8. **[manual, máquina do usuário]** Com ComfyUI no ar: gerar 1 keyframe e fazer 1 inpaint real
   preservando a área fora da máscara. (evidência do usuário — fora do CI, `soft`/pendência)

### 10. Riscos e mitigação
- **Polaridade da máscara** (principal): usar `ImageToMask(channel=red)` sobre máscara binária
  branco=mudar torna a polaridade determinística, sem depender do alfa do clipspace. Validação viva
  fica no critério 8 (manual). Se a convecção do modelo exigir inversão, um único ponto
  (`localengine.inpaint`) inverte.
- **Ambiente externo ausente** (ComfyUI/modelos): coberto pelo gate 409 + runbook; nunca 5xx.
- **Crescimento do `service.py`**: a lógica local vive em módulo próprio `studio/storyboard/local.py`
  (não incha `service.py`), importando helpers pontuais.
- **Node ausente para o build**: verificado disponível (Node 24). Se faltasse, o front seria
  `soft fail` e o backend entregaria sozinho.

### 11. Sequenciamento de implementação (Build Order)
1. `studio/localengine.py` — bridge (status/require/generate_image/inpaint) + grafo, fakeável.
2. `studio/storyboard/local.py` — serviço da etapa (status/start_generate/job/start_inpaint) sobre
   `_local_registry` + `ingest_bytes`.
3. `studio/etapas/storyboard/router.py` — 4 rotas `/local/*` (delegam a `local.py`; mapeiam erros).
4. Testes backend: `tests/test_storyboard_local.py` (fakes de engine e ComfyClient).
5. `studio/etapas/storyboard/ui/MaskEditor.tsx` + `MaskEditor.test.tsx`.
6. `studio/etapas/storyboard/ui/Ideation.tsx` — painel "Motor local (grátis)" (gerar + inpaint).
7. Declarar titularidade em `tests/test_adr010_fronteira_nucleo.py`.
8. `make frontend-schema` + `make frontend-build` (regenera schema.ts e dist).
9. ADR-033 (motor local como 2ª ponte externa; supera parcialmente ADR-004).

### Pendências para o gate em lote (nunca auto-aceitas)
- Nenhuma divergência com contrato publicado (a etapa não tem `contracts-fit`; contratos vivem no
  `/openapi.json`). Validação viva do inpaint (critério 8) depende da máquina do usuário → registrada
  como pendência de ambiente, não bloqueio de merge.
