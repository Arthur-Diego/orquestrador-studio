### FDD: mood-etapa2-pick — etapa 2 só ESCOLHE mood da biblioteca (criação centralizada)

Task-Id: ADH-OS-20260827-07 · Domínio: studio (etapa mood + shell) · Base: `develop` (pós #55)
Pedido do dono do produto (27/08/2026): "restringir a criação de moods apenas para a tela
Biblioteca · independente de campanha (Mood boards); a etapa 2 passa a só usar o que existe lá."
Decisões do dono (em lote): (1) etapa 2 = **só escolher** um board da biblioteca (remover os painéis
de criação: achar vibe, prompt de vibe, importar grid, curar); (2) escolher um board **copia** as
imagens dele para a campanha (`mood/selected` + vibe + paleta) — campanha independente do board.

### 0. Fidelidade (ADR-004) — é `[extensão]` que aprofunda a ADR-007/013

A aula 009 constrói o mood NA etapa 2. Centralizar a criação na biblioteca e transformar a etapa 2
em "escolher um board" é decisão do dono do produto, `[extensão]`. **Atualizar a ADR-013** (ou criar
`ADR-014`) registrando: a criação de mood board acontece só na biblioteca global; a etapa 2 da
campanha seleciona um board e o aplica copiando as imagens para o mood da campanha. O texto da aula
009 continua no guia/plano (não some do conhecimento; só deixa de ser executado na etapa 2).

### 1. Frontend — etapa 2 (mood) vira tela de ESCOLHA (`studio/etapas/mood/*`)

Remover os painéis de criação de `studio/etapas/mood/view.html`/`view.js`:
- 01 "Achar a vibe" (upload de imagens de vibe), 02 "Prompt de vibe — o bot", 03 "Importar o grid",
  04 "Escolher o mood" (curadoria com várias fotos).
Nova etapa 2 (um/dois painéis):
- **Painel 01 "Escolher um mood board"**: grade dos boards da biblioteca (`GET /api/moodboards`,
  card = capa + nome + nº de imagens + vibe). Vazio → estado "Nenhum mood board ainda — crie na
  biblioteca" + botão que navega para `#/moodboards`. Selecionar um board + botão **"Aplicar a esta
  campanha"** → chama o `pull_board` (copia imagens → `mood/selected` + `mood.md` + `palette.json` +
  `project.vibe`). Toast + recarrega o estado.
- **Painel 02 "Mood atual da campanha"**: mostra o mood aplicado — galeria das imagens de
  `mood/selected` (thumbs) + a paleta + a vibe em palavras. Botão "Trocar" (volta a escolher) e
  "Criar / gerenciar mood boards" (→ `#/moodboards`).
- Sem criação/curadoria/importação/prompt na etapa 2. O `[extensão]` some do botão (agora é o fluxo).

### 2. Backend

- Reusar `mood.pull_board(pid, mbid)` (já existe desde #53) — é o que copia o board para a campanha.
  Se ele ainda exigir algo, ajustar para ser idempotente (reaplicar troca o mood).
- Os endpoints de criação da etapa 2 (`mood/vibe/import/*`, `mood/prompts/generate`,
  `mood/import/*`, `mood/generate`, `mood/select`) **permanecem no backend** (não quebrar contratos
  nem a biblioteca, que usa a mesma família de ingest/prompter) mas deixam de ser chamados pela tela
  da etapa 2. Marcar no docstring do `mood/service.py` que a criação migrou para a biblioteca.
- `GET /api/projects/{pid}/mood` (status) deve expor o mood atual (imagens/paleta/vibe) para o
  painel 02.

### 3. Guia da etapa 2 (`studio/etapas/mood/guide.py`)

- `done` = há mood aplicado (`mood/selected` não vazio). 
- `next_action` = "Escolha um mood board da biblioteca e aplique à campanha" quando vazio; imperativo
  curto quando pronto. Remover checagens que exigiam "gerar prompt/importar grid" na etapa 2.
- O texto de aula (achar a vibe pelo sentimento etc.) continua referenciado como contexto, mas a
  ação da etapa é escolher da biblioteca.

### 4. Testes

- `tests/test_mood_api.py` / `test_view_follows...`: refletir a nova tela (painel de escolha + painel
  do mood atual; ausência dos painéis de criação). Reapontar asserts de substring.
- `tests/test_mood_guide.py`: novo `done`/`next_action`.
- Guardar um teste de `pull_board` aplicando um board (fixture em `STUDIO_MOODBOARDS` tmp) → 
  `mood/selected` populado + `project.vibe`/`palette` setados.
- Não reduzir baseline sem justificar (remoção de asserts que fixavam painéis removidos é justificada).

### 5. Verificação

- `make verify` verde.
- Smoke Playwright: (a) criar um board na biblioteca (import + curar + salvar); (b) na etapa 2 da
  campanha, escolher esse board e "Aplicar" → painel "Mood atual" mostra as imagens; (c) etapa 3
  (base) continua enxergando o mood aplicado. 0 erro de console; dark+light; sem scroll horizontal.
  Prints fora do git.

### 6. Fora de escopo

- Remover os endpoints de criação do backend (podem virar limpeza futura; agora só saem da UI).
- Migração de campanhas antigas que já tinham mood criado na etapa 2 (o `mood/selected` existente
  continua válido; a nova tela mostra "Mood atual" e permite trocar por um board).
