"""Etapa 3 — a imagem base segue a aula 009: produto na situação da referência, rótulo próprio, upscale 2x.

Sem rede e sem navegador: o CLI da Higgsfield é sempre fakeado (ADR-008) e os artefatos das
etapas 1 e 2 que a etapa consome são criados como fixture aqui (handoff da wave 1).
"""
import json
import threading

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def project(studio_env):
    meta = studio_env["refs"].create_project("Gelo Zero", "energetico Gelo Zero", "snow neon")
    return meta["id"]


@pytest.fixture()
def svc(studio_env):
    return studio_env["svc"]("base")


def prepare(studio_env, pid, n_refs=2, colors=("#0ff0ff", "#1a1a2e"), note="neon frio", mood=2):
    """Cria os provides das etapas 1 e 2 que a etapa 3 consome."""
    root = studio_env["refs"].project_dir(pid)
    cands = []
    for i in range(n_refs):
        rid = f"{i}f8e7d6c5b4a"
        make_image(root / "refs" / "brainstorming" / f"{rid}.jpg", color=(20 * i + 10, 60, 200))
        cands.append({"id": rid, "source": "pinterest", "term": "energy drink snow ads", "url": "u",
                      "pin_url": None, "alt": "", "file": f"{rid}.jpg", "thumb": f"thumbs/{rid}.jpg",
                      "selected": True})
    (root / "refs" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "refs" / "candidates" / "candidates.json").write_text(json.dumps(cands))
    for j in range(mood):
        make_image(root / "mood" / "selected" / f"mood{j}.jpg", color=(0, 200, 200 - 30 * j))
    (root / "mood").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": list(colors), "note": note}))
    return root


# ---------- prompts (passo 5 da aula) ----------
def test_prompts_are_deterministic_and_one_per_selected_ref(studio_env, svc, project):
    prepare(studio_env, project)
    a, b = svc.prompts(project), svc.prompts(project)
    assert a == b, "mesmo insumo, mesmo prompt"
    assert len(a["refs"]) == 2, "um prompt de situação por referência escolhida"
    for r in a["refs"]:
        assert "energetico Gelo Zero" in r["prompt"] and "#0ff0ff" in r["prompt"]
        assert "exact same situation" in r["prompt"]
        assert "No people unless they appear in the reference image" in r["prompt"]
        assert "identical to this one" in r["prompt_no_bias"], "aula 009: prompt sem viés em aba nova"
    assert a["aspect_ratio"] == "16:9" and a["mood_files"] == ["mood/selected/mood0.jpg", "mood/selected/mood1.jpg"]


def test_prompts_ignore_refs_without_file_and_unselected(studio_env, svc, project):
    root = prepare(studio_env, project, n_refs=2)
    (root / "refs" / "brainstorming" / "1f8e7d6c5b4a.jpg").unlink()
    assert len(svc.prompts(project)["refs"]) == 1


def test_prompts_require_refs_and_mood(studio_env, svc, project):
    root = studio_env["refs"].project_dir(project)
    with pytest.raises(ValueError, match="etapa 1"):
        svc.prompts(project)
    prepare(studio_env, project)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": [], "note": ""}))
    with pytest.raises(ValueError, match="etapa 2"):
        svc.prompts(project)


def test_brand_unlocks_label_prompt(studio_env, svc, project):
    prepare(studio_env, project)
    assert svc.prompts(project)["label_prompt"] is None
    assert svc.prompts(project)["label_prompt_ready"] is False
    with pytest.raises(ValueError):
        svc.brand_set(project, "  ")
    svc.brand_set(project, "Gelo Zero", "lightning bolt logo with neon effect")
    assert svc.brand_get(project) == {"name": "Gelo Zero", "description": "lightning bolt logo with neon effect"}
    p = svc.prompts(project)
    assert p["label_prompt_ready"] and "Gelo Zero" in p["label_prompt"]
    assert "lightning bolt logo" in p["label_prompt"] and "identical" in p["label_prompt"]


# ---------- importação ----------
def test_upload_tags_kind_and_ref_and_dedupes(studio_env, svc, project):
    prepare(studio_env, project)
    data = image_bytes()
    assert svc.import_upload(project, [("a.png", data)], "situation", "0f8e7d6c5b4a")["added"] == 1
    assert svc.import_upload(project, [("a.png", data)], "situation", "0f8e7d6c5b4a")["added"] == 0, "dedupe por conteúdo"
    c = svc.load(project)[0]
    assert c["kind"] == "situation" and c["ref_id"] == "0f8e7d6c5b4a"
    assert c["file"].startswith("base/candidates/") and c["thumb"].startswith("base/candidates/thumbs/")
    with pytest.raises(ValueError):
        svc.import_upload(project, [("b.png", image_bytes(color=(1, 2, 3)))], "situacao")


def test_import_downloads_only_recent_images(studio_env, svc, project):
    import os
    import time
    prepare(studio_env, project)
    dl = studio_env["tmp"] / "downloads"
    make_image(dl / "novo.jpg")
    make_image(dl / "novo2.jpg", color=(9, 9, 9))
    old = make_image(dl / "velho.jpg", color=(1, 2, 3))
    os.utime(old, (time.time() - 3 * 3600, time.time() - 3 * 3600))
    r = svc.import_downloads(project, since_minutes=60, kind="upscale")
    assert r["added"] == 2 and r["scanned"] == 2
    assert {c["kind"] for c in svc.load(project)} == {"upscale"}
    with pytest.raises(FileNotFoundError):
        svc.import_downloads(project, folder=str(studio_env["tmp"] / "nao-existe"))


def test_import_history_uses_cli_bridge(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    monkeypatch.setattr(svc.hf, "history_media", lambda kind="image", size=50: [
        {"id": "j1", "prompt": "p", "model": "nano_banana_2", "created": "", "urls": ["http://x/a.png", "http://x/b.png"]}])
    payloads = iter([image_bytes(color=(10, 10, 10)), image_bytes(color=(20, 20, 20))])
    monkeypatch.setattr(svc.ingest, "urlopen", lambda *a, **k: type("R", (), {"read": lambda self: next(payloads)})())
    r = svc.import_history(project, kind="label", ref_id="0f8e7d6c5b4a")
    assert r == {"added": 2, "jobs": 1}
    assert all(c["kind"] == "label" and c["job_id"] == "j1" for c in svc.load(project))


# ---------- seleção, base_final.png e base.md ----------
def _up(svc, pid, kind, color, ref_id=None):
    svc.import_upload(pid, [(f"{kind}{color[0]}.png", image_bytes(color=color))], kind, ref_id)
    return [c for c in svc.load(pid) if c["kind"] == kind][-1]["id"]


def test_select_writes_final_png_and_md_and_is_exclusive_per_kind(studio_env, svc, project):
    from PIL import Image
    root = prepare(studio_env, project)
    svc.brand_set(project, "Gelo Zero", "raio neon")
    s1 = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    s2 = _up(svc, project, "situation", (40, 200, 40), "1f8e7d6c5b4a")
    r = svc.select(project, s1, note="melhor enquadramento")
    assert r == {"final": "base/base_final.png", "kind": "situation",
                 "chain": {"situation": s1, "label": None, "upscale": None}}
    final = root / "base" / "base_final.png"
    src = root / [c for c in svc.load(project) if c["id"] == s1][0]["file"]
    assert final.read_bytes() == src.read_bytes(), "cópia byte a byte da candidata escolhida"
    with Image.open(final) as im:
        assert im.format == "PNG"
    md = (root / "base" / "base.md").read_text()
    assert "Imagem base" in md and "energetico Gelo Zero" in md and "0f8e7d6c5b4a" in md
    assert "**Marca [extensão]:** Gelo Zero" in md and "melhor enquadramento" in md and "#0ff0ff" in md
    svc.select(project, s2)
    sel = [c["id"] for c in svc.load(project) if c["selected"]]
    assert sel == [s2], "no máximo uma selecionada por kind"


def test_chain_advances_and_restarts_when_situation_changes(studio_env, svc, project):
    root = prepare(studio_env, project)
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    lbl = _up(svc, project, "label", (40, 200, 40))
    up = _up(svc, project, "upscale", (40, 40, 200))
    svc.select(project, s)
    svc.select(project, lbl)
    r = svc.select(project, up)
    assert r["kind"] == "upscale" and r["chain"] == {"situation": s, "label": lbl, "upscale": up}
    src = root / [c for c in svc.load(project) if c["id"] == up][0]["file"]
    assert (root / "base" / "base_final.png").read_bytes() == src.read_bytes()
    r = svc.select(project, s)
    assert r["chain"] == {"situation": s, "label": None, "upscale": None}, "trocar a situação recomeça a cadeia"
    assert r["kind"] == "situation"
    with pytest.raises(FileNotFoundError):
        svc.select(project, "naoexiste")


# ---------- custo e geração via CLI ----------
def test_cost_multiplies_per_item_and_propagates_unknown(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: {"credits": 5, "raw": {}})
    c = svc.estimate_cost(project, "situation", count=2)
    assert c["count"] == 4 and c["per_item"] == 5 and c["total"] == 20
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: {"credits": None, "error": "sem login"})
    assert svc.estimate_cost(project, "situation")["total"] is None


def test_cost_sends_the_same_params_the_generation_will_send(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    seen = []
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: seen.append((model, params)) or {"credits": 1})
    svc.estimate_cost(project, "situation", count=2)
    assert seen[0][1] == {"prompt": svc.prompts(project)["refs"][0]["prompt"],
                          "aspect_ratio": "16:9", "resolution": "2k", "count": 2}
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    svc.select(project, s)
    svc.brand_set(project, "Gelo Zero", "raio neon")
    svc.estimate_cost(project, "label")
    assert seen[1][0] == svc.DEFAULT_MODEL_LABEL and "aspect_ratio" not in seen[1][1]


def _fake_cli(svc, monkeypatch, urls_by_call, fail_on=()):
    calls = []
    payloads = {}

    def generate(model, params, timeout_s=600):
        i = len(calls)
        calls.append({"model": model, "params": params})
        if i in fail_on:
            raise RuntimeError("higgsfield: model not found")
        urls = urls_by_call[i]
        for u in urls:
            payloads[u] = image_bytes(color=(10 + 30 * len(payloads), 90, 140))
        return {"raw": {"id": f"job{i}"}, "urls": urls, "id": f"job{i}"}

    def download(url, dest):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payloads[url])
        return dest

    monkeypatch.setattr(svc.hf, "generate", generate)
    monkeypatch.setattr(svc.hf, "download", download)
    return calls


def _wait(svc, pid, timeout=5):
    for _ in range(int(timeout / 0.05)):
        if svc.job_status(pid)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return svc.job_status(pid)


def test_generate_situation_imports_one_call_per_ref(studio_env, svc, project, monkeypatch):
    root = prepare(studio_env, project)
    calls = _fake_cli(svc, monkeypatch, [["http://x/1.png"], ["http://x/2.png"]])
    svc.start_generate(project, "situation")
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 2 and job["done"] == 2
    assert len(calls) == 2 and {c["params"]["image_references"][0].split("/")[-1] for c in calls} == \
        {"0f8e7d6c5b4a.jpg", "1f8e7d6c5b4a.jpg"}
    assert len(calls[0]["params"]["image_references"]) == 3, "referência + até 3 imagens do mood"
    cands = svc.load(project)
    assert all(c["source"] == "cli" and c["kind"] == "situation" and c["model"] == "nano_banana_2" for c in cands)
    assert {c["ref_id"] for c in cands} == {"0f8e7d6c5b4a", "1f8e7d6c5b4a"}
    assert (root / "jobs" / "base_job0.json").exists() and not (root / "jobs" / "_tmp").exists()


def test_generate_situation_multiplies_by_count_and_records_the_job(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    calls = _fake_cli(svc, monkeypatch, [["http://x/1.png", "http://x/2.png"], ["http://x/3.png", "http://x/4.png"]])
    svc.start_generate(project, "situation", count=2)
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 4, "duas referências × duas variações"
    assert all(c["params"]["count"] == 2 for c in calls)
    assert {c["job_id"] for c in svc.load(project)} == {"job0", "job1"}


def test_generate_refuses_concurrent_job(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    gate = threading.Event()
    monkeypatch.setattr(svc.hf, "generate",
                        lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    svc.start_generate(project, "situation")
    with pytest.raises(RuntimeError):
        svc.start_generate(project, "situation")
    gate.set()
    assert _wait(svc, project)["state"] == "done"


def test_generate_partial_failure_keeps_what_worked(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    _fake_cli(svc, monkeypatch, [[], ["http://x/2.png"]], fail_on=(0,))
    svc.start_generate(project, "situation")
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 1
    assert any(line.startswith("erro:") for line in job["log"])


def test_generate_total_failure_is_an_error_job(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    _fake_cli(svc, monkeypatch, [[], []], fail_on=(0, 1))
    svc.start_generate(project, "situation")
    job = _wait(svc, project)
    assert job["state"] == "error" and "model not found" in job["error"]


def test_generate_label_requires_situation_and_brand(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    calls = _fake_cli(svc, monkeypatch, [["http://x/l.png"]])
    with pytest.raises(ValueError, match="situação"):
        svc.start_generate(project, "label")
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    svc.select(project, s)
    with pytest.raises(ValueError, match="marca"):
        svc.start_generate(project, "label")
    svc.brand_set(project, "Gelo Zero", "raio neon")
    svc.start_generate(project, "label")
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 1
    assert calls[0]["params"]["image_references"] == [str(studio_env["refs"].project_dir(project)
                                                         / [c for c in svc.load(project) if c["id"] == s][0]["file"])]
    assert "Gelo Zero" in calls[0]["params"]["prompt"] and "raio neon" in calls[0]["params"]["prompt"]
    assert [c["kind"] for c in svc.load(project) if c["source"] == "cli"] == ["label"]


def test_generate_upscale_uses_the_most_advanced_selection(studio_env, svc, project, monkeypatch):
    root = prepare(studio_env, project)
    calls = _fake_cli(svc, monkeypatch, [["http://x/u.png"]])
    with pytest.raises(ValueError, match="ampliada"):
        svc.start_generate(project, "upscale")
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    lbl = _up(svc, project, "label", (40, 200, 40))
    svc.select(project, s)
    svc.select(project, lbl)
    svc.start_generate(project, "upscale", model=None)
    job = _wait(svc, project)
    assert job["state"] == "done"
    assert calls[0]["model"] == svc.DEFAULT_MODEL_UPSCALE
    assert calls[0]["params"]["image_references"] == [str(root / [c for c in svc.load(project) if c["id"] == lbl][0]["file"])]
    assert "prompt" not in calls[0]["params"]
