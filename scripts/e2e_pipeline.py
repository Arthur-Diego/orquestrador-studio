"""E2E mockado do pipeline do Orquestrador Studio — ADH-OS-20260827-02.

Cria um projeto NOVO do zero via API e dirige as 10 etapas (1→10) com fixtures sintéticas
(PNG via PIL; vídeo/áudio via ffmpeg lavfi) onde a aula exige geração externa, afirmando as
saídas de cada etapa. Depois exercita a feature de RESET (cascata de etapa + campanha).

Sem rede: não usa Pinterest nem Claude (etapas 1–2 entram por upload; prompt do mood em modo
`template`). Autocontido — NÃO depende do projeto 2026-08-wave-teste.

Uso direto (report determinístico + exit code):
    . .venv/bin/activate && export PATH="$HOME/.local/bin:$PATH"
    STUDIO_PROJECTS=$PWD/projects python scripts/e2e_pipeline.py [--populate-only]

`--populate-only` roda só 1→10 (sem reset) e deixa o projeto cheio no disco — é o modo usado
antes de tirar os prints (smoke_ui) com as telas populadas.

Também é chamado por tests/test_e2e_pipeline.py (que injeta um client isolado + tmp dir).
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_NAME = "E2E Mock"


def png(color=(30, 120, 200), size=(640, 360)) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def run(client, projects_dir: Path, do_reset: bool = True) -> tuple[list[str], list[str]]:
    """Roda o E2E contra `client` (TestClient) com STUDIO_PROJECTS == `projects_dir`.

    Devolve (ok, fail). Não sai do processo — quem chama decide o exit code.
    """
    from studio.common import ffmpeg as ff

    c = client
    ok: list[str] = []
    fail: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> bool:
        (ok if cond else fail).append(f"{name}{' — ' + detail if detail else ''}")
        print(("✓ " if cond else "✗ ") + name + (f"  ({detail})" if detail else ""))
        return bool(cond)

    def api(method, path, expect=(200, 201, 202), **kw):
        r = getattr(c, method)(path, **kw)
        if r.status_code not in expect:
            print(f"   ! {method.upper()} {path} → {r.status_code} {r.text[:200]}")
        return r

    # ---- Projeto novo do zero ----
    r = api("post", "/api/projects", json={"name": PROJECT_NAME, "product": "energético",
                                           "vibe": ""}, expect=(200, 201))
    pid = r.json().get("id") if r.status_code in (200, 201) else None
    check("projeto: POST /api/projects cria pid novo", bool(pid), str(pid))
    if not pid:
        return ok, fail
    root = projects_dir / pid
    check("projeto: project.json no disco", (root / "project.json").exists(), pid)

    steps = {s["id"]: s["status"] for s in c.get("/api/steps").json()}
    check("catálogo: 10 etapas ready", len(steps) == 10 and all(v == "ready" for v in steps.values()),
          str(steps))

    # ---- Etapa 1 · refs (sem rede: upload + select) ----
    api("post", f"/api/projects/{pid}/refs/import/upload",
        files=[("files", ("ref1.png", png((200, 60, 60)), "image/png")),
               ("files", ("ref2.png", png((60, 200, 120)), "image/png"))])
    cands = api("get", f"/api/projects/{pid}/refs/candidates").json()
    ref_ids = [x["id"] for x in cands]
    check("etapa 1 (refs): 2 candidatas importadas por upload", len(ref_ids) >= 2, str(len(ref_ids)))
    api("post", f"/api/projects/{pid}/refs/select",
        json={"ids": ref_ids, "notes": {ref_ids[0]: "cor da marca"}})
    bstorm = list((root / "refs" / "brainstorming").glob("*.jpg"))
    check("etapa 1 (refs): refs/brainstorming/ populado", len(bstorm) >= 2, str(len(bstorm)))

    # ---- Etapa 2 · mood (upload vibe + prompt template + upload candidatas + select) ----
    api("post", f"/api/projects/{pid}/mood/vibe/import/upload",
        files=[("files", ("vibe1.png", png((20, 40, 90)), "image/png")),
               ("files", ("vibe2.png", png((30, 30, 60)), "image/png"))])
    vibe = api("get", f"/api/projects/{pid}/mood/vibe").json()
    check("etapa 2 (mood): imagens de vibe carregadas", len(vibe.get("images", [])) >= 1,
          str(len(vibe.get("images", []))))
    r = api("post", f"/api/projects/{pid}/mood/prompts/generate",
            json={"mode": "template", "purpose": "campanha", "tone": "gelo neon"}, expect=(200, 201))
    check("etapa 2 (mood): prompt gerado em modo template (sem Claude)",
          r.status_code in (200, 201) and (root / "mood" / "prompts.json").exists(),
          str(r.json())[:80] if r.status_code < 400 else r.text[:80])
    api("post", f"/api/projects/{pid}/mood/import/upload",
        files=[("files", ("m1.png", png((15, 35, 80)), "image/png")),
               ("files", ("m2.png", png((25, 45, 95)), "image/png"))],
        data={"prompt": "vibe gelo neon ciano"})
    mc = api("get", f"/api/projects/{pid}/mood/candidates").json()
    mids = [x["id"] for x in (mc if isinstance(mc, list) else mc.get("candidates", []))]
    check("etapa 2 (mood): candidatas de mood importadas", len(mids) >= 2, str(len(mids)))
    r = api("post", f"/api/projects/{pid}/mood/select",
            json={"ids": mids, "note": "gelo neon ciano, alto contraste"}, expect=(200, 201))
    sel = list((root / "mood" / "selected").glob("*"))
    proj = json.loads((root / "project.json").read_text())
    check("etapa 2 (mood): mood/selected/ + mood.md + palette.json",
          len(sel) >= 2 and (root / "mood" / "mood.md").exists()
          and (root / "mood" / "palette.json").exists(), str(len(sel)))
    check("etapa 2 (mood): project.vibe gravado a partir da seleção",
          bool(proj.get("vibe")), proj.get("vibe", ""))

    # ---- Etapa 3 · base (consome refs + mood) ----
    r = api("get", f"/api/projects/{pid}/base/prompts")
    check("etapa 3 (base): prompts a partir de refs/mood reais",
          r.status_code == 200 and len(r.json().get("refs", [])) >= 1
          and len(r.json().get("mood_files", [])) >= 1,
          f"refs={len(r.json().get('refs', []))} mood={len(r.json().get('mood_files', []))}")
    api("post", f"/api/projects/{pid}/base/brand",
        json={"name": "Gelo Zero", "description": "raio neon ciano"}, expect=(200, 201))
    api("post", f"/api/projects/{pid}/base/import/upload",
        files=[("files", ("sit.png", png(), "image/png"))], data={"kind": "situation"})
    bc = api("get", f"/api/projects/{pid}/base/candidates").json().get("candidates", [])
    if bc:
        api("post", f"/api/projects/{pid}/base/select", json={"id": bc[-1]["id"]})
    check("etapa 3 (base): base_final.png gerado", (root / "base" / "base_final.png").exists())

    # ---- Etapa 4 · storyboard guiado por pré-roteiro (ADR-018) ----
    # Sem Claude/rede: grava o pré-roteiro direto pela API de edição (PUT) em vez de gerar por LLM.
    # (a geração por Claude e as fotos-semente/foto por CLI são cobertas em test_storyboard_flow.py.)
    scenes = [{"title": t.split()[0], "text": t, "arc": a} for t, a in [
        ("Close no produto na nevasca", "comeco"), ("A lata gigante aparece", "descoberta"),
        ("A corda no chão", "descoberta"), ("Puxa a corda", "acao"), ("A lata cai e inunda", "desfecho")]]
    api("put", f"/api/projects/{pid}/storyboard/prescript", json={"scenes": scenes}, expect=(200, 201))
    scenes_ok = (root / "storyboard" / "scenes.json").exists() and len(
        json.loads((root / "storyboard" / "scenes.json").read_text())["scenes"]) == 5
    check("etapa 4 (storyboard): pré-roteiro com 5 cenas", scenes_ok)

    # ---- Etapa 4 · ângulos por cena (aula 011, absorvida na etapa 4 — ADR-015) ----
    r = api("get", f"/api/projects/{pid}/storyboard/angles/scenes")
    nscenes = len(r.json() if isinstance(r.json(), list) else r.json().get("scenes", []))
    check("etapa 4 (ângulos): lê scenes.json real (5 cenas)", r.status_code == 200 and nscenes == 5,
          str(nscenes))
    for sc in ("cena01", "cena02"):
        api("post", f"/api/projects/{pid}/storyboard/angles/scenes/{sc}/base", json={"source": "storyboard"},
            expect=(200, 201, 404, 409, 422))
        api("post", f"/api/projects/{pid}/storyboard/angles/scenes/{sc}/base/upload",
            files=[("file", ("b.png", png((10, 10, 10)), "image/png"))], expect=(200, 201, 404, 422))
        # aula 011: cada cena com VÁRIOS ângulos (≥ 2 imagens) — é o que o animate vai ler
        api("post", f"/api/projects/{pid}/storyboard/angles/scenes/{sc}/import/upload",
            files=[("files", ("s1.png", png((50, 60, 70)), "image/png")),
                   ("files", ("s2.png", png((80, 90, 100)), "image/png"))])
        cs = api("get", f"/api/projects/{pid}/storyboard/angles/scenes/{sc}/candidates").json()
        ids = [x["id"] for x in (cs if isinstance(cs, list) else cs.get("candidates", []))][:2]
        api("post", f"/api/projects/{pid}/storyboard/angles/scenes/{sc}/select",
            json={"shots": [{"id": i} for i in ids]}, expect=(200, 201, 422))
    sb = api("get", f"/api/projects/{pid}/storyboard/angles/storyboard").json()
    nshots = sum(len(s.get("shots", [])) for s in sb.get("scenes", []))
    check("etapa 4 (ângulos): storyboard.json com ≥ 2 frames por cena nas cenas 1–2", nshots >= 4, str(nshots))
    check("etapa 4 (ângulos): cena01 com ≥ 2 imagens (vários ângulos, aula 011)",
          len((sb.get("scenes") or [{}])[0].get("shots", [])) >= 2,
          str(len((sb.get("scenes") or [{}])[0].get("shots", []))))

    if not ff.available():
        check("ffmpeg disponível para etapas 5–10", False, "ffmpeg ausente do PATH")
        print(f"\nRESULTADO: {len(ok)} ok · {len(fail)} falhas")
        return ok, fail

    tmp = Path(os.environ.get("STUDIO_STATE", "/tmp")) / "e2e-fixtures"
    tmp.mkdir(parents=True, exist_ok=True)

    # ---- Etapa 5 · animate ----
    r = api("get", f"/api/projects/{pid}/animate/shots")
    plan = r.json()
    shots_plan = plan.get("shots", plan) if isinstance(plan, dict) else plan
    check("etapa 5 (animate): plano lido do storyboard.json real", r.status_code == 200
          and len(shots_plan) >= 2, str(len(shots_plan)))
    vid = tmp / "take.mp4"
    ff.run(["-f", "lavfi", "-i", "testsrc=size=320x240:rate=30", "-f", "lavfi",
            "-i", "sine=frequency=440", "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(vid)])
    for i, sh in enumerate(shots_plan[:2]):
        scene, shot = sh.get("scene"), sh.get("shot")
        api("post", f"/api/projects/{pid}/animate/import/upload",
            files=[("files", (f"t{i}.mp4", vid.read_bytes(), "video/mp4"))])
        vc = api("get", f"/api/projects/{pid}/animate/candidates").json()
        vids = [x["id"] for x in (vc if isinstance(vc, list) else vc.get("candidates", []))]
        if vids and scene and shot:
            r = api("post", f"/api/projects/{pid}/animate/shots/{scene}/{shot}/takes",
                    json={"candidate_id": vids[-1]}, expect=(200, 201))
            body = r.json() if r.status_code < 400 else {}
            tk = (body.get("take", body).get("id", "take1")
                  if isinstance(body, dict) else "take1")
            api("post", f"/api/projects/{pid}/animate/shots/{scene}/{shot}/takes/{tk}/like",
                json={"liked": True}, expect=(200, 201))
    takes = (json.loads((root / "animate" / "takes.json").read_text())
             if (root / "animate" / "takes.json").exists() else {})
    check("etapa 5 (animate): takes.json com take liked",
          any(t.get("liked") for s in takes.get("shots", []) for t in s.get("takes", [])),
          str(len(takes.get("shots", []))) + " shots")

    # ---- Etapa 6 · music ----
    wav = tmp / "m.wav"
    ff.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=12", "-af",
            "volume='if(lt(mod(t,0.5),0.08),1,0.05)':eval=frame", str(wav)])
    api("post", f"/api/projects/{pid}/music/import/upload",
        files=[("files", ("m.wav", wav.read_bytes(), "audio/wav"))])
    mc = api("get", f"/api/projects/{pid}/music/candidates").json()
    mid = [x["id"] for x in (mc if isinstance(mc, list) else mc.get("candidates", []))]
    if mid:
        api("post", f"/api/projects/{pid}/music/select",
            json={"id": mid[0], "license": "YouTube Audio Library — teste"}, expect=(200, 201))
    beats = (json.loads((root / "audio" / "beats.json").read_text())
             if (root / "audio" / "beats.json").exists() else {})
    check("etapa 6 (music): beats.json com impactos (~120 bpm)",
          bool(beats.get("impacts")) and 100 <= beats.get("bpm", 0) <= 140,
          f"bpm={beats.get('bpm')} impacts={len(beats.get('impacts', []))}")

    # ---- Etapa 7 · edit ----
    r = api("get", f"/api/projects/{pid}/edit/timeline")
    tl = r.json().get("timeline", r.json())
    check("etapa 7 (edit): timeline inicial a partir de takes.json real",
          r.status_code == 200 and len(tl.get("clips", [])) >= 1, str(len(tl.get("clips", []))))
    api("post", f"/api/projects/{pid}/edit/propose-cuts", json={"apply": True},
        expect=(200, 201, 422))
    api("post", f"/api/projects/{pid}/edit/render", json={"target": "master"},
        expect=(200, 201, 202))
    j = {}
    for _ in range(90):
        j = api("get", f"/api/projects/{pid}/edit/render/job").json()
        if j.get("state") in ("done", "error", "idle"):
            break
        time.sleep(2)
    master = root / "edit" / "master.mp4"
    check("etapa 7 (edit): master.mp4 renderizado 1920x1080",
          master.exists() and ff.probe(master)["width"] == 1920, str(j.get("state")))

    # ---- Etapa 8 · export ----
    api("post", f"/api/projects/{pid}/export/render", json={"formats": ["16x9", "9x16", "1x1"]},
        expect=(200, 201, 202))
    for _ in range(90):
        j = api("get", f"/api/projects/{pid}/export/job").json()
        if j.get("state") in ("done", "error", "idle"):
            break
        time.sleep(2)
    api("post", f"/api/projects/{pid}/export/thumb", json={"t": 1.0}, expect=(200, 201))
    api("post", f"/api/projects/{pid}/export/qa", expect=(200, 201))
    ex = root / "export"
    check("etapa 8 (export): 9x16 e 1x1 derivados do master",
          (ex / "9x16.mp4").exists() and (ex / "1x1.mp4").exists()
          and ff.probe(ex / "9x16.mp4")["width"] == 1080, str(j.get("state")))
    check("etapa 8 (export): qa_report.md", (ex / "qa_report.md").exists())

    # ---- Etapa 9 · publish ----
    # ADR-012: o portfólio conta OBRAS (projetos distintos), não arquivos. 16x9/9x16/1x1 do mesmo
    # projeto = 1 obra; o mesmo 9x16 no Instagram e no TikTok = 1 vídeo, 2 posts.
    r = api("get", f"/api/projects/{pid}/publish/exports")
    names = [e.get("name") for e in r.json().get("files", [])]
    check("etapa 9 (publish): lista os exports reais",
          any("9x16" in str(n) for n in names), str(names))
    for i, (v, net) in enumerate([("16x9.mp4", "youtube"), ("9x16.mp4", "instagram"),
                                  ("1x1.mp4", "instagram"), ("9x16.mp4", "tiktok")]):
        api("post", f"/api/projects/{pid}/publish/log",
            json={"video": v, "network": net, "url": f"https://example.com/p{i}", "note": ""},
            expect=(200, 201))
    pf = api("get", f"/api/projects/{pid}/publish/portfolio").json()
    check("etapa 9 (publish): 4 posts / 3 arquivos neste projeto; portfólio global 1/4 obras (ready=false)",
          pf.get("count") == 4 and pf.get("videos") == 3
          and pf.get("distinct_videos") == 1 and pf.get("ready") is False,
          f"count={pf.get('count')} videos={pf.get('videos')} "
          f"obras={pf.get('distinct_videos')} ready={pf.get('ready')}")

    # ---- Etapa 10 · prospect (gate + teaser) ----
    g = api("get", f"/api/projects/{pid}/prospect/gate").json()
    check("etapa 10 (prospect): gate fechado com 1 obra publicada",
          g.get("ok") is False and g.get("published") == 1, str(g.get("message")))

    # Abre o gate: o portfólio precisa de 4 OBRAS distintas (ADR-012). Cria 3 projetos-irmãos,
    # cada um com um export no disco e 1 post registrado.
    from studio.refs.service import slugify as _slug
    portfolio_vid = vid.read_bytes()
    for i in range(1, 4):
        sib_name = f"E2E Portfolio {i}"
        sib_pid = f"{proj.get('created', '')[:7]}-{_slug(sib_name)}"
        sib_dir = projects_dir / sib_pid
        if sib_dir.exists():
            shutil.rmtree(sib_dir)
        api("post", "/api/projects", json={"name": sib_name, "product": "energético"},
            expect=(200, 201, 409))
        (sib_dir / "export").mkdir(parents=True, exist_ok=True)
        (sib_dir / "export" / "obra.mp4").write_bytes(portfolio_vid)
        api("post", f"/api/projects/{sib_pid}/publish/log",
            json={"video": "obra.mp4", "network": "youtube",
                  "url": f"https://example.com/obra{i}", "note": ""}, expect=(200, 201))
    g = api("get", f"/api/projects/{pid}/prospect/gate").json()
    check("etapa 10 (prospect): gate aberto com 4 obras distintas",
          g.get("ok") is True and g.get("published") >= 4, str(g.get("message")))
    r = api("post", f"/api/projects/{pid}/prospect/leads",
            json={"business": "Zé do Hambúrguer", "handle": "@zeburger",
                  "post_ref": "hambúrgueres gourmet", "why": "prefiro gourmet", "role": "fã"},
            expect=(200, 201, 409))
    lid = r.json().get("id") if r.status_code in (200, 201) else None
    if lid:
        dm = api("get", f"/api/projects/{pid}/prospect/leads/{lid}/dm").json()
        check("etapa 10 (prospect): DM literal sem link",
              "portf" in json.dumps(dm, ensure_ascii=False).lower()
              and "http" not in json.dumps(dm.get("text", dm)), str(dm)[:80])
        api("post", f"/api/projects/{pid}/prospect/leads/{lid}/sent", expect=(200, 201))
        api("post", f"/api/projects/{pid}/prospect/leads/{lid}/replied", expect=(200, 201))
        api("post", f"/api/projects/{pid}/prospect/leads/{lid}/teaser", json={"duration": 6},
            expect=(200, 201, 202))
        for _ in range(60):
            j = api("get", f"/api/projects/{pid}/prospect/job").json()
            if j.get("state") in ("done", "error", "idle"):
                break
            time.sleep(2)
        teasers = (list((root / "prospect" / "teasers").glob("*.mp4"))
                   if (root / "prospect" / "teasers").exists() else [])
        check("etapa 10 (prospect): teaser 5–10 s com música (take+trilha reais)",
              bool(teasers) and 5 <= ff.probe(teasers[0])["duration"] <= 10
              and ff.probe(teasers[0])["has_audio"], str(j.get("state")))
    else:
        check("etapa 10 (prospect): lead criado", False, "não foi possível criar lead")

    if not do_reset:
        print(f"\nRESULTADO (populate-only): {len(ok)} ok · {len(fail)} falhas")
        return ok, fail

    # ================= RESET =================
    # --- Reset de etapa (cascata) em `base` ---
    r = api("post", f"/api/projects/{pid}/steps/base/reset", expect=(200, 201))
    cleared = set(r.json().get("cleared", [])) if r.status_code < 400 else set()
    check("reset etapa (base): 200 + cascata reportada",
          r.status_code in (200, 201) and {"base", "storyboard", "animate", "audio",
                                           "edit", "export", "publish", "prospect"} <= cleared,
          str(sorted(cleared)))
    check("reset etapa (base): base e seguintes voltaram ao vazio",
          not (root / "base" / "base_final.png").exists()
          and not (root / "storyboard" / "scenes.json").exists()
          and not (root / "edit" / "master.mp4").exists()
          and not (root / "export" / "9x16.mp4").exists()
          and not (root / "prospect" / "leads.json").exists())
    check("reset etapa (base): refs e mood INTACTOS",
          len(list((root / "refs" / "brainstorming").glob("*.jpg"))) >= 2
          and len(list((root / "mood" / "selected").glob("*"))) >= 2)
    proj2 = json.loads((root / "project.json").read_text())
    check("reset etapa (base): project.json intacto (nome/produto/vibe)",
          proj2.get("name") == PROJECT_NAME and proj2.get("product") == "energético"
          and bool(proj2.get("vibe")), str(proj2))

    # --- Reconstrói o suficiente (base_final) para provar que o reset de campanha varre tudo ---
    api("post", f"/api/projects/{pid}/base/brand",
        json={"name": "Gelo Zero", "description": "raio neon ciano"}, expect=(200, 201))
    api("post", f"/api/projects/{pid}/base/import/upload",
        files=[("files", ("sit.png", png(), "image/png"))], data={"kind": "situation"})
    bc = api("get", f"/api/projects/{pid}/base/candidates").json().get("candidates", [])
    if bc:
        api("post", f"/api/projects/{pid}/base/select", json={"id": bc[-1]["id"]})
    check("reset: reconstruiu base_final antes do reset de campanha",
          (root / "base" / "base_final.png").exists())

    # --- Reset de campanha ---
    r = api("post", f"/api/projects/{pid}/reset", expect=(200, 201))
    check("reset campanha: 200", r.status_code in (200, 201),
          str(r.json())[:80] if r.status_code < 400 else r.text[:80])
    check("reset campanha: TODAS as saídas somem (refs/mood/base incluídos)",
          not (root / "base" / "base_final.png").exists()
          and not list((root / "refs" / "brainstorming").glob("*.jpg"))
          and not list((root / "mood" / "selected").glob("*"))
          and not (root / "mood" / "mood.md").exists())
    proj3 = json.loads((root / "project.json").read_text())
    check("reset campanha: project.json permanece (nome/produto/vibe)",
          proj3.get("name") == PROJECT_NAME and proj3.get("product") == "energético"
          and bool(proj3.get("vibe")), str(proj3))

    print(f"\nRESULTADO: {len(ok)} ok · {len(fail)} falhas")
    for f in fail:
        print("  FALHA:", f)
    return ok, fail


def _main() -> int:
    do_reset = "--populate-only" not in sys.argv
    os.environ.setdefault("STUDIO_PROJECTS", str(Path.cwd() / "projects"))
    sys.path.insert(0, str(Path.cwd()))
    projects_dir = Path(os.environ["STUDIO_PROJECTS"])
    projects_dir.mkdir(parents=True, exist_ok=True)

    # idempotência: remove o projeto E2E de execuções anteriores (pid é estável por nome/mês)
    from datetime import date

    from studio.refs.service import slugify
    pid = f"{date.today():%Y-%m}-{slugify(PROJECT_NAME)}"
    stale = projects_dir / pid
    if stale.exists():
        shutil.rmtree(stale)

    from fastapi.testclient import TestClient

    from studio.app import app
    client = TestClient(app)
    ok, fail = run(client, projects_dir, do_reset=do_reset)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(_main())
