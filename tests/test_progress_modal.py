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


def test_sync_claude_calls_open_the_progress_modal(client):
    """As ações que POSTam num endpoint do bot (Claude) abrem `Studio.ui.progress` com fases.

    A etapa 2 (mood) deixou de chamar o bot (etapa2-pick, ADR-014: a criação de moods migrou para
    a biblioteca).

    Wave 10 · E6 (card [REACT-07]): a biblioteca de mood boards migrou para React
    (`frontend/src/areas/moodboards/MoodboardsArea.tsx`) e o `studio/web/moodboards.js` vanilla foi
    removido. A chamada síncrona ao Claude na criação de moods (modal de progresso com fases + modo
    `template` instantâneo) passa a ser afirmada pelo substituto Vitest
    `frontend/src/areas/moodboards/MoodboardsArea.test.tsx` e pelo cenário `moodboards.py`. Aqui fica
    só o que continua vanilla: a etapa base.
    """
    base = _view(client, "base")
    assert "ui.progress(" in base and "Consultando o Claude" in base
    # "Gerar prompt" e "Gerar sem viés" passam pela mesma função; só o modo `images` usa o bot.
    assert "usaBot" in base


def test_jobs_use_progressjob_as_single_source(client):
    """Cada JOB (geração/render/scrape/teaser) é ligado ao `progressJob` (log real)."""
    liga = {
        "refs": "refs/job",         # scrape
        # a etapa 2 (mood) não roda mais job de geração via CLI (etapa2-pick, ADR-014: criação
        # migrou para a biblioteca — a geração paga vive em moodboards, fora do escopo da tela)
        "edit": "render/job",       # render ffmpeg
        "export": 'url("job")',     # render por formato
        "animate": "/job",          # geração paga
        "music": "music/story/job",  # sequência bruta
        "prospect": "/job",         # teaser
    }
    for step, jobref in liga.items():
        js = _view(client, step)
        assert "progressJob(" in js, f"{step}: a ação de job precisa abrir o progressJob"
        assert jobref in js, f"{step}: o jobUrl esperado ({jobref}) sumiu"


def test_confirm_cost_still_precedes_paid_generations(client):
    """O modal de progresso abre DEPOIS do `confirmCost` (FDD §2B) — a confirmação não regrediu.

    A etapa 2 (mood) não tem mais geração paga (etapa2-pick, ADR-014); resta `animate`.
    """
    for step in ("animate",):
        js = _view(client, step)
        assert "ui.confirmCost(" in js, step
        # a ordem no código: confirmCost antes do progressJob (o `if (!ok) return;` corta antes).
        assert js.index("confirmCost(") < js.index("progressJob("), step


def test_deterministic_generators_do_not_open_a_modal(client):
    """Storyboard: "Montar instrução" (ideação) e "Gerar prompt" (ângulos) são determinísticos: sem modal.

    Wave 7 (`[extensão]`, ADR-021): o MESMO `view.js` ganhou o vídeo por cena, que SIM abre modal —
    `ui.progress` no "Gerar prompt de vídeo" (chamada síncrona ao Claude) e `progressJob` na geração
    via CLI (`/video/job`). O que este teste trava é que os DOIS geradores determinísticos
    (`build` = montar instrução; `prompts` = prompt de ângulo) seguem SEM modal.
    """
    js = _view(client, "storyboard")
    # o caminho de vídeo da wave 7 usa os dois modais...
    assert "ui.progress(" in js and "Gerar prompt de vídeo" in js
    assert "progressJob(" in js and "/video/job" in js
    # ...mas os geradores determinísticos continuam modal-free:
    build = js.split("async function build(", 1)[1].split("\n    }", 1)[0]
    assert "ui.progress" not in build and "progressJob" not in build, "montar instrução não abre modal"
    prompts = js.split("async function prompts(", 1)[1].split("\n    }", 1)[0]
    assert "ui.progress" not in prompts and "progressJob" not in prompts, "prompt de ângulo não abre modal"
