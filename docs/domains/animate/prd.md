# PRD: animate (Etapa 6 · Animação · aula 012) · OS-006

Data: 2026-08-25 · Wave 1 (`/dd-parallel`, modo batch) · Domínio novo `animate`

## Em uma frase (gate 5 do CLAUDE.md)
A aula 012 pega cada frame escolhido na etapa 5, escreve um prompt de movimento, gera 2 vídeos, dá "like" no usável, baixa e guarda em `videos/cena N/`; a etapa produz `videos/cenaNN/shotMM_takeK.mp4` e o índice `animate/takes.json` que a montagem (etapa 8) consome.

## Problema
Sem esta etapa o pipeline para na imagem: a montagem precisa de takes nomeados por cena e shot, com o take usável marcado, e a aula é explícita sobre como chegar neles (prompt por shot, 2 takes, troca de modelo após falhas, corte para preto como plano B).

## Usuário e contexto
Aluno do curso operando o Studio localmente (ADR-001). Caminho padrão é o "modo UI": o Studio entrega o prompt e as instruções da aula, o usuário gera na interface da Higgsfield (ilimitado no plano) e importa o mp4. Caminho pago via CLI (`hf.generate`) só quando logado e sempre com `cost` antes (ADR-002).

## O que a etapa faz (fiel à aula 012)
1. Lista os shots de `shots/storyboard.json` na ordem do storyboard, com o frame de cada um.
2. Para cada shot, sugere um prompt de movimento: simples para cena simples; elaborado (câmera + ação) quando o usuário pedir, seguindo as fórmulas da aula.
3. Quando dois frames consecutivos são da mesma cena, oferece o par start/end frame com a fórmula "Esta é uma cena start frame e end frame...".
4. Duração 5 s por padrão; 10 s quando a mudança é lenta (time-lapse, transição). Áudio do modelo sempre OFF.
5. Gera (ou orienta a gerar) 2 takes por shot; o usuário dá "like" no usável.
6. Importa mp4 por upload, pasta Downloads ou histórico de vídeo do CLI; renomeia para `videos/cenaNN/shotMM_takeK.mp4`.
7. Após 3 falhas no shot, sugere o próximo modelo na ordem kling3_0, seedance_2_0, veo3_1_lite.
8. Se nenhum take servir, o usuário marca "corte para preto" no shot; a montagem lê a flag.

## Fora de escopo
Bot de análise de imagem (a aula usa um bot externo; aqui o prompt é sugerido por template e editado pelo usuário), color match, upscale de vídeo, montagem (etapa 8), qualquer modelo fora da ordem acima, edição de `higgsfield.py`, `app.py`, `steps.py`.

## Critérios de aceite (resumo; detalhe no FDD)
- `animate/takes.json` segue o schema do `wave-1.md` e é lido pela etapa `edit` sem adaptação.
- Cada take importado ou gerado existe em `videos/cenaNN/shotMM_takeK.mp4`; o take com "like" vira `shotMM_final.mp4`.
- Geração por CLI nunca ocorre sem `cost` antes e sem `sound=false`.
- Testes sem rede: CLI fakeado, vídeos por `make_video`.

## Auto-aceites deste PRD
[auto-aceito: prompt sugerido por template pt-BR da aula traduzido para inglês (CLAUDE.md, aula 007), sem bot de análise de imagem, porque o bot é ferramenta externa e não processo]
[auto-aceito: limite de troca de modelo em 3 falhas (o menor da faixa "3 a 4" da aula, mais conservador em créditos)]
[auto-aceito: flag "corte para preto" gravada no registro do shot em takes.json, pois ela existe justamente quando nenhum take é usável]

## Pendências para o lote
- IDs `kling3_0`, `seedance_2_0`, `veo3_1_lite` não confirmados no catálogo vivo (CLI sem login na máquina).
- Formato real de `shots/storyboard.json` depende da frente shots; esta frente usa fixture do schema do `wave-1.md`.
