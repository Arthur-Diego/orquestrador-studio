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


def test_fallback_follows_the_pattern_too():
    for kind in ("mood", "base"):
        t = prompter.fallback_template(kind, {"product": "energy drink", "vibe": "snow neon"})
        lines = t["prompt"].split("\n")
        assert lines[0] and lines[1] == "" and [ln.split(":")[0] + ":" for ln in lines[2:]] == list(prompter.PROMPT_SECTIONS)
    sem = prompter.fallback_template("base", {"product": "x"}, no_people=False)
    assert "no people" not in sem["prompt"].lower()
