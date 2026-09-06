### FDD: storyboard-geracao-por-cena `[extensão]`

Versão: 1.0 · Data: 2026-09-06 · Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11) ·
Task-Id: ADH-OS-20260906-09 · Card(s): https://trello.com/c/QVr0fPRk (leitura B) ·
Card da wave: https://trello.com/c/OvSfo3D2

Domínio: `storyboard` (etapa 4). A documentação dos ângulos por cena vive em `docs/domains/shots/`
(`features/shots-fdd.md` §5); os nomes pré-fusão `/api/projects/{pid}/shots/*` daquele documento
correspondem hoje a `/api/projects/{pid}/storyboard/angles/*` (ADR-015, nota em `shots-fdd.md:228`).

---

### 1. Contexto e motivação técnica

**Problema técnico.** A metade "Ângulos por cena" da etapa 4 (`studio/etapas/storyboard/ui/Angles.tsx`)
só sabe *importar*: o único caminho para uma cena ganhar um frame é gerar na interface da Higgsfield e
trazer o arquivo ("Gere na interface da Higgsfield… e traga os resultados", `Angles.tsx:716`; vazio da
galeria em `:581`). Os endpoints que geram, custam e upscalam por cena **já existem e são testados no
backend** (`studio/etapas/storyboard/router.py:512-604`; serviço `studio/storyboard/angles.py:413-529`;
testes `tests/test_storyboard_angles_{api,service,guide}.py`, 24/42/12 casos) e estão **órfãos no
frontend** desde a wave 4 (nota "`[extensão]` rota sem comando na UI", `shots-fdd.md:225-229` e
`:246-247`, decisão ADH-OS-20260829-37, pinada pelo caso de QA `C-STORYBOARD-50`). O motor local grátis
(ADR-033, `studio/storyboard/local.py`) gera apenas keyframes de ideação para a galeria do painel 01b:
`start_generate` ingere sempre em `STEP = "storyboard"` (`local.py:70`), nunca na pasta de uma cena. E o
MCP (ADR-037/040) expõe `storyboard_local_generate`, `storyboard_pick` e `storyboard_scenes`
(`studio/mcp/server.py:104-112`), nenhuma tool por cena.

Resultado: quem já escreveu as cenas precisa sair da ferramenta para produzir os ângulos, e o assistente
não consegue ajudar nessa parte do método (aula 011) nem na cena do produto (aula 013).

**Encaixe no HLD e nas decisões vigentes.** A frente não cria ponte de geração nova: liga a ponte paga
existente (Higgsfield via CLI oficial, ADR-002) e a ponte gratuita existente (motor local, ADR-033) ao
painel de ângulos, que hoje só tem o caminho de importação. O caminho da aula ("gere na UI da Higgsfield
e importe") **permanece intacto e continua sendo o texto padrão da tela**: CLI e local são atalhos
opt-in marcados `[extensão]` (ADR-002/004/033, gate 3 do `CLAUDE.md`: trocar ferramenta é legítimo,
trocar processo não). Todo gasto passa pelo gate de custo antes de gerar (ADR-016) e pelo gate de login
do CLI (`hf.require_cli`, ADR-028 HIGGSFIELD, 409). A escolha visual e o gasto continuam do usuário
(ADR-038). As tools MCP são clientes HTTP da própria API, nunca importam o serviço da etapa (ADR-037), e
o caminho pago do agente passa por `_paid` (`studio/mcp/actions.py:34-59`).

**Atores.** Usuário na tela (painel 04/05 de Ângulos); assistente de chat pelas tools `mcp__studio__*`;
Higgsfield CLI (pago); motor local `engine` + ComfyUI (grátis); livro-caixa de créditos
(`studio/common/settings.py`).

**Limites.** A frente é dona da metade **ângulos/local por cena** de `studio/etapas/storyboard/router.py`
e `studio/storyboard/{angles,local}.py`. Não toca `Ideation.tsx` nem `studio/storyboard/service.py` na
parte de ideação/cenas/roteiro, que são da F06 (`wave-11.md` §Conflitos).

**Provides/Consumes (copiado de `docs/domains/studio/waves/wave-11.md`, feature F07)**

Provides
- Botões por cena no painel Ângulos: "Gerar imagem da cena - local (grátis)" (`POST …/local/generate`
  com `scene` opcional, saída em `cenaNN/`) e "Gerar via CLI (gasta créditos)" ligando os endpoints
  órfãos `angles/scenes/{scene}/{cost,generate,upscale}` com `useCostConfirm`; idem cena do produto.
- Preset de realismo injetado nos prompts de ângulos via
  `settings.preset_default_for("storyboard.angles", pid)`.
- Tools MCP `storyboard_scene_generate(scene, engine=local|cli)` (CLI passa por `_paid`) e
  `storyboard_scene_pick(scene)`.

Consumes
- Chave `storyboard.angles` em `PRESET_ACTIONS` ← **storyboard-cenas** (mesma sub-wave; F07 registra a
  chave de forma idempotente, `setdefault`, se ainda não existir; conflito trivial no rebase).
- [cross-feature] Critério: com o preset da campanha configurado por F06, os prompts de ângulos de F07
  carregam o `preset_block` correspondente (evidência no estado integrado).

---

### 2. Objetivos técnicos

- **Fechar a órfandade dos endpoints por cena.** Invariante verificável: toda rota de
  `angles/scenes/{scene}/{cost,generate,upscale}` e `angles/product/{cost,generate,upscale}` passa a ter
  pelo menos um chamador em `studio/etapas/storyboard/ui/Angles.tsx`; `grep` de cada caminho no arquivo
  devolve ao menos uma ocorrência.
- **Geração local por cena, grátis e determinística no destino.** Invariante: com `scene="cenaNN"`, todo
  candidato gerado é ingerido em `storyboard/cenaNN/candidates/` e aparece em
  `GET …/angles/scenes/cenaNN/candidates`; sem `scene`, o comportamento de hoje (galeria de ideação,
  `storyboard/candidates/`) fica byte a byte idêntico.
- **Zero crédito gasto sem confirmação.** Invariante: nenhum `POST` de `generate`/`upscale` dos ângulos
  parte da tela sem um `POST …/cost` respondido e um "Gerar" confirmado no `useCostConfirm`; no MCP,
  nenhum `generate` parte sem `_paid` (ADR-016/038).
- **Preset de realismo opt-in.** Invariante: com `storyboard.angles` resolvido em `None` (default de
  código), o texto dos prompts de ângulo é byte a byte igual ao de hoje; com preset configurado, o texto
  carrega o rig do preset e a resposta expõe `preset` e `preset_source`.
- **Um job por projeto preservado (ADR-006).** Invariante: nenhum registro de job novo é criado; a
  geração por cena reaproveita `angles.registry` (pago) e `local._local_registry` (grátis), ambos
  chaveados por `pid`, e devolve 409 quando já existe trabalho em andamento.
- **Paridade tela × agente.** Invariante: o que a tela faz por cena (gerar local, gerar via CLI com
  custo, escolher e ordenar) o agente faz por `storyboard_scene_generate` e `storyboard_scene_pick`, sem
  nenhuma tool importar `studio.storyboard.*` (ADR-037).

---

### 3. Escopo e exclusões

**Incluído**
- B1-local: campo `scene` opcional em `POST /api/projects/{pid}/storyboard/local/generate`; saída
  ingerida em `storyboard/<scene>/candidates/`; `scene` refletido no job.
- B1-CLI: ligação dos endpoints `angles/scenes/{scene}/{cost,generate,upscale}` no painel 05 de
  `Angles.tsx`, com `useCostConfirm` (custo antes) e `progressJob` (progresso honesto).
- B1-UX: os candidatos gerados (local ou CLI) caem na mesma galeria da cena e ganham o botão já
  existente "Usar como base da cena" (`Angles.tsx:565-575` → `POST …/scenes/{scene}/base`
  `{"source":"candidate","id":…}`).
- B2: tools MCP `storyboard_scene_generate(pid, scene, engine="local"|"cli", …)` e
  `storyboard_scene_pick(pid, scene)`, registradas no catálogo curado do `server.py` (ADR-040).
- B3: cena do produto (aula 013) com `angles/product/{cost,generate,upscale}` e geração local com
  `scene="product"`.
- Preset de realismo nos prompts de ângulos e da cena do produto, com registro idempotente de
  `storyboard.angles` em `PRESET_ACTIONS`.
- `image_prompt` exposto por cena em `GET …/angles/scenes` para pré-preencher o prompt da geração.
- Coleção Postman e README novos em `docs/domains/storyboard/postman/` cobrindo os contratos ligados
  (hoje a coleção `storyboard` tem zero ocorrências de `angles`; a coleção `docs/domains/shots/postman/
  shots.postman_collection.json` ainda usa o prefixo `/shots/` pré-ADR-015, 0 ocorrências de
  `storyboard/angles`).
- Testes: pytest (serviço, API, MCP) e Vitest (tela).

**Excluído**
- Qualquer alteração em `studio/etapas/storyboard/ui/Ideation.tsx` (metade ideação/cenas/roteiro,
  dona é a F06), inclusive o bloco `STYLE` escopado que vive nesse arquivo (`Ideation.tsx:2069+`).
- Migração de `angles.py` para o componente multishot do núcleo (ADR-017; as duas implementações
  seguem coexistindo, recon §0.3).
- Inpaint por máscara na cena (`POST …/local/inpaint` continua atendendo só a ideação).
- Vídeo/animação por cena (ADR-021/022, fora desta frente).
- Catalogar `storyboard.angles`/`storyboard.upscale` em `settings.ACTIONS` (é a F05).
- Registrar preset por foto ou por cena persistido em `scenes.json` (é a F06; F07 lê, não grava).
- Criar HLD do domínio storyboard (lacuna conhecida, recon §0.5; fora do escopo desta frente).
- Editar cenários existentes de `scripts/qa/cenarios/storyboard.py` (só acréscimo é permitido;
  `CLAUDE.md`, convenção 4 da Wave 10).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal 1: gerar a imagem da cena no motor local (grátis)**
1. O usuário abre a cena no painel 04; o painel 05 monta a barra de geração `[extensão]`.
2. A tela consulta `GET /api/projects/{pid}/storyboard/local/status` uma vez por montagem e guarda
   `ready`/`detail` (mesmo contrato do painel 01b, `motor-local-fdd.md` §5). Motor offline deixa o botão
   local desabilitado com o `detail` no `title`, sem erro.
3. O prompt é pré-preenchido, nesta ordem: `image_prompt` da cena vindo de `GET …/angles/scenes`
   (campo novo, vazio hoje), senão `image_prompt` da cena correspondente em `GET …/storyboard/script`
   (`script.json`, quando o roteiro por LLM foi usado), senão o `text` da cena. O usuário pode editar.
   `[auto-aceito: a leitura do prompt é defensiva e opcional em toda a cadeia, para F07 não depender da
   persistência de `image_prompt` que a F06 vai criar; sem nada disponível cai no texto da cena]`
4. "Gerar imagem da cena - local (grátis)" chama `progressJob` com
   `start: POST …/storyboard/local/generate {prompt, count, model, scene:"cenaNN"}`,
   `jobUrl: …/storyboard/local/job`, `done: recarregar candidatos da cena`.
5. O serviço valida a cena por `angles._resolve(pid, scene)` (sem exigir base), resolve
   `step = "storyboard/cenaNN"` e ingere cada resultado com `ingest.ingest_bytes(root, step, …,
   {"local_kind": "keyframe_local", "model": model, "scene": scene})`.
6. Terminado o job, a galeria da cena mostra os novos candidatos; "Usar como base da cena" promove um
   deles a `storyboard/cenaNN/base.png`, e a partir daí o Multi Shot pago da aula funciona igual.

**Fluxo principal 2: gerar ângulos da cena via CLI (gasta créditos)**
1. Com a base da cena preparada, o usuário monta o prompt no builder existente (`Gerar prompt` →
   `GET …/angles/scenes/{scene}/prompts?…`), que agora resolve o preset de realismo da ação
   `storyboard.angles` e devolve `preset`/`preset_source` junto dos prompts.
2. "Gerar via CLI (gasta créditos)" chama `useCostConfirm` em modo simples, com
   `costFn: POST …/angles/scenes/{scene}/cost {model, prompts, count, resolution}`; a planilha mostra o
   total estimado e o botão primário "Gerar".
   `[auto-aceito: modo simples (costFn com a rota `cost` real) em vez do modo rico por `action`, porque
   `storyboard.angles` só entra em `settings.ACTIONS` com a F05; o modo rico vira melhoria posterior]`
3. Confirmado, `progressJob` roda `start: POST …/angles/scenes/{scene}/generate`,
   `jobUrl: …/angles/job`, `done: recarregar candidatos e cenas`.
4. O serviço já existente barra CLI ausente/deslogado (409), base não preparada (409), `prompts` vazio
   ou `count` fora de 1..8 (422); grava o livro-caixa por chamada bem-sucedida
   (`settings.record_generation(action="storyboard.angles", …)`, `angles.py:476`).
5. "Upscalar 2x (gasta créditos)" repete o par custo → confirmação → job sobre o candidato selecionado
   (`POST …/angles/scenes/{scene}/upscale {id, model}`), com o ledger em `storyboard.upscale`
   (`angles.py:509`). O checkbox "já upscalei estes na UI" continua existindo para quem seguiu a aula.

**Fluxo principal 3: cena do produto (aula 013)**
1. O card "produto" do painel 04 continua exigindo a imagem 1 (`POST …/angles/product/ref`).
2. `GET …/angles/product/prompts` devolve as duas instruções da aula, agora com o preset resolvido.
3. Geração local: `POST …/storyboard/local/generate {prompt, count, model, scene:"product"}` (ingere em
   `storyboard/product/candidates/`, não exige `ref.png`).
4. Geração paga: `POST …/angles/product/cost` e `…/product/generate` com o mesmo par custo →
   confirmação; upscale por `…/product/upscale`. A regra da aula ("uma rodada por vez, a segunda sobre o
   resultado da primeira") continua no `ui_hint` do backend e no texto da tela.

**Fluxos alternativos e exceções**
- Caminho da aula preservado: o chip "N candidatos · M escolhidos" e o modal de importação
  (Downloads/histórico/upload) seguem intactos; o texto "gere na UI da Higgsfield e importe" continua
  visível na tela, agora ao lado dos dois atalhos.
- Motor local offline: 409 com `detail`; a tela desabilita só o botão local e mantém o CLI e a
  importação.
- CLI ausente ou deslogado: 409 de `hf.require_cli`; a tela desabilita só o botão pago e mantém o local
  e a importação.
- Job em andamento no mesmo projeto: 409 ("Já existe um trabalho em andamento para este projeto"), tanto
  no registro pago (`angles.registry`) quanto no local (`local._local_registry`). Decisão registrada em
  §12 (ADR-006 mantido, sem registro por cena).
- Cena sem base e geração paga: 409 "Prepare a base da cena"; a tela oferece o menu "base ▾" já
  existente e o caminho local, que não exige base.
- Sem interface (agente no terminal, sem `STUDIO_CHAT_ID`): `_paid` devolve o texto de custo e exige
  `confirm=true` na segunda chamada; `_pick` equivalente devolve a lista de ids para o usuário escolher
  por texto.

**Diagramas**
- Sequência sugerida (não obrigatória nesta frente): `docs/domains/storyboard/diagrams/mermaid/
  geracao-por-cena.mmd`, com as duas pontes (local grátis e CLI paga) convergindo na galeria da cena e
  em "Usar como base da cena". Se produzido, segue o padrão dos 7 `.mmd` já existentes do domínio.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Prefixo comum: `/api/projects/{pid}/storyboard`. `pid` inexistente devolve 404 pelo núcleo.
Content-Type `application/json` salvo onde indicado. **Todas as mudanças abaixo são aditivas**: nenhum
campo existente muda de nome, tipo ou semântica (regra do gate em lote sobre `frontend/src/api/schema.ts`).

---

**Contrato 1: geração local por cena**
- Tipo: endpoint (alteração aditiva de um endpoint existente)
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/local/generate`
- Método: POST
- Corpo: `LocalGenerateReq` ganha `scene: str | None = None`. Ausente ou `null` mantém o
  comportamento atual (ingestão em `storyboard/candidates/`, galeria de ideação). Valores aceitos:
  `cena01`..`cena99` presentes em `storyboard/scenes.json`, ou o literal `product`.
- Semântica de status:
  - 200: job iniciado (formato de job do studio, start devolve 200)
  - 404: `scene` fora de `scenes.json` (`LookupError`)
  - 409: motor local offline (`EngineUnavailable` → `Precondition`); job local em andamento para o `pid`;
    `storyboard/scenes.json` ausente
  - 422: `scene` fora do regex `^cena\d{2}$` e diferente de `product`; prompt vazio; `count` fora de
    `{1, 4}`; modelo de geração desconhecido
- Limites: `count ∈ {1, 4}` (regra da aula 007 preservada); um job local por projeto.

Exemplo de requisição
```json
{"prompt": "close-up on the astronaut walking through the blizzard, cinematic", "count": 4, "model": "flux-schnell", "scene": "cena01"}
```

Exemplo de resposta
```json
{"state": "running", "done": 0, "total": 4, "added": 0, "error": null, "log": [], "mode": "generate", "scene": "cena01", "result": null, "result_id": null}
```

---

**Contrato 2: job do motor local com a cena de destino**
- Tipo: endpoint (alteração aditiva)
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/local/job`
- Método: GET
- Semântica de status: 200 sempre (job `idle` inclusive); 404 se o `pid` não existe.
- Mudança: o dicionário de estado ganha `scene: str | null`, preenchido pelo `extras` do
  `JobRegistry.start`. `null` para os jobs de ideação (comportamento de hoje), o id da cena para os jobs
  por cena. A tela usa esse campo para só recarregar a galeria certa.

Exemplo de resposta
```json
{"state": "done", "done": 4, "total": 4, "added": 3, "error": null, "log": ["4/4 gerado localmente, 3 importadas"], "mode": "generate", "scene": "cena01", "result": null, "result_id": null}
```

---

**Contrato 3: cenas dos ângulos com o prompt de imagem**
- Tipo: endpoint (alteração aditiva)
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/angles/scenes`
- Método: GET
- Mudança: cada item de `scenes` ganha `image_prompt: str` (repasse defensivo de
  `scenes.json`; string vazia quando a chave não existe). Nenhum outro campo muda.
- Semântica de status: 200; 409 `storyboard/scenes.json` ausente.

Exemplo de resposta (recorte)
```json
{
  "warning": "Acerte cores e luz ANTES do multishot: as variações herdam o que a base tiver.",
  "scenes": [
    {"id": "cena01", "n": 1, "text": "close no astronauta andando na nevasca",
     "image_prompt": "A lone astronaut walking through a blizzard, wide shot, cold blue light",
     "primary": "storyboard/ideas/a1b2c3d4e5f6.png", "images": ["storyboard/ideas/a1b2c3d4e5f6.png"],
     "base": "storyboard/cena01/base.png", "base_ready": true, "candidates": 4, "selected": 2, "upscaled": 1}
  ],
  "product_scene": {"ref_ready": false, "selected": false}
}
```

---

**Contrato 4: prompts de ângulo com preset de realismo**
- Tipo: endpoint (alteração aditiva)
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/angles/scenes/{scene}/prompts`
- Método: GET
- Query nova: `preset` com três estados. Ausente resolve o default por
  `settings.preset_default_for("storyboard.angles", pid)` (projeto → global → código, hoje `None`);
  `preset=none` desliga o preset explicitamente nesta chamada; `preset=<id>` usa esse id do catálogo
  `prompter.REALISM_PRESETS`. As queries existentes (`kind`, `subject`, `scale`, `realism`, `lens`,
  `aperture`, `angle`, `edits`, `model`, `count`, `camera`) não mudam.
  `[auto-aceito: o literal `none` é a forma de expressar "null explícito" numa query string, espelhando
  a semântica de três estados de `settings.PresetUnset` usada nos bodies (roteiro-llm §5)]`
- Resposta: ganha `preset: str | null` e `preset_source: "project"|"global"|"code"|"request"`.
- Efeito no texto: com `preset` resolvido em `null` (default de código), o campo `text` é **byte a byte
  igual ao de hoje**. Com preset resolvido, o bloco de câmera manual (`_camera`, `angles.py:274-277`) é
  substituído pelo rig do preset (corpo, lente, formato, focal, abertura, luz dominante, color grade,
  fidelidade), composto dentro de `studio/storyboard/angles.py` a partir de `prompter.REALISM_PRESETS`.
  `[auto-aceito: a composição do bloco fica em `angles.py` e não em `studio/common/prompter.py`, para não
  colidir com a F06, que vai mexer em `ROLES` do prompter; a fonte dos valores continua sendo o catálogo
  único `REALISM_PRESETS`]`
- Semântica de status: 200; 404 cena desconhecida; 422 `kind=edit` sem `edits`, escala inválida ou
  `preset` fora do catálogo (`prompter.valid_preset`).

Exemplo de resposta (`?kind=angle&scale=close`, preset `red-commercial-precision` configurado no projeto)
```json
{
  "model": "nano_banana_2", "aspect_ratio": "16:9", "count": 4, "scene": "cena01",
  "preset": "red-commercial-precision", "preset_source": "project",
  "camera": null,
  "ui_hint": "Na Higgsfield: abra storyboard/cena01/base.png, use Multi Shot com este prompt.",
  "warning": "Acerte cores e luz ANTES do multishot.",
  "prompts": [
    {"label": "Outro ponto de vista (aula 011)",
     "text": "Bring me another point of view of this image. I want a close-up on the astronaut. Same scene, same lighting and colors. Shot on RED V-Raptor, Zeiss Supreme Prime, Large Format, 35-50mm, T4.0. Dominant light: clean controlled key, crisp speculars. Color grade: precise color, high micro-contrast, clean punchy look. Realistic."}
  ]
}
```

---

**Contrato 5: prompts da cena do produto com preset**
- Tipo: endpoint (alteração aditiva)
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/angles/product/prompts`
- Método: GET
- Query nova: `preset` com a mesma semântica de três estados do contrato 4 (`model` continua existindo).
- Resposta: ganha `preset` e `preset_source`; as duas instruções da aula 013 continuam nos mesmos
  rótulos e na mesma ordem, com o rig do preset anexado ao final de cada `text` quando houver preset.
- Semântica de status: 200; 409 sem `storyboard/product/ref.png`; 422 preset desconhecido.

---

**Contrato 6: tool MCP `storyboard_scene_generate`**
- Tipo: tool MCP (`mcp__studio__storyboard_scene_generate`), registrada ao final do bloco
  "4 Storyboard" de `studio/mcp/server.py`
- Assinatura:
```python
def storyboard_scene_generate(client: StudioClient, pid: str, scene: str, engine: str = "local",
                              prompt: str = "", count: int = 4, model: str = "",
                              confirm: bool = False) -> str
```
- Comportamento: `engine="local"` (default, grátis) chama
  `POST /api/projects/{pid}/storyboard/local/generate {prompt, count, model or "flux-schnell", scene}`,
  aplicando antes o prefixo de identidade do personagem (`_character_prefix`, ADR-039), como já faz
  `storyboard_local_generate`. `engine="cli"` (pago) passa obrigatoriamente por `_paid`, com
  `cost_path=/api/projects/{pid}/storyboard/angles/scenes/{scene}/cost`,
  `gen_path=…/generate`, `cost_body = gen_body = {model or "nano_banana_2", prompts:[prompt], count,
  resolution:"2k"}`, `action="storyboard.angles"`, `step=f"storyboard/{scene}"`. Prompt vazio no modo
  `cli` é resolvido antes por `GET …/angles/scenes/{scene}/prompts` (primeiro prompt da lista).
- Retorno (texto, exemplos exatos):
  - local: `"Imagem da cena cena01 sendo gerada no motor LOCAL (grátis) com flux-schnell. Acompanhe com `job_wait` (etapa storyboard)."`
  - cli confirmado: `"Geração iniciada (nano_banana_2). Acompanhe com `job_wait` (etapa storyboard/cena01)."`
  - cli sem interface e sem `confirm`: `"Custo estimado: 48 créditos (nano_banana_2). Para gerar, chame esta tool de novo com confirm=true."`
  - cli cancelado pelo usuário: `"Geração cancelada pelo usuário (custo estimado: 48 créditos)."`
  - engine inválido: `"engine inválido: <x> (use local ou cli)."`
  - erro da API (409/422): o `detail` do servidor devolvido como texto.

---

**Contrato 7: tool MCP `storyboard_scene_pick`**
- Tipo: tool MCP (`mcp__studio__storyboard_scene_pick`)
- Assinatura:
```python
def storyboard_scene_pick(client: StudioClient, pid: str, scene: str) -> str
```
- Comportamento: lê `GET /api/projects/{pid}/storyboard/angles/scenes/{scene}/candidates`, extrai a
  chave `candidates` do dicionário de resposta, monta as imagens com
  `_images_for(pid, f"storyboard/{scene}", cands)`, chama `ui.choose_images` (ADR-038, humano no laço) e
  grava com `POST …/angles/scenes/{scene}/select {"shots": [{"id": …}, …]}`, na ordem escolhida.
  `[auto-aceito: F07 não reescreve o helper `_pick` (que hoje trata a resposta como lista e é o alvo da
  F04); implementa a normalização localmente para não conflitar com a F04 na mesma sub-wave]`
- Retorno (texto): `"2 shot(s) escolhido(s) e ordenado(s) na cena cena01 (shot01_final.png, shot02_final.png)."`;
  sem candidatos: `"Nenhum candidato na cena cena01 ainda: gere (local ou CLI) ou importe antes de escolher."`;
  sem interface: `"Sem interface para escolher aqui. Candidatas disponíveis: <ids>. Diga quais escolher."`

---

**Contratos existentes ligados sem alteração** (só ganham chamador no frontend e no MCP; nenhuma mudança
de request, response ou status):
`POST …/angles/scenes/{scene}/cost`, `POST …/angles/scenes/{scene}/generate`,
`POST …/angles/scenes/{scene}/upscale`, `GET …/angles/job`,
`POST …/angles/scenes/{scene}/base` (`source=candidate`), `POST …/angles/scenes/{scene}/select`,
`POST …/angles/product/{cost,generate,upscale,select}`, `GET …/angles/product/candidates`.
Contratos e status estão em `docs/domains/shots/features/shots-fdd.md` §5 (com os nomes pré-ADR-015).

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Notas |
| --- | --- | --- |
| `pid` inexistente | 404 pelo núcleo (`refs.project_dir`) | sem código próprio |
| `scene` fora do regex `^cena\d{2}$` e diferente de `product` | `ValueError` → 422 | `angles._resolve`; barra path traversal |
| `scene` válida mas ausente de `scenes.json` | `LookupError` → 404 | `angles._resolve` |
| `storyboard/scenes.json` ausente | `FileNotFoundError` → 409 | mensagem "conclua as cenas da etapa 4" |
| Motor local offline (`engine` ausente ou ComfyUI fora) | `EngineUnavailable` → `Precondition` → 409 com `detail` | ADR-033; a tela desabilita só o botão local |
| Job local já em andamento no `pid` | `Precondition` → 409 | ADR-006, um job por projeto |
| Prompt vazio (local) | `Invalid` → 422 "Escreva o prompt (em inglês, aula 007)" | mensagem existente preservada |
| `count` fora de `{1, 4}` (local) | `Invalid` → 422 | regra da aula preservada |
| Modelo local desconhecido | `Invalid` → 422 | `le.GEN_MODEL_IDS` |
| CLI Higgsfield ausente ou deslogado | `hf.require_cli` → 409 | ADR-028 HIGGSFIELD; gate único da etapa |
| Base da cena não preparada em `generate`/`upscale` pago | `NotReady` → 409 "Prepare a base da cena" | caminho local não exige base |
| `prompts` vazio ou `count` fora de 1..8 (pago) | `ValueError` → 422 | `angles._check_gen` |
| Job de ângulos já em andamento | `RuntimeError` → 409 | `angles._start` |
| Candidato inexistente no upscale ou no `select` | `LookupError` → 404 / `ValueError` → 422 | `angles._candidate`, `select_shots` |
| `preset` fora do catálogo | `ValueError` → 422 | `prompter.valid_preset` |
| Download do resultado pago falha | 2 tentativas, depois segue o job com log; nada ingerido | `angles._fetch`, comportamento atual |
| Resultado idêntico a um candidato existente (SHA-1) | `ingest_bytes` devolve `None`; `added` não incrementa | dedupe do ingest; a tela avisa "sem mudança" |
| Usuário cancela no gate de custo | nenhum `POST` de `generate` parte; zero crédito | ADR-016 |

**Estratégias de resiliência.** Timeouts e retries continuam onde já vivem: 600 s por chamada de
`hf.generate`; duas tentativas de `hf.download` com `DOWNLOAD_RETRY_SLEEP`; polling de job pela
`progressJob` (funil único que também refresca o chip de créditos, ADR-016 §4). Nada de retry
automático em geração paga (evita gasto duplicado). Sem circuit breaker (processo local, ADR-001).

**Política de fallback.** As três pontes são independentes e nenhuma substitui a outra (ADR-033):
Higgsfield offline não afeta o local, o local offline não afeta o pago, e a importação manual da UI da
Higgsfield (caminho da aula) continua funcionando com as duas fora do ar.

**Invariantes**
- Sem `scene`, a geração local escreve exatamente onde escreve hoje (`storyboard/candidates/`).
- Com `scene`, todo byte gerado vai para `storyboard/<scene>/candidates/` e nunca para a galeria de
  ideação.
- Nenhum crédito é gasto sem `cost` consultado e confirmação humana.
- `storyboard/cenaNN/base.png` só muda por ação explícita do usuário ("Usar como base da cena" ou o
  menu "base ▾"); geração nunca sobrescreve a base sozinha.
- O texto dos prompts de ângulo é idêntico ao atual enquanto nenhum preset for configurado.
- Nenhum registro de job novo é criado (ADR-006).

---

### 7. Observabilidade

**Métricas** (derivadas dos artefatos já existentes, sem stack de métricas nova)
- Contadores por job: `done`, `total`, `added` no `GET …/angles/job` e `GET …/storyboard/local/job`.
- Créditos por cena: linhas do `spend-ledger.jsonl` com `action="storyboard.angles"` /
  `"storyboard.upscale"` e `step="storyboard"`, visíveis em `GET /api/creditos/history` e no
  `summary(pid)`.
- Cobertura da órfandade: teste que afirma que cada rota `angles/.../{cost,generate,upscale}` tem
  chamador em `Angles.tsx` (guarda contra regressão de desligamento).

**Logs**
- Já existentes e preservados: `log.info("shots pid=%s scene=%s op=generate model=%s prompts=%d
  count=%d prompt=%.120s")` e `op=upscale` (`angles.py:494`, `:528`); `log.info("local_job %s", {...})`
  (`local.py:75`).
- Acrescentado: a chave `"scene"` no dicionário de `local_job` (hoje `pid`, `mode`, `model`, `count`).
- Formato mantido: logger nomeado por módulo (`studio.storyboard.local`, `studio.storyboard.angles`),
  sem PII, sem prompt completo (truncado em 120 chars no caminho pago).

**Tracing.** Não há tracing distribuído (monólito single-process, ADR-001). O rastro por operação é o
`job_id` da Higgsfield gravado em `projects/<pid>/jobs/storyboard_<id>.json` (`_save_raw`) e o `job_id`
no ledger.

**Dashboards e alertas.** Mínimo: a própria tela de Créditos (`#/creditos`, `HistorySection`) filtrando
por `step="storyboard"`, e o `progressJob` como painel de progresso honesto durante a corrida. Sem
alerta automático (ferramenta local, um usuário).

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Higgsfield CLI oficial | a já exigida por `studio/higgsfield.py` | ADR-002; gate de login por `hf.require_cli` (ADR-028 HF) |
| Motor local `engine` + ComfyUI (Flux GGUF) | a já exigida por `studio/localengine.py` | ADR-033; ausência é 409, nunca 5xx |
| `studio/common/settings.py` (`PRESET_ACTIONS`, `preset_default_for`) | atual | chave `storyboard.angles` registrada por `setdefault` em import time |
| `studio/common/prompter.py` (`REALISM_PRESETS`, `valid_preset`) | atual | leitura apenas; F07 não edita o arquivo |
| `frontend/src/ui` (`progressJob`, `useCostConfirm`, `Modal`, `useUpload`) | atual | design system do núcleo, consumido sem alteração |
| `frontend/src/api/schema.ts` | regenerado | `make frontend-schema` por causa do campo `scene` no modelo Pydantic |
| `studio/web/dist/` | rebuild | `make frontend-build` e commit do bundle (guarda de drift do CI) |
| Feature F06 (storyboard-cenas) | mesma sub-wave | fornece `storyboard.angles` em `PRESET_ACTIONS` e `image_prompt` em `scenes.json`; F07 funciona sem ela (registro idempotente e leitura defensiva) |

**Garantias de compatibilidade**
- Todas as mudanças de contrato são aditivas: nenhum campo publicado em `frontend/openapi.json` /
  `schema.ts` é renomeado, removido ou tem o tipo alterado.
- `POST …/local/generate` sem `scene` é compatível byte a byte com os clientes atuais (painel 01b e tool
  `storyboard_local_generate`).
- Prompts de ângulo permanecem idênticos enquanto `storyboard.angles` resolver `None` (default de
  código, opt-in por ADR-004).
- Registro do preset por `setdefault`: se a F06 já registrou a chave (com outro default), F07 não
  sobrescreve; se F07 rebasear primeiro, a F06 encontra a chave posta e o `setdefault` dela é um no-op.
- `scripts/qa/cenarios/storyboard.py` não é editado; os casos existentes (inclusive `C-STORYBOARD-50`,
  que pina as rotas por API) continuam válidos, e novos casos podem ser acrescentados.

---

### 9. Critérios de aceite técnicos

1. `POST /api/projects/{pid}/storyboard/local/generate` com `scene="cena01"` cria candidatos em
   `projects/<pid>/storyboard/cena01/candidates/` e eles aparecem em
   `GET …/angles/scenes/cena01/candidates`; o mesmo POST sem `scene` continua criando em
   `storyboard/candidates/` (teste pytest com o motor local fakeado).
2. `scene` inválida devolve 422 (fora do regex) e 404 (cena inexistente em `scenes.json`), sem tocar o
   motor local.
3. `GET …/storyboard/local/job` devolve `scene: "cena01"` durante e depois de um job por cena, e
   `scene: null` para o job da ideação.
4. No painel 05 de `Angles.tsx` existem e funcionam: "Gerar imagem da cena - local (grátis)",
   "Gerar via CLI (gasta créditos)" e "Upscalar 2x (gasta créditos)"; os dois últimos abrem o
   `useCostConfirm` antes de qualquer `POST` de `generate`/`upscale` (teste Vitest com `api` fakeada
   afirmando a ordem `cost` → confirmação → `generate`).
5. Cancelar no gate de custo não dispara `generate` nem `upscale` (Vitest).
6. Com o motor local offline (`ready:false`), o botão local fica desabilitado com o `detail` no `title`
   e o botão do CLI continua habilitado; com o CLI indisponível, o inverso (Vitest).
7. O texto "gere na UI da Higgsfield e importe" e o fluxo de importação continuam presentes e
   funcionais na tela (assert de texto no Vitest; ADR-002/004).
8. Um candidato gerado pelo motor local na cena pode virar base pelo botão "Usar como base da cena"
   (`POST …/scenes/{scene}/base {"source":"candidate","id":…}` devolve 200 e `base_ready` vira `true`).
9. `GET …/angles/scenes/{scene}/prompts` sem preset configurado devolve `preset: null`,
   `preset_source: "code"` e `text` idêntico ao baseline atual (teste de igualdade contra a string de
   hoje); com `?preset=red-commercial-precision` devolve `preset_source: "request"` e o `text` contém o
   rig do preset; com `?preset=inexistente` devolve 422.
10. `GET …/angles/scenes` devolve `image_prompt` por cena (string vazia quando `scenes.json` não tem a
    chave).
11. `storyboard_scene_generate(engine="local")` chama a rota local com `scene` e devolve o texto de
    início; `engine="cli"` sem `confirm` e sem `STUDIO_CHAT_ID` devolve o texto de custo sem chamar
    `generate`; com `confirm=true` chama `cost` e depois `generate`, nessa ordem (teste com cliente HTTP
    fakeado, `tests/test_mcp_actions.py`).
12. `storyboard_scene_pick` lê a resposta em formato de dicionário (`{scene, base, candidates}`) sem
    erro, monta URLs `/files/{pid}/storyboard/cena01/candidates/thumbs/<sha12>.jpg` e posta em
    `…/select` no formato `{"shots":[{"id":…}]}`.
13. As duas tools aparecem em `studio/mcp/server.py` com descrição em pt-BR e nenhuma delas importa
    `studio.storyboard.*` (assert de ausência de import; ADR-037).
14. Cena do produto: `POST …/storyboard/local/generate {"scene":"product"}` ingere em
    `storyboard/product/candidates/`; os botões de custo/geração/upscale do produto estão ligados na
    tela.
15. Nenhum registro de job novo existe: `grep JobRegistry()` em `studio/storyboard/` continua devolvendo
    exatamente as ocorrências de hoje (ADR-006).
16. Coleção Postman `docs/domains/storyboard/postman/angles.postman_collection.json` cobre os contratos
    1 a 5 e os endpoints ligados, com README de execução; roda por newman quando disponível.
17. `make verify` e `make frontend-verify` verdes; `studio/web/dist/` e `frontend/src/api/schema.ts`
    regenerados e commitados; `tests/test_adr010_fronteira_nucleo.py` com a entrada da branch.
18. Os cenários existentes de `scripts/qa/cenarios/storyboard.py` continuam passando sem edição.
19. **[cross-feature, estado integrado]** Com o preset da campanha configurado pela F06 (por exemplo
    `PUT /api/projects/{pid}/prompter/presets` gravando `storyboard.angles`), `GET
    …/angles/scenes/{scene}/prompts` sem query devolve `preset` igual ao configurado,
    `preset_source: "project"` e o `text` carrega o bloco do preset correspondente. Evidência exigida na
    W5 (integração), não na worktree isolada.

---

### 10. Riscos e mitigação

### Risco 1: dois atalhos novos empurram o usuário para fora do método da aula (ADR-004)

- **Probabilidade:** média
- **Impacto:** a etapa deixa de reproduzir a aula 011 (gerar e upscalar na UI da Higgsfield) e vira um
  método próprio, que é exatamente o que os gates de fidelidade proíbem.
- **Mitigação:**
    - Manter o texto e o fluxo de importação da UI da Higgsfield como primeiro caminho visível da tela.
    - Rotular os dois botões novos com `[extensão]` no código e nos rótulos, com custo explícito
      ("grátis" e "gasta créditos").
    - Critério de aceite 7 afirma a permanência do caminho da aula.
- **Plano de contingência:** se o dono considerar poluição, os botões viram um submenu "atalhos
  `[extensão]`" fechado por padrão; o backend não muda.

### Risco 2: conflito de arquivo com a F06 (storyboard-cenas) na mesma sub-wave

- **Probabilidade:** alta
- **Impacto:** rebase doloroso em `studio/etapas/storyboard/router.py`, `studio/mcp/{actions,server}.py`
  e `studio/common/settings.py`.
- **Mitigação:**
    - F07 só acrescenta blocos, sempre ao final da seção correspondente (`# ---------- CLI: custo,
      geração, upscale, job ----------` e o bloco `local`), como manda `wave-11.md` §Conflitos.
    - Zero edição em `Ideation.tsx` (inclusive no bloco `STYLE`): a barra nova reaproveita as classes já
      existentes (`row wrap sh-builder`, `field`, `eyebrow lbl`, `primary`, `ghost`).
    - Registro do preset por `settings.PRESET_ACTIONS.setdefault("storyboard.angles", None)`, idempotente
      nos dois sentidos do rebase.
    - Tools registradas ao final do bloco "4 Storyboard" do `server.py`.
- **Plano de contingência:** ordem de integração da wave já coloca F07 antes de F06 (`wave-11.md`
  §Ordem de integração); se o conflito ainda ocorrer, `dist/` e `schema.ts` são regenerados, nunca
  resolvidos à mão.

### Risco 3: gasto acidental de créditos

- **Probabilidade:** média
- **Impacto:** crédito real queimado sem intenção; a geração paga é serial (`prompts × count`
  chamadas de 600 s).
- **Mitigação:**
    - Gate de custo obrigatório antes de `generate` e de `upscale` (ADR-016), com o total estimado.
    - O botão local (grátis) é o primeiro da barra e o default visual.
    - `_paid` no caminho do agente, com `confirm=true` explícito quando não há interface.
    - Critério de aceite 5 (cancelar não dispara nada).
- **Plano de contingência:** o `count` default da tela fica em 1 para o caminho pago, e o total estimado
  aparece no rótulo do botão primário.

### Risco 4: um job por projeto (ADR-006) trava a geração por cena

- **Probabilidade:** média
- **Impacto:** usuário pede a cena 2 enquanto a cena 1 roda e recebe 409, sem entender.
- **Mitigação:**
    - Decisão registrada: nenhum registro por cena; `angles.registry` e `local._local_registry` seguem
      chaveados por `pid` e já carregam `scene`/`op` nos extras.
    - A tela mostra a cena em execução (campo `scene` do job) e desabilita os botões das outras cenas
      com o motivo no `title`.
    - Motivo técnico adicional: `studio/common/reset.py::_registries` descobre registros por uma lista
      fechada de atributos de `studio.<step>.service`; registros novos por cena ficariam invisíveis ao
      reset da etapa e criariam vazamento de estado.
- **Plano de contingência:** se o dono pedir paralelismo por cena, isso vira ADR próprio (revisão do
  ADR-006) e uma frente separada, incluindo o ajuste do `reset.py`.

### Risco 5: `storyboard.angles` grava no ledger sem estar em `settings.ACTIONS`

- **Probabilidade:** alta (é o estado de hoje, recon §5)
- **Impacto:** o modo rico do `useCostConfirm` e o `POST /api/creditos/spend` rejeitam a ação não
  catalogada; a planilha de custo do painel ficaria vazia.
- **Mitigação:**
    - F07 usa o modo simples do `useCostConfirm`, com `costFn` batendo na rota `cost` real dos ângulos
      (que existe e é testada), sem depender do catálogo.
    - A correção do catálogo é da F05 (creditos-actions-catalog), com teste de cobertura "toda ação
      gravada no ledger está no catálogo".
- **Plano de contingência:** depois da integração da F05, trocar `costFn` pelo modo rico (`action:
  "storyboard.angles"`) em um follow-up de uma linha.

### Risco 6: ingestão em `step` com subpasta (`storyboard/cena01`) no caminho local

- **Probabilidade:** baixa
- **Impacto:** arquivos gerados caindo no lugar errado ou erro de path.
- **Mitigação:**
    - O caminho pago dos ângulos já usa exatamente esse `step` (`angles._step_of`, `ingest.ingest_bytes`
      com `storyboard/cena01`), então o suporte está provado em produção e coberto por
      `tests/test_storyboard_angles_service.py`.
    - Teste explícito do caminho local por cena (critério 1), afirmando o diretório de saída.
- **Plano de contingência:** se o `ingest` recusar algum caso, a validação do `scene` acontece antes de
  qualquer chamada ao motor (422/404), sem efeito colateral em disco.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Geração local por cena (serviço + rota + job) | - | `studio/storyboard/local.py`, `studio/etapas/storyboard/router.py` (bloco `local`) | 1, 2, 3 |
| 2 | Preset de realismo nos prompts de ângulo e do produto | - | `studio/storyboard/angles.py` (`build_prompts`, `product_prompts`, registro `setdefault`), `studio/etapas/storyboard/router.py` (bloco ângulos) | 9 |
| 3 | `image_prompt` por cena em `GET angles/scenes` | 2 | `studio/storyboard/angles.py` (`list_scenes`) | 10 |
| 4 | Testes de backend | 1, 2, 3 | `tests/test_storyboard_local.py`, `tests/test_storyboard_angles_api.py`, `tests/test_storyboard_angles_service.py` | 1, 2, 3, 9, 10 |
| 5 | Tela: barra de geração por cena (local, CLI, upscale) e cena do produto | 1, 2, 3 | `studio/etapas/storyboard/ui/Angles.tsx`, `studio/etapas/storyboard/ui/types.ts` | 4, 5, 6, 7, 8, 14 |
| 6 | Testes da tela | 5 | `studio/etapas/storyboard/ui/Angles.test.tsx` (novo) | 4, 5, 6, 7 |
| 7 | Tools MCP por cena | 1, 2 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `studio/chat/prompts/sistema.md` | 11, 12, 13 |
| 8 | Testes do MCP | 7 | `tests/test_mcp_actions.py` | 11, 12, 13 |
| 9 | Coleção Postman e README dos ângulos | 1, 2, 3 | `docs/domains/storyboard/postman/angles.postman_collection.json`, `angles.README.md`, `angles.postman_environment.json` | 16 |
| 10 | Núcleo, build e schema | 5 | `tests/test_adr010_fronteira_nucleo.py` (entrada da branch), `frontend/src/api/schema.ts` (gerado), `studio/web/dist/**` (gerado) | 17 |
| 11 | Notas de documentação viva | 1..10 | `docs/domains/shots/features/shots-fdd.md` (nota: rotas deixam de ser órfãs), `docs/domains/storyboard/features/motor-local-fdd.md` (nota do campo `scene`), `docs/domains/storyboard/postman/divergencias.md` | 15, 18 |

**Prefixos de núcleo que a frente declara em `TITULARES_DO_NUCLEO`** (`tests/test_adr010_fronteira_nucleo.py:72`):
`("frontend/", "studio/web/")`. Recorte mínimo: em `frontend/` muda **apenas o arquivo gerado**
`frontend/src/api/schema.ts` (regenerado por causa do campo `scene` no modelo Pydantic
`LocalGenerateReq`); em `studio/web/` muda **apenas o bundle gerado** `studio/web/dist/`. Nenhuma fonte
do shell, do design system ou de outra área é tocada. A UI da etapa
(`studio/etapas/storyboard/ui/**`) está fora de `NUCLEO_PREFIXOS` e não exige titularidade.

**Contagem para a decisão direta × SDD**

Contratos (seção 5): 7
Fluxos principais (seção 4): 3
Arquivos previstos: 20

Regra da wave (direta se ≤3 contratos E 1 fluxo E ≤8 arquivos): **não atende**. A frente vai por
**SDD/Compozy**, com as tarefas decompostas a partir da tabela acima: T1 B1-local (ordens 1 e 4 parciais),
T2 preset + `image_prompt` (ordens 2, 3 e 4 parciais), T3 B1-CLI na tela (ordens 5 e 6), T4 B3 cena do
produto (fatia das ordens 5 e 6), T5 tools MCP (ordens 7 e 8), T6 Postman (ordem 9), T7 núcleo/build e
notas de docs (ordens 10 e 11).

Lista dos 20 arquivos previstos: `studio/storyboard/local.py`; `studio/storyboard/angles.py`;
`studio/etapas/storyboard/router.py`; `studio/etapas/storyboard/ui/Angles.tsx`;
`studio/etapas/storyboard/ui/types.ts`; `studio/etapas/storyboard/ui/Angles.test.tsx` (novo);
`studio/mcp/actions.py`; `studio/mcp/server.py`; `studio/chat/prompts/sistema.md`;
`tests/test_storyboard_local.py`; `tests/test_storyboard_angles_api.py`;
`tests/test_storyboard_angles_service.py`; `tests/test_mcp_actions.py`;
`tests/test_adr010_fronteira_nucleo.py`; `frontend/src/api/schema.ts` (gerado);
`studio/web/dist/**` (gerado); `docs/domains/storyboard/postman/angles.postman_collection.json` (novo);
`docs/domains/storyboard/postman/angles.postman_environment.json` (novo);
`docs/domains/storyboard/postman/angles.README.md` (novo);
`docs/domains/shots/features/shots-fdd.md` (nota de estado).

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas** (todas rotuladas no ponto em que aparecem)

1. `[auto-aceito]` §4, fluxo 1, passo 3: a leitura do prompt da cena é defensiva e opcional em toda a
   cadeia (`image_prompt` de `scenes.json` → `image_prompt` de `script.json` → `text` da cena), para F07
   não depender da persistência que a F06 vai criar.
2. `[auto-aceito]` §4, fluxo 2, passo 2: gate de custo em **modo simples** (`costFn` batendo na rota
   `cost` real dos ângulos), porque `storyboard.angles` só entra em `settings.ACTIONS` com a F05. Fonte:
   recon §5 (ações gravadas fora de `ACTIONS`) e §0.6 (F05 é a dona).
3. `[auto-aceito]` §5, contrato 4: `preset=none` como forma de expressar "null explícito" numa query
   string, espelhando os três estados de `settings.PresetUnset` já usados nos bodies do roteiro por LLM.
4. `[auto-aceito]` §5, contrato 4: a composição do bloco de preset vive em `studio/storyboard/angles.py`
   (lendo `prompter.REALISM_PRESETS`), não em `studio/common/prompter.py`, para não colidir com a F06,
   que vai mexer em `ROLES` do prompter. Catálogo continua único.
5. `[auto-aceito]` §5, contrato 7: `storyboard_scene_pick` normaliza a resposta localmente em vez de
   editar o helper `_pick` de `studio/mcp/actions.py`, que é o alvo da F04 na mesma sub-wave.
6. `[auto-aceito]` §2 e §10 (risco 4): **nenhum registro de job por cena**. ADR-006 mantido; motivo
   técnico adicional é `studio/common/reset.py::_registries`, que descobre registros por uma lista
   fechada de atributos e não enxergaria registros novos. Decisão a registrar como nota, não como ADR
   novo (o card pedia "avaliar e registrar a decisão").
7. `[auto-aceito]` §3 e §10 (risco 2): zero edição em `Ideation.tsx`, inclusive no bloco `STYLE`
   escopado da tela; a barra nova reaproveita apenas classes já existentes do catálogo.
8. `[auto-aceito]` §5: registro do preset por
   `settings.PRESET_ACTIONS.setdefault("storyboard.angles", None)` em import time no módulo da própria
   frente, seguindo o precedente de `studio/storyboard/service.py:1166` (`storyboard.script`), sem
   editar `studio/common/settings.py`. Default `None` porque nenhuma aula ensina presets (ADR-004).

**Pendências para o gate em lote** (nunca auto-aceitas)

- **P1: substituição do bloco de câmera manual pelo rig do preset.** Quando o usuário configura um
  preset para `storyboard.angles`, o texto do prompt de ângulo deixa de trazer o bloco
  `_camera(lens, aperture, scale, angle, camera)` e passa a trazer o rig do preset. É opt-in (com o
  default `None` nada muda) e a forma da resposta é aditiva, mas o **texto de um contrato existente**
  muda sob configuração do usuário. Recomendação: aprovar como está, porque o preset e o bloco manual
  descrevem a mesma coisa e somá-los produziria instruções de câmera contraditórias. Alternativa se o
  gate preferir o caminho mais conservador: **anexar** o bloco do preset ao final do texto atual e
  manter o bloco manual, aceitando a redundância.
- **P2: `storyboard.angles` e `storyboard.upscale` gravam no livro-caixa sem estar em
  `settings.ACTIONS`.** É o estado de hoje (recon §5) e a correção pertence à F05. F07 contorna com o
  modo simples do gate de custo (auto-aceite 2). Confirmar na integração (W5) que a F05 cobriu as duas
  ações; caso não cubra, a planilha rica dos ângulos fica pendente para uma frente futura.
