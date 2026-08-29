"""Ponte com o CLI da Higgsfield: montagem de flags e leitura defensiva de JSON (sem chamar o CLI)."""
import json

import pytest

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


# ---------- dedup do companion `_min.webp` (bug ADH-OS-20260828-19) ----------
def test_dedup_min_helper_prefers_full_and_preserves_order():
    urls = ["https://cdn.x/a.png", "https://cdn.x/a_min.webp",
            "https://cdn.x/b.png", "https://cdn.x/b_min.webp"]
    assert hf._dedup_min(urls) == ["https://cdn.x/a.png", "https://cdn.x/b.png"]


def test_dedup_min_helper_keeps_min_when_alone():
    assert hf._dedup_min(["https://cdn.x/c_min.webp"]) == ["https://cdn.x/c_min.webp"]


def test_dedup_min_helper_keeps_unpaired_full():
    assert hf._dedup_min(["https://cdn.x/d.png"]) == ["https://cdn.x/d.png"]


def test_dedup_min_helper_prefers_full_even_when_min_comes_first():
    # a versão cheia deve vencer independentemente da ordem de aparição
    assert hf._dedup_min(["https://cdn.x/a_min.webp", "https://cdn.x/a.png"]) == ["https://cdn.x/a.png"]


def test_dedup_min_ignores_query_string():
    urls = ["https://cdn.x/a.png?sig=1", "https://cdn.x/a_min.webp?sig=2"]
    assert hf._dedup_min(urls) == ["https://cdn.x/a.png?sig=1"]


def test_generate_drops_min_companion(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    payload = {"id": "job1", "outputs": [
        {"image_url": "https://cdn.x/a.png"}, {"preview_url": "https://cdn.x/a_min.webp"},
        {"image_url": "https://cdn.x/b.png"}, {"preview_url": "https://cdn.x/b_min.webp"},
    ]}
    monkeypatch.setattr(hf, "_run", _fake_run(payload))
    r = hf.generate("nano_banana_2", {"prompt": "x"})
    assert r["urls"] == ["https://cdn.x/a.png", "https://cdn.x/b.png"] and r["id"] == "job1"


def test_generate_keeps_lone_min(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", _fake_run({"id": "j", "outputs": [{"url": "https://cdn.x/c_min.webp"}]}))
    assert hf.generate("nano_banana_2", {"prompt": "x"})["urls"] == ["https://cdn.x/c_min.webp"]


def test_history_media_drops_min_companion(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    payload = {"items": [
        {"id": "j1", "job_type": "nano_banana_2", "prompt": "vibe",
         "results": [{"url": "https://cdn.x/a.png"}, {"url": "https://cdn.x/a_min.webp"}]},
    ]}
    monkeypatch.setattr(hf, "_run", _fake_run(payload))
    jobs = hf.history_media("image", 10)
    assert jobs[0]["urls"] == ["https://cdn.x/a.png"]


def test_history_media_keeps_lone_min(monkeypatch):
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    payload = {"items": [{"id": "j2", "results": [{"url": "https://cdn.x/d_min.webp"}]}]}
    monkeypatch.setattr(hf, "_run", _fake_run(payload))
    jobs = hf.history_media("image", 10)
    assert jobs[0]["urls"] == ["https://cdn.x/d_min.webp"]


# ---------- adapt_params: cada modelo aceita um conjunto diferente (ADH-OS-20260829-34) ----------
def _cli_por_subcomando(respostas: dict, chamadas: list | None = None):
    """`_run` fake que responde por (args[0], args[1]) e registra as chamadas."""
    def run(args, timeout=120):
        if chamadas is not None:
            chamadas.append(list(args))
        key = tuple(args[:2])
        if key not in respostas:
            return 1, "", f"sem resposta fake para {key}"
        return 0, json.dumps(respostas[key]), ""
    return run


KLING26 = {"job_type": "kling2_6", "params": [{"name": n} for n in ("aspect_ratio", "duration", "prompt", "sound", "start_image")]}
KLING30 = {"job_type": "kling3_0", "params": [{"name": n} for n in ("aspect_ratio", "duration", "end_image", "mode", "prompt", "sound", "start_image")]}


def test_adapt_params_drops_what_the_model_does_not_declare(monkeypatch):
    hf.reset_model_params_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", _cli_por_subcomando({("model", "get"): KLING26}))
    out = hf.adapt_params("kling2_6", {"prompt": "p", "duration": 5, "aspect_ratio": "16:9", "mode": "pro",
                                       "sound": False, "start_image": "/x.png"})
    assert "mode" not in out and out["prompt"] == "p" and out["start_image"] == "/x.png"


def test_adapt_params_keeps_everything_when_model_declares_it(monkeypatch):
    hf.reset_model_params_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", _cli_por_subcomando({("model", "get"): KLING30}))
    params = {"prompt": "p", "mode": "pro", "start_image": "/a.png", "end_image": "/b.png"}
    assert hf.adapt_params("kling3_0", params) == params


def test_adapt_params_refuses_essential_param_the_model_lacks(monkeypatch):
    hf.reset_model_params_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", _cli_por_subcomando({("model", "get"): KLING26}))
    with pytest.raises(RuntimeError, match="não aceita end_image"):
        hf.adapt_params("kling2_6", {"prompt": "p", "start_image": "/a.png", "end_image": "/b.png"})


def test_adapt_params_without_catalog_changes_nothing(monkeypatch):
    hf.reset_model_params_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (1, "", "Error: model not found"))
    params = {"prompt": "p", "mode": "pro"}
    assert hf.adapt_params("modelo_x", params) == params


def test_generate_and_cost_send_only_declared_params_and_cache_catalog(monkeypatch):
    hf.reset_model_params_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    chamadas: list = []
    monkeypatch.setattr(hf, "_run", _cli_por_subcomando({
        ("model", "get"): KLING26,
        ("generate", "cost"): {"credits": 3},
        ("generate", "create"): {"id": "job1", "outputs": [{"video_url": "https://cdn.x/o.mp4"}]},
    }, chamadas))
    params = {"prompt": "p", "duration": 5, "aspect_ratio": "16:9", "mode": "pro", "sound": False, "start_image": "/x.png"}
    assert hf.cost("kling2_6", params)["credits"] == 3
    assert hf.generate("kling2_6", params)["urls"] == ["https://cdn.x/o.mp4"]
    enviados = [c for c in chamadas if c[:2] in (["generate", "cost"], ["generate", "create"])]
    assert enviados and all("--mode" not in c for c in enviados)
    assert sum(1 for c in chamadas if c[:2] == ["model", "get"]) == 1     # catálogo cacheado


def test_cost_reports_essential_param_error_instead_of_raising(monkeypatch):
    hf.reset_model_params_cache()
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", _cli_por_subcomando({("model", "get"): KLING26}))
    r = hf.cost("kling2_6", {"prompt": "p", "start_image": "/a.png", "end_image": "/b.png"})
    assert r["credits"] is None and "end_image" in r["error"]
