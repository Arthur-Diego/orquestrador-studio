# Triagem, severidade, dono e revalidação incremental (qa-studio)

Toda decisão desta página é determinística: aplica-se a regra, executa-se e reporta-se em uma linha
`[decisão] <o que> — <regra> (<evidência>)`. O que não tem regra aqui e não está no `<HARD-GATE>` da
skill resolve-se pela opção mais conservadora (não corrigir; card aberto) e vira lacuna no resumo.

## 1. O que vira apontamento

| Sinal | Vira apontamento? |
| --- | --- |
| Caso funcional `FALHA` | Sim |
| Caso `BLOQUEADO` por limitação do modo offline (Pinterest, `--real`) | Não — ressalva no relatório |
| Caso `BLOQUEADO` por ambiente (Chromium, ffmpeg, servidor caiu) | Não — soft fail de ambiente (watchdog) |
| `pageerror` / `console.error` em qualquer tela | Sim (MEDIA; ALTA se a tela não renderiza) |
| `console.warning` | Sim, BAIXA, um apontamento por mensagem distinta |
| HTTP ≥ 500 vindo da UI ou da auditoria | Sim, ALTA |
| HTTP 4xx **esperado** pelo fluxo (validação, 404 de estado vazio) | Não |
| HTTP 4xx **não tratado** pela UI (sem toast/mensagem) | Sim, MEDIA |
| Auditoria visual: overflow, imagem quebrada, botão sem nome, campo sem rótulo, fora do viewport | Sim, BAIXA (MEDIA se impede uso: botão inalcançável) |
| Inspeção visual do agente sobre o print (alinhamento, contraste, texto sobreposto, inconsistência entre telas/temas) | Sim, BAIXA — sempre com o print como evidência e descrição verificável |
| Timer órfão (requests da tela anterior após navegar) | Sim, MEDIA |
| Latência > 5 s em GET | Sim, MEDIA |
| Traceback/ERROR em `server.log` | Sim, ALTA se ligado a 5xx; MEDIA caso contrário |
| Newman `contrato` (app diverge da coleção) | Sim — dono `backend` se o app está errado, `docs` se a coleção está desatualizada (decidir pelo FDD do domínio: o FDD manda) |
| Newman `fixture` / `legado` | Não — AVISO |
| Texto/documentação inconsistente com o app (ex.: "11 etapas" vs 10) | Sim, BAIXA, dono `docs` ou `frontend` (onde está o texto) |
| Chamada a binário real em modo offline (`fakes.log` vazio para uma geração) | Sim, ALTA (dono `backend`) |

Um apontamento por causa-raiz: vários casos falhando pelo mesmo defeito → um AP com todos os casos
de origem listados.

## 2. Severidade

- **ALTA**: fluxo principal da etapa quebrado; dado incorreto persistido; artefato perdido; 5xx;
  ação destrutiva sem confirmação; tela que não abre.
- **MEDIA**: fluxo alternativo/estado com defeito; erro sem mensagem amigável; job que não termina
  ou não atualiza a UI; latência; timer órfão; regressão de acessibilidade que impede uso por teclado.
- **BAIXA**: visual, texto, rótulo, contraste, alinhamento, inconsistência de documentação.

## 3. Dono

| Onde está a causa | Dono |
| --- | --- |
| `studio/web/**`, `studio/etapas/<id>/view.html|view.js` | frontend |
| `studio/etapas/<id>/router.py`, `studio/<dom>/service.py`, `studio/common/**`, `studio/app.py`, `studio/higgsfield.py` | backend |
| `README.md`, `docs/**`, textos em HTML que só citam docs | docs |

Quando frontend e backend discordam de um contrato, o **FDD do domínio** decide quem está errado
(`docs/domains/<dom>/features/*.md`). Sem FDD: a aula/plano (`docs/plano/`) decide. Sem nenhum dos
dois, é ambiguidade → HARD-GATE 3 (decisão humana).

## 4. Destino

| Condição | Destino |
| --- | --- |
| Defeito de código, correção local, não muda método do curso nem contraria ADR | **Corrigir nesta rodada** (Passo 8) |
| Correção muda o que a aula ensina (gate de fidelidade do `CLAUDE.md`) ou contraria ADR em `docs/adrs/generated/` | **HARD-GATE 3** — card com "Precisa de decisão", sem correção |
| Divergência só de documentação | Corrigir a doc na mesma branch (dono `docs`) |
| Coleção Postman desatualizada (FDD confirma o app) | Atualizar a coleção na mesma branch |
| Ambiente/ferramenta | Soft fail — relatório, sem card de produto |
| Sobreviveu a 2 rodadas seguidas sem progresso | **HARD-GATE 4** — card fica aberto com diagnóstico |
| `--sem-correcao` | Card apenas |

"Muda método do curso" = altera entradas, saídas, ordem ou regra de qualidade que a aula define
para a etapa (ver `studio/steps.py` → aula; `docs/plano/*.md`). Corrigir um botão que não chama a
API certa **não** muda método; trocar "1 prompt × grid de 4" por outra coisa muda.

## 5. Ordem de correção

ALTA → MEDIA → BAIXA; dentro da mesma severidade, backend antes de frontend (a UI pode depender do
contrato); docs por último. Uma correção por vez, sequencial, na mesma branch.

## 6. Revalidação incremental (o que reexecutar depois de corrigir)

Premissa: **o que passou continua valendo** — só se reexecuta o que a correção pode ter mudado.
Regra determinística a partir do `git diff --name-only <base>..HEAD` dos commits de correção:

| Arquivo alterado | Reexecutar |
| --- | --- |
| `studio/etapas/<id>/**` ou `studio/<id>/**` | casos FALHA da rodada + **todos** os casos e auditoria (light+dark, 1 viewport) da tela `<id>` |
| `studio/common/**`, `studio/app.py`, `studio/steps.py`, `studio/higgsfield.py`, `studio/config.py` | casos FALHA + auditoria de **todas** as telas + `api_audit.py` + `make verify` |
| `studio/web/app.js`, `studio/web/ui.js`, `studio/web/*.css`, `index.html` | casos FALHA + casos `shell`/`overview` + auditoria de **todas** as telas (light+dark) |
| `studio/web/moodboards.js` / `creditos.js` / `multishot.js` | casos FALHA + casos da tela correspondente (+ `mood` e `storyboard` para multishot) |
| `studio/moodboards/**` / `studio/creditos/**` | idem acima + `api_audit.py` |
| `docs/**`, `README.md`, `scripts/qa/**` (só cenários) | casos FALHA relacionados; nada mais |
| Qualquer alteração | `make verify` (ruff + pytest) sempre |

Além da regra, a skill **pode** ampliar (nunca reduzir) a revalidação quando julgar necessário —
ex.: correção em `service.py` de uma etapa que outra etapa consome (contratos em
`docs/domains/studio/waves/wave-1.md`): incluir a tela consumidora. Registrar sempre:
`[decisão] revalidação: casos <ids> + telas <ids> — regra "<linha da tabela>" (diff: <arquivos>)`.

Regressão completa (todas as telas, todos os casos, dois temas, dois viewports) só na rodada 1 ou
quando a regra acima mandar; nunca "por garantia".

## 7. Quando parar o loop

Parar quando qualquer um valer: (a) zero apontamentos com destino "corrigir" abertos; (b) atingiu
`--rodadas`; (c) a rodada não corrigiu nenhum apontamento (sem progresso). Apontamentos restantes
ficam em cards abertos com o diagnóstico mais recente comentado.
