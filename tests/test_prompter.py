"""O 'bot' de prompts (Claude CLI) — comando montado, parse do JSON, fallback e regras da aula 009."""
import json
import subprocess

import pytest

from studio.common import prompter


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
