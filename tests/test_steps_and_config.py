"""As etapas do menu espelham o curso; só as implementadas ficam `ready`."""


def test_steps_follow_course_order(studio_env):
    from studio.steps import STEPS
    ids = [s["id"] for s in STEPS]
    assert ids[:3] == ["refs", "mood", "base"], "ordem das aulas 009 → 009 → 009 (refs, mood, base)"
    assert [s["n"] for s in STEPS] == list(range(1, len(STEPS) + 1))
    assert all(s["aula"] for s in STEPS)


def test_only_implemented_steps_are_ready(studio_env):
    from studio.steps import STEPS
    ready = {s["id"] for s in STEPS if s["status"] == "ready"}
    assert ready == {"refs", "mood"}


def test_project_layout_mirrors_course_folders(studio_env):
    from studio.config import PROJECT_LAYOUT
    for folder in ("refs/brainstorming", "images", "videos", "audio", "mood"):
        assert folder in PROJECT_LAYOUT


def test_plugins_are_discovered_and_serve_assets(client):
    from studio.etapas import discover
    plugins = discover()
    assert set(plugins) == {"refs", "mood"}
    for sid in plugins:
        assert client.get(f"/steps/{sid}/view.html").status_code == 200
        assert client.get(f"/steps/{sid}/view.js").status_code == 200
    assert client.get("/steps/base/view.html").status_code == 404
    assert client.get("/steps/refs/secret.txt").status_code == 404
