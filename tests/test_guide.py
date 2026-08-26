"""Contrato transversal do guia por etapa: builder, derivação de estado, fallback e rotas.

O guia é calculado lendo os artefatos do projeto (ADR-003) — nenhum teste aqui grava artefato
por um caminho que não seja o do próprio serviço.
"""
import pytest

META = {"id": "base", "n": 3, "title": "Imagem base", "aula": "009", "desc": "Produto na situação da referência."}


def _new_project(client, name="G", **extra):
    return client.post("/api/projects", json={"name": name, **extra}).json()["id"]


# ---------- builder ----------
def test_build_derives_todo_without_outputs_ok(studio_env):
    from studio.common import guide as G
    g = G.Guide(META).text("O que fazer.", ["checklist da aula"]).output("final", "base/base_final.png", False).build()
    assert g["status"] == "todo" and g["progress"] == 0.0
    assert g["id"] == "base" and g["n"] == 3 and g["aula"] == "009" and g["title"] == "Imagem base"
    assert g["what"] == "O que fazer." and g["checklist"] == ["checklist da aula"]
    assert g["missing"] == ["base/base_final.png"]
    assert "base/base_final.png" in g["next_action"]


def test_build_in_progress_done_and_progress_fraction(studio_env):
    from studio.common import guide as G
    parcial = G.Guide(META).output("a", "a.png", True).output("b", "b.png", False).build()
    assert parcial["status"] == "in_progress" and parcial["progress"] == 0.5
    pronto = G.Guide(META).output("a", "a.png", True).output("b", "b.png", True).build()
    assert pronto["status"] == "done" and pronto["progress"] == 1.0 and pronto["missing"] == []
    assert "storyboard" in pronto["next_action"] or "etapa 4" in pronto["next_action"]


def test_input_fail_blocks_even_with_outputs_ok(studio_env):
    from studio.common import guide as G
    g = (G.Guide(META)
         .input("mood", "mood/selected/ com imagens", False, fix="Volte à etapa 2 e salve o mood", step="mood")
         .output("a", "a.png", True)
         .build())
    assert g["status"] == "blocked"
    assert g["inputs"][0] == {"id": "mood", "label": "mood/selected/ com imagens", "status": "fail",
                              "fix": "Volte à etapa 2 e salve o mood", "step": "mood"}
    assert "Volte à etapa 2" in g["next_action"]
    assert g["missing"] == ["mood/selected/ com imagens"], "só o que não está ok entra em missing"


def test_validations_never_block_and_reject_invalid_status(studio_env):
    from studio.common import guide as G
    g = (G.Guide(META).output("a", "a.png", True)
         .check("upscale_2x", "Upscale 2x (aula 009)", "fail", detail="1.0x", fix="Reimporte o upscale")
         .check("brand", "Rótulo trocado pela marca", "warn")
         .build())
    assert g["status"] == "done", "validação nunca bloqueia a etapa"
    assert [v["status"] for v in g["validations"]] == ["fail", "warn"]
    with pytest.raises(ValueError):
        G.Guide(META).check("x", "x", "quase")


def test_next_step_comes_from_the_course_catalog(studio_env):
    from studio.common import guide as G
    assert G.next_step_id("refs") == "mood"
    assert G.next_step_id("prospect") is None, "etapa 11 é a última"
    assert G.next_step_id("nao-existe") is None
    assert G.Guide(META).output("a", "a", True).build()["next_step"] == "storyboard"
    assert G.Guide(META).output("a", "a", True).build(next_step=None)["next_step"] is None
    assert G.Guide(META).output("a", "a", True).build(next_step="publish")["next_step"] == "publish"


def test_summary_is_optional_and_always_present(studio_env):
    """Wave 4: o chip extra do guia (`summary`) e a sua cor (`summary_kind`) são campos fixos."""
    from studio.common import guide as G
    sem = G.Guide(META).output("a", "a.png", True).build()
    assert sem["summary"] is None and sem["summary_kind"] is None, "campo sempre presente"

    com = G.Guide(META).output("a", "a.png", False).build(summary="1/6 shots prontos")
    assert com["summary"] == "1/6 shots prontos" and com["summary_kind"] is None, "cor neutra por default"

    warn = G.Guide(META).output("a", "a.png", False).build(summary="portfólio 1/4 vídeos", summary_kind="warn")
    assert warn["summary"] == "portfólio 1/4 vídeos" and warn["summary_kind"] == "warn"

    # `summary_kind` sem `summary` não vira chip órfão na UI.
    orfao = G.Guide(META).output("a", "a.png", True).build(summary_kind="warn")
    assert orfao["summary"] is None and orfao["summary_kind"] is None

    generico = G.generic_guide(META)
    assert generico["summary"] is None and generico["summary_kind"] is None


def test_build_without_outputs_is_todo(studio_env):
    from studio.common import guide as G
    g = G.Guide(META).text("Só texto.").build()
    assert g["status"] == "todo" and g["progress"] == 0.0 and g["missing"] == []
    assert g["next_action"]


# ---------- helpers de leitura ----------
def test_read_helpers_only_read_the_project(studio_env, client):
    from studio.common import guide as G
    pid = _new_project(client, "Helpers")
    root = studio_env["tmp"] / "projects" / pid
    (root / "mood" / "selected").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "selected" / "a.png").write_bytes(b"x")
    (root / "mood" / "selected" / "b.jpg").write_bytes(b"x")
    (root / "mood" / "selected" / "notes.txt").write_text("x")
    (root / "mood" / "palette.json").write_text('{"colors": ["#fff"]}')
    (root / "mood" / "quebrado.json").write_text("{nao json")

    assert G.exists(pid, "mood/palette.json") and G.exists(pid, "mood/selected")
    assert not G.exists(pid, "base/base_final.png")
    assert G.read_json(pid, "mood/palette.json")["colors"] == ["#fff"]
    assert G.read_json(pid, "mood/quebrado.json", default={}) == {}, "JSON corrompido não explode o guia"
    assert G.read_json(pid, "nao/existe.json") is None
    assert G.count_files(pid, "mood/selected") == 3
    assert G.count_files(pid, "mood/selected", {".png", ".jpg"}) == 2
    assert G.count_files(pid, "mood/selected", ("png",)) == 1, "extensão sem ponto também vale"
    assert G.count_files(pid, "nao/existe") == 0
    with pytest.raises(ValueError):
        G.exists(pid, "../outro-projeto/project.json")
    with pytest.raises(KeyError):
        G.exists("projeto-inexistente", "project.json")


# ---------- fallback ----------
def test_generic_guide_is_unknown_and_carries_the_error(studio_env):
    from studio.common import guide as G
    g = G.generic_guide(META)
    assert g["status"] == "unknown" and g["progress"] == 0.0 and g["next_step"] == "storyboard"
    assert g["what"] == META["desc"] and g["inputs"] == [] and g["outputs"] == [] and "detail" not in g
    com_erro = G.generic_guide(META, detail="RuntimeError: sem ffprobe")
    assert com_erro["status"] == "unknown" and com_erro["detail"] == "RuntimeError: sem ffprobe"


# ---------- descoberta ----------
def test_discover_exposes_an_optional_guide_hook(studio_env):
    from studio.etapas import discover
    plugins = discover()
    assert len(plugins) == 11
    for sid, p in plugins.items():
        assert "guide" in p, f"{sid} sem a chave guide na descoberta"
        assert p["guide"] is None or callable(p["guide"])
        assert p["router"] is not None and p["meta"]["status"] == "ready"


# ---------- rotas ----------
def _fake_hook(step_id, outputs_ok):
    """Hook de plugin de mentira: um artefato, ok ou não — sem tocar em disco."""
    def hook(pid):
        from studio.common import guide as G
        from studio.etapas import discover
        meta = discover()[step_id]["meta"]
        return (G.Guide(meta).text(f"guia de {step_id}", ["bullet da aula"])
                .output("artefato", f"{step_id}/artefato.json", outputs_ok)
                .build())
    return hook


def test_step_guide_route_uses_the_plugin_hook(studio_env, client, monkeypatch):
    from studio import app as app_module
    pid = _new_project(client, "Rota")
    monkeypatch.setitem(app_module.PLUGINS["refs"], "guide", _fake_hook("refs", True))
    g = client.get(f"/api/projects/{pid}/guide/refs").json()
    assert g["id"] == "refs" and g["status"] == "done" and g["progress"] == 1.0
    assert g["what"] == "guia de refs" and g["next_step"] == "mood"
    monkeypatch.setitem(app_module.PLUGINS["mood"], "guide", None)   # simula etapa sem guide.py
    sem_hook = client.get(f"/api/projects/{pid}/guide/mood").json()
    assert sem_hook["status"] == "unknown", "etapa sem guide.py cai no guia genérico"


def test_summary_travels_over_http(studio_env, client, monkeypatch):
    """O resumo chega ao frontend pelas rotas existentes — nenhuma rota nova (regra 5)."""
    from studio import app as app_module
    from studio.common import guide as G
    from studio.etapas import discover

    pid = _new_project(client, "Resumo")

    def hook(_pid):
        meta = discover()["refs"]["meta"]
        return (G.Guide(meta).output("a", "refs/brainstorming/", True)
                .build(summary="18 escolhidas", summary_kind="ok"))

    monkeypatch.setitem(app_module.PLUGINS["refs"], "guide", hook)
    g = client.get(f"/api/projects/{pid}/guide/refs").json()
    assert g["summary"] == "18 escolhidas" and g["summary_kind"] == "ok"
    agg = client.get(f"/api/projects/{pid}/guide").json()
    assert agg["steps"][0]["summary"] == "18 escolhidas"
    assert all("summary" in s and "summary_kind" in s for s in agg["steps"]), "campo fixo nas 11"


def test_step_guide_route_404s(studio_env, client):
    pid = _new_project(client, "Faltando")
    assert client.get(f"/api/projects/{pid}/guide/nao-existe").status_code == 404
    assert client.get("/api/projects/nao-existe/guide/refs").status_code == 404
    assert client.get("/api/projects/nao-existe/guide").status_code == 404


def test_hook_exception_becomes_unknown_never_500(studio_env, client, monkeypatch):
    from studio import app as app_module

    def explode(pid):
        raise RuntimeError("ffprobe não existe")

    pid = _new_project(client, "Explode")
    monkeypatch.setitem(app_module.PLUGINS["refs"], "guide", explode)
    r = client.get(f"/api/projects/{pid}/guide/refs")
    assert r.status_code == 200
    assert r.json()["status"] == "unknown" and "ffprobe não existe" in r.json()["detail"]
    agg = client.get(f"/api/projects/{pid}/guide")
    assert agg.status_code == 200 and agg.json()["steps"][0]["status"] == "unknown"


def test_aggregate_guide_counts_progress_and_current(studio_env, client, monkeypatch):
    from studio import app as app_module
    pid = _new_project(client, "Agregado")
    monkeypatch.setitem(app_module.PLUGINS["refs"], "guide", _fake_hook("refs", True))
    monkeypatch.setitem(app_module.PLUGINS["mood"], "guide", _fake_hook("mood", False))
    agg = client.get(f"/api/projects/{pid}/guide").json()
    assert agg["total"] == 11 and len(agg["steps"]) == 11
    assert [s["id"] for s in agg["steps"]][:3] == ["refs", "mood", "base"], "ordem do curso"
    assert agg["done"] == 1 and agg["progress"] == round(1 / 11, 2)
    assert agg["current"] == "mood", "primeira etapa não concluída"


def test_real_plugin_without_artifacts_is_todo_or_unknown(studio_env, client):
    """Projeto recém-criado: nenhuma etapa pode aparecer como concluída."""
    pid = _new_project(client, "Vazio")
    agg = client.get(f"/api/projects/{pid}/guide").json()
    assert agg["done"] == 0 and agg["progress"] == 0.0 and agg["current"] == "refs"
    assert {s["status"] for s in agg["steps"]} <= {"todo", "blocked", "unknown"}
