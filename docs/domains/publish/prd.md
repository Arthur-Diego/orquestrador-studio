# PRD: publish (Etapa 10, Publicar)

Task-Id: OS-010 · Wave 1 · Aulas 014/015 · Gerado em modo batch (W3 do `/dd-parallel`).

## Problema
O curso ensina que o criador precisa **publicar** os vídeos que produziu e montar um **portfólio de
4 vídeos** antes de prospectar clientes (aula 015). Hoje o Studio para na etapa 9 (export): não há
onde registrar o que foi publicado, nem um sinal claro de "já posso prospectar".

## O que a aula manda (015, com o "publicar mesmo que fique ruim" da 014)
1. Criar perfil nas redes e publicar os vídeos criativos (Instagram/TikTok/YouTube, aula 007).
2. Ter 4 vídeos publicados antes de começar a prospecção.
3. Pedir feedback sobre o que foi publicado.
Publicar é ato humano, nas redes. O Studio **registra** (rede, URL, data, nota, feedback).
[auto-aceito: sem integração com APIs de rede social; ADR-001/ADR-004 e plano §2.3 mantêm publicação humana]

## Usuários e valor
Criador solo do curso. Valor: um único lugar que lista os arquivos de `export/` prontos para postar,
guarda o log de publicações, mostra o contador **N/4** e libera a etapa 11 (prospect) quando o portfólio
está pronto.

## Escopo
- Listar os arquivos `export/*.mp4` disponíveis para publicar, marcando os já publicados.
- Registrar uma publicação: vídeo, rede, URL, data, nota livre. Remover um registro.
- Campo "feedback recebido" por post (materializa o "peça feedback").
- Contador N/4 e estado "portfólio pronto" (N >= 4). Gerar `publish/portfolio.md`.
- Handoff: `publish/log.json` é o gate de `prospect` (>= 4 entradas).

## Fora de escopo
- Publicar via API (YouTube Data, Instagram Graph, TikTok): fora da aula e da ADR-002/ADR-004.
- Copy automática de legenda ou hashtags: a aula não ensina; só campo livre `note`.
- Agendamento, métricas de alcance, upload do arquivo para a rede.
- Programa de afiliação citado na aula 015 (não é parte do método de produção).

## Critérios de aceite (produto)
- Com `export/9x16.mp4` e `export/16x9.mp4` no projeto, a tela lista os dois com botão "Registrar publicação".
- Após registrar 4 posts, o contador mostra `4/4` e o chip "portfólio pronto"; `portfolio.md` é regravado.
- `publish/log.json` segue o schema da wave: `[{id, video, network, url, posted_at, note, feedback}]`.
- Tudo funciona sem Higgsfield, sem rede e sem ffmpeg (registro puro em FS).
