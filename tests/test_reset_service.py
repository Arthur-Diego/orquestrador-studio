"""`[extensão]` Reset de etapa (cascata) e da campanha — studio/common/reset.py (ADH-OS-20260827-01).

Sem rede (ADR-008): os artefatos-fake vêm de `seed_all_steps`, não de jobs reais.
"""
from __future__ import annotations

import importlib
import json

import pytest

from tests.conftest import RESET_FAKES, files_under, seed_all_steps


def _reset():
    return importlib.import_module("studio.common.reset")


def _new_project(studio_env, name="Gelo Zero", product="energy drink", vibe="snow neon"):
    meta = studio_env["refs"].create_project(name, product, vibe)
    root = studio_env["tmp"] / "projects" / meta["id"]
    return meta["id"], root


def _has_files(root, rel) -> bool:
    return bool(files_under(root, rel))


def test_reset_step_no_meio_apaga_base_e_seguintes(studio_env):
    """base e seguintes voltam ao estado inicial; refs/mood e project.json ficam intactos."""
    reset = _reset()
    pid, root = _new_project(studio_env)
    seed_all_steps(root)

    res = reset.reset_step(pid, "base")
    assert res["kept"] == "project.json"

    # refs e mood (n < 3) permanecem
    assert _has_files(root, "refs") and _has_files(root, "mood")
    # base e todas as seguintes ficam vazias (as pastas existem, sem arquivos dentro)
    for step in ["base", "storyboard", "shots", "animate", "music", "edit", "export", "publish", "prospect"]:
        for rel in RESET_FAKES[step]:
            assert not (root / rel).is_file(), f"{rel} deveria ter sido apagado"
    assert not _has_files(root, "videos") and not _has_files(root, "audio")

    # jobs: mood_ (n=2) fica; base_..export_ (n>=3) somem
    assert (root / "jobs" / "mood_1.json").is_file()
    for f in ["base_1.json", "storyboard_1.json", "shots_1.json", "animate_1.json", "music_1.json", "export_1.json"]:
        assert not (root / "jobs" / f).exists(), f
    # infra compartilhada não é tocada no reset de etapa
    assert (root / "assets" / "a.bin").is_file() and (root / "images" / "i.png").is_file()

    # PROJECT_LAYOUT recriado (pastas vazias voltam a existir)
    assert (root / "base").is_dir() and (root / "storyboard" / "ideas").is_dir()
    assert (root / "audio").is_dir() and (root / "videos").is_dir()

    # project.json intacto
    meta = json.loads((root / "project.json").read_text())
    assert meta["name"] == "Gelo Zero" and meta["product"] == "energy drink" and meta["vibe"] == "snow neon"


def test_reset_step_primeira_etapa_apaga_tudo(studio_env):
    """reset em refs (n=1) cascateia por todas as 11 etapas; só project.json sobrevive nas saídas."""
    reset = _reset()
    pid, root = _new_project(studio_env)
    seed_all_steps(root)

    reset.reset_step(pid, "refs")

    for rels in RESET_FAKES.values():
        for rel in rels:
            assert not (root / rel).is_file(), f"{rel} deveria ter sido apagado"
    for f in ["mood_1.json", "base_1.json", "export_1.json"]:
        assert not (root / "jobs" / f).exists()
    assert json.loads((root / "project.json").read_text())["name"] == "Gelo Zero"
    # camadas do layout recriadas
    assert (root / "refs" / "candidates" / "thumbs").is_dir() and (root / "mood" / "vibe").is_dir()


def test_reset_campaign_apaga_tudo_menos_project(studio_env):
    """Campanha inteira: saídas + infra compartilhada apagadas; project.json mantido; layout recriado."""
    reset = _reset()
    pid, root = _new_project(studio_env)
    seed_all_steps(root)

    res = reset.reset_campaign(pid)
    assert res["kept"] == "project.json"

    # nada de arquivo sobra além do project.json
    remaining = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    assert remaining == ["project.json"], remaining
    # infra compartilhada some também
    assert not (root / "assets" / "a.bin").exists() and not (root / "images" / "i.png").exists()
    # PROJECT_LAYOUT recriado por inteiro
    from studio.config import PROJECT_LAYOUT
    for sub in PROJECT_LAYOUT:
        assert (root / sub).is_dir(), sub
    assert json.loads((root / "project.json").read_text())["vibe"] == "snow neon"


def test_reset_step_idempotente(studio_env):
    """Rodar duas vezes não quebra e mantém o mesmo estado final; project.json permanece."""
    reset = _reset()
    pid, root = _new_project(studio_env)
    seed_all_steps(root)

    reset.reset_step(pid, "storyboard")
    estado1 = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    reset.reset_step(pid, "storyboard")   # não deve levantar exceção
    estado2 = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    assert estado1 == estado2
    assert (root / "project.json").is_file()


def test_reset_pid_inexistente_e_step_desconhecido(studio_env):
    """pid inexistente e etapa desconhecida levantam KeyError (a rota traduz em 404)."""
    reset = _reset()
    pid, _ = _new_project(studio_env)
    with pytest.raises(KeyError):
        reset.reset_step("nao-existe", "base")
    with pytest.raises(KeyError):
        reset.reset_step(pid, "etapa-que-nao-existe")
    with pytest.raises(KeyError):
        reset.reset_campaign("nao-existe")


def test_reset_bloqueado_por_job_em_andamento(studio_env):
    """Job 'running' numa etapa afetada recusa o reset (ResetBlocked → 409 na rota)."""
    reset = _reset()
    pid, root = _new_project(studio_env)
    seed_all_steps(root)

    music = studio_env["svc"]("music")
    music._registry._jobs[pid] = {"state": "running"}     # simula geração de trilha em curso
    with pytest.raises(reset.ResetBlocked):
        reset.reset_step(pid, "base")     # base(n=3) cascateia até music(n=7)
    with pytest.raises(reset.ResetBlocked):
        reset.reset_campaign(pid)
    # nada foi apagado enquanto o job travava
    assert (root / "base" / "base_final.png").is_file()

    music._registry.clear(pid)            # job termina → reset volta a ser aceito
    reset.reset_step(pid, "base")
    assert not (root / "base" / "base_final.png").exists()


def test_reset_bloqueado_por_job_de_refs(studio_env):
    """refs usa registro próprio (dict por pid); o reset também o respeita."""
    reset = _reset()
    pid, root = _new_project(studio_env)
    seed_all_steps(root)

    refs = studio_env["refs"]
    refs._jobs[pid] = {"state": "running"}
    with pytest.raises(reset.ResetBlocked):
        reset.reset_step(pid, "refs")
    refs._jobs.pop(pid)
    reset.reset_step(pid, "refs")
    assert not (root / "refs" / "README.md").exists()
