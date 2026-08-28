# Wave 6 — Retro (dedup CLI · mood board · referências · imagem base)

**Fechada em:** 2026-08-28 · **Recon:** `../recon-wave-6.md` · **Contrato:** `wave-6.md`

## Resultado

| Frente | PR | Testes (pós) | Entrega |
|---|---|---|---|
| A · higgsfield-min-dedup | **#66** | 789 passed | `_dedup_min` em `generate`/`history_media`: some o companion `_min.webp` (conserta multishot/base/mood/histórico; animate já era imune) |
| B · mood-board-rework | **#69** | 788 passed | fluxo painel 01→02, multishot em carrossel, remover/importar candidata, abrir pasta; rotas `DELETE candidates/{cid}`, `downloads-folder`, `open-folder`; **ADR-019** |
| C · refs-filtros-termos | **#68** | 785 passed | filtros multiseleção (checkbox); "marca validada" persistida (`refs/validated_brand.json`) como fonte única das sugestões (≥12 termos); **ADR-020** |
| D · base-painel01 | **#67** | 781 passed | painel 01 com referência grande (`#baseRefHero`) sem espaço morto; "Copiar" + "Gerar via CLI" no prompt |

Integração em série A→D→B→C. Verify integrado (A+B+C+D) verde em `develop`. 4 frentes em
worktrees isoladas, **arquivos de código disjuntos** (CSS todo escopado nas views — ninguém tocou
`style.css`/`ui.css`/`ui.js`). Limpeza pós-integração: removidos os 4 duplicados `_min.webp`
(+thumbs) já cadastrados no board `teste-mood` (dado local não versionado).

## Decisões automáticas (regra/recomendação, sem perguntar — usuário aprovou tudo)

- Implementação **direta** e **sem Postman** nas 4 (trabalho pequeno, sem contrato HTTP público novo).
- B: pasta do board **não renomeada** (já é slug do nome; renomear quebraria `pull_board`/campanhas,
  ADR-013) → em vez disso, "Abrir pasta" + caminho no editor.
- B: "explorer na pasta de Downloads" (impossível pelo `<input file>`) → import server-side +
  botão `open-folder` best-effort (WSL `explorer.exe`/`xdg-open`).
- C: "marca validada" não existia persistida → criada no domínio refs; sugestões passam a sair
  **só** dela.
- D: botão "Gerar via CLI" do painel 01 age sempre sobre a situação (independe do stepper do 03).

## Conflitos e incidentes de integração (e a regra que viram)

1. **`docs/adrs/mapping.md` conflitou entre B e C** (as duas anexaram o bloco do seu ADR). O recon
   não marcou `mapping.md` como compartilhado. Resolvido no rebase de C mantendo os dois blocos.
   → **Regra:** `docs/adrs/mapping.md` é ponto de conflito sempre que ≥2 frentes criam ADR na
   mesma wave. Números de ADR já eram atribuídos no plano (019 B, 020 C), mas o append ainda
   conflita. Opções para a próxima wave: (a) o **orquestrador** consolida `mapping.md` na W5
   (frentes não o tocam), ou (b) cada frente anexa em seção com âncora única. (Reforço para
   `references/gates.md`/`ambiente.md`.)
2. **Corrida do watcher de CI:** `gh pr checks <pr> --watch` **sai cedo** quando roda logo após o
   push, antes de o `build-and-test` ser registrado (vê só o `task-id-check` e conclui). Levou a
   uma tentativa de merge barrada ("base branch policy"). → **Regra:** após rebase/force-push,
   **aguardar o `build-and-test` aparecer E concluir** (poll explícito por estado
   `pass`/`fail`), não confiar no primeiro retorno do `--watch`.
3. **`strict` + serialização do runner:** cada merge move o `develop` e obriga rebase da próxima
   frente (branch up-to-date) → N ciclos de CI. Esperado; integração em série resolve. Rebases
   limpos por causa da disjunção de arquivos.

## Aprendizados → regras (resumo acionável)

- Manter CSS novo **escopado na view** (ou `<style>` inline) para preservar a disjunção de
  arquivos entre frentes — funcionou, zero conflito de CSS.
- `mapping.md` (e qualquer índice append-only compartilhado) é responsabilidade da **integração**,
  não das frentes.
- Watcher de CI: poll do `build-and-test` por estado terminal, com tolerância ao atraso de
  registro do check.

## Pendências que seguem (fora do escopo da wave)

- Validação **visual no navegador** não foi feita em nenhuma frente (worktrees headless) — smoke
  recomendado: mood board (carrossel/remover/importar/abrir pasta/fluxo 01→02), referências
  (filtros + marca validada + ≥12 termos), imagem base (painel 01 hero + copiar/CLI).
- Worktree antiga `feature-adh-os-20260827-13-storyboard` (com alterações não commitadas) segue no
  workspace → `dd-parallel-clean` quando o dono decidir.
- Promoção `develop → main` (release) permanece como decisão do dono.
