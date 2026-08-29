# Template do relatório de uma rodada de QA (determinístico)

Preencha TODAS as seções, na ordem, sem acrescentar seções novas. Célula sem dado recebe `—`.
Salve em `docs/qa/reports/<AAAA-MM-DD>-<run-id>/relatorio.md` e comente o caminho no card-pai
da rodada. Prints e JSONs ficam em `.qa/runs/<run-id>/` (gitignored) — cite o caminho relativo.
Cada rodada de correção/revalidação ACRESCENTA uma subseção em "8. Histórico de rodadas"; as
seções 3–6 refletem sempre o estado mais recente (casos revalidados sobrescrevem o resultado).

```markdown
# QA E2E — <escopo: todas as telas | telas X, Y> — <AAAA-MM-DD> — <run-id>

## 1. Identificação

| Campo | Valor |
| --- | --- |
| Card-pai (Trello) | <URL> |
| Task-Id | ADH-OS-<YYYYMMDD>-<seq> |
| Branch / worktree | fix/qa-<data> · <caminho> |
| Commit base (develop) | <sha curto> |
| Modo | offline (fakes) \| real |
| Base URL | http://127.0.0.1:<porta> |
| Telas pedidas / executadas | <lista> / <lista> |
| Rodadas executadas | <n> de <--rodadas> |
| Executado por | qa-studio |

## 2. Ambiente (saída real do check-env.sh)

```text
<colar a saída integral>
```

## 3. Casos executados

| # | Tela | Cenário | Resultado | Evidência |
| --- | --- | --- | --- | --- |
| C-REFS-01 | refs | <título do caso> | PASSA / FALHA / BLOQUEADO | <evidencias/… ou trecho de detalhe> |

Regras: um caso por linha, na ordem de `resultados.json`; `BLOQUEADO` exige o motivo na
evidência; `FALHA` exige o `detalhe` do caso.

## 4. Auditoria automática por tela (tema × viewport)

| Tela | Tema | Viewport | Problemas | Console/pageerror | HTTP ≥ 400 | Print |
| --- | --- | --- | --- | --- | --- | --- |
| refs | light | 1440x900 | <— ou lista> | <— ou n> | <— ou lista> | evidencias/light-1440x900-refs.png |

Timers órfãos: <— ou `{tela: [urls]}`>.

## 5. Inspeção visual (feita pelo agente sobre os prints)

| Tela | Tema | Observação | Severidade | Print |
| --- | --- | --- | --- | --- |
| <tela> | <tema> | <o que está errado, em uma frase verificável> | ALTA / MEDIA / BAIXA | <caminho> |

## 6. Backend

### 6.1 Auditoria de API (api_audit.py)

| Grupo | Item | Resultado | Detalhe |
| --- | --- | --- | --- |
| openapi | <item> | PASSA / FALHA / AVISO | <—> |

### 6.2 Newman

| Coleção | Requests | Falhas | Classificação | Observação |
| --- | --- | --- | --- | --- |
| docs/domains/<d>/postman/<arquivo> | <n> | <n> | contrato \| fixture \| legado | <—> |

Classificação: `contrato` = o app diverge do que a coleção afirma (vira apontamento);
`fixture` = a coleção pressupõe um estado que o seed não tem (AVISO, não apontamento);
`legado` = domínio sem plugin (não executada).

## 7. Apontamentos

| # | Severidade | Dono | Tela/rota | Descrição objetiva | Caso de origem | Destino | Card |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AP-01 | ALTA / MEDIA / BAIXA | frontend / backend / docs | <tela ou endpoint> | <uma frase verificável> | C-… | corrigido (commit <sha>) / card aberto / decisão humana | <URL> |

Regras de severidade: ALTA = fluxo principal quebrado, dado incorreto, 5xx, perda de artefato;
MEDIA = fluxo alternativo/estado com defeito, erro sem mensagem amigável, latência > 5 s;
BAIXA = visual, texto, acessibilidade, inconsistência de documentação.

## 8. Veredito

- Casos: <X> PASSA, <Y> FALHA, <Z> BLOQUEADO de <N>.
- Apontamentos: <A> ALTA, <M> MEDIA, <B> BAIXA — <c> corrigidos, <k> em cards abertos, <h> aguardando decisão humana.
- Situação: <APROVADA | APROVADA COM RESSALVAS | REPROVADA> — regra: REPROVADA se houver ALTA
  sem correção; COM RESSALVAS se houver MEDIA/BAIXA abertas; APROVADA se tudo corrigido/validado.
- PR: <URL ou "sem alterações de código">.

## 9. Histórico de rodadas

### Rodada 1 — <data hora>
- Executado: <telas>, <n> casos, auditoria de API, newman.
- Apontamentos abertos: AP-01 … AP-NN.

### Rodada 2 — <data hora> (correção + revalidação)
- Corrigidos: AP-xx (commit …), …
- Revalidado: casos <ids> + telas <ids> (raio de impacto: <arquivos alterados → telas>) — decisão:
  `[decisão] regressão parcial — diff só toca studio/etapas/refs/*`.
- Ainda abertos: …
```
