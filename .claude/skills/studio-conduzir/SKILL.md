---
name: studio-conduzir
description: >
  [extensão] Conduz a criação de um vídeo no Orquestrador Studio do início ao fim pelas tools do
  MCP `studio` (referências → mood → base → storyboard → animação → trilha → montagem → export).
  Use num terminal `claude` com o Studio rodando (`make run`) e o `.mcp.json` do repositório
  carregado. Mesma lógica do assistente embutido (ADR-036/037/038), agora no terminal.
allowed-tools: Bash
---

# Conduzir uma campanha no Studio (terminal)

Pré-requisitos: o Studio no ar (`make run`, http://127.0.0.1:8765) e o servidor MCP `studio`
conectado (`.mcp.json` do repo; confira com `claude mcp list`). As tools chegam como
`mcp__studio__*`.

## Princípio (igual ao assistente embutido)
- Aja **só** pelas tools `mcp__studio__*`. Confira o estado com `guide`/`guide_step` antes de agir.
- **A aula é a fonte de verdade** (ADR-004). Não invente etapa. Extensões são marcadas `[extensão]`.
- **Escolha visual e gasto são do usuário.** No terminal não há widget: liste as opções e pergunte
  em texto; para gerar pago, chame a tool com `confirm=true` só depois do ok explícito do usuário.
- Grátis na exploração (motor local no storyboard); pago só na versão final.

## Roteiro
1. `guide <pid>` para ver o que falta. Sem campanha, ajude a criar/escolher.
2. Referências: `refs_suggest_terms` → `refs_search` → `job_wait <pid> refs` → `refs_pick`.
3. Mood: `mood_prompt` → `mood_generate` (confirme custo) → `job_wait` → `mood_pick`.
4. Base: `base_prompt` → `base_generate` (confirme custo) → `job_wait <pid> base` → `base_review`
   (mostra as candidatas NOVAS com o par antes→depois e deixa o usuário definir a base final).
   Use `base_pick` quando a escolha for entre candidatas já existentes, sem geração recente.
5. Storyboard: `storyboard_local_generate` (grátis) → `job_wait` → `storyboard_pick`.
6. Animação/Trilha/Montagem/Export: `animate_generate`/`music_generate` (pago, confirme) ·
   `edit_render`/`export_render`/`export_qa` (grátis) · `job_wait` a cada passo.
7. `portfolio` para o progresso dos 4 vídeos.

Regra de custo: nenhuma geração paga sem confirmação explícita do usuário.
