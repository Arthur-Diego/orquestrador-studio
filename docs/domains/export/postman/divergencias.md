# Divergências: FDD `export` × implementação (`router.py` / `service.py`)

Gerado em 2026-08-25, commit `b7e1052`.

- FDD: `docs/domains/export/features/export-fdd.md` (seção 5 "Contratos públicos", linhas 124-333; matriz de erros da seção 6, linhas 341-355).
- Contrato publicado (OpenAPI): **não existe neste repositório**. Busca por `openapi*.{yaml,yml,json}` com profundidade 3 a partir da raiz da worktree, dos repositórios irmãos do workspace e de `node_modules/@*/contracts*/` não retornou nada. A comparação abaixo é FDD × código implementado.

> **Estado após a revisão da frente (2026-08-25).** Os itens **1**, **3** e **5** foram tratados
> antes da PR: o **5** (risco de 500 em `GET /status` e `GET /list` com arquivo ilegível) virou
> correção de código — `_safe_probe` engole a falha do ffprobe e a rota devolve 200 sem os
> metadados daquele arquivo, com teste de regressão; o **3** (ordem de validação do reframe)
> também virou correção — as duas rotas de reframe validam projeto → `aspect_ratio` (422) → CLI
> (409), nessa ordem; o **1** (502 do contrato 9) foi resolvido como **documentação**: não existe
> caminho de execução para ele, e isso está registrado nas "Notas de implementação" do FDD.
> Os demais itens continuam válidos como registrados e estão descritos no FDD.

| # | Severidade | O que o FDD diz | O que o código faz | Fontes |
| --- | --- | --- | --- | --- |
| 1 | **ALTA** | Contrato 9: `POST /export/reframe` responde **502** em "falha do CLI ao iniciar" (linha 318). A matriz da seção 6 fixa o padrão `CLI→502` (linha 339). | Nenhum caminho produz 502. `_call` traduz só `FileNotFoundError→404`, `ValueError→422`, `RuntimeError→409` (`router.py:30-39`). A falha do `hf.generate` acontece dentro da thread do job, depois do 200 já devolvido, e vira `state=error` (`service.py:445-453`). | FDD linha 318 · `studio/etapas/export/router.py:30-39,85-90` |
| 2 | MEDIA | Contrato 8: `POST /export/reframe/cost` tem apenas **200** e **409 CLI não instalado** (linha 302). | `reframe_cost` também valida `aspect_ratio` (`ValueError → 422`) e exige o master (`FileNotFoundError → 404`). Dois status não declarados no contrato. | FDD linha 302 · `studio/export/service.py:424-432` |
| 3 | MEDIA | Contrato 9: `aspect_ratio` fora de `{"9:16","1:1"}` → **422** (linha 318). | O router checa `hf.available()` **antes** de validar o corpo, então em máquina sem o CLI um `aspect_ratio` inválido responde **409 "CLI da Higgsfield não instalado"**, nunca 422. O 422 só é observável com o CLI instalado. | FDD linha 318 · `studio/etapas/export/router.py:85-90` |
| 4 | MEDIA | Contratos 2, 3, 5 e 6 listam 404 (master ausente), 409 (ffmpeg indisponível) e 422 (entrada inválida) **sem definir precedência** (linhas 178-180, 197-200, 228, 244). | A ordem é fixa e nem sempre a mais informativa: `preview` valida o formato (422) antes de tudo; `preview`, `render`, `thumb` e `qa` checam ffmpeg (409) **antes** do master (404). Projeto sem master numa máquina sem ffmpeg responde 409, não 404. O critério de aceite da linha 416 ("`POST /render` sem master responde 404") só vale com ffmpeg presente. | FDD linhas 178-180, 416 · `studio/export/service.py:234-241,253-258,296-301,327-332` |
| 5 | MEDIA | Contrato 1: `GET /export/status` → "200 **sempre** que o projeto existe" (linha 152). Contrato 7: `GET /export/list` → "200 **sempre**" (linha 286). | As duas rotas não passam por `_call` e chamam `ff.probe`/`_probe_full` direto. Um arquivo corrompido ou de 0 byte em `export/` faz o ffprobe sair com código não zero → `RuntimeError` não tratado → **500**. `ff.available()` sendo True não garante que o probe de cada arquivo funcione. | FDD linhas 152, 286 · `studio/etapas/export/router.py:42-49` · `studio/export/service.py:184,217` · `studio/common/ffmpeg.py:39-40` |
| 6 | BAIXA | Exemplo do contrato 3 (linha 210) não tem o campo `mode`; o do contrato 9 (linha 328) não tem `formats`. | `start_render` passa `mode="render", formats=[...]` e `start_reframe` passa `mode="reframe", aspect_ratio=..., formats=[fmt]` para a `JobRegistry`, que espalha os extras no corpo do job. Campos aditivos, compatíveis com a garantia da seção 8 (linha 402). | FDD linhas 210, 328 · `studio/export/service.py:287,468` |
| 7 | BAIXA | Exemplo do contrato 1 (linha 164): `"thumb": {"file": "export/thumb.jpg", "t": 3.0}`. | O corpo real também traz `size`, e `t` vem de `export/.state.json` — arquivo interno não documentado em nenhuma seção do FDD (pode ser `null` se a thumb foi gerada por outra via). | FDD linha 164 · `studio/export/service.py:38,66-78,186` |
| 8 | BAIXA | Seção 6, linha 346: 409 com a mensagem "job em andamento". | A mensagem real vem da `JobRegistry`: "Já existe um trabalho em andamento para este projeto." Semântica igual, texto diferente. | FDD linha 346 · `studio/common/jobs.py:17` |
| 9 | BAIXA | Modelo do `qa_report.md` (linhas 265-266): cabeçalho de 2 linhas terminando em "publique mesmo que o primeiro fique **ruim**". | O gerado tem 3 linhas de cabeçalho e termina em "publique mesmo que o primeiro fique **fraco**". Divergência puramente textual; nenhuma checagem depende disso. | FDD linhas 265-266 · `studio/export/service.py:390-396` |
| 10 | BAIXA | Seção 6, linha 348: `t` fora de `[0, duração]` → 422. | `_valid_t` só aplica o limite superior quando `duration` é verdadeiro: com um master de duração 0 (arquivo degenerado), qualquer `t` positivo passa. | FDD linha 348 · `studio/export/service.py:148-155` |

## Sem divergência (verificado)

- As 9 rotas da seção 5 existem no router com método e caminho exatos, sob `/api/projects/{pid}/export/...`, sem prefixo extra (`studio/app.py:63` inclui o router do plugin sem `prefix`).
- 404 para `pid` inválido ou inexistente em todas as rotas, pelo handler de `KeyError` do núcleo (`studio/app.py:25-27`), como a seção 6 (linha 343) descreve.
- Nomes de checagem do QA (`exists`, `resolution`, `duration`, `vcodec`, `audio`, `size`) batem com a linha 280 do FDD, e `verdict` é `OK`/`ATENCAO` derivado delas.
- `GET /export/list` ignora `previews/` e arquivos que começam com ponto, como a seção 8 (linha 404) exige.
- Nomes de arquivo fixos (`16x9.mp4`, `9x16.mp4`, `1x1.mp4`, `thumb.jpg`, `qa_report.md`) preservados, como a seção 8 (linha 401) garante para a etapa 10.
