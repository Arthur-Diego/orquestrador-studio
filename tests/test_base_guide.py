"""Guia da etapa 3 (aula 009) — `studio/etapas/base/guide.py`, leitura pura dos artefatos.

Sem rede e sem navegador (ADR-008): o bot (Claude CLI) é fakeado como em `tests/test_prompter.py`
e os artefatos das etapas 1 e 2 são criados como fixture.
"""
import io
import json
import subprocess

import pytest
from PIL import Image

from tests.conftest import make_image

LONG_EN = ("A giant energy drink can standing on a snowy ridge at dusk, photorealistic cinematic still, "
           "shot on RED Komodo with a 50mm lens at T2.8, cold cyan rim light, volumetric fog, fine film "
           "grain, deep blue and teal palette, low angle hero composition, crisp condensation on the "
           "aluminium surface, distant mountains fading into haze")


def png(w, h, color=(200, 40, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def svc(studio_env):
    return studio_env["svc"]("base")


@pytest.fixture()
def pid(client, studio_env):
    """Projeto com os provides das etapas 1 e 2 (2 referências escolhidas + mood salvo)."""
    p = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energetico Gelo Zero",
                                           "vibe": "snow neon"}).json()["id"]
    root = studio_env["refs"].project_dir(p)
    cands = []
    for i in range(2):
        rid = f"{i}f8e7d6c5b4a"
        make_image(root / "refs" / "brainstorming" / f"{rid}.jpg", color=(20 * i + 10, 60, 200))
        cands.append({"id": rid, "source": "pinterest", "term": "energy drink", "url": "u", "pin_url": None,
                      "alt": "", "file": f"{rid}.jpg", "thumb": f"thumbs/{rid}.jpg", "selected": True})
    (root / "refs" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "refs" / "candidates" / "candidates.json").write_text(json.dumps(cands))
    make_image(root / "mood" / "selected" / "m0.jpg", color=(0, 200, 200))
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0ff0ff"], "note": "neon frio"}))
    return p


def guide_of(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/base")
    assert r.status_code == 200
    return r.json()


def checks(g):
    return {c["id"]: c for c in g["validations"]}


def upload(client, pid, name, data, **form):
    return client.post(f"/api/projects/{pid}/base/import/upload",
                       files=[("files", (name, data, "image/png"))], data=form).json()


def last_of(client, pid, kind):
    return [c for c in client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
            if c["kind"] == kind][-1]["id"]


# ---------- texto da aula (§3.4 da auditoria) ----------
def test_guide_text_comes_from_the_lesson(client, pid):
    g = guide_of(client, pid)
    assert g["id"] == "base" and g["n"] == 3 and g["title"] == "Imagem base" and g["aula"] == "009"
    assert g["next_step"] == "storyboard"
    assert "exata mesma situação" in g["what"] and "High Fidelity V2" in g["what"]
    assert "sessão nova do bot" in g["what"], "B2: a aba nova é do bot"
    low = [c.lower() for c in g["checklist"]]
    assert len(low) >= 8
    assert any("ignorei marca" in c for c in low), "B5"
    assert any("paciência" in c for c in low), "B5"
    assert any("dever de casa" in c for c in low), "B10"
    assert any("mood anexado" in c for c in low)


# ---------- entradas bloqueiam (contrato do preparo) ----------
def test_guide_blocks_without_refs_and_mood(client):
    p = client.post("/api/projects", json={"name": "Guia Vazio", "product": "energetico"}).json()["id"]
    g = guide_of(client, p)
    assert g["status"] == "blocked" and g["progress"] == 0.0
    assert "≥ 1 referência escolhida em refs/brainstorming/ (etapa 1)" in g["missing"]
    assert "≥ 1 imagem em mood/selected/ (etapa 2)" in g["missing"]
    assert {i["step"] for i in g["inputs"] if i.get("step")} == {"refs", "mood"}
    assert g["next_action"].startswith("Antes de continuar")


def test_guide_blocks_without_product(client, studio_env, pid):
    root = studio_env["refs"].project_dir(pid)
    meta = json.loads((root / "project.json").read_text())
    meta["product"] = ""
    (root / "project.json").write_text(json.dumps(meta))
    g = guide_of(client, pid)
    assert g["status"] == "blocked" and "Produto descrito na campanha" in g["missing"]


def test_guide_is_todo_with_inputs_and_no_output(client, pid):
    g = guide_of(client, pid)
    assert g["status"] == "todo" and g["progress"] == 0.0
    assert all(i["status"] == "ok" for i in g["inputs"])
    assert set(checks(g)) == {"situation_chosen", "upscale_2x", "label_applied", "prompt_en",
                              "ref_id_valid", "final_2048", "md_prompts"}
    assert checks(g)["upscale_2x"]["status"] == "todo"
    # wave 4: a próxima ação é curta, no infinitivo, um passo só (estilo do protótipo)
    assert g["next_action"] == "Escolher uma referência e gerar o primeiro prompt de situação"
    assert g["summary"] is None and g["summary_kind"] is None, "sem passo escolhido, sem chip extra"


# ---------- validações da §3.5 ----------
def test_guide_is_in_progress_until_the_chain_of_the_lesson_ends(client, pid):
    """A cadeia da aula é situação → rótulo → upscale: escolher só a situação NÃO fecha a etapa
    (senão o `current` do núcleo pularia a etapa 3 antes do rótulo e do upscale)."""
    upload(client, pid, "s.png", png(2048, 1152), kind="situation", ref_id="0f8e7d6c5b4a", prompt=LONG_EN)
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    g = guide_of(client, pid)
    c = checks(g)
    assert g["status"] == "in_progress" and g["progress"] == 0.5
    assert [o["status"] for o in g["outputs"]] == ["ok", "todo"]
    assert "base/base.md com a cadeia situação → rótulo → upscale e os prompts" in g["missing"]
    assert c["situation_chosen"]["status"] == "ok" and c["md_prompts"]["status"] == "todo"
    assert c["prompt_en"]["status"] == "ok" and "palavras" in c["prompt_en"]["detail"]
    assert c["final_2048"]["status"] == "ok" and c["ref_id_valid"]["status"] == "ok"
    assert "upscale" in g["next_action"].lower(), "a cadeia da aula ainda pede o upscale 2x"
    assert g["summary"] == "cadeia 1/3" and g["summary_kind"] is None, "chip extra da faixa do guia"


def test_guide_done_only_when_the_upscale_closes_the_chain(client, pid):
    upload(client, pid, "s.png", png(1024, 576), kind="situation", ref_id="0f8e7d6c5b4a", prompt=LONG_EN)
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    upload(client, pid, "u.png", png(2048, 1152, (9, 9, 9)), kind="upscale")
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "upscale")})
    g = guide_of(client, pid)
    assert g["status"] == "done" and g["progress"] == 1.0 and not g["missing"]
    assert "concluída" in g["next_action"]
    # com a marca-imagem anexada, a cadeia da aula também exige o rótulo — volta a ficar incompleta
    client.post(f"/api/projects/{pid}/base/brand-image", files={"file": ("m.png", png(64, 64), "image/png")})
    g = guide_of(client, pid)
    assert g["status"] == "in_progress" and checks(g)["label_applied"]["status"] == "warn"
    assert "rótulo" in g["next_action"]


def test_guide_warns_on_short_or_portuguese_prompt(client, pid):
    upload(client, pid, "s.png", png(1024, 576), kind="situation", ref_id="0f8e7d6c5b4a",
           prompt="A lata gigante na mesma situação da imagem de referência")
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    c = checks(guide_of(client, pid))
    assert c["prompt_en"]["status"] == "warn" and "gere pelo bot" in c["prompt_en"]["fix"]
    assert c["final_2048"]["status"] == "warn" and "1024px" in c["final_2048"]["detail"]


def test_guide_upscale_ratio_ok_and_warn(client, pid):
    upload(client, pid, "s.png", png(1024, 576), kind="situation", ref_id="0f8e7d6c5b4a", prompt=LONG_EN)
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    upload(client, pid, "u.png", png(2048, 1152, (9, 9, 9)), kind="upscale")
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "upscale")})
    c = checks(guide_of(client, pid))
    assert c["upscale_2x"]["status"] == "ok" and c["upscale_2x"]["detail"] == "1024px → 2048px (2.0x)"
    assert guide_of(client, pid)["status"] == "done", "a cadeia da aula fechou"

    r = upload(client, pid, "u2.png", png(1130, 640, (3, 3, 3)), kind="upscale")
    assert r["warnings"] and "2x" in r["warnings"][0], "B6: aviso já no import"
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "upscale")})
    g = guide_of(client, pid)
    c = checks(g)
    assert c["upscale_2x"]["status"] == "warn" and "1.1x" in c["upscale_2x"]["detail"]
    assert "High Fidelity V2" in c["upscale_2x"]["fix"]
    assert g["summary"] == "cadeia 2/3" and g["summary_kind"] == "warn", "chip extra pede atenção"


def test_guide_label_check_follows_the_brand_extension(client, pid):
    c = checks(guide_of(client, pid))
    assert c["label_applied"]["status"] == "todo", "sem marca não há o que cobrar"
    client.post(f"/api/projects/{pid}/base/brand-image", files={"file": ("m.png", png(64, 64), "image/png")})
    c = checks(guide_of(client, pid))
    assert c["label_applied"]["status"] == "warn" and "marca anexada" in c["label_applied"]["detail"]

    upload(client, pid, "s.png", png(1024, 576), kind="situation", ref_id="0f8e7d6c5b4a", prompt=LONG_EN)
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    assert "rótulo" in guide_of(client, pid)["next_action"]
    upload(client, pid, "l.png", png(1024, 576, (5, 5, 5)), kind="label", prompt="Replace the label")
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "label")})
    assert checks(guide_of(client, pid))["label_applied"]["status"] == "ok"


def test_guide_warns_on_candidate_without_a_valid_ref(client, pid):
    upload(client, pid, "s.png", png(1024, 576), kind="situation", ref_id="inexistente", prompt=LONG_EN)
    c = checks(guide_of(client, pid))
    assert c["ref_id_valid"]["status"] == "warn" and "1 candidata" in c["ref_id_valid"]["detail"]


def test_guide_uses_the_prompt_the_bot_wrote_when_nothing_is_selected(client, pid, svc, monkeypatch):
    """O bot (Claude CLI) fakeado: o prompt gerado já conta para a validação `prompt_en`."""
    calls = []

    def run(args, capture_output, text, timeout):
        calls.append(args)
        payload = {"prompt": LONG_EN, "negative": "text", "camera": "RED, 50mm", "notes_pt": "ok"}
        return subprocess.CompletedProcess(args, 0, "```json\n" + json.dumps(payload) + "\n```", "")

    monkeypatch.setattr(svc.prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(svc.prompter.subprocess, "run", run)
    assert checks(guide_of(client, pid))["prompt_en"]["status"] == "todo"
    r = client.post(f"/api/projects/{pid}/base/prompts/generate",
                    json={"ref_id": "0f8e7d6c5b4a", "mode": "images"})
    assert r.status_code == 200 and calls, "o bot foi chamado"
    c = checks(guide_of(client, pid))
    assert c["prompt_en"]["status"] == "ok"


# ---------- o hook é puro e barato (contrato do preparo) ----------
def test_guide_writes_nothing(client, pid, studio_env):
    root = studio_env["refs"].project_dir(pid)
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    for _ in range(3):
        guide_of(client, pid)
    client.get(f"/api/projects/{pid}/guide")
    assert sorted(str(p.relative_to(root)) for p in root.rglob("*")) == before
    assert not (root / "base" / "base.md").exists() and not (root / "base" / "prompts.json").exists()


def test_guide_never_unknown_in_the_aggregate(client, pid):
    body = client.get(f"/api/projects/{pid}/guide").json()
    step = next(s for s in body["steps"] if s["id"] == "base")
    assert step["status"] != "unknown" and step["what"] and step["checklist"]
    assert body["total"] == len(body["steps"])


def test_guide_survives_corrupted_json(client, pid, studio_env):
    """O núcleo trata exceção do hook como bug da frente: JSON corrompido não pode virar `unknown`."""
    root = studio_env["refs"].project_dir(pid)
    (root / "base").mkdir(parents=True, exist_ok=True)
    (root / "base" / "candidates.json").write_text("{isto não é json")
    (root / "base" / "brand.json").write_text("{tampouco")
    (root / "refs" / "candidates" / "candidates.json").write_text("[quebrado")
    g = guide_of(client, pid)
    assert g["status"] in {"blocked", "todo"} and "detail" not in g
    assert g["what"] and g["validations"]


# ---------- kind "clean": limpeza de marca `[extensão]` (wave 9) ----------
def test_clean_guide_chip_still_counts_three_course_steps(client, pid):
    """O chip mede a cadeia da AULA (situação → rótulo → upscale). A limpeza é `[extensão]`:
    aparece no detalhe da cadeia, mas não vira um quarto passo do curso."""
    upload(client, pid, "s.png", png(2048, 1152), kind="situation", ref_id="0f8e7d6c5b4a", prompt=LONG_EN)
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    upload(client, pid, "c.png", png(2048, 1152, (40, 200, 40)), kind="clean", prompt="Remove all brand names")
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "clean")})
    g = guide_of(client, pid)
    assert g["summary"] == "cadeia 1/3", "a limpeza não conta como passo da aula"
    detalhe = next(o for o in g["outputs"] if o["id"] == "base_md")["detail"]
    assert "limpeza de marca" in detalhe, "mas aparece no detalhe da cadeia, na ordem dos passos"


def test_clean_guide_does_not_block_the_step(client, pid):
    """A limpeza é opcional: escolhê-la não muda o status da etapa nem a próxima ação."""
    upload(client, pid, "s.png", png(1024, 576), kind="situation", ref_id="0f8e7d6c5b4a", prompt=LONG_EN)
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "situation")})
    antes = guide_of(client, pid)
    upload(client, pid, "c.png", png(1024, 576, (40, 200, 40)), kind="clean", prompt="Remove all brand names")
    client.post(f"/api/projects/{pid}/base/select", json={"id": last_of(client, pid, "clean")})
    depois = guide_of(client, pid)
    assert depois["status"] == antes["status"] and depois["progress"] == antes["progress"]
    assert depois["next_action"] == antes["next_action"] == \
        "Fazer o upscale 2x (High Fidelity V2) e importar como “upscale”"
    assert depois["missing"] == antes["missing"], "a limpeza não passa a bloquear a etapa"
