# Wave 7 — Retro (vídeo por cena no storyboard, painel 02)

**Fechada em:** 2026-08-28 · **Recon:** `../recon-wave-7.md` · **Contrato:** `wave-7.md`

## Resultado

| Frente | PR | Testes | Entrega |
|---|---|---|---|
| A · storyboard-video-backend | **#74** | 821 passed | prompt de vídeo por cena (Claude, papel `motion` + template agnóstico); geração via CLI (JobRegistry próprio, chave `pid:scene`); `kling2_6` (cena) / `kling3_0_turbo` (transição); 1 frame ou start/end; scenes.json aditivo (`video_desc`/`video_prompt`/`videos`); **ADR-021** |
| B · storyboard-video-frontend | **#73** | 817 passed | por cena: fotos 110px clicáveis (lightbox), descrição + "gerar prompt de vídeo", "gerar vídeo via CLI" (confirmCost→progressJob→`<video>`), seletor 1 frame/start→end; **modal maior** de reordenação (CSS escopado, sem tocar `ui.css`) |

Integração em série A→B. Rebase de B **auto-mergeou** `test_storyboard_api.py` (A e B tocaram
partes diferentes); verify integrado (A+B) verde. 2 frentes disjuntas em código de produto
(A: service/router/pricing/settings/animate; B: view.js/html).

## Decisões técnicas confirmadas no CLI (não suposição)

- `higgsfield model list`: **`kling2_6` existe** ("Kling 2.6 Video") → cenas. `generate cost`:
  5s=10, 10s=20 créditos; `duration` **inteiro** (5/10), não "5s".
- **Não existe "Kling 2.5 Turbo"** no CLI. A turbo é `kling3_0_turbo` (5s=7,5, 10s=15) → adotada
  para transições (start/end), **configurável** por `settings.default_for("storyboard.video.
  transition")` — troca trivial se a Higgsfield publicar um 2.5-turbo.
- Isso **reverteu o desvio** documentado no `animate` (`LESSON_MODEL_NOTE`: "CLI só tem 3.0") —
  agora `animate.video` usa `kling2_6` (cena) e start_end→`kling3_0_turbo`. Registrado em ADR-021.

## Auto-aceites relevantes

- Papel `motion` do prompter reusado (NÃO editar `ROLES`); template agnóstico como instrução.
- `video/cost` usa `pricing.estimate` (offline, determinístico) casando com os custos medidos no CLI.
- `seconds` do `video-prompt` = duração sugerida do clipe (5 cena / 10 transição).
- Frente B estreitou (não removeu) 3 guards da wave 4 (`confirmCost`/`ui.progress`/`progressJob`
  proibidos na tela) porque a ADR-021 adiciona o caminho pago de **vídeo** — mudança de spec
  explícita e documentada, os guards seguem barrando o caminho pago de imagem da ideação.

## Incidentes de integração (regras)

- **Corrida do gate de merge:** após `merge` de A e rebase/force-push de B, o `mergeStateStatus`
  ficou `UNKNOWN`→`BLOCKED` por vários minutos apesar do `build-and-test` já `pass` — o gate de
  branch protection reavalia o check no head novo com atraso. → **Regra:** aguardar
  `mergeStateStatus == CLEAN` (não só `checks pass`) antes de `gh pr merge`; a branch/PR remota
  sobrevive a um merge barrado (worktree local pode ser removida antes sem perder a PR).
- Sobreposição de teste prevista (`test_storyboard_api.py` em A e B) auto-resolveu no rebase —
  ainda assim rodei o verify integrado antes do merge (auto-merge textual ≠ consistência lógica).

## Pendências que seguem (fora do escopo)

- **Handoff automático** dos mp4 do storyboard → etapa 6 (animate): hoje os vídeos ficam por cena
  (`storyboard/<cena>/video/take_K.mp4`), disponíveis, mas o animate não os importa sozinho.
- Refletir os campos novos de `scenes.json` (`video_desc`/`video_prompt`/`videos`) no `wave-1.md`
  e no "Provides" do `storyboard-fdd.md` (feito nesta integração).
- **`reset`** não descobre o JobRegistry de vídeo (chave `pid:scene`) — reset durante job de vídeo
  em voo não é bloqueado por ele (registrado no ADR-021).
- Smoke visual no navegador do painel 02 (descrição→prompt→vídeo, lightbox, modal de reordenar).
- Promoção `develop → main` (release) — decisão do dono.
