"""Contrato de tela da feature progress-modal (ADH-OS-20260827-06).

Não há runner de JS (ADR-008): a prova de comportamento é o smoke Playwright do PR. Aqui checamos,
por substring, que os helpers existem no shell e que cada ação relevante os liga — a mesma técnica
dos outros `test_*_view`/`test_*_api`. A regra da feature:

- Chamada SÍNCRONA ao Claude (bot de prompts) → `Studio.ui.progress` (fases + cronômetro), pulando
  o modal no modo `template` (instantâneo);
- JOB (geração/render/scrape/teaser) → `Studio.ui.progressJob` (log real, fonte única de polling).
"""


def _static(client, name):
    r = client.get(f"/static/{name}")
    assert r.status_code == 200, name
    return r.text


def _view(client, step):
    r = client.get(f"/steps/{step}/view.js")
    assert r.status_code == 200, step
    return r.text


def test_shell_exposes_progress_and_progressjob(client):
    """Os dois helpers vivem no `ui.js` (ADR-010: nenhuma frente recopia o componente)."""
    js = _static(client, "ui.js")
    assert "progress({" in js, "Studio.ui.progress precisa existir no ui.js"
    assert "progressJob({" in js, "Studio.ui.progressJob precisa existir no ui.js"
    # progressJob é construído SOBRE progress + poll (fonte única de polling dos jobs).
    assert "this.progress(" in js and "window.Studio.ui.poll(" in js
    # Contrato do handle e da acessibilidade da FDD §1/§4.
    for parte in ('role="dialog"', 'aria-live="polite"', "prog-timer", "disabled", "step(", "ok(", "fail("):
        assert parte in js, parte


def test_progress_styles_use_catalog_tokens(client):
    """O CSS do modal fica no `ui.css` e usa só os tokens do catálogo (claro/escuro de style.css)."""
    css = _static(client, "ui.css")
    assert ".progress-modal" in css and ".prog-steps" in css and ".prog-timer" in css
    assert "var(--accent)" in css and "var(--ok)" in css and "var(--gate)" in css
    assert "prog-spin" in css, "spinner do passo em andamento"


# Wave 10: `test_sync_claude_calls_open_the_progress_modal` foi removido — os DOIS consumidores da
# chamada síncrona ao Claude com o modal `Studio.ui.progress` migraram para React e são afirmados
# por substitutos Vitest: a biblioteca de mood boards (E6 · [REACT-07] →
# `frontend/src/areas/moodboards/MoodboardsArea.test.tsx`) e a etapa 3 · base (E7 · [REACT-08] →
# `studio/etapas/base/ui/index.test.tsx`, teste "Gerar prompt … Consultando o Claude"). Não resta
# consumidor vanilla para este assert de fonte.


def test_jobs_use_progressjob_as_single_source(client):
    """Cada JOB (geração/render/scrape/teaser) é ligado ao `progressJob` (log real).

    Wave 10 · E5 (card [REACT-06]): `refs`, `animate` e `prospect` migraram para React e não têm mais
    `view.js` — o uso do `progressJob` nessas telas passou a ser provado pelos substitutos Vitest
    (`studio/etapas/<id>/ui/index.test.tsx`) e pelos cenários de QA (C-REFS busca, C-ANIMATE-24,
    C-PROSPECT-15). Aqui ficam só as etapas ainda vanilla.
    """
    liga = {
        # a etapa 2 (mood) não roda mais job de geração via CLI (etapa2-pick, ADR-014: criação
        # migrou para a biblioteca — a geração paga vive em moodboards, fora do escopo da tela)
        # Wave 10: todas as telas com job por `progressJob` migraram para React (`ui/index.tsx`) e
        # não têm mais `view.js`: `export`/`music` na E4, `refs`/`animate`/`prospect` na E5 e `edit`
        # na E9 (render ffmpeg via `/render/job`). A fonte única de polling (`progressJob` da E2,
        # `frontend/src/ui`) é provada pelos substitutos Vitest de cada tela + os cenários de QA
        # (C-EXPORT-07/09, C-MUSIC-02, C-REFS, C-ANIMATE-24, C-PROSPECT-15, C-EDIT-*). O dict fica
        # vazio: não resta etapa vanilla com job (o teste continua verde, a guarda migra para o Vitest).
    }
    for step, jobref in liga.items():
        js = _view(client, step)
        assert "progressJob(" in js, f"{step}: a ação de job precisa abrir o progressJob"
        assert jobref in js, f"{step}: o jobUrl esperado ({jobref}) sumiu"


# Wave 10 · E5 (card [REACT-06]): `test_confirm_cost_still_precedes_paid_generations` lia
# `animate/view.js` para provar que o `confirmCost` (aula 008) precede o `progressJob`. A `animate`
# migrou para React; a garantia virou o substituto Vitest
# `studio/etapas/animate/ui/index.test.tsx` ("'Gerar via CLI' passa pelo gate de custo …") e é
# reforçada pelos cenários de QA C-ANIMATE-23/24 (recon §7.2).


# Wave 10 · E8 (card [REACT-09]): `test_deterministic_generators_do_not_open_a_modal` lia o fonte de
# `studio/etapas/storyboard/view.js` (agora React). O invariante — os geradores DETERMINÍSTICOS
# "Montar instrução" (ideação) e "Gerar prompt" (ângulo) NÃO abrem modal, enquanto o "Gerar prompt de
# vídeo" (chamada ao Claude) e a geração paga SIM — migrou para o substituto Vitest de renderização
# `studio/etapas/storyboard/ui/storyboard.test.tsx` (assert de `.modal.progress-modal` ausente após o
# clique nos geradores determinísticos, presente após o vídeo). Os demais testes deste arquivo, que
# leem as telas ainda vanilla (refs/edit/export/animate/music/prospect), permanecem até a E10.
