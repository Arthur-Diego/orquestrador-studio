# PRD — Inpaint por marcação na etapa 4 (`edit_area`) `[extensão]`

Task-Id: `ADH-OS-20260830-02` · Card da wave: <https://trello.com/c/T53Hnvlv> · Wave 9, sub-wave 1, frente **inpaint-marcacao**
TechSpec normativa: `_techspec.md` (FDD aprovado em lote, gate W3 do `dd-parallel`).
Fontes de produto: `docs/domains/storyboard/prd.md` (subseção `[extensão]` Wave 9 — Inpaint por marcação),
`docs/domains/studio/waves/wave-9.md` (contratos e resolução das pendências P1/P2/P3),
`docs/domains/studio/recon-wave-9.md` (terreno).

## 1. Problema

A aula 010 do curso cita "Inpaint para ajustes localizados", mas esse gesto acontece na interface da
Higgsfield: o usuário marca a região sobre a imagem e descreve a mudança. O CLI oficial
(`hf.generate`, ADR-002) **não aceita máscara**, então hoje o Studio só oferece o inpaint como preset
de texto (`"Inpaint: corda proporcional"`, kind `edit`) — o usuário descreve a região em palavras e
torce. Falta o gesto: marcar a área na própria imagem, dentro do Studio.

## 2. Usuário e valor

Usuário: o dono do projeto, single-user local (ADR-001), na etapa 4 (storyboard), refinando uma
imagem base ou uma ideia gerada. Valor: aproximar o gesto da aula sem sair do método — o usuário
rabisca a região, escreve uma instrução, e o Studio manda a marcação como referência EXTRA para o
modelo, com instrução fixa em inglês pedindo para mudar só ali.

## 3. Requisitos de produto

1. **Canvas de marcação na SPA.** Modal reutilizável (`studio/web/annotate.js`, padrão do
   `web/multishot.js`) com pincel vermelho, espessura ajustável, desfazer e limpar; exporta o PNG
   achatado (imagem original + traços) na mesma resolução da original.
2. **Marcação persistida no projeto.** O PNG anotado é salvo via `ingest_bytes` com
   `meta {role:"annotation", parent}`; **nunca** aparece como ideia na galeria nem pode ser
   selecionada como imagem de cena. Reenvio do mesmo conteúdo é idempotente (dedupe SHA-1).
3. **Modo de edição "área marcada"** (`kind="edit_area"`) no fluxo de edição iterativa da etapa 4:
   a imagem ORIGINAL vai **primeira** em `image_references`, a anotada entra como referência extra,
   e o servidor monta a instrução fixa em inglês (seção 5 do `_techspec.md`) envolvendo a instrução
   única do usuário.
4. **Fluxo pago obrigatório** (ADR-016): `cost` no servidor → `Studio.ui.confirmCost` → job com
   polling → `record_generation` com a ação nova `storyboard.inpaint` após cada geração bem-sucedida.
   Registro de gasto **só** no modo novo (pendência P1 resolvida no gate: kinds antigos ficam fora).
5. **Limite declarado na UI.** Rótulo `[extensão]` no modo e aviso fixo de que é aproximação
   **best-effort por prompt**, não inpaint real com máscara. O preset de texto da aula permanece
   intocado e convive com o modo novo.
6. **Configuração por ação** (ADR-016): `storyboard.inpaint` entra em `ACTIONS`/`DEFAULTS`
   (`nano_banana_2` / `2k`), resolvido por `default_for` (projeto → global → código) e listado no
   painel "Créditos & Custos" sem mudança de tela.

## 4. Fora de escopo

- Inpaint real com máscara (o CLI não suporta; ADR-002 proíbe outros caminhos).
- Qualquer edição de `studio/app.py`, `studio/steps.py`, `studio/web/index.html`,
  `studio/web/app.js`, `studio/web/ui.js`, `studio/web/multishot.js` (ADR-010) — o arquivo novo
  `studio/web/annotate.js` é servido pelo mount `/static` já existente.
- Mudança em rotas, campos, kinds, mensagens ou schemas existentes (`scenes.json`,
  `candidates.json`): tudo é aditivo.
- Uso do canvas por outras etapas nesta entrega.
- Retroagir `record_generation` aos kinds antigos (`edit`/`multishot`).

## 5. Sucesso

- O usuário marca uma região, gera 4 variações e escolhe uma, sem sair da etapa 4 e sem que a
  marcação polua a galeria de ideias.
- No fake de `hf.generate`, `params.image_references` tem exatamente 2 itens com a original
  primeira, e `params.prompt` é a instrução fixa com a instrução do usuário interpolada.
- `index.html`, `app.js`, `app.py`, `steps.py`, `ui.js`, `multishot.js` sem diff; `make verify`
  verde; testes novos sem rede e sem navegador (fakes de `hf.*`, ADR-008).

## 6. Restrições do repositório

- Python 3.12 · FastAPI · sem banco (arquivos em `projects/<pid>/`); frontend estático sem build.
- Etapas são plugins (`studio/etapas/<id>/`); geração só via CLI oficial da Higgsfield (ADR-002).
- Documentação e PR em pt-BR; prompts de geração em inglês (aula 007).
- Commits com trailer `Task-Id`; `make verify` = ruff + pytest.
