---
status: completed
title: Backend — persistência da marcação, kind `edit_area` e ação `storyboard.inpaint`
type: backend
complexity: high
---

# Task 1: Backend — persistência da marcação, kind `edit_area` e ação `storyboard.inpaint`

## Overview
Entrega a fatia vertical de servidor inteira do modo "área marcada" `[extensão]`: persistir o PNG
anotado como candidato `role:"annotation"` (invisível na galeria e não selecionável), o kind novo
`edit_area` que manda `image_references = [original, anotada]` com instrução fixa em inglês, o
registro no livro-caixa com a ação nova `storyboard.inpaint`, e a rota `POST .../storyboard/annotate`
mais o campo aditivo `annotation_id` no `GenerateReq`. Tudo é aditivo: nenhuma rota, kind, mensagem
ou schema existente muda.

<critical>
- ALWAYS READ `_techspec.md` (seções 5, 6, 9 e 11) e `_prd.md` before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `KINDS` em `studio/storyboard/service.py` **MUST** ganhar um quarto item
  `{"kind": "edit_area", "label": ..., "cli": True, "ui_hint": ...}` com o rótulo `[extensão]`
  visível; os três itens existentes **MUST NOT** mudar (label, `cli` e `ui_hint` byte a byte).
- `build_instruction` **MUST** ganhar um ramo próprio para `edit_area` que devolve exatamente a
  instrução fixa da seção 5 do `_techspec.md` com `{core}` interpolado (a instrução do usuário sem
  a pontuação final, como já faz `core = body.rstrip(" .;")`). Esse ramo **MUST NOT** usar `SUFFIX`
  como os kinds antigos. As validações existentes (vazio, `MAX_TEXT`, `COUNTS`,
  `_check_single_instruction`) **MUST** valer igualmente para o kind novo, com as mesmas mensagens.
- Uma função nova de serviço **MUST** persistir a marcação: validar que os bytes decodificam como
  imagem (Pillow) — senão `Invalid` com a mensagem da matriz —, resolver o `parent`
  (`source_id` do candidato ou o literal `"base"`, exigindo a base via `_require_base` quando não há
  `source_id`), chamar `ingest.ingest_bytes(root, STEP, data, "annotation", name, "", {"role": "annotation", "parent": parent})`
  e devolver `{id, file, thumb, parent, role, deduped}`.
- Como `ingest_bytes` devolve `None` tanto em dedupe quanto em conteúdo inválido, o serviço
  **MUST** calcular o `sha1(data)[:12]` e consultar os candidatos ANTES de ingerir para saber se é
  dedupe, devolvendo `deduped: true` com o candidato já existente (idempotência do contrato 1).
  `ingest_bytes` **MUST NOT** ser alterada (afetaria todos os chamadores).
- A galeria pública **MUST NOT** listar anotações: `list_ideas` filtra candidatos com
  `role == "annotation"`. `select_ideas` **MUST** recusar id de anotação com 422 e a mensagem da
  matriz, e a validação de imagem de cena **MUST** continuar impedindo que uma anotação vire cena.
- `_cli_request` **MUST** ser estendida para aceitar `annotation_id` e devolver a LISTA de
  referências em vez de uma string única, com a ORIGINAL sempre no índice 0. Para os kinds antigos
  a lista **MUST** ter exatamente 1 item, preservando o comportamento atual byte a byte
  (`{"prompt": ..., "image_references": [src]}`).
- `cost` e `start_generate` **MUST** aceitar `annotation_id` opcional (default `None`) e repassá-lo;
  chamadas existentes sem o campo **MUST** continuar válidas.
- Validações de `edit_area` (todas 422, mensagens exatas da matriz da seção 6 do `_techspec.md`):
  sem `annotation_id`; `annotation_id` inexistente ou com `role != "annotation"`; `parent` da
  anotação diferente da imagem original resolvida (`source_id` ou `"base"`).
- Dentro do job, cada geração bem-sucedida do kind `edit_area` **MUST** chamar
  `settings.record_generation(action="storyboard.inpaint", model=..., count=1, pid=..., step="storyboard", job_id=...)`.
  Os kinds antigos **MUST NOT** passar a registrar nada (pendência P1 do gate: fora desta wave).
- Os candidatos importados pelo job de `edit_area` **MUST** levar
  `meta = {"job_id": ..., "model": ..., "kind": "edit_area", "annotation": <id da anotação>}`.
- `ACTIONS` e `DEFAULTS` em `studio/common/settings.py` **MUST** ganhar a chave
  `storyboard.inpaint` exatamente como na seção 5 do `_techspec.md` (contrato 5); nenhuma chave
  existente muda de posição de forma que altere mensagens ou testes atuais.
- `studio/etapas/storyboard/router.py` **MUST** ganhar `annotation_id: str | None = None` em
  `GenerateReq` e a rota `POST /api/projects/{pid}/storyboard/annotate` (multipart `file` +
  `source_id` opcional via `Form`), com 413 acima de `MAX_UPLOAD_BYTES` no padrão das rotas de
  upload existentes e `_guard` traduzindo `Invalid → 422` / `Precondition → 409`.
- A task **MUST NOT** editar `studio/app.py`, `studio/steps.py`, `studio/web/*`,
  `studio/common/ingest.py`, `studio/higgsfield.py` nem `tests/conftest.py`.
- A task **MUST NOT** tocar a metade de ângulos (`studio/storyboard/angles.py` e suas rotas).
</requirements>

## Subtasks
- [x] 1.1 Ler `_techspec.md` seções 5 (contratos 1, 2, 3 e 5), 6 (matriz de erros), 9 (critérios 1 a 6)
      e 11 (build order), e `_prd.md`.
- [x] 1.2 Acrescentar o kind `edit_area` em `KINDS` e o ramo da instrução fixa em `build_instruction`.
- [x] 1.3 Implementar a persistência da marcação no serviço (decode, resolução do `parent`, dedupe
      explícito por SHA-1, retorno do contrato 1).
- [x] 1.4 Filtrar anotações da galeria e recusá-las em seleção de ideia e como imagem de cena.
- [x] 1.5 Estender `_cli_request` para devolver lista de referências e validar `annotation_id`
      (existência, `role`, `parent` × original).
- [x] 1.6 Estender `cost` e `start_generate` com `annotation_id`; ligar `record_generation` só no
      ramo `edit_area` e gravar `meta.annotation` nos candidatos importados.
- [x] 1.7 Acrescentar `storyboard.inpaint` em `ACTIONS`/`DEFAULTS`.
- [x] 1.8 Acrescentar `annotation_id` ao `GenerateReq` e a rota `POST .../storyboard/annotate`.
- [x] 1.9 Escrever os testes de serviço e de API listados em `## Tests`.
- [x] 1.10 Rodar `make verify` e deixar verde (a suíte inteira leva ~6 min; use
      `.venv/bin/pytest tests/test_storyboard_service.py tests/test_storyboard_api.py` durante o
      desenvolvimento e a suíte completa no fim).

## Implementation Details

Arquivos a modificar (caminhos relativos à worktree):

- `studio/storyboard/service.py` — `KINDS` (~linha 74), `build_instruction` (~228-254),
  `_candidates`/`_idea_row`/`list_ideas` (~131-135, 283-293), `select_ideas` (~303-341),
  `_check_image` (~447-455), `_cli_request` (~552-565), `cost` (~568-574),
  `start_generate` (~577-612). `BASE_IMAGE`/`base_rel`/`_require_base` (~39, 138-147) resolvem a
  imagem base. O módulo já importa `settings`; `start_video_generate` (~930) é o exemplo vivo de
  `record_generation` neste mesmo arquivo — copiar o estilo da chamada.
- `studio/common/settings.py` — `ACTIONS` (~32-56) e `DEFAULTS` (~61-75).
- `studio/etapas/storyboard/router.py` — `GenerateReq` (~61-66), rotas de `cost`/`generate`
  (~194-201), helper `_payload` (~308-315) e `MAX_UPLOAD_BYTES` (~21). O padrão exato de rota de
  upload de arquivo único está em `angles_base_upload` (~330-333) e o de `file` + `Form` em
  `storyboard_upload` (~136-145).
- `tests/test_storyboard_service.py` e `tests/test_storyboard_api.py` — acrescentar ao FIM dos
  arquivos, sem renomear nem reescrever testes existentes.

Pontos de atenção descobertos na exploração:

- `ingest_bytes(root, step, data, source, name, prompt="", meta=None, kind="image")` devolve
  `dict | None`; o `None` NÃO distingue dedupe de conteúdo inválido, e o `meta` é espalhado por
  cima do dict do candidato (`**meta`), de modo que `meta["kind"]` sombreia o `kind` de mídia —
  comportamento existente, a preservar, não a corrigir.
- `_cli_request` hoje devolve `(built, src)` com `src` string; `cost` e `start_generate` fazem
  `"image_references": [src]`. Mudar o retorno para uma lista é local a este arquivo (só esses dois
  chamadores), mas a lista de 1 item dos kinds antigos precisa continuar produzindo exatamente o
  mesmo payload para o CLI.
- `start_generate` hoje NÃO chama `record_generation` — é justamente a pendência P1; só o ramo novo
  passa a chamar.
- A instrução fixa é montada pelo SERVIDOR e é o valor de `params["prompt"]`; o teste do contrato
  compara o prompt inteiro, então o texto precisa bater com o `_techspec.md` caractere a caractere.

### Relevant Files
- `studio/storyboard/service.py` — serviço da etapa 4; concentra kinds, instrução, CLI e job.
- `studio/common/ingest.py` — `ingest_bytes` (leitura apenas; é o mecanismo de dedupe/thumbs/meta).
- `studio/common/settings.py` — `ACTIONS`/`DEFAULTS`/`default_for`/`all_defaults`/`record_generation`.
- `studio/etapas/storyboard/router.py` — rotas da etapa e `GenerateReq`.
- `studio/common/jobs.py` — `JobRegistry` usado por `start_generate` (um job por projeto → 409).
- `tests/conftest.py` — `make_image`/`image_bytes`, fixtures `studio_env`/`project`.
- `tests/test_storyboard_service.py` — `_fake_cli` (~283-301) e `_wait_job` (~304-309) a reutilizar.
- `tests/test_storyboard_api.py` — fixture `base` (~19-22) e o teste que captura `image_references`
  (~278-294), que é o molde do assert de ordem das referências.

### Dependent Files
- `studio/etapas/storyboard/view.js` / `view.html` — consumidores do contrato (task 02); esta task
  **não** os edita.
- `docs/domains/storyboard/postman/storyboard.postman_collection.json` — atualizado fora do
  pipeline, depois desta task.

### Related ADRs
- ADR-002 — geração só pelo CLI oficial da Higgsfield; nada de máscara real nem de API direta.
- ADR-004 — `[extensão]` exige aprovação do dono (dada no gate W3 da Wave 9) e marca explícita.
- ADR-010 — núcleo (`app.py`, `steps.py`, `web/*`) não é editado por feature de etapa.
- ADR-016 — custo estimado antes de gerar, livro-caixa depois, modelo default por ação.
- ADR-006 — job longo em thread com polling.
- ADR-008 — testes sem rede e sem navegador, com fakes de `hf.*`.

## Deliverables
- Kind `edit_area` funcional de ponta a ponta no servidor (instrução fixa, duas referências na
  ordem certa, custo, job, livro-caixa).
- Rota `POST /api/projects/{pid}/storyboard/annotate` idempotente por SHA-1.
- Anotações invisíveis na galeria e recusadas em seleção/cena.
- Ação `storyboard.inpaint` resolvível por `default_for` e listada em `all_defaults`.
- Todos os casos de `## Tests` implementados e passando; `make verify` verde.

## Tests

Sem `_tests.md` neste workflow — os casos abaixo são normativos e vêm dos critérios 1 a 6 da
seção 9 do `_techspec.md`. Fakes de `hf.*` obrigatórios (ADR-008); nada de rede.

**Serviço (`tests/test_storyboard_service.py`)**
1. Marcação salva com PNG válido e `source_id` de um candidato cria candidato com
   `role == "annotation"` e `parent == <source_id>`; sem `source_id`, `parent == "base"`.
2. Reenviar bytes idênticos devolve `deduped: true`, o MESMO `id`, e não cria segundo arquivo em
   `storyboard/candidates/`.
3. Bytes que não decodificam como imagem levantam `Invalid` com a mensagem
   "arquivo de marcação inválido (envie o PNG exportado pelo canvas)".
4. `list_ideas` não inclui o candidato de anotação; um candidato comum importado antes continua
   aparecendo.
5. `select_ideas` com id de anotação levanta `Invalid` com "marcação não pode ser selecionada como
   ideia"; seleção de ideia comum segue funcionando.
6. `build_instruction(kind="edit_area")` devolve o prompt fixo do `_techspec.md` com o texto do
   usuário interpolado, e continua recusando texto vazio, texto acima de 300 chars, `count` fora de
   `{1, 4}` e instrução múltipla com as mensagens atuais.
7. `start_generate` com `kind="edit_area"` chama `hf.generate` com `params["image_references"]` de
   exatamente 2 itens, o primeiro terminando no arquivo da imagem ORIGINAL (base ou candidato) e o
   segundo no arquivo da anotação; `params["prompt"]` igual à instrução fixa.
8. Job de `edit_area` concluído importa os resultados com `meta.kind == "edit_area"` e
   `meta.annotation == <id da anotação>`, e grava uma linha por geração no ledger com
   `action == "storyboard.inpaint"`.
9. `start_generate` com `kind="edit"` (antigo) NÃO grava nada no ledger e manda
   `image_references` com exatamente 1 item — regressão da pendência P1.
10. `settings.default_for("storyboard.inpaint", pid)` resolve `nano_banana_2`/`2k` com
    `source == "code"`, respeita override global e de projeto, e a ação aparece em `all_defaults`.

**API (`tests/test_storyboard_api.py`)**
11. `POST .../storyboard/annotate` com PNG válido responde 200 no formato do contrato 1
    (`id`, `file`, `thumb`, `parent`, `role`, `deduped`) e o arquivo é servível por `/files/{pid}/<file>`.
12. `POST .../storyboard/annotate` em projeto inexistente → 404; com `source_id` inexistente → 422;
    sem `source_id` e sem `base/base_final.png` → 409; arquivo acima de `MAX_UPLOAD_BYTES` → 413.
13. `POST .../storyboard/cost` com `kind="edit_area"` sem `annotation_id` → 422 com
    "o modo área marcada exige a marcação salva (annotation_id)".
14. `POST .../storyboard/cost` com `annotation_id` inexistente ou apontando para candidato comum
    (`role != "annotation"`) → 422 com "marcação inexistente: {id}".
15. `POST .../storyboard/cost` com anotação cujo `parent` não bate com a original resolvida → 422
    com "a marcação {id} pertence a outra imagem; marque a imagem escolhida".
16. `POST .../storyboard/cost` e `/generate` com `edit_area` válido respondem no formato atual
    (`{per_image, total}` e o payload do `JobRegistry`), e `GET .../storyboard/candidates` após o
    job lista os resultados sem listar a anotação.
17. Requisições dos kinds antigos sem `annotation_id` continuam com o mesmo status e a mesma
    mensagem de hoje (regressão de compatibilidade do contrato 2).

## Success Criteria
- Todos os casos de `## Tests` implementados e passando.
- `git diff --name-only` não inclui `studio/app.py`, `studio/steps.py`, `studio/web/index.html`,
  `studio/web/app.js`, `studio/web/ui.js`, `studio/web/multishot.js` nem `studio/common/ingest.py`.
- `make verify` verde (ruff + suíte completa), com a suíte de baseline (976 testes) sem regressão.
- Nenhuma mensagem, rota ou campo existente alterado.
