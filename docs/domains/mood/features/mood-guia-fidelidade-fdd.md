### FDD: mood — guia da etapa 2 e fidelidade à aula 009 — OS-014

Versão: 1.0 · Data: 2026-08-25 · Domínio: `mood` (etapa 2) + `common/prompter` (papel `mood`) · Wave 2
Fontes normativas: `docs/domains/studio/waves/wave-2.md` (feature refs+mood),
`docs/domains/studio/waves/wave-2-auditoria-etapas-1-3.md` §2 (M1–M5, M8, M10, §2.4 textos, §2.5 validações)
e §4 (G2, G8, G10), `docs/domains/studio/waves/wave-2-api-transversal.md`.
Redesign visual das telas 1 e 2 (wave 3, `ADH-OS-20260826-03`): `docs/domains/refs/features/views-refs-mood-redesign-fdd.md` — este FDD continua normativo para o comportamento; o do redesign é normativo para o markup.

### 1. Contexto e motivação técnica
A etapa 2 monta **uma** vibe para a campanha inteira. A auditoria confirmou a estrutura (1 prompt de
vibe, grid de 4, teto de 8, bot com imagem) e encontrou um desvio **grave**: o Studio injeta
"No product, no people, no text, no logos" em todo prompt de mood e atribui a regra à aula 009 — mas na
aula o mood board **tem o produto** ("ele já me deu inclusive o Red Bull […] Essa é a vibe"; "Gostei
muito da noite, a lata aqui"). A única restrição que o instrutor enuncia é "não tenho nenhum interesse
em pessoas", e ela é uma escolha *daquela* campanha (M1). Outros desvios: a geração via CLI manda as
referências do Pinterest como `image_references`, quando a aula usa a **imagem de vibe** (1ª rodada) e a
**melhor imagem do grid** como referência de estilo (2ª rodada) (M2); não há campo para o "prompt copiado
do Explore", que é o ponto de partida do primeiro grid (M3); os termos e `alt` do Pinterest são injetados
no prompt de vibe, embora a aula diga que a vibe "não precisa ter a ver com o produto" (M4);
`palette.json` é derivado técnico que a aula não ensina (M5); `_STYLE_VARIANTS` está duplicado (M8); a
tela promete "2K/16:9" e chama o plano de "Ultra" (M10/G10); falta a regra "estilização no meio-termo"
(G8); e a `vibe` do projeto nunca é gravada pela etapa que a encontra (G2).

**Provides**: `studio/etapas/mood/guide.py`; prompt de vibe sem negativos forçados; `no_people` explícito;
`explore_prompt`; referência de estilo a partir das imagens de vibe e da "melhor do grid"; `project.vibe`
gravada no `select`; textos e docs corrigidos.
**Consumes**: `studio/common/guide.py`, `Studio.ui`, `GET /api/projects/{pid}/guide/{step}`,
`common/prompter.py`, `refs/candidates.json` (só para validação/etapa 3, não mais para o prompt).

### 2. Objetivos técnicos
1. **M1** — remover "no product / no text / no logos" do papel do bot (`ROLES["mood"]`), do template e dos
   guards; manter "no people" como padrão **sugerido e visível** (checkbox marcado, com explicação),
   nunca como injeção silenciosa; corrigir a atribuição "(aula 009)" na tela, no HLD e no `prompter-fdd`.
2. **M2** — `POST /mood/generate` usa como `image_references` as imagens de vibe escolhidas e, quando
   informada, a candidata marcada "melhor do grid" (2ª rodada da aula).
3. **M3** — campo "prompt copiado do Explore/da imagem de vibe": base do prompt no modo `template` e
   instrução de preservação nos modos com Claude.
4. **M4** — `_refs_summary` fora do prompt de mood (segue disponível para a etapa 3 via `refs_terms`).
5. **M5** — `palette.json` marcado `[extensão]` (artefato fiel é `mood/selected/`).
6. **M8** — uma única lista de variações de estilização (`prompter.STYLE_VARIANTS`).
7. **M10/G10** — "2K/16:9" como *sugestão do Studio*; plano chamado **Ultimate**.
8. **G8** — "estilização no meio-termo; extremos alucinam" no painel.
9. **G2** — `POST /mood/select {note}` grava `project.vibe` (a aula encontra a vibe aqui).
10. Painel de guia da etapa 2 (auditoria §2.4/§2.5) + `Studio.ui` + `destroy()`.

### 3. Escopo e exclusões
Inclui: `studio/etapas/mood/{guide.py,router.py,view.html,view.js}`, `studio/mood/service.py`,
`studio/common/prompter.py` **apenas no papel `mood`** (ROLES, guards, template, `STYLE_VARIANTS`),
`docs/domains/mood/**`, `tests/test_mood_*`, `tests/test_prompter.py`.
Exclui: papéis `base` e `motion` do prompter; mood board de filme (M11) e Color Transfer (fica como texto
no guia, sem implementação); `studio/web/*`, `app.py`, `steps.py`, `config.py`.

### 4. Fluxos
**Principal** — o usuário traz 1–4 imagens de vibe (Explore, Pinterest, frame de filme) e marca as que
definem a identidade; opcionalmente cola o **prompt copiado do Explore**; escolhe o modo do bot e gera o
prompt de vibe (com "sem pessoas" marcado por padrão, desmarcável); gera o grid de 4 na UI da Higgsfield
(ou via CLI, com as imagens de vibe como referência de estilo); importa; se "não pegou a vibe", marca a
melhor do grid como referência e gera outra rodada com o mesmo prompt; escolhe até 8 no mesmo mood e
salva → `mood/selected/`, `mood.md`, `palette.json` `[extensão]`, `project.vibe` ← `note`.
**Erro** — modo `images` sem imagem → 422; Claude ausente → 409; falha do bot → 502; > 8 escolhidas → 422
(seleção anterior preservada); CLI ausente → 409.

### 5. Contratos públicos
| Rota | Mudança | Contrato |
| --- | --- | --- |
| `GET /api/projects/{pid}/mood/prompts?model&variation&no_people&explore_prompt` | **novos** `no_people` (default `true`) e `explore_prompt` | prompt **sem** "no product/no text/no logos"; "No people." só quando `no_people`; com `explore_prompt`, o prompt copiado é a base e só a estilização é acrescentada |
| `POST /api/projects/{pid}/mood/prompts/generate` | **novos** `no_people: bool = true`, `explore_prompt: str = ""` | resposta ganha `no_people` e `explore_prompt`; `enforce_mood_rules` só acrescenta "No people." e só se `no_people` |
| `POST /api/projects/{pid}/mood/generate` | `use_refs` → **`use_style_refs`** (M2) + `vibe_ids: [str]`, `best_id: str \| null` | `image_references` = imagens de vibe escolhidas (ou todas, até 4) + arquivo da candidata `best_id`; `use_refs` segue aceito como alias depreciado |
| `POST /api/projects/{pid}/mood/cost` | idem (mesmo corpo) | inalterado no cálculo |
| `POST /api/projects/{pid}/mood/select {ids, note}` | **efeito novo** (G2) | além de `mood/selected|palette.json|mood.md`, grava `project.vibe = note` (escrita atômica) quando `note` não é vazio; resposta ganha `"vibe"` |
| `GET /api/projects/{pid}/guide/mood` | **novo** (hook) | `Guide` da etapa 2 |

`prompter`: `ROLES["mood"]` sem os negativos de produto/texto/logo; `MOOD_GUARDS = ("no people",)`;
`enforce_mood_rules(result, no_people=True)`; `STYLE_VARIANTS` público (`_STYLE_VARIANTS` mantido como alias).

### 6. O guia da etapa 2 (`studio/etapas/mood/guide.py`)
- `what`/`checklist`: texto literal da auditoria §2.4 (inclui a linha do mood board de filme e a de
  estilização no meio-termo, G8).
- `inputs`: `product` — "produto do projeto (`project.json`)" (bloqueia: sem produto o prompt de vibe não
  se escreve). **Referências da etapa 1 não bloqueiam** — a aula encontra a vibe no Explore; a ausência
  vira validação `todo` com atalho para a etapa 1.
- `outputs`: `selected` — "`mood/selected/` com 1 a 8 imagens no mesmo mood"; `mood_md` — "`mood/mood.md`
  com o prompt de vibe".
- `validations` (§2.5, leitura pura):
  | id | regra | status |
  | --- | --- | --- |
  | `vibe_images` | ≥ 1 imagem de vibe importada (aula: a vibe é encontrada) | `ok` / `todo` |
  | `selected_range` | `mood/selected/` entre 1 e 8 imagens | `ok` / `warn` / `todo` |
  | `single_vibe` | `mood.md` registra **um** prompt de vibe (≤ 2 linhas "prompt:") | `ok` / `warn` / `todo` |
  | `prompt_en` | prompt de vibe em inglês (≥ 90 % ASCII e sem stopwords pt) | `ok` / `warn` / `todo` |
  | `images_mode_ref` | se o último prompt saiu do modo `images`, havia imagem anexada | `ok` / `warn` |
  | `no_forced_negatives` | o prompt não contém "no product"/"no logos" sem o usuário ter pedido (M1) | `ok` / `warn` |
  | `same_mood` | paletas das escolhidas próximas entre si (distância média dos 3 tons principais) | `ok` / `warn` / `todo` |
  | `refs_from_step1` | referências da etapa 1 disponíveis (contexto, não bloqueio) | `ok` / `todo` |
  | `project_vibe` | `project.vibe` preenchida (a etapa 2 grava ao salvar) | `ok` / `todo` |
- `same_mood` usa `palette.json` `[extensão]` quando existe; sem ele, a validação fica `todo` (nunca
  abre imagem: o hook é barato e não usa Pillow).

### 7. Erros e fallback
Hook puro; `mood.md`/`palette.json` corrompidos → `todo`. `select` grava `project.vibe` por escrita
atômica (tmp + `os.replace`); falha ao ler `project.json` não derruba a seleção (o mood é salvo primeiro).
`use_refs` continua aceito para não quebrar cliente antigo.

### 8. Dependências
`common/prompter.py` (Claude CLI opcional), `common/ingest.py`, Pillow, `common/guide.py`, `Studio.ui`.

### 9. Critérios de aceite
1. `GET …/mood/prompts` devolve prompt **sem** "no product", "no logos" e "no text"; com "No people." por padrão e sem ele quando `no_people=false`.
2. `POST …/mood/prompts/generate` (modo template) idem; `enforce_mood_rules({"prompt": "x"}, no_people=False)` não altera o prompt.
3. O prompt de vibe não contém termos nem `alt` das referências do Pinterest (M4), e `mood.refs_terms(pid)` segue devolvendo os termos para a etapa 3.
4. `explore_prompt` preenchido → o prompt gerado começa pelo prompt colado (modo template) e a variação de estilização é acrescentada.
5. `POST …/mood/generate` com `vibe_ids` manda os arquivos de `mood/vibe/candidates/` como `image_references`; com `best_id`, acrescenta o arquivo da candidata; sem `use_style_refs`, manda `None`.
6. `POST …/mood/select {note}` grava `project.vibe` (visível em `GET /api/projects/{pid}`) e devolve `vibe`.
7. `mood.md` marca `palette.json` como `[extensão]`; textos dizem "sugestão do Studio" e "Ultimate".
8. `GET …/guide/mood` sem produto → `blocked`; com produto e sem seleção → `todo` com `missing`; com 4 escolhidas + `mood.md` → `done`, `next_step: "base"`.
9. `view.html` mantém `Etapa 2 · aula 009`, tem `<section id="guide" class="guide">` e não atribui "sem produto" à aula; `view.js` usa `Studio.ui.*`, chama `ctx.guide()` após cada ação e expõe `destroy()`.
10. `test_mood_prompt_is_single_vibe_without_product` invertido: passa a exigir a ausência dos negativos forçados.

### 10. Riscos
- Cliente antigo enviando `use_refs` continua funcionando (alias), mas o comportamento muda: as
  referências do Pinterest deixam de ser mandadas ao CLI — mudança **intencional** (M2), registrada aqui.
- `same_mood` por `palette.json` é aproximação; por isso é aviso.
- Remover os guards pode fazer o Claude devolver prompt com produto/pessoas; a aula aceita produto, e
  "sem pessoas" segue como checkbox marcado por padrão.

### 11. Build order
`studio/common/prompter.py` (papel mood) → `studio/mood/service.py` → `studio/etapas/mood/router.py` →
`studio/etapas/mood/guide.py` → `view.html` → `view.js` → `tests/test_prompter.py`,
`tests/test_mood_service.py`, `tests/test_mood_guide.py` → `docs/domains/mood/{hld.md,features/prompter-fdd.md}`.
~10 arquivos, mas 1 fluxo principal e ≤ 3 contratos alterados → **implementação direta**.

### 12. Auto-aceites (Gate 1 em lote)
1. `use_refs` mantido como alias depreciado de `use_style_refs` em vez de quebra dura.
2. "Melhor do grid" exposta como seletor único (`best_id`) na tela, não como estrela por card.
3. `same_mood` implementada sobre `palette.json` (sem abrir imagem no hook do guia).
4. `project.vibe` gravada pelo **serviço** (escrita atômica direta), não por chamada HTTP `PATCH` a
   partir do `view.js` — menos ida e volta e funciona também quando o `select` vem por API.
5. "no people" permanece **default marcado** (a aula pediu, para aquela campanha); nunca silencioso.
