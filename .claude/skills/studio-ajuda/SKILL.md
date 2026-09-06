---
name: studio-ajuda
description: >
  [extensão] Tira dúvidas sobre o método do curso e a aplicação Orquestrador Studio, lendo o guia
  ao vivo e os resources do MCP `studio` (studio://help, studio://help/<etapa>). Use num terminal
  `claude` com o Studio rodando e o `.mcp.json` carregado. Responde "o que falta", "por que está
  bloqueada", "como a aula faz". ADR-037.
allowed-tools: Bash
---

# Ajuda do Studio (terminal)

Fontes de verdade (não invente):
- `guide <pid>` e `guide_step <pid> <etapa>` — estado ao vivo, o que falta, próxima ação.
- `steps` — catálogo das 10 etapas e a aula de cada uma.
- resource `studio://help` e `studio://help/<etapa>` — como conduzir cada etapa.
- `doctor` — saúde do Higgsfield (pago) e do motor local (grátis).

Responda curto, citando a etapa/aula quando ela for a razão. Para agir, use a skill
`studio-conduzir`; aqui é só explicar.
