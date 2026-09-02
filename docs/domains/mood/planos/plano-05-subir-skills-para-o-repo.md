# Plano 05 — Subir as skills `mood_*` para o repositório

Task-Id: `ADH-OS-20260902-05`
Status: **plano** — nada commitado.
Data: 2026-09-02

---

## 1. O que se quer

As quatro skills `mood_*`, o agente, os scripts e a documentação existem só na working tree.
Levar isso para `develop` **sem arrastar junto** 25 MB de imagem de terceiro.

## 2. Inventário verificado

### Entra

| Caminho | Tam. | Arq. | O que é |
|---|---|---|---|
| `.claude/skills/mood_orquestrador/` | 16K | 1 | porta de entrada da cadeia |
| `.claude/skills/mood_vibe_scout/` | 52K | 5 | entrevista + coleta (inclui `scripts/pinterest_vibes.py`) |
| `.claude/skills/mood_visual_dna/` | 48K | 10 | DNA visual (inclui `scripts/validate_visual_dna.py`) |
| `.claude/skills/mood_board_builder/` | 28K | 3 | curadoria + `scripts/montar_board.py` |
| `.claude/agents/mood_visual_dna.md` | 4K | 1 | o mesmo DNA como subagente |
| `skills_proprias/visual-dna-moodboard/` | ~70K | 10 | **original** da `mood_visual_dna` — o `AGENTS.md` referencia como proveniência |
| `docs/domains/mood/skills-mood-uso.md` | — | 1 | guia de uso (novo) |
| `scripts/trello-mcp-setup.sh` | — | 1 | registro do MCP do Trello, **sem segredo dentro** |
| `CLAUDE.md`, `AGENTS.md`, `docs/dd.md` | — | 3 | modificados: tabela de skills, seção da cadeia `mood_`, acesso ao Trello |
| os 5 `plano-0*.md` + `_cards-trello.md` | — | 6 | estes planos (ver D1) |

`.claude/skills/` **já é versionado** (41 arquivos hoje), então as novas skills entram no
lugar onde as `cy-*` e `compozy` já vivem — não é precedente novo.

### NÃO entra, em hipótese alguma

| Caminho | Por quê |
|---|---|
| `processo_manual/**/*.jpg` — **206 arquivos, ~25 MB** | referências de terceiros baixadas do Pinterest; uso local, sem commit (regra dos HARD-GATEs das skills) |
| `.DS_Store` (raiz e `skills_proprias/`) | lixo do Finder |
| `skills_proprias/visual-dna-moodboard-claude-skill.zip` | binário duplicado do diretório ao lado |
| `~/.config/orquestrador-studio/trello.env` | credenciais — já está fora do repo, **conferir que continua** |

## 3. Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D1 | Onde ficam os planos | (a) mover para `docs/domains/mood/planos/`; (b) manter em `processo_manual/` com exceção no `.gitignore` | **(a)** — o `CLAUDE.md` diz "todo o contexto vive em `docs/`", e (b) exige regra de exceção frágil (`!`) num diretório cheio de imagem |
| D2 | `processo_manual/` | ignorar o diretório inteiro | **sim** — depois de D1 não sobra nada lá que deva ser versionado |
| D3 | `skills_proprias/` | (a) entra como proveniência; (b) fica fora | **(a)** — o `AGENTS.md` já a referencia como o original; entra sem o `.zip` e sem `.DS_Store` |
| D4 | Como fechar | skill `ship-manual` (commit `ADH-OS-*` + PR para `develop`) + gate `ft-pr` | **sim** — não há task SDD `OS-NNN` aqui |
| D5 | ADR | as skills são `[extensão]`, não alteram decisão de arquitetura | **não precisa** — mas o PR tem de dizer que é `[extensão]` e por quê |

## 4. Passos

1. Branch a partir de `develop` (nunca commitar direto).
2. `.gitignore`: adicionar `processo_manual/`, `.DS_Store`, `skills_proprias/*.zip`.
3. Mover `processo_manual/moodboard/planos/*.md` → `docs/domains/mood/planos/` (D1) e corrigir
   os caminhos citados dentro dos planos e nos cards do Trello.
4. `git add` **explícito por caminho** — nunca `git add -A` nesta task.
5. **Portões de conferência antes do commit** (todos têm de passar):
   ```bash
   git diff --cached --name-only | grep -Ei '\.(jpg|jpeg|png|zip)$'   # tem de vir vazio
   git diff --cached --name-only | grep -F '.DS_Store'                # tem de vir vazio
   # o grep de credencial EXCLUI este próprio plano: senão ele casa com esta linha
   # (falso positivo real, visto na execução de 2026-09-02)
   git diff --cached -U0 -- . ':(exclude)docs/domains/mood/planos/plano-05-*.md' \
     | grep -Ei 'ATTA[0-9]{5}|f414990dbac5|0009cb880e'  # tem de vir vazio
   git diff --cached --shortstat                                       # sanidade de tamanho
   ```
6. `make hooks` (trailer `Task-Id:`) e commit com `Task-Id: ADH-OS-20260902-05`.
7. `make verify` (ruff + pytest) — as skills não têm teste, mas o repo não pode regredir.
8. Conferir que os três scripts das skills rodam a partir do repo limpo (`--help` / validação de
   um `dna.json` de exemplo), porque eles dependem de `playwright` e `Pillow`.
9. PR para `develop` pelo gate `ft-pr`, dizendo no corpo: é `[extensão]`, não altera etapa do
   curso, não gera imagem com IA, não gasta crédito.

## 5. Riscos

| Risco | Mitigação |
|---|---|
| `git add -A` arrastar 25 MB de imagem de terceiro | passo 4 proíbe; passo 5 é o portão que falha |
| Credencial do Trello vazar no diff | grep dedicado no passo 5; o `trello-mcp-setup.sh` lê de arquivo fora do repo |
| Planos citarem caminho antigo depois do D1 | passo 3 inclui corrigir as referências, inclusive nos cards |
| Script quebrar em clone limpo por falta de dependência | passo 8; se faltar, declarar em `requirements-dev.txt` |
| `.gitignore` de `processo_manual/` esconder algo útil no futuro | os planos saem de lá em D1; o resto é saída de corrida, descartável |

## 6. Critérios de aceite

- `git ls-files` não devolve nenhum `.jpg`, `.png`, `.zip` ou `.DS_Store` novo.
- Nenhuma das três credenciais do Trello aparece em qualquer arquivo versionado.
- As quatro skills, o agente e os três scripts estão em `develop` depois do merge.
- `docs/domains/mood/` contém o guia de uso e os planos, e os links internos funcionam.
- `make verify` verde.
- O PR declara explicitamente o caráter `[extensão]` da cadeia.
