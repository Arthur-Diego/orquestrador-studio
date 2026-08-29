# QA E2E do Orquestrador Studio (`scripts/qa/`)

Ferramental da skill `qa-studio` (`.claude/skills/qa-studio/SKILL.md`). Fora do CI (ADR-008):
precisa de Chromium do Playwright, ffmpeg e do servidor da rodada no ar.

```
bash scripts/qa/stack-up.sh . <run> [--real] [--restart]   # servidor isolado + fakes → .qa/runs/<run>/
bash scripts/qa/check-env.sh . <run>                        # pré-voo (PRE-VOO OK)
bash scripts/qa/seed.sh . <run>                             # pid_cheio, pid_vazio, mbid → seed.json
source .qa/runs/<run>/env.sh
.venv/bin/python scripts/qa/run.py --run <run> [--telas …] [--casos …] [--temas light,dark] [--viewports 1440x900,1024x768]
.venv/bin/python scripts/qa/api_audit.py --run <run> [--sem-newman]
bash scripts/qa/stack-down.sh . <run> [--purge]
```

Atalhos: `make qa-up RUN=x`, `qa-seed`, `qa-run TELAS="refs mood"`, `qa-api`, `qa-down`.

## Estrutura

- `harness.py` — `Ctx`, `Resultado`, `Caso`/`registrador`, `Navegador`/`Sonda`, navegação, modais,
  toasts, jobs, evidência, auditoria visual, fixtures, helpers de disco.
- `run.py` — runner (auditoria por tema × viewport, casos funcionais, timers órfãos) →
  `resultados.json`; `--casos` mescla com o resultado anterior (revalidação incremental).
- `api_audit.py` — OpenAPI, contratos, offline, `server.log`, newman → `api.json`.
- `fakes/higgsfield`, `fakes/claude` — CLIs falsos (mídia sintética, JSON fixo, `fakes.log`).
- `cenarios/<tela>.py` — casos por tela (`TELA`, `CASOS`, `caso = H.registrador(TELA, CASOS)`).

## Escrevendo casos — regras aprendidas

1. Um caso por comando/fluxo; id `C-<TELA>-NN`; título curto e verificável; sempre
   `H.verifica(cond, ok, erro, *evidencias)` com o `erro` dizendo o que se viu (valores reais).
2. **Nunca destrua o `pid_cheio`.** Ação destrutiva → `with H.projeto_descartavel(page, ctx, nome) as pid:`
   ou `H.retrato(...)`/`H.restaurar(...)` no `finally`. A SPA só conhece campanhas carregadas no
   boot: projeto criado por API exige `H.remontar(page)` (o `projeto_descartavel` já faz). `H.abrir_tela`
   levanta `RuntimeError` se a SPA cair em outro pid — nunca "corrija" isso afrouxando a guarda.
3. Hash igual não remonta a tela: estado do plugin vive no closure. Depois de mexer no disco/API,
   `H.abrir_tela(..., forcar=True)` ou `H.remontar(page)` antes de ler o DOM.
4. O `ingest` deduplica por hash: fixtures `H.png_temp` (único por padrão), `H.mp4_temp(..., unico=True)`,
   `H.mp3_temp(..., unico=True)`, `H.plantar_download(ctx)` para a pasta Downloads da rodada
   (`ctx.downloads_dir`); `H.arquivo_invalido(ctx)` para rejeição.
5. Modais: `H.modal(page)` (o último), `H.modal_com(page, ".cost-sheet")` (empilhado),
   `H.confirmar_custo(page, aceitar)`, `H.esperar_progresso(page)` (✕ nasce `disabled`; devolve passos e
   nota), `H.observar_progresso`/`H.progresso_visto` para o `progressJob` que se fecha sozinho,
   `H.fechar_modal` (clique → Escape → remove backdrop).
6. `confirm()`/`alert()` nativos: `with H.dialogos(page, aceitar=True) as d:`; abas: `with
   H.capturar_popup(page) as pop:`; clipboard já liberado (`H.clipboard(page)`); drag&drop de arquivo
   `H.soltar_arquivos(page, "#drop", path)`; drag de ponteiro `H.arrastar(page, origem, destino)`;
   overlay cobrindo controle `H.elemento_no_ponto(page, "#btn")`.
7. Caminho triste provocado de propósito (422/409): devolva `H.verifica(...).esperando(422)` — o
   runner não conta esses status como erro da sonda.
8. `H.api_json(page, ctx, "post", path, body)` para JSON; `H.esperar_job(ctx, page, url)` para `/job`;
   `H.esperar_disco(lambda: p.exists(), page=page)` para autosave com debounce.
9. Radios/checkboxes customizados ficam ocultos: clique no `label`. Avalie `Locator.count()` ANTES
   de fechar o modal (locators são preguiçosos). Toasts duram ~3 s: `H.limpar_toast(page)` entre dois.
10. Offline: proibido `#btnLogin` (Pinterest), `#btnMbOpenFolder` (explorer), rede externa. Comando
    da tela sem caminho de UI → `H.Resultado.bloqueado("motivo")` explicando (isso vira observação
    de produto no relatório, não apontamento).
11. Nunca afrouxe um assert para passar: caso que falha por defeito real fica falhando — é o que a
    skill precisa achar. Caso que falha por seletor/timing é bug do caso: corrija o caso.
12. `ruff check scripts/qa` precisa passar; casos idempotentes (o runner pode reexecutar só um).
