"""Utilidades transversais: ingestão por etapa (imagem/vídeo/áudio), jobs e ffmpeg."""
import threading

import pytest

from tests.conftest import image_bytes, make_audio, make_video


@pytest.fixture()
def root(studio_env):
    refs = studio_env["refs"]
    return refs.project_dir(refs.create_project("Common")["id"])


def test_ingest_image_dedupes_and_thumbs(studio_env, root):
    from studio.common import ingest
    c = ingest.ingest_bytes(root, "base", image_bytes(), "upload", "a.png", "p", {"ref_id": "x"})
    assert c and c["kind"] == "image" and c["thumb"] and c["ref_id"] == "x" and c["width"] == 48
    assert (root / "base" / "candidates" / c["file"]).exists() and (root / "base" / "candidates" / c["thumb"]).exists()
    assert ingest.ingest_bytes(root, "base", image_bytes(), "upload", "b.png") is None, "mesmo conteúdo → dedupe"
    assert ingest.ingest_bytes(root, "base", b"nao-e-imagem", "upload", "c.png") is None
    assert len(ingest.load_candidates(root, "base")) == 1


def test_ingest_downloads_filters_kind_and_recency(studio_env, root, tmp_path):
    import os
    import time

    from studio.common import ingest
    dl = studio_env["tmp"] / "downloads"
    (dl / "novo.png").write_bytes(image_bytes(color=(1, 2, 3)))
    old = dl / "velho.png"
    old.write_bytes(image_bytes(color=(4, 5, 6)))
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    (dl / "clip.mp4").write_bytes(b"x")
    r = ingest.import_downloads(root, "storyboard", since_minutes=60, kind="image")
    assert r == {"added": 1, "scanned": 1, "folder": str(dl)}


@pytest.mark.skipif(not __import__("studio.common.ffmpeg", fromlist=["available"]).available(), reason="sem ffmpeg")
def test_ingest_video_and_audio(studio_env, root, tmp_path):
    from studio.common import ffmpeg as ff
    from studio.common import ingest
    v = make_video(tmp_path / "v.mp4", seconds=1)
    a = make_audio(tmp_path / "a.wav", seconds=1)
    cv = ingest.ingest_bytes(root, "animate", v.read_bytes(), "upload", "v.mp4", kind="video")
    ca = ingest.ingest_bytes(root, "music", a.read_bytes(), "upload", "a.wav", kind="audio")
    assert cv and cv["duration"] >= 0.9 and cv["width"] == 320 and cv["thumb"]
    assert ca and ca["duration"] >= 0.9 and ca["thumb"] is None
    assert ingest.ingest_bytes(root, "animate", b"nao-e-video", "upload", "x.mp4", kind="video") is None
    png = ff.last_frame(v, tmp_path / "last.png")
    assert png.exists() and ff.probe(v)["fps"] > 0


def test_job_registry_single_running_job():
    from studio.common.jobs import JobRegistry
    reg = JobRegistry()
    gate = threading.Event()

    def work(job):
        gate.wait(5)
        job["done"] = 1

    reg.start("p", 1, work)
    with pytest.raises(RuntimeError):
        reg.start("p", 1, work)
    assert reg.status("p")["state"] == "running" and reg.status("outro")["state"] == "idle"
    gate.set()
    for _ in range(50):
        if reg.status("p")["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert reg.status("p") == {**reg.status("p"), "state": "done", "done": 1}

    def boom(job):
        raise ValueError("x")

    reg.start("q", 1, boom)
    for _ in range(50):
        if reg.status("q")["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert reg.status("q")["state"] == "error" and "ValueError" in reg.status("q")["error"]


def test_higgsfield_history_media_by_kind(monkeypatch):
    import json

    from studio import higgsfield as hf
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    payload = {"items": [{"id": "j1", "results": [{"url": "https://c/x.mp4"}, {"url": "https://c/y.png"}]}]}
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (0, json.dumps(payload), ""))
    assert hf.history_media("video")[0]["urls"] == ["https://c/x.mp4"]
    assert hf.history_media("image")[0]["urls"] == ["https://c/y.png"]
    with pytest.raises(ValueError):
        hf.history_media("3d")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (0, json.dumps({"id": "g", "video_url": "https://c/out.mp4"}), ""))
    assert hf.generate("kling3_0", {"prompt": "p"})["urls"] == ["https://c/out.mp4"]


# ---------- escrita atômica (AP-22) ----------
def _tmps(d):
    return [p.name for p in d.iterdir() if p.name.endswith(".tmp")]


def test_atomic_write_helpers_grava_conteudo_e_nao_deixa_tmp(tmp_path):
    import json

    from studio.common import atomic
    alvo = tmp_path / "sub" / "a.json"
    atomic.write_json_atomic(alvo, {"vibe": "café à noite"}, ensure_ascii=False, indent=1)
    assert json.loads(alvo.read_text()) == {"vibe": "café à noite"}
    assert alvo.read_text() == '{\n "vibe": "café à noite"\n}', "formato do arquivo preservado"
    atomic.write_text_atomic(alvo.with_name("b.txt"), "linha\n")
    atomic.write_bytes_atomic(alvo.with_name("c.bin"), b"\x00\x01", fsync=True)
    assert alvo.with_name("b.txt").read_text() == "linha\n" and alvo.with_name("c.bin").read_bytes() == b"\x00\x01"
    assert atomic.write_json_atomic(alvo, [1], newline=True) == alvo and alvo.read_text() == "[1]\n"
    assert _tmps(alvo.parent) == [], "nenhum temporário sobrando"


def test_atomic_write_falha_preserva_destino_e_nao_deixa_lixo(tmp_path):
    from studio.common import atomic
    alvo = tmp_path / "a.json"
    atomic.write_text_atomic(alvo, "bom")

    with pytest.raises(TypeError):                   # falha DEPOIS de abrir o temporário
        atomic.write_bytes_atomic(alvo, "não é bytes")
    with pytest.raises(RuntimeError):
        with atomic.atomic_path(alvo) as tmp:
            tmp.write_text("meio")
            raise RuntimeError("boom")
    assert alvo.read_text() == "bom", "o arquivo bom continua de pé"
    assert _tmps(tmp_path) == [], "temporário removido na falha"


def test_atomic_write_concorrente_nao_estoura(tmp_path):
    """Com temporário de nome fixo, uma das threads estourava FileNotFoundError no os.replace."""
    from studio.common import atomic
    alvo = tmp_path / "project.json"
    largada, erros = threading.Barrier(3), []

    def grava(n):
        largada.wait(5)
        for i in range(40):
            try:
                atomic.write_json_atomic(alvo, {"t": n, "i": i}, ensure_ascii=False, indent=1)
            except Exception as e:  # noqa: BLE001 — o teste é justamente "não pode levantar"
                erros.append(f"{type(e).__name__}: {e}")

    ts = [threading.Thread(target=grava, args=(n,)) for n in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(20)
    import json
    assert erros == []
    assert json.loads(alvo.read_text())["i"] == 39, "sempre um JSON íntegro de UMA das escritas"
    assert _tmps(tmp_path) == []


def test_project_lock_reentrante_e_por_raiz(tmp_path):
    from studio.common import atomic
    with atomic.project_lock(tmp_path):
        with atomic.project_lock(tmp_path):          # reentrante: não trava o próprio fluxo
            pass
    ordem, solto = [], threading.Event()

    def segura():
        with atomic.project_lock(tmp_path / "a"):
            ordem.append("entrou")
            solto.wait(5)
            ordem.append("saiu")

    t = threading.Thread(target=segura)
    t.start()
    for _ in range(50):
        if ordem:
            break
        threading.Event().wait(0.05)
    with atomic.project_lock(tmp_path / "b"):        # outra raiz não espera
        ordem.append("outra-raiz")
    solto.set()
    t.join(10)
    assert ordem == ["entrou", "outra-raiz", "saiu"]
