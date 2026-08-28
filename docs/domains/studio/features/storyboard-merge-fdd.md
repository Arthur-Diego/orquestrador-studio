### FDD: storyboard-merge — unir a etapa 5 (Ângulos por cena) na etapa 4 (Storyboard)

Task-Id: ADH-OS-20260827-10 · Domínio: studio (storyboard + shots + animate + steps) · Base: `develop@43844f4`
Pedido do dono (27/08/2026): "o storyboard precisa ser mais flexível: as cenas podem conter mais de
uma foto (duram mais que uma foto); poder upar imagens com diferentes ângulos geradas a partir da
imagem-base." Decisões (em lote): (1) **unir tudo na etapa 4** — o Storyboard vira o lugar único:
cada cena = texto + VÁRIAS imagens (upload de ângulos + escolher/ordenar); a etapa 5 é **absorvida/
removida** (pipeline com uma etapa a menos); (2) adicionar ângulos = **upload + ajuda de prompt**
(o Studio sugere "outro ponto de vista desta cena a partir da base" para gerar na Higgsfield e importar).

### 0. Fidelidade (ADR-004) — `[extensão]` que reescreve o pipeline

O curso separa aula 010 (storyboard: ideação + cenas em texto) e aula 011 (ângulos por cena). O dono
optou por unir numa etapa só. É `[extensão]`. **Criar ADR-015** registrando a fusão (a etapa 4 passa
a cobrir aulas 010 **e** 011; a etapa 5 sai do pipeline) e superseder/complementar o que a
`shots-*`/ADRs de shots diziam. Atualizar índice `docs/adrs/README.md` e a nota de status do protótipo
(a tela 05-shots deixa de existir; as telas seguintes renumeram).

### 1. Modelo novo da cena (etapa 4)

Hoje: `scenes.json` = `[{id, n, text, image}]` (1 imagem). Novo: cada cena carrega VÁRIAS imagens/
ângulos, escolhidas e ordenadas, além do texto. Reaproveitar o que a etapa 5 (shots) já faz — é
exatamente isto: `shots/cenaNN/base.png` (base da cena = imagem de ideação ou `base/base_final.png`),
candidatos importados, `_final.png` selecionados e ordenados, e a cena extra do produto (aula 013).

Estratégia recomendada (MENOR risco): **mover o serviço `studio/shots/` para dentro do domínio da
etapa 4** (ou fazer o `storyboard` importar/absorver suas funções), preservando o SCHEMA de saída que
o `animate` lê. Concretamente:
- A etapa 4 mantém o texto das cenas (`scenes.json`) E ganha, por cena: base da cena, importar
  (upload/Downloads/histórico), **prompt de ângulo** ("another point of view … from the base"),
  gerar via CLI (opcional, pago) OU importar do Higgsfield, escolher/ordenar frames, upscale, e a
  cena do produto (aula 013).
- Saída para o animate: manter o SCHEMA atual `{scenes:[{id, base, shots:[{scene,shot,order,image,
  scene_prompt,...}]}], product_scene}`. **Mover o arquivo** de `shots/storyboard.json` para
  `storyboard/storyboard.json` e atualizar o `animate._storyboard_file()` (uma linha) + o caminho das
  imagens (`videos/`/`shots/` → decidir: manter as imagens em `storyboard/cenaNN/…` e ajustar o
  animate para ler o novo `base`/`image`). Alternativa de risco menor: manter a pasta física de saída
  como está e só reapontar a etapa — o subagente escolhe o caminho que mantém `animate` funcionando
  com o mínimo de mudança, DESDE QUE `make verify` fique verde.

### 2. Pipeline (`studio/steps.py`) — uma etapa a menos

- Remover a entrada `shots` do `SOON`; renumerar: `animate` n=5, `music` 6, `edit` 7, `export` 8,
  `publish` 9, `prospect` 10 (auals inalteradas: animate=012, music=013, …). A etapa 4 (storyboard)
  passa a citar aulas **010+011** e a descrição vira "cenas em texto + vários ângulos por cena".
- Remover o plugin `studio/etapas/shots/` (absorvido). O backend de shots vira parte da etapa 4
  (mover para `studio/storyboard/` ou `studio/etapas/storyboard/`), sem perder capacidade.
- Rotas: as `/api/projects/{pid}/shots/...` passam a viver sob a etapa 4 (renomear para
  `/storyboard/...` OU manter compatibilidade — o subagente decide, mas a TELA da etapa 4 deve usar
  as novas). O `animate` só depende do arquivo de saída, não das rotas.

### 3. Frontend (etapa 4)

Tela única com: (a) ideação a partir da base (o que a etapa 4 já tem: instrução Draw to Edit/edição/
Multi Shot + importar ideias) — manter; (b) as cenas (texto) — manter; (c) por cena: base da cena +
**várias imagens/ângulos** (upload + o prompt de ângulo sugerido para gerar no Higgsfield e importar;
gerar via CLI opcional com custo/`progressJob`), escolher e **ordenar** os frames; (d) cena do
produto (aula 013). Reusar os componentes visuais que a etapa 5 já tinha (galerias, `.rowcard`,
ordenação) — mova o view da etapa 5 para dentro da etapa 4.

### 4. Testes e scripts

- Mover/reescrever `tests/test_shots_*` para a etapa 4; atualizar `tests/test_animate_*` (novo caminho
  de storyboard), `tests/test_api.py` (catálogo: 10 etapas, sem `shots`, renumeração), `test_storyboard_*`
  e o guia. Atualizar `scripts/e2e_pipeline.py` e `scripts/crossfeature_wave1.py` (não pollam mais a
  etapa 5 isolada; a etapa 4 produz os frames que o animate lê). O E2E deve rodar 1→10 verde.
- `make verify` verde (o baseline muda por remoção de etapa — justificar a variação de contagem; não
  perder cobertura, só reagrupar).

### 5. Verificação

- `make verify` verde; `scripts/e2e_pipeline.py` verde (1→10, incluindo cenas com ≥2 imagens e o animate
  lendo os frames da etapa 4).
- Smoke Playwright: etapa 4 com uma cena tendo ≥2 imagens (upload), o prompt de ângulo aparece, e a
  etapa 6 (animate, agora n=5) monta o plano a partir disso. 0 erro; dark+light. Prints fora do git.

### 6. Regras de segurança

- Se não conseguir manter `make verify` verde ou o `animate` lendo os frames, PARAR e reportar em vez
  de deixar o pipeline quebrado. Preferir reusar o serviço de shots a reescrever do zero.
- Não tocar em `studio/base/*`/`studio/etapas/base/*` (outra frente em paralelo mexe lá).

### 7. Fora de escopo

- Mudar as etapas 6–10 além da renumeração e do caminho de leitura do animate.
