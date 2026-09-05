# Recon (solo) — Motor de imagem local no Storyboard `[extensão]`

> Estado compartilhado desta entrega (ADH-OS-20260905-01). Sintetizado da análise do codebase
> em 2026-09-05. Serve de terreno para o FDD e a implementação — não reexplorar.

## 1. Arquitetura do domínio (etapa 4 · Storyboard)

- **Plugin da etapa**: `studio/etapas/storyboard/` (`META`, `router.py`, `guide.py`, `ui/`).
  Descoberto por `studio.etapas.discover()` (backend) e `import.meta.glob` (shell React). Núcleo
  (`app.py`, `steps.py`, `higgsfield.py`) **não** se edita (ADR-010/ADR-032).
- **Serviço**: `studio/storyboard/service.py` (ideação + cenas) e `studio/storyboard/angles.py`
  (ângulos por cena → escreve `storyboard.json` consumido pela etapa 5 `animate`).
- **UI**: `ui/Ideation.tsx` (ideação + `[extensão]` inpaint-marcacao/vídeo/roteiro), `ui/Angles.tsx`,
  `ui/Annotate.tsx` (modal de canvas de MARCAÇÃO), `ui/index.tsx` (monta as duas metades).

## 2. Como a geração de imagem funciona HOJE (100% Higgsfield / pago)

- Toda geração passa **só** pelo CLI oficial da Higgsfield via `studio/higgsfield.py`
  (`_run` → subprocess + `--json`; `require_cli()` → gate 409; `cost`, `generate`). Nunca a HTTP
  API (ADR-002). Modelos: `nano_banana_2` (default), `gpt_image_2 [extensão]`.
- Ideação: `POST .../storyboard/instructions` (só monta prompt, 0 crédito), `.../cost`,
  `.../generate` (`sb.start_generate` → `hf.generate` em loop `count`, ingere cada resultado como
  candidato `source:"cli"`), `GET .../job` (poll `JobRegistry`).
- `kind`s: `draw_to_edit` (só UI Higgsfield, recusado no CLI), `edit`, `multishot`, `edit_area`.

## 3. O "inpaint" atual (`edit_area`) NÃO é inpaint real

- `EDIT_AREA_INSTRUCTION` + o modal `Annotate.tsx`: o usuário rabisca de vermelho a região; o
  front **achata** foto+rabisco num PNG e envia como 2ª `image_reference` ao modelo **pago**,
  pedindo por texto para mudar só ali. Código admite: *"aproximação best-effort, nunca inpaint
  real"* (`service.py:119-125`), porque o CLI não aceita máscara (ADR-002, ADR-004).
- Persistência da marcação: `import_annotation` → candidato `role:"annotation"` (invisível na
  galeria), `parent` = id da fonte ou `"base"`, dedupe por SHA-1. Uso em `_cli_request` (checagem
  de posse `parent == source_id|base`).

## 4. Stack LOCAL grátis já existente no workspace (a reusar)

- **CLI `engine`** (`~/.local/bin/engine` → `local_ai_engine/.venv/bin/engine`, pacote
  `local-ai-engine`). `engine image <prompt> --preset --model flux-schnell|flux-dev --steps --seed`
  imprime o caminho do PNG na última linha do stdout. `engine doctor` = health.
- **Precedente de uso por subprocess**: `fluxo_video/engine_local.py` (`gerar_imagem`, `runner`
  injetável) — o padrão a espelhar para NÃO carregar torch/comfy no venv do studio.
- **Inpaint real** existe só como grafo inline em
  `.agents/skills/kling-storyboard-video/scripts/1a_editar.py`: fala HTTP direto com o ComfyUI
  (`/upload/image` opcional, `/prompt`, `/history`, `/view`). Grafo Flux GGUF:
  `UnetLoaderGGUF flux1-dev-Q5` + `DualCLIPLoaderGGUF` + `VAELoader ae.safetensors` +
  `LoadImage(base)` + `LoadImage(mask)` + `InpaintModelConditioning(pixels=base, mask, noise_mask)`
  → `FluxGuidance` → `BasicGuider`/`RandomNoise`/`KSamplerSelect(euler)`/`BasicScheduler(simple)` →
  `SamplerCustomAdvanced(latent=Inpaint.slot2)` → `VAEDecode` → `SaveImage`. Knobs: model dev/schnell,
  steps (dev=20/schnell=4), guidance (3.5; 6-8 reforça remoção), denoise (1.0).
  ComfyUI default `http://127.0.0.1:8188`. Cliente HTTP reusável: `engine.comfy.ComfyClient`.

## 5. Persistência e contratos

- Candidatos: `studio/common/ingest.py::ingest_bytes(root, "storyboard", data, source, name, prompt, meta)`
  → grava PNG + thumb em `projects/<id>/storyboard/candidates/`, linha em `candidates.json`,
  dedupe por SHA-1. Galeria oculta `role:"annotation"`.
- Saída da etapa: `storyboard.json` (escrito pela metade ÂNGULOS), consumido por `animate`.
- **Gate de custo** (front): `useCostConfirm`/`CostSheet`; **livro-caixa** (ADR-016):
  `settings.record_generation(action=..., model=..., count=...)`. O caminho local é GRÁTIS → sem
  cost-confirm e sem débito de crédito (registra evento grátis, como o roteiro por Claude).

## 6. Frontend (Wave 10 · React)

- Design system em `frontend/src/ui/` (`Modal`, `ProgressModal`+`useProgress`, `CostSheet`,
  `HfChip`, etc.). Acesso à API em `frontend/src/api/` com `schema.ts` **gerado** do `/openapi.json`
  (`make frontend-schema` + commit; guarda de drift no CI). Bundle **versionado** em
  `studio/web/dist/` (`make frontend-build` + commit; CI rebuilda e compara).
- `ui/Annotate.tsx`: canvas em resolução natural, pointer events unificados, pincel/undo/clear,
  export PNG. Base direta para o novo `MaskEditor.tsx` (muda export → máscara binária branco/preto).

## 7. Restrições que limitam o desenho

- Núcleo intocável (ADR-010/032): não editar `app.py`/`steps.py`/`higgsfield.py`/`etapas/__init__.py`/
  `frontend/src/**` (exceto o gerado `schema.ts` e o `dist/`). Novo módulo `studio/localengine.py`
  e UI co-localizada são permitidos à frente da etapa.
- Testes sem rede e sem navegador (fakes). A ponte local precisa ser fakeável (runner/cliente
  injetáveis), como `hf` e `engine_local` já são.
- Fidelidade ao curso: motor local é troca de FERRAMENTA (mesmo artefato) + capacidade nova
  (inpaint real) → tudo `[extensão]` + **ADR novo** (supera parcialmente ADR-004).

## 8. Lacunas

- Não há `hld.md` do domínio storyboard (só `prd.md` + ADRs + FDDs). Terreno usado: `prd.md`,
  ADR-002/004/010/013/015/016/018/021/022/031/032 e os FDDs existentes. HLD fica como pendência.
