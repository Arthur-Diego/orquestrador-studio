"""As etapas do menu espelham o curso; `ready` é exatamente o conjunto de plugins descobertos."""


def test_steps_follow_course_order(studio_env):
    from studio.steps import SOON, all_steps
    steps = all_steps()
    assert [s["id"] for s in steps][:3] == ["refs", "mood", "base"], "ordem das aulas 009 → 009 → 009 (refs, mood, base)"
    assert [s["n"] for s in steps] == list(range(1, len(SOON) + 1))
    assert all(s["aula"] for s in steps)


def test_ready_steps_are_exactly_the_discovered_plugins(studio_env):
    from studio.etapas import discover
    from studio.steps import SOON, all_steps
    plugins = discover()
    ready = {s["id"] for s in all_steps() if s["status"] == "ready"}
    assert ready == set(plugins)
    assert {"refs", "mood"} <= ready, "etapas 1 e 2 já implementadas"
    by_id = {s["id"]: s for s in SOON}
    for sid, plugin in plugins.items():
        assert plugin["meta"]["n"] == by_id[sid]["n"], f"META.n de {sid} diverge do catálogo"
        assert plugin["meta"]["aula"] == by_id[sid]["aula"]


def test_project_layout_mirrors_course_folders(studio_env):
    """O layout cobre as pastas de todas as etapas — o guia lê o projeto sem precisar criar nada."""
    from studio.config import PROJECT_LAYOUT
    for folder in ("refs/brainstorming", "images", "videos", "audio", "mood", "mood/vibe",
                   "base", "storyboard", "storyboard/ideas", "animate", "publish", "prospect"):
        assert folder in PROJECT_LAYOUT
    assert len(PROJECT_LAYOUT) == len(set(PROJECT_LAYOUT)), "sem pasta repetida"


def test_new_project_creates_every_layout_folder(client, studio_env):
    from studio.config import PROJECT_LAYOUT
    pid = client.post("/api/projects", json={"name": "Layout"}).json()["id"]
    root = studio_env["tmp"] / "projects" / pid
    for folder in PROJECT_LAYOUT:
        assert (root / folder).is_dir(), folder


def test_plugins_serve_their_assets(client):
    """Wave 10 · E10 (ADR-031/ADR-032): a migração para React terminou. TODAS as 10 etapas são React
    (`ui/index.tsx`, descoberto por `import.meta.glob` e servido pelo bundle `studio/web/dist/`), e a
    rota `/steps/<id>/view.{html,js}` foi REMOVIDA de `studio/app.py`. Nenhuma etapa serve mais
    `view.*`; o contrato de cada tela vive no substituto Vitest `ui/index.test.tsx`.

    Guarda: toda etapa migrada tem `ui/index.tsx` e `/steps/<id>/view.html` responde 404 (rota
    inexistente). O `else` — etapa vanilla ainda servindo `view.*` — não deve existir mais."""
    from studio.etapas import discover
    for sid, plugin in discover().items():
        assert (plugin["dir"] / "ui" / "index.tsx").exists(), \
            f"{sid} deveria ter migrado para React (ui/index.tsx) até a E10"
        assert client.get(f"/steps/{sid}/view.html").status_code == 404, \
            f"{sid} é React: a rota /steps/<id>/view.* não existe mais (removida na E10)"
    assert client.get("/steps/nao-existe/view.html").status_code == 404
    assert client.get("/steps/refs/secret.txt").status_code == 404


def test_edit_step_is_named_studio_de_video(studio_env):
    """A etapa 7 se chama "Studio de vídeo" no catálogo; META e SOON dizem o mesmo título."""
    from studio.etapas import discover
    from studio.steps import SOON, all_steps
    by_id = {s["id"]: s for s in all_steps()}
    assert by_id["edit"]["title"] == "Studio de vídeo"
    soon = {s["id"]: s for s in SOON}["edit"]
    assert discover()["edit"]["meta"]["title"] == soon["title"], "META e catálogo divergem no título"
    assert soon["n"] == 7 and soon["aula"] == "014", "o número e a aula da etapa não mudam"
