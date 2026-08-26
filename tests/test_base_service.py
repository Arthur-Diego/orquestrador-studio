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


def _fake_claude(svc, monkeypatch, prompt="A cinematic can in the snow", negative="text", camera="RED, 50mm"):
    """O bot da aula (Claude CLI) fakeado como em tests/test_prompter.py — sem rede (ADR-008)."""
    import subprocess
    calls = []
    payload = {"prompt": prompt, "negative": negative, "camera": camera, "notes_pt": "ok"}

    def run(args, capture_output, text, timeout):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "```json\n" + json.dumps(payload) + "\n```", "")

    monkeypatch.setattr(svc.prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(svc.prompter.subprocess, "run", run)
    return calls


# ---------- prompts (passos 2 a 5 da aula) ----------
def test_prompts_fallback_is_deterministic_and_one_per_selected_ref(studio_env, svc, project):
    """Sem Claude, o template de fallback é determinístico (B1: o critério de igualdade da wave 1
    vale para o fallback; o prompt da aula vem do bot e varia)."""
    prepare(studio_env, project)
    a, b = svc.prompts(project), svc.prompts(project)
    assert a == b, "mesmo insumo, mesmo prompt de fallback"
    assert len(a["refs"]) == 2, "um prompt de situação por referência escolhida"
    for r in a["refs"]:
        assert "energetico Gelo Zero" in r["prompt"] and "#0ff0ff" in r["prompt"]
        assert "exact same situation" in r["prompt"] and r["prompt_source"] == "template"
        assert "identical to this one" in r["bot_instruction"], "B2: instrução para o bot, não prompt"
        assert r["bot_instruction"] != r["prompt"]
        assert "No people" not in r["prompt"], "B11: a frase é opcional na etapa 3"
    assert a["aspect_ratio"] == "16:9" and a["mood_files"] == ["mood/selected/mood0.jpg", "mood/selected/mood1.jpg"]


def test_hints_say_the_new_tab_is_the_bots(studio_env, svc, project):
    """B2: a 'aba nova' da aula é do bot; a Higgsfield só recebe o prompt pronto."""
    prepare(studio_env, project)
    p = svc.prompts(project)
    assert "aba nova" in p["bot_hint"] and "bot" in p["bot_hint"].lower()
    assert "aba nova" not in p["ui_hint"] and "Higgsfield" in p["ui_hint"]
    assert "mood" in p["ui_hint"] and "16:9" in p["ui_hint"]


def test_prompts_ignore_refs_without_file_and_unselected(studio_env, svc, project):
    root = prepare(studio_env, project, n_refs=2)
    (root / "refs" / "brainstorming" / "1f8e7d6c5b4a.jpg").unlink()
    assert len(svc.prompts(project)["refs"]) == 1


def test_prompts_require_refs_and_mood_images(studio_env, svc, project):
    """B3: o mood entra como IMAGEM (o print que a aula mostra ao bot); os hex são opcionais."""
    import shutil
    root = studio_env["refs"].project_dir(project)
    with pytest.raises(ValueError, match="etapa 1"):
        svc.prompts(project)
    prepare(studio_env, project)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": [], "note": ""}))
    p = svc.prompts(project)
    assert p["palette"] == {"colors": [], "note": ""}, "paleta vazia não bloqueia mais"
    assert "campaign mood" not in p["refs"][0]["prompt"]
    shutil.rmtree(root / "mood" / "selected")
    with pytest.raises(ValueError, match="etapa 2"):
        svc.prompts(project)


def test_generate_prompt_calls_the_bot_with_reference_and_mood(studio_env, svc, project, monkeypatch):
    """B1: o prompt de situação nasce do bot olhando a referência + o mood da campanha."""
    root = prepare(studio_env, project)
    calls = _fake_claude(svc, monkeypatch, "A giant can on a snowy ridge, RED Komodo, 50mm")
    e = svc.generate_prompt(project, "0f8e7d6c5b4a", "images", "a lata está gigante")
    assert e["source"] == "claude" and e["prompt"].startswith("A giant can")
    assert e["mode"] == "images" and e["ref_id"] == "0f8e7d6c5b4a" and e["no_bias"] is False
    cmd = calls[0][2]
    assert str(root / "refs" / "brainstorming" / "0f8e7d6c5b4a.jpg") in cmd
    assert str(root / "mood" / "selected" / "mood0.jpg") in cmd, "o bot vê o mood (o 'print' da aula)"
    assert "a lata está gigante" in cmd and "energetico Gelo Zero" in cmd, "instrução + brief da campanha"
    # o prompt gerado passa a ser o prompt daquela referência
    p = svc.prompts(project)
    ref = next(r for r in p["refs"] if r["ref_id"] == "0f8e7d6c5b4a")
    assert ref["prompt"] == e["prompt"] and ref["prompt_source"] == "claude"
    assert p["refs"][1]["prompt_source"] == "template", "a outra referência continua no fallback"
    assert svc.prompt_history(project)[0]["prompt"] == e["prompt"]


def test_generate_prompt_without_bias_sends_only_the_reference(studio_env, svc, project, monkeypatch):
    """B2/aula 009: sessão nova sem contexto — só a referência, sem brief e sem mood."""
    root = prepare(studio_env, project)
    calls = _fake_claude(svc, monkeypatch, "An identical image, but on a snowy mountain")
    e = svc.generate_prompt(project, "0f8e7d6c5b4a", "images", "o energético gigante numa montanha de neve",
                            no_bias=True)
    cmd = calls[0][2]
    assert e["no_bias"] is True
    assert str(root / "refs" / "brainstorming" / "0f8e7d6c5b4a.jpg") in cmd
    assert "mood/selected" not in cmd, "sem mood: o bot não pode saber da campanha"
    assert "snow neon" not in cmd, "sem a vibe do projeto (brief) — é isso que tira o viés"
    assert "neon frio" not in cmd and "#0ff0ff" not in cmd, "sem a nota e a paleta do mood"
    assert "Vibe:" not in cmd and "Aesthetic reference" not in cmd, "nenhum campo do brief"
    assert "energetico Gelo Zero" in cmd, "o PRODUTO vai: a aula pede 'o energético gigante está…'"
    assert "identical to this one" in cmd and "montanha de neve" in cmd


def test_generate_prompt_modes_template_and_no_people(studio_env, svc, project, monkeypatch):
    """B11: 'No people' vira opcional; sem Claude o modo template continua funcionando."""
    prepare(studio_env, project)
    monkeypatch.setattr(svc.prompter, "BIN", None)
    t = svc.generate_prompt(project, "0f8e7d6c5b4a", "template")
    assert t["source"] == "template" and "No people" not in t["prompt"]
    t2 = svc.generate_prompt(project, "0f8e7d6c5b4a", "template", no_people=True)
    assert "No people unless they appear in the reference image" in t2["prompt"]
    with pytest.raises(RuntimeError, match="indisponível"):
        svc.generate_prompt(project, "0f8e7d6c5b4a", "images")
    with pytest.raises(ValueError, match="mode"):
        svc.generate_prompt(project, "0f8e7d6c5b4a", "magico")
    with pytest.raises(ValueError, match="referência inexistente"):
        svc.generate_prompt(project, "naoexiste", "template")


def test_generate_prompt_brief_mode_has_no_images(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    calls = _fake_claude(svc, monkeypatch, "A cinematic can in the snow")
    e = svc.generate_prompt(project, None, "brief", "sem imagens")
    assert e["images"] == [] and "--allowedTools" not in calls[0]
    assert e["ref_id"] == "0f8e7d6c5b4a", "sem ref_id usa a primeira referência escolhida"


def test_project_aspect_ratio_drives_prompts_and_cli(studio_env, svc, project, monkeypatch):
    """G3: o formato vem do projeto (aula 007 manda escolher pelo destino), não fixo em 16:9."""
    root = prepare(studio_env, project)
    meta = json.loads((root / "project.json").read_text())
    meta["aspect_ratio"] = "9:16"
    (root / "project.json").write_text(json.dumps(meta))
    p = svc.prompts(project)
    assert p["aspect_ratio"] == "9:16" and "9:16" in p["ui_hint"]
    seen = []
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: seen.append(params) or {"credits": 1})
    svc.estimate_cost(project, "situation")
    assert seen[0]["aspect_ratio"] == "9:16"
    meta["aspect_ratio"] = "coisa-errada"
    (root / "project.json").write_text(json.dumps(meta))
    assert svc.prompts(project)["aspect_ratio"] == "16:9", "valor inválido cai no default"



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
    assert r == {"added": 2, "jobs": 1, "warnings": []}
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
    calls = _fake_cli(svc, monkeypatch, [["http://x/l1.png"], ["http://x/l2.png"], ["http://x/l3.png"]])
    with pytest.raises(ValueError, match="situação"):
        svc.start_generate(project, "label")
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    svc.select(project, s)
    with pytest.raises(ValueError, match="marca"):
        svc.start_generate(project, "label")
    svc.brand_set(project, "Gelo Zero", "raio neon")
    j = svc.start_generate(project, "label")
    assert j["total"] == 3, "B4: a aula gera 3 variações do rótulo por vez"
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 3 and len(calls) == 3
    assert calls[0]["params"]["image_references"] == [str(studio_env["refs"].project_dir(project)
                                                         / [c for c in svc.load(project) if c["id"] == s][0]["file"])]
    assert "Gelo Zero" in calls[0]["params"]["prompt"] and "raio neon" in calls[0]["params"]["prompt"]
    assert [c["kind"] for c in svc.load(project) if c["source"] == "cli"] == ["label"] * 3


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


# ---------- correções da wave 2 (auditoria de fidelidade, etapa 3) ----------
def _png(w, h, color=(200, 40, 40)):
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def test_upscale_import_warns_when_it_is_not_2x(studio_env, svc, project):
    """B6: a aula manda '2x, preset High Fidelity V2' — o import confere e avisa."""
    prepare(studio_env, project)
    svc.import_upload(project, [("s.png", _png(1024, 576))], "situation", "0f8e7d6c5b4a")
    sit = [c for c in svc.load(project) if c["kind"] == "situation"][0]
    svc.select(project, sit["id"])
    r = svc.import_upload(project, [("u1.png", _png(1130, 640, (10, 20, 30)))], "upscale")
    assert r["added"] == 1 and len(r["warnings"]) == 1
    assert "2x" in r["warnings"][0] and "1.1x" in r["warnings"][0]
    r2 = svc.import_upload(project, [("u2.png", _png(2048, 1152, (40, 50, 60)))], "upscale")
    assert r2["added"] == 1 and r2["warnings"] == [], "2x exato não avisa"
    assert svc.import_upload(project, [("s2.png", _png(800, 600, (7, 7, 7)))], "situation")["warnings"] == []


def test_upscale_ratio_reads_the_selected_chain(studio_env, svc, project):
    root = prepare(studio_env, project)
    svc.import_upload(project, [("s.png", _png(1024, 576))], "situation", "0f8e7d6c5b4a")
    svc.import_upload(project, [("u.png", _png(2048, 1152, (10, 20, 30)))], "upscale")
    cands = svc.load(project)
    svc.select(project, [c for c in cands if c["kind"] == "situation"][0]["id"])
    svc.select(project, [c for c in cands if c["kind"] == "upscale"][0]["id"])
    ratio, w0, w1 = svc.upscale_ratio(root, svc.load(project))
    assert (ratio, w0, w1) == (2.0, 1024, 2048)


def test_label_defaults_to_three_variations(studio_env, svc, project, monkeypatch):
    """B4: a aula reescreve a instrução do rótulo e gera 3 variações."""
    prepare(studio_env, project)
    svc.brand_set(project, "Gelo Zero", "raio neon")
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    svc.select(project, s)
    seen = []
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: seen.append(params) or {"credits": 2})
    assert svc.estimate_cost(project, "label")["count"] == 3
    assert svc.estimate_cost(project, "label", count=1)["count"] == 1
    assert svc.estimate_cost(project, "situation")["count"] == 2, "situação continua 1 por referência"


def test_edited_prompt_wins_over_history_and_template(studio_env, svc, project, monkeypatch):
    """B4: o texto editado na tela é o que vai ao CLI."""
    prepare(studio_env, project)
    seen = []
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: seen.append(params) or {"credits": 1})
    svc.estimate_cost(project, "situation", prompt="  A totally custom prompt  ")
    assert seen[0]["prompt"] == "A totally custom prompt"


def test_base_md_keeps_the_whole_prompt_and_the_bot_instruction(studio_env, svc, project, monkeypatch):
    """B4/B10: base.md guarda a instrução usada inteira — é o que o dever de casa pede."""
    root = prepare(studio_env, project)
    _fake_claude(svc, monkeypatch, "A giant can on a snowy ridge shot on RED Komodo with a 50mm lens " * 3)
    svc.generate_prompt(project, "0f8e7d6c5b4a", "images", "a lata está gigante")
    svc.brand_set(project, "Gelo Zero", "raio neon")
    long_prompt = svc.prompts(project)["refs"][0]["prompt"]
    svc.import_upload(project, [("s.png", _png(1024, 576))], "situation", "0f8e7d6c5b4a", long_prompt)
    sit = [c for c in svc.load(project) if c["kind"] == "situation"][0]
    svc.select(project, sit["id"])
    md = (root / "base" / "base.md").read_text()
    assert "## Prompts e instruções usados" in md and long_prompt in md, "prompt inteiro, não truncado"
    assert "Instrução ao bot (sessão nova, sem viés)" in md and "a lata está gigante" in md
    assert "Dever de casa (aula 009)" in md and "comunidade" in md


def test_generate_situation_uses_the_prompt_the_bot_wrote(studio_env, svc, project, monkeypatch):
    prepare(studio_env, project)
    _fake_claude(svc, monkeypatch, "Bot written prompt for ref zero")
    svc.generate_prompt(project, "0f8e7d6c5b4a", "images")
    calls = _fake_cli(svc, monkeypatch, [["http://x/1.png"], ["http://x/2.png"]])
    svc.start_generate(project, "situation")
    _wait(svc, project)
    prompts = {c["params"]["prompt"] for c in calls}
    assert "Bot written prompt for ref zero" in prompts, "a referência com prompt do bot usa o do bot"
    assert any("exact same situation" in p for p in prompts), "a outra continua no fallback"


def test_generate_sends_the_project_aspect_ratio_to_the_cli(studio_env, svc, project, monkeypatch):
    """G3 no caminho pago: `start_generate` sem aspect_ratio usa o formato da campanha."""
    root = prepare(studio_env, project)
    meta = json.loads((root / "project.json").read_text())
    meta["aspect_ratio"] = "9:16"
    (root / "project.json").write_text(json.dumps(meta))
    calls = _fake_cli(svc, monkeypatch, [["http://x/1.png"], ["http://x/2.png"]])
    svc.start_generate(project, "situation")
    _wait(svc, project)
    assert {c["params"]["aspect_ratio"] for c in calls} == {"9:16"}


def test_base_md_keeps_the_label_instruction_in_full(studio_env, svc, project):
    """§13.5: a instrução de rótulo usada aparece inteira em base.md (o dever de casa pede o prompt)."""
    root = prepare(studio_env, project)
    svc.brand_set(project, "Gelo Zero", "raio neon")
    instrucao = ("Replace the product label. Keep the can colors, but add a lightning bolt logo with a "
                 "neon effect, exactly like the sketch, keeping every other element identical.")
    s = _up(svc, project, "situation", (200, 40, 40), "0f8e7d6c5b4a")
    svc.import_upload(project, [("l.png", image_bytes(color=(40, 200, 40)))], "label", None, instrucao)
    svc.select(project, s)
    svc.select(project, [c for c in svc.load(project) if c["kind"] == "label"][-1]["id"])
    md = (root / "base" / "base.md").read_text()
    assert "### Rótulo" in md and instrucao in md, "instrução de rótulo inteira, não truncada"
