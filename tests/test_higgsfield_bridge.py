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
    hf.reset_status_cache()
    monkeypatch.setattr(hf, "BIN", None)
    assert hf.status() == {"installed": False, "logged_in": False}


def test_status_not_logged_in(monkeypatch):
    hf.reset_status_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/false")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (1, "", "Error: Not authenticated."))
    s = hf.status()
    assert s["installed"] and not s["logged_in"] and "Not authenticated" in s["error"]


def _fake_run(payload, code=0):
    import json
    return lambda args, timeout=120: (code, json.dumps(payload), "")


def test_history_images_extracts_urls_defensively(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    payload = {"items": [
        {"id": "j1", "job_type": "nano_banana_2", "prompt": "vibe", "results": [{"url": "https://cdn.x/a.png"}, {"url": "https://cdn.x/b.jpg?x=1"}]},
        {"id": "j2", "job_type": "kling3_0", "results": [{"url": "https://cdn.x/v.mp4"}]},   # sem imagem → ignorado
        "lixo",
    ]}
    monkeypatch.setattr(hf, "_run", _fake_run(payload))
    jobs = hf.history_images(10)
    assert [j["id"] for j in jobs] == ["j1"]
    assert jobs[0]["urls"] == ["https://cdn.x/a.png", "https://cdn.x/b.jpg?x=1"] and jobs[0]["model"] == "nano_banana_2"


def test_cost_and_generate_parse_outputs(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", _fake_run({"estimate": {"credits": 4}}))
    assert hf.cost("nano_banana_2", {"prompt": "x"})["credits"] == 4
    monkeypatch.setattr(hf, "_run", _fake_run({"id": "job9", "outputs": [{"image_url": "https://cdn.x/out.png"}]}))
    r = hf.generate("nano_banana_2", {"prompt": "x"})
    assert r["id"] == "job9" and r["urls"] == ["https://cdn.x/out.png"]


def test_generate_raises_on_cli_error(monkeypatch):
    import pytest
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (1, "", "Error: insufficient credits"))
    with pytest.raises(RuntimeError, match="insufficient credits"):
        hf.generate("nano_banana_2", {"prompt": "x"})
    assert hf.cost("nano_banana_2", {"prompt": "x"})["credits"] is None


def test_run_handles_missing_binary_and_timeout(monkeypatch):
    import subprocess
    monkeypatch.setattr(hf, "BIN", "/definitely/not/here")
    code, _, err = hf._run(["account", "status"], timeout=5)
    assert code == 127 and "indisponível" in err

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="hf", timeout=1)
    monkeypatch.setattr(hf.subprocess, "run", boom)
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    code, _, err = hf._run(["generate", "create"], timeout=1)
    assert code == 124 and "tempo esgotado" in err


def test_status_cache_avoids_repeated_subprocess(monkeypatch):
    """`account status` custa até 30 s e 7 telas pedem o chip a cada troca de projeto."""
    hf.reset_status_cache()
    calls = []
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (calls.append(args), (0, '{"plan": "ultimate"}', ""))[1])
    assert hf.status()["plan"] == "ultimate"
    assert hf.status()["plan"] == "ultimate" and len(calls) == 1, "segunda leitura vem do cache"
    assert hf.status(refresh=True)["plan"] == "ultimate" and len(calls) == 2, "refresh ignora o cache"
    hf.reset_status_cache()
    hf.status()
    assert len(calls) == 3, "cache zerado volta a consultar o CLI"


def test_status_cache_expires_after_ttl(monkeypatch):
    hf.reset_status_cache()
    calls = []
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (calls.append(args), (0, "{}", ""))[1])
    hf.status()
    monkeypatch.setattr(hf.time, "monotonic", lambda: hf._STATUS_CACHE["at"] + hf.STATUS_TTL + 1)
    hf.status()
    assert len(calls) == 2


def test_status_without_cli_is_never_cached(monkeypatch):
    """Sem binário não há subprocess para poupar — e cachear atrapalharia os testes seguintes."""
    hf.reset_status_cache()
    monkeypatch.setattr(hf, "BIN", None)
    assert hf.status() == {"installed": False, "logged_in": False}
    assert hf._STATUS_CACHE["data"] is None
