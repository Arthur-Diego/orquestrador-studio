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
