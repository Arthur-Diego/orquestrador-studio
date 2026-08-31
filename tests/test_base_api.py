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
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "base")
    assert step["status"] == "ready" and step["n"] == 3 and step["aula"] == "009"
    assert client.get("/steps/base/view.html").status_code == 200
    assert client.get("/steps/base/view.js").status_code == 200
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    assert "Etapa 3 · aula 009" in html
    assert 'Studio.register("base"' in js


def test_view_follows_the_wave2_screen_contract(client):
    """Convenção da wave 2: painel do guia e helpers do Studio.ui.

    Wave 4: o painel 04 (geração paga via CLI) saiu da tela. base-cli-generation
    (ADH-OS-20260827-09) RE-ADICIONOU a geração via CLI, mas DENTRO do passo 03 (não um painel 04):
    o `ui.confirmCost` volta (custo por passo) e o poll passa a ser o `ui.progressJob` (que polla
    por dentro — a tela não chama `ui.poll` nem para o timer na mão). `ui.hfChip` segue fora.
    """
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    head = html.index('<header class="stephead">')
    guide = html.index('<section id="guide" class="guide">')
    assert head < guide < html.index("<section class=\"panel\">"), "o guia vem logo após o header"
    for helper in ("Studio.ui", "ui.drop(", "ui.esc(", "ui.tile(", "ui.autosize(",
                   'ui.renderGuide("base")'):
        assert helper in js, helper
    # base-cli-generation reusa o modal de progresso: `ui.progressJob` (não `ui.poll` cru)
    assert "ui.progressJob(" in js and "ui.confirmCost(" in js
    for ausente in ("ui.poll(", "ui.hfChip(", "job.stop()"):
        assert ausente not in js, f"{ausente} não voltou com o CLI (o poll é do progressJob)"
    assert "setTimeout(pollJob" not in js and "addEventListener(\"dragover\"" not in js, "sem helper local duplicado"
    assert "ctx.guide()" in js, "o guia é recarregado depois de cada ação que muda artefato"
    # B2/B11 na tela: a sessão nova do bot continua sendo um botão, agora só com o title do protótipo
    assert "Gerar sem viés" in html and "Sessão nova do bot" in html
    assert "no_bias" in js
    assert "aba nova na Higgsfield" not in html and "aba nova na Higgsfield" not in js


def test_view_follows_the_wave4_prototype(client):
    """Wave 4 (ADH-OS-20260826-12): a etapa 3 é o protótipo `proto/03-base.html`, elemento a
    elemento — 3 painéis, nenhum `<details>` de aula e nenhum controle que o protótipo não desenha."""
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    # painéis numerados com `.pn`, na ordem visual (o painel 04, do CLI pago, saiu)
    posicoes = [html.index(f'<span class="pn">{n}</span>') for n in ("01", "02", "03")]
    assert posicoes == sorted(posicoes), "os 3 painéis são numerados com .pn na ordem visual"
    # wave 5 · ponto 1 (ADH-OS-20260828-14): o painel "Mood de referência" (ADR-013) foi FUNDIDO
    # na junção do painel 01 — o seletor campanha/board e o mosaico do mood passam a ser
    # renderizados dentro de #baseJunction pelo view.js. Restam os 3 painéis do curso (01/02/03).
    assert html.count('<section class="panel">') == 3
    assert '<span class="pn">M</span>' not in html and 'id="moodSourceGallery"' not in html
    assert 'id="moodSource"' in js and "moodMosaic" in js
    assert '<span class="pn">04</span>' not in html and "gasta créditos" not in html
    # o texto de aula vive no guia: `<details class="lesson">` só existe na etapa 1 (regra 4)
    assert '<details class="lesson">' not in html
    assert "O que a aula 009 manda fazer aqui" not in html
    # títulos e textos fixos do protótipo
    assert '<span class="pn">01</span>O prompt da aula — quem escreve é o bot' in html
    assert '<span class="pn">02</span>Marca do rótulo' in html
    assert '<span class="pn">03</span>Escolher e fechar a imagem base' in html
    assert 'placeholder="o que muda nesta referência"' in html, "sem o exemplo entre parênteses"
    assert 'placeholder="como é a logo"' in html
    assert ">Usar como imagem base<" in html and ">Gerar prompt<" in html
    # ref-picker no `.gallery.xs` e galeria de candidatas no `.gallery.sm`
    assert '<div id="refGallery" class="gallery xs"></div>' in html
    assert '<div id="baseGallery" class="gallery sm"></div>' in html
    assert '<span class="eyebrow lbl">Referência (etapa 1) — clique para escolher</span>' in html
    # cadeia situação → rótulo → upscale 2x como `.stepper` renderizado pelo view.js; o stepper
    # é também o seletor do passo da importação (não há mais `select` de passo nem chip no fim)
    assert '<div id="baseChain" class="stepper"></div>' in html
    assert '"st done"' in js and '"st on"' in js and '<span class="sep"></span>' in js
    assert 'data-step="' in js and "bs-chain-state" not in js and "bs-chain-state" not in html
    # marca do rótulo com `.ext` e nota de fechamento
    assert '<span class="ext">[extensão]</span>' in html
    assert '<p class="note bs-note">Escolha uma imagem por passo' in html
    # um card de prompt só, de largura total, com a etiqueta exata do protótipo
    assert '<div id="basePrompts" class="prompts one bs-one"></div>' in html
    assert "Prompt · situação · editável" in js and "Prompt · rótulo · editável" in js
    assert "prompt-group" not in js and "instrução para o bot" not in js
    assert "ui.tile(" in js and 'class="link copy"' in js
    # defaults fixos no lugar dos controles removidos
    assert "no_people: false" in js and "SINCE_MINUTES = 120" in js
    assert 'url("prompts")' in js and "prompts?model=" not in js
    # o shell é contrato de leitura: os utilitários de layout vêm dele (`.grow`/`.grow-lg`)
    # e só o que sobra de específico fica escopado `.bs-`
    assert 'class="grow"' in html and 'class="grow-lg"' in html
    assert "<style>" in html and ".bs-io" in html
    assert ".bs-grow" not in html, "utilitário de crescimento é do shell, não da etapa"


def test_view_shows_the_mood_reference_junction(client):
    """base-prompt-provenance (FDD §3): o painel 01 ganha o cabeçalho de junção (thumb da
    referência + thumbs do mood + paleta) e a visão anotada `[extensão]` das 5 linhas com chips de
    proveniência — SEM remover o textarea copiável nem os 3 painéis do curso (contrato da wave 4)."""
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    # contêineres dentro do painel 01 (não são painéis novos); wave 5 · ponto 1: com o "M" fundido
    # na junção, a contagem de painéis cai para 3 (os do curso: 01/02/03)
    assert '<div id="baseJunction"' in html and '<div id="baseProvenance"' in html
    assert html.count('<section class="panel">') == 3
    # junção (ADH-OS-20260828-25): a "equação" referência + mood → prompt, com legendas e o texto
    # que explica que o prompt é a junção dos dois (a referência já é o hero grande do painel 01)
    assert 'class="bs-fuse"' in js and 'class="bs-fuse-thumb"' in js
    assert ">referência</figcaption>" in js and ">mood</figcaption>" in js
    assert 'class="bs-fuse-out">prompt' in js
    assert "O prompt ao lado é a <b>junção</b> dos dois" in js
    # a visão anotada é read-only, marcada [extensão], com chip por proveniência e parágrafo "junção"
    assert 'class="ext">[extensão]' in js
    assert 'from-${ui.esc(p.from)}' in js and "from-join" in js
    assert "renderJunction" in js and "renderProvenance" in js
    # cores por token (regra 6): --accent (mood), --info (referência), --ink-4 (técnico)
    assert ".bs-chip.from-mood{color:var(--accent)" in html
    assert ".bs-chip.from-reference{color:var(--info)" in html
    assert ".bs-chip.from-technical{color:var(--ink-4)" in html
    # o textarea copiável com o prompt COMPLETO segue intacto (não pode quebrar "Copiar"/editar)
    assert '<div id="basePrompts" class="prompts one bs-one"></div>' in html
    assert "<textarea" in js and 'class="link copy"' in js
    # os 3 painéis do curso permanecem; wave 5 · ponto 1: o seletor de fonte do mood (ADR-013) foi
    # fundido na junção (renderizado por moodSourceSelectHtml no view.js), não é mais um painel "M"
    for pn in ("01", "02", "03"):
        assert f'<span class="pn">{pn}</span>' in html
    assert '<span class="pn">M</span>' not in html and "moodSourceSelectHtml" in js
    assert '<span class="pn">04</span>' not in html and '<details class="lesson">' not in html


def test_view_shows_final_base_image_card_and_mosaic(client):
    """wave 5 · pontos 2 e 4 (ADH-OS-20260828-14): o painel 03 ganha o card da imagem base final
    (preview + selo + "segue para o storyboard →"), reusando o `final` que /base/candidates já
    devolve — sem rota nova; e a junção do painel 01 usa o mosaico quadricular do mood."""
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    # ponto 2: container do card + render a partir de `finalRel` (dado já existente, sem endpoint novo)
    assert '<div id="baseFinalCard"></div>' in html
    assert "renderFinalCard" in js and "finalRel = r.final" in js
    assert "imagem base final ✓" in js and "segue para o storyboard →" in js
    assert "base/base_final.png" in js
    # ponto 4: o mood da junção é renderizado como mosaico quadricular reutilizável
    assert "ui.moodMosaic(currentMoodThumbs()" in js
    # estilos escopados da fatia (regra 6): card final e <details> da proveniência
    assert ".bs-final{" in html and ".bs-prov-det" in html


def test_view_keeps_every_id_the_script_queries(client):
    """Contrato DOM da etapa (recon-wave-3 §1): nenhum id consultado pelo view.js some do HTML."""
    import re

    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    consultados = set(re.findall(r'[$(]"#([A-Za-z0-9_-]+)"', js))
    declarados = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
    assert consultados <= declarados, sorted(consultados - declarados)
    for obrigatorio in ("baseClaude", "refGallery", "promptInstruction", "btnPrompt",
                        "btnPromptNoBias", "basePrompts", "brandName", "brandDesc", "btnBrand",
                        "btnBaseSelect", "baseChain", "baseDrop", "baseUpload",
                        "btnBaseDownloads", "btnBaseHistory", "baseGallery"):
        assert f'id="{obrigatorio}"' in html, obrigatorio
    # ids dos controles que o protótipo não desenha (wave 4): saíram do HTML e do JS
    for removido in ("baseModel", "btnBasePrompts", "refPickState", "promptRef", "impRef",
                     "promptMode", "promptNoPeople", "botHint", "baseHint", "basePalette",
                     "baseMood", "upscaleHint", "labelPrompt", "galKind", "baseCounts",
                     "impKind", "impRefChip", "baseDlFolder", "baseDlMinutes", "baseHf",
                     "genKind", "genCount", "btnBaseGen", "baseProgress", "baseLog"):
        assert f'id="{removido}"' not in html and f'#{removido}"' not in js, removido


def test_prompts_endpoint(client, pid):
    r = client.get(f"/api/projects/{pid}/base/prompts")
    assert r.status_code == 200
    body = r.json()
    assert len(body["refs"]) == 2 and body["label_prompt"] is None and body["model"] == "nano_banana_2"
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


def test_brand_roundtrip(client, pid):
    assert client.get(f"/api/projects/{pid}/base/brand").json() == {"name": "", "description": ""}
    assert client.post(f"/api/projects/{pid}/base/brand", json={"name": "  "}).status_code == 422
    r = client.post(f"/api/projects/{pid}/base/brand", json={"name": "Gelo Zero", "description": "raio neon"})
    assert r.status_code == 200 and r.json()["name"] == "Gelo Zero"
    assert client.get(f"/api/projects/{pid}/base/brand").json()["description"] == "raio neon"
    assert "Gelo Zero" in client.get(f"/api/projects/{pid}/base/prompts").json()["label_prompt"]


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
    assert client.get(f"/api/projects/{pid}/base/job").json() == {"state": "idle"}
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


def test_view_offers_cli_generation_in_the_three_steps(client):
    """base-cli-generation (ADH-OS-20260827-09): a etapa 3 volta a oferecer GERAÇÃO VIA CLI nos 3
    passos (situação/rótulo/upscale), DENTRO do passo 03 — sem criar um painel 04 nem quebrar as
    asserções da wave 4. O botão age no passo ativo do stepper (rótulo por passo, custo por passo);
    há a linha explícita do Higgsfield (UI ilimitada) e, após import/geração, download + antes/depois."""
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    # o botão de CLI vive no passo 03, com marcador [extensão] e o slot de custo — sem painel 04
    assert 'id="btnBaseCli"' in html and ">Gerar via CLI<" in html
    assert 'id="baseCliCost"' in html and 'id="baseGenResult"' in html
    assert '<span class="pn">04</span>' not in html and html.count('<section class="panel">') == 3
    # a linha do Higgsfield (UI ilimitada) — o caminho não pago — aparece explícita na tela
    assert "Higgsfield (UI ilimitada)" in html and "importe aqui" in html
    # o botão age no PASSO ATIVO: o rótulo muda por passo (situação/rótulo/upscale)
    assert "gerarViaCli" in js and "updateCliButton" in js
    assert "`Gerar ${KINDS[step] || step} via CLI`" in js
    # custo REAL antes de pagar (upscale usa outro modelo → número por passo) via base/cost + confirmCost
    assert 'url("cost")' in js and "ui.confirmCost(" in js
    # trata CLI deslogado (custo null) com aviso claro, sem 500, mantendo o caminho de importação
    assert "cost.total == null" in js and "higgsfield auth login" in js
    # durante a geração: o modal de progresso honesto (progressJob) sobre base/generate + base/job
    assert "ui.progressJob(" in js and 'url("generate")' in js and 'url("job")' in js
    # depois de gerar/importar: download (<a download>) + antes/depois (origem da cadeia → resultado)
    assert "showResult" in js and 'class="link dl" download' in js
    assert "Modificação — antes → depois" in js and "originFor" in js
    # o fluxo de importação, o prompt e a junção mood×referência (#57) seguem intactos
    assert "ui.drop(" in js and "renderJunction" in js and 'url("import/upload")' in js


def test_view_panel01_ref_hero_and_cli(client):
    """base-painel01 (ADH-OS-20260828-22, wave 6 · frente D): o painel 01 ganha um PREVIEW GRANDE
    da referência selecionada (#baseRefHero) ocupando a largura útil, mantendo a tira compacta
    (#refGallery) como seletor — fim do espaço morto — e um botão "Gerar via CLI" que reusa o fluxo
    do painel 03 forçando kind:"situation", sem tocar o stepper. Sem novos painéis (segue com 3)."""
    html = client.get("/steps/base/view.html").text
    js = client.get("/steps/base/view.js").text
    # hero da referência: container no painel 01 + render dedicado no view.js; a tira compacta segue
    assert '<div id="baseRefHero" class="bs-refhero"></div>' in html
    assert '<div id="refGallery" class="gallery xs"></div>' in html
    assert "renderRefHero" in js and "(selecionada)" in js
    # CSS escopado `.bs-` da fatia (regra 6): hero de largura plena + tira sem o cap de 560px
    assert ".bs-refhero img{" in html and ".bs-refpick .gallery.xs{" in html
    assert "max-width:none" in html
    # a lógica de seleção não muda — só a apresentação (selectRef segue existindo e é só render)
    assert "function selectRef(" in js
    # botão "Gerar via CLI" no painel 01, com [extensão] e slot de custo próprio
    assert '<button id="btnBasePanel01Cli" class="primary">Gerar via CLI</button>' in html
    assert 'id="basePanel01CliCost"' in html
    # reusa gerarViaCli/genBody do painel 03 FORÇANDO a situação (independe do stepper)
    assert 'gerarViaCli("situation", $("#basePanel01CliCost"))' in js
    assert "function gerarViaCli(kind = step" in js and "function genBody(kind = step)" in js
    assert 'kind === "situation"' in js
    # o botão do painel 03 segue existindo e agindo no passo ativo (não regride)
    assert 'id="btnBaseCli"' in html and "() => gerarViaCli()" in js
    # sem painel novo: continuam os 3 painéis do curso
    assert html.count('<section class="panel">') == 3
    assert '<span class="pn">04</span>' not in html


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
    client.post(f"/api/projects/{pid}/base/brand", json={"name": "Gelo Zero", "description": "raio neon"})
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
    client.post(f"/api/projects/{pid}/base/brand", json={"name": "Gelo Zero"})
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
