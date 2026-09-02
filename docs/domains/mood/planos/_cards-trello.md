# Cards a criar no Trello (pendente de acesso)

Board: `senhordatecnologia` (`BDwwpWPU`, id `65e781cd1a65f6c4e84c164a`) · lista **DD · To Do**
(conforme `docs/dd.md`). Os quatro cards são independentes entre si na criação, mas têm
dependência de execução: 01 ← 03 ← 04, e 02 depende de 01.

---

## Card 1 — `ADH-OS-20260902-01` · Tela de mood boards dispara as skills `mood_`

**Descrição:**
Rodar a cadeia `mood_` (vibe → DNA → prancha) a partir da tela de mood boards, usando a
assinatura do Claude CLI que já existe (`studio/common/prompter.py`), sem chave de API.

Plano completo: `docs/domains/mood/planos/plano-01-tela-chama-orquestrador.md`

Ponto crítico: o `prompter._run()` atual **não serve** (180 s, `--allowedTools Read`). Precisa
de um runner irmão com Bash/Write/Read, `cwd` na raiz e timeout de minutos. O **passo 1 é um
spike** para confirmar que a skill roda em modo `claude -p`; se não rodar, o plano muda inteiro.

**Checklist:**
- [ ] Spike: `claude -p "/mood_orquestrador --params …"` roda? quais `--allowedTools` mínimos?
- [ ] Decidir D1 (onde a corrida grava) e D5 (ADR do modo de execução com escrita)
- [ ] FDD + matriz de erros do runner
- [ ] `studio/common/skill_runner.py` + testes com fake do CLI
- [ ] Endpoints `mood-run/{options,estimate,job,result}` + `POST mood-run`
- [ ] Front: painel, estimativa de downloads antes de confirmar, polling, galeria
- [ ] ADR + `make verify` + PR (`ft-pr`)

**Labels:** `mood`, `studio`, `[extensão]`

---

## Card 2 — `ADH-OS-20260902-02` · Refino do mood com Higgsfield, versionado

**Descrição:**
Refinar um mood existente via CLI da Higgsfield gerando **uma versão nova**, sem apagar a
anterior. A nova aparece completa na tela (imagens, paleta, prompt) para o usuário escolher ou
manter a antiga.

Plano completo: `docs/domains/mood/planos/plano-02-refino-higgsfield-versionado.md`

**BLOQUEIO DE ENTRADA:** o arquivo `.txt` do usuário com o passo a passo do moodboard via
Higgsfield **não foi localizado no repositório**. O plano foi escrito a partir de
`docs/plano/plano-higgsfield.md` §"4 · Mood", `studio/common/multishot.py` e
`studio/higgsfield.py`. Reconciliar com o `.txt` antes de implementar — se divergir, o `.txt`
ganha.

Decisão central: hoje `moodboards/<mbid>/` é diretório plano e **não tem conceito de versão**.
Recomendação: `versoes/v<N>/` + ponteiro `versao_ativa`, com leitura compatível (board sem
`versoes/` = `v1` implícito).

**Checklist:**
- [ ] Localizar e ler o `.txt` do usuário; reconciliar o plano
- [ ] ADR do versionamento de mood board (relacionar com ADR-013)
- [ ] FDD + matriz de erros da ponte (CLI ausente, deslogado, timeout, custo, parcial)
- [ ] Leitura compatível (`v1` implícito) + teste que falha se a versão anterior mudar de hash
- [ ] `cost` obrigatório antes de gerar + gate no front
- [ ] Job de refino, escrita atômica da versão, paleta recalculada
- [ ] Faixa de versões + troca de ativa no front
- [ ] `make verify` (com fake, sem gastar crédito) + PR (`ft-pr`)

**Labels:** `mood`, `higgsfield`, `[extensão]`

---

## Card 3 — `ADH-OS-20260902-03` · Painel paginado de seleção das fotos de vibe

**Descrição:**
Painel na tela de mood boards para ver o resultado do `mood_vibe_scout`: paginação com **até 20
fotos por página**, marcação múltipla, e salvar → copia para **fotos escolhidas**. É dessas
escolhidas que o orquestrador (card 01) é chamado.

Plano completo: `docs/domains/mood/planos/plano-03-painel-selecao-pinterest.md`

Buracos: nada serve `fotos_vibe/` ao browser hoje (só `MOODBOARDS_DIR` e `PROJECTS_DIR` estão
montados); o `select` existente tem teto de 8 e semântica de board, não de peneira; e não há
paginação em lugar nenhum da tela.

**Checklist:**
- [ ] Decidir D1: mover `fotos_vibe`/`fotos_escolhidas` para a raiz já montada (recomendado) ou criar rota
- [ ] FDD com contrato de paginação (`page`, `per_page` máx. 20, `total`, `pages`)
- [ ] `studio/moodboards/vibes.py` + testes (bordas de paginação, duplicata por hash, índice corrompido)
- [ ] Endpoints `/api/vibes`, `/api/vibes/facets`, `/api/vibes/select`, `/api/escolhidas`
- [ ] Front: grade de 20, filtro por vibe, seleção persistente entre páginas, painel de escolhidas
- [ ] Salvar **copia** (não move) e reporta duplicata
- [ ] `make verify` + PR (`ft-pr`)

**Labels:** `mood`, `studio`, `[extensão]`

---

## Card 4 — `ADH-OS-20260902-04` · Busca do Pinterest parametrizável e exposta ao front

**Descrição:**
Restringir a busca (assunto, tipo, exclusões, orientação, tamanho mínimo) para não voltar lixo,
mantendo o comportamento atual quando nada é passado. Os parâmetros são servidos por um
**manifesto** que o frontend usa para montar o formulário sozinho.

Plano completo: `docs/domains/mood/planos/plano-04-params-das-skills-no-front.md`

Evidência do problema, colhida na corrida de 2026-09-02: `school backpack … still life blue
neon light` devolveu stock em fundo branco; `japanese school uniform night street fashion
photography` (longa demais) devolveu **zero** resultados.

**Checklist:**
- [ ] Fechar o vocabulário dos parâmetros com o usuário (é contrato de UI)
- [ ] `SKILL.md` + `catalogo.md`: novos parâmetros e regra de query sob restrição
- [ ] `pinterest_vibes.py`: filtros no download + **redução automática de query que volta vazia** + testes sem rede
- [ ] `GET /api/skills/mood/params` (manifesto) + teste que falha se skill e manifesto divergirem
- [ ] Front: formulário gerado do manifesto, "avançado" recolhido, vazio = default
- [ ] Corrida de validação antes/depois nos dois casos de lixo acima
- [ ] `make verify` + PR (`ft-pr`)

**Labels:** `mood`, `skills`, `[extensão]`
