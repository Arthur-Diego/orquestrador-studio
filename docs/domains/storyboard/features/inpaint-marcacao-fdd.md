# FDD: inpaint-marcacao `[extensão]`

Versão: 1.0
Data: 2026-08-30
Responsável: Wave 9 (`docs/domains/studio/waves/wave-9.md`) · Modo batch (auto-aceite, revisão em lote)
Card da wave: https://trello.com/c/T53Hnvlv

---

### 1. Contexto e motivação técnica

A aula 010 cita "Inpaint para ajustes localizados", mas na UI da Higgsfield: o usuário marca a
região e descreve a mudança. O CLI oficial (`hf.generate`, ADR-002) **não aceita máscara**, então
o Studio hoje só oferece o inpaint como preset de texto (`"Inpaint: corda proporcional"`, kind
`edit`). Esta feature entrega uma **aproximação de inpaint sem máscara**, toda `[extensão]`
(ADR-004): o usuário rabisca sobre a imagem escolhida dentro do Studio, o PNG anotado vira uma
referência EXTRA na geração via CLI, e uma instrução fixa em inglês pede para editar somente a
região marcada. É **best-effort por prompt**, não inpaint real, e a UI diz isso explicitamente.

Encaixe no HLD `studio`: plugin da etapa 4 (`studio/etapas/storyboard/`) + serviço
(`studio/storyboard/service.py`) + um asset novo de frontend (`studio/web/annotate.js`).
Nada do núcleo é **editado** (ADR-010): `app.py`, `steps.py`, `web/index.html`, `web/app.js`,
`web/ui.js` ficam intocados. O arquivo novo em `studio/web/` é servido automaticamente pelo mount
`/static` já existente (`app.py:214`, `StaticFiles` sobre o diretório) e é carregado sob demanda
pelo `view.js` da etapa por injeção dinâmica de `<script>`.

[auto-aceito: `studio/web/annotate.js` (caminho do contrato publicado na wave-9) servido pelo
mount `/static` existente e carregado por injeção dinâmica de script no `view.js` da etapa;
nenhum arquivo do núcleo é editado, apenas um arquivo novo é criado, preservando ADR-010]

Atores: usuário único local (ADR-001). Limites: a feature não automatiza a UI da Higgsfield,
não chama `api.higgsfield.ai` (ADR-002) e não altera o schema de `scenes.json` (ADR-018/021/022).

**Provides** (bloco da wave-9):
- Componente de canvas de marcação na SPA (`studio/web/annotate.js`, modal reutilizável no
  padrão de `web/multishot.js`): rabisco sobre a imagem, PNG anotado salvo no projeto via
  `ingest_bytes` com `meta {role:"annotation", parent}`.
- Modo de edição "área marcada" (`kind="edit_area"`) no fluxo de edição iterativa da etapa 4:
  original PRIMEIRA em `image_references`, anotada como referência extra, instrução fixa em
  inglês, fluxo pago `cost → confirmCost → job → record_generation`.

**Consumes**: nenhum (candidata imediata, sub-wave 1).

---

### 2. Objetivos técnicos

- O usuário marca uma região de uma imagem (base ou candidata) sem sair do Studio; o PNG anotado
  é persistido em `projects/<pid>/storyboard/candidates/` com `role:"annotation"` e `parent`
  (invariante: anotação nunca aparece como ideia nem é selecionável para cena).
- A geração `kind="edit_area"` envia SEMPRE `image_references = [original, anotada]`, nesta
  ordem (invariante testável no fake do CLI), com instrução em inglês montada pelo servidor.
- Toda geração do modo novo passa pelo gate de custo (estimativa grátis antes; ADR-016) e
  registra o gasto no livro-caixa (`record_generation`, ação `storyboard.inpaint`) após sucesso.
- Comportamento existente inalterado: kinds `draw_to_edit`/`edit`/`multishot`, presets da aula
  (inclusive "Inpaint: corda proporcional", que convive como texto), rotas e mensagens atuais.
- A UI declara em texto fixo que é aproximação best-effort por prompt, sem máscara real.

---

### 3. Escopo e exclusões

**Incluído**
- `studio/web/annotate.js`: modal `Studio.annotate.open({...})` com canvas de rabisco (pincel,
  espessura, desfazer, limpar), exportação em PNG achatado (imagem + traços) e callback de save.
- Rota nova de persistência da anotação: `POST /api/projects/{pid}/storyboard/annotate`.
- Kind novo `edit_area` em `KINDS` (`[extensão]`, `cli: True`) e o campo aditivo
  `annotation_id` em `GenerateReq`; extensão de `_cli_request`/`cost`/`start_generate`.
- Filtro aditivo: candidatos `role:"annotation"` fora de `GET .../storyboard/candidates` e
  recusados em `candidates/select` e como imagem de cena.
- Ação nova `storyboard.inpaint` em `settings.ACTIONS`/`DEFAULTS` (aditiva; painel de custos).
- Botões/painel na tela da etapa 4 (`studio/etapas/storyboard/view.js`), com o aviso best-effort.

**Excluído**
- Inpaint real com máscara (o CLI não suporta; ADR-002 proíbe outros caminhos).
- Qualquer edição de `app.py`, `steps.py`, `web/index.html`, `web/app.js`, `web/ui.js`,
  `web/multishot.js` (ADR-010) e de rotas/campos/mensagens existentes.
- Uso do canvas por outras etapas nesta entrega (o componente é reutilizável por contrato, mas
  só a etapa 4 o carrega).
- Mudança nos kinds existentes, no preset "Inpaint: corda proporcional" e no schema de
  `scenes.json`/`candidates.json` (apenas chaves de `meta` novas, que `ingest_bytes` já aceita).
- Retroagir `record_generation` para os kinds antigos (`edit`/`multishot`) — ver pendência P1.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (marcar e gerar)**
1. Na etapa 4, o usuário clica em "Marcar área `[extensão]`" na imagem base ou em um candidato.
2. `view.js` garante o componente carregado (injeta `<script src="/static/annotate.js">` na
   primeira vez; `window.Studio.annotate` presente nas seguintes) e abre o modal com a imagem.
3. O usuário rabisca a região (traço vermelho `#ff2d2d`, espessura 4 a 24 px, desfazer/limpar).
   [auto-aceito: cor fixa vermelha de alta visibilidade e traço opaco, porque a instrução fixa
   referencia "red hand-drawn marking" e o modelo precisa distinguir a marcação da foto]
4. "Salvar marcação" exporta o PNG achatado (imagem original + traços, mesma resolução da
   original) e faz `POST .../storyboard/annotate` (multipart: `file`, `source_id` opcional).
5. O serviço persiste via `ingest.ingest_bytes(root, "storyboard", data, "annotation", name, "",
   {"role": "annotation", "parent": <source_id ou "base">})` e devolve `{id, file, thumb, parent}`.
   Dedupe por SHA-1: reenvio idêntico devolve o candidato já existente (idempotente).
6. O painel "Área marcada" mostra original + anotada lado a lado, campo de instrução (regra "uma
   instrução por vez" da aula 010, mesma validação dos outros kinds), contagem 4 ou 1, seletor
   de modelo (catálogo atual: `nano_banana_2` default, `gpt_image_2 [extensão]`) e o aviso fixo:
   "Best-effort por prompt: a marcação vai como referência, não é inpaint com máscara; o
   resultado pode variar fora da área marcada (CLI sem máscara, ADR-002)".
7. Usuário clica "Gerar via CLI": `view.js` chama `POST .../storyboard/cost` (kind `edit_area` +
   `annotation_id`), mostra `Studio.ui.confirmCost` e, confirmado, `POST .../storyboard/generate`.
8. O job (JobRegistry da ideação, thread + polling em `GET .../storyboard/job`, ADR-006) chama
   `hf.generate(model, {"prompt": <instrução fixa>, "image_references": [original, anotada]})`
   `count` vezes; cada resultado é ingerido como candidato `source:"cli"` com
   `meta {kind:"edit_area", model, job_id, annotation: <id>}` e aparece na galeria de ideias.
9. Após cada geração bem-sucedida, `settings.record_generation(action="storyboard.inpaint",
   model=..., count=1, pid=..., step="storyboard", job_id=...)` registra no livro-caixa.

**Fluxos alternativos e exceções**
- Sem `base/base_final.png`: 409 (pré-requisito da etapa 3, regra atual mantida).
- CLI ausente/deslogado: 409 nas rotas pagas; o canvas e o upload da anotação continuam
  funcionando (a marcação não depende do CLI).
- `confirmCost` cancelado: nada é gerado nem registrado.
- Reenvio da mesma anotação (mesmo conteúdo): resposta 200 com o candidato existente.
- Job já em andamento no projeto: 409 (mesma regra dos kinds atuais).
- `annotation_id` cujo `parent` não corresponde à imagem original resolvida
  (`source_id`/base): 422, para impedir gerar com a marcação de outra foto.
  [auto-aceito: correspondência parent×original obrigatória (422) em vez de aviso, opção mais
  conservadora; o usuário resolve remarcando a imagem certa]
- Falha do `hf.generate`/download no meio do job: erro registrado no `log` do job (estado
  `error`), gasto registrado apenas para as chamadas que retornaram com sucesso.

**Diagramas**
- Sequência (resumo): view.js → annotate.js (canvas) → POST /annotate → ingest_bytes →
  view.js → POST /cost → confirmCost → POST /generate → thread(hf.generate×count →
  ingest_bytes → record_generation) → GET /job (polling) → galeria.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

**Contrato 1 — salvar a marcação**
- Tipo: endpoint
- Rota: `POST /api/projects/{pid}/storyboard/annotate`
- Método: POST · Content-Type: `multipart/form-data`
- Campos: `file` (PNG anotado, obrigatório, ≤ 25 MB — mesmo teto `MAX_UPLOAD_BYTES` das rotas
  de upload da etapa), `source_id` (opcional; id do candidato original. Ausente = imagem base).
- Status: 200 sucesso (novo ou dedupe); 404 projeto inexistente; 413 arquivo acima de 25 MB;
  422 imagem inválida/não decodificável ou `source_id` inexistente; 409 base ausente quando
  `source_id` ausente.

Exemplo de resposta
```json
{"id": "a1b2c3d4e5f6", "file": "storyboard/candidates/a1b2c3d4e5f6.png",
 "thumb": "storyboard/candidates/thumbs/a1b2c3d4e5f6.jpg",
 "parent": "9f8e7d6c5b4a", "role": "annotation", "deduped": false}
```
Semântica: `parent` é o id do candidato original ou o literal `"base"`; `deduped: true` indica
que o conteúdo já existia (idempotência por SHA-1 do `ingest_bytes`). O arquivo é servível por
`/files/{pid}/<file>`.

**Contrato 2 — custo do modo área marcada (extensão aditiva de rota existente)**
- Tipo: endpoint
- Rota: `POST /api/projects/{pid}/storyboard/cost`
- Método: POST
- Body (`GenerateReq` + campo aditivo `annotation_id`):
```json
{"model": "nano_banana_2", "kind": "edit_area", "text": "make the rope thinner",
 "count": 4, "source_id": "9f8e7d6c5b4a", "annotation_id": "a1b2c3d4e5f6"}
```
- Resposta (formato atual, inalterado): `{"per_image": 1.0, "total": 4.0}`
- Status: 200; 409 CLI ausente/deslogado ou base ausente; 422 validações (matriz, seção 6).
- Compatibilidade: `annotation_id` é ignorado pelos kinds existentes; pedidos antigos sem o
  campo seguem válidos byte a byte.

**Contrato 3 — geração do modo área marcada (extensão aditiva de rota existente)**
- Tipo: endpoint
- Rota: `POST /api/projects/{pid}/storyboard/generate`
- Método: POST · Body: idêntico ao Contrato 2.
- Resposta: a do `JobRegistry` atual (`{"state":"running","total":4,...}`); polling em
  `GET /api/projects/{pid}/storyboard/job` (contrato inalterado; job concluído lista os
  candidatos importados via `added`/`log`).
- Semântica interna fixada (verificável no fake de `hf.generate` nos testes):
  `params.image_references == [<abs original>, <abs anotada>]` (original SEMPRE primeira) e
  `params.prompt` igual à instrução fixa abaixo.

**Instrução fixa em inglês (montada pelo servidor; `{core}` = instrução única do usuário)**
```
Image 1 is the original photo. Image 2 is the same photo with a red hand-drawn marking
highlighting one region. Apply the following change ONLY inside the marked region: {core}.
Keep everything outside the marked region exactly identical to image 1, and do not render
the marking itself in the result. Keep everything else identical, realistic.
```
[auto-aceito: texto fixo derivado do padrão dos prompts da etapa (sufixo "Keep everything else
identical, realistic." da aula 010) + convenção image 1/image 2 já usada na aula 013
(`product_prompts`); prompts de geração em inglês por regra do repositório (aula 007)]

**Contrato 4 — componente de frontend**
- Tipo: sdk (JS do navegador)
- Assinatura: `Studio.annotate.open({ title, subtitle, sourceUrl, brush, onSave(blob) }) -> modal`
  - `sourceUrl`: URL servível da imagem original (`/files/{pid}/...`).
  - `onSave(blob)`: recebe o `Blob` PNG achatado; quem chama faz o upload (o componente não
    conhece rotas — mesmo princípio de dono/endpoints do `multishot.js`, ADR-017).
  - CSS 100% escopado (prefixo `ann-`) em `<style>` inline; não toca `ui.css`/`style.css`.
- Carregamento: `view.js` injeta `<script src="/static/annotate.js">` sob demanda e aguarda
  `window.Studio.annotate` antes de abrir.

**Contrato 5 — ação de custo (settings, ADR-016)**
- Tipo: dado de configuração (aditivo)
- `ACTIONS` += `{key: "storyboard.inpaint", screen: "Etapa 4 — Storyboard", kind: "image",
  label: "Editar área marcada (inpaint aproximado) [extensão]"}`
- `DEFAULTS` += `{"storyboard.inpaint": {"model": "nano_banana_2", "variant": "2k"}}`
- Override projeto → global → código via `default_for` (padrão existente); aparece no painel
  "Créditos & Custos" sem mudança de tela (o painel lê `ACTIONS`).

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | HTTP | Tratamento/mensagem (pt-BR) |
| --- | --- | --- |
| Projeto inexistente | 404 | padrão `project_dir` |
| `base/base_final.png` ausente | 409 | "Imagem base ausente: conclua a etapa 3 (base)" (atual) |
| CLI ausente / sem login (cost/generate) | 409 | mensagens atuais de `_cli_ready` |
| Upload da anotação > 25 MB | 413 | "arquivo acima de 25 MB" (padrão da etapa) |
| Anotação não decodificável como imagem | 422 | "arquivo de marcação inválido (envie o PNG exportado pelo canvas)" |
| `source_id` inexistente (annotate ou generate) | 422 | "ideia inexistente: {id}" (mensagem atual) |
| `kind="edit_area"` sem `annotation_id` | 422 | "o modo área marcada exige a marcação salva (annotation_id)" |
| `annotation_id` inexistente ou `role != "annotation"` | 422 | "marcação inexistente: {id}" |
| `parent` da anotação ≠ imagem original resolvida | 422 | "a marcação {id} pertence a outra imagem; marque a imagem escolhida" |
| Instrução vazia / > 300 chars / múltiplos pedidos / count ∉ {1,4} | 422 | validações atuais de `build_instruction` (reutilizadas) |
| Job de ideação já em andamento | 409 | "Já existe uma geração em andamento para este projeto." (atual) |
| Falha do `hf.generate`/download dentro do job | job `error`/`log` | padrão `JobRegistry`; itens já baixados são mantidos |
| Anotação usada em `candidates/select` ou como imagem de cena | 422 | "marcação não pode ser selecionada como ideia" |

**Notas de fechamento da implementação (2026-08-30)** — divergências residuais entre esta matriz e
o comportamento entregue, registradas em vez de silenciadas:

- A última linha junta dois casos com mensagens diferentes. Em `candidates/select` sai exatamente
  "marcação não pode ser selecionada como ideia" (guarda explícita). Como **imagem de cena** o 422
  vem da barreira já existente `_check_image` ("imagem fora de storyboard/ideas/ ou inexistente"),
  porque a anotação nunca é copiada para `storyboard/ideas/` — não há estado que produza o outro
  caminho. Coberto por `test_annotation_can_never_become_a_scene_image`.
- Precedência sobre as linhas de 422 do `edit_area`: `cost`/`generate` chamam `_cli_ready()` e
  `_require_base` **antes** das validações da marcação, então sem CLI logado ou sem a base o
  resultado é 409, não 422. É o comportamento das rotas de hoje, preservado de propósito.
- Contrato 1: enviar bytes idênticos aos de uma **ideia comum** (nenhum rabisco) é recusado com 422
  "essa imagem já existe como ideia, sem marcação: rabisque a região antes de salvar". O dedupe de
  `deduped: true` vale só entre marcações — devolver 200 aqui daria `role`/`parent` vazios, fora do
  domínio do contrato.
- Contrato 1: `thumb` é `null` quando o `ingest` não gera miniatura, e o upload aceita qualquer
  imagem decodificável pelo Pillow (não só PNG) — o canvas sempre envia PNG.
- Seção 8: `GET .../storyboard/instructions` passa a listar 4 kinds em vez de 3. É o efeito
  pretendido do kind aditivo (nenhum kind existente muda); o exemplo de resposta no
  `storyboard-fdd.md` §5 foi atualizado junto.

- Estratégias de resiliência: as do fluxo atual (timeout 600 s por chamada do CLI, job em
  thread, polling; sem retry novo).
- Política de fallback: sem CLI, o modo área marcada fica desabilitado na UI com a dica de usar
  o inpaint na própria interface da Higgsfield (caminho ilimitado do plano); não existe fallback
  de geração fora do CLI (ADR-002).
- Invariantes: original primeira em `image_references`; anotação nunca vira ideia/cena;
  `record_generation` só após geração bem-sucedida; nenhum contrato existente muda.

---

### 7. Observabilidade

**Métricas** (derivadas de logs/ledger, sem stack nova — padrão do monólito)
- Gasto por ação `storyboard.inpaint` no livro-caixa (`STATE_DIR/spend-ledger.jsonl`),
  agregado no painel de custos.
- `added`/`done`/`total` do job (polling), como hoje.

**Logs** (logger `studio.storyboard`, formato atual `evento %s {dict}`)
- `annotation_saved {pid, id, parent, deduped}` no upload da marcação.
- `instruction_built {pid, kind: "edit_area", count}` (reuso do log atual).
- `cli_job {pid, model, kind: "edit_area", count, state, seconds}` (reuso do log atual).

**Tracing**: não há (fora do padrão do projeto).

**Dashboards e alertas**: painel "Créditos & Custos" passa a listar a ação nova automaticamente
(lê `ACTIONS`); nenhum alerta novo.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| `@higgsfield/cli` | 1.1.23 (HLD higgsfield) | `generate cost`/`create` com `image_references` (lista já aceita, `storyboard/service.py:571`) |
| `studio/common/ingest.py` | atual | `ingest_bytes` com `meta` livre (role/parent) já suportado |
| `studio/common/settings.py` | atual | chaves novas aditivas em `ACTIONS`/`DEFAULTS` |
| Navegador | Canvas 2D + `toBlob` | SPA vanilla, sem build |

**Garantias de compatibilidade**
- Rotas, bodies e mensagens existentes byte a byte inalterados; `annotation_id` é campo
  opcional aditivo; kind novo é valor novo (nunca troca dos existentes).
- `candidates.json` mantém o schema; `role`/`parent` entram só nos itens novos (o multishot,
  ADR-017, já usa o mesmo padrão de meta).
- Projetos antigos (sem anotações) funcionam sem migração; anotações são ignoradas por
  qualquer código que não as conheça (aparecem como candidatos comuns só no arquivo).
- O preset de texto "Inpaint: corda proporcional" (kind `edit`) permanece intocado e convive
  com o modo novo.

---

### 9. Critérios de aceite técnicos

1. `POST .../storyboard/annotate` com PNG válido cria candidato com `role:"annotation"` e
   `parent` correto; reenvio idêntico devolve `deduped: true` e não duplica arquivo.
2. `GET .../storyboard/candidates` NÃO lista candidatos `role:"annotation"`;
   `POST .../candidates/select` com id de anotação devolve 422.
3. `POST .../storyboard/cost` e `/generate` com `kind:"edit_area"` válido funcionam; no fake de
   `hf.generate`/`hf.cost`, `image_references` tem exatamente 2 itens com a ORIGINAL primeira e
   o prompt é a instrução fixa com `{core}` interpolado.
4. `kind:"edit_area"` sem `annotation_id`, com anotação inexistente, com `role` errado ou com
   `parent` divergente devolve 422 com as mensagens da matriz; kinds antigos seguem passando
   nos testes existentes sem alteração de mensagem.
5. Job concluído importa os resultados como candidatos `source:"cli"` com
   `meta.kind:"edit_area"` e `meta.annotation` e grava 1 linha por geração no ledger com
   `action:"storyboard.inpaint"`; job cancelado no confirmCost não grava nada.
6. `settings.default_for("storyboard.inpaint", pid)` resolve projeto → global → código
   (`nano_banana_2`/`2k`), e a ação aparece em `all_defaults` (painel de custos).
7. A tela da etapa 4 exibe o rótulo `[extensão]` no modo novo e o aviso fixo de best-effort
   (verificável por assert de string no HTML/JS servido, padrão ADR-008).
8. `index.html`, `app.js`, `app.py`, `steps.py`, `ui.js`, `multishot.js` sem diff; `make verify`
   verde; testes novos sem rede/navegador (fakes de `hf.*`, ADR-008).

---

### 10. Riscos e mitigação

### O modelo edita fora da área marcada (limitação intrínseca sem máscara)

- **Probabilidade:** alta
- **Impacto:** resultado altera detalhes fora da região; frustração se a UI prometer inpaint real
- **Mitigação:**
    - Aviso fixo best-effort na UI e neste FDD; rótulo `[extensão]` no modo
    - Instrução fixa reforça "exactly identical outside the marked region"
    - Original primeira em `image_references` (ancoragem da cena) e contagem 4 para escolher
- **Plano de contingência:** orientar o caminho da UI da Higgsfield (inpaint real, ilimitado no plano)

### A marcação vermelha "vaza" para o resultado

- **Probabilidade:** média
- **Impacto:** traços renderizados na imagem gerada
- **Mitigação:**
    - Cláusula "do not render the marking itself" na instrução fixa
    - Traço fino/opaco padronizado; usuário pode regenerar (fluxo de 4)
- **Plano de contingência:** rodada extra `kind="edit"` "remove the red marking strokes"

### Conflito de merge em `view.js`/`service.py` com a sub-wave 2 (storyboard-roteiro-llm)

- **Probabilidade:** média
- **Impacto:** retrabalho de integração na W5
- **Mitigação:**
    - Ordem de integração da wave: inpaint-marcacao integra ANTES da sub-wave 2
    - Mudanças aditivas e localizadas (blocos novos, sem reescrever funções existentes)
- **Plano de contingência:** rebase guiado pela skill `git-rebase`

### Divergência com o FDD base do storyboard (exclusões "sem desenho no Studio / sem inpaint por CLI")

- **Probabilidade:** certa (documental)
- **Impacto:** doc viva contraditória se não sincronizada
- **Mitigação:**
    - Pendência P2 no gate em lote; nota aditiva no `storyboard-fdd.md` no fechamento
      (dd-parallel-doc-sync), marcando a exclusão como superada por esta `[extensão]`
- **Plano de contingência:** manter a exclusão e restringir o FDD novo, se o dono negar

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Serviço: `import_annotation` + filtro de anotações + guarda de seleção | - | `studio/storyboard/service.py` | 1 (parcial), 2 |
| 2 | Serviço: kind `edit_area` (`KINDS`, `_cli_request`, instrução fixa, `cost`, `start_generate` + `record_generation`) | 1 | `studio/storyboard/service.py`, `studio/common/settings.py` (ACTIONS/DEFAULTS) | 3, 5, 6 |
| 3 | Rotas: `POST /annotate` + campo `annotation_id` em `GenerateReq` | 1, 2 | `studio/etapas/storyboard/router.py` | 1, 4 |
| 4 | Frontend: `studio/web/annotate.js` (canvas) + carregamento dinâmico e painel na etapa 4 | 3 | `studio/web/annotate.js` (novo), `studio/etapas/storyboard/view.js`, `view.html` | 7 |
| 5 | Testes (fakes `hf.*`) + `make verify` + docs (PRD aditivo, este FDD) | 1 a 4 | `tests/test_storyboard*.py`, `docs/domains/storyboard/` | 3, 4, 5, 8 |

---

### Pendências para o gate em lote (nunca auto-aceitas)

- **P1 — livro-caixa dos kinds antigos:** a ideação atual (`edit`/`multishot` via CLI,
  `start_generate`) NÃO chama `record_generation`; este FDD registra o gasto só do modo novo
  (`storyboard.inpaint`), como manda a recon da wave. Estender o registro aos kinds antigos muda
  comportamento observável fora do escopo desta feature: decisão do dono no lote.
- **P2 — exclusões do FDD base:** `docs/domains/storyboard/features/storyboard-fdd.md` (§3)
  exclui "desenho/sketch dentro do Studio" e "inpaint por CLI". Esta feature supera essas
  exclusões como `[extensão]`; divergência com documento publicado não é auto-aceita — aprovação
  no lote + nota aditiva no FDD base no fechamento do ciclo.
- **P3 — aprovação `[extensão]`:** ADR-004/recon exigem aprovação explícita do dono para o
  inpaint por rabisco; o gate em lote da wave é essa aprovação. Nenhuma ADR nova é necessária
  (não contraria decisão vigente: geração continua exclusivamente via CLI, ADR-002), salvo se o
  dono quiser formalizar a aproximação sem máscara como ADR-025.
