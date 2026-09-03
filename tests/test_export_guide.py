"""Etapa 8 — o guia por etapa (aula 014) e os textos de tela corrigidos pela auditoria 9.1/9.2.

Tudo por HTTP e por leitura pura de artefatos (ADR-003/ADR-008): nenhum teste aqui chama
ffprobe, e o hook do guia também não pode.
"""
import json

import pytest


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]


def guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/export")
    assert r.status_code == 200
    return r.json()


def check(g, cid):
    return next(v for v in g["validations"] if v["id"] == cid)


def write(studio_env, pid, rel, data=b"x"):
    path = studio_env["refs"].project_dir(pid) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def timeline(studio_env, pid, seconds):
    write(studio_env, pid, "edit/timeline.json", json.dumps(
        {"clips": [{"in": 0.0, "out": seconds, "speed": 1.0}], "blacks": []}).encode())


# ---------- estado ----------
def test_guia_bloqueado_sem_o_master_da_etapa_8(client, pid):
    g = guide(client, pid)
    assert g["status"] == "blocked" and g["n"] == 8 and g["aula"] == "014"
    assert g["inputs"][0]["step"] == "edit" and g["inputs"][0]["status"] == "fail"
    assert "edit/master.mp4 (etapa 7)" in g["missing"]
    assert "publicar mesmo que o primeiro fique ruim" in g["what"]
    assert g["next_step"] == "publish"


def test_saida_cobrada_e_o_formato_da_rede_alvo(client, studio_env, pid):
    write(studio_env, pid, "edit/master.mp4")
    g = guide(client, pid)
    assert g["status"] == "todo" and [o["id"] for o in g["outputs"]] == ["formato_alvo"]
    assert g["outputs"][0]["label"] == "export/16x9.mp4", "sem escolha, o default é 16:9"

    client.patch(f"/api/projects/{pid}", json={"aspect_ratio": "9:16"})
    g = guide(client, pid)
    assert g["outputs"][0]["label"] == "export/9x16.mp4"
    assert "Reels e TikTok" in g["outputs"][0]["detail"]

    write(studio_env, pid, "export/9x16.mp4")
    g = guide(client, pid)
    assert g["status"] == "done" and g["progress"] == 1.0
    assert check(g, "formato_16x9")["status"] == "todo", "o outro formato é opcional, não trava"


def test_thumb_qa_e_1x1_aparecem_marcados_como_extensao(client, studio_env, pid):
    write(studio_env, pid, "edit/master.mp4")
    g = guide(client, pid)
    assert "[extensão]" in check(g, "thumb")["label"]
    assert "[extensão]" in check(g, "qa")["label"]
    assert "[extensão]" in check(g, "formato_1x1")["label"]
    assert check(g, "thumb")["status"] == "todo"
    write(studio_env, pid, "export/thumb.jpg")
    write(studio_env, pid, "export/qa_report.md")
    g = guide(client, pid)
    assert check(g, "thumb")["status"] == "ok" and check(g, "qa")["status"] == "ok"


def test_preview_do_corte_central_entra_como_validacao(client, studio_env, pid):
    write(studio_env, pid, "edit/master.mp4")
    assert check(guide(client, pid), "preview")["status"] == "todo"
    write(studio_env, pid, "export/previews/16x9.jpg")
    assert check(guide(client, pid), "preview")["status"] == "ok"


# ---------- duração 30 s a 1 min (aula 016), sem ffprobe ----------
def test_duracao_do_comercial_e_lida_da_timeline_da_etapa_8(client, studio_env, pid):
    write(studio_env, pid, "edit/master.mp4")
    assert check(guide(client, pid), "duracao")["status"] == "todo", "sem timeline não há o que medir"
    timeline(studio_env, pid, 42)
    ok = check(guide(client, pid), "duracao")
    assert ok["status"] == "ok" and ok["detail"] == "42 s"
    timeline(studio_env, pid, 95)
    fora = check(guide(client, pid), "duracao")
    assert fora["status"] == "warn" and "30 s a 1 min" in fora["fix"], "aviso, nunca trava"


def test_timeline_corrompida_nao_derruba_o_guia(client, studio_env, pid):
    write(studio_env, pid, "edit/master.mp4")
    write(studio_env, pid, "edit/timeline.json", b"{quebrado")
    g = guide(client, pid)
    assert g["status"] != "unknown" and check(g, "duracao")["status"] == "todo"


def test_guia_nao_escreve_nada_no_projeto(client, studio_env, pid):
    write(studio_env, pid, "edit/master.mp4")
    guide(client, pid)
    export = studio_env["refs"].project_dir(pid) / "export"
    assert list(export.iterdir()) == [], "o hook do guia é leitura pura"


# ---------- chip-resumo da faixa do guia (wave 4, 9.4) ----------
def test_resumo_do_guia_e_o_estado_do_master(client, studio_env, pid):
    assert guide(client, pid)["summary"] == "master: aguardando a etapa 7"
    write(studio_env, pid, "edit/master.mp4")
    g = guide(client, pid)
    assert g["summary"] == "master: pronto" and g["summary_kind"] is None
    assert g["next_action"] == "Renderizar o formato da rede onde você vai publicar"
    write(studio_env, pid, "export/16x9.mp4")
    assert "Renderizar o formato" not in guide(client, pid)["next_action"]


# ---------- textos de tela (auditoria 9.1, 9.2 e wave 4) ----------
# Wave 10 · E4 (ADR-032): `test_tela_atribui_o_formato_ao_destino_e_marca_a_extensao` e
# `test_view_segue_o_catalogo_do_redesign` liam o fonte de `export/view.{html,js}` (substring sobre a
# tela vanilla). A tela virou React (`export/ui/index.tsx`); o contrato de DOM/comportamento e os
# textos de aula (ADR-004) passam a ser verificados pelo substituto Vitest
# `studio/etapas/export/ui/index.test.tsx` (C-EXPORT-*) e pelo diff de `textContent` do baseline da
# E0. Os testes de guia deste arquivo (leitura pura de `/guide`, ADR-010) seguem intactos.
