# Retro — Wave 9 (2026-08-30/31)

Wave: lacunas do levantamento do curso (5 features). Card: https://trello.com/c/T53Hnvlv.
Resultado: **5/5 integradas em `develop`** — PRs #88 (refs-import-url), #89 (inpaint-marcacao),
#90 (prompter-presets-realismo), #91 (base-clean-marca), #92 (storyboard-roteiro-llm).
Testes no tronco ao fim: 1147+ (baseline 976). ADR-025 criada (roteiro por LLM `[extensão]`).

## O que funcionou

- Handoff provedora→consumidora por contrato congelado (mapa `defaults` aberto via
  `PRESET_ACTIONS`): a consumidora registrou `storyboard.script` sem tocar código da provedora,
  e o critério `[cross-feature]` foi provado em runtime real (5 cenas com o rig do
  `documentary-street`).
- Sub-waves por topologia evitaram conflito de contrato; os únicos conflitos de merge foram
  "dois blocos de teste anexados no mesmo ponto" — resolvidos preservando ambos os lados.
- Gate em lote com delegação explícita do dono: 12 pendências resolvidas por regra
  determinística, todas registradas no `wave-9.md` (seção Gate W3).

## Aprendizados → regras novas

1. **Daemon Compozy nunca deve ter `cwd` em worktree de frente.** O daemon ficou com cwd em
   `wt-inpaint-marcacao` (removida depois) e precisou de restart do checkout principal antes
   da sub-wave 2. Regra: antes de `git worktree remove`, conferir `/proc/<pid>/cwd` do daemon;
   ao subir daemon, sempre a partir do checkout principal.
2. **`.env.local` versionado quebra o isolamento por porta no modo paralelo.** Três frentes
   colidiram no `PORT=8767` do arquivo versionado; cada uma contornou de um jeito
   (skip-worktree, reverter, ignorar). Regra: tirar `.env.local` do versionamento (candidato
   a trabalho de manutenção) ou documentar `skip-worktree` como padrão da frente.
3. **Teste que passa só com dependência local instalada é bomba para o CI.** O 409 de
   concorrência do roteiro dependia do `claude` no PATH; o runner não tem. Regra: todo guard
   de precondição com múltiplas causas precisa de ordem determinística (estado do projeto
   antes de ambiente) e de teste que mocka o binário — nunca confiar no ambiente da máquina.
4. **Frente não pode empurrar commit sem trailer `Task-Id` nem terminar o turno "aguardando
   monitor".** Ambos ocorreram; o segundo já era regra da Wave 8 (reforçada), o primeiro virou
   verificação do orquestrador antes do merge (`task-id-check` pegou).
5. **Docs de spec no checkout principal precisam ser removidos na integração de cada PR** que
   os carrega (o `git pull` recusa sobrescrever untracked) — rotina aplicada 5×; funcionou,
   mas o backup prévio em scratchpad é obrigatório.

## Pendências que ficaram (candidatas a trabalho futuro)

- UI de preset default na tela "Créditos & Custos" e presets na biblioteca de mood boards
  (frente de preparo/shell — ADR-010).
- `record_generation` nos kinds antigos de edição do storyboard (mudança observável).
- `docs/domains/studio/waves/wave-1.md:36`: enum de `base/candidates.json` deve listar `clean`.
- `_video_registry` e `_story_registry` fora da lista do reset (`reset.py::_registries`) —
  gap pré-existente registrado pela frente do roteiro (o `_story_registry` foi nomeado para
  ser descoberto; o `_video_registry` segue fora).
- 3 falhas pré-existentes do newman no domínio storyboard (drift de features antigas) e
  guarda de crédito ausente na pasta 05 da coleção.
- Import de pin via `pin.it` (URL encurtada) rejeitado na v1.
- QA E2E Playwright (`make qa-*`) não rodou nas frentes (recurso físico único) — rodar
  `/qa-studio` no tronco é o próximo passo natural de validação.
