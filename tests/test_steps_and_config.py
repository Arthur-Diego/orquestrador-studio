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
    from studio.config import PROJECT_LAYOUT
    for folder in ("refs/brainstorming", "images", "videos", "audio", "mood"):
        assert folder in PROJECT_LAYOUT


def test_plugins_serve_their_assets(client):
    from studio.etapas import discover
    for sid in discover():
        assert client.get(f"/steps/{sid}/view.html").status_code == 200, sid
        assert client.get(f"/steps/{sid}/view.js").status_code == 200, sid
    assert client.get("/steps/nao-existe/view.html").status_code == 404
    assert client.get("/steps/refs/secret.txt").status_code == 404
