# Divergências: FDD `mood-run` × contrato implementado

Gerado em **2026-09-02**, worktree `feature/adh-os-20260902-01-mood-run`, commit base **`753b99b`**.

- **FDD (spec normativa):** `docs/domains/mood/features/mood-run-fdd.md` — seção **5**
  "Contratos públicos" (linhas 165-313, rotas nas linhas 195, 217, 232, 257, 263) e a matriz de
  erros da seção **6** (linhas 328-351).
- **Implementação conferida:** `studio/moodboards/mood_run_router.py` (as cinco rotas e os
  modelos `EstimateReq`/`RunReq`), `studio/moodboards/mood_run.py` (validadores e as cinco
  operações), `studio/common/skill_runner.py` e o handler global de `KeyError` do núcleo
  (`studio/app.py`).
- **Contrato publicado (OpenAPI estático): não existe neste repositório.** Busca por
  `openapi*.{yaml,yml,json}` com profundidade 3 na raiz da worktree, nos repositórios irmãos do
  workspace (`../contracts-*`, `../*-contracts`) e em `node_modules/@*/contracts*/`: nenhum
  resultado. O FDD também não cita caminho de contrato nas seções 5 e 8. O único contrato
  publicado é o **`/openapi.json` que o FastAPI gera em runtime a partir do próprio código** — ele
  foi inspecionado e as cinco rotas estão lá (`GET …/options`, `POST …/estimate`, `POST …/mood-run`,
  `GET …/job`, `GET …/result`), então **não há nenhuma rota do FDD faltando no contrato nem rota do
  contrato ausente do FDD**. Por isso o cruzamento abaixo é **FDD × implementação**, feita por
  execução real com `TestClient` sobre `studio.app`, `STUDIO_MOODBOARDS` isolado, sem rede e sem
  `claude` (ADR-008) — nenhuma corrida foi disparada.

**Placar: 0 ALTA · 4 MEDIA · 3 BAIXA.**

| # | Sev. | O que o FDD diz | O que o contrato/implementação faz | Fonte |
| --- | --- | --- | --- | --- |
| D1 | MEDIA | `POST …/estimate` recebe `{ "objetivos": [...], "board": 8, "n": 3 }` — os três campos aparecem sempre no exemplo de corpo (linhas 220-221), e a lista de erros (linha 227-228) só fala de valor fora do piso | `EstimateReq` declara `board: int \| None = None` e `n: int \| None = None`; ausentes ou `null`, caem nos **defaults do manifesto** (8/3) e a rota responde 200. O corpo `{}` responde 422 pelo objetivo vazio, não por `board`/`n` | FDD linhas 219-228 × `mood_run_router.py` `EstimateReq` e `mood_run_estimate` |
| D2 | MEDIA | A lista de erros de `POST …/mood-run` (linhas 253-255) e a matriz da seção 6 **não têm nenhuma linha para `fundo` inválido** | `mood_run._validar_fundo` levanta `ValueError` → **422** `"fundo inválido: <x>. Aceitos: escuro, claro"`. É um 422 real, não documentado no FDD | FDD linhas 253-255 e 328-351 × `mood_run.py::_validar_fundo` |
| D3 | MEDIA | `GET …/result` é apresentado com `semente`, `gate`, `downloads` e `boards` como se fossem contrato do servidor (linhas 265-279) | O servidor devolve `{**_run.json, "boards": [...]}`: só `boards` e as três `*_url` são **nossas**. `semente`, `gate` e `downloads` vêm do produtor externo e **somem sem erro** se a skill não os gravar — a validação de shape é apenas `dict` + `boards: list` (o próprio FDD diz isso na linha 284 e no risco R1, mas o exemplo da linha 266 sugere garantia). Cliente que assumir esses três campos quebra em runtime | FDD linhas 263-285 × `mood_run.py::read_result` |
| D4 | MEDIA | Os erros declarados por rota são 404, 409, 422 e 502 (linhas 215, 228, 253-255, 261, 283-285) | O **`/openapi.json` gerado pelo FastAPI declara, para as cinco rotas, apenas `200` (objeto genérico, sem schema de campos) e `422` com o `HTTPValidationError` do próprio FastAPI** — nenhum 404, 409 ou 502, porque as rotas não passam `responses=`. Pior: o 422 desta feature devolve `detail` **string** (`HTTPException(422, str(e))`), enquanto o schema publicado promete `detail` como **lista** de objetos `{loc,msg,type}`. Quem gerar cliente a partir do openapi vai tipar errado o corpo de erro. **Não é ALTA** porque os quatro status existem e foram verificados por execução; o que falta é a declaração | FDD seção 5 × `/openapi.json` em runtime |
| D5 | BAIXA | E7 (linha 338): `mbid` inexistente → **404** "pelo handler global de `KeyError` do núcleo" | O status está correto, mas a mensagem literal é **`"projeto não encontrado: <mbid>"`** — e mood board **não é projeto** (a biblioteca é global, ADR-013). O próprio `mood_run_router.py` registra isso em comentário ao justificar o `FileNotFoundError` do `/result`. Ruído de UX/documentação, não de comportamento | FDD linha 338 × `studio/app.py` (handler de `KeyError`) |
| D6 | BAIXA | E12 (linha 343): caminho com `"` → `ValueError` de `skill_runner.build_prompt` → **422** | Pelo caminho HTTP, `_validar_foto` recusa antes (o arquivo com aspas precisaria existir **dentro** de `_escolhidas/`), com a mensagem de E10. O status final continua 422; a origem e a mensagem são outras. `build_prompt` só é alcançado com um arquivo realmente escolhido cujo nome contenha `"` | FDD linha 343 × `mood_run.py::start_run` (ordem `_validar_foto` → `build_prompt`) |
| D7 | BAIXA | §5.2 fixa os pisos em prosa: "`board < 4`, `n < 1`" (linha 228) | A implementação lê os pisos do manifesto (`limites()` → `apresentacao.minimo`) e nunca de literal. Hoje batem (4 e 1); se a frente 04 mexer no manifesto, o texto do FDD envelhece sozinho. A coleção assere o piso **vindo de `GET /options`**, não o número escrito no FDD | FDD linha 228 × `mood_run.py::_validar_numeros` + `skills_params.py` linhas 210 e 221 |

## O que foi conferido e **não** divergiu

- As cinco rotas existem, com os métodos e caminhos exatos da seção 5.
- `GET /options`: `gate` fixo em `auto`, `objetivos` = `[ambiente, campanha, produto, personagem]`,
  `agregador` = `todos`, `fundos` = `[escuro, claro]`, `defaults` = `{board: 8, n: 3, fundo: escuro}`,
  `limites` = `{board_min: 4, n_min: 1}`, `saida` terminando em `/mood_run` dentro do board,
  `timeout_s` = 1800, `job` com `state`.
- `POST /estimate`: `todos --board 8 --n 3` = **84 downloads / 7 consultas / 4 objetivos**
  (critério A2, FDD linha 230), e `["ambiente","produto"] 8/3` = **42**, idêntico ao exemplo da
  linha 223. A `formula` volta na resposta.
- Precedência **404 antes de 422 e de 409** em `/estimate` e em `/mood-run` (E7).
- 422 de E9 listando os aceitos, de E11 citando o piso, e de E8/E10 falando da foto escolhida.
- 404 de E13 com a mensagem própria `"nenhuma corrida de mood neste board ainda"`, distinta do 404
  de board inexistente.
- `GET /job` com as chaves-base (`done`, `total`, `added`, `error`, `log`) sempre presentes e
  `state: "idle"` quando nunca rodou.
