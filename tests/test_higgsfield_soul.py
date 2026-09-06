"""Soul ID na ponte Higgsfield (ADR-039/002): sem CLI real, via fake de `_run`."""
import json

import pytest

from studio import higgsfield as hf


@pytest.fixture(autouse=True)
def _logged_in(monkeypatch):
    monkeypatch.setattr(hf, "require_cli", lambda: None)


def test_soul_list(monkeypatch):
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (0, json.dumps([{"id": "s1", "name": "Eden"}]), ""))
    assert hf.soul_list()[0]["id"] == "s1"


def test_soul_create_extrai_id(monkeypatch):
    capturado = {}

    def fake_run(args, timeout=120):
        capturado["args"] = args
        return 0, json.dumps({"reference_id": "ref-123", "status": "queued"}), ""

    monkeypatch.setattr(hf, "_run", fake_run)
    res = hf.soul_create("Eden", ["/a.png", "/b.png"], variant="soul-2")
    assert res["id"] == "ref-123" and res["variant"] == "soul-2"
    assert "--soul-2" in capturado["args"] and capturado["args"].count("--image") == 2


def test_soul_create_falha_propaga(monkeypatch):
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (1, "", "Minimum Basic plan required"))
    with pytest.raises(RuntimeError, match="Basic plan"):
        hf.soul_create("Eden", ["/a.png"])
