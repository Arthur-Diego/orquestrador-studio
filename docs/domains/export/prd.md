# PRD: export (OS-009) · Etapa 9 · Export e QA · aulas 007/014

Data: 2026-08-25 · Wave 1 (`docs/domains/studio/waves/wave-1.md`) · Modo batch (auto-aceite, revisão em lote na W5)

## Uma frase (gate 5 do CLAUDE.md)
A aula 014 manda publicar o vídeo montado mesmo que o primeiro fique ruim, e a aula 007 diz que vertical serve para Instagram/TikTok e 16:9 para YouTube; a etapa 9 pega `edit/master.mp4` e produz os três formatos (16:9, 9:16, 1:1), uma thumb e um checklist técnico que só confere se o arquivo está íntegro, sem julgar gosto.

## Problema
Depois da montagem (etapa 8) o usuário tem um único `master.mp4` 16:9. Para publicar (etapa 10) ele precisa das versões por rede e de uma confirmação objetiva de que os arquivos abrem, têm áudio e a duração esperada. Hoje isso seria feito à mão no CapCut/ffmpeg.

## Usuário e cenário
Aluno do curso, offline, com ffmpeg estático em `~/.local/bin`. Abre a etapa 9 no Studio, vê o master, manda gerar os formatos, escolhe o frame da thumb pelo tempo, gera o QA e segue para a etapa 10.

## Escopo (o que a aula manda)
- Derivar `export/16x9.mp4`, `export/9x16.mp4`, `export/1x1.mp4` do `edit/master.mp4` por ffmpeg (crop central fixo, com preview do enquadramento antes de renderizar).
- `export/thumb.jpg`: frame escolhido pelo usuário por tempo (segundos).
- `export/qa_report.md` técnico via ffprobe: duração, resolução, codec de vídeo e áudio, áudio presente, tamanho. Sem nota estética; o texto lembra "publique mesmo que fique ruim".
- Opcional, só quando logado no CLI da Higgsfield e sempre com `cost` antes: `generate workflow reframe` como alternativa paga ao crop local (trocar ferramenta não é trocar processo, gate 3).

## Fora de escopo
- Legendas automáticas (`captions.srt`, Whisper), hook nos 3 s, safe areas, `brain_activity`, QA estético: a aula não ensina (recon, linha "export").
- Posição horizontal do crop ajustável por clipe ou por percentual na UI: `[extensão]` NÃO aprovada nesta wave; fica crop central fixo. `shots/storyboard.json` (POI por shot) continua listado em Consumes mas não é lido nesta versão.
- Publicar por API, editar o master (é da etapa 8), tocar `app.py`, `steps.py`, `index.html`, `app.js`, `conftest.py`, `requirements.txt`.

## Resultado esperado / critérios de sucesso
- Os três mp4 existem, abrem no ffprobe com a resolução alvo (1920x1080, 1080x1920, 1080x1080), duração igual à do master (tolerância 0,5 s) e mesma trilha de áudio.
- `thumb.jpg` corresponde ao tempo escolhido; `qa_report.md` lista cada arquivo com os campos técnicos e um veredito OK/ATENÇÃO por item.
- `[cross-feature]` a frente `publish` lista os arquivos de `export/` sem adaptação; a frente `export` roda contra o `master.mp4` real produzido por `edit` na integração (W5).

## Auto-aceites deste PRD
- `[auto-aceito: 16x9.mp4 é o master re-encapsulado (copy) quando já for 1920x1080, senão scale+pad; a aula não fala em reprocessar o 16:9]`
- `[auto-aceito: thumb default em t=3 s, valor do plano §4.2, editável pelo usuário]`
- `[auto-aceito: reframe via CLI entra como opcional pago porque a regra comum da wave permite alternativa CLI com cost antes; ADR-004 lista reframe como inferência, então fica registrado como pendência para o lote]`

## Pendências para o lote (W5)
- Confirmar que `reframe` pode ficar como alternativa CLI opcional apesar de ADR-004 listá-lo como [INFERÊNCIA].
- Confirmar leitura da aula 007 para o 1:1 (a aula cita vertical e 16:9; 1:1 vem do catálogo `SOON` da etapa 9).
