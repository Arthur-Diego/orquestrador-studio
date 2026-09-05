# ADR-033: Motor de Imagem Local (ComfyUI/Flux) como Segunda Ponte de Ferramenta Externa

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-01
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-002](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md)

## Contexto e Problema

Até aqui, toda geração de imagem da etapa 4 (Storyboard) passava por uma única ponte de
ferramenta externa: o CLI oficial da Higgsfield (`studio/higgsfield.py`, ADR-002), que gasta
crédito. O "inpaint" da etapa (`kind edit_area`, `[extensão]` inpaint-marcacao) é, por
limitação registrada, uma **aproximação**: como o CLI não aceita máscara (ADR-002), o Studio
manda a imagem rabiscada de vermelho como referência extra e pede, por prompt, para mudar só
ali — o próprio código diz *"aproximação best-effort, nunca inpaint real"*. O ajuste
localizado fino, portanto, era impreciso e pago por tentativa.

O workspace já tem um stack LOCAL e grátis para exatamente isso: o CLI `engine`
(local-ai-engine) gera imagens Flux, e o ComfyUI local faz **inpaint real por máscara**
(grafo `InpaintModelConditioning` Flux GGUF) — usados hoje fora da ferramenta pela skill
`kling-storyboard-video`. O problema: trazer esse caminho para dentro do Studio significa
introduzir uma **segunda ferramenta externa local** (o ComfyUI, falado por HTTP) e um
inpaint que o curso só ensina na UI da Higgsfield — o que exige decisão explícita à luz de
ADR-001 (monolito single-process), ADR-002 (Higgsfield só via CLI) e ADR-004 (fidelidade ao
curso: capacidade nova é `[extensão]` + ADR).

Restrição de produto (decisão do usuário): **a Higgsfield não é substituída** — o motor
local é um caminho ADICIONAL.

## Decision Drivers

- Iteração grátis e ilimitada de keyframes, e ajuste localizado **preciso** (inpaint real),
  sem sair da ferramenta nem gastar crédito na exploração.
- Não regredir o caminho pago existente (Higgsfield, `edit`/`multishot`/`edit_area`).
- Preservar as invariantes: single-process do Studio (ADR-001), fronteira do núcleo
  (ADR-010), testes sem rede/navegador (ADR-008), livro-caixa de créditos (ADR-016).
- Fidelidade ao curso (ADR-004): troca/adição de FERRAMENTA que produz o mesmo artefato é
  legítima; a capacidade nova (inpaint real) entra marcada `[extensão]`.

## Decisão

Adotar o **motor de imagem local** como uma **segunda ponte de ferramenta externa**, análoga
à ponte da Higgsfield, num novo módulo `studio/localengine.py`:

1. **Ferramenta externa local, não segundo runtime.** O ComfyUI e o `engine` são tratados
   como o CLI da Higgsfield já é: processos externos locais que o Studio (mesmo processo
   single-process, ADR-001) invoca — `engine image` por subprocess (geração) e a HTTP API do
   ComfyUI (inpaint headless). Não há segundo servidor no runtime do Studio.
2. **Caminho ADICIONAL, grátis.** Novas rotas `POST/GET .../storyboard/local/{status,
   generate,job,inpaint}` ao lado das pagas. Sem `cost`/cost-confirm e sem débito no
   livro-caixa (ADR-016 intacto: só o pago registra crédito). O `edit_area` legado e o
   `Annotate.tsx` permanecem.
3. **Inpaint REAL por máscara, headless.** A máscara é pintada num modal do próprio sistema
   (`MaskEditor.tsx`), exportada como máscara binária e enviada ao ComfyUI via `/upload/image`
   + grafo `InpaintModelConditioning`; a região fora da máscara é preservada de verdade. O
   usuário nunca abre a UI do ComfyUI. Isto **supera parcialmente** a limitação registrada em
   ADR-004/ADR-002 ("inpaint só na UI/CLI sem máscara"): agora existe inpaint real, local.
4. **Gate de saúde, não erro.** `localengine.require()` levanta `EngineUnavailable` → HTTP
   409 quando o `engine` está ausente ou o ComfyUI não responde; a UI desabilita os botões
   locais com o motivo. Motor offline nunca é 5xx, e nunca afeta o caminho pago.
5. **Fakeável (ADR-008).** `generate_image(runner=...)` e `inpaint(client=...)` aceitam
   injeção; o health é monkeypatchável. Os testes rodam sem rede, sem subprocess, sem ComfyUI.
6. **Fronteira do núcleo (ADR-010).** A ponte (`studio/localengine.py`), o serviço
   (`studio/storyboard/local.py`), as rotas e a UI co-localizada não tocam o núcleo. Os
   únicos artefatos de núcleo tocados são os **gerados** — `frontend/src/api/schema.ts`
   (rotas novas mudam o `/openapi.json`) e o bundle `studio/web/dist/` —, com a branch
   declarando titularidade mínima `("frontend/", "studio/web/")` em
   `tests/test_adr010_fronteira_nucleo.py`.

Config por env (lidas no `localengine.py`, não em `config.py`, que é núcleo):
`STUDIO_LOCAL_ENGINE_BIN`, `STUDIO_COMFY_URL` (default `http://127.0.0.1:8188`),
`STUDIO_LOCAL_ENGINE_PRESET`, `STUDIO_LOCAL_ENGINE_TIMEOUT`.

## Alternativas consideradas

- **Importar `engine` em processo** (usar `engine.image.generate` diretamente): rejeitada —
  puxaria torch/comfy para o venv do Studio e conflitaria com o espírito single-process leve.
  Subprocess + HTTP (como a `fluxo_video` já faz) mantém o Studio enxuto.
- **Substituir a Higgsfield pelo local**: rejeitada por decisão do usuário e por fidelidade
  ao curso — o pago é o caminho da aula; o local é adição.
- **Manter só o `edit_area` aproximado**: rejeitada — é justamente a limitação que motiva
  este ADR.

## Consequências

**Positivas:** iteração grátis; inpaint localizado preciso e preservador; integrado ao fluxo
(resultado vira candidato `source:"local"` e segue seleção → cena → ângulos → animate); sem
regressão do pago; invariantes preservadas.

**Negativas / custos:** nova dependência de ambiente externo (ComfyUI no ar + modelos Flux
GGUF) — mitigada pelo gate 409 e por runbook; a polaridade da máscara depende da convenção do
ComfyUI (mitigada por `ImageToMask channel=red`, determinístico, com um ponto único de
inversão se necessário); a validação viva do inpaint (com o ComfyUI no ar) é manual, na
máquina do usuário, fora do CI.
