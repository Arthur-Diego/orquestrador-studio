"""Ponte com o CLI da Higgsfield: montagem de flags e leitura defensiva de JSON (sem chamar o CLI)."""
from studio import higgsfield as hf


def test_params_map_to_cli_flags():
    args = hf._params({"prompt": "a", "aspect_ratio": "16:9", "image_references": ["x.png", "y.png"],
                       "sound": False, "count": 2, "empty": "", "none": None})
    assert args == ["--prompt", "a", "--aspect-ratio", "16:9", "--image-references", "x.png",
                    "--image-references", "y.png", "--sound", "false", "--count", "2"]


def test_flatten_and_pick_find_nested_values():
    flat = hf._flatten({"job": {"id": "j1", "results": [{"url": "https://cdn/x.png"}]}, "prompt": ""})
    assert hf._pick(flat, "id") == "j1"
    assert hf._pick(flat, "prompt") is None, "string vazia não conta"
    urls = {u for v in flat.values() if isinstance(v, str) for u in hf.IMG_URL_RE.findall(v)}
    assert urls == {"https://cdn/x.png"}


def test_json_parser_accepts_json_lines():
    assert hf._json('{"a":1}\n{"b":2}') == [{"a": 1}, {"b": 2}]
    assert hf._json("") is None


def test_status_without_cli(monkeypatch):
    monkeypatch.setattr(hf, "BIN", None)
    assert hf.status() == {"installed": False, "logged_in": False}


def test_status_not_logged_in(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/false")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (1, "", "Error: Not authenticated."))
    s = hf.status()
    assert s["installed"] and not s["logged_in"] and "Not authenticated" in s["error"]
