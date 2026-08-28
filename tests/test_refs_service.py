"""Etapa 1 — projetos, termos de busca e seleção de referências (sem tocar na rede)."""
import json
import time

import pytest

from tests.conftest import make_image


def test_create_project_builds_course_tree(studio_env):
    refs = studio_env["refs"]
    meta = refs.create_project("Gelo Zero", "energy drink", "snow neon")
    root = refs.project_dir(meta["id"])
    assert meta["id"].endswith("-gelo-zero")
    for sub in ("refs/candidates/thumbs", "refs/brainstorming", "mood", "videos"):
        assert (root / sub).is_dir()
    assert json.loads((root / "project.json").read_text())["product"] == "energy drink"


def test_create_project_rejects_duplicate(studio_env):
    refs = studio_env["refs"]
    refs.create_project("Dup")
    with pytest.raises(ValueError):
        refs.create_project("Dup")


def test_suggest_terms_are_english_and_include_vibe(studio_env):
    refs = studio_env["refs"]
    terms = refs.suggest_terms("energy drink", "snow neon")
    assert "energy drink ad campaign" in terms
    assert any("snow neon" in t for t in terms)
    assert all(t == t.strip() and t for t in terms)


def test_suggest_terms_start_from_the_validated_brand(studio_env):
    """R1 — aula 009: "uma marca conhecida de alguma coisa que já tá validada […] Red Bull"."""
    refs = studio_env["refs"]
    terms = refs.suggest_terms("energy drink", "snow neon", "Red Bull")
    assert terms[0] == "Red Bull ads", "a marca validada vem primeiro"
    assert "Red Bull snow neon ads" in terms, "e depois refina pela situação"
    assert "energy drink ad campaign" in terms, "os termos por produto seguem como complemento"
    assert len(terms) == len(set(terms)), "sem termos repetidos"
    assert refs.suggest_terms("soda") == refs.suggest_terms("soda", "", ""), "sem marca, nada muda"


def test_validated_brand_persists_in_the_refs_domain(studio_env):
    """ADR-020 `[extensão]`: a marca validada persiste em `refs/validated_brand.json`."""
    refs = studio_env["refs"]
    meta = refs.create_project("Marca Val", "energy drink", "snow neon")
    pid = meta["id"]
    assert refs.get_validated_brand(pid) == "", "projeto novo não tem marca validada"

    assert refs.set_validated_brand(pid, "  Red Bull  ") == {"brand": "Red Bull"}, "grava aparado"
    path = refs.project_dir(pid) / "refs" / "validated_brand.json"
    assert json.loads(path.read_text()) == {"brand": "Red Bull"}
    assert refs.get_validated_brand(pid) == "Red Bull"

    # não colide com o `brand` do project.json (marca do produto) — arquivo separado no domínio refs
    assert "brand" not in json.loads((refs.project_dir(pid) / "project.json").read_text())

    assert refs.set_validated_brand(pid, "") == {"brand": ""}, "texto vazio limpa"
    assert refs.get_validated_brand(pid) == ""


def test_suggest_terms_from_validated_brand_are_richer_and_only_from_it(studio_env):
    """ADR-020 `[extensão]`: com marca validada, ≥12 termos, todos dela, sem product/vibe."""
    refs = studio_env["refs"]
    terms = refs.suggest_terms("energy drink", "snow neon", "", validated_brand="Red Bull")
    assert len(terms) >= 12, "gerador expandido: alvo ≥12 termos"
    assert len(terms) == len(set(terms)), "sem termos repetidos"
    assert all(t.startswith("Red Bull ") for t in terms), "todos derivados só da marca validada"
    assert not any("energy drink" in t or "snow neon" in t for t in terms), "não mistura product/vibe"

    # sem marca validada persistida, o comportamento atual (product/vibe/brand) é preservado
    assert refs.suggest_terms("energy drink", "snow neon") == \
        refs.suggest_terms("energy drink", "snow neon", "", validated_brand="")


def test_select_copies_to_brainstorming_and_writes_readme(studio_env):
    refs = studio_env["refs"]
    from studio.refs import pinterest
    meta = refs.create_project("Sel")
    root = refs.project_dir(meta["id"])
    cdir = root / "refs" / "candidates"
    cands = []
    for i, cid in enumerate(("aaa111", "bbb222", "ccc333")):
        make_image(cdir / f"{cid}.jpg")
        cands.append(pinterest.Candidate(id=cid, source="pinterest", term=f"term {i}", url=f"https://x/{cid}.jpg",
                                         pin_url=None, alt="", file=f"{cid}.jpg", thumb=f"thumbs/{cid}.jpg"))
    pinterest.save_candidates(cdir, cands)

    r = refs.select(meta["id"], ["aaa111", "ccc333"], {"aaa111": "gostei do gelo"})
    assert r == {"selected": 2}
    assert sorted(p.name for p in (root / "refs" / "brainstorming").iterdir()) == ["aaa111.jpg", "ccc333.jpg"]
    readme = (root / "refs" / "README.md").read_text()
    # R3: a regra "não entra no vídeo" é do Studio (direitos), não da aula; R4: "por quê" é [extensão].
    assert "gostei do gelo" in readme and "Regra do Studio" in readme
    assert "não entram no vídeo final" in readme and "[extensão]" in readme
    assert "Nunca entram no vídeo final (aula 009)" not in readme
    assert {c["id"]: c["selected"] for c in refs.candidates(meta["id"])} == {"aaa111": True, "bbb222": False, "ccc333": True}

    # o "por quê" fica gravado no candidato: a tela reabre preenchida
    assert {c["id"]: c["extra"].get("why") for c in refs.candidates(meta["id"])}["aaa111"] == "gostei do gelo"
    refs.select(meta["id"], ["aaa111", "ccc333"])
    assert "gostei do gelo" in (root / "refs" / "README.md").read_text(), "não se perde ao resalvar"

    # desmarcar remove da pasta de brainstorming
    refs.select(meta["id"], ["bbb222"])
    assert [p.name for p in (root / "refs" / "brainstorming").iterdir()] == ["bbb222.jpg"]


def test_pinterest_best_url_upgrades_to_originals(studio_env):
    from studio.refs.pinterest import _best_url
    assert _best_url("https://i.pinimg.com/236x/ab/cd/ef.jpg") == "https://i.pinimg.com/originals/ab/cd/ef.jpg"
    assert _best_url("https://i.pinimg.com/originals/ab/cd/ef.jpg") == "https://i.pinimg.com/originals/ab/cd/ef.jpg"


def test_project_dir_rejects_unsafe_ids(studio_env):
    refs = studio_env["refs"]
    for bad in ("../etc", "a/b", "", "X Y", "a" * 90):
        with pytest.raises(KeyError):
            refs.project_dir(bad)


def test_import_upload_adds_manual_references(studio_env):
    """R2 — a aula cita o Explore do Midjourney como segunda fonte; entra por upload `[extensão]`."""
    refs = studio_env["refs"]
    from tests.conftest import image_bytes
    meta = refs.create_project("Upload")
    data = image_bytes()
    assert refs.import_upload(meta["id"], [("explore-1.png", data), ("copia.png", data)]) == {"added": 1}
    assert refs.import_upload(meta["id"], [("outra.png", image_bytes(color=(3, 200, 9)))]) == {"added": 1}
    assert refs.import_upload(meta["id"], [("nao-imagem.txt", b"nada disso")]) == {"added": 0}

    cands = refs.candidates(meta["id"])
    assert len(cands) == 2 and {c["source"] for c in cands} == {"upload"}
    root = refs.project_dir(meta["id"])
    for c in cands:
        assert (root / "refs" / "candidates" / c["file"]).is_file()
        assert (root / "refs" / "candidates" / c["thumb"]).is_file()

    # e seguem selecionáveis como qualquer candidata do Pinterest
    refs.select(meta["id"], [cands[0]["id"]])
    assert [p.name for p in (root / "refs" / "brainstorming").iterdir()] == [cands[0]["file"]]


def test_last_scrape_is_persisted_for_the_status_column(studio_env, monkeypatch):
    """Wave 4 (1.22–1.24): a coluna de status abre preenchida com o último scrape.

    O job vive em memória; o resumo (`baixadas/meta` + log por termo) fica em `refs/last_job.json`
    para a tela desenhar barra, rótulo e log ao reabrir — sem isso ela nasce vazia.
    """
    refs = studio_env["refs"]
    pid = refs.create_project("Ultimo Scrape")["id"]
    assert refs.job_status(pid) == {"state": "idle"}, "projeto sem scrape mantém a resposta mínima"
    assert refs.last_job(pid) is None

    def fake_search(terms, cdir, max_per_term, headless, progress):
        for i, term in enumerate(terms):
            progress({"stage": "term", "term": term, "index": i, "n_terms": len(terms)})
            progress({"stage": "download", "term": term, "count": 30})
            progress({"stage": "saved", "term": term, "id": f"x{i}", "total": 30 * (i + 1)})
        progress({"stage": "done", "total": 30 * len(terms)})

    monkeypatch.setattr(studio_env["refs"].pinterest, "search", fake_search)
    refs.start_search(pid, ["red bull ads", "red bull snow ads"], max_per_term=40)
    for _ in range(200):
        if refs.job_status(pid)["state"] != "running":
            break
        time.sleep(0.02)

    st = refs.job_status(pid)
    assert st["state"] == "done" and st["total"] == 60 and st["meta"] == 80, "meta = termos × máx."
    assert [ln["text"] for ln in st["log"]] == [
        "red bull ads — 30 imagens", "red bull snow ads — 30 imagens", "concluído · 60 candidatas"]
    assert st["log"][-1]["ok"] is True, "a última linha é a verde do protótipo (`.log .ok`)"
    assert all(len(ln["time"]) == 5 for ln in st["log"]), "cada linha tem hora [HH:MM]"

    saved = refs.last_job(pid)
    assert saved["total"] == 60 and saved["meta"] == 80 and len(saved["log"]) == 3
    refs._jobs.pop(pid)                                   # simula recarregar a página/processo
    idle = refs.job_status(pid)
    assert idle["state"] == "idle" and idle["last_job"]["total"] == 60
