### FDD: base-cli-generation — gerar a imagem-base via CLI (custo, download, antes/depois, Higgsfield)

Task-Id: ADH-OS-20260827-09 · Domínio: studio (etapa base) · Base: `develop@43844f4`
Pedido do dono (27/08/2026): na etapa 3 (imagem-base), poder GERAR via CLI os passos 01 situação,
02 rótulo (marca) e 03 upscale 2x; mostrar o CUSTO em crédito antes (o upscale custa diferente da
geração — modelos distintos); assim que gerar, mostrar DOWNLOAD e a MODIFICAÇÃO (antes/depois); e
deixar claro que a etapa também pode ser feita no Higgsfield (UI ilimitada).

### 0. Estado atual (verificado)

O backend já suporta tudo: `POST base/generate` (kind ∈ situation|label|upscale), `POST base/cost`
(estimativa REAL via `higgsfield generate cost <modelo>`), `GET base/job`. Modelos:
situação/rótulo=`nano_banana_2`, upscale=`bytedance_image_upscale` (custo diferente). MAS a TELA
(redesign wave 4) NÃO expõe geração por CLI — só importar. Esta feature re-adiciona a geração por
CLI na tela — é `[extensão]` (a wave 4 removeu por fidelidade ao protótipo; o dono aprovou re-adicionar).

### 1. Frontend (`studio/etapas/base/view.*`, shell — ADR-010)

Em cada um dos 3 passos (situação, rótulo, upscale), além de "importar do Higgsfield", adicionar
**"Gerar via CLI [extensão]"**:
- Antes de gerar: chamar `POST base/cost` e mostrar o custo (`total`/`per_item` créditos) num
  `Studio.ui.confirmCost` — como o upscale usa outro modelo, o número aparece por passo. Se o CLI
  NÃO estiver logado (`credits: null` + erro "No workspace selected"), mostrar aviso claro
  ("Faça login no Higgsfield para gerar via CLI e ver o custo") e manter o caminho de importação.
- Durante a geração: `Studio.ui.progressJob({ start: POST base/generate, jobUrl: base/job })` (o
  modal de progresso já existe) mostrando o log real.
- Depois de gerar: os resultados entram como candidatos (fluxo `afterImport` já existe). ADICIONAR:
  - **Download**: botão/ação de baixar cada imagem gerada (link para `/files/{pid}/<caminho>` com
    atributo `download` — funciona no app real). 
  - **Antes/depois**: mostrar a MODIFICAÇÃO — a imagem de origem da cadeia (situação→rótulo→upscale;
    ver `_selected`/`upscale_ratio`) ao lado do novo resultado, rotulado "antes → depois".
- **Deixar explícito**, em cada passo, uma linha: "Você também pode fazer no Higgsfield (UI
  ilimitada): gere lá e importe aqui." (o CLI é o caminho pago; o Higgsfield é o ilimitado).
- Não remover o fluxo de importação nem o prompt/junção da feature anterior.

### 2. Backend

- Reusar `base/cost`, `base/generate`, `base/job` (já existem para os 3 kinds). Garantir que `cost`
  devolva `{per_item,total,raw}` e trate CLI deslogado (credits null + error) sem 500.
- ~~Para o "antes/depois": expor, no retorno do job/candidatos ou num helper, a imagem de ORIGEM de
  cada resultado (a candidata selecionada da cadeia: upscale←label←situação) para a UI parear.
  `upscale_ratio()` já dá origem/destino do upscale; generalizar para os 3 kinds se necessário.~~
  **FECHADO em 2026-09-06** pela frente F11 da Wave 11 (`base-upscale-chat-fdd.md`, Task-Id
  ADH-OS-20260906-13, card #94): a origem virou o campo persistido `source_id` na candidata
  (`studio/base/service.py::source_candidate`, generalizado para os 3 kinds derivados) e o job passa
  a devolver `new_candidates: [{id, kind, thumb_url, file_url, source_id}]`
  (`studio/base/service.py::new_candidates`, injetado por `job_status`). A tela deixou de inferir a
  origem no cliente e passou a ler o campo do servidor.
- Endpoint de download não é preciso (os arquivos já são servidos por `/files/{pid}/...`); a UI usa
  `<a download>`.

### 3. Custos (o que responder ao usuário)

O custo real vem de `higgsfield generate cost <modelo>` — só com CLI logado. Geração
(`nano_banana_2`) e upscale (`bytedance_image_upscale`) têm custos DIFERENTES. A UI mostra o número
por passo antes de pagar. (Se logado, o valor aparece; se não, aviso.)

### 4. Testes

- `tests/test_base_api.py`: a tela tem "Gerar via CLI" nos 3 passos + o aviso "pode ser feito no
  Higgsfield"; `base/cost` responde para os 3 kinds (mockar `hf.cost`); download presente; a visão
  antes/depois existe. Não reduzir baseline (743).
- Preservar as asserções da wave 4 na base (painéis 01/02/03, painel M, sem 04, sem details.lesson)
  e a junção mood×referência (#57): o "Gerar via CLI" entra DENTRO dos passos existentes, sem criar
  um painel novo que quebre a contagem — se precisar, ajuste a asserção justificando.

### 5. Verificação

- `make verify` verde.
- Smoke Playwright (mockar `hf` se preciso, ou só provar a UI): os botões "Gerar via CLI [extensão]"
  aparecem nos 3 passos com aviso de custo; a linha "pode ser feito no Higgsfield" aparece; após um
  import/geração, o download e o antes/depois aparecem. 0 erro console; dark+light. Prints fora do git.

### 6. Fora de escopo

- Logar o Higgsfield (é ação do usuário: `higgsfield auth login` + `hf workspace set`).
- Mudar os modelos/custos (vêm do catálogo vivo do CLI).
