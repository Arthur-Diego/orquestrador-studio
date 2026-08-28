"""W5 — verificação cross-feature no estado integrado (develop), projeto 2026-08-wave-teste.

Percorre etapas 3→11 pela API real (TestClient), usando fixtures onde a aula exige geração
externa (imagens/vídeos importados), e cobra cada handoff listado em wave-1.md.
Rode a partir do checkout principal: `. .venv/bin/activate && STUDIO_PROJECTS=$PWD/projects python scripts/crossfeature_wave1.py`
(exige o projeto 2026-08-wave-teste com etapas 1–2 concluídas e ffmpeg; NÃO faz parte da suíte pytest).
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("STUDIO_PROJECTS", str(Path.cwd() / "projects"))
sys.path.insert(0, str(Path.cwd()))
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from studio.app import app  # noqa: E402
from studio.common import ffmpeg as ff  # noqa: E402

PID = "2026-08-wave-teste"
ROOT = Path(os.environ["STUDIO_PROJECTS"]) / PID
c = TestClient(app)
ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append(f"{name}{' — ' + detail if detail else ''}")
    print(("✓ " if cond else "✗ ") + name + (f"  ({detail})" if detail else ""))


def png(color=(30, 120, 200), size=(640, 360)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def api(method, path, expect=(200, 201, 202), **kw):
    r = getattr(c, method)(path, **kw)
    if r.status_code not in expect:
        print(f"   ! {method.upper()} {path} → {r.status_code} {r.text[:200]}")
    return r


steps = {s["id"]: s["status"] for s in c.get("/api/steps").json()}
check("catálogo: 10 etapas ready", all(v == "ready" for v in steps.values()), str(steps))

# ---- Etapa 3 · base (consome refs + mood reais) ----
r = api("get", f"/api/projects/{PID}/base/prompts")
check("base: prompts a partir das refs/mood reais", r.status_code == 200 and len(r.json().get("refs", [])) >= 1 and len(r.json().get("mood_files", [])) >= 1, f"refs={len(r.json().get('refs', []))} mood={len(r.json().get('mood_files', []))}")
api("post", f"/api/projects/{PID}/base/brand", json={"name": "Gelo Zero", "description": "raio neon ciano"}, expect=(200, 201))
r = api("post", f"/api/projects/{PID}/base/import/upload", files=[("files", ("sit.png", png(), "image/png"))], data={"kind": "situation"})
cands = api("get", f"/api/projects/{PID}/base/candidates").json().get("candidates", [])
cid = cands[-1]["id"] if cands else None
if cid:
    r = api("post", f"/api/projects/{PID}/base/select", json={"id": cid})
check("base: base_final.png gerado", (ROOT / "base" / "base_final.png").exists())

# ---- Etapa 4 · storyboard (consome base_final) ----
r = api("get", f"/api/projects/{PID}/storyboard")
check("storyboard: enxerga base_final real", r.status_code == 200 and "base" in json.dumps(r.json()).lower(), str(r.json())[:160])
api("post", f"/api/projects/{PID}/storyboard/import/upload", files=[("files", ("idea.png", png((200, 40, 40)), "image/png"))])
ideas = api("get", f"/api/projects/{PID}/storyboard/candidates").json()
iid = ideas[0]["id"] if isinstance(ideas, list) and ideas else None
if iid:
    api("post", f"/api/projects/{PID}/storyboard/candidates/select", json={"ids": [iid]})
scenes = [{"id": f"cena{i:02d}", "n": i, "text": t, "image": None} for i, t in enumerate(
    ["Close no astronauta andando na nevasca", "Ele para e encontra a lata gigante", "Olha o chão e vê a corda", "Começa a puxar", "A lata cai e inunda"], 1)]
r = api("put", f"/api/projects/{PID}/storyboard/scenes", json={"scenes": scenes})
api("post", f"/api/projects/{PID}/storyboard/render", expect=(200, 201, 422))
check("storyboard: scenes.json com 5 cenas", (ROOT / "storyboard" / "scenes.json").exists() and len(json.loads((ROOT / "storyboard" / "scenes.json").read_text())["scenes"]) == 5)

# ---- Etapa 4 · ângulos por cena (aula 011, absorvida na etapa 4 — ADR-015) ----
r = api("get", f"/api/projects/{PID}/storyboard/angles/scenes")
check("ângulos: lê scenes.json real (5 cenas)", r.status_code == 200 and len(r.json() if isinstance(r.json(), list) else r.json().get("scenes", [])) == 5, str(r.json())[:160])
for sc in ("cena01", "cena02"):
    api("post", f"/api/projects/{PID}/storyboard/angles/scenes/{sc}/base", json={"source": "storyboard"}, expect=(200, 201, 404, 409, 422))
    api("post", f"/api/projects/{PID}/storyboard/angles/scenes/{sc}/base/upload", files=[("file", ("b.png", png((10, 10, 10)), "image/png"))], expect=(200, 201, 404, 422))
    api("post", f"/api/projects/{PID}/storyboard/angles/scenes/{sc}/import/upload", files=[("files", ("s1.png", png((50, 60, 70)), "image/png")), ("files", ("s2.png", png((80, 90, 100)), "image/png"))])
    cs = api("get", f"/api/projects/{PID}/storyboard/angles/scenes/{sc}/candidates").json()
    ids = [x["id"] for x in (cs if isinstance(cs, list) else cs.get("candidates", []))][:2]
    api("post", f"/api/projects/{PID}/storyboard/angles/scenes/{sc}/select", json={"shots": [{"id": i} for i in ids]}, expect=(200, 201, 422))
sb = api("get", f"/api/projects/{PID}/storyboard/angles/storyboard").json()
check("ângulos: storyboard.json com ≥ 2 frames por cena (cenas 1–2)", sum(len(s.get("shots", [])) for s in sb.get("scenes", [])) >= 4, str(sb)[:160])

# ---- Etapa 5 · animate (consome storyboard.json) ----
r = api("get", f"/api/projects/{PID}/animate/shots")
plan = r.json()
shots_plan = plan.get("shots", plan) if isinstance(plan, dict) else plan
check("animate: plano lido do storyboard.json real", r.status_code == 200 and len(shots_plan) >= 2, str(plan)[:160])
tmp = Path("/tmp/claude-1000/wave-cf")
tmp.mkdir(parents=True, exist_ok=True)
if ff.available():
    vid = tmp / "take.mp4"
    ff.run(["-f", "lavfi", "-i", "testsrc=size=320x240:rate=30", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(vid)])
    for i, sh in enumerate(shots_plan[:2]):
        scene, shot = sh.get("scene"), sh.get("shot")
        data = vid.read_bytes() + bytes([i])  # conteúdo distinto → ids distintos
        api("post", f"/api/projects/{PID}/animate/import/upload", files=[("files", (f"t{i}.mp4", vid.read_bytes(), "video/mp4"))])
        vc = api("get", f"/api/projects/{PID}/animate/candidates").json()
        vids = [x["id"] for x in (vc if isinstance(vc, list) else vc.get("candidates", []))]
        if vids and scene and shot:
            r = api("post", f"/api/projects/{PID}/animate/shots/{scene}/{shot}/takes", json={"candidate_id": vids[-1]}, expect=(200, 201))
            tk = r.json().get("take", r.json()).get("id", "take1") if isinstance(r.json(), dict) else "take1"
            api("post", f"/api/projects/{PID}/animate/shots/{scene}/{shot}/takes/{tk}/like", json={"liked": True}, expect=(200, 201))
    takes = json.loads((ROOT / "animate" / "takes.json").read_text()) if (ROOT / "animate" / "takes.json").exists() else {}
    check("animate: takes.json com take liked", any(t.get("liked") for s in takes.get("shots", []) for t in s.get("takes", [])), str(takes)[:160])

    # ---- Etapa 6 · music ----
    wav = tmp / "m.wav"
    ff.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=12", "-af", "volume='if(lt(mod(t,0.5),0.08),1,0.05)':eval=frame", str(wav)])
    api("post", f"/api/projects/{PID}/music/import/upload", files=[("files", ("m.wav", wav.read_bytes(), "audio/wav"))])
    mc = api("get", f"/api/projects/{PID}/music/candidates").json()
    mid = [x["id"] for x in (mc if isinstance(mc, list) else mc.get("candidates", []))]
    if mid:
        api("post", f"/api/projects/{PID}/music/select", json={"id": mid[0], "license": "YouTube Audio Library — teste"}, expect=(200, 201))
    beats = json.loads((ROOT / "audio" / "beats.json").read_text()) if (ROOT / "audio" / "beats.json").exists() else {}
    check("music: beats.json com impactos (~120 bpm)", bool(beats.get("impacts")) and 100 <= beats.get("bpm", 0) <= 140, str({k: (v if not isinstance(v, list) else len(v)) for k, v in beats.items()}))

    # ---- Etapa 7 · edit (consome takes + beats + storyboard) ----
    r = api("get", f"/api/projects/{PID}/edit/timeline")
    check("edit: timeline inicial a partir de takes.json real", r.status_code == 200 and len(r.json().get("timeline", r.json()).get("clips", [])) >= 1, str(r.json())[:160])
    api("post", f"/api/projects/{PID}/edit/propose-cuts", json={"apply": True}, expect=(200, 201, 422))
    r = api("post", f"/api/projects/{PID}/edit/render", json={"target": "master"}, expect=(200, 201, 202))
    for _ in range(90):
        j = api("get", f"/api/projects/{PID}/edit/render/job").json()
        if j.get("state") in ("done", "error", "idle"):
            break
        time.sleep(2)
    master = ROOT / "edit" / "master.mp4"
    check("edit: master.mp4 renderizado 1920x1080", master.exists() and ff.probe(master)["width"] == 1920, str(j)[:160])

    # ---- Etapa 8 · export (consome master) ----
    r = api("post", f"/api/projects/{PID}/export/render", json={"formats": ["16x9", "9x16", "1x1"]}, expect=(200, 201, 202))
    for _ in range(90):
        j = api("get", f"/api/projects/{PID}/export/job").json()
        if j.get("state") in ("done", "error", "idle"):
            break
        time.sleep(2)
    api("post", f"/api/projects/{PID}/export/thumb", json={"t": 1.0}, expect=(200, 201))
    api("post", f"/api/projects/{PID}/export/qa", expect=(200, 201))
    ex = ROOT / "export"
    check("export: 9x16 e 1x1 derivados do master", (ex / "9x16.mp4").exists() and (ex / "1x1.mp4").exists() and ff.probe(ex / "9x16.mp4")["width"] == 1080, str(j)[:120])
    check("export: qa_report.md", (ex / "qa_report.md").exists())

    # ---- Etapa 9 · publish (consome export) ----
    r = api("get", f"/api/projects/{PID}/publish/exports")
    names = [e.get("name") for e in r.json().get("files", [])]
    check("publish: lista os exports reais", any("9x16" in str(n) for n in names), str(names))
    for i, (v, net) in enumerate([("16x9.mp4", "youtube"), ("9x16.mp4", "instagram"), ("1x1.mp4", "instagram"), ("9x16.mp4", "tiktok")]):
        api("post", f"/api/projects/{PID}/publish/log", json={"video": v, "network": net, "url": f"https://example.com/p{i}", "note": ""}, expect=(200, 201))
    pf = api("get", f"/api/projects/{PID}/publish/portfolio").json()
    # ADR-012: o portfólio conta OBRAS distintas (projetos), não vídeos de um mesmo projeto.
    check("publish: 3 vídeos distintos em 4 posts → ready=false (decisão 1)", pf.get("distinct_videos") == 3 and pf.get("ready") is False, str(pf))

    # ---- Etapa 10 · prospect (gate + teaser) ----
    g = api("get", f"/api/projects/{PID}/prospect/gate").json()
    check("prospect: gate fechado com 3 vídeos distintos", g.get("ok") is False, str(g))
    # publica um 4º vídeo distinto para abrir o gate
    shutil.copy2(ROOT / "export" / "9x16.mp4", ROOT / "export" / "teaser.mp4")
    api("post", f"/api/projects/{PID}/publish/log", json={"video": "teaser.mp4", "network": "instagram", "url": "https://example.com/p9", "note": "teaser"}, expect=(200, 201))
    g = api("get", f"/api/projects/{PID}/prospect/gate").json()
    # NB (ADR-012): o gate abre por 4 OBRAS (projetos) publicadas, não por 4 vídeos deste projeto —
    # aqui ele passa porque o diretório de projetos já tem 4+ obras. Ver scripts/e2e_pipeline.py,
    # que abre o gate criando projetos-irmãos publicados (forma correta pós-ADR-012).
    check("prospect: gate aberto (>=4 obras publicadas no workspace)", g.get("ok") is True, str(g))
    r = api("post", f"/api/projects/{PID}/prospect/leads", json={"business": "Zé do Hambúrguer", "handle": "@zeburger", "post_ref": "hambúrgueres gourmet", "why": "prefiro gourmet", "role": "fã"}, expect=(200, 201, 409))
    lid = r.json().get("id") if r.status_code in (200, 201) else None
    if lid:
        dm = api("get", f"/api/projects/{PID}/prospect/leads/{lid}/dm").json()
        check("prospect: DM literal sem link", "portfólio" in json.dumps(dm, ensure_ascii=False) and "http" not in json.dumps(dm.get("text", dm)), str(dm)[:120])
        api("post", f"/api/projects/{PID}/prospect/leads/{lid}/sent", expect=(200, 201))
        api("post", f"/api/projects/{PID}/prospect/leads/{lid}/replied", expect=(200, 201))
        api("post", f"/api/projects/{PID}/prospect/leads/{lid}/teaser", json={"duration": 6}, expect=(200, 201, 202))
        for _ in range(60):
            j = api("get", f"/api/projects/{PID}/prospect/job").json()
            if j.get("state") in ("done", "error", "idle"):
                break
            time.sleep(2)
        teasers = list((ROOT / "prospect" / "teasers").glob("*.mp4")) if (ROOT / "prospect" / "teasers").exists() else []
        check("prospect: teaser 5–10 s com música a partir de take+trilha reais", bool(teasers) and 5 <= ff.probe(teasers[0])["duration"] <= 10 and ff.probe(teasers[0])["has_audio"], str(j)[:120])
else:
    print("ffmpeg indisponível: etapas 6–11 não verificadas")

print(f"\nRESULTADO: {len(ok)} ok · {len(fail)} falhas")
for f in fail:
    print("  FALHA:", f)
sys.exit(1 if fail else 0)
