# PRD: storyboard (OS-004) · Etapa 4 · Storyboard · aula 010

Data: 2026-08-25 · Wave 1 (`docs/domains/studio/waves/wave-1.md`) · Modo batch (auto-aceite, revisão em lote na W5)

## Em uma frase (gate 5 do CLAUDE.md)
A aula 010 pega a imagem base da campanha, tem ideias de cena desenhando e editando sobre ela (uma instrução por vez) e termina com a história escrita em 5 cenas; a etapa produz `storyboard/scenes.json` (5 cenas editáveis, cada uma com texto e imagem de ideação opcional), `storyboard/ideas/` + `ideas.json` e `storyboard/storyboard.md`.

## Problema
Depois da imagem base (etapa 3) o aluno precisa decidir o que acontece no vídeo. A aula ensina um método concreto de ideação visual e de roteiro curto; sem a etapa, o usuário faz isso em Google Docs e perde o handoff estruturado que a etapa 5 (shots) exige.

## O que a aula 010 manda (fonte de verdade)
1. Draw to Edit: o usuário desenha a ideia sobre a imagem base na UI da Higgsfield; o Studio entrega a instrução textual que acompanha o desenho.
2. Edições iterativas com UMA instrução por vez, simples ("faça o alpinista ainda menor e mais realista", "elimine o pequeno personagem da parte direita"). Gerar 4 quando incerto, 1 quando é tweak.
3. Multi Shot para experimentar ângulos e ter mais ideias; Inpaint para ajustes localizados.
4. Escrever a história em ~5 cenas em texto ("cena 1: close no astronauta andando na nevasca…").
5. Storyboard em documento (Google Docs na aula; aqui `storyboard.md` local, troca de ferramenta permitida pelo gate 3).

## Usuários e cenário
Usuário único, local (ADR-001). Gera imagens na interface da Higgsfield (ilimitado no plano) e importa no Studio por upload, pasta Downloads ou histórico do CLI. Alternativa paga via CLI só quando logado e sempre com `cost` antes (regra comum da wave).

## Escopo
- Instruções prontas por tipo (draw_to_edit, edit, multishot) com o botão "gerar 4 / gerar 1" e a regra "uma instrução por vez" validada.
- Importação das imagens de ideação (upload, Downloads, histórico) via `studio/common/ingest.py`; seleção das ideias que entram no storyboard.
- 5 cenas em texto por padrão, editáveis (adicionar, remover, reordenar, anexar imagem de ideação).
- `storyboard.md` gerado a partir das cenas, em ordem, com a imagem de cada uma.
- Pré-requisito: `base/base_final.png` da etapa 3.

## Fora de escopo
- Desenhar dentro do Studio (o Draw to Edit é feito na UI da Higgsfield); automatizar a UI da Higgsfield (ADR-002).
- Shotlist com gramática de cinema, character sheet, hook 3 s, geração de roteiro por LLM [INFERÊNCIA no plano, não ensinado na aula].
- Ângulos por cena (etapa 5) e qualquer vídeo (etapa 6).

## Sucesso
- Com `base/base_final.png` presente, o usuário sai da etapa com `scenes.json` válido (≥ 1 cena com texto) e `storyboard.md`; a etapa 5 lê `scenes.json` sem adaptação `[cross-feature]`.
- Nenhuma instrução gerada pelo Studio contém mais de uma edição (validação determinística).

## Decisões auto-aceitas (auditar na W5)
[auto-aceito: o texto da instrução é digitado pelo usuário e o Studio só envelopa com o sufixo em inglês da regra do curso, porque não há LLM/tradução na stack; fórmulas da aula ficam disponíveis como presets em inglês (aula 007: prompts em inglês)]
[auto-aceito: número de cenas editável entre 1 e 10, padrão 5, porque a aula diz "~5 cenas" e o schema da wave diz "5 cenas por padrão, editável"]
[auto-aceito: geração paga por CLI limitada aos tipos edit e multishot (nano_banana_2 / modelo escolhido no catálogo); Draw to Edit é só modo UI, porque o CLI não tem equivalente de imagem]

## `[extensão]` Wave 9 — Inpaint por marcação (inpaint-marcacao) · 2026-08-30

Subseção ADITIVA (Wave 9, card https://trello.com/c/T53Hnvlv, modo batch). A aula 010 cita
"Inpaint para ajustes localizados" na UI da Higgsfield; o CLI (ADR-002) não aceita máscara, e por
isso o Studio só tinha o inpaint como preset de texto. Esta extensão aproxima o gesto da aula sem
sair do método:

- **Canvas de marcação na SPA**: o usuário rabisca sobre a imagem escolhida (base ou candidata)
  em um modal (`studio/web/annotate.js`, padrão do `multishot.js`); o PNG anotado é salvo no
  projeto via `ingest_bytes` com `meta {role:"annotation", parent}` e nunca aparece como ideia.
- **Modo de edição "área marcada"** (`kind="edit_area"`) no fluxo de edição iterativa: a imagem
  ORIGINAL vai primeira em `image_references`, a anotada entra como referência extra e o servidor
  monta instrução fixa em inglês pedindo para editar somente a região marcada, mantendo o resto
  idêntico. Fluxo pago obrigatório: `cost` → `confirmCost` → job com polling →
  `record_generation` (ação nova `storyboard.inpaint`, ADR-016).
- **Limite declarado na UI**: é aproximação **best-effort por prompt**, não inpaint real com
  máscara (ADR-002 proíbe qualquer caminho fora do CLI). O preset da aula
  "Inpaint: corda proporcional" (texto, kind `edit`) permanece e convive com o modo novo.

Fora de escopo: máscara real, automação da UI da Higgsfield, mudanças em rotas/kinds/schemas
existentes. Comportamento técnico completo, contratos, matriz de erros e pendências do gate em
lote: `docs/domains/storyboard/features/inpaint-marcacao-fdd.md`.

[auto-aceito: componente como arquivo NOVO em `studio/web/` (contrato publicado da wave-9),
servido pelo mount `/static` existente e carregado por injeção dinâmica de script pelo `view.js`
da etapa 4 — nenhuma edição em `index.html`/`app.js`/`app.py` (ADR-010)]
[auto-aceito: as exclusões "sem desenho no Studio / sem inpaint por CLI" do FDD base seguem
válidas para o escopo do curso; esta subseção só ADICIONA a extensão aprovada no gate da wave]
