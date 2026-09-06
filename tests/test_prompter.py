"""O 'bot' de prompts (Claude CLI) — comando montado, parse do JSON, fallback e regras da aula 009."""
import json
import subprocess
from pathlib import Path

import pytest

from studio.common import clibin, prompter


def _fake_claude(payload: dict, calls: list):
    def run(args, capture_output, text, timeout):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "Sure.\n```json\n" + json.dumps(payload) + "\n```\n", "")
    return run


def test_from_images_builds_command_and_parses(monkeypatch, tmp_path):
    img = tmp_path / "vibe.png"
    img.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_claude({"prompt": "Icy blue snowfield at dusk", "negative": "text", "camera": "RED, 35mm", "notes_pt": "ok"}, calls))
    r = prompter.from_images("mood", [img], "bastante neon", {"product": "energy drink"})
    args = calls[0]
    assert args[0] == "/usr/bin/claude" and args[1] == "-p" and "--allowedTools" in args and "Read" in args
    assert str(img) in args[2] and "bastante neon" in args[2] and "energy drink" in args[2]
    assert r["prompt"] == "Icy blue snowfield at dusk" and r["source"] == "claude" and r["images"] == [str(img)]


def test_from_images_limits_and_validates(monkeypatch, tmp_path):
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    with pytest.raises(ValueError):
        prompter.from_images("mood", [], "x")
    with pytest.raises(FileNotFoundError):
        prompter.from_images("mood", [tmp_path / "nao.png"], "x")


def test_from_brief_parses_json_without_fence(monkeypatch):
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", lambda args, capture_output, text, timeout: (calls.append(args), subprocess.CompletedProcess(args, 0, '{"prompt": "Neon snow", "negative": "", "camera": "", "notes_pt": ""}', ""))[1])
    r = prompter.from_brief("mood", {"product": "soda", "vibe": "neon"})
    assert r["prompt"] == "Neon snow" and "--allowedTools" not in calls[0] and "soda" in calls[0][2]


def test_errors_are_runtime_errors(monkeypatch):
    monkeypatch.setattr(prompter, "BIN", None)
    with pytest.raises(RuntimeError, match="não encontrado"):
        prompter.from_brief("mood", {})
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "sem json aqui", ""))
    with pytest.raises(RuntimeError, match="JSON"):
        prompter.from_brief("mood", {})

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)
    monkeypatch.setattr(prompter.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="demorou"):
        prompter.from_brief("mood", {})


def test_fallback_template_and_mood_rules():
    """Aula 009: o mood board TEM o produto. Só "sem pessoas" é regra — e é escolha do usuário."""
    t = prompter.fallback_template("mood", {"product": "energy drink", "vibe": "snow neon"}, 1)
    assert t["source"] == "template" and "stronger stylization" in t["prompt"]
    low = t["prompt"].lower()
    assert "no product" not in low and "no logos" not in low and "no text" not in low
    assert "No people." in t["prompt"], "sugestão da aula, marcada por padrão"

    sem_regra = prompter.fallback_template("mood", {"product": "energy drink"}, 1, no_people=False)
    assert "no people" not in sem_regra["prompt"].lower()

    fixed = prompter.enforce_mood_rules({"prompt": "Blue snow at dusk"})
    assert "No people" in fixed["prompt"] and "No product" not in fixed["prompt"]
    assert prompter.enforce_mood_rules({"prompt": "x. No people."})["prompt"].count("No people") == 1
    intacto = prompter.enforce_mood_rules({"prompt": "Blue snow at dusk"}, no_people=False)
    assert intacto["prompt"] == "Blue snow at dusk", "nada entra no prompt sem o usuário pedir"


def test_mood_role_does_not_forbid_the_product():
    """M1: o papel do bot não pode mandar 'NO product/NO text/NO logos' (a aula não manda)."""
    role = prompter.ROLES["mood"].lower()
    assert "no product" not in role and "no logos" not in role and "no text" not in role
    assert "one single vibe" in role


def test_style_variants_have_a_single_source():
    """M8: a lista de variações de estilização vive só aqui (os módulos são reimportados
    por `studio_env`, então compare instâncias vindas do mesmo estado de importação)."""
    from studio.common import prompter as pr
    from studio.mood import service as mood
    assert mood._STYLE_VARIANTS is pr.STYLE_VARIANTS
    assert pr._STYLE_VARIANTS is pr.STYLE_VARIANTS


def test_explore_prompt_becomes_the_base_of_the_vibe_prompt():
    """M3: 'copiar o prompt dessa pessoa' (Explore) — o prompt colado é a base."""
    t = prompter.fallback_template("mood", {"product": "soda", "explore_prompt": "Neon snowfield at dusk"}, 1)
    assert t["prompt"].startswith("Neon snowfield at dusk.")
    assert "stronger stylization" in t["prompt"]


def test_bot_uses_opus_and_the_instructor_pattern(monkeypatch):
    """Pedido do dono do produto: Opus 4.8 e o padrão de prompt extraído do vídeo da aula 009."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_claude({"prompt": "x", "negative": "", "camera": "", "notes_pt": ""}, calls))
    prompter.from_brief("base", {"product": "energy drink"})
    args = calls[0]
    assert args[args.index("--model") + 1] == prompter.MODEL == "claude-opus-4-8"
    sent = args[2]
    for label in prompter.PROMPT_SECTIONS:
        assert label in sent, label
    assert "Canon EOS R5" in sent, "o exemplar do vídeo vai junto como referência de estrutura"
    for kind in ("mood", "base"):
        assert "Color grading:" in prompter.ROLES[kind]
    assert "Color grading:" not in prompter.ROLES["motion"], "vídeo tem padrão próprio (aula 012)"


def test_split_sections_parses_paragraph_and_five_lines():
    """base-prompt-provenance: o parser separa o parágrafo das 5 linhas nomeadas do padrão do bot."""
    parsed = prompter.split_sections(prompter.EXAMPLE_PROMPT)
    assert set(parsed["sections"]) == {"Camera", "Lighting", "Composition", "Color grading", "Style"}
    assert "Ultra-realistic commercial product photography" in parsed["paragraph"]
    assert "Camera:" not in parsed["paragraph"] and "\n" not in parsed["sections"]["Composition"]
    assert parsed["sections"]["Camera"].startswith("Canon EOS R5")
    assert parsed["sections"]["Composition"] == "clean, minimal, premium, centered hero shot."


def test_split_sections_is_robust_to_missing_lines():
    """Degradação graciosa (FDD §1): linha nomeada ausente não quebra — só não entra em `sections`."""
    prompt = ("A dense paragraph about the product.\n\n"
              "Camera: RED Komodo, 50mm.\nComposition: centered hero shot.")
    parsed = prompter.split_sections(prompt)
    assert parsed["paragraph"] == "A dense paragraph about the product."
    assert set(parsed["sections"]) == {"Camera", "Composition"}
    assert "Lighting" not in parsed["sections"]
    # Prompt sem nenhuma linha nomeada: tudo vira parágrafo, `sections` vazio.
    solto = prompter.split_sections("Just a single sentence prompt. Photorealistic.")
    assert solto["sections"] == {} and solto["paragraph"].startswith("Just a single sentence")


def test_provenance_maps_each_line_to_its_source():
    """FDD §1: Composição→referência; Lighting/Color grading/Style→mood; Camera→técnico."""
    prov = prompter.provenance(prompter.EXAMPLE_PROMPT)
    assert prov["paragraph"].startswith("Ultra-realistic")
    by_label = {p["label"]: p["from"] for p in prov["parts"]}
    assert by_label == {"Camera": "technical", "Lighting": "mood", "Composition": "reference",
                        "Color grading": "mood", "Style": "mood"}
    # partes na ordem em que aparecem no prompt e cada uma com o seu texto
    assert [p["label"] for p in prov["parts"]] == list(prompter.SECTION_NAMES)
    assert all(p["text"] for p in prov["parts"])
    froms = {p["from"] for p in prov["parts"]}
    assert froms == {"reference", "mood", "technical"}
    # sem as 5 linhas → sem partes, mas o retorno mantém o formato (o parágrafo é o prompt inteiro)
    vazio = prompter.provenance("Single sentence, no named lines.")
    assert vazio["parts"] == [] and vazio["paragraph"] == "Single sentence, no named lines."


def test_fallback_follows_the_pattern_too():
    for kind in ("mood", "base"):
        t = prompter.fallback_template(kind, {"product": "energy drink", "vibe": "snow neon"})
        lines = t["prompt"].split("\n")
        assert lines[0] and lines[1] == "" and [ln.split(":")[0] + ":" for ln in lines[2:]] == list(prompter.PROMPT_SECTIONS)
    sem = prompter.fallback_template("base", {"product": "x"}, no_people=False)
    assert "no people" not in sem["prompt"].lower()


# ---------- presets de realismo `[extensão]` (nenhuma aula ensina presets; tudo opt-in) ----------
def test_realism_presets_have_the_five_ids_and_the_full_shape():
    """T1.1: estrutura do catálogo — 5 ids, campos obrigatórios e um único `default: true`."""
    assert set(prompter.REALISM_PRESETS) == {"documentary-street", "arri-natural-narrative",
                                             "red-commercial-precision", "sony-venice-night",
                                             "anamorphic-film-look"}
    for pid, p in prompter.REALISM_PRESETS.items():
        assert p["id"] == pid, "o id do valor bate com a chave do dict"
        assert p["name"] and p["desc_pt"] and p["light"] and p["grade"] and p["fidelity"]
        assert set(p["rig"]) == {"camera", "lens", "format", "focal", "aperture"}
        assert all(p["rig"][k] for k in p["rig"])
        assert isinstance(p["negative"], list) and p["negative"]
    marcados = [pid for pid, p in prompter.REALISM_PRESETS.items() if p.get("default")]
    assert marcados == ["documentary-street"], "exatamente um default, e é o documentário"


def test_realism_presets_transcribe_the_rig_table():
    """T1.2: os rigs são a transcrição da tabela da skill de origem, não invenção do código."""
    arri = prompter.REALISM_PRESETS["arri-natural-narrative"]["rig"]
    assert arri["camera"] == "ARRI Alexa Mini LF"
    assert arri["lens"] == "Cooke S4" and arri["format"] == "Large Format"
    assert prompter.REALISM_PRESETS["documentary-street"]["rig"]["camera"] == "Blackmagic Pocket 6K Pro"


def test_preset_block_carries_the_rig_and_never_opens_a_new_section():
    """T1.3: bloco curto (< 80 palavras) que PREENCHE as 5 linhas do padrão, sem criar seção nova."""
    block = prompter.preset_block("red-commercial-precision")
    assert "RED V-Raptor" in block and "Zeiss Supreme Prime" in block
    assert len(block.split()) < 80
    for bloco in map(prompter.preset_block, prompter.REALISM_PRESETS):
        linhas = bloco.split("\n")
        for label in prompter.PROMPT_SECTIONS:
            assert not any(ln.strip().startswith(label) for ln in linhas), label
        assert len(bloco.split()) < 80


def test_preset_block_raises_on_unknown_id():
    """T1.4: id desconhecido é KeyError (os routers convertem em 422)."""
    with pytest.raises(KeyError):
        prompter.preset_block("nao-existe")


def test_from_brief_without_preset_is_byte_identical(monkeypatch):
    """T1.5: invariante do gate W3 — sem preset, o texto enviado ao CLI é o de sempre."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_claude({"prompt": "x", "negative": "", "camera": "", "notes_pt": ""}, calls))
    brief = {"product": "energy drink", "vibe": "snow neon"}
    sem = prompter.from_brief("mood", brief)
    explicito = prompter.from_brief("mood", brief, preset=None)
    assert calls[0][2] == calls[1][2], "campo ausente e `preset=None` mandam o MESMO prompt"
    cameras = {p["rig"]["camera"] for p in prompter.REALISM_PRESETS.values()}
    assert not any(c in calls[0][2] for c in cameras), "nenhum rig do catálogo vaza sem preset"
    assert sem["preset"] is None and explicito["preset"] is None


def test_from_brief_with_preset_injects_the_rig(monkeypatch):
    """T1.6: com preset, o rig completo vai no prompt e o id volta na resposta."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_claude({"prompt": "x", "negative": "", "camera": "", "notes_pt": ""}, calls))
    r = prompter.from_brief("mood", {"product": "energy drink"}, preset="arri-natural-narrative")
    sent = calls[0][2]
    assert "ARRI Alexa Mini LF" in sent and "Cooke S4" in sent and "Large Format" in sent
    assert r["preset"] == "arri-natural-narrative"


def test_from_images_preset_is_opt_in_and_keeps_the_image_contract(monkeypatch, tmp_path):
    """T1.7: mesmo comportamento com imagens; limite de 4 e `--allowedTools Read` inalterados."""
    img = tmp_path / "vibe.png"
    img.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_claude({"prompt": "x", "negative": "", "camera": "", "notes_pt": ""}, calls))
    sem = prompter.from_images("base", [img], "bastante neon")
    cameras = {p["rig"]["camera"] for p in prompter.REALISM_PRESETS.values()}
    assert not any(c in calls[0][2] for c in cameras) and sem["preset"] is None
    com = prompter.from_images("base", [img], "bastante neon", preset="sony-venice-night")
    assert "Sony Venice 2" in calls[1][2] and com["preset"] == "sony-venice-night"
    for args in calls:
        assert "--allowedTools" in args and args[args.index("--allowedTools") + 1] == "Read"
    cinco = [tmp_path / f"i{i}.png" for i in range(5)]
    for p in cinco:
        p.write_bytes(b"x")
    r = prompter.from_images("base", cinco, preset="sony-venice-night")
    assert r["images"] == [str(p) for p in cinco[:prompter.MAX_IMAGES]]
    assert str(cinco[4]) not in calls[2][2], "a 5ª imagem continua fora do prompt"


def test_preset_negatives_merge_without_duplicating(monkeypatch):
    """T1.8: os negativos do preset entram no campo `negative` sem repetir nem descartar nada."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_claude({"prompt": "x", "negative": "text, plastic skin",
                                      "camera": "", "notes_pt": ""}, calls))
    com = prompter.from_brief("mood", {}, preset="documentary-street")
    assert "text" in com["negative"] and "CGI look" in com["negative"]
    assert com["negative"].count("plastic skin") == 1, "não repete o que o Claude já pediu"
    sem = prompter.from_brief("mood", {})
    assert sem["negative"] == "text, plastic skin", "sem preset, sai como o CLI devolveu"


def test_fallback_template_with_preset_fills_the_technical_lines():
    """T1.9: sem Claude, o preset explícito preenche Camera/Lighting/Color grading."""
    t = prompter.fallback_template("base", {"product": "energy drink", "vibe": "snow neon"},
                                   preset="red-commercial-precision")
    linhas = t["prompt"].split("\n")
    camera = next(ln for ln in linhas if ln.startswith("Camera:"))
    grading = next(ln for ln in linhas if ln.startswith("Color grading:"))
    assert "RED V-Raptor" in camera and "Zeiss Supreme Prime" in camera
    assert "precise color" in grading and "high micro-contrast" in grading


def test_fallback_template_without_preset_is_the_course_template():
    """T1.10: sem preset, o template da aula continua sem uma vírgula de diferença."""
    brief = {"product": "energy drink", "vibe": "snow neon"}
    assert prompter.fallback_template("mood", brief) == prompter.fallback_template("mood", brief, preset=None)
    assert "RED Komodo 6K, 50mm lens, T2.8" in prompter.fallback_template("mood", brief)["prompt"]


def test_provenance_survives_a_prompt_generated_with_preset(monkeypatch):
    """T1.11: preset não cria seção nova — `split_sections`/`provenance` seguem iguais."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_claude({"prompt": prompter.EXAMPLE_PROMPT, "negative": "",
                                      "camera": "", "notes_pt": ""}, calls))
    r = prompter.from_brief("base", {"product": "energy drink"}, preset="anamorphic-film-look")
    parsed = prompter.split_sections(r["prompt"])
    assert set(parsed["sections"]) == set(prompter.SECTION_NAMES)
    assert prompter.provenance(r["prompt"]) == prompter.provenance(prompter.EXAMPLE_PROMPT)
    assert len(prompter.provenance(r["prompt"])["parts"]) == 5


# ---------- roteiro de storyboard `[extensão]` (ADR-025; nenhuma aula ensina roteiro por LLM) ----------
ARCOS5 = ["comeco", "descoberta", "acao", "acao", "desfecho"]


def _scene(n: int, **over) -> dict:
    """Cena válida do fake, no formato que `SCRIPT_OUTPUT_SPEC` pede."""
    scene = {"n": n, "arc": "acao",
             "text": f"Cena {n}: o personagem avança pela trilha com a lata presa à mochila.",
             "image_prompt": (f"A cinematic photograph of scene {n}, shot on Blackmagic Pocket 6K Pro "
                              "with a Cooke S4 lens at T2.8, Super 35."),
             "negative": "plastic skin, HDR glow"}
    scene.update(over)
    return scene


def _fake_script_claude(scenes: list, calls: list, notes: str = "Arco fechado no desfecho."):
    """Fake do Claude CLI para o roteiro: registra `args`/`timeout` e devolve a fence ```json."""
    body = json.dumps({"scenes": scenes, "notes_pt": notes}, ensure_ascii=False)

    def run(args, capture_output, text, timeout):
        calls.append({"args": args, "timeout": timeout})
        return subprocess.CompletedProcess(args, 0, "Segue o roteiro.\n```json\n" + body + "\n```\n", "")
    return run


def _img(tmp_path, name="base_final.png"):
    p = tmp_path / name
    p.write_bytes(b"x")
    return p


def test_script_generates_the_full_screenplay(monkeypatch, tmp_path):
    """T1.1: roteiro feliz com preset — N cenas, `source` claude, `seconds` e `n` renumerado."""
    base = _img(tmp_path)
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 6)], calls))
    r = prompter.script(images=[base], brief={"product": "energy drink", "vibe": "snow neon"},
                        preset="documentary-street", count=5, arcs=ARCOS5, model_target="nano_banana_2")
    assert len(r["scenes"]) == 5 and r["count"] == 5
    assert r["source"] == "claude" and isinstance(r["seconds"], float)
    assert r["preset"] == "documentary-street" and r["model_target"] == "nano_banana_2"
    assert [s["n"] for s in r["scenes"]] == [1, 2, 3, 4, 5]
    assert all(s["text"] and s["image_prompt"] for s in r["scenes"])
    assert r["notes_pt"] == "Arco fechado no desfecho." and r["images"] == [str(base)]
    assert "--allowedTools" in calls[0]["args"], "o Claude precisa da tool Read para ver as imagens"


def test_script_prompt_carries_the_preset_rig(monkeypatch, tmp_path):
    """T1.2 `[cross-feature]`: o rig do preset escolhido vai LITERALMENTE no pedido ao CLI."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 6)], calls))
    prompter.script(images=[_img(tmp_path)], brief={"product": "energy drink"},
                    preset="documentary-street", count=5, arcs=ARCOS5)
    sent = calls[0]["args"][2]
    p = prompter.REALISM_PRESETS["documentary-street"]
    assert p["rig"]["camera"] in sent and p["rig"]["lens"] in sent and p["rig"]["format"] in sent
    assert p["light"] in sent and p["grade"] in sent and p["fidelity"] in sent
    for termo in p["negative"]:
        assert termo in sent, termo


def test_script_without_preset_sends_no_rig(monkeypatch, tmp_path):
    """T1.3: `preset=None` não injeta bloco de realismo nenhum — o roteiro sai sem rig fixo."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 6)], calls))
    r = prompter.script(images=[_img(tmp_path)], brief={"product": "energy drink"},
                        preset=None, count=5, arcs=ARCOS5)
    sent = calls[0]["args"][2]
    assert "REALISM PRESET" not in sent
    cameras = {pr["rig"]["camera"] for pr in prompter.REALISM_PRESETS.values()}
    assert not any(c in sent for c in cameras), "nenhum rig do catálogo vaza sem preset"
    assert len(r["scenes"]) == 5 and r["preset"] is None


def test_script_arcs_come_from_the_server(monkeypatch, tmp_path):
    """T1.4: o arco é decisão do servidor (`scene_arc`) — o que o modelo devolveu é descartado."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_script_claude([_scene(i, arc="acao") for i in range(1, 6)], calls))
    r = prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)
    assert [s["arc"] for s in r["scenes"]] == ARCOS5


def test_script_refuses_to_invent_missing_scenes(monkeypatch, tmp_path):
    """T1.5: cenas de menos é erro — jamais completar o roteiro com conteúdo determinístico."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 4)], calls))
    with pytest.raises(RuntimeError, match="5 cenas pedidas, 3 recebidas"):
        prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)


def test_script_rejects_a_response_without_json(monkeypatch, tmp_path):
    """T1.6: texto livre sem fence vira erro claro, não `KeyError`/`IndexError` cru."""
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        lambda args, capture_output, text, timeout:
                        subprocess.CompletedProcess(args, 0, "Não consegui escrever o roteiro.", ""))
    with pytest.raises(RuntimeError, match="não devolveu JSON do roteiro"):
        prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)


def test_script_rejects_a_scene_without_image_prompt(monkeypatch, tmp_path):
    """T1.7: cena sem `image_prompt` derruba o roteiro inteiro, citando qual cena."""
    cenas = [_scene(i) for i in range(1, 6)]
    cenas[2]["image_prompt"] = "   "
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude(cenas, calls))
    with pytest.raises(RuntimeError, match="cena 3 do roteiro sem 'image_prompt'"):
        prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)
    cenas[2]["image_prompt"] = "ok"
    cenas[4]["text"] = ""
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude(cenas, calls))
    with pytest.raises(RuntimeError, match="cena 5 do roteiro sem 'text'"):
        prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)


def test_script_cuts_extra_scenes(monkeypatch, tmp_path):
    """T1.8: cenas a mais são cortadas em `count`, com `n` renumerado 1..count."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 6)], calls))
    r = prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=3,
                        arcs=["comeco", "descoberta", "desfecho"])
    assert [s["n"] for s in r["scenes"]] == [1, 2, 3] and r["count"] == 3


def test_script_respects_the_image_ceiling(monkeypatch, tmp_path):
    """T1.9: teto de `MAX_IMAGES` (4) — a 5ª e a 6ª imagem não entram no prompt nem no retorno."""
    seis = [_img(tmp_path, f"i{i}.png") for i in range(6)]
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 6)], calls))
    r = prompter.script(images=seis, brief={}, preset=None, count=5, arcs=ARCOS5)
    sent = calls[0]["args"][2]
    assert r["images"] == [str(p) for p in seis[:prompter.MAX_IMAGES]]
    assert sum(1 for p in seis if str(p) in sent) == prompter.MAX_IMAGES
    assert str(seis[4]) not in sent and str(seis[5]) not in sent


def test_script_validates_that_every_image_exists(monkeypatch, tmp_path):
    """T1.10: caminho inexistente é `FileNotFoundError` (mesmo contrato de `from_images`)."""
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    with pytest.raises(FileNotFoundError):
        prompter.script(images=[_img(tmp_path), tmp_path / "nao.png"], brief={}, preset=None,
                        count=5, arcs=ARCOS5)


def test_script_uses_its_own_timeout(monkeypatch, tmp_path):
    """T1.11: o roteiro tem teto próprio de 300 s; o prompt único continua em 180 s."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 6)], calls))
    prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)
    assert prompter.SCRIPT_TIMEOUT_S == 300 and prompter.TIMEOUT_S == 180
    assert calls[0]["timeout"] == prompter.SCRIPT_TIMEOUT_S


def test_script_without_the_cli_is_a_runtime_error(monkeypatch, tmp_path):
    """T1.12: sem Claude CLI o roteiro não existe (a tradução para 409 é do serviço da etapa)."""
    monkeypatch.setattr(prompter, "BIN", None)
    with pytest.raises(RuntimeError, match="não encontrado"):
        prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=5, arcs=ARCOS5)


def test_script_is_strictly_additive_to_the_single_prompt_path(monkeypatch, tmp_path):
    """T1.13: regressão de R1 — papéis e caminho do prompt único intocados pelo roteiro.

    `character` `[extensão]` (ADR-039) é aditivo, como `script`: não altera mood/base/motion nem o
    caminho do prompt único; por isso entra no conjunto esperado sem tocar as demais asserções.
    `keyframe` `[extensão]` (Wave 11 · F06, §5.12) entra pelo mesmo motivo: papel novo, aditivo,
    que reusa o BRIEFING do roteiro e o `_parse` do prompt único sem alterar nenhum dos dois."""
    assert set(prompter.ROLES) == {"mood", "base", "motion", "script", "character", "keyframe"}
    assert "one single vibe" in prompter.ROLES["mood"] and prompter.PROMPT_FORMAT in prompter.ROLES["mood"]
    assert prompter.PROMPT_FORMAT in prompter.ROLES["base"]
    assert "40–90 words" in prompter.ROLES["motion"] and "Color grading:" not in prompter.ROLES["motion"]
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_claude({"prompt": "x", "negative": "", "camera": "", "notes_pt": ""}, calls))
    prompter.from_brief("mood", {"product": "energy drink"})
    prompter.from_images("base", [_img(tmp_path)], "bastante neon")
    for args in calls:
        assert prompter.OUTPUT_SPEC in args[2] and prompter.SCRIPT_OUTPUT_SPEC not in args[2]
        assert prompter.ROLES["script"] not in args[2]
        assert args[args.index("--model") + 1] == prompter.MODEL


# ---------- `[extensão]` roteiro-por-cena (ADR-028): N fotos por cena INFERIDO + fotos coesas ----------
def _scene_shots(n: int, shots: list[str], arc: str = "acao") -> dict:
    """Cena que já traz `shots`/`shot_prompts` (o formato novo do `SCRIPT_OUTPUT_SPEC`)."""
    return {"n": n, "arc": arc, "text": f"Cena {n}: o personagem age.",
            "shots": len(shots), "shot_prompts": shots, "image_prompt": shots[0],
            "negative": "plastic skin"}


def test_script_output_spec_asks_for_inferred_shots_per_scene():
    """T1.14 (ADR-028): o output spec pede `shots` (na faixa) e `shot_prompts` coesos por cena."""
    spec = prompter.SCRIPT_OUTPUT_SPEC
    assert '"shots"' in spec and '"shot_prompts"' in spec
    assert str(prompter.SHOTS_MIN) in spec and str(prompter.SHOTS_MAX) in spec
    assert prompter.SHOTS_MIN == 3 and prompter.SHOTS_MAX == 6
    assert "VISUALLY COHERENT" in spec, "as fotos de uma cena têm de ser pedidas coesas entre si"


def test_script_keeps_the_inferred_shots_of_each_scene(monkeypatch, tmp_path):
    """T1.15: o número de fotos vem do MODELO (por cena), e cada `shot_prompt` é preservado."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    cenas = [_scene_shots(1, ["ph 1a", "ph 1b", "ph 1c"]),           # cena simples: 3 fotos
             _scene_shots(2, ["ph 2a", "ph 2b", "ph 2c", "ph 2d", "ph 2e"])]  # cena densa: 5 fotos
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude(cenas, calls))
    r = prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=2,
                        arcs=["comeco", "desfecho"])
    assert [s["shots"] for s in r["scenes"]] == [3, 5]
    assert r["scenes"][0]["shot_prompts"] == ["ph 1a", "ph 1b", "ph 1c"]
    assert r["scenes"][1]["shot_prompts"][-1] == "ph 2e"
    # compat: `image_prompt` continua sendo a PRIMEIRA foto da cena.
    assert r["scenes"][0]["image_prompt"] == "ph 1a"


def test_script_clamps_shot_prompts_to_the_ceiling(monkeypatch, tmp_path):
    """T1.16: mais fotos que o teto → cortadas em `SHOTS_MAX`; `shots` acompanha o que sobrou."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    demais = [f"ph {i}" for i in range(9)]                            # 9 fotos → teto 6
    monkeypatch.setattr(prompter.subprocess, "run",
                        _fake_script_claude([_scene_shots(1, demais)], calls))
    r = prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=1, arcs=["comeco"])
    assert r["scenes"][0]["shots"] == prompter.SHOTS_MAX
    assert len(r["scenes"][0]["shot_prompts"]) == prompter.SHOTS_MAX


def test_script_falls_back_to_one_shot_without_shot_prompts(monkeypatch, tmp_path):
    """T1.17 (compat): roteiro sem `shot_prompts` (formato antigo) vira uma foto = `image_prompt`."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_script_claude([_scene(i) for i in range(1, 3)], calls))
    r = prompter.script(images=[_img(tmp_path)], brief={}, preset=None, count=2,
                        arcs=["comeco", "desfecho"])
    for s in r["scenes"]:
        assert s["shots"] == 1 and s["shot_prompts"] == [s["image_prompt"]]


# ==========================================================================================
# `[extensão]` Wave 11 · F06 (FDD §5.9/§5.10) — diagnóstico do binário `claude`. O `BIN` resolvido
# em import time era a causa-raiz do defeito 1 do PRD: instalar o CLI com o Studio no ar não
# adiantava nada. Todo teste aqui é sem rede e sem subprocess (ADR-008).
# ==========================================================================================
DIAG_KEYS = {"name", "available", "path", "searched_path", "checked_at", "hint"}


def test_clibin_describe_reports_missing_binary_with_a_hint():
    """F06.1: sem binário, as seis chaves, `available: False` e uma dica de como resolver."""
    d = clibin.describe("claude", None)
    assert set(d) == DIAG_KEYS
    assert d["name"] == "claude" and d["available"] is False and d["path"] is None
    assert d["hint"] and "run.sh" in d["hint"]
    # Com binário resolvido não há conselho a dar: `hint` fica vazia mesmo se for passada.
    ok = clibin.describe("claude", "/x/claude", hint="ignorada")
    assert set(ok) == DIAG_KEYS
    assert ok["available"] is True and ok["path"] == "/x/claude" and ok["hint"] == ""


def test_clibin_describe_reports_the_path_of_this_process(monkeypatch):
    """F06.2: `searched_path` é o PATH DESTE processo — é ele que decide, não o do terminal."""
    monkeypatch.setenv("PATH", "/so/isto")
    assert clibin.describe("claude", None)["searched_path"] == "/so/isto"
    monkeypatch.delenv("PATH", raising=False)
    assert clibin.describe("claude", None)["searched_path"] == ""


def test_cli_status_describes_the_current_bin_without_touching_the_path(monkeypatch):
    """F06.3: sem `refresh`, `cli_status` só descreve o `BIN` atual — o monkeypatch de `BIN`
    continua sendo o jeito de fingir o CLI nos testes (ADR-008)."""
    monkeypatch.setattr(prompter, "BIN", None)
    monkeypatch.setattr(prompter.clibin, "which", lambda name="claude": "/nao/deveria/ser/chamado")
    ausente = prompter.cli_status()
    assert set(ausente) == DIAG_KEYS
    assert ausente["available"] is False and ausente["path"] is None and prompter.BIN is None

    monkeypatch.setattr(prompter, "BIN", "/x/claude")
    presente = prompter.cli_status()
    assert presente["available"] is True and presente["path"] == "/x/claude"


def test_cli_status_refresh_reassigns_bin_without_restarting_the_process(monkeypatch):
    """F06.4 (critério A2): o CLI instalado DEPOIS de o servidor subir passa a valer com
    `refresh=True` — é isso que faz o botão "Verificar de novo" funcionar sem restart."""
    monkeypatch.setattr(prompter, "BIN", None)
    monkeypatch.setattr(prompter.clibin, "which", lambda name="claude": "/novo/claude")
    d = prompter.cli_status(refresh=True)
    assert d["available"] is True and d["path"] == "/novo/claude"
    assert prompter.BIN == "/novo/claude"          # o módulo-global foi REATRIBUÍDO
    assert prompter.available() is True            # e `available()` enxerga o binário novo


def test_available_still_reads_bin_after_cli_status(monkeypatch):
    """F06.5: `available()` continua sendo `BIN is not None` — nenhuma chamada existente muda."""
    monkeypatch.setattr(prompter, "BIN", "/x/claude")
    prompter.cli_status()
    assert prompter.available() is True
    monkeypatch.setattr(prompter.clibin, "which", lambda name="claude": None)
    prompter.cli_status(refresh=True)
    assert prompter.BIN is None and prompter.available() is False


# ------------------------------------------------------------------------------------------
# `run.sh` (critério A4): inspeção do script, sem subir servidor e sem subprocess (ADR-008).
# ------------------------------------------------------------------------------------------
def _run_sh_path_block() -> str:
    """O trecho de `run.sh` que monta o PATH, do `for` até o `export PATH` (sem subir o uvicorn)."""
    src = (Path(__file__).resolve().parents[1] / "run.sh").read_text()
    ini = src.index("for _d in")
    fim = src.index("export PATH") + len("export PATH")
    return src[ini:fim]


def _path_resultante(herdado: str, home: str) -> str:
    """Roda SÓ o bloco de PATH num `sh` limpo e devolve o PATH que ele produz.

    Executar em vez de inspecionar o texto: a asserção textual antiga (`valor.startswith('"$PATH')`)
    aprovava qualquer expansão que começasse com `$PATH` e reprovava a correção do elemento vazio,
    ou seja, media a FORMA do script em vez do que ele faz (rodada de review 001, issue_006)."""
    import subprocess
    script = _run_sh_path_block() + '\nprintf "%s" "$PATH"\n'
    r = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True,
                       env={"PATH": herdado, "HOME": home} if herdado else {"HOME": home})
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_run_sh_appends_user_bin_dirs_after_the_inherited_path(tmp_path):
    """Critério A4: `$HOME/.local/bin` entra, e o PATH do usuário continua NA FRENTE."""
    home = str(tmp_path)
    got = _path_resultante("/usr/bin:/bin", home)
    assert got.startswith("/usr/bin:/bin"), f"prepend proibido (FDD §10, Risco 6): {got}"
    assert f"{home}/.local/bin" in got.split(":")


def test_run_sh_never_puts_the_current_directory_on_the_path(tmp_path):
    """Um elemento VAZIO de PATH é o diretório atual no POSIX — e `run.sh` já fez `cd` no repo.

    Regressão da rodada de review 001 (issue_006): com o PATH herdado vazio — o caso `env -i`, que
    é justamente o cenário "fora de um shell interativo" que o bloco existe para cobrir — o
    `PATH="$PATH:$_d"` produzia um dois-pontos INICIAL, e qualquer arquivo com nome de binário na
    raiz do repositório virava executável por nome para o processo do servidor."""
    home = str(tmp_path)
    for herdado in ("", "/usr/bin:/bin"):
        got = _path_resultante(herdado, home)
        assert "" not in got.split(":"), f"elemento vazio (= diretório atual) no PATH: {got!r}"
        assert not got.startswith(":") and not got.endswith(":") and "::" not in got


def test_run_sh_does_not_duplicate_a_dir_the_user_already_has(tmp_path):
    """Diretório já presente fica ONDE o usuário o pôs — o `case` de dedup existe para isso."""
    home = str(tmp_path)
    got = _path_resultante(f"{home}/.local/bin:/usr/bin", home)
    assert got.split(":").count(f"{home}/.local/bin") == 1
    assert got.startswith(f"{home}/.local/bin:/usr/bin")


# ------------------------------------------------------------------------------------------
# `[extensão]` Wave 11 · F06 (FDD §5.12, Risco 5): papel `keyframe` — UM prompt de imagem por foto.
# Todo teste finge o binário `claude` (`prompter.BIN` + `subprocess.run`), sem rede (ADR-008).
# ------------------------------------------------------------------------------------------
def _keyframe_fake(calls: list, negative="plastic skin"):
    """Bot OBEDIENTE do papel `keyframe`: devolve, dentro do `prompt`, o rig que lhe foi exigido.

    É assim que o teste mede o PROMPTER: se `script_preset_block` não entrar na montagem, não há
    rig no prompt enviado e o rig não volta no prompt devolvido (Risco 5 do FDD)."""
    import re as _re

    def run(args, capture_output=True, text=True, timeout=None, **kw):
        prompt = args[2]
        calls.append({"args": args, "prompt": prompt, "timeout": timeout})
        rig = _re.search(r"MANDATORY RIG, IDENTICAL IN EVERY SCENE: (.+?) — write", prompt, _re.S)
        rig_text = rig.group(1) if rig else "no fixed rig"
        body = json.dumps({"prompt": f"A lone courier holds the can at chest height. Shot on {rig_text}.",
                           "negative": negative, "camera": "irrelevante", "notes_pt": "duas linhas"})
        return subprocess.CompletedProcess(args, 0, "Segue.\n```json\n" + body + "\n```\n", "")

    return run


def test_keyframe_role_shares_the_briefing_order_with_the_script(monkeypatch, tmp_path):
    """Risco 5: os dois papéis citam a MESMA ordem de briefing, vinda da constante compartilhada.

    A prova de que não é texto duplicado é a constante estar literalmente dentro dos dois papéis —
    editar `BRIEFING_ORDER` muda os dois de uma vez, que é o ponto da mitigação."""
    assert prompter.BRIEFING_ORDER in prompter.ROLES["script"]
    assert prompter.BRIEFING_ORDER in prompter.ROLES["keyframe"]
    # E o hint de modelo sai do MESMO mapa do roteiro, pelo mesmo acessor.
    assert prompter.model_hint("nano_banana_2") == prompter.SCRIPT_MODEL_HINTS["nano_banana_2"]
    assert prompter.model_hint("modelo-que-nao-existe") == prompter._SCRIPT_MODEL_HINT_FALLBACK

    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _keyframe_fake(calls))
    prompter.keyframe([_img(tmp_path, "foto.png")], {"product": "energy drink"})
    enviado = calls[0]["prompt"]
    assert prompter.ROLES["keyframe"] in enviado and prompter.KEYFRAME_OUTPUT_SPEC in enviado
    assert prompter.model_hint("nano_banana_2") in enviado
    # Caminho do prompt ÚNICO: nada do roteiro (papel, output spec, timeout de 300 s) entra aqui.
    assert prompter.ROLES["script"] not in enviado and prompter.SCRIPT_OUTPUT_SPEC not in enviado
    assert calls[0]["timeout"] == prompter.TIMEOUT_S


def test_keyframe_returns_one_prompt_and_carries_the_preset_rig_literally(monkeypatch, tmp_path):
    """§5.12 + Risco 5: contrato de retorno e rig LITERAL no prompt devolvido quando há preset."""
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _keyframe_fake(calls))

    sem = prompter.keyframe([_img(tmp_path, "foto.png")], {"product": "energy drink"})
    assert set(sem) == {"prompt", "negative", "source", "seconds", "preset"}
    assert sem["source"] == "claude" and sem["preset"] is None and sem["prompt"].strip()
    assert isinstance(sem["seconds"], float)
    # Sem preset, nenhum bloco de rig entra no prompt enviado (invariante 7 do gate W3).
    assert "MANDATORY RIG" not in calls[0]["prompt"]

    com = prompter.keyframe([_img(tmp_path, "foto.png")], {"product": "energy drink"},
                            preset="documentary-street")
    rig = prompter.REALISM_PRESETS["documentary-street"]["rig"]
    assert com["preset"] == "documentary-street"
    for parte in (rig["camera"], rig["lens"], rig["format"]):
        assert parte in com["prompt"], parte
    # O bloco do rig é o MESMO do roteiro (reuso de `script_preset_block`, não uma segunda cópia).
    assert prompter.script_preset_block("documentary-street") in calls[1]["prompt"]
    # E os negativos do catálogo entram no campo `negative`, como em todo caminho com preset.
    for termo in prompter.REALISM_PRESETS["documentary-street"]["negative"]:
        assert termo in com["negative"], termo


def test_keyframe_without_the_cli_raises_for_the_caller_to_fall_back(monkeypatch, tmp_path):
    """§5.12: o fallback é do SERVIÇO, não do prompter — sem CLI o erro SOBE, não vira texto."""
    monkeypatch.setattr(prompter, "BIN", None)
    with pytest.raises(RuntimeError):
        prompter.keyframe([_img(tmp_path, "foto.png")], {"product": "energy drink"})

    # Falha do bot (returncode ≠ 0) também sobe: o prompter nunca inventa prompt por conta própria.
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "boom"))
    with pytest.raises(RuntimeError):
        prompter.keyframe([_img(tmp_path, "foto.png")], {"product": "energy drink"})

    # Foto inexistente é erro do chamador, antes de qualquer subprocess.
    with pytest.raises(FileNotFoundError):
        prompter.keyframe([tmp_path / "nao-existe.png"], {})
