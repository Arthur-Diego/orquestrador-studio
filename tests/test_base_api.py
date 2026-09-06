"""Contrato HTTP da etapa 3 (Imagem base) — FastAPI TestClient, sem rede e sem navegador."""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def hf(studio_env):
    import studio.higgsfield as hf_module
    return hf_module


@pytest.fixture()
def pid(client, studio_env):
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
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0ff0ff", "#1a1a2e"], "note": "neon frio"}))
    return p


def test_step_is_published_as_ready(client):
    # Wave 10 · E7 (card [REACT-08]): a etapa 3 virou React (`studio/etapas/base/ui/index.tsx`);
    # `view.{html,js}` foram removidos. O catálogo de etapas (backend) continua publicando a etapa
    # como `ready`; o contrato de DOM/comportamento da tela mora agora no substituto Vitest
    # (`studio/etapas/base/ui/index.test.tsx`).
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "base")
    assert step["status"] == "ready" and step["n"] == 3 and step["aula"] == "009"


def test_prompts_endpoint(client, pid):
    r = client.get(f"/api/projects/{pid}/base/prompts")
    assert r.status_code == 200
    body = r.json()
    assert len(body["refs"]) == 2 and body["label_ready"] is False and body["model"] == "nano_banana_2"
    assert body["mood_files"] == ["mood/selected/m0.jpg"]
    assert body["aspect_ratio"] == "16:9" and body["label_count"] == 3
    assert "aba nova" in body["bot_hint"] and "aba nova" not in body["ui_hint"]
    ref = body["refs"][0]
    assert ref["prompt_source"] == "template" and ref["bot_instruction"] != ref["prompt"]
    assert client.get(f"/api/projects/{pid}/base/prompts", params={"model": "gpt_image_2"}).json()["model"] == "gpt_image_2"
    assert client.get("/api/projects/nao-existe/base/prompts").status_code == 404


#: Prompt no padrão do bot (parágrafo + 5 linhas) para exercitar a proveniência ponta a ponta.
_FIVE_LINE_PROMPT = (
    "Ultra-realistic product photography of an energy drink can in a snowy forest at dusk.\n\n"
    "Camera: RED Komodo 6K, 50mm, T2.8, shallow depth of field.\n"
    "Lighting: diffused cold key, neon rim lights on both sides.\n"
    "Composition: clean, minimal, premium, centered hero shot.\n"
    "Color grading: icy blues, teal shadows, neon cyan highlights.\n"
    "Style: futuristic winter commercial, ultra-photorealistic, no illustration."
)


def test_prompts_endpoint_carries_provenance(client, pid):
    """base-prompt-provenance (FDD §2/§3): cada referência já vem com a proveniência do prompt
    exibido (o template de fallback), além dos insumos visuais da junção (mood + paleta)."""
    body = client.get(f"/api/projects/{pid}/base/prompts").json()
    assert body["mood_files"] == ["mood/selected/m0.jpg"]
    assert body["palette"]["colors"] == ["#0ff0ff", "#1a1a2e"]
    ref = body["refs"][0]
    assert "provenance" in ref and set(ref["provenance"]) == {"paragraph", "parts"}
    # o template da base não segue as 5 linhas → degradação graciosa: sem partes, mas com parágrafo
    assert ref["provenance"]["parts"] == [] and ref["provenance"]["paragraph"]


def test_generate_returns_labeled_provenance(client, pid, monkeypatch):
    """FDD §1/§2: com um prompt no padrão do bot, o retorno traz `provenance.parts` rotuladas por
    `from` (reference/mood/technical) + o parágrafo, e os insumos visuais (mood_refs + palette)."""
    import json as _json

    from studio.common import prompter

    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")

    def fake_run(args, capture_output, text, timeout):
        import subprocess
        payload = {"prompt": _FIVE_LINE_PROMPT, "negative": "", "camera": "", "notes_pt": ""}
        return subprocess.CompletedProcess(args, 0, "```json\n" + _json.dumps(payload) + "\n```", "")

    monkeypatch.setattr(prompter.subprocess, "run", fake_run)
    r = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "images"})
    assert r.status_code == 200
    prov = r.json()["provenance"]
    assert prov["paragraph"].startswith("Ultra-realistic")
    by_label = {p["label"]: p["from"] for p in prov["parts"]}
    assert by_label == {"Camera": "technical", "Lighting": "mood", "Composition": "reference",
                        "Color grading": "mood", "Style": "mood"}
    assert all(part["text"] for part in prov["parts"])
    # insumos visuais da junção mood × referência, em caminhos relativos para thumbs
    assert r.json()["mood_refs"] == [{"file": "mood/selected/m0.jpg", "board": None}]
    assert r.json()["palette"]["colors"] == ["#0ff0ff", "#1a1a2e"]
    # persiste no histórico (prompts.json)
    hist = client.get(f"/api/projects/{pid}/base/prompts/history").json()
    assert hist[0]["provenance"]["parts"][0]["from"] == "technical"
    # e o prompts() já reflete a proveniência do prompt novo
    ref = client.get(f"/api/projects/{pid}/base/prompts").json()["refs"][0]
    assert {p["from"] for p in ref["provenance"]["parts"]} == {"reference", "mood", "technical"}


def test_generate_provenance_is_robust_to_missing_lines(client, pid):
    """Robustez (FDD §1): prompt fora do formato (template) → `provenance` com partes vazias e o
    prompt inteiro no parágrafo, sem quebrar o retorno."""
    r = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "template"})
    assert r.status_code == 200
    prov = r.json()["provenance"]
    assert prov["parts"] == [] and prov["paragraph"]


def test_prompts_422_without_inputs(client, studio_env):
    p = client.post("/api/projects", json={"name": "Vazio", "product": "x"}).json()["id"]
    r = client.get(f"/api/projects/{p}/base/prompts")
    assert r.status_code == 422 and "etapa 1" in r.json()["detail"]


def test_prompt_generate_over_http(client, pid, studio_env, monkeypatch):
    """B1/B2 pelo contrato HTTP: modos do bot, sem viés e os erros mapeados."""
    from studio.common import prompter
    assert client.get(f"/api/projects/{pid}/base/prompter").json()["modes"] == ["images", "brief", "template"]
    monkeypatch.setattr(prompter, "BIN", None)
    r = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "images"})
    assert r.status_code == 409 and "indisponível" in r.json()["detail"]
    r = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "template", "no_people": True})
    assert r.status_code == 200 and "No people" in r.json()["prompt"] and r.json()["source"] == "template"
    assert client.get(f"/api/projects/{pid}/base/prompts/history").json()[0]["mode"] == "template"
    assert client.post(f"/api/projects/{pid}/base/prompts/generate",
                       json={"mode": "template", "ref_id": "naoexiste"}).status_code == 422
    assert client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "magico"}).status_code == 422

    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "brief"}).status_code == 502


def test_prompts_422_without_mood_images(client, studio_env):
    """B3: sem imagem em mood/selected/ a etapa 3 não começa — o bot precisa ver o mood."""
    import json as _json
    p = client.post("/api/projects", json={"name": "Sem Mood", "product": "x"}).json()["id"]
    root = studio_env["refs"].project_dir(p)
    make_image(root / "refs" / "brainstorming" / "aaaaaaaaaaaa.jpg")
    (root / "refs" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "refs" / "candidates" / "candidates.json").write_text(_json.dumps(
        [{"id": "aaaaaaaaaaaa", "source": "pinterest", "term": "t", "url": "u", "pin_url": None,
          "alt": "", "file": "aaaaaaaaaaaa.jpg", "thumb": None, "selected": True}]))
    r = client.get(f"/api/projects/{p}/base/prompts")
    assert r.status_code == 422 and "etapa 2" in r.json()["detail"] and "mood" in r.json()["detail"]


def test_brand_image_roundtrip(client, pid):
    """Marca do rótulo por IMAGEM: vazio → upload → get devolve o arquivo → o rótulo fica pronto."""
    assert client.get(f"/api/projects/{pid}/base/brand-image").json() == {}
    # arquivo inválido (não é imagem) → 422
    assert client.post(f"/api/projects/{pid}/base/brand-image",
                       files={"file": ("m.txt", b"nao sou imagem", "text/plain")}).status_code == 422
    r = client.post(f"/api/projects/{pid}/base/brand-image",
                    files={"file": ("marca.png", image_bytes(), "image/png")})
    assert r.status_code == 200 and r.json() == {"file": "brand_image.png"}
    assert client.get(f"/api/projects/{pid}/base/brand-image").json() == {"file": "brand_image.png"}
    assert client.get(f"/api/projects/{pid}/base/prompts").json()["label_ready"] is True
    # remover
    assert client.request("DELETE", f"/api/projects/{pid}/base/brand-image").status_code == 200
    assert client.get(f"/api/projects/{pid}/base/brand-image").json() == {}


def test_upload_import_and_limits(client, pid, monkeypatch):
    r = client.post(f"/api/projects/{pid}/base/import/upload",
                    files=[("files", ("a.png", image_bytes(), "image/png"))],
                    data={"kind": "situation", "ref_id": "0f8e7d6c5b4a"})
    assert r.status_code == 200 and r.json() == {"added": 1, "warnings": []}
    body = client.get(f"/api/projects/{pid}/base/candidates").json()
    assert body["final"] is None and len(body["candidates"]) == 1
    c = body["candidates"][0]
    assert c["kind"] == "situation" and c["ref_id"] == "0f8e7d6c5b4a" and c["file"].startswith("base/candidates/")
    assert client.post(f"/api/projects/{pid}/base/import/upload",
                       files=[("files", ("b.png", image_bytes(color=(1, 2, 3)), "image/png"))],
                       data={"kind": "situacao"}).status_code == 422
    from studio.etapas.base import router as base_router
    monkeypatch.setattr(base_router, "MAX_UPLOAD_BYTES", 10)
    assert client.post(f"/api/projects/{pid}/base/import/upload",
                       files=[("files", ("c.png", image_bytes(color=(9, 9, 9)), "image/png"))],
                       data={"kind": "situation"}).status_code == 413


def test_downloads_import(client, pid, studio_env):
    make_image(studio_env["tmp"] / "downloads" / "novo.jpg")
    r = client.post(f"/api/projects/{pid}/base/import/downloads", json={"since_minutes": 60, "kind": "upscale"})
    assert r.status_code == 200 and r.json()["added"] == 1
    assert client.post(f"/api/projects/{pid}/base/import/downloads",
                       json={"folder": str(studio_env["tmp"] / "nao-existe")}).status_code == 404


def test_history_import_maps_cli_failures(client, pid, hf, monkeypatch):
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/base/import/history", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: (_ for _ in ()).throw(RuntimeError("boom")))
    assert client.post(f"/api/projects/{pid}/base/import/history", json={"kind": "situation"}).status_code == 502
    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: [])
    r = client.post(f"/api/projects/{pid}/base/import/history", json={"kind": "situation"})
    assert r.status_code == 200 and r.json() == {"added": 0, "jobs": 0, "warnings": []}


def test_cost_requires_cli(client, pid, hf, monkeypatch):
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/base/cost", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 4, "raw": {}})
    r = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "situation", "count": 2})
    assert r.status_code == 200 and r.json()["total"] == 16 and r.json()["count"] == 4


def test_generate_gates_and_job(client, pid, hf, monkeypatch):
    import threading
    # `new_candidates` `[extensão]` (F11, FDD §5 contrato 1): sempre presente, `[]` sem job.
    assert client.get(f"/api/projects/{pid}/base/job").json() == {"state": "idle", "new_candidates": []}
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": False})
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "label"}).status_code == 422
    gate = threading.Event()
    monkeypatch.setattr(hf, "generate", lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    r = client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"})
    assert r.status_code == 200 and r.json()["state"] == "running" and r.json()["total"] == 2
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"}).status_code == 409
    gate.set()
    for _ in range(100):
        if client.get(f"/api/projects/{pid}/base/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{pid}/base/job").json()["state"] == "done"
def _seed_situation(client, pid):
    """Importa e escolhe uma candidata de situação (origem da cadeia p/ rótulo e upscale)."""
    client.post(f"/api/projects/{pid}/base/import/upload",
                files=[("files", ("s.png", image_bytes(), "image/png"))],
                data={"kind": "situation", "ref_id": "0f8e7d6c5b4a"})
    cid = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"][0]["id"]
    client.post(f"/api/projects/{pid}/base/select", json={"id": cid})
    return cid


def test_cost_for_the_three_kinds(client, pid, hf, monkeypatch):
    """base-cli-generation §3: `base/cost` responde para os 3 kinds com o CUSTO REAL do CLI
    (`hf.cost` mockado). O upscale usa outro modelo (`bytedance_image_upscale`) → custo diferente."""
    _seed_situation(client, pid)
    client.post(f"/api/projects/{pid}/base/brand-image", files={"file": ("marca.png", image_bytes(), "image/png")})
    monkeypatch.setattr(hf, "available", lambda: True)
    # custo por MODELO: upscale (bytedance) difere da geração (nano_banana_2) — a UI mostra por passo
    monkeypatch.setattr(hf, "cost",
                        lambda model, params: {"credits": 9 if "upscale" in model else 4, "model": model, "raw": {}})

    sit = client.post(f"/api/projects/{pid}/base/cost",
                      json={"kind": "situation", "ref_ids": ["0f8e7d6c5b4a"]}).json()
    assert sit["per_item"] == 4 and sit["count"] == 1 and sit["total"] == 4 and sit["raw"]["model"] == "nano_banana_2"

    lab = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "label"}).json()
    assert lab["per_item"] == 4 and lab["count"] == 3 and lab["total"] == 12  # rótulo: 3 por passo (B4)

    up = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "upscale"}).json()
    assert up["per_item"] == 9 and up["count"] == 1 and up["total"] == 9, "upscale usa outro modelo → custo diferente"
    assert up["raw"]["model"] == "bytedance_image_upscale"


def test_cost_when_logged_out_is_null_without_500(client, pid, hf, monkeypatch):
    """base-cli-generation §1/§2: CLI deslogado devolve credits=null (+ erro) — a UI avisa e mantém
    o import. O endpoint NÃO pode dar 500: responde 200 com `total=null` para a tela tratar."""
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": None, "error": "No workspace selected", "raw": {}})
    r = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "situation", "ref_ids": ["0f8e7d6c5b4a"]})
    assert r.status_code == 200
    body = r.json()
    assert body["per_item"] is None and body["total"] is None


def test_generate_download_and_before_after_over_http(client, pid, hf, monkeypatch):
    """base-cli-generation §1: depois de gerar via CLI os resultados viram candidatas servidas por
    `/files/{pid}/...` (download com `<a download>`) e a origem da cadeia existe p/ o antes→depois."""
    import threading

    _seed_situation(client, pid)  # origem da cadeia (a "antes" do rótulo/upscale)
    client.post(f"/api/projects/{pid}/base/brand-image", files={"file": ("marca.png", image_bytes(), "image/png")})
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})

    def fake_generate(model, params):
        return {"urls": ["https://cdn.higgsfield/x/out.png"], "id": "job1", "raw": {}}

    monkeypatch.setattr(hf, "generate", fake_generate)
    monkeypatch.setattr(hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                           dest.write_bytes(image_bytes(color=(7, 8, 9))), dest)[-1])
    r = client.post(f"/api/projects/{pid}/base/generate", json={"kind": "label"})
    assert r.status_code == 200 and r.json()["state"] == "running"
    for _ in range(100):
        if client.get(f"/api/projects/{pid}/base/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{pid}/base/job").json()["state"] == "done"
    cands = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
    gen = [c for c in cands if c["kind"] == "label"]
    assert gen, "a geração via CLI entrou como candidata do passo (rótulo)"
    # o arquivo é servido por /files/{pid}/... (o <a download> da UI aponta pra cá)
    assert client.get(f"/files/{pid}/{gen[0]['file']}").status_code == 200
    # a origem da cadeia (situação escolhida) existe → a UI monta o antes→depois
    sit = [c for c in cands if c["kind"] == "situation" and c["selected"]]
    assert sit and client.get(f"/files/{pid}/{sit[0]['file']}").status_code == 200


def test_select_over_http(client, pid):
    client.post(f"/api/projects/{pid}/base/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))], data={"kind": "situation"})
    cid = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"][0]["id"]
    r = client.post(f"/api/projects/{pid}/base/select", json={"id": cid, "note": "essa"})
    assert r.status_code == 200 and r.json()["final"] == "base/base_final.png"
    assert client.get(f"/api/projects/{pid}/base/candidates").json()["final"] == "base/base_final.png"
    assert client.get(f"/files/{pid}/base/base_final.png").status_code == 200
    assert client.post(f"/api/projects/{pid}/base/select", json={"id": "naoexiste"}).status_code == 404
    assert client.post(f"/api/projects/{pid}/base/select", json={}).status_code == 422



# ---------- `[extensão]` presets de realismo no body de generate (FDD prompter-presets §5) ----------
def _fake_claude(monkeypatch, sent: list[str]) -> list[str]:
    """Claude fakeado no padrão do repo: guarda o prompt enviado (`args[2]`) e devolve JSON fixo."""
    import json as _json
    import subprocess

    from studio.common import prompter

    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")

    def fake_run(args, capture_output, text, timeout):
        sent.append(args[2])
        payload = {"prompt": _FIVE_LINE_PROMPT, "negative": "blur", "camera": "", "notes_pt": ""}
        return subprocess.CompletedProcess(args, 0, "```json\n" + _json.dumps(payload) + "\n```", "")

    monkeypatch.setattr(prompter.subprocess, "run", fake_run)
    return sent


#: Nomes de corpo de câmera do catálogo — nenhum deles pode vazar para um prompt sem preset.
_RIGS = ("Blackmagic Pocket 6K Pro", "ARRI Alexa Mini LF", "RED V-Raptor", "Sony Venice 2")


def test_generate_without_preset_is_byte_identical_to_before(client, pid, monkeypatch):
    """T3.1 — o body de hoje (sem `preset`), com o opt-in de fábrica, não muda nada: mesmas chaves
    (só `preset` a mais, em `None`) e nenhum rig do catálogo no texto que vai para o CLI."""
    sent = _fake_claude(monkeypatch, [])
    r = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "images"})
    assert r.status_code == 200 and r.json()["preset"] is None
    assert set(r.json()) == {"ref_id", "ref_file", "mode", "instruction", "no_bias", "no_people", "model",
                             "board", "aspect_ratio", "created", "prompt", "negative", "camera", "notes_pt",
                             "source", "seconds", "images", "provenance", "mood_refs", "palette", "preset"}
    assert not any(rig in sent[0] for rig in _RIGS), "sem preset o prompt do CLI é o de antes da extensão"
    assert "REALISM PRESET" not in sent[0]


def test_generate_with_explicit_preset_reaches_the_cli(client, pid, monkeypatch):
    """T3.2 — preset explícito no body vira bloco de realismo no prompt enviado ao Claude."""
    sent = _fake_claude(monkeypatch, [])
    r = client.post(f"/api/projects/{pid}/base/prompts/generate",
                    json={"mode": "images", "preset": "arri-natural-narrative"})
    assert r.status_code == 200 and r.json()["preset"] == "arri-natural-narrative"
    assert "ARRI Alexa Mini LF" in sent[0] and "REALISM PRESET" in sent[0]


def test_generate_null_preset_turns_off_a_configured_default(client, pid, studio_env, monkeypatch):
    """T3.3 — a distinção AUSENTE × `null`: com override global gravado, o campo ausente resolve o
    default e o `null` explícito desliga o preset (a rota de fuga do usuário)."""
    from studio.common import settings
    settings.set_global_preset("base", "documentary-street")

    sent = _fake_claude(monkeypatch, [])
    off = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "images", "preset": None})
    assert off.status_code == 200 and off.json()["preset"] is None
    assert not any(rig in sent[0] for rig in _RIGS)

    on = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "images"})
    assert on.status_code == 200 and on.json()["preset"] == "documentary-street"
    assert "Blackmagic Pocket 6K Pro" in sent[1]


def test_generate_unknown_preset_is_422_before_the_cli(client, pid, monkeypatch):
    """T3.4 — id fora do catálogo é 422 com os ids válidos na mensagem, e o CLI não é chamado."""
    sent = _fake_claude(monkeypatch, [])
    r = client.post(f"/api/projects/{pid}/base/prompts/generate",
                    json={"mode": "images", "preset": "nao-existe"})
    assert r.status_code == 422
    assert "documentary-street" in json.dumps(r.json(), ensure_ascii=False)
    assert sent == [], "a validação acontece antes de qualquer chamada ao Claude CLI"


def test_generate_history_keeps_the_preset_and_the_existing_fields(client, pid, monkeypatch):
    """T3.5 — `base/prompts.json` grava o preset sem perder provenance/mood_refs/palette."""
    _fake_claude(monkeypatch, [])
    r = client.post(f"/api/projects/{pid}/base/prompts/generate",
                    json={"mode": "images", "preset": "red-commercial-precision"})
    assert r.status_code == 200
    entry = client.get(f"/api/projects/{pid}/base/prompts/history").json()[0]
    assert entry["preset"] == "red-commercial-precision"
    assert entry["provenance"]["parts"] and entry["mood_refs"] and entry["palette"]["colors"]


def test_generate_error_matrix_survives_the_preset_field(client, pid, monkeypatch):
    """T3.6 — a matriz 409/200/422/502 da etapa 3 continua idêntica com `preset` no body."""
    from studio.common import prompter
    monkeypatch.setattr(prompter, "BIN", None)
    body = {"mode": "images", "preset": "documentary-street"}
    r = client.post(f"/api/projects/{pid}/base/prompts/generate", json=body)
    assert r.status_code == 409 and "indisponível" in r.json()["detail"]
    assert client.post(f"/api/projects/{pid}/base/prompts/generate",
                       json={**body, "mode": "template"}).status_code == 200
    assert client.post(f"/api/projects/{pid}/base/prompts/generate",
                       json={**body, "mode": "magico"}).status_code == 422

    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert client.post(f"/api/projects/{pid}/base/prompts/generate",
                       json={**body, "mode": "brief"}).status_code == 502


def test_template_only_obeys_an_explicit_preset(client, pid):
    """T3.7 — determinismo do fallback (FDD §4): o preset ESCOLHIDO preenche a linha `Camera:`;
    o preset apenas resolvido por default deixa o template byte-idêntico ao do curso."""
    from studio.common import settings

    antes = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "template"})
    assert antes.status_code == 200 and antes.json()["preset"] is None

    r = client.post(f"/api/projects/{pid}/base/prompts/generate",
                    json={"mode": "template", "preset": "red-commercial-precision"})
    assert r.status_code == 200 and r.json()["preset"] == "red-commercial-precision"
    assert "Camera: RED V-Raptor" in r.json()["prompt"]

    settings.set_global_preset("base", "documentary-street")
    depois = client.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "template"})
    assert depois.status_code == 200 and depois.json()["preset"] == "documentary-street"
    assert depois.json()["prompt"] == antes.json()["prompt"], "default resolvido não mexe no template"
    assert not any(rig in depois.json()["prompt"] for rig in _RIGS)
# ---------- kind "clean": limpeza de marca `[extensão]` (wave 9) ----------
def _bridge(hf, monkeypatch, credits=2):
    """Ponte falsificada disponível e logada — o 409 do router vem antes do 422 do serviço."""
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": credits, "model": model, "raw": {}})


def _run_job(client, pid):
    import threading
    for _ in range(100):
        if client.get(f"/api/projects/{pid}/base/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    return client.get(f"/api/projects/{pid}/base/job").json()


def test_clean_cost_accepts_the_new_kind(client, pid, hf, monkeypatch):
    """FDD §5 contrato 1: `kind:"clean"` passa pelo `Literal` e cobra as 3 variações do passo."""
    _seed_situation(client, pid)
    _bridge(hf, monkeypatch)
    r = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "clean", "target": "Red Bull"})
    assert r.status_code == 200
    body = r.json()
    assert body["per_item"] == 2 and body["count"] == 3 and body["total"] == 6


def test_clean_generate_accepts_the_new_kind_and_target(client, pid, hf, monkeypatch):
    """FDD §5 contrato 2: o `target` do corpo chega ao prompt enviado ao CLI."""
    _seed_situation(client, pid)
    _bridge(hf, monkeypatch)
    calls = []

    def fake_generate(model, params):
        calls.append(params)
        return {"urls": ["https://cdn.higgsfield/x/out.png"], "id": "job1", "raw": {}}

    monkeypatch.setattr(hf, "generate", fake_generate)
    monkeypatch.setattr(hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                           dest.write_bytes(image_bytes(color=(7, 8, 9))), dest)[-1])
    r = client.post(f"/api/projects/{pid}/base/generate", json={"kind": "clean", "target": "Red Bull"})
    assert r.status_code == 200
    # schema atual do JobRegistry (o FDD §5 remete a ele): estado + total + extras do passo
    assert r.json()["state"] == "running" and r.json()["kind"] == "clean" and r.json()["total"] == 3
    assert _run_job(client, pid)["state"] == "done"
    assert calls and all('"Red Bull"' in p["prompt"] for p in calls)
    cands = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
    assert [c for c in cands if c["kind"] == "clean"], "a geração paga entrou como candidata do passo"


def test_clean_unknown_kind_is_rejected_by_the_literal(client, pid, hf, monkeypatch):
    """FDD §6: kind fora dos quatro valores é 422 do Pydantic, antes de chegar ao serviço."""
    _bridge(hf, monkeypatch)
    assert client.post(f"/api/projects/{pid}/base/cost", json={"kind": "nope"}).status_code == 422
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "nope"}).status_code == 422


def test_clean_cost_without_selected_situation_is_422(client, pid, hf, monkeypatch):
    """FDD §6/§9 critério 9: sem situação escolhida, a limpeza usa a mensagem existente do rótulo."""
    _bridge(hf, monkeypatch)
    r = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "clean"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Escolha primeiro a melhor imagem de situação (aula 009)."


def test_clean_imports_accept_the_new_kind(client, pid, studio_env):
    """FDD §5 contrato 3: o caminho sem custo (modo UI ilimitado) classifica candidatas `clean`."""
    make_image(studio_env["tmp"] / "downloads" / "limpa.jpg")
    r = client.post(f"/api/projects/{pid}/base/import/downloads", json={"since_minutes": 60, "kind": "clean"})
    assert r.status_code == 200 and r.json()["added"] == 1
    r = client.post(f"/api/projects/{pid}/base/import/upload",
                    files=[("files", ("c.png", image_bytes(color=(40, 200, 40)), "image/png"))],
                    data={"kind": "clean"})
    assert r.status_code == 200 and r.json()["added"] == 1
    cands = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
    assert len([c for c in cands if c["kind"] == "clean"]) == 2
    assert client.post(f"/api/projects/{pid}/base/import/downloads",
                       json={"since_minutes": 60, "kind": "nope"}).status_code == 422


def test_clean_select_response_carries_the_clean_key(client, pid):
    """FDD §5 contrato 4: a chave `clean` entra no mapa `chain` da resposta de `select`."""
    _seed_situation(client, pid)
    client.post(f"/api/projects/{pid}/base/import/upload",
                files=[("files", ("c.png", image_bytes(color=(40, 200, 40)), "image/png"))],
                data={"kind": "clean"})
    cid = [c for c in client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
           if c["kind"] == "clean"][-1]["id"]
    r = client.post(f"/api/projects/{pid}/base/select", json={"id": cid})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "clean" and "clean" in body["chain"] and body["chain"]["clean"] == cid


# ---------- tela do passo "clean" (FDD §9 critério 11) ----------
def test_clean_prompts_endpoint_exposes_the_clean_template(client, pid):
    """O texto default do card vem do backend, no molde de `label_prompt`/`label_count`."""
    body = client.get(f"/api/projects/{pid}/base/prompts").json()
    assert "Remove all brand names" in body["clean_prompt"] and body["clean_count"] == 3
    # aditivo puro: nenhuma chave existente do payload mudou
    assert body["label_count"] == 3 and body["label_ready"] is False
    assert body["model"] == "nano_banana_2" and len(body["refs"]) == 2


def test_clean_guide_text_mentions_the_optional_step(client, pid):
    """FDD §9 critério 11: o guia da etapa cita o passo opcional, marcado `[extensão]`."""
    g = client.get(f"/api/projects/{pid}/guide/base").json()
    texto = g["what"] + " " + " ".join(g["checklist"])
    assert "limpar marca" in texto or "limpei a marca" in texto.lower()
    assert "[extensão]" in texto and "inpaint" in g["what"]


# ---------- `new_candidates` no status do job `[extensão]` (F11, FDD §5 contrato 1) ----------
def _fake_cli_urls(hf, monkeypatch, n=1):
    """CLI falsificado que devolve `n` URLs por chamada e baixa uma imagem DIFERENTE por URL
    (cores distintas: sem colisão de sha12, o dedupe do `ingest` não come nada)."""
    monkeypatch.setattr(hf, "generate",
                        lambda model, params: {"urls": [f"https://cdn.higgsfield/x/o{i}.png" for i in range(n)],
                                               "id": "job1", "raw": {}})
    seq = {"i": 0}

    def fake_download(url, dest):
        seq["i"] += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes(color=(7 * seq["i"], 8 * seq["i"], 9 * seq["i"])))
        return dest

    monkeypatch.setattr(hf, "download", fake_download)


def test_job_reports_the_upscale_it_produced(client, pid, hf, monkeypatch):
    """FDD §9 critério 1: depois de um upscale concluído, `GET /base/job` diz O QUE produziu —
    uma entrada por candidata ingerida, com URLs servíveis e a origem da cadeia."""
    _seed_situation(client, pid)
    client.post(f"/api/projects/{pid}/base/brand-image", files={"file": ("marca.png", image_bytes(), "image/png")})
    _bridge(hf, monkeypatch)
    _fake_cli_urls(hf, monkeypatch)
    # a origem do upscale é o rótulo escolhido (a candidata mais avançada da cadeia)
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "label"}).status_code == 200
    assert _run_job(client, pid)["state"] == "done"
    lab = [c for c in client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
           if c["kind"] == "label"][0]
    client.post(f"/api/projects/{pid}/base/select", json={"id": lab["id"]})

    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "upscale"}).status_code == 200
    job = _run_job(client, pid)
    assert job["state"] == "done" and job["added"] == 1
    novas = job["new_candidates"]
    assert len(novas) == 1 == job["added"], "o invariante len(new_candidates) == added (FDD §6)"
    nova = novas[0]
    ids = {c["id"] for c in client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]}
    assert nova["id"] in ids and nova["kind"] == "upscale"
    assert nova["file_url"].startswith(f"/files/{pid}/base/candidates/")
    assert "/base/candidates/thumbs/" in nova["thumb_url"]
    assert nova["source_id"] == lab["id"], "a origem é o rótulo selecionado"
    # as URLs são de fato servíveis (é o que o chat vai mostrar)
    assert client.get(nova["file_url"]).status_code == 200
    assert client.get(nova["thumb_url"]).status_code == 200


def test_job_lists_every_new_candidate_in_ingestion_order(client, pid, hf, monkeypatch):
    """FDD §9 critério 1 com N itens: um job de limpeza com 2 variações devolve 2 entradas, na
    ordem de ingestão, e `len(new_candidates)` continua igual a `added`."""
    _seed_situation(client, pid)
    _bridge(hf, monkeypatch)
    _fake_cli_urls(hf, monkeypatch)
    r = client.post(f"/api/projects/{pid}/base/generate", json={"kind": "clean", "count": 2, "target": "Red Bull"})
    assert r.status_code == 200
    job = _run_job(client, pid)
    assert job["state"] == "done" and job["added"] == 2
    novas = job["new_candidates"]
    assert len(novas) == job["added"] == 2
    assert all(c["kind"] == "clean" for c in novas)
    ordem = [c["id"] for c in client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"]
             if c["kind"] == "clean"]
    assert [c["id"] for c in novas] == ordem, "ordem de ingestão preservada"


def test_job_without_job_is_idle_with_an_empty_list(client, pid):
    """FDD §9 critério 2: sem job, a rota devolve exatamente o exemplo do contrato 1."""
    assert client.get(f"/api/projects/{pid}/base/job").json() == {"state": "idle", "new_candidates": []}


def test_job_keeps_every_current_key_and_the_404(client, pid, hf, monkeypatch):
    """FDD §9 critério 2: o enriquecimento é ADITIVO — nenhuma chave atual do job desaparece,
    e `pid` inexistente continua 404."""
    _seed_situation(client, pid)
    _bridge(hf, monkeypatch)
    _fake_cli_urls(hf, monkeypatch)
    client.post(f"/api/projects/{pid}/base/generate", json={"kind": "clean", "target": "Red Bull"})
    job = _run_job(client, pid)
    for k in ("state", "done", "total", "added", "error", "log", "kind", "model"):
        assert k in job, f"chave atual sumiu do status do job: {k}"
    assert "new_ids" not in job, "escrituração interna não vaza para o payload"
    assert client.get("/api/projects/naoexiste/base/job").status_code == 404


def test_job_enrichment_does_not_mutate_the_registry(client, pid, hf, monkeypatch, studio_env):
    """FDD §5: `JobRegistry.status` devolve a referência VIVA do job — o enriquecimento tem de
    trabalhar numa cópia, senão `new_candidates` vazaria e cresceria a cada polling."""
    _seed_situation(client, pid)
    _bridge(hf, monkeypatch)
    _fake_cli_urls(hf, monkeypatch)
    client.post(f"/api/projects/{pid}/base/generate", json={"kind": "clean", "count": 1, "target": "Red Bull"})
    um = _run_job(client, pid)
    dois = client.get(f"/api/projects/{pid}/base/job").json()
    assert um["new_candidates"] == dois["new_candidates"] and len(dois["new_candidates"]) == 1
    vivo = studio_env["svc"]("base")._registry.status(pid)
    assert "new_candidates" not in vivo, "o dict interno do registry ficou intacto"


def test_job_with_a_failed_download_reports_only_what_was_ingested(client, pid, hf, monkeypatch):
    """FDD §6: job cuja segunda URL falha no download não levanta — `new_candidates` traz só o
    que chegou, e o invariante com `added` continua de pé."""
    _seed_situation(client, pid)
    _bridge(hf, monkeypatch)
    monkeypatch.setattr(hf, "generate",
                        lambda model, params: {"urls": ["https://cdn.higgsfield/x/ok.png",
                                                        "https://cdn.higgsfield/x/expirada.png"],
                                               "id": "job1", "raw": {}})

    def fake_download(url, dest):
        if "expirada" in url:
            raise RuntimeError("link expirado")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes(color=(7, 8, 9)))
        return dest

    monkeypatch.setattr(hf, "download", fake_download)
    client.post(f"/api/projects/{pid}/base/generate", json={"kind": "clean", "count": 1, "target": "Red Bull"})
    job = _run_job(client, pid)
    assert job["state"] == "done" and job["added"] == 1
    assert len(job["new_candidates"]) == job["added"] == 1
    assert any("download pulado" in linha for linha in job["log"])
