# Plano 02 — Refinar o mood com a Higgsfield, versionando sem apagar

Task-Id: `ADH-OS-20260902-02`
Status: **plano** — nada implementado.
Data: 2026-09-02

---

## 1. O que se quer

Depois que um mood existe, poder mandá-lo para a Higgsfield via CLI e receber **um mood novo**,
sem destruir o anterior. O novo nasce completo (imagens, paleta, prompt) e aparece na tela já
atualizado, para o usuário **escolher ou não** — a versão anterior continua intacta como backup.

## 2. Fonte da verdade — pendência declarada

O usuário mencionou um **arquivo .txt com o passo a passo do moodboard via Higgsfield**. Ele
não foi localizado no repositório: o único `.txt` em `processo_manual/moodboard/` é
`mood_board_draft.txt`, que contém a árvore de decisão das skills, não o fluxo Higgsfield.

Este plano foi escrito a partir das fontes que **estão** no repo:
- `docs/plano/plano-higgsfield.md` §"4 · Mood" — `nano_banana_2 --image-references refs/*.jpg
  --prompt "<mood>" --count 4 --resolution 1k`, ×2 prompts, paleta extraída por Python;
- `studio/common/multishot.py` — já faz exatamente esse tipo de chamada (`DEFAULT_MODEL =
  "nano_banana_2"`, `image-references`, `count`), com job assíncrono;
- `studio/higgsfield.py` — ponte oficial (`cost`, `generate --wait`, `model_params`,
  `adapt_params`, `download`).

**Antes de implementar, reconciliar este plano com o .txt do usuário.** Se o .txt divergir,
ele ganha, e a diferença vira nota no FDD.

## 3. O que já existe (verificado)

| Peça | Onde | Serve para |
|---|---|---|
| Ponte Higgsfield | `studio/higgsfield.py` | única via permitida (ADR): subprocess + `--json`. Nunca `api.higgsfield.ai`, nunca UI. |
| Custo antes de gerar | `higgsfield.cost(model, params)` | o gate de crédito |
| Geração N variações a partir de uma imagem | `studio/common/multishot.py:start_generate` | **o precedente mais próximo do que se quer** |
| Boards no disco | `moodboards/<mbid>/moodboard.json` | onde a versão vive |
| Paleta | `studio/common/palette.py` + `_rederive_palette` | recalcular a paleta do mood novo |
| Prompt do board | `service.generate_prompt` | o prompt que alimenta a geração |

## 4. O buraco: hoje um board não tem versões

`moodboards/<mbid>/` é um diretório plano. Não existe conceito de "versão do mood", então
"gerar um novo sem apagar o antigo" **não tem onde morar**. Essa é a decisão central do plano.

## 5. Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D1 | Onde vive a versão | (a) `moodboards/<mbid>/versoes/v<N>/` com ponteiro `versao_ativa` no `moodboard.json`; (b) board novo por refino | **(a)** — mantém a linhagem visível e o backup automático; (b) espalha a biblioteca |
| D2 | O que entra numa versão | imagens, `palette.json`, prompt usado, params Higgsfield, custo cobrado, origem (`v2 ← v1`) | tudo isso, num `versao.json` |
| D3 | Quem é o "mood atual" | `versao_ativa` no `moodboard.json` | **sim** — trocar de versão é mudar um ponteiro, operação barata e reversível |
| D4 | Modelo e params | `nano_banana_2` + `--image-references` das imagens da versão de origem | seguir `plano-higgsfield.md` e `multishot.py`; params passam por `adapt_params` |
| D5 | Gate de crédito | `cost` antes, confirmação explícita | **obrigatório** — nunca gerar sem o usuário ver o número |
| D6 | ADR | versionamento de mood board | **sim** — muda o contrato de `moodboards/<mbid>/` (relacionar com ADR-013) |

## 6. Escopo

### Entra
- **Migração de leitura compatível**: board sem `versoes/` continua funcionando e é lido como
  `v1` implícito. Nada de migração destrutiva no disco.
- `studio/moodboards/service.py`: `list_versions`, `create_version_from(mbid, origem, params)`,
  `activate_version`, `version_detail`; `_rederive_palette` aplicada à versão nova.
- Endpoints em `studio/moodboards/router.py`:
  - `GET  /api/moodboards/{mbid}/versions`
  - `POST /api/moodboards/{mbid}/refine/cost` → custo em crédito **antes**
  - `POST /api/moodboards/{mbid}/refine` → job assíncrono (`JobRegistry`, chave `refine:<mbid>`)
  - `GET  /api/moodboards/{mbid}/refine/job`
  - `POST /api/moodboards/{mbid}/versions/{v}/activate`
- Front (`studio/web/moodboards.js`): faixa de versões (v1, v2, v3…) com a ativa marcada,
  botão "Refinar com Higgsfield" mostrando **o custo antes**, progresso por polling, e a versão
  nova aparecendo **já montada** ao lado da anterior, com "usar esta" / "manter a anterior".
- Testes com **fake do CLI Higgsfield** (sem rede, sem crédito): sucesso, CLI ausente, não
  logado, custo acima do saldo, job concorrente, geração parcial.
- FDD + atualização do HLD de `mood` e de `higgsfield`; ADR de versionamento.

### Não entra
- Apagar, sobrescrever ou mover a versão anterior — **nunca**.
- Automatizar a UI da Higgsfield ou chamar a API HTTP direto.
- Gerar sem confirmação de custo.
- Refino em lote de vários boards.

## 7. Passos

1. Localizar e ler o `.txt` do usuário; reconciliar §2 e registrar divergências.
2. ADR do versionamento (D1–D3) — é o que trava o formato no disco.
3. FDD com a matriz de erros da ponte (CLI ausente, não logado, timeout, custo, parcial).
4. Leitura compatível (`v1` implícito) + testes — **antes** de qualquer escrita nova.
5. `cost` + endpoint de custo + gate no front.
6. Job de refino + escrita da versão + paleta recalculada.
7. Faixa de versões e troca de ativa no front.
8. `make verify`, QA, PR pelo gate `ft-pr`.

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Perder o mood anterior | versão nova **só escreve em diretório novo**; teste que falha se `v<N-1>` mudar de hash |
| Queimar crédito sem querer | `cost` obrigatório + confirmação; fake nos testes |
| Job parcial deixa versão quebrada | escrever em `.tmp` e promover atômico (`studio/common/atomic.py`) |
| Divergir do .txt do usuário | passo 1 é bloqueante para a implementação |
| Catálogo de modelos mudar | já há `model_params` + `adapt_params` com cache |

## 9. Critérios de aceite

- Refinar um board cria `v2` e **`v1` continua byte-idêntico** (teste verifica hash).
- A tela mostra o custo em crédito antes e não gera sem confirmação.
- A versão nova aparece completa: imagens, paleta recalculada, prompt e params registrados.
- Trocar a versão ativa é reversível e não apaga nada.
- Com o CLI Higgsfield ausente ou deslogado, a tela explica e não quebra.
- `make verify` verde; nenhum teste gasta crédito ou toca a rede.
