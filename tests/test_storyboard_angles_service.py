"""Etapa 4 (ângulos, ADR-015) — segue a aula 011 (ângulos por cena) e a aula 013 (cena do produto).

Sem rede e sem CLI: `hf.generate`/`hf.download` são fakeados; os artefatos consumidos
(`storyboard/scenes.json`, `base/base_final.png`, `mood/palette.json`) são fixtures locais.
"""
from __future__ import annotations

import json
import threading

import pytest

from tests.conftest import image_bytes, make_image

SCENES = [
    {"id": "cena01", "n": 1, "text": "close no astronauta andando na nevasca",
     "image": "storyboard/ideas/a1.png"},
    {"id": "cena02", "n": 2, "text": "a lata cravada na neve", "image": "storyboard/ideas/a2.png"},
    {"id": "cena03", "n": 3, "text": "plano aberto da tempestade", "image": None},
    {"id": "cena04", "n": 4, "text": "detalhe do rótulo congelando", "image": None},
    {"id": "cena05", "n": 5, "text": "o astronauta bebe e o gelo racha", "image": None},
]


@pytest.fixture()
def shots(studio_env):
    import importlib
    return importlib.import_module("studio.storyboard.angles")


@pytest.fixture()
def project(studio_env):
    """Projeto com o terreno das etapas 2, 3 e 4 (as frentes irmãs desta wave)."""
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    root = refs.project_dir(pid)
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": SCENES}))
    make_image(root / "storyboard" / "ideas" / "a1.png", color=(10, 40, 90))
    make_image(root / "storyboard" / "ideas" / "a2.png", color=(90, 40, 10))
    make_image(root / "base" / "base_final.png", color=(200, 200, 250))
    (root / "mood").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0b1d3a", "#39ff14"],
                                                            "note": "neon na neve"}))
    return pid


def _wait(shots, pid, tries=100):
    for _ in range(tries):
        if shots.job_status(pid)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return shots.job_status(pid)


# ---------- risco do FDD §10: `ingest` com step de subpasta ----------
def test_ingest_accepts_scene_subfolder_as_step(studio_env, project):
    """Decisão 8 da wave: `step="storyboard/cena01"` separa candidatos por cena sem tocar em ingest."""
    from studio.common import ingest
    root = studio_env["refs"].project_dir(project)
    c = ingest.ingest_bytes(root, "storyboard/cena01", image_bytes(), "upload", "a.png")
    assert c and (root / "storyboard" / "cena01" / "candidates" / c["file"]).exists()
    assert ingest.load_candidates(root, "storyboard/cena01") and not ingest.load_candidates(root, "storyboard/cena02")


# ---------- base por cena ----------
def test_prepare_base_uses_scene_image_or_campaign_base(shots, studio_env, project):
    root = studio_env["refs"].project_dir(project)
    sources = {s["id"]: shots.prepare_base(project, s["id"])["source"] for s in SCENES}
    assert sources == {"cena01": "storyboard", "cena02": "storyboard",
                       "cena03": "base", "cena04": "base", "cena05": "base"}
    for s in SCENES:
        assert (root / "storyboard" / s["id"] / "base.png").exists()


def test_prepare_base_uses_the_primary_keyframe(shots, studio_env, project):
    """[extensão] cena-multi-keyframe (ADR-018): a base da cena vem da PRINCIPAL, não do 1º da galeria.

    a1 (1ª da galeria) é apagada e a principal é a2 (existe): se o código usasse a 1ª imagem cairia
    para a base da campanha (`source="base"`); usar a principal mantém `source="storyboard"`."""
    root = studio_env["refs"].project_dir(project)
    (root / "storyboard" / "ideas" / "a1.png").unlink()
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": [
        {"id": "cena01", "n": 1, "text": "galeria",
         "images": ["storyboard/ideas/a1.png", "storyboard/ideas/a2.png"],
         "primary": "storyboard/ideas/a2.png"},
    ]}))
    assert shots.prepare_base(project, "cena01")["source"] == "storyboard"
    # a tela dos ângulos recebe a principal e a galeria da cena
    s = next(x for x in shots.list_scenes(project)["scenes"] if x["id"] == "cena01")
    assert s["primary"] == "storyboard/ideas/a2.png"
    assert s["images"] == ["storyboard/ideas/a1.png", "storyboard/ideas/a2.png"]


def test_prepare_base_is_idempotent_and_accepts_upload(shots, studio_env, project):
    a = shots.prepare_base(project, "cena01")
    assert shots.prepare_base(project, "cena01") == a
    r = shots.prepare_base(project, "cena03", "upload", image_bytes(color=(3, 3, 3)), "x.png")
    assert r["source"] == "upload"
    with pytest.raises(ValueError):
        shots.prepare_base(project, "cena03", "upload", b"x", "x.txt")
    with pytest.raises(ValueError):   # extensão aceita, conteúdo corrompido: 422, nunca 500
        shots.prepare_base(project, "cena03", "upload", b"nao e uma imagem", "x.png")


def test_prepare_base_without_any_image_is_a_conflict(shots, studio_env, project):
    (studio_env["refs"].project_dir(project) / "base" / "base_final.png").unlink()
    with pytest.raises(FileNotFoundError):
        shots.prepare_base(project, "cena03")


def test_unknown_or_malformed_scene(shots, project):
    with pytest.raises(LookupError):
        shots.prepare_base(project, "cena09")
    with pytest.raises(ValueError):
        shots.prepare_base(project, "../etc")


def test_scenes_json_missing_blocks_the_step(shots, studio_env, project):
    (studio_env["refs"].project_dir(project) / "storyboard" / "scenes.json").unlink()
    with pytest.raises(FileNotFoundError):
        shots.list_scenes(project)


# ---------- prompts da aula ----------
def test_angle_prompt_follows_lesson_formula(shots, project):
    r = shots.build_prompts(project, "cena01", "angle", "the astronaut", "close", True)
    text = r["prompts"][0]["text"]
    assert "Bring me another point of view of this image" in text
    assert "close-up on the astronaut" in text
    assert "Shot on RED Komodo 6K, 35mm, f/2.8, close shot, eye-level angle" in text
    assert r["count"] == 4 and r["aspect_ratio"] == "16:9"


def test_angle_prompt_without_realism_has_no_camera_block(shots, project):
    text = shots.build_prompts(project, "cena01", realism=False)["prompts"][0]["text"]
    assert "RED Komodo" not in text
    assert "energy drink" in text, "sem subject explícito usa o produto do projeto"


def test_edit_prompt_is_numbered_and_closes_with_keep(shots, project):
    r = shots.build_prompts(project, "cena01", "edit",
                            edits=["Make the helmet visor tinted so the face cannot be seen",
                                   "Remove the can in the background",
                                   "Make him walking through the blizzard"])
    assert len(r["prompts"]) == 1
    text = r["prompts"][0]["text"]
    assert text == ("I want the following modifications. "
                    "1. Make the helmet visor tinted so the face cannot be seen. "
                    "2. Remove the can in the background. "
                    "3. Make him walking through the blizzard. "
                    "Keep everything else identical, realistic.")
    with pytest.raises(ValueError):
        shots.build_prompts(project, "cena01", "edit", edits=[])


def test_list_scenes_carries_palette_and_the_color_warning(shots, studio_env, project):
    r = shots.list_scenes(project)
    assert "ANTES do multishot" in r["warning"]
    assert r["palette"]["colors"] == ["#0b1d3a", "#39ff14"]
    assert [s["id"] for s in r["scenes"]] == [s["id"] for s in SCENES]
    assert r["base_final"] == "base/base_final.png"
    (studio_env["refs"].project_dir(project) / "mood" / "palette.json").unlink()
    assert shots.list_scenes(project)["palette"]["colors"] == []


# ---------- importação ----------
def test_import_requires_base_and_dedupes(shots, project):
    with pytest.raises(shots.NotReady):
        shots.import_upload(project, "cena01", [("a.png", image_bytes())])
    shots.prepare_base(project, "cena01")
    data = image_bytes(color=(9, 9, 9))
    assert shots.import_upload(project, "cena01", [("a.png", data), ("b.png", data)])["added"] == 1
    assert shots.import_upload(project, "cena01", [("c.png", image_bytes(color=(1, 200, 1)))])["added"] == 1
    r = shots.list_candidates(project, "cena01")
    assert len(r["candidates"]) == 2
    assert r["candidates"][0]["file"].startswith("storyboard/cena01/candidates/"), "caminho relativo à raiz"
    assert r["base"] == "storyboard/cena01/base.png"


def test_import_downloads_only_recent_images(shots, studio_env, project):
    import os
    import time
    shots.prepare_base(project, "cena02")
    dl = studio_env["tmp"] / "downloads"
    make_image(dl / "novo.jpg", color=(4, 5, 6))
    old = make_image(dl / "velho.jpg", color=(7, 8, 9))
    os.utime(old, (time.time() - 3 * 3600, time.time() - 3 * 3600))
    r = shots.import_downloads(project, "cena02", since_minutes=60)
    assert r["added"] == 1 and r["scanned"] == 1
    assert shots.list_candidates(project, "cena02")["candidates"][0]["scene"] == "cena02"


def test_import_downloads_missing_folder_is_not_found(shots, project):
    shots.prepare_base(project, "cena02")
    with pytest.raises(LookupError):
        shots.import_downloads(project, "cena02", folder="/nao/existe")


# ---------- seleção, ordenação e storyboard ----------
def _two_candidates(shots, project, scene="cena01"):
    shots.prepare_base(project, scene)
    shots.import_upload(project, scene, [("a.png", image_bytes(color=(11, 22, 33))),
                                         ("b.png", image_bytes(color=(44, 55, 66)))], prompt="Bring me another…")
    return [c["id"] for c in shots.list_candidates(project, scene)["candidates"]]


def test_select_writes_final_frames_in_order_and_rewrites_storyboard(shots, studio_env, project):
    root = studio_env["refs"].project_dir(project)
    a, b = _two_candidates(shots, project)
    r = shots.select_shots(project, "cena01", [{"id": b, "upscaled": True}, {"id": a}])
    assert [s["id"] for s in r["shots"]] == ["shot01", "shot02"]
    assert [s["order"] for s in r["shots"]] == [1, 2]
    assert r["shots"][0]["candidate"] == b and r["shots"][0]["upscaled"] is True
    assert (root / "storyboard" / "cena01" / "shot01_final.png").exists()
    assert (root / "storyboard" / "cena01" / "shot02_final.png").exists()
    board = shots.load_storyboard(project)
    assert board["scenes"][0]["shots"][0]["file"] == "storyboard/cena01/shot01_final.png"
    assert board["scenes"][0]["shots"][0]["prompt"] == "Bring me another…"

    shots.select_shots(project, "cena01", [{"id": a}])
    assert not (root / "storyboard" / "cena01" / "shot02_final.png").exists(), "frame órfão é removido"
    assert len(shots.load_storyboard(project)["scenes"][0]["shots"]) == 1

    shots.select_shots(project, "cena01", [])
    assert shots.load_storyboard(project)["scenes"][0]["shots"] == []


def test_select_marks_candidates_with_flag_and_saved_order(shots, project):
    """Reabrir a cena remarca os frames escolhidos NA ORDEM salva: o painel 04 relê `selected` e
    `selected_order` de GET /scenes/{cena}/candidates (sem isso, salvar de novo apagaria os finais)."""
    a, b = _two_candidates(shots, project)
    shots.select_shots(project, "cena01", [{"id": b, "upscaled": True}, {"id": a}])
    cands = {c["id"]: c for c in shots.list_candidates(project, "cena01")["candidates"]}
    assert cands[b]["selected"] is True and cands[a]["selected"] is True
    assert cands[b]["selected_order"] == 1 and cands[a]["selected_order"] == 2

    shots.select_shots(project, "cena01", [{"id": a}])
    cands = {c["id"]: c for c in shots.list_candidates(project, "cena01")["candidates"]}
    assert cands[a]["selected"] is True and cands[a]["selected_order"] == 1
    assert cands[b]["selected"] is False and cands[b]["selected_order"] is None


def test_select_rejects_unknown_or_duplicated_candidate(shots, project):
    a, _b = _two_candidates(shots, project)
    with pytest.raises(ValueError):
        shots.select_shots(project, "cena01", [{"id": "naoexiste"}])
    with pytest.raises(ValueError):
        shots.select_shots(project, "cena01", [{"id": a}, {"id": a}])


def test_storyboard_matches_the_wave_schema_for_animate(shots, studio_env, project):
    """[cross-feature] shape que `animate` lê sem adaptação (contrato copiado da wave-1)."""
    root = studio_env["refs"].project_dir(project)
    a, _b = _two_candidates(shots, project)
    board = shots.select_shots(project, "cena01", [{"id": a}]) and shots.load_storyboard(project)
    assert set(board) == {"scenes", "product_scene"}
    assert [s["id"] for s in board["scenes"]] == [s["id"] for s in SCENES], "toda cena aparece, na ordem de n"
    for scene in board["scenes"]:
        assert set(scene) >= {"id", "base", "shots"}
        for shot in scene["shots"]:
            assert set(shot) >= {"id", "file", "order", "prompt"}
            assert (root / shot["file"]).exists()
    assert board["product_scene"] is None


# ---------- cena do produto (aula 013) ----------
def test_product_ref_requires_the_campaign_base(shots, studio_env, project):
    root = studio_env["refs"].project_dir(project)
    (root / "base" / "base_final.png").unlink()
    with pytest.raises(FileNotFoundError):
        shots.set_product_ref(project, image_bytes(), "geladeira.png")


def test_product_prompts_are_the_two_lesson_instructions(shots, project):
    with pytest.raises(FileNotFoundError):
        shots.product_prompts(project)
    shots.set_product_ref(project, image_bytes(color=(80, 80, 80)), "geladeira.png")
    r = shots.product_prompts(project)
    assert r["image_references"] == ["storyboard/product/ref.png", "base/base_final.png"]
    assert r["prompts"][0]["text"] == ("Replace the can in image 1 with the can from image 2. "
                                       "Keep everything else identical, realistic.")
    assert r["prompts"][1]["text"] == ("Remove the text below the can and make everything around it "
                                       "frozen. Keep everything else identical, realistic.")


def test_product_select_writes_product_scene_and_can_be_cleared(shots, studio_env, project):
    root = studio_env["refs"].project_dir(project)
    shots.set_product_ref(project, image_bytes(color=(80, 80, 80)), "geladeira.png")
    shots.import_upload(project, "product", [("p.png", image_bytes(color=(120, 10, 10)))],
                        prompt="Remove the text below the can…")
    cid = shots.list_candidates(project, "product")["candidates"][0]["id"]
    ps = shots.select_product(project, cid, upscaled=True)["product_scene"]
    assert ps["id"] == "product" and ps["base"] == "storyboard/product/ref.png"
    assert ps["shots"][0]["file"] == "storyboard/product/product_final.png" and ps["shots"][0]["order"] == 1
    assert (root / "storyboard" / "product" / "product_final.png").exists()
    assert shots.load_storyboard(project)["product_scene"]["shots"][0]["upscaled"] is True
    assert shots.select_product(project, None)["product_scene"] is None
    assert shots.load_storyboard(project)["product_scene"] is None


def test_product_clear_also_unmarks_the_candidate(shots, project):
    """Remover a cena do produto apaga o flag `selected` do candidato — senão o painel 04 reabre
    com a candidata marcada e ressuscita uma escolha que já não existe no disco."""
    shots.set_product_ref(project, image_bytes(color=(80, 80, 80)), "geladeira.png")
    shots.import_upload(project, "product", [("p.png", image_bytes(color=(120, 10, 10)))])
    cid = shots.list_candidates(project, "product")["candidates"][0]["id"]
    shots.select_product(project, cid)
    assert shots.list_candidates(project, "product")["candidates"][0]["selected"] is True
    shots.select_product(project, None)
    assert shots.list_candidates(project, "product")["candidates"][0]["selected"] is False


# ---------- geração e upscale via CLI (fakeados) ----------
def _fake_cli(monkeypatch, shots):
    """Uma chamada ao CLI por imagem (FDD §4.5): cada `generate` devolve uma URL nova."""
    monkeypatch.setattr(shots, "DOWNLOAD_RETRY_SLEEP", 0)
    calls = {"n": 0}

    def generate(*a, **k):
        calls["n"] += 1
        n = calls["n"]
        return {"urls": [f"https://higgsfield.example/{n}.png"], "id": f"job-{n}", "raw": {"call": n}}

    def download(url, dest):
        from pathlib import Path
        n = int(url.rsplit("/", 1)[-1].split(".")[0])
        Path(dest).write_bytes(image_bytes(color=(n * 20 % 255, 40, 200)))
        return Path(dest)

    monkeypatch.setattr(shots.hf, "generate", generate)
    monkeypatch.setattr(shots.hf, "download", download)


def test_generate_downloads_and_registers_candidates(shots, studio_env, project, monkeypatch):
    root = studio_env["refs"].project_dir(project)
    shots.prepare_base(project, "cena01")
    _fake_cli(monkeypatch, shots)
    shots.start_generate(project, "cena01", "nano_banana_2", ["Bring me another point of view."], count=4)
    job = _wait(shots, project)
    assert job["state"] == "done" and job["added"] == 4 and job["done"] == 4 and job["total"] == 4
    assert job["scene"] == "cena01" and job["op"] == "generate"
    cands = shots.list_candidates(project, "cena01")["candidates"]
    assert len(cands) == 4 and all(c["model"] == "nano_banana_2" and c["scene"] == "cena01" for c in cands)
    assert {c["job_id"] for c in cands} == {f"job-{i}" for i in range(1, 5)}
    assert len(list((root / "jobs").glob("storyboard_job-*.json"))) == 4
    assert any("prompt 1/1 imagem 4/4" in line for line in job["log"])


def test_generate_records_the_spend_in_the_ledger(shots, studio_env, project, monkeypatch):
    """Livro-caixa (ADR-016): cada geração paga de ângulo escreve uma linha `storyboard.angles`."""
    from studio.common import settings
    shots.prepare_base(project, "cena01")
    _fake_cli(monkeypatch, shots)
    shots.start_generate(project, "cena01", "nano_banana_2", ["Bring me another point of view."], count=3)
    assert _wait(shots, project)["state"] == "done"
    rows = [r for r in settings.history(project) if r["action"] == "storyboard.angles"]
    assert len(rows) == 3
    assert all(r["step"] == "storyboard" and r["model"] == "nano_banana_2" for r in rows)


def test_upscale_records_the_spend_in_the_ledger(shots, studio_env, project, monkeypatch):
    """Livro-caixa (ADR-016): o upscale 2x High Fidelity registra `storyboard.upscale`."""
    from studio.common import settings
    shots.prepare_base(project, "cena01")
    _fake_cli(monkeypatch, shots)
    shots.start_generate(project, "cena01", "nano_banana_2", ["p"], count=1)
    assert _wait(shots, project)["state"] == "done"
    cid = shots.list_candidates(project, "cena01")["candidates"][0]["id"]
    shots.start_upscale(project, "cena01", cid)
    assert _wait(shots, project)["state"] == "done"
    rows = [r for r in settings.history(project) if r["action"] == "storyboard.upscale"]
    assert len(rows) == 1 and rows[0]["step"] == "storyboard"


def test_generate_reports_cli_failure_without_losing_progress(shots, project, monkeypatch):
    shots.prepare_base(project, "cena01")

    def boom(*a, **k):
        raise RuntimeError("higgsfield: modelo desconhecido")

    monkeypatch.setattr(shots.hf, "generate", boom)
    shots.start_generate(project, "cena01", "nao_existe", ["p"], count=1)
    job = _wait(shots, project)
    assert job["state"] == "error" and "modelo desconhecido" in job["error"]


def test_generate_refuses_a_concurrent_job(shots, project, monkeypatch):
    shots.prepare_base(project, "cena01")
    gate = threading.Event()
    monkeypatch.setattr(shots.hf, "generate",
                        lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    shots.start_generate(project, "cena01", prompts=["p"], count=1)
    with pytest.raises(RuntimeError):
        shots.start_generate(project, "cena01", prompts=["p"], count=1)
    gate.set()
    assert _wait(shots, project)["state"] == "done"


def test_generate_validates_prompts_and_count(shots, project):
    shots.prepare_base(project, "cena01")
    with pytest.raises(ValueError):
        shots.start_generate(project, "cena01", prompts=[], count=1)
    with pytest.raises(ValueError):
        shots.start_generate(project, "cena01", prompts=["p"], count=9)


def test_upscale_creates_a_child_candidate(shots, project, monkeypatch):
    a, _b = _two_candidates(shots, project)
    _fake_cli(monkeypatch, shots)
    shots.start_upscale(project, "cena01", a)
    job = _wait(shots, project)
    assert job["state"] == "done" and job["added"] == 1 and job["op"] == "upscale"
    up = [c for c in shots.list_candidates(project, "cena01")["candidates"] if c.get("role") == "upscale"]
    assert len(up) == 1 and up[0]["parent"] == a and up[0]["upscaled"] is True


def test_upscale_of_unknown_candidate(shots, project):
    shots.prepare_base(project, "cena01")
    with pytest.raises(LookupError):
        shots.start_upscale(project, "cena01", "naoexiste")


# ---------- wave 2: fidelidade à aula 011 (auditoria 5.1–5.8) ----------
def test_candidate_can_be_promoted_to_the_scene_base(shots, studio_env, project):
    """5.2: a aula acerta a BASE da cena antes do Multishot — o resultado bom vira a nova base."""
    root = studio_env["refs"].project_dir(project)
    a, _b = _two_candidates(shots, project)
    antes = (root / "storyboard" / "cena01" / "base.png").read_bytes()
    r = shots.prepare_base(project, "cena01", "candidate", cand_id=a)
    assert r["source"] == "candidate" and r["candidate"] == a
    assert (root / "storyboard" / "cena01" / "base.png").read_bytes() != antes
    with pytest.raises(ValueError):
        shots.prepare_base(project, "cena01", "candidate")
    with pytest.raises(LookupError):
        shots.prepare_base(project, "cena01", "candidate", cand_id="naoexiste")


def test_edit_prompt_hint_points_to_the_new_base(shots, project):
    """5.2: o `ui_hint` da edição diz o que fazer com o resultado."""
    hint = shots.build_prompts(project, "cena01", "edit", edits=["Remove the can"])["ui_hint"]
    assert "NOVA BASE" in hint and "Multi Shot" in hint


def test_camera_block_is_offered_in_the_edit_prompt(shots, project):
    """5.3: a linguagem de câmera é do realismo da BASE — passa a ser oferecida também na edição,
    sem virar padrão (a edição da aula é uma lista de modificações)."""
    plain = shots.build_prompts(project, "cena01", "edit", edits=["Remove the can"])
    assert plain["prompts"][0]["text"].endswith("Keep everything else identical, realistic.")
    with_cam = shots.build_prompts(project, "cena01", "edit", edits=["Remove the can"], camera="red")
    assert "Shot on RED Komodo 6K, 35mm" in with_cam["prompts"][0]["text"]


def test_camera_presets_are_published_and_editable(shots, project):
    """5.7: "RED comercial" é preset aprovado (decisão 9), não trilho — dá para trocar e escrever."""
    r = shots.build_prompts(project, "cena01")
    ids = [c["id"] for c in r["cameras"]]
    assert ids == ["red", "documentario", "wide"] and r["camera"] == "red"
    assert "[extensão]" in r["cameras"][0]["label"]
    doc = shots.build_prompts(project, "cena01", camera="documentario")["prompts"][0]["text"]
    assert "Documentary style, handheld camera, available light, 35mm" in doc
    livre = shots.build_prompts(project, "cena01", camera="Shot on ARRI Alexa 35")["prompts"][0]["text"]
    assert "Shot on ARRI Alexa 35, 35mm" in livre


def test_aspect_ratio_comes_from_the_project_not_from_a_constant(shots, studio_env, project):
    """5.6: 16:9 é só o default `[extensão]`; o formato real é escolhido pelo destino (aula 007)."""
    assert shots.build_prompts(project, "cena01")["aspect_ratio"] == "16:9"
    root = studio_env["refs"].project_dir(project)
    meta = json.loads((root / "project.json").read_text())
    (root / "project.json").write_text(json.dumps({**meta, "aspect_ratio": "9:16"}))
    assert shots.build_prompts(project, "cena01")["aspect_ratio"] == "9:16"
    assert shots.build_prompts(project, "cena01", "edit", edits=["x"])["aspect_ratio"] == "9:16"
    shots.set_product_ref(project, image_bytes(color=(3, 3, 3)))
    assert shots.product_prompts(project)["aspect_ratio"] == "9:16"
    assert shots.list_scenes(project)["aspect_ratio"] == "9:16"


def test_generate_sends_the_project_aspect_ratio_to_the_cli(shots, studio_env, project, monkeypatch):
    root = studio_env["refs"].project_dir(project)
    meta = json.loads((root / "project.json").read_text())
    (root / "project.json").write_text(json.dumps({**meta, "aspect_ratio": "1:1"}))
    seen = []
    shots.prepare_base(project, "cena01")
    monkeypatch.setattr(shots.hf, "generate",
                        lambda model, params, **k: (seen.append(params), {"urls": [], "id": "x", "raw": {}})[1])
    shots.start_generate(project, "cena01", prompts=["p"], count=1)
    _wait(shots, project)
    assert seen[0]["aspect_ratio"] == "1:1"


def test_select_warns_when_a_frame_is_not_upscaled(shots, project):
    """5.1: a aula manda "aplicar upscale e baixar" — o Studio avisa em vez de recusar."""
    a, b = _two_candidates(shots, project)
    r = shots.select_shots(project, "cena01", [{"id": b, "upscaled": True}, {"id": a}])
    assert r["warning"] and "1 frame(s) sem upscale" in r["warning"] and "shot02" in r["warning"]
    ok = shots.select_shots(project, "cena01", [{"id": b, "upscaled": True}, {"id": a, "upscaled": True}])
    assert ok["warning"] is None


def test_list_scenes_counts_upscaled_frames_per_scene(shots, project):
    """5.1: o chip da cena mostra N/M upscalados."""
    a, b = _two_candidates(shots, project)
    shots.select_shots(project, "cena01", [{"id": b, "upscaled": True}, {"id": a}])
    cena01 = next(s for s in shots.list_scenes(project)["scenes"] if s["id"] == "cena01")
    assert cena01["selected"] == 2 and cena01["upscaled"] == 1


def test_candidates_always_report_the_upscale_state(shots, project, monkeypatch):
    """5.1: por candidato, a tela precisa saber se aquele frame já passou pelo upscale."""
    a, _b = _two_candidates(shots, project)
    assert all(c["upscaled"] is False for c in shots.list_candidates(project, "cena01")["candidates"])
    _fake_cli(monkeypatch, shots)
    shots.start_upscale(project, "cena01", a)
    _wait(shots, project)
    filhos = [c for c in shots.list_candidates(project, "cena01")["candidates"] if c["upscaled"]]
    assert len(filhos) == 1 and filhos[0]["role"] == "upscale"


def test_select_writes_the_storyboard_document(shots, studio_env, project):
    """5.4: a aula monta a ordem dos frames DENTRO do documento de storyboard, com prints."""
    root = studio_env["refs"].project_dir(project)
    a, b = _two_candidates(shots, project)
    r = shots.select_shots(project, "cena01", [{"id": b, "upscaled": True}, {"id": a}])
    assert r["storyboard_md"] == "storyboard/frames.md"
    md = (root / "storyboard" / "frames.md").read_text()
    assert "## cena01" in md and "close no astronauta andando na nevasca" in md
    assert "![base](cena01/base.png)" in md
    assert "![shot01 · upscalado](cena01/shot01_final.png)" in md
    assert "![shot02 · sem upscale](cena01/shot02_final.png)" in md
    assert "## cena05" in md and "_(nenhum frame escolhido ainda)_" in md


def test_product_scene_document_and_note_carry_lesson_013(shots, studio_env, project):
    """5.8: a cena do produto nasce depois da trilha — a etapa diz isso em vez de esconder."""
    root = studio_env["refs"].project_dir(project)
    assert "depois" in shots.PRODUCT_NOTE and "trilha" in shots.PRODUCT_NOTE
    shots.set_product_ref(project, image_bytes(color=(3, 3, 3)))
    assert "trilha" in shots.product_prompts(project)["note"]
    shots.import_upload(project, "product", [("p.png", image_bytes(color=(120, 10, 10)))])
    cid = shots.list_candidates(project, "product")["candidates"][0]["id"]
    shots.select_product(project, cid, upscaled=True)
    md = (root / "storyboard" / "frames.md").read_text()
    assert "## Cena do produto (aula 013)" in md and "trilha" in md


def test_focus_examples_come_from_the_lesson(shots, project):
    """5.5: "close no rosto, foco nos pés, foco nas mãos, plano aberto" viram exemplo na tela."""
    ex = " ".join(shots.build_prompts(project, "cena01")["focus_examples"])
    for termo in ("rosto", "pés", "mãos", "cenário"):
        assert termo in ex


# ---------- `[extensão]` preset de realismo nos prompts (FDD storyboard-geracao-por-cena §5) ----------
#: O texto de HOJE, byte a byte: o invariante do gate é que sem preset nada muda (ADR-004).
BASELINE_ANGLE = (
    "Bring me another point of view of this image. I want a close-up on energy drink. "
    "Same scene, same lighting and colors. "
    "Shot on RED Komodo 6K, 35mm, f/2.8, close shot, eye-level angle. Realistic."
)
RIG_RED = ("Shot on RED V-Raptor, Zeiss Supreme Prime, Large Format, 35-50mm, T4.0. "
           "Dominant light: clean controlled key, crisp speculars. "
           "Color grade: precise color, high micro-contrast, clean punchy look. Realistic.")


def test_preset_action_registrada_de_forma_idempotente(shots):
    """A chave entra por `setdefault`: se a frente irmã já a registrou, F07 NÃO sobrescreve."""
    from studio.common import settings
    assert shots.PRESET_ACTION == "storyboard.angles"
    assert settings.PRESET_ACTIONS[shots.PRESET_ACTION] is None
    settings.PRESET_ACTIONS[shots.PRESET_ACTION] = "red-commercial-precision"
    settings.PRESET_ACTIONS.setdefault(shots.PRESET_ACTION, None)
    assert settings.PRESET_ACTIONS[shots.PRESET_ACTION] == "red-commercial-precision"
    settings.PRESET_ACTIONS[shots.PRESET_ACTION] = None


def test_sem_preset_o_texto_do_angulo_e_byte_a_byte_o_de_hoje(shots, project):
    """Critério 9: com o preset resolvido em `None` (default de código) nada muda no prompt."""
    r = shots.build_prompts(project, "cena01")
    assert r["prompts"][0]["text"] == BASELINE_ANGLE
    assert r["preset"] is None and r["preset_source"] == "code"
    assert r["camera"] == "red"


def test_preset_explicito_substitui_o_bloco_de_camera(shots, project):
    """Decisão P1 do gate: o rig do preset ENTRA NO LUGAR do bloco manual (não soma)."""
    r = shots.build_prompts(project, "cena01", preset="red-commercial-precision")
    texto = r["prompts"][0]["text"]
    assert texto.endswith(RIG_RED)
    assert "Shot on RED Komodo 6K, 35mm" not in texto, "o bloco manual não pode coexistir com o rig"
    assert r["preset"] == "red-commercial-precision" and r["preset_source"] == "request"
    assert r["camera"] is None


def test_preset_none_na_query_desliga_o_preset(shots, project):
    """`preset=none` é o `null` explícito da query string (auto-aceite 3 do FDD)."""
    from studio.common import settings
    settings.set_project_preset(project, shots.PRESET_ACTION, "sony-venice-night")
    assert shots.build_prompts(project, "cena01")["preset"] == "sony-venice-night"
    r = shots.build_prompts(project, "cena01", preset="none")
    assert r["preset"] is None and r["preset_source"] == "request"
    assert r["prompts"][0]["text"] == BASELINE_ANGLE


def test_preset_do_projeto_e_resolvido_quando_a_query_esta_ausente(shots, project):
    from studio.common import settings
    settings.set_project_preset(project, shots.PRESET_ACTION, "arri-natural-narrative")
    r = shots.build_prompts(project, "cena01")
    assert r["preset"] == "arri-natural-narrative" and r["preset_source"] == "project"
    assert "ARRI Alexa Mini LF" in r["prompts"][0]["text"]


def test_preset_desconhecido_e_erro_de_pedido(shots, project):
    with pytest.raises(ValueError):
        shots.build_prompts(project, "cena01", preset="nao-existe")


def test_preset_nao_entra_quando_o_realismo_esta_desligado(shots, project):
    """`realism=False` continua significando "sem bloco de câmera nenhum"."""
    texto = shots.build_prompts(project, "cena01", realism=False,
                                preset="red-commercial-precision")["prompts"][0]["text"]
    assert "Shot on" not in texto


def test_preset_no_prompt_de_edicao(shots, project):
    """Na edição o bloco é opt-in: sem preset e sem `camera` o texto segue o de hoje."""
    plain = shots.build_prompts(project, "cena01", "edit", edits=["Remove the can"])
    assert plain["prompts"][0]["text"].endswith("Keep everything else identical, realistic.")
    com = shots.build_prompts(project, "cena01", "edit", edits=["Remove the can"],
                              preset="red-commercial-precision")
    assert com["prompts"][0]["text"].endswith(RIG_RED)


def test_preset_na_cena_do_produto(shots, project):
    """Contrato 5: o rig é ANEXADO ao final das duas instruções da aula 013, na mesma ordem."""
    import shutil
    root = shots.project_dir(project)
    (root / "storyboard" / "product").mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "base" / "base_final.png", root / "storyboard" / "product" / "ref.png")
    plain = shots.product_prompts(project)
    assert plain["preset"] is None and plain["preset_source"] == "code"
    assert plain["prompts"][0]["text"].endswith("Keep everything else identical, realistic.")
    com = shots.product_prompts(project, preset="red-commercial-precision")
    assert com["preset"] == "red-commercial-precision" and com["preset_source"] == "request"
    assert len(com["prompts"]) == 2
    assert all(p["text"].endswith(RIG_RED) for p in com["prompts"])
    assert com["prompts"][0]["label"] == plain["prompts"][0]["label"]


def test_image_prompt_por_cena(shots, project):
    """Critério 10: repasse defensivo — string vazia quando `scenes.json` não tem a chave."""
    import json
    root = shots.project_dir(project)
    f = root / "storyboard" / "scenes.json"
    data = json.loads(f.read_text())
    data["scenes"][0]["image_prompt"] = "A lone astronaut walking through a blizzard"
    f.write_text(json.dumps(data))
    cenas = {c["id"]: c for c in shots.list_scenes(project)["scenes"]}
    assert cenas["cena01"]["image_prompt"] == "A lone astronaut walking through a blizzard"
    assert cenas["cena02"]["image_prompt"] == ""
