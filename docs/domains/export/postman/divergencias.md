# Divergências: FDD `export` × implementação (`router.py` / `service.py`)

Gerado em 2026-08-25, commit `f049d45`.

- FDD: `docs/domains/export/features/export-fdd.md` — seção 5 "Contratos públicos" (linhas 124-333) e matriz de erros da seção 6 (linhas 341-355).
- Contrato publicado (OpenAPI): **não existe neste repositório**. A busca por `openapi*.{yaml,yml,json}` com profundidade 3 a partir da raiz da worktree, dos repositórios irmãos do workspace e de `node_modules/@*/contracts*/` não retornou nada. O cruzamento abaixo é FDD × código implementado.
- Durante a geração desta coleção, o commit `5df89a7` acrescentou ao FDD uma seção **"Notas de implementação"** (linhas 514-558) em que a própria frente registra parte destas diferenças. Quando isso acontece, a linha da nota está citada na tabela. Importante: **as notas não corrigem o texto dos contratos da seção 5** — quem lê só a seção 5 continua vendo o contrato antigo, e é a seção 5 que esta coleção exercita.

| # | Severidade | O que o FDD diz | O que o código faz | Fontes |
| --- | --- | --- | --- | --- |
| 1 | **ALTA** | Contrato 9: `POST /export/reframe` responde **502** em "falha do CLI ao iniciar" (linha 318). A matriz da seção 6 fixa o padrão `CLI→502` (linha 339). | Nenhum caminho produz 502. `_call` traduz só `FileNotFoundError→404`, `ValueError→422`, `RuntimeError→409`. A falha do `hf.generate` acontece na thread do job, depois do 200 já devolvido, e vira `state=error`. A nota da linha 522 reconhece isso, mas **o contrato da linha 318 continua declarando 502**: o texto normativo e a nota se contradizem dentro do mesmo documento. | FDD linhas 318, 339, 522 · `router.py:30-39,85-90` · `service.py:445-453` |
| 2 | MEDIA | Contrato 8: `POST /export/reframe/cost` tem apenas **200** e **409 CLI não instalado** (linha 302). | `reframe_cost` também valida `aspect_ratio` (`ValueError → 422`) e exige o master (`FileNotFoundError → 404`). A nota da linha 555 confirma o comportamento ("`aspect_ratio` inválido continua 422 e master ausente continua 404"), mas o contrato da linha 302 não foi atualizado: dois status reais ficam invisíveis para quem só lê a seção 5. | FDD linhas 302, 555 · `service.py:424-432` |
| 3 | MEDIA | Contratos 2, 3, 5 e 6 listam 404 (master ausente), 409 (ffmpeg indisponível) e 422 (entrada inválida) **sem definir precedência** (linhas 178-180, 197-200, 228, 244). O critério da linha 416 afirma que `POST /render` sem master responde 404. | A ordem é fixa: `preview` valida o formato (422) antes de tudo; `preview`, `render`, `thumb` e `qa` checam ffmpeg (409) **antes** do master (404). Num ambiente sem ffmpeg, o critério da linha 416 falha — a resposta é 409, não 404. Ambiguidade do FDD resolvida em código sem registro. | FDD linhas 178-180, 416 · `service.py:234-241,253-258,296-301,327-332` |
| 4 | BAIXA | Exemplo do contrato 3 (linha 210) não traz o campo `mode`; o do contrato 9 (linha 328) não traz `formats`. | `start_render` passa `mode="render", formats=[...]` e `start_reframe` passa `mode="reframe", aspect_ratio=..., formats=[fmt]`; a `JobRegistry` espalha os extras no corpo do job. Campos aditivos, compatíveis com a garantia da seção 8 (linha 402). Não mencionado nas notas. | FDD linhas 210, 328 · `service.py:287,468` · `common/jobs.py:18` |
| 5 | BAIXA | Exemplo do contrato 1 (linha 164): `"thumb": {"file": "export/thumb.jpg", "t": 3.0}`. | O corpo real também traz `size`, e `t` vem de `export/.state.json` — arquivo interno criado pela frente. Reconhecido na nota da linha 516, que explica por que ele não vaza para `GET /list`. O exemplo do contrato 1 continua sem `size`. | FDD linhas 164, 516 · `service.py:38,66-78,186` |
| 6 | BAIXA | Seção 6, linha 346: 409 com a mensagem `"job em andamento"`. | A mensagem real vem da `JobRegistry`: "Já existe um trabalho em andamento para este projeto." Status igual, texto diferente — reconhecido na nota da linha 549. A coleção assere só o trecho "andamento". | FDD linhas 346, 549 · `common/jobs.py:17` |
| 7 | BAIXA | Assinatura da seção 5, linha 142: `_filter_for(fmt: str, width: int, height: int)`. | A implementação é `_filter_for(fmt, width, height, vcodec="")` — o codec decide o caminho `-c copy` do 16:9. Parâmetro com default, sem quebra; reconhecido na nota da linha 527. Função interna, não observável por HTTP. | FDD linhas 142, 527 · `service.py:138` |
| 8 | BAIXA | Modelo do `qa_report.md` (linhas 265-266): cabeçalho de 2 linhas terminando em "publique mesmo que o primeiro fique **ruim**". | O gerado tem 3 linhas de cabeçalho e termina em "publique mesmo que o primeiro fique **fraco**". Divergência puramente textual; nenhuma checagem depende dela. Não mencionada nas notas. | FDD linhas 265-266 · `service.py:390-396` |
| 9 | BAIXA | Seção 6, linha 348: `t` fora de `[0, duração]` → 422. | `_valid_t` só aplica o limite superior quando `duration` é verdadeiro: com um master de duração 0 (arquivo degenerado) qualquer `t` positivo passa. Não mencionado nas notas. | FDD linha 348 · `service.py:148-155` |
| 10 | BAIXA | Tabela de filtros da seção 4 (linhas 82-83): `crop=ih*9/16:ih:(iw-ih*9/16)/2:0`, expressão avaliada pelo ffmpeg. | O crop é calculado em Python (`_crop_rect`) e emitido com números concretos, o que também define o comportamento quando o master é mais estreito que a proporção alvo. Reconhecido na nota da linha 534. O retângulo devolvido pelo `POST /preview` é o mesmo que vai para o filtro — a coleção assere exatamente isso. | FDD linhas 82-83, 534 · `service.py:110-130` |

## Corrigidas durante esta auditoria (commit `f049d45`)

Duas divergências levantadas na primeira passagem foram tratadas pela frente antes do fecho deste
relatório, com teste de regressão. Ficam registradas porque o contrato da seção 5 as previa e o
código não cumpria:

| Severidade original | O que o FDD dizia | O que o código fazia | Correção |
| --- | --- | --- | --- |
| MEDIA | Contrato 1 (linha 152) e contrato 7 (linha 286): 200 **sempre** que o projeto existe. | `GET /status` e `GET /list` chamavam o ffprobe direto; um mp4 corrompido ou de 0 byte em `export/` virava **500**. | `_safe_probe` (`service.py`) captura a falha do ffprobe e devolve a entrada sem os campos de mídia, com aviso no log. Nota acrescentada ao FDD (linha 556). |
| MEDIA | Contrato 9 (linha 318): `aspect_ratio` fora de `{"9:16","1:1"}` → **422**. | As duas rotas de reframe checavam `hf.available()` antes do corpo, então em máquina sem o CLI a resposta era **409**, nunca 422. | `_reframe_preflight` (`router.py`) fixa a ordem projeto (404) → corpo (422) → CLI (409). Nota acrescentada ao FDD (linha 561). |

As asserções da coleção já refletem o comportamento corrigido: os dois requests de
`aspect_ratio` inválido esperam 422 sem ramificação por ambiente, e o `GET /list` pós-render
aceita entradas sem metadados de mídia.

## Sem divergência (verificado item a item)

- As 9 rotas da seção 5 existem no router com método e caminho exatos, sob `/api/projects/{pid}/export/...`; `studio/app.py:63` inclui o router do plugin sem `prefix` adicional.
- 404 para `pid` inválido ou inexistente em todas as 9 rotas, pelo handler de `KeyError` do núcleo (`studio/app.py:25-27`), como a seção 6 (linha 343) descreve. As duas rotas de reframe chamam `project_dir` antes de checar o CLI justamente para isso.
- Corpos de requisição batem com os exemplos: `{format, t}`, `{formats: [...]}`, `{t}`, `{aspect_ratio}`; os modelos Pydantic estão no router, como a linha 126 afirma.
- Nomes de checagem do QA (`exists`, `resolution`, `duration`, `vcodec`, `audio`, `size`) batem com a linha 280, e `verdict` é `OK`/`ATENCAO` derivado delas.
- `GET /export/list` ignora `previews/` e arquivos que começam com ponto, como a seção 8 (linha 404) exige.
- Nomes de arquivo fixos (`16x9.mp4`, `9x16.mp4`, `1x1.mp4`, `thumb.jpg`, `qa_report.md`) preservados, como a seção 8 (linha 401) garante para a etapa 10.
- Um job por projeto para render e reframe na mesma chave `pid` (linha 364), com 409 da `JobRegistry`.
