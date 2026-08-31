# PRD: base (Etapa 3, Imagem base, aula 009)

Task-Id: OS-003 · Wave 1 · Data: 2026-08-25 · Modo batch (auto-aceites listados no FDD)

## Problema
Após as etapas 1 (referências do Pinterest) e 2 (mood board com paleta), o criador ainda não tem a
imagem que define a campanha: o produto do cliente inserido na situação de uma referência escolhida,
com o mood aprovado, já com o rótulo da marca própria e em resolução suficiente para as próximas
etapas (storyboard, ângulos, animação). Hoje esse passo é feito à mão na Higgsfield, sem registro
de prompt, referência usada nem do arquivo final, e as etapas 4 e 5 não têm de onde partir.

## Objetivo da aula (009)
Para cada referência escolhida, pedir "o produto na exata mesma situação da imagem de referência,
com o mood da campanha" (em aba nova, sem viés de conversa anterior); escolher a melhor imagem;
trocar o rótulo pela marca própria com Nano Banana, uma instrução por vez; fazer upscale 2x
High Fidelity. Sem pessoas, a menos que a referência as tenha. O produto sai da aula com UMA imagem
base da campanha.

## Usuário
O aluno do curso operando o Studio localmente, com plano da Higgsfield (ilimitado na UI) e,
opcionalmente, CLI logado para gerar por créditos.

## Escopo
- Entregar os prompts em inglês (situação por referência, troca de rótulo, upscale) a partir de
  `refs/brainstorming/`, `mood/selected/`, `mood/palette.json` e `project.json`.
- Importar as imagens geradas na UI (upload, pasta Downloads, histórico do CLI) como candidatas
  classificadas por tipo: `situation`, `label`, `upscale`.
- Alternativa paga via CLI (somente logado, sempre com `cost` antes): situação, rótulo, upscale.
- Escolher a candidata final e gravar `base/base_final.png`, `base/candidates.json`, `base/base.md`.
- `[extensão]` campo `brand` (nome/descrição do rótulo) em `base/base.md`, necessário ao prompt de
  troca de rótulo (extensão aprovada na wave-1).

## Fora de escopo
- Character sheet, product sheet em 3 vistas, Soul ID, color match, Color Transfer automatizado
  ([INFERÊNCIA] do plano; ADR-004).
- Edição da imagem dentro do Studio (inpaint, draw to edit): pertence à etapa 4.
- Múltiplas imagens base por projeto; a aula produz uma só.
- Qualquer chamada a `api.higgsfield.ai` ou automação da UI (ADR-002).
- Alterar `app.py`, `steps.py`, `index.html`, `app.js`, `conftest.py`, `higgsfield.py`, `requirements*`.

## Feature: base-clean-marca `[extensão]` (Wave 9)

Adição da Wave 9 (modo batch; spec: `features/base-clean-marca-fdd.md`). O levantamento do curso
(passo 4.3, fonte externa ao repo: pendência confirmada no gate em lote da wave) pede um passo de
**limpeza de marca**: remover marca/logo/texto alheios da imagem de situação antes de aplicar a
marca do usuário no rótulo.

- Novo `kind="clean"` na etapa 3, entre `situation` e `label` na cadeia
  (situation → clean opcional → label → upscale). Remoção por prompt no `nano_banana_2`
  (best-effort: o CLI não tem máscara/inpaint, ADR-002); prompt em inglês, determinístico,
  editável na tela; 3 variações por default (mesmo padrão do rótulo).
- Sem rota nova: os endpoints existentes da etapa (`cost`, `generate`, `import/*`, `select`)
  aceitam o valor novo de `kind`, no padrão do `kind="label"`. Campo opcional `target` nomeia a
  marca a remover; a tela o pré-preenche com a marca validada da etapa 1
  (`GET .../refs/validated-brand`, ADR-020, leitura só no cliente).
- Fluxo pago com ação de custo própria `base.clean` (ADR-016): `cost` → `confirmCost` → job →
  `record_generation`; modo UI ilimitado com import `kind:"clean"` continua sendo o caminho sem
  custo.
- "Trocar por minha marca" não é um kind híbrido: após selecionar a clean, o passo `label`
  existente aplica `base/brand.json` partindo da clean selecionada (fallback: situação, como hoje).
- Fora de escopo da feature: inpaint real com máscara, limpar referências cruas da etapa 1,
  ler `refs/validated_brand.json` no backend da etapa 3.

---

## Contexto da Wave 9 (frente `base-clean-marca`, sub-wave 1)

Este workflow SDD roda numa worktree isolada (`wt-base-clean-marca`, branch
`feature/base-clean-marca`, base `develop@7162c41`, PORT=8767). A spec normativa é o
`_techspec.md` (FDD aprovado no gate em lote W3). **Em qualquer divergência entre este `_prd.md`
e o `_techspec.md`, a §5 do `_techspec.md` vence.**

Resolução do gate W3 aplicável a esta frente (item 4): a fonte do "passo 4.3" foi confirmada pelo
dono no levantamento do curso ("4.3 retirar marca (caso exista)… pedir para retirar ou modificar").
A feature entra inteira como `[extensão]` (ADR-004).

Sem dependências de outras frentes (sub-wave 1). Nada precisa ser mockado.

## Decisão de contrato tomada pela frente (vale para todas as tasks)

O FDD §5 (Contrato 4) determina que a resposta de `POST /base/select` passe a incluir a chave
`clean` no mapa `chain`. O FDD §9 critério 10 pede que "nenhum teste existente seja alterado em
asserção". As duas coisas são **incompatíveis**: três asserções de igualdade exata em
`tests/test_base_service.py` (linhas 238-239, 261 e 265) comparam o `chain` com um dict fechado de
três chaves. A §5 vence (é o contrato); as três asserções ganham `"clean": None` (ou o id da
clean) e nada mais. É a única alteração permitida em teste existente, e ela é **aditiva**.

## Invariantes de ambiente (Wave 9)

- Só é permitido tocar: `studio/base/*`, `studio/etapas/base/*`, `studio/common/settings.py`,
  `tests/test_base_*.py`, `tests/test_settings.py` e `docs/domains/base/**`.
- **PROIBIDO** tocar o núcleo (ADR-010): `studio/app.py`, `studio/steps.py`, `studio/web/**`,
  `studio/higgsfield.py`, `studio/common/pricing.py`, `studio/common/ingest.py`,
  `tests/conftest.py`, `requirements*.txt`, `pyproject.toml`, `Makefile`.
- **PROIBIDO** tocar arquivos de outras frentes da wave: `studio/common/prompter.py`,
  `studio/storyboard/**`, `studio/etapas/storyboard/**`, `studio/refs/**`,
  `studio/etapas/refs/**` (a rota `GET .../refs/validated-brand` é consumida **read-only pelo
  cliente**, sem uma linha de código novo em `refs`).
- **PROIBIDO** tocar artefatos compartilhados da wave: `docs/domains/studio/waves/*.md`,
  `docs/adrs/**`, `CLAUDE.md`.
- Testes sem rede, sem navegador e sem CLI real (ADR-008): a Higgsfield é sempre falsificada
  por monkeypatch, no padrão já usado em `tests/test_base_service.py` e `tests/test_base_api.py`.
- `make verify` (ruff + pytest) VERDE ao fim de cada task. **Baseline antes da frente: 976 testes
  passando.** Nenhum teste existente pode passar a falhar.
- Idioma: docstrings, comentários e mensagens de erro em pt-BR; identificadores em inglês;
  prompts de geração de imagem em inglês (aula 007).
- Commits com trailer `Task-Id: ADH-OS-20260830-44`.
