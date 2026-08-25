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
    t = prompter.fallback_template("mood", {"product": "energy drink", "vibe": "snow neon"}, 1)
    assert t["source"] == "template" and "No product" in t["prompt"] and "stronger stylization" in t["prompt"]
    fixed = prompter.enforce_mood_rules({"prompt": "Blue snow at dusk"})
    assert "No product" in fixed["prompt"] and "No people" in fixed["prompt"] and "No text" in fixed["prompt"]
    assert prompter.enforce_mood_rules({"prompt": "x. No product, no people, no text."})["prompt"].count("No product") == 1
