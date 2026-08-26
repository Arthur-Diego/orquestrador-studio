"""Etapa 2 — o mood board segue a aula 009: UMA vibe encontrada, grid de 4, teto de 8.

Fidelidade (auditoria da wave 2, §2): o mood da aula **tem** o produto; "sem pessoas" é sugestão
do usuário, não injeção silenciosa; a referência de estilo do CLI são as imagens de vibe.
"""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def project(studio_env):
    refs = studio_env["refs"]
    meta = refs.create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


def test_mood_prompt_is_single_vibe_and_does_not_forbid_the_product(studio_env, project):
    """M1 (teste invertido): a aula não proíbe produto/texto/logo no mood — só sugere "sem pessoas"."""
    mood = studio_env["mood"]
    r = mood.suggest_prompts(project)
    assert len(r["prompts"]) == 1, "aula 009: um prompt de vibe, gerado em grid de 4"
    text = r["prompts"][0]["text"].lower()
    assert "no product" not in text and "no logos" not in text and "no text" not in text
    assert "no people" in text, "sugestão da aula, marcada por padrão"
    assert "snow neon" in text and "energy drink" in text
    assert r["aspect_ratio"] == "16:9" and r["no_people"] is True

    sem_regra = mood.suggest_prompts(project, no_people=False)["prompts"][0]["text"].lower()
    assert "no people" not in sem_regra, "desmarcado, nada é injetado"


def test_mood_prompt_hint_is_honest_about_studio_choices(studio_env, project):
    """M10/G10/G8: 2K/16:9 é sugestão do Studio; o plano chama-se Ultimate; estilização no meio-termo."""
    hint = studio_env["mood"].suggest_prompts(project)["ui_hint"]
    assert "sugestão" in hint and "Ultimate" in hint and "Ultra ·" not in hint
    assert "meio-termo" in hint


def test_mood_prompt_can_start_from_the_explore_prompt(studio_env, project):
    """M3: o prompt copiado do Explore é a base; só a estilização é acrescentada."""
    mood = studio_env["mood"]
    r = mood.suggest_prompts(project, variation=1, explore_prompt="Neon snowfield at dusk")
    text = r["prompts"][0]["text"]
    assert text.startswith("Neon snowfield at dusk.") and "stronger stylization" in text
    assert r["explore_prompt"] == "Neon snowfield at dusk"


def test_mood_prompt_variations_change_only_style(studio_env, project):
    mood = studio_env["mood"]
    a = mood.suggest_prompts(project, variation=0)["prompts"][0]["text"]
    b = mood.suggest_prompts(project, variation=1)["prompts"][0]["text"]
    assert a != b
    assert a.split("Wide establishing")[0] == b.split("Wide establishing")[0], "a vibe (parte inicial) não muda"


def test_mood_prompt_does_not_carry_the_pinterest_terms(studio_env, project):
    """M4: a vibe é escolhida pelo sentimento — os termos da etapa 1 ficam para a etapa 3."""
    from studio.refs import pinterest
    from studio.refs import service as refs
    mood = studio_env["mood"]
    cdir = refs.project_dir(project) / "refs" / "candidates"
    make_image(cdir / "a.jpg")
    pinterest.save_candidates(cdir, [pinterest.Candidate(id="a", source="pinterest", term="energy drink snow ads",
                                                         url="u", pin_url=None, alt="Salvar Pins", file="a.jpg",
                                                         thumb="thumbs/a.jpg", selected=True)])
    text = mood.suggest_prompts(project)["prompts"][0]["text"]
    assert "Salvar Pins" not in text and "energy drink snow ads" not in text
    assert mood.refs_terms(project) == ["energy drink snow ads"], "os termos seguem disponíveis"


def test_import_downloads_only_recent_images(studio_env, project):
    import os
    import time
    mood = studio_env["mood"]
    dl = studio_env["tmp"] / "downloads"
    make_image(dl / "novo.jpg")
    old = make_image(dl / "velho.jpg", color=(1, 2, 3))
    os.utime(old, (time.time() - 3 * 3600, time.time() - 3 * 3600))
    (dl / "nao-imagem.txt").write_text("x")
    r = mood.import_downloads(project, since_minutes=60)
    assert r["added"] == 1 and r["scanned"] == 1
    assert mood.load(project)[0]["source"] == "downloads"


def test_import_upload_dedupes_by_content(studio_env, project):
    mood = studio_env["mood"]
    data = image_bytes()
    assert mood.import_upload(project, [("a.png", data), ("b.png", data)])["added"] == 1
    assert mood.import_upload(project, [("c.png", image_bytes(color=(1, 200, 1)))])["added"] == 1
    assert len(mood.load(project)) == 2


def test_select_writes_palette_and_md_and_caps_at_eight(studio_env, project):
    mood = studio_env["mood"]
    mood.import_upload(project, [(f"{i}.png", image_bytes(color=(10 * i, 100, 200))) for i in range(10)])
    ids = [c["id"] for c in mood.load(project)]
    r = mood.select(project, ids[:3], note="neve, neon, silêncio")
    assert r["selected"] == 3 and len(r["palette"]) >= 1 and all(c.startswith("#") for c in r["palette"])
    root = studio_env["refs"].project_dir(project)
    assert len(list((root / "mood" / "selected").iterdir())) == 3
    pal = json.loads((root / "mood" / "palette.json").read_text())
    assert pal["note"] == "neve, neon, silêncio"
    assert len(pal["by_file"]) == 3, "paleta por imagem alimenta a validação 'mesmo mood' do guia"
    md = (root / "mood" / "mood.md").read_text()
    assert "Mood board" in md
    assert "[extensão]" in md, "M5: a paleta é derivado técnico do Studio, não da aula"
    with pytest.raises(ValueError):
        mood.select(project, ids[:9])


def test_select_records_the_vibe_in_the_project(studio_env, project):
    """G2: a aula encontra a vibe na etapa 2 — é aqui que ela é gravada no projeto."""
    mood = studio_env["mood"]
    refs = studio_env["refs"]
    mood.import_upload(project, [("a.png", image_bytes())])
    ids = [c["id"] for c in mood.load(project)]
    r = mood.select(project, ids, note="neve, neon, silêncio")
    assert r["vibe"] == "neve, neon, silêncio"
    meta = json.loads((refs.project_dir(project) / "project.json").read_text())
    assert meta["vibe"] == "neve, neon, silêncio"
    assert meta["product"] == "energy drink", "os outros campos ficam intactos"
    mood.select(project, ids)   # sem note: não apaga a vibe já encontrada
    assert json.loads((refs.project_dir(project) / "project.json").read_text())["vibe"] == "neve, neon, silêncio"


def test_style_references_are_the_vibe_images_not_the_pinterest_refs(studio_env, project):
    """M2: 1ª rodada = imagem de vibe; 2ª rodada = a melhor do grid como referência de estilo."""
    mood = studio_env["mood"]
    root = studio_env["refs"].project_dir(project)
    make_image(root / "refs" / "brainstorming" / "pin.jpg")
    mood.vibe_import_upload(project, [("v1.png", image_bytes(color=(0, 90, 200))),
                                      ("v2.png", image_bytes(color=(9, 9, 9)))])
    vids = [c["id"] for c in mood.vibe_images(project)]
    mood.import_upload(project, [("grid.png", image_bytes(color=(200, 10, 10)))])
    best = mood.load(project)[0]["id"]

    todas = mood.style_reference_files(project)
    assert len(todas) == 2 and all("mood/vibe/candidates" in f for f in todas)
    assert not any("brainstorming" in f for f in todas), "as referências do Pinterest não vão ao CLI"

    uma = mood.style_reference_files(project, [vids[0]])
    assert len(uma) == 1

    segunda_rodada = mood.style_reference_files(project, [vids[0]], best)
    assert len(segunda_rodada) == 2 and segunda_rodada[-1].endswith(".png")
    assert "mood/candidates" in segunda_rodada[-1]

    with pytest.raises(ValueError):
        mood.style_reference_files(project, [vids[0]], "nao-existe")


def test_select_over_cap_keeps_previous_selection(studio_env, project):
    mood = studio_env["mood"]
    mood.import_upload(project, [(f"{i}.png", image_bytes(color=(20 * i, 50, 90))) for i in range(10)])
    ids = [c["id"] for c in mood.load(project)]
    mood.select(project, ids[:2])
    with pytest.raises(ValueError):
        mood.select(project, ids[:9])
    root = studio_env["refs"].project_dir(project)
    assert len(list((root / "mood" / "selected").iterdir())) == 2, "seleção válida anterior não pode ser destruída"
    assert sum(c["selected"] for c in mood.load(project)) == 2


def test_start_generate_refuses_concurrent_job(studio_env, project, monkeypatch):
    import threading
    mood = studio_env["mood"]
    gate = threading.Event()
    monkeypatch.setattr(mood.hf, "generate", lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    mood.start_generate(project, "nano_banana_2", ["p"])
    with pytest.raises(RuntimeError):
        mood.start_generate(project, "nano_banana_2", ["p"])
    gate.set()
    for _ in range(50):
        if mood.job_status(project)["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert mood.job_status(project)["state"] == "done"


def test_generate_prompt_modes_and_history(studio_env, project, monkeypatch):
    mood = studio_env["mood"]
    from studio.common import prompter
    # template não precisa de Claude
    t = mood.generate_prompt(project, "template", variation=2)
    assert t["source"] == "template" and t["mode"] == "template" and "No product" not in t["prompt"]
    # sem Claude, brief/images → RuntimeError (409 na API)
    monkeypatch.setattr(prompter, "BIN", None)
    with pytest.raises(RuntimeError):
        mood.generate_prompt(project, "brief")
    # com Claude fakeado: imagens de vibe + instrução
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    mood.vibe_import_upload(project, [("v1.png", image_bytes(color=(0, 90, 200)))])
    vid = mood.vibe_images(project)[0]["id"]
    seen = {}
    def fake_from_images(kind, images, instruction="", brief=None):
        seen.update(kind=kind, images=[str(p) for p in images], instruction=instruction, brief=brief)
        return {"prompt": "Cold neon snowfield", "negative": "text", "camera": "RED 35mm", "notes_pt": "n", "source": "claude", "seconds": 1.0}
    monkeypatch.setattr(prompter, "from_images", fake_from_images)
    r = mood.generate_prompt(project, "images", "bastante neon", [vid])
    assert seen["kind"] == "mood" and seen["images"][0].endswith(".png") and seen["instruction"] == "bastante neon"
    assert seen["brief"]["product"] == "energy drink" and r["images"] == [vid]
    assert "No people" in r["prompt"] and "No product" not in r["prompt"], "M1"
    assert "hints" not in seen["brief"], "M4: o brief do mood não carrega os termos do Pinterest"
    with pytest.raises(ValueError):
        mood.generate_prompt(project, "images", "x", [])
    with pytest.raises(ValueError):
        mood.generate_prompt(project, "images", "x", ["nao-existe"])
    hist = mood.prompt_history(project)
    assert [h["mode"] for h in hist] == ["images", "template"]


def test_candidates_expose_the_import_batch_for_the_tile_legend(studio_env, project):
    """Wave 4 (2.36): a legenda do tile é "<lote> · img N" — `batch`/`batch_index` derivados.

    O lote não é estado novo: sai do `job_id` do CLI ou do minuto da importação (um grid inteiro
    entra de uma vez). Só o `GET /mood/candidates` anota; `load()` segue devolvendo o arquivo cru.
    """
    mood = studio_env["mood"]
    mood.import_upload(project, [(f"g{i}.png", image_bytes(color=(i * 20, 30, 40))) for i in range(4)])
    lote1 = mood.candidates(project)
    assert [c["batch"] for c in lote1] == ["grid_01"] * 4
    assert [c["batch_index"] for c in lote1] == [1, 2, 3, 4]
    assert all("batch" not in c for c in mood.load(project)), "o derivado não é gravado no disco"

    root = studio_env["refs"].project_dir(project)
    cru = json.loads((root / "mood" / "candidates.json").read_text())
    for c in cru[2:]:                                     # simula um segundo grid (outro job do CLI)
        c["job_id"] = "job-2"
    (root / "mood" / "candidates.json").write_text(json.dumps(cru, ensure_ascii=False))

    lote2 = mood.candidates(project)
    assert [c["batch"] for c in lote2] == ["grid_01", "grid_01", "grid_02", "grid_02"]
    assert [c["batch_index"] for c in lote2] == [1, 2, 1, 2]
