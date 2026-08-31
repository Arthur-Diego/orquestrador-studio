"""Etapa 4 — o storyboard segue a aula 010: uma instrução por vez, 4/1 gerações, ~5 cenas em texto."""
import json
import threading
from pathlib import Path

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def project(studio_env):
    meta = studio_env["refs"].create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


@pytest.fixture()
def sb(studio_env):
    return studio_env["svc"]("storyboard")


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


@pytest.fixture()
def base(root):
    """Handoff da etapa 3 (OS-003, em voo na mesma wave): fixture no lugar da base real."""
    return make_image(root / "base" / "base_final.png")


# ---------- instruções (aula 010) ----------
def test_instruction_keeps_course_formula_and_suffix(sb, project, base):
    r = sb.build_instruction(project, "edit", "Make the climber even smaller and more realistic", 4)
    assert r["instruction"] == "Make the climber even smaller and more realistic. Keep everything else identical, realistic."
    assert r["count"] == 4 and r["base_image"] == "base/base_final.png"
    assert "4 variações" in r["ui_hint"], "aula 010: 4 gerações quando está incerto"
    assert sb.build_instruction(project, "draw_to_edit", "the climber climbs the can", 1)["instruction"].startswith("Follow the sketch:")
    ms = sb.build_instruction(project, "multishot", "a close-up on the character", 1)["instruction"]
    assert ms.startswith("Another point of view of this exact scene:") and "1 variação" in \
        sb.build_instruction(project, "multishot", "a close-up on the character", 1)["ui_hint"]


def test_instruction_refuses_more_than_one_edit(sb, project, base):
    with pytest.raises(sb.Invalid) as e:
        sb.build_instruction(project, "edit", "1. Make it smaller 2. Remove the rope", 4)
    assert "uma instrução por vez" in str(e.value).lower()
    assert "Make it smaller" in str(e.value), "a mensagem sugere a primeira instrução"
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "edit", "Make it smaller. Remove the rope.", 4)


def test_instruction_count_is_four_or_one(sb, project, base):
    for bad in (0, 2, 3, 10):
        with pytest.raises(sb.Invalid):
            sb.build_instruction(project, "edit", "Make it smaller", bad)


def test_instruction_validates_kind_and_text(sb, project, base):
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "inpaint", "Make it smaller", 4)
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "edit", "   ", 4)
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "edit", "x" * 301, 4)


def test_instruction_requires_base_image_from_step_three(sb, project):
    with pytest.raises(sb.Precondition):
        sb.build_instruction(project, "edit", "Make it smaller", 4)
    assert sb.status(project)["has_base"] is False


def test_every_published_preset_is_accepted_by_the_validator(sb, project, base):
    """Contrato 2 x contrato 3: a fórmula que a etapa publica não pode ser recusada por ela mesma.
    O preset de inpaint da aula usa ponto-e-vírgula ligando contexto e pedido — é UMA instrução."""
    for preset in sb.presets()["presets"]:
        r = sb.build_instruction(project, preset["kind"], preset["text"], 4)
        assert r["instruction"], preset["label"]


def test_semicolon_joins_one_instruction_but_period_separates(sb, project, base):
    ok = "There is a rope hanging from the top of the can; make it thinner and realistic"
    assert sb.build_instruction(project, "edit", ok, 1)["instruction"].startswith("There is a rope")
    for two in ("Make it smaller. Remove the rope.", "Make it smaller. Remove the rope"):
        with pytest.raises(sb.Invalid):
            sb.build_instruction(project, "edit", two, 1)


def test_presets_are_in_english_with_ptbr_labels(sb):
    p = sb.presets()
    assert p["counts"] == {"uncertain": 4, "tweak": 1}
    # `[extensão]` inpaint-marcacao: o kind `edit_area` entra ADITIVO ao lado dos três da aula.
    assert {k["kind"] for k in p["kinds"]} == {"draw_to_edit", "edit", "multishot", "edit_area"}
    assert any(x["text"] == "a close-up on the character" for x in p["presets"])


# ---------- cenas ----------
def test_scenes_default_to_five_empty_scenes(sb, project, root):
    scenes = sb.load_scenes(project)["scenes"]
    assert [s["id"] for s in scenes] == [f"cena{i:02d}" for i in range(1, 6)]
    # [extensão] cena-multi-keyframe (ADR-018): cada cena vira {id,n,text,images,primary}.
    assert all(s["text"] == "" and s["images"] == [] and s["primary"] is None for s in scenes)
    assert [s["n"] for s in scenes] == [1, 2, 3, 4, 5]
    on_disk = json.loads((root / "storyboard" / "scenes.json").read_text())
    assert on_disk == {"scenes": scenes}, "schema cena-multi-keyframe, persistido na primeira leitura"


def test_save_scenes_renumbers_by_order_and_writes_md(sb, project, root):
    r = sb.save_scenes(project, [{"text": "Close no astronauta"},
                                 {"text": "Ele encontra a lata gigante"},
                                 {"text": "A lata cai"}])
    assert [s["id"] for s in r["scenes"]] == ["cena01", "cena02", "cena03"]
    assert r["storyboard_md"] == "storyboard/storyboard.md"
    md = (root / "storyboard" / "storyboard.md").read_text()
    assert "# Storyboard: Gelo Zero" in md and "## Cena 1" in md and "Close no astronauta" in md
    reordered = sb.save_scenes(project, [{"text": "A lata cai"}, {"text": "Close no astronauta"}])["scenes"]
    # `[extensão]` wave 7 (ADR-021): campos aditivos de vídeo (retrocompat) no schema da cena.
    assert reordered[0] == {"id": "cena01", "n": 1, "text": "A lata cai", "images": [], "primary": None,
                            "video_desc": "", "video_prompt": "", "videos": [], "photos": {}}


def test_save_scenes_limits_and_image_must_live_in_ideas(sb, project, base):
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [])
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [{"text": f"c{i}"} for i in range(11)])
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [{"text": "x" * 501}])
    for bad in ("../base/base_final.png", "storyboard/ideas/../../base/base_final.png",
                "storyboard/ideas/nao-existe.png", "storyboard/candidates/x.png"):
        with pytest.raises(sb.Invalid):
            sb.save_scenes(project, [{"text": "c", "image": bad}])


def test_corrupted_scenes_json_falls_back_to_default(sb, project, root):
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text("{quebrado")
    assert len(sb.load_scenes(project)["scenes"]) == 5


def test_render_requires_at_least_one_written_scene(sb, project):
    with pytest.raises(sb.Invalid):
        sb.render(project)
    sb.save_scenes(project, [{"text": "Close no astronauta"}])
    assert sb.render(project)["storyboard_md"] == "storyboard/storyboard.md"


# ---------- cena-multi-keyframe (ADR-018, [extensão]) ----------
def _two_ideas(sb, project):
    """Duas ideias selecionadas em storyboard/ideas/ — devolve (fileA, fileB)."""
    sb.import_upload(project, [("a.png", image_bytes(color=(1, 2, 3))), ("b.png", image_bytes(color=(9, 9, 9)))])
    ids = [i["id"] for i in sb.list_ideas(project)["ideas"]]
    sb.select_ideas(project, ids)
    return tuple(i["file"] for i in sb.list_ideas(project)["ideas"])


def test_legacy_scenes_json_migrates_image_to_images_and_primary(sb, project, root):
    """Migração retrocompatível: um scenes.json antigo (`image` singular) é lido no schema novo."""
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": [
        {"id": "cena01", "n": 1, "text": "close", "image": "storyboard/ideas/a.png"},
        {"id": "cena02", "n": 2, "text": "aberta", "image": None},
    ]}))
    scenes = sb.load_scenes(project)["scenes"]
    assert scenes[0]["images"] == ["storyboard/ideas/a.png"] and scenes[0]["primary"] == "storyboard/ideas/a.png"
    assert scenes[1]["images"] == [] and scenes[1]["primary"] is None
    assert "image" not in scenes[0], "o formato novo não carrega mais o campo antigo"


def test_save_scenes_persists_multiple_images_with_default_primary(sb, project):
    a, b = _two_ideas(sb, project)
    r = sb.save_scenes(project, [{"text": "cena com galeria", "images": [a, b]}])
    s = r["scenes"][0]
    assert s["images"] == [a, b] and s["primary"] == a, "default: a 1ª imagem vira principal"
    # persistiu: relê do disco no schema novo
    assert sb.load_scenes(project)["scenes"][0] == s


def test_save_scenes_honors_explicit_primary_and_dedupes(sb, project):
    a, b = _two_ideas(sb, project)
    s = sb.save_scenes(project, [{"text": "c", "images": [a, b, a], "primary": b}])["scenes"][0]
    assert s["images"] == [a, b], "itens repetidos são deduplicados preservando a ordem"
    assert s["primary"] == b, "a principal explícita é respeitada"


def test_save_scenes_recomputes_primary_when_it_is_not_in_images(sb, project):
    a, b = _two_ideas(sb, project)
    s = sb.save_scenes(project, [{"text": "c", "images": [a, b], "primary": "storyboard/ideas/fora.png"}])["scenes"][0]
    assert s["primary"] == a, "principal fora da galeria volta para o primeiro item válido"


def test_save_scenes_validates_each_image_of_the_gallery(sb, project):
    a, _ = _two_ideas(sb, project)
    for bad in ("storyboard/ideas/nao-existe.png", "storyboard/candidates/x.png",
                "storyboard/ideas/../../base/base_final.png"):
        with pytest.raises(sb.Invalid):
            sb.save_scenes(project, [{"text": "c", "images": [a, bad]}])


def test_detach_removes_from_gallery_and_promotes_next_primary(sb, project):
    """select() detach: se a principal cai, promove o próximo item da cena (ADR-018)."""
    a, b = _two_ideas(sb, project)
    ids = [i["id"] for i in sb.list_ideas(project)["ideas"]]
    id_a = next(i["id"] for i in sb.list_ideas(project)["ideas"] if i["file"] == a)
    sb.save_scenes(project, [{"text": "c", "images": [a, b], "primary": a}])
    # desmarca a ideia que era a principal: sai da galeria e a próxima é promovida
    out = sb.select_ideas(project, [i for i in ids if i != id_a])
    assert out["detached"] == ["cena01"]
    cena01 = sb.load_scenes(project)["scenes"][0]
    assert cena01["images"] == [b] and cena01["primary"] == b


def test_storyboard_md_shows_primary_as_hero_and_the_rest_as_alternatives(sb, project, root):
    a, b = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena galeria", "images": [a, b], "primary": a}])
    md = (root / "storyboard" / "storyboard.md").read_text()
    assert f"![cena01](ideas/{Path(a).name})" in md, "a principal é o hero da cena"
    assert "Alternativas:" in md and f"![cena01 alternativa 1](ideas/{Path(b).name})" in md


# ---------- ideias ----------
def test_upload_reports_skipped_and_dedupes(sb, project, root):
    data = image_bytes()
    assert sb.import_upload(project, [("a.png", data), ("nota.txt", b"nao e imagem")]) == {"added": 1, "skipped": 1}
    assert sb.import_upload(project, [("a.png", data)]) == {"added": 0, "skipped": 1}
    assert (root / "storyboard" / "candidates").exists()
    assert list((root / "storyboard" / "candidates" / "thumbs").glob("*.jpg"))


def test_downloads_import_records_the_prompt_used(sb, project, studio_env):
    make_image(studio_env["tmp"] / "downloads" / "idea.png")
    r = sb.import_downloads(project, since_minutes=60, prompt="Make it smaller. Keep everything else identical, realistic.")
    assert r["added"] == 1
    idea = sb.list_ideas(project)["ideas"][0]
    assert idea["prompt"].startswith("Make it smaller") and idea["source"] == "downloads"


def test_downloads_import_rejects_unknown_folder(sb, project, studio_env):
    with pytest.raises(sb.Invalid):
        sb.import_downloads(project, folder=str(studio_env["tmp"] / "nao-existe"))


def test_select_copies_to_ideas_and_detaches_scene_on_deselect(sb, project, root):
    sb.import_upload(project, [("a.png", image_bytes(color=(1, 2, 3))), ("b.png", image_bytes(color=(9, 9, 9)))])
    a, b = [i["id"] for i in sb.list_ideas(project)["ideas"]]
    r = sb.select_ideas(project, [a, b])
    assert r == {"selected": 2, "detached": []}
    ideas_dir = root / "storyboard" / "ideas"
    assert len([p for p in ideas_dir.iterdir() if p.name != "ideas.json"]) == 2
    rows = json.loads((ideas_dir / "ideas.json").read_text())
    assert all(set(row) == {"id", "file", "thumb", "prompt", "selected"} for row in rows)
    assert all(row["file"].startswith("storyboard/ideas/") for row in rows)

    img = next(i["file"] for i in sb.list_ideas(project)["ideas"] if i["id"] == a)
    sb.save_scenes(project, [{"text": "Close no astronauta", "images": [img], "primary": img}, {"text": "A lata cai"}])
    out = sb.select_ideas(project, [b])
    assert out == {"selected": 1, "detached": ["cena01"]}
    cena01 = sb.load_scenes(project)["scenes"][0]
    assert cena01["images"] == [] and cena01["primary"] is None
    assert len([p for p in ideas_dir.iterdir() if p.name != "ideas.json"]) == 1, "ideias/ guarda só as selecionadas (decisão 7)"


def test_select_rejects_unknown_id(sb, project):
    with pytest.raises(sb.Invalid):
        sb.select_ideas(project, ["nao-existe"])


def test_status_counts_ideas_scenes_and_base(sb, project, root, base):
    sb.import_upload(project, [("a.png", image_bytes())])
    sb.select_ideas(project, [sb.list_ideas(project)["ideas"][0]["id"]])
    sb.save_scenes(project, [{"text": "Close no astronauta"}, {"text": ""}])
    st = sb.status(project)
    assert st == {"base_image": "base/base_final.png", "has_base": True, "ideas": 1, "selected": 1,
                  "scenes": 2, "scenes_with_text": 1, "storyboard_md": "storyboard/storyboard.md",
                  # `[extensão]` vídeo por foto (ADR-022): seletor de modelo do modal "Gerar animação".
                  "video_models": sb._video_model_ids(),
                  "video_model_defaults": {"single": sb.video_model(project, "single"),
                                           "start_end": sb.video_model(project, "start_end")},
                  # `[extensão]` roteiro por LLM (ADR-025): campos aditivos da wave 9 (FDD §5.4).
                  "script": {"exists": False, "generated_at": None},
                  "script_preset_default": "documentary-street",
                  "script_models": [dict(m) for m in sb.SCRIPT_MODELS],
                  "script_cli": sb.prompter.available()}


# ---------- alternativa paga pelo CLI ----------
def _fake_cli(monkeypatch, sb, urls=("http://x/a.png", "http://x/b.png"), gate=None):
    monkeypatch.setattr(sb.hf, "available", lambda: True)
    monkeypatch.setattr(sb.hf, "status", lambda: {"installed": True, "logged_in": True, "credits": 100})
    colors = iter([(10, 20, 30), (40, 50, 60), (70, 80, 90), (100, 110, 120)])

    def fake_generate(model, params, timeout_s=600):
        if gate is not None:
            gate.wait(5)
        return {"raw": {"model": model, "params": params}, "urls": list(urls), "id": "job1"}

    def fake_download(url, dest):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes(color=next(colors)))
        return dest

    monkeypatch.setattr(sb.hf, "generate", fake_generate)
    monkeypatch.setattr(sb.hf, "download", fake_download)


def _wait_job(sb, project, tries=100):
    for _ in range(tries):
        if sb.job_status(project)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return sb.job_status(project)


def test_cli_generate_imports_results_as_candidates(sb, project, base, monkeypatch, root):
    _fake_cli(monkeypatch, sb)
    sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    job = _wait_job(sb, project)
    assert job["state"] == "done" and job["added"] == 2 and job["done"] == 1
    ideas = sb.list_ideas(project)["ideas"]
    assert len(ideas) == 2 and all(i["source"] == "cli" for i in ideas)
    assert all(i["prompt"] == "Make it smaller. Keep everything else identical, realistic." for i in ideas)
    assert list((root / "jobs").glob("storyboard_*.json"))


def test_cli_generate_refuses_concurrent_job(sb, project, base, monkeypatch):
    gate = threading.Event()
    _fake_cli(monkeypatch, sb, gate=gate)
    sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    with pytest.raises(sb.Precondition):
        sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    gate.set()
    assert _wait_job(sb, project)["state"] == "done"


def test_cli_has_no_draw_to_edit(sb, project, base, monkeypatch):
    _fake_cli(monkeypatch, sb)
    with pytest.raises(sb.Invalid):
        sb.start_generate(project, "nano_banana_2", "draw_to_edit", "the climber climbs", 1)


def test_cli_requires_login_and_reports_cost(sb, project, base, monkeypatch):
    monkeypatch.setattr(sb.hf, "available", lambda: False)
    with pytest.raises(sb.Precondition):
        sb.cost(project, "nano_banana_2", "edit", "Make it smaller", 4)
    _fake_cli(monkeypatch, sb)
    monkeypatch.setattr(sb.hf, "cost", lambda model, params: {"credits": 3})
    assert sb.cost(project, "nano_banana_2", "edit", "Make it smaller", 4) == {"per_image": 3, "total": 12}
    monkeypatch.setattr(sb.hf, "cost", lambda model, params: {"credits": None, "error": "x"})
    assert sb.cost(project, "nano_banana_2", "edit", "Make it smaller", 1) == {"per_image": None, "total": None}


# ---------- wave 2: fidelidade à aula 010 (auditoria 4.1–4.6) ----------
def test_single_instruction_heuristic_accepts_one_request_split_in_two_sentences(sb, project, base):
    """4.6: "uma instrução por vez" é sobre EDIÇÕES, não sobre pontuação. Uma frase de reforço
    ("Realistic.") não transforma o pedido em dois."""
    for uma in ("Make him smaller. Realistic.", "Remove the rope. Nothing else changes.",
                "Make the climber even smaller and more realistic. Same lighting."):
        assert sb.build_instruction(project, "edit", uma, 1)["instruction"], uma
    for duas in ("Make it smaller. Remove the rope.", "Remove the rope. Add a shadow."):
        with pytest.raises(sb.Invalid):
            sb.build_instruction(project, "edit", duas, 1)


def test_refusal_explains_that_the_rule_is_a_heuristic(sb, project, base):
    """4.6: o erro precisa dizer que é heurística — senão o usuário acha que é regra do produto."""
    with pytest.raises(sb.Invalid) as e:
        sb.build_instruction(project, "edit", "Make it smaller. Remove the rope.", 4)
    msg = str(e.value)
    assert "heurística" in msg.lower() and "uma instrução por vez" in msg.lower()
    assert "Make it smaller" in msg


def test_presets_publish_models_arc_and_the_upscale_note(sb):
    """4.1, 4.4 e 4.5: o modelo extra vem marcado, a estrutura da história e o aviso do upscale
    saem do backend (a tela não inventa texto de aula)."""
    p = sb.presets()
    models = {m["id"]: m for m in p["models"]}
    assert models["nano_banana_2"]["default"] is True
    assert models["gpt_image_2"]["default"] is False and "[extensão]" in models["gpt_image_2"]["label"]
    assert [a["label"] for a in p["arc"]] == ["começo", "descoberta", "ação", "desfecho"]
    assert "ângulos" in p["upscale_note"] and "aula 011" in p["upscale_note"]


def test_scene_arc_follows_the_lesson_structure(sb):
    """4.5: começo → descoberta → ação → desfecho, com a ação ocupando o miolo das ~5 cenas."""
    assert [sb.scene_arc(n, 5)["label"] for n in range(1, 6)] == \
        ["começo", "descoberta", "ação", "ação", "desfecho"]
    assert [sb.scene_arc(n, 3)["label"] for n in range(1, 4)] == ["começo", "descoberta", "desfecho"]
    assert sb.scene_arc(1, 1)["label"] == "começo"


def test_storyboard_md_carries_the_arc_and_the_upscale_note(sb, project, root, base):
    sb.save_scenes(project, [{"text": "abre na nevasca"}, {"text": "acha a lata"}, {"text": "bebe"}])
    md = (root / "storyboard" / "storyboard.md").read_text()
    assert "## Cena 1 — começo" in md and "## Cena 3 — desfecho" in md
    assert "ângulos" in md, "4.1: o documento diz onde o upscale acontece"


# ---------- `[extensão]` wave 7 (ADR-021): vídeo por cena ----------
def _fake_video_cli(monkeypatch, sb, url="https://cdn/out.mp4?sig=1", gate=None):
    """Fake do CLI da Higgsfield para VÍDEO: logado, hf.generate devolve uma URL .mp4, hf.download grava."""
    monkeypatch.setattr(sb.hf, "available", lambda: True)
    monkeypatch.setattr(sb.hf, "status", lambda: {"installed": True, "logged_in": True, "credits": 100})
    sent = {}

    def fake_generate(model, params, timeout_s=600):
        if gate is not None:
            gate.wait(5)
        sent.update({"model": model, "params": params, "timeout": timeout_s})
        return {"raw": {"id": "vid1"}, "urls": [url], "id": "vid1"}

    def fake_download(u, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        return dest

    monkeypatch.setattr(sb.hf, "generate", fake_generate)
    monkeypatch.setattr(sb.hf, "download", fake_download)
    return sent


def _wait_video(sb, project, scene, tries=100):
    for _ in range(tries):
        if sb.video_job_status(project, scene)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return sb.video_job_status(project, scene)


def test_video_prompt_falls_back_to_the_template_without_claude(sb, project, monkeypatch):
    monkeypatch.setattr(sb.prompter, "available", lambda: False)
    r = sb.video_prompt(project, "cena01", "an astronaut walking through a blizzard",
                        {"mode": "single"})
    assert r["source"] == "template" and r["seconds"] == 5
    assert r["prompt"].startswith("A photorealistic cinematic animation of an astronaut walking")
    assert "No text, no audio." in r["prompt"], "estrutura agnóstica do template"
    se = sb.video_prompt(project, "cena01", "the weather changes", {"mode": "start_end"})
    assert se["seconds"] == 10 and "start-frame/end-frame transition" in se["prompt"]


def test_video_prompt_uses_claude_when_available(sb, project, monkeypatch):
    monkeypatch.setattr(sb.prompter, "available", lambda: True)
    seen = {}

    def fake_brief(kind, brief):
        seen.update({"kind": kind, "brief": brief})
        return {"prompt": "Slow dolly-in on the astronaut, snow drifting, realistic.", "source": "claude", "seconds": 3.0}

    monkeypatch.setattr(sb.prompter, "from_brief", fake_brief)
    r = sb.video_prompt(project, "cena01", "an astronaut walking", {"mode": "single"})
    assert r["source"] == "claude" and r["prompt"].startswith("Slow dolly-in")
    assert r["seconds"] == 5, "seconds é a duração sugerida do clipe, não o tempo do bot"
    assert seen["kind"] == "motion" and "an astronaut walking" in seen["brief"]["instruction"]


def test_video_prompt_sends_scene_images_to_claude(sb, project, monkeypatch):
    a, b = _two_ideas(sb, project)
    monkeypatch.setattr(sb.prompter, "available", lambda: True)
    got = {}

    def fake_images(kind, images, instruction="", brief=None):
        got.update({"kind": kind, "images": [str(i) for i in images], "instruction": instruction})
        return {"prompt": "faithful motion prompt", "source": "claude", "seconds": 4.0}

    monkeypatch.setattr(sb.prompter, "from_images", fake_images)
    r = sb.video_prompt(project, "cena01", "the can falls", {"mode": "single", "image": a})
    assert r["source"] == "claude" and got["kind"] == "motion"
    assert len(got["images"]) == 1 and got["images"][0].endswith(Path(a).name)


def test_video_prompt_validates_description_and_scene(sb, project):
    with pytest.raises(sb.Invalid):
        sb.video_prompt(project, "cena01", "   ", {"mode": "single"})
    with pytest.raises(sb.Invalid):
        sb.video_prompt(project, "not-a-scene", "walk", {"mode": "single"})
    with pytest.raises(sb.Invalid):
        sb.video_prompt(project, "cena01", "walk", {"mode": "magic"})


def test_video_cost_resolves_model_by_mode(sb, project):
    single = sb.video_cost(project, "cena01", "single", 5)
    assert single == {"model": "kling2_6", "per_item": 10, "total": 10}
    trans = sb.video_cost(project, "cena01", "start_end", 10)
    assert trans == {"model": "kling3_0", "per_item": 20, "total": 20}, "ADR-023: transição = Kling 3.0"
    with pytest.raises(sb.Invalid):
        sb.video_cost(project, "cena01", "single", 7)


# ---------- `[extensão]` vídeo por FOTO (ADR-022) ----------
def test_video_cost_accepts_client_model_override(sb, project):
    """ADR-022: um `model` válido do cliente vence a resolução por servidor; inválido → Invalid."""
    r = sb.video_cost(project, "cena01", "single", 5, model="seedance_2_0")
    assert r["model"] == "seedance_2_0"
    with pytest.raises(sb.Invalid):
        sb.video_cost(project, "cena01", "single", 5, model="nano_banana_2")   # não é vídeo
    with pytest.raises(sb.Invalid):
        sb.video_cost(project, "cena01", "single", 5, model="inexistente")


def test_video_generate_per_photo_stores_under_the_owning_photo(sb, project, monkeypatch, root):
    """ADR-022: com `photo`, o mp4 é numerado por foto e gravado em `photos[foto]`, sem tocar o par
    por-cena; o `model` do cliente é respeitado."""
    a, b = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a, b], "primary": a}])
    sent = _fake_video_cli(monkeypatch, sb)
    sb.start_video_generate(project, "cena01", "dolly na foto A", "single", 5,
                            {"image": a}, photo=a, model="seedance_2_0")
    for _ in range(100):
        if sb.video_job_status(project, "cena01", photo=a)["state"] != "running":
            break
        threading.Event().wait(0.05)
    job = sb.video_job_status(project, "cena01", photo=a)
    stem = Path(a).stem
    rel = f"storyboard/cena01/video/{stem}_take_1.mp4"
    assert job["state"] == "done" and job["video"] == rel and (root / rel).exists()
    assert sent["model"] == "seedance_2_0"
    scene = sb.load_scenes(project)["scenes"][0]
    assert scene["photos"][a] == {"video_desc": "", "video_prompt": "dolly na foto A", "videos": [rel]}
    assert scene["photos"][b] == {"video_desc": "", "video_prompt": "", "videos": []}
    assert scene["videos"] == [], "vídeo por foto não polui o par por-cena (legado)"


def test_video_generate_two_photos_same_scene_run_isolated(sb, project, monkeypatch):
    """ADR-022: a chave do JobRegistry é por (cena, foto) — duas fotos da mesma cena não colidem."""
    a, b = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a, b], "primary": a}])
    gate = threading.Event()
    _fake_video_cli(monkeypatch, sb, gate=gate)
    sb.start_video_generate(project, "cena01", "p", "single", 5, {"image": a}, photo=a)
    with pytest.raises(sb.Precondition):                       # mesma foto em andamento → recusa
        sb.start_video_generate(project, "cena01", "p", "single", 5, {"image": a}, photo=a)
    assert sb.video_job_status(project, "cena01", photo=b)["state"] == "idle"   # outra foto não colide
    gate.set()
    for _ in range(100):
        if sb.video_job_status(project, "cena01", photo=a)["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert sb.video_job_status(project, "cena01", photo=a)["state"] == "done"


def test_scene_photos_migrates_legacy_per_scene_to_primary(sb, project, root):
    """ADR-022: cena antiga (par por-cena, sem `photos`) lê com o par migrado para a foto principal."""
    a, b = _two_ideas(sb, project)
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": [
        {"id": "cena01", "n": 1, "text": "t", "images": [a, b], "primary": a,
         "video_prompt": "prompt legado", "videos": ["storyboard/cena01/video/take_1.mp4"]}]}))
    scene = sb.load_scenes(project)["scenes"][0]
    assert scene["photos"][a] == {"video_desc": "", "video_prompt": "prompt legado",
                                  "videos": ["storyboard/cena01/video/take_1.mp4"]}
    assert scene["photos"][b] == {"video_desc": "", "video_prompt": "", "videos": []}


# ---------- ponte storyboard → montagem (`[extensão]` ADR-022, R2) ----------
def _gen_photo_video(sb, project, scene, img, prompt="dolly", photo=None):
    sb.start_video_generate(project, scene, prompt, "single", 5, {"image": img}, photo=photo or img)
    for _ in range(100):
        if sb.video_job_status(project, scene, photo=photo or img)["state"] != "running":
            break
        threading.Event().wait(0.05)


def test_photo_video_bridges_into_montage_as_liked_take(sb, project, root, monkeypatch):
    """ADR-022 (ponte R2): vídeo por FOTO → take **liked** em animate/takes.json → a montagem
    (edit.initial_timeline) monta um clipe com aquele vídeo, sem tocar a tela do animate."""
    from studio.animate import service as animate
    from studio.edit import service as edit
    a, _ = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a], "primary": a}])
    _fake_video_cli(monkeypatch, sb)
    _gen_photo_video(sb, project, "cena01", a)
    # 1) virou take liked em animate/takes.json, com o mp4 sob videos/
    shot = next(s for s in animate.stored_takes(project)["shots"] if s["scene"] == "cena01")
    assert len(shot["takes"]) == 1
    take = shot["takes"][0]
    assert take["liked"] is True and take["source"] == "storyboard"
    assert take["file"].startswith("videos/cena01/") and (root / take["file"]).exists()
    # 2) a montagem monta um clipe determinístico com aquele vídeo (storyboard.json foi criado aditivo)
    tl = edit.initial_timeline(project)
    assert any(c["file"] == take["file"] for c in tl["clips"])


def test_photo_reanimation_replaces_the_bridged_take(sb, project, monkeypatch):
    """ADR-022: reanimar a MESMA foto substitui o take (um like por shot), sem duplicar clipes."""
    from studio.animate import service as animate
    from studio.edit import service as edit
    a, _ = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a], "primary": a}])
    _fake_video_cli(monkeypatch, sb)
    _gen_photo_video(sb, project, "cena01", a, prompt="take um")
    _gen_photo_video(sb, project, "cena01", a, prompt="take dois")
    shot = next(s for s in animate.stored_takes(project)["shots"] if s["scene"] == "cena01")
    assert len(shot["takes"]) == 1 and shot["takes"][0]["liked"] is True
    assert len(edit.initial_timeline(project)["clips"]) == 1, "um clipe por foto, sem duplicar"


def test_per_scene_preview_without_photo_does_not_reach_montage(sb, project, monkeypatch):
    """ADR-022: sem `photo` (preview por-cena, wave-7), nada é registrado no downstream (retrocompat)."""
    from studio.animate import service as animate
    a, _ = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a], "primary": a}])
    _fake_video_cli(monkeypatch, sb)
    sb.start_video_generate(project, "cena01", "dolly", "single", 5, {"image": a})   # sem photo
    for _ in range(100):
        if sb.video_job_status(project, "cena01")["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert animate.stored_takes(project)["shots"] == [], "preview por-cena não vira take da montagem"


def test_video_generate_single_saves_take_and_persists_scene(sb, project, monkeypatch, root):
    a, _ = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a], "primary": a}])
    sent = _fake_video_cli(monkeypatch, sb)
    sb.start_video_generate(project, "cena01", "Slow dolly on the can", "single", 5, {"image": a})
    job = _wait_video(sb, project, "cena01")
    assert job["state"] == "done" and job["added"] == 1
    rel = "storyboard/cena01/video/take_1.mp4"
    assert job["video"] == rel and (root / rel).exists()
    assert sent["model"] == "kling2_6" and sent["timeout"] == sb.VIDEO_TIMEOUT_S
    assert sent["params"]["duration"] == 5 and sent["params"]["sound"] is False
    assert sent["params"]["start_image"].endswith(Path(a).name) and "end_image" not in sent["params"]
    scene = sb.load_scenes(project)["scenes"][0]
    assert scene["videos"] == [rel] and scene["video_prompt"] == "Slow dolly on the can"


def test_video_generate_start_end_sends_both_frames_with_kling30(sb, project, monkeypatch, root):
    a, b = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a, b], "primary": a}])
    sent = _fake_video_cli(monkeypatch, sb)
    sb.start_video_generate(project, "cena01", "dramatic transition", "start_end", 10,
                            {"start_image": a, "end_image": b})
    job = _wait_video(sb, project, "cena01")
    assert job["state"] == "done"
    assert sent["model"] == "kling3_0" and sent["params"]["duration"] == 10   # ADR-023
    assert sent["params"]["start_image"].endswith(Path(a).name)
    assert sent["params"]["end_image"].endswith(Path(b).name)


def test_video_generate_second_take_increments_and_keeps_history(sb, project, monkeypatch, root):
    a, _ = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "cena", "images": [a], "primary": a}])
    _fake_video_cli(monkeypatch, sb)
    sb.start_video_generate(project, "cena01", "take one", "single", 5, {"image": a})
    _wait_video(sb, project, "cena01")
    sb.start_video_generate(project, "cena01", "take two", "single", 5, {"image": a})
    _wait_video(sb, project, "cena01")
    assert (root / "storyboard/cena01/video/take_2.mp4").exists()
    assert sb.load_scenes(project)["scenes"][0]["videos"] == [
        "storyboard/cena01/video/take_1.mp4", "storyboard/cena01/video/take_2.mp4"]


def test_video_generate_validates_prompt_mode_and_frames(sb, project, monkeypatch):
    a, _ = _two_ideas(sb, project)
    _fake_video_cli(monkeypatch, sb)
    with pytest.raises(sb.Invalid):
        sb.start_video_generate(project, "cena01", "  ", "single", 5, {"image": a})     # sem prompt
    with pytest.raises(sb.Invalid):
        sb.start_video_generate(project, "cena01", "p", "single", 5, {})                # sem frame
    with pytest.raises(sb.Invalid):
        sb.start_video_generate(project, "cena01", "p", "start_end", 5, {"start_image": a})  # falta end


def test_video_job_is_isolated_per_scene(sb, project, monkeypatch, root):
    a, _ = _two_ideas(sb, project)
    sb.save_scenes(project, [{"text": "c1", "images": [a], "primary": a}, {"text": "c2"}])
    gate = threading.Event()
    _fake_video_cli(monkeypatch, sb, gate=gate)
    sb.start_video_generate(project, "cena01", "p", "single", 5, {"image": a})
    # mesma cena em andamento → recusa (chave por cena)
    with pytest.raises(sb.Precondition):
        sb.start_video_generate(project, "cena01", "p", "single", 5, {"image": a})
    # outra cena não colide (registry por cena) — mas idle ainda
    assert sb.video_job_status(project, "cena02")["state"] == "idle"
    gate.set()
    assert _wait_video(sb, project, "cena01")["state"] == "done"


def test_scenes_videos_are_additive_and_retrocompatible(sb, project, root):
    """Um scenes.json antigo (sem campos de vídeo) lê com defaults; PUT valida o mp4 sob <cena>/video/."""
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": [
        {"id": "cena01", "n": 1, "text": "antiga", "images": [], "primary": None}]}))
    s = sb.load_scenes(project)["scenes"][0]
    assert s["video_desc"] == "" and s["video_prompt"] == "" and s["videos"] == []
    # PUT com um vídeo inexistente é recusado (sem traversal); um mp4 real sob <cena>/video/ passa
    make_image(root / "storyboard" / "ideas" / "x.png")  # só para existir a pasta ideas
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [{"text": "c", "videos": ["storyboard/cena01/video/nao-existe.mp4"]}])
    (root / "storyboard" / "cena01" / "video").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "cena01" / "video" / "take_1.mp4").write_bytes(b"x")
    out = sb.save_scenes(project, [{"text": "c", "video_desc": "a can falls",
                                    "videos": ["storyboard/cena01/video/take_1.mp4"]}])["scenes"][0]
    assert out["video_desc"] == "a can falls" and out["videos"] == ["storyboard/cena01/video/take_1.mp4"]


# ---------- `[extensão]` inpaint-marcacao: marcação (rabisco) + kind `edit_area` ----------
def _annotate(sb, project, color=(9, 9, 9), source_id=None):
    return sb.import_annotation(project, image_bytes(color=color), "marcacao.png", source_id)


def test_annotation_is_saved_with_role_and_parent(sb, project, base, root):
    """Contrato 1: `parent` é o candidato de origem ou o literal "base"; role sempre `annotation`."""
    sb.import_upload(project, [("a.png", image_bytes(color=(1, 2, 3)))])
    idea = sb.list_ideas(project)["ideas"][0]
    on_idea = _annotate(sb, project, (10, 10, 10), idea["id"])
    assert on_idea["role"] == "annotation" and on_idea["parent"] == idea["id"]
    assert on_idea["deduped"] is False
    assert on_idea["file"] == f"storyboard/candidates/{on_idea['id']}.png"
    assert on_idea["thumb"] == f"storyboard/candidates/thumbs/{on_idea['id']}.jpg"
    assert (root / on_idea["file"]).exists() and (root / on_idea["thumb"]).exists()
    on_base = _annotate(sb, project, (20, 20, 20))
    assert on_base["parent"] == "base" and on_base["role"] == "annotation"


def test_annotation_upload_is_idempotent_by_sha1(sb, project, base, root):
    """Reenviar os MESMOS bytes devolve o candidato já existente, sem criar segundo arquivo."""
    first = _annotate(sb, project, (33, 44, 55))
    files = sorted(p.name for p in (root / "storyboard" / "candidates").glob("*.png"))
    again = _annotate(sb, project, (33, 44, 55))
    assert again["deduped"] is True and again["id"] == first["id"]
    assert again["parent"] == first["parent"] and again["role"] == "annotation"
    assert sorted(p.name for p in (root / "storyboard" / "candidates").glob("*.png")) == files


def test_annotation_refuses_bytes_that_are_not_an_image(sb, project, base):
    with pytest.raises(sb.Invalid) as e:
        sb.import_annotation(project, b"nao sou uma imagem", "marcacao.png")
    assert str(e.value) == "arquivo de marcação inválido (envie o PNG exportado pelo canvas)"


def test_annotation_requires_base_or_an_existing_source(sb, project, root):
    """Sem `source_id` a marcação é sobre a base (409 sem ela); `source_id` inexistente é 422."""
    with pytest.raises(sb.Precondition):
        _annotate(sb, project)
    make_image(root / "base" / "base_final.png")
    with pytest.raises(sb.Invalid) as e:
        _annotate(sb, project, (7, 7, 7), "nao-existe")
    assert str(e.value) == "ideia inexistente: nao-existe"


def test_annotation_never_shows_up_in_the_gallery(sb, project, base):
    """Invariante do FDD §2: a marcação é insumo da geração, nunca ideia."""
    sb.import_upload(project, [("a.png", image_bytes(color=(4, 5, 6)))])
    idea_ids = [i["id"] for i in sb.list_ideas(project)["ideas"]]
    ann = _annotate(sb, project, (60, 60, 60))
    ideas = sb.list_ideas(project)["ideas"]
    assert [i["id"] for i in ideas] == idea_ids, "o candidato comum continua aparecendo"
    assert ann["id"] not in [i["id"] for i in ideas]
    assert sb.status(project)["ideas"] == len(idea_ids)


def test_annotation_cannot_be_selected_as_an_idea(sb, project, base):
    sb.import_upload(project, [("a.png", image_bytes(color=(4, 5, 6)))])
    idea = sb.list_ideas(project)["ideas"][0]
    ann = _annotate(sb, project, (70, 70, 70))
    with pytest.raises(sb.Invalid) as e:
        sb.select_ideas(project, [ann["id"]])
    assert str(e.value) == "marcação não pode ser selecionada como ideia"
    assert sb.select_ideas(project, [idea["id"]])["selected"] == 1, "seleção comum segue funcionando"


def test_edit_area_instruction_is_the_fixed_english_prompt(sb, project, base):
    """A instrução é montada pelo SERVIDOR (FDD §5) e não usa o sufixo genérico dos kinds antigos."""
    r = sb.build_instruction(project, "edit_area", "make the rope thinner", 4)
    assert r["instruction"] == (
        "Image 1 is the original photo. Image 2 is the same photo with a red hand-drawn marking "
        "highlighting one region. Apply the following change ONLY inside the marked region: "
        "make the rope thinner. Keep everything outside the marked region exactly identical to "
        "image 1, and do not render the marking itself in the result. Keep everything else "
        "identical, realistic.")
    assert r["kind"] == "edit_area" and r["count"] == 4
    # a pontuação final do usuário some, como nos kinds da aula (`core = body.rstrip(" .;")`)
    assert sb.build_instruction(project, "edit_area", "make the rope thinner.", 1)["instruction"] == r["instruction"]
    assert sb.SUFFIX not in r["instruction"].replace(
        "Keep everything else identical, realistic.", "", 1) , "o texto fixo não é o sufixo dos kinds antigos"
    # as validações da aula 010 valem igual, com as mesmas mensagens
    for text, count in [("", 4), ("x" * 301, 4), ("Make it smaller", 2)]:
        with pytest.raises(sb.Invalid):
            sb.build_instruction(project, "edit_area", text, count)
    with pytest.raises(sb.Invalid) as e:
        sb.build_instruction(project, "edit_area", "Make it smaller. Remove the rope", 4)
    assert "uma instrução por vez" in str(e.value).lower()


def test_edit_area_sends_original_first_and_the_annotation_second(sb, project, base, monkeypatch, root):
    """Invariante do FDD §6: `image_references` tem 2 itens com a ORIGINAL no índice 0."""
    seen = []
    _fake_cli(monkeypatch, sb, urls=("http://x/a.png",))
    real = sb.hf.generate
    monkeypatch.setattr(sb.hf, "generate", lambda m, p, timeout_s=600: (seen.append(p), real(m, p, timeout_s))[-1])
    ann = _annotate(sb, project, (80, 80, 80))
    sb.start_generate(project, "nano_banana_2", "edit_area", "make the rope thinner", 1,
                      annotation_id=ann["id"])
    assert _wait_job(sb, project)["state"] == "done"
    refs = seen[-1]["image_references"]
    assert len(refs) == 2
    assert refs[0].replace("\\", "/").endswith("base/base_final.png")
    assert refs[1].replace("\\", "/").endswith(f"storyboard/candidates/{ann['id']}.png")
    assert seen[-1]["prompt"] == sb.build_instruction(project, "edit_area", "make the rope thinner", 1)["instruction"]


def test_edit_area_job_tags_candidates_and_records_the_spend(sb, project, base, monkeypatch, root):
    """FDD §9.5: `meta.kind`/`meta.annotation` nos importados + 1 linha por geração no livro-caixa."""
    from studio.common import settings
    _fake_cli(monkeypatch, sb, urls=("http://x/a.png",))
    ann = _annotate(sb, project, (90, 90, 90))
    sb.start_generate(project, "nano_banana_2", "edit_area", "make the rope thinner", 1,
                      annotation_id=ann["id"])
    assert _wait_job(sb, project)["state"] == "done"
    cands = json.loads((root / "storyboard" / "candidates.json").read_text())
    imported = [c for c in cands if c.get("source") == "cli"]
    assert imported and all(c["kind"] == "edit_area" and c["annotation"] == ann["id"] for c in imported)
    rows = [r for r in settings.history(project) if r["action"] == "storyboard.inpaint"]
    assert len(rows) == 1 and rows[0]["step"] == "storyboard" and rows[0]["model"] == "nano_banana_2"


def test_legacy_kinds_keep_one_reference_and_record_nothing(sb, project, base, monkeypatch):
    """Regressão da pendência P1: os kinds da aula não passam a registrar gasto nem ganham referência."""
    from studio.common import settings
    seen = []
    _fake_cli(monkeypatch, sb, urls=("http://x/a.png",))
    real = sb.hf.generate
    monkeypatch.setattr(sb.hf, "generate", lambda m, p, timeout_s=600: (seen.append(p), real(m, p, timeout_s))[-1])
    sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    assert _wait_job(sb, project)["state"] == "done"
    assert len(seen[-1]["image_references"]) == 1
    assert settings.history(project) == []


def test_inpaint_action_resolves_the_default_model(sb, project, studio_env):
    from studio.common import settings
    d = settings.default_for("storyboard.inpaint", project)
    assert d == {"action": "storyboard.inpaint", "model": "nano_banana_2", "variant": "2k", "source": "code"}
    settings.set_global_default("storyboard.inpaint", "gpt_image_2")
    assert settings.default_for("storyboard.inpaint", project)["source"] == "global"
    settings.set_project_default(project, "storyboard.inpaint", "nano_banana_2", "2k")
    assert settings.default_for("storyboard.inpaint", project)["source"] == "project"
    assert "storyboard.inpaint" in {a["key"] for a in settings.all_defaults(project)}


def test_annotation_refuses_bytes_that_are_a_plain_candidate(sb, project, base):
    """Divergência D1 do fechamento: o SHA-1 idêntico ao de uma IDEIA comum não é dedupe de marcação.

    Devolver 200 nesse caso daria `role`/`parent` vazios (fora do domínio do Contrato 1) e o id
    resultante seria recusado depois pelo `edit_area`. A recusa acontece cedo, com a causa real.
    """
    data = image_bytes(color=(9, 9, 9))
    sb.import_upload(project, [("a.png", data)])
    with pytest.raises(sb.Invalid) as e:
        sb.import_annotation(project, data, "a.png")
    assert str(e.value) == "essa imagem já existe como ideia, sem marcação: rabisque a região antes de salvar"
    # e a ideia comum continua intacta na galeria (a recusa não mexeu em candidates.json)
    assert len(sb.list_ideas(project)["ideas"]) == 1


def test_annotation_can_never_become_a_scene_image(sb, project, base):
    """Matriz §6, metade "como imagem de cena": a marcação nunca chega a `storyboard/ideas/`.

    `select_ideas` já a recusa, então ela não é copiada para `ideas/` — e `_check_image` barra
    qualquer caminho fora dali. O teste prova a barreira de ponta a ponta (a mensagem que sai é a
    de `_check_image`, não a da linha de seleção da matriz: divergência registrada no fechamento).
    """
    ann = _annotate(sb, project, (80, 80, 80))
    scenes = sb.load_scenes(project)["scenes"]
    scenes[0]["images"] = [f"storyboard/candidates/{ann['id']}.png"]
    scenes[0]["primary"] = scenes[0]["images"][0]
    with pytest.raises(sb.Invalid) as e:
        sb.save_scenes(project, scenes)
    assert "storyboard/ideas" in str(e.value)
    assert not (sb.project_dir(project) / "storyboard" / "ideas" / f"{ann['id']}.png").exists()
# ---------- `[extensão]` preset de realismo no video-prompt (FDD prompter-presets §5) ----------
#: `preset` aqui é o preset de REALISMO, não as fórmulas da aula (`PRESETS`/`sbPreset`, amenda A3).
def test_video_prompt_carries_the_realism_preset(sb, project, monkeypatch):
    """T3.10 — sem o campo, resolve o default da ação `motion` (`None` de fábrica) e o prompter é
    chamado sem preset; com id explícito, o id vai ao prompter e volta na resposta."""
    monkeypatch.setattr(sb.prompter, "available", lambda: True)
    seen = {}

    def fake_brief(kind, brief, preset=None):
        seen["preset"] = preset
        return {"prompt": "Slow dolly-in.", "source": "claude", "seconds": 3.0, "preset": preset}

    monkeypatch.setattr(sb.prompter, "from_brief", fake_brief)
    r = sb.video_prompt(project, "cena01", "an astronaut walking", {"mode": "single"})
    assert r["preset"] is None and seen["preset"] is None

    com = sb.video_prompt(project, "cena01", "an astronaut walking", {"mode": "single"},
                          preset="anamorphic-film-look")
    assert com["preset"] == "anamorphic-film-look" and seen["preset"] == "anamorphic-film-look"


def test_video_prompt_keeps_the_preset_when_claude_fails(sb, project, monkeypatch):
    """T3.12 — o `except Exception` que cai no template não pode perder o preset nem virar 500."""
    monkeypatch.setattr(sb.prompter, "available", lambda: True)
    monkeypatch.setattr(sb.prompter, "from_brief",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bot caiu")))
    r = sb.video_prompt(project, "cena01", "an astronaut walking", {"mode": "single"},
                        preset="sony-venice-night")
    assert r["source"] == "template" and r["preset"] == "sony-venice-night"


def test_video_prompt_does_not_touch_the_scenes_schema(sb, project, root, monkeypatch):
    """T3.13 — amenda A5: quem persiste é o `PUT /storyboard/scenes`; `scenes.json` não ganha campo
    (ADR-018/022). O preset do video-prompt vive só na resposta."""
    sb.save_scenes(project, [{"text": "Close no astronauta"}])
    arquivo = root / "storyboard" / "scenes.json"
    antes = arquivo.read_bytes()
    monkeypatch.setattr(sb.prompter, "available", lambda: False)
    r = sb.video_prompt(project, "cena01", "an astronaut walking", {"mode": "single"},
                        preset="documentary-street")
    assert r["preset"] == "documentary-street"
    assert arquivo.read_bytes() == antes, "video_prompt não escreve scenes.json"


# ---------- `[extensão]` wave 9 (ADR-025): roteiro por LLM no serviço (Claude sempre fake) ----------
def _script_result(count: int, text: str = "Cena curta.", images=None, rig=None,
                   preset=None) -> dict:
    """Resposta no formato que `prompter.script` publica (contrato da task_01).

    Bot OBEDIENTE: com `rig`, corpo/lente/formato entram LITERALMENTE em cada `image_prompt` — é o
    que o serviço passou a exigir quando há preset (review 001 · issue_002).
    """
    rig_text = (f" Shot on camera body {rig['camera']}, lens {rig['lens']}, "
                f"format {rig['format']}." if rig else "")
    return {"scenes": [{"n": i, "arc": "acao", "text": text,
                        "image_prompt": f"A cinematic photograph, scene {i}.{rig_text}",
                        "negative": "plastic skin"} for i in range(1, count + 1)],
            "notes_pt": "Arco fechado.", "source": "claude", "seconds": 12.5,
            "preset": preset, "model_target": "nano_banana_2", "count": count,
            "images": images or []}


def _fake_prompter_script(sb, monkeypatch, calls, count=5, text="Cena curta."):
    """Substitui `prompter.script` (ADR-008: nada de processo real) e registra a chamada."""
    def fake(images, brief, preset=None, **kw):
        calls.append({"images": list(images), "brief": brief, "preset": preset, **kw})
        rig = sb.prompter.REALISM_PRESETS[preset]["rig"] if preset else None
        return _script_result(kw.get("count", count), text, rig=rig, preset=preset)
    monkeypatch.setattr(sb.prompter, "available", lambda: True)
    monkeypatch.setattr(sb.prompter, "script", fake)
    return calls


def _wait_script(sb, project) -> dict:
    for _ in range(100):
        job = sb.script_status(project)
        if job["state"] != "running":
            return job
        threading.Event().wait(0.05)
    return sb.script_status(project)


def test_script_truncates_a_long_scene_text_and_logs_it(sb, project, base, root, monkeypatch):
    """T2.18: o teto de 500 (`MAX_SCENE_TEXT`) é do SERVIÇO — e o corte fica registrado no job."""
    _fake_prompter_script(sb, monkeypatch, [], text="x" * 700)
    sb.script_generate(project, count=1)
    job = _wait_script(sb, project)
    assert job["state"] == "done"
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert len(data["scenes"][0]["text"]) == sb.MAX_SCENE_TEXT
    assert any("truncado" in linha for linha in job["log"]), job["log"]


def test_script_never_touches_scenes_json(sb, project, base, root, monkeypatch):
    """T2.19 (critério 1 / invariante suprema): o roteiro é sugestão — `scenes.json` fica intocado."""
    sb.save_scenes(project, [{"text": "Cena 1 escrita à mão"}, {"text": ""},
                             {"text": "Cena 3 escrita à mão"}, {"text": ""}, {"text": ""}])
    antes = (root / "storyboard" / "scenes.json").read_bytes()
    _fake_prompter_script(sb, monkeypatch, [])
    sb.script_generate(project, count=5)
    assert _wait_script(sb, project)["state"] == "done"
    assert (root / "storyboard" / "scenes.json").read_bytes() == antes
    assert (root / "storyboard" / "script.json").is_file()


def test_script_spends_no_higgsfield_credit(sb, project, base, root, monkeypatch):
    """T2.20 (critério 11 / R2): Claude é assinatura local — nada de `hf.*` nem livro-caixa."""
    def boom(*a, **kw):  # pragma: no cover - o teste falha se for chamado
        raise AssertionError("o roteiro não pode tocar a Higgsfield")
    for attr in ("generate", "cost", "download"):
        monkeypatch.setattr(sb.hf, attr, boom)
    ledger = sb.settings.LEDGER_PATH
    antes = ledger.read_text() if ledger.is_file() else ""
    _fake_prompter_script(sb, monkeypatch, [])
    sb.script_generate(project, count=2)
    assert _wait_script(sb, project)["state"] == "done"
    assert (ledger.read_text() if ledger.is_file() else "") == antes


def test_script_context_images_are_base_first_then_mood(sb, project, base, root, monkeypatch):
    """T2.22 (R8): base + até 3 frames do mood selecionado, no teto de 4 imagens do prompter."""
    for i in range(5):
        make_image(root / "mood" / "selected" / f"m{i}.png")
    calls = _fake_prompter_script(sb, monkeypatch, [])
    sb.script_generate(project, count=2)
    assert _wait_script(sb, project)["state"] == "done"
    enviadas = calls[0]["images"]
    assert len(enviadas) == sb.prompter.MAX_IMAGES == 4
    assert enviadas[0] == root / sb.BASE_IMAGE
    assert [p.name for p in enviadas[1:]] == ["m0.png", "m1.png", "m2.png"]
    assert all(p.is_file() for p in enviadas)


def test_script_runs_with_the_base_alone_when_there_is_no_mood(sb, project, base, root, monkeypatch):
    """T2.22 (segunda metade): sem mood selecionado o job segue só com a base e termina `done`."""
    calls = _fake_prompter_script(sb, monkeypatch, [])
    sb.script_generate(project, count=2)
    assert _wait_script(sb, project)["state"] == "done"
    assert calls[0]["images"] == [root / sb.BASE_IMAGE]


def test_script_registry_is_the_one_the_step_reset_discovers(sb, project, base, studio_env):
    """T2.23 (R5): o registro do roteiro mora no único slot que `reset._registries` conhece."""
    from studio.common import reset
    assert hasattr(sb, "_story_registry"), "o nome trava o reset da etapa (lista fechada em reset.py)"
    assert sb._story_registry in reset._registries("storyboard")
    sb._story_registry._jobs[project] = {"state": "running"}
    with pytest.raises(reset.ResetBlocked):
        reset.reset_step(project, "storyboard")
    sb._story_registry.clear(project)
