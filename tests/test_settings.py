"""Config de modelo default por ação + livro-caixa de gasto `[extensão]` (ADR-016).

`settings` é importado DENTRO de cada teste: o fixture `studio_env` recarrega os módulos de
`studio` com o STATE_DIR isolado em tmp, e a referência ao módulo precisa ser a recarregada
(senão os arquivos de config/livro-caixa cairiam no diretório real do usuário)."""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def project(client, studio_env):
    p = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()
    return p["id"]


def test_default_resolution_chain_project_over_global_over_code(studio_env, project):
    from studio.common import settings
    d = settings.default_for("base.image", project)
    assert d["model"] == "nano_banana_2" and d["source"] == "code"
    settings.set_global_default("base.image", "gpt_image_2")
    assert settings.default_for("base.image", project) == {
        "action": "base.image", "model": "gpt_image_2", "variant": None, "source": "global"}
    settings.set_project_default(project, "base.image", "nano_banana_2", "4k")
    d = settings.default_for("base.image", project)
    assert d["model"] == "nano_banana_2" and d["variant"] == "4k" and d["source"] == "project"
    assert settings.default_for("base.image")["source"] == "global"
    settings.clear_project_default(project, "base.image")
    assert settings.default_for("base.image", project)["source"] == "global"


def test_dead_model_in_override_is_ignored(studio_env):
    from studio.common import settings
    settings.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.CONFIG_PATH.write_text(json.dumps({"defaults": {"base.image": {"model": "ghost"}}}))
    assert settings.default_for("base.image")["model"] == "nano_banana_2"


def test_invalid_action_or_model_rejected(studio_env):
    from studio.common import settings
    with pytest.raises(ValueError):
        settings.set_global_default("nope", "nano_banana_2")
    with pytest.raises(ValueError):
        settings.set_global_default("base.image", "ghost")


def test_ledger_records_and_summarizes(studio_env):
    from studio.common import settings
    settings.record_generation(action="base.image", model="nano_banana_2", params={"resolution": "2k"},
                               count=1, pid="p1", step="base", project_name="P1")
    settings.record_generation(action="base.image", model="nano_banana_2", params={"resolution": "4k"},
                               count=2, pid="p1", step="base", project_name="P1")
    settings.record_generation(action="music.track", model="sonilo_music", params={}, count=1,
                               pid="p2", step="music", project_name="P2")
    s = settings.summary()
    assert s["count"] == 3
    assert s["total_credits"] == pytest.approx(2 + 4 * 2 + 0.94)
    steps = {r["step"]: r for r in s["by_step"]}
    assert steps["base"]["credits"] == pytest.approx(10) and steps["base"]["count"] == 2
    projs = {r["pid"]: r for r in s["by_project"]}
    assert projs["p1"]["credits"] == pytest.approx(10)
    assert settings.summary("p2")["total_credits"] == pytest.approx(0.94)
    assert len(settings.history("p1")) == 2


def test_storyboard_video_defaults_map_scene_to_kling26_and_transition_to_kling30(studio_env):
    """ADR-023 (substitui a parte de modelo da ADR-021): cena → Kling 2.6, transição (start/end) →
    Kling 3.0 — a 3.0 Turbo não declara `end_image` no catálogo do CLI."""
    from studio.common import settings
    assert {a["key"] for a in settings.ACTIONS} >= {"storyboard.video.scene", "storyboard.video.transition"}
    scene = settings.default_for("storyboard.video.scene")
    trans = settings.default_for("storyboard.video.transition")
    assert scene["model"] == "kling2_6" and scene["variant"] == "5s"
    assert trans["model"] == "kling3_0" and trans["variant"] == "5s"
    assert settings.default_for("animate.video")["model"] == "kling2_6"


# ---------- preset de realismo por ação `[extensão]` (mesmo padrão ADR-016) ----------
def test_preset_default_is_opt_in_for_the_three_prompter_kinds(studio_env):
    """T1.12: gate W3 — sem override, nenhum preset é aplicado (fidelidade à aula preservada)."""
    from studio.common import settings
    assert settings.PROMPTER_KINDS == ("mood", "base", "motion")
    for kind in settings.PROMPTER_KINDS:
        assert settings.preset_default_for(kind) == {"kind": kind, "preset": None, "source": "code"}


def test_preset_resolution_accepts_any_registered_action(studio_env, monkeypatch):
    """T1.13: contrato do handoff — a resolução é por AÇÃO registrada, não pelos 3 kinds fixos."""
    from studio.common import settings
    monkeypatch.setitem(settings.PRESET_ACTIONS, "storyboard.script", "documentary-street")
    d = settings.preset_default_for("storyboard.script")
    assert d == {"kind": "storyboard.script", "preset": "documentary-street", "source": "code"}
    with pytest.raises(ValueError):
        settings.preset_default_for("nao.existe")


def test_project_preset_wins_over_global(studio_env, project):
    """T1.14: cadeia projeto → global → código, igual à de modelos."""
    from studio.common import settings
    settings.set_global_preset("base", "arri-natural-narrative")
    settings.set_project_preset(project, "base", "sony-venice-night")
    assert settings.preset_default_for("base", project) == {
        "kind": "base", "preset": "sony-venice-night", "source": "project"}
    assert settings.preset_default_for("base") == {
        "kind": "base", "preset": "arri-natural-narrative", "source": "global"}


def test_persisted_null_ends_the_chain(studio_env, project):
    """T1.15: `null` gravado é "sem preset" ESCOLHIDO — não cai para o global."""
    from studio.common import settings
    settings.set_global_preset("base", "documentary-street")
    settings.set_project_preset(project, "base", None)
    assert settings.preset_default_for("base", project) == {
        "kind": "base", "preset": None, "source": "project"}


def test_clear_project_preset_falls_back_to_global(studio_env, project):
    """T1.16: limpar o override do projeto devolve a decisão ao nível global."""
    from studio.common import settings
    settings.set_global_preset("base", "documentary-street")
    settings.set_project_preset(project, "base", None)
    assert settings.clear_project_preset(project, "base") == {
        "kind": "base", "preset": "documentary-street", "source": "global"}
    assert settings.preset_default_for("base", project)["source"] == "global"


def test_dead_preset_in_override_is_ignored(studio_env, project):
    """T1.17: id que saiu do catálogo é ignorado — a UI nunca fica presa a um id morto."""
    from studio.common import settings
    path = settings._project_config_path(project)
    path.write_text(json.dumps({"prompter_presets": {"base": "preset-que-nao-existe"}}))
    assert settings.preset_default_for("base", project) == {
        "kind": "base", "preset": None, "source": "code"}
    settings.set_global_preset("base", "documentary-street")
    assert settings.preset_default_for("base", project) == {
        "kind": "base", "preset": "documentary-street", "source": "global"}


def test_preset_setters_validate_kind_and_preset(studio_env):
    """T1.18: ação não registrada e preset fora do catálogo são ValueError; `None` é válido."""
    from studio.common import settings
    with pytest.raises(ValueError):
        settings.set_global_preset("nao-existe", "documentary-street")
    with pytest.raises(ValueError):
        settings.set_global_preset("base", "preset-que-nao-existe")
    assert settings.set_global_preset("base", None) == {
        "kind": "base", "preset": None, "source": "global"}
    assert json.loads(settings.CONFIG_PATH.read_text())["prompter_presets"]["base"] is None


def test_preset_persistence_does_not_touch_the_defaults_key(studio_env):
    """T1.19: a chave nova convive com `defaults` (ADR-016) sem tocá-la."""
    from studio.common import settings
    settings.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.CONFIG_PATH.write_text(json.dumps({"defaults": {"base.image": {"model": "gpt_image_2", "variant": None}}}))
    antes = settings.default_for("base.image")
    settings.set_global_preset("base", "documentary-street")
    cfg = json.loads(settings.CONFIG_PATH.read_text())
    assert cfg["defaults"] == {"base.image": {"model": "gpt_image_2", "variant": None}}
    assert cfg["prompter_presets"] == {"base": "documentary-street"}
    assert settings.default_for("base.image") == antes and antes["source"] == "global"


def test_config_without_the_new_key_still_works(studio_env, project):
    """T1.20: `config.json` antigo (sem `prompter_presets`) segue válido, sem migração."""
    from studio.common import settings
    settings.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.CONFIG_PATH.write_text(json.dumps({"defaults": {"base.image": {"model": "gpt_image_2"}}}))
    assert settings.global_config() == {"defaults": {"base.image": {"model": "gpt_image_2"}}}
    assert settings.preset_default_for("base") == {"kind": "base", "preset": None, "source": "code"}
    assert settings.preset_default_for("base", project)["source"] == "code"
