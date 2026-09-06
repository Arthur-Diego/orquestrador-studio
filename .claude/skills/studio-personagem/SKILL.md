---
name: studio-personagem
description: >
  [extensão] Cria e fixa um personagem consistente no Orquestrador Studio e o aplica a uma campanha
  (identidade mantida entre cenas, foto e vídeo), pelas tools `character_*` do MCP `studio`. Use num
  terminal `claude` com o Studio rodando e o `.mcp.json` carregado. ADR-039.
allowed-tools: Bash
---

# Personagem consistente (terminal)

Pré-requisitos: Studio no ar + MCP `studio` conectado. Tools `mcp__studio__character_*`.

## Fluxo
1. `character_create <name> <style>` (foto|anime|3d).
2. `character_explore <cid> "<brief em inglês>"` — variações no motor local (grátis).
3. `character_pick <cid>` — o **usuário** escolhe a que acertou; o Studio fixa e gera o descritor
   canônico de identidade.
4. `character_sheet <cid>` — vistas ancoradas no descritor (grátis).
5. `character_apply <pid> <cid>` — a partir daí o descritor reancora os prompts de base/storyboard.
6. Identidade paga (opcional): `character_bind_soul <cid>` — treina um Soul ID (Higgsfield, plano
   Basic+; confirme antes). Nota de identidade: `character_score` (se `engine faces` existir).

Regra: a escolha do personagem é do usuário; identidade paga só com confirmação.
