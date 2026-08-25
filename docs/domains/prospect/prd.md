# PRD curto: prospect (OS-011, Etapa 11, Prospecção, aula 001)
Data: 2026-08-25 · Wave 1 (`docs/domains/studio/waves/wave-1.md`) · Modo batch (auto-aceite)

## Problema
A aula 001 ensina um método de prospecção por DM em pequenos negócios; hoje o Studio para na etapa 10
(publicar) e o aluno prospecta "de cabeça", perdendo o script, o teaser e o controle de quantas DMs mandou.

## Objetivo e usuário
Reproduzir a aula 001 como etapa executável para o aluno com 4 vídeos publicados (etapa 10) prospectando
pequenos negócios no Instagram. O Studio redige e registra; **enviar é humano**.

## O que a aula manda (fonte de verdade)
1. Só prospectar depois de publicar 4 vídeos (gate lido de `publish/log.json`).
2. 10 DMs por dia com o script literal (fã/consumidor → post que ressoou → "produzo anúncios criativos" →
   "tive uma inspiração e criei algo para o seu negócio, quer ver como ficou?"). Sem links.
3. Quem responde recebe um teaser de 5 a 10 s **com música**.
4. Follow-up literal convidando para uma call de 15 minutos.
5. Na call: tabela de etapas de produção para ancorar valor (sem valores), oferta só-agora (50% no primeiro),
   50% entrada / 50% entrega, faixa inicial R$ 100 a 500 por vídeo de 30 s a 1 min. Vender resultado, não IA.

## Escopo desta entrega
- Gate "≥ 4 vídeos publicados" com a mensagem da aula quando bloqueado.
- Cadastro de leads: negócio, @, post que ressoou e por quê.
- Texto da DM gerado do script literal, botão copiar, marcação "enviada em"; contador N/10 hoje.
- Teaser por lead: um take de `animate/takes.json` + `audio/music.*` cortados via ffmpeg → `prospect/teasers/<lead>.mp4`.
- Texto de follow-up literal e registro da call (data, feito, nota).
- `prospect/pitch.md`: tabela de etapas (conceito, mood board, roteirização, direção criativa, produção,
  montagem, entrega) sem valores + lembretes da aula.

## Fora de escopo
Envio automático de DM, API de Instagram, CRM, precificação automática, geração de vídeo novo para o teaser
(usa take já existente) e qualquer coisa que a aula 001 não ensina.

## Critérios de sucesso
- Com `< 4` entradas em `publish/log.json` o cadastro de leads e a DM ficam bloqueados com a mensagem da aula.
- A DM gerada é o script literal com os campos do lead substituídos e nenhum link.
- O teaser tem entre 5 e 10 s, faixa de áudio presente e é reproduzível (H.264 + AAC).
- O contador mostra quantas DMs foram marcadas como enviadas hoje em relação ao limite 10.

[auto-aceito: PRD derivado só de wave-1.md + recon-wave-1.md; nenhuma pergunta de negócio ficou sem fonte]
