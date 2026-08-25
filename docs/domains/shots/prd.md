# PRD: shots (OS-005) · Etapa 5 · Ângulos por cena · aula 011 (+ cena extra do produto, aula 013)

Data: 2026-08-25 · Wave 1 (`docs/domains/studio/waves/wave-1.md`) · Modo batch (auto-aceite; revisão em lote na W5)

## Problema
Após a etapa 4 o projeto tem 5 cenas roteirizadas, cada uma com uma imagem de ideia. A aula 011 manda transformar cada cena em vários ângulos consistentes (Multi Shot), escolher, fazer upscale, salvar em `cena N` e ordenar os prints no storyboard. A aula 013 acrescenta uma cena final que mostra o produto ("troque a lata da imagem 1 pela da imagem 2", "tudo ao redor congelado"). Hoje nada disso existe no Studio: a etapa 5 está como `soon` no catálogo.

## Em uma frase (gate 5 do CLAUDE.md)
A aula 011 pega a imagem base de cada cena, pede "outro ponto de vista" (Multi Shot), escolhe, faz upscale e ordena os prints; a etapa produz `shots/cenaNN/shotMM_final.png` por cena e `shots/storyboard.json` com a ordem, mais a cena extra do produto da aula 013.

## Usuário e valor
Aluno do curso operando o Studio localmente. Valor: sair da etapa com todos os frames que a etapa 6 (animate) vai animar, na ordem certa, sem "cheiro de plástico" (bloco de câmera no prompt) e com cores/luz acertadas antes do Multi Shot.

## Escopo (o que a aula ensina)
1. Por cena: preparar a imagem base da cena a partir de `storyboard/scenes.json` (ou `base/base_final.png` se a cena não tem imagem).
2. Prompt de ângulo no molde da aula: "me traga outro ponto de vista desta imagem, quero um close em …"; Multi Shot na UI da Higgsfield ou `nano_banana_2` via CLI (N chamadas, padrão 4).
3. Prompt de edição com instruções numeradas ("1. … 2. … 3. …"), uma rodada por vez, terminando com "keep everything else identical, realistic".
4. Realismo: bloco de câmera no prompt (lente, abertura, escala, ângulo) no lugar do Cinema Studio, que não tem API; na UI o usuário pode usar o Cinema Studio.
5. Aviso permanente antes do Multi Shot: "acerte cores e luz ANTES do multishot", mostrando `mood/palette.json`.
6. Importar os resultados (upload, pasta Downloads, histórico do CLI), escolher, upscale (na UI e importar, ou `bytedance_image_upscale` via CLI), ordenar.
7. Cena extra do produto (aula 013): imagem de referência (ex.: geladeira) + `base/base_final.png`; instrução 1 "troque a lata da imagem 1 pela da imagem 2"; instrução 2 "retire o texto abaixo da lata e faça com que tudo ao redor esteja congelado"; escolher e salvar.
8. Saída: `shots/storyboard.json` no schema da wave, lido por `animate` sem adaptação.

## Fora de escopo
Shotlist com gramática de cinema, character sheet/Soul ID, color match automático, hook nos 3 s (todos [INFERÊNCIA] do plano, ADR-004). Animação (etapa 6). Edição de `storyboard/scenes.json` (pertence à etapa 4). Automação da UI da Higgsfield (ADR-002).

## Critérios de sucesso
- Cada uma das 5 cenas pode terminar com ≥ 1 `shotMM_final.png` ordenado; `storyboard.json` valida contra o schema da wave.
- Prompts entregues reproduzem as fórmulas da aula (ângulo, edição numerada, bloco de câmera); aviso de cores/luz visível antes de gerar.
- Caminho "modo UI + importar" funciona sem CLI logado; caminho CLI só com `logged_in` e `cost` antes.
- `pytest` sem rede: serviço e API cobertos com fixtures de `scenes.json`, `base_final.png` e `palette.json`.

[auto-aceito: PRD curto derivado só de wave-1.md, recon-wave-1.md e CLAUDE.md, sem entrevista, por ser modo batch da W3]
[auto-aceito: cena do produto fica nesta feature (não em music) porque a wave-1 já a aloca em shots e o artefato é um frame estático]
