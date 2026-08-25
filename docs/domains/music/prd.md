# PRD curto: music (OS-007) · Etapa 7 · Trilha · aula 013

Data: 2026-08-25 · Wave 1 (`docs/domains/studio/waves/wave-1.md`) · Modo batch (auto-aceite)

## Uma frase (gate 5 do CLAUDE.md)
A aula 013 manda escolher a trilha ANTES de montar, ouvindo varias candidatas ate "sentir" a certa, porque
as batidas fortes ditam onde "algo acontece" no corte. A etapa produz `audio/music.*` escolhida,
`audio/candidates.json`, `audio/beats.json` (bpm, batidas, impactos) e `audio/license.txt`.

## Problema e usuario
Montar antes da trilha "soa amador" (aula 013). Sem a etapa 7, o produtor solo escolhe a musica fora do
Studio e a etapa 8 (edit) nao tem os impactos para propor cortes. Entradas: `mood/mood.md`, `project.json`.

## O que a etapa faz (so o que a aula ensina)
1. Reune varias candidatas: upload de arquivos baixados de bibliotecas (YouTube Audio Library, Artlist,
   Epidemic, Envato, Musicbed), pasta Downloads, historico de audio do CLI, ou geracao paga por CLI
   (`sonilo_music`) com prompt derivado do mood, sempre com `cost` antes e confirmacao.
2. Deixa o usuario "sentir": player na UI, uma candidata por vez, com nome e origem.
3. O usuario escolhe uma; o Studio copia para `audio/music.<ext>`, pede a origem/licenca e grava `audio/license.txt`.
4. Detecta batidas e impactos da escolhida e grava `audio/beats.json` para a montagem (etapa 8).

## Fora de escopo
- Montagem, cortes, SFX, mix (etapa 8). Cena extra do produto (fica em shots, ja decidido na wave).
- Edicao de audio (trim, fade, ganho). Busca automatica em bibliotecas de terceiros (sem API, termos de uso).
- Qualquer analise musical alem de bpm/batidas/impactos `[INFERENCIA]` fora.

## Criterios de sucesso
- Usuario ouve N candidatas e escolhe uma sem sair do Studio.
- `audio/beats.json` existe apos a escolha e `edit` consegue ler `impacts` sem adaptacao `[cross-feature]`.
- `audio/license.txt` registra o que o usuario declarou (nunca inventado pelo Studio).
- Sem rede nos testes; ffmpeg ausente vira mensagem clara, nao crash.

## Decisoes ja tomadas
- `[auto-aceito: deteccao de batidas com numpy + ffmpeg em vez de librosa; librosa pesa no CI e numpy ja entra em requirements.txt pela tarefa transversal]`
- `[auto-aceito: trilha escolhida vira audio/music.<ext original> (wav ou mp3), sem transcodificar; edit aceita os dois]`
- `[auto-aceito: licenca e texto livre declarado pelo usuario no momento do select; Studio nao valida direitos]`

## Pendencias para o lote
- Confirmar id `sonilo_music` no catalogo vivo do CLI (login pendente na maquina de referencia).
