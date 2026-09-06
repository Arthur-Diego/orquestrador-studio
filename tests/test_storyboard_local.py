"""`[extensão]` Motor de imagem LOCAL na etapa 4 (ADR-033) — contrato HTTP + ponte, com fakes.

Sem rede, sem subprocess, sem ComfyUI: o CLI `engine` e o cliente do ComfyUI são injetados/fakeados.
Cobre geração local de keyframes, inpaint real por máscara, o gate de saúde (409) e a validação (422),
e prova que o caminho pago (Higgsfield) não é tocado.
"""
import time
import types
from types import SimpleNamespace

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy", "vibe": "snow"}).json()["id"]


@pytest.fixture()
def root(studio_env, pid):
    return studio_env["refs"].project_dir(pid)


@pytest.fixture()
def le(studio_env):
    """Módulo da ponte já recarregado no ambiente isolado (o mesmo que `storyboard.local` importou)."""
    import studio.localengine as le
    return le


def _ready(le, monkeypatch, ready=True):
    monkeypatch.setattr(le, "status", lambda refresh=False: {
        "engine_installed": ready, "comfy_up": ready, "ready": ready,
        "detail": "" if ready else "suba o ComfyUI local (porta 8188)",
        "gen_models": le.GEN_MODELS, "inpaint_models": le.INPAINT_MODELS})


def _wait(client, pid, timeout=5.0):
    url = f"/api/projects/{pid}/storyboard/local/job"
    end = time.time() + timeout
    j = client.get(url).json()
    while j.get("state") == "running" and time.time() < end:
        time.sleep(0.03)
        j = client.get(url).json()
    return j


def _candidates(root):
    import json
    p = root / "storyboard" / "candidates.json"
    return json.loads(p.read_text()) if p.exists() else []


def _seed_idea(client, pid) -> str:
    """Sobe uma imagem como candidato e devolve o id (fonte para o inpaint)."""
    r = client.post(f"/api/projects/{pid}/storyboard/import/upload",
                    files={"files": ("idea.png", image_bytes(), "image/png")})
    assert r.status_code == 200
    return client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["id"]


# ---------- status / gate ----------
def test_local_status_reflects_readiness(client, pid, le, monkeypatch):
    _ready(le, monkeypatch, ready=False)
    r = client.get(f"/api/projects/{pid}/storyboard/local/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is False and body["detail"]
    assert {m["id"] for m in body["gen_models"]} == {"flux-schnell", "flux-dev"}
    assert {m["id"] for m in body["inpaint_models"]} == {"flux-dev", "flux-schnell"}


def test_local_status_404_for_unknown_project(client):
    assert client.get("/api/projects/nope/storyboard/local/status").status_code == 404


# ---------- geração local de keyframes ----------
def test_local_generate_ingests_candidates(client, pid, root, le, monkeypatch):
    _ready(le, monkeypatch)
    calls = []

    def fake_gen(prompt, *, model, steps=None, seed=None, preset=None, runner=None):
        calls.append({"prompt": prompt, "model": model, "seed": seed})
        return image_bytes(color=(10, 20, 30 + len(calls)))

    monkeypatch.setattr(le, "generate_image", fake_gen)
    r = client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    json={"prompt": "a red fox", "count": 4, "model": "flux-schnell"})
    assert r.status_code == 200 and r.json()["mode"] == "generate"
    job = _wait(client, pid)
    assert job["state"] == "done" and job["added"] == 4
    assert len(calls) == 4 and calls[0]["model"] == "flux-schnell"
    cands = _candidates(root)
    locais = [c for c in cands if c.get("source") == "local"]
    assert len(locais) == 4
    assert all(c["local_kind"] == "keyframe_local" and c["kind"] == "image" for c in locais)
    # aparecem na galeria de ideias (não são anotação)
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    assert len(ideas) == 4


def test_local_generate_offline_is_409(client, pid, le, monkeypatch):
    _ready(le, monkeypatch, ready=False)
    r = client.post(f"/api/projects/{pid}/storyboard/local/generate", json={"prompt": "x"})
    assert r.status_code == 409


def test_local_generate_validation(client, pid, le, monkeypatch):
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes())
    assert client.post(f"/api/projects/{pid}/storyboard/local/generate", json={"prompt": "  "}).status_code == 422
    assert client.post(f"/api/projects/{pid}/storyboard/local/generate",
                       json={"prompt": "ok", "count": 3}).status_code == 422
    assert client.post(f"/api/projects/{pid}/storyboard/local/generate",
                       json={"prompt": "ok", "model": "sdxl"}).status_code == 422


# ---------- inpaint real por máscara ----------
def test_local_inpaint_on_idea(client, pid, root, le, monkeypatch):
    _ready(le, monkeypatch)
    seen = {}

    def fake_inpaint(base, mask, instruction, *, model="flux-dev", **kw):
        seen.update(base=base, mask=mask, instruction=instruction, model=model, kw=kw)
        return image_bytes(color=(90, 10, 10))

    monkeypatch.setattr(le, "inpaint", fake_inpaint)
    sid = _seed_idea(client, pid)
    r = client.post(
        f"/api/projects/{pid}/storyboard/local/inpaint",
        data={"instruction": "remove the book", "source_id": sid, "model": "flux-dev"},
        files={"mask": ("mask.png", image_bytes(color=(255, 255, 255)), "image/png")},
    )
    assert r.status_code == 200 and r.json()["mode"] == "inpaint"
    job = _wait(client, pid)
    assert job["state"] == "done" and job["added"] == 1
    assert seen["instruction"] == "remove the book" and seen["model"] == "flux-dev"
    inp = [c for c in _candidates(root) if c.get("local_kind") == "inpaint_local"]
    assert len(inp) == 1 and inp[0]["parent"] == sid and inp[0]["source"] == "local"
    # o job aponta o candidato gerado (antes/depois da UI)
    assert job["result"] == f"storyboard/candidates/{inp[0]['file']}" and job["result_id"] == inp[0]["id"]


def test_local_inpaint_on_base_when_no_source(client, pid, root, le, monkeypatch):
    _ready(le, monkeypatch)
    make_image(root / "base" / "base_final.png")
    monkeypatch.setattr(le, "inpaint", lambda *a, **k: image_bytes(color=(1, 2, 3)))
    r = client.post(
        f"/api/projects/{pid}/storyboard/local/inpaint",
        data={"instruction": "add snow"},
        files={"mask": ("m.png", image_bytes(color=(255, 255, 255)), "image/png")},
    )
    assert r.status_code == 200
    assert _wait(client, pid)["state"] == "done"
    inp = [c for c in _candidates(root) if c.get("local_kind") == "inpaint_local"]
    assert inp and inp[0]["parent"] == "base"


def test_local_inpaint_validation(client, pid, root, le, monkeypatch):
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "inpaint", lambda *a, **k: image_bytes())
    mask = {"mask": ("m.png", image_bytes(color=(255, 255, 255)), "image/png")}
    # instrução vazia
    assert client.post(f"/api/projects/{pid}/storyboard/local/inpaint",
                       data={"instruction": " "}, files=mask).status_code == 422
    # fonte inexistente
    assert client.post(f"/api/projects/{pid}/storyboard/local/inpaint",
                       data={"instruction": "x", "source_id": "zzz"}, files=mask).status_code == 422
    # máscara inválida (não é imagem)
    assert client.post(f"/api/projects/{pid}/storyboard/local/inpaint",
                       data={"instruction": "x"},
                       files={"mask": ("m.png", b"not an image", "image/png")}).status_code == 422
    # sem base e sem source → 409 (precondição)
    assert client.post(f"/api/projects/{pid}/storyboard/local/inpaint",
                       data={"instruction": "x"}, files=mask).status_code == 409


def test_local_inpaint_offline_is_409(client, pid, le, monkeypatch):
    _ready(le, monkeypatch, ready=False)
    r = client.post(f"/api/projects/{pid}/storyboard/local/inpaint",
                    data={"instruction": "x"},
                    files={"mask": ("m.png", image_bytes(color=(255, 255, 255)), "image/png")})
    assert r.status_code == 409


# ---------- a ponte (localengine) em isolamento ----------
def test_inpaint_graph_has_real_mask_nodes(le):
    g = le.inpaint_graph("base.png", "mask.png", "remove x", "flux-dev", 20, 3.5, 1.0)
    kinds = {n["class_type"] for n in g.values()}
    assert {"InpaintModelConditioning", "ImageToMask", "FluxGuidance", "UnetLoaderGGUF"} <= kinds
    # a máscara (ImageToMask, canal red) alimenta o InpaintModelConditioning
    imgtomask = next(k for k, n in g.items() if n["class_type"] == "ImageToMask")
    assert g[imgtomask]["inputs"]["channel"] == "red"
    inpaint_node = next(n for n in g.values() if n["class_type"] == "InpaintModelConditioning")
    assert inpaint_node["inputs"]["mask"] == [imgtomask, 0]
    assert inpaint_node["inputs"]["noise_mask"] is True
    # modelo dev usa o UNET dev
    assert g["10"]["inputs"]["unet_name"] == "flux1-dev-Q5_K_S.gguf"


def test_inpaint_uses_fake_comfy_client(le):
    class FakeClient:
        def __init__(self):
            self.uploaded = []
            self.graph = None

        def upload_image(self, name, data):
            self.uploaded.append((name, data))
            return name

        def queue(self, graph):
            self.graph = graph
            return "pid-1"

        def wait(self, prompt_id, timeout=None):
            return {"9": {"images": [{"filename": "out.png", "type": "output"}]}}

        def view(self, filename, subfolder="", type="output"):
            return b"RESULT-BYTES"

    fc = FakeClient()
    out = le.inpaint(b"BASE", b"MASK", "remove", model="flux-schnell", client=fc)
    assert out == b"RESULT-BYTES"
    assert len(fc.uploaded) == 2 and fc.uploaded[0][1] == b"BASE" and fc.uploaded[1][1] == b"MASK"
    assert any(n["class_type"] == "InpaintModelConditioning" for n in fc.graph.values())
    assert fc.graph["10"]["inputs"]["unet_name"] == "flux1-schnell-Q5_K_S.gguf"


def test_generate_image_reads_last_png_path(le, tmp_path):
    png = tmp_path / "out.png"
    png.write_bytes(image_bytes())

    def fake_runner(args, capture_output=True, text=True, timeout=None):
        assert args[1] == "image" and "--model" in args
        return SimpleNamespace(stdout=f"loading...\n{png}\n", stderr="")

    out = le.generate_image("a fox", model="flux-schnell", runner=fake_runner)
    assert out == image_bytes()


def test_generate_image_unknown_model_raises(le):
    with pytest.raises(le.EngineUnavailable):
        le.generate_image("x", model="sdxl")


def test_require_raises_when_offline(le, monkeypatch):
    monkeypatch.setattr(le, "_engine_installed", lambda: False)
    monkeypatch.setattr(le, "_comfy_up", lambda timeout=3: False)
    with pytest.raises(le.EngineUnavailable):
        le.require()


# ---------- o caminho pago não é afetado ----------
def test_paid_higgsfield_kinds_untouched(client, pid, root):
    make_image(root / "base" / "base_final.png")
    presets = client.get(f"/api/projects/{pid}/storyboard/instructions").json()
    assert len(presets["kinds"]) == 4  # edit_area legado permanece
    assert {k["kind"] for k in presets["kinds"]} == {"draw_to_edit", "edit", "multishot", "edit_area"}


def test_module_shape(le):
    assert isinstance(le.GEN_MODELS, list) and isinstance(le.INPAINT_MODELS, list)
    assert callable(le.status) and callable(le.require)
    assert isinstance(le.inpaint, types.FunctionType)


# ---------- `[extensão]` geração POR CENA (FDD storyboard-geracao-por-cena, contratos 1 e 2) ----------
def _seed_scenes(root):
    import json
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps(
        {"scenes": [{"id": "cena01", "n": 1, "text": "close no astronauta",
                     "image_prompt": "A lone astronaut walking through a blizzard"},
                    {"id": "cena02", "n": 2, "text": "a lata na neve"}]}))


def _scene_candidates(root, scene):
    import json
    p = root / "storyboard" / scene / "candidates.json"
    return json.loads(p.read_text()) if p.exists() else []


def test_local_generate_com_scene_ingere_na_pasta_da_cena(client, pid, root, le, monkeypatch):
    """Critério 1: com `scene`, TODO byte gerado vai para `storyboard/cenaNN/candidates/`."""
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes(color=(7, 8, 9)))
    _seed_scenes(root)
    r = client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    json={"prompt": "a lone astronaut", "count": 1, "scene": "cena01"})
    assert r.status_code == 200 and r.json()["scene"] == "cena01"
    job = _wait(client, pid)
    assert job["state"] == "done" and job["added"] == 1
    # o candidato está na pasta da CENA, e não na galeria de ideação
    da_cena = _scene_candidates(root, "cena01")
    assert len(da_cena) == 1 and da_cena[0]["source"] == "local"
    assert da_cena[0]["local_kind"] == "keyframe_local" and da_cena[0]["scene"] == "cena01"
    assert _candidates(root) == []
    assert (root / "storyboard" / "cena01" / "candidates" / da_cena[0]["file"]).exists()
    # e aparece na galeria da cena (rota dos ângulos)
    vistos = client.get(f"/api/projects/{pid}/storyboard/angles/scenes/cena01/candidates").json()
    assert [c["id"] for c in vistos["candidates"]] == [da_cena[0]["id"]]
    assert vistos["candidates"][0]["file"].startswith("storyboard/cena01/candidates/")


def test_local_generate_sem_scene_continua_na_ideacao(client, pid, root, le, monkeypatch):
    """Critério 1 (metade 2): sem `scene`, o destino é o de hoje (`storyboard/candidates/`)."""
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes(color=(3, 4, 5)))
    _seed_scenes(root)
    client.post(f"/api/projects/{pid}/storyboard/local/generate", json={"prompt": "x", "count": 1})
    assert _wait(client, pid)["state"] == "done"
    assert len(_candidates(root)) == 1
    assert _scene_candidates(root, "cena01") == []
    # o job de ideação segue com `scene: null` (contrato 2)
    assert client.get(f"/api/projects/{pid}/storyboard/local/job").json()["scene"] is None


def test_local_generate_scene_product(client, pid, root, le, monkeypatch):
    """Critério 14: a cena do produto (aula 013) também gera local, sem exigir `ref.png`."""
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes(color=(6, 6, 6)))
    _seed_scenes(root)
    r = client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    json={"prompt": "the can", "count": 1, "scene": "product"})
    assert r.status_code == 200
    assert _wait(client, pid)["state"] == "done"
    assert len(_scene_candidates(root, "product")) == 1


def test_local_generate_scene_invalida_nao_toca_o_motor(client, pid, root, le, monkeypatch):
    """Critério 2: 422 fora do regex, 404 para cena ausente do `scenes.json` — sem chamar o motor."""
    _ready(le, monkeypatch)
    chamou = []
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: chamou.append(1) or image_bytes())
    _seed_scenes(root)
    url = f"/api/projects/{pid}/storyboard/local/generate"
    assert client.post(url, json={"prompt": "x", "scene": "../etc"}).status_code == 422
    assert client.post(url, json={"prompt": "x", "scene": "cena9"}).status_code == 422
    assert client.post(url, json={"prompt": "x", "scene": "cena09"}).status_code == 404
    assert chamou == []


def test_local_generate_scene_sem_scenes_json_e_409(client, pid, le, monkeypatch):
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes())
    r = client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    json={"prompt": "x", "scene": "cena01"})
    assert r.status_code == 409 and "etapa 4" in r.json()["detail"]


def test_local_job_expoe_a_cena_do_job(client, pid, root, le, monkeypatch):
    """Critério 3: o job local carrega `scene` durante e depois da corrida."""
    _ready(le, monkeypatch)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes(color=(2, 2, 2)))
    _seed_scenes(root)
    client.post(f"/api/projects/{pid}/storyboard/local/generate",
                json={"prompt": "x", "count": 1, "scene": "cena02"})
    assert _wait(client, pid)["scene"] == "cena02"


def test_local_generate_por_cena_nao_cria_registro_de_job(client, pid, root, le, monkeypatch):
    """Critério 15 / ADR-006: um job por projeto — a 2ª cena em paralelo recebe 409."""
    import threading
    _ready(le, monkeypatch)
    _seed_scenes(root)
    solta = threading.Event()
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: (solta.wait(3), image_bytes())[1])
    url = f"/api/projects/{pid}/storyboard/local/generate"
    assert client.post(url, json={"prompt": "x", "count": 1, "scene": "cena01"}).status_code == 200
    try:
        assert client.post(url, json={"prompt": "y", "count": 1, "scene": "cena02"}).status_code == 409
    finally:
        solta.set()
    _wait(client, pid)
