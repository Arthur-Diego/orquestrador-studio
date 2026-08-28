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
