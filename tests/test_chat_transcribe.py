"""Entrada por voz no chat (ADR-043): validação, transcrição no servidor e procedência `via`.

Nenhum teste aqui importa `openai`, abre socket ou toca o provedor real (ADR-008): o provedor é
sempre um stub injetado em `voice.get_transcribe`, e o caminho "sem chave" usa o `FakeTranscribe`
que o próprio módulo da ADR-024 devolve.
"""
import sys
import tempfile
from pathlib import Path

import pytest

# Assinaturas mínimas de cada formato da allowlist do `whisper-1` (o resto dos bytes é irrelevante:
# a validação olha só o cabeçalho).
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
OGG = b"OggS" + b"\x00" * 64
M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 48
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 48
MP3_ID3 = b"ID3\x03\x00" + b"\x00" * 64
MP3_SYNC = b"\xff\xfb\x90\x00" + b"\x00" * 64


class StubTranscribe:
    """Provedor de mentira que NÃO é o `FakeTranscribe`: devolve o texto combinado e conta chamadas."""

    model = "stub-1"

    def __init__(self, texto: str = "gera as ideias", erro: Exception | None = None) -> None:
        self.texto = texto
        self.erro = erro
        self.chamadas: list[tuple[str, float]] = []
        self.existia: list[bool] = []

    def words(self, audio, text, duration_s):  # pragma: no cover — não usado pela voz
        return []

    def transcribe_text(self, audio, duration_s):
        self.chamadas.append((Path(audio).name, duration_s))
        self.existia.append(Path(audio).is_file())
        if self.erro is not None:
            raise self.erro
        return self.texto, []


def _injeta(monkeypatch, provider):
    """Troca o provedor resolvido por `voice.transcribe`, sem tocar o módulo da ADR-024."""
    from studio.chat import voice
    monkeypatch.setattr(voice, "get_transcribe", lambda: provider)
    return provider


def _tmp_vazio(monkeypatch, tmp_path) -> Path:
    """Aponta `tempfile.tempdir` para um diretório vazio — o detector de byte sobrevivente."""
    d = tmp_path / "tmp-vazio"
    d.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(d))
    return d


# ---------- unidade: studio/chat/voice.py ----------
def test_ut01_check_audio_aceita_webm_valido():
    from studio.chat import voice
    assert voice.check_audio(WEBM, "audio/webm;codecs=opus", "fala.webm") == "webm"


def test_ut02_check_audio_rejeita_arquivo_vazio():
    from studio.chat import voice
    with pytest.raises(voice.VoiceError) as e:
        voice.check_audio(b"", "audio/webm", "fala.webm")
    assert str(e.value).startswith("file:") and "vazio" in str(e.value)


def test_ut03_check_audio_rejeita_tipo_fora_da_allowlist():
    from studio.chat import voice
    with pytest.raises(voice.VoiceError) as e:
        voice.check_audio(WEBM, "application/pdf", "fala.pdf")
    assert str(e.value).startswith("file: formato não suportado: application/pdf")


def test_ut04_check_audio_rejeita_assinatura_incompativel():
    from studio.chat import voice
    with pytest.raises(voice.VoiceError) as e:
        voice.check_audio(b"nao sou webm de jeito nenhum", "audio/webm", "fala.webm")
    assert "assinatura inválida" in str(e.value) and str(e.value).startswith("file:")


@pytest.mark.parametrize("duracao", [180, -1])
def test_ut05_check_audio_rejeita_duracao_fora_do_intervalo(duracao):
    from studio.chat import voice
    with pytest.raises(voice.VoiceError) as e:
        voice.check_audio(WEBM, "audio/webm", "fala.webm", duracao)
    assert str(e.value).startswith("duration_s:")


@pytest.mark.parametrize(("data", "tipo", "ext"), [
    (OGG, "audio/ogg", "ogg"),
    (M4A, "audio/mp4", "m4a"),
    (M4A, "audio/m4a", "m4a"),
    (WAV, "audio/wav", "wav"),
    (WAV, "audio/x-wav", "wav"),
    (MP3_ID3, "audio/mpeg", "mp3"),
    (MP3_SYNC, "audio/mpeg", "mp3"),
])
def test_ut06_check_audio_aceita_os_demais_formatos_do_whisper(data, tipo, ext):
    from studio.chat import voice
    assert voice.check_audio(data, tipo, f"fala.{ext}", 6.4) == ext


def test_ut07_transcribe_recusa_o_provedor_de_mentira(monkeypatch):
    """Sem `OPENAI_API_KEY` o resolvido é o `FakeTranscribe`, e ele NUNCA é chamado (ADR-024 §5)."""
    from studio.chat import voice
    from studio.edit.captions.transcribe import FakeTranscribe
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    chamou = []
    monkeypatch.setattr(FakeTranscribe, "transcribe_text",
                        lambda self, audio, duration_s: chamou.append(audio) or ("", []))
    with pytest.raises(voice.NoProvider) as e:
        voice.transcribe(WEBM, "audio/webm", "fala.webm", 6.4)
    assert "OPENAI_API_KEY" in str(e.value) and ".env.local" in str(e.value)
    assert chamou == []


def test_ut08_transcribe_descarta_o_audio_nos_dois_caminhos(monkeypatch, tmp_path):
    from studio.chat import voice
    from studio.edit.captions.transcribe import ProviderError
    d = _tmp_vazio(monkeypatch, tmp_path)

    ok = _injeta(monkeypatch, StubTranscribe("falei isso"))
    assert voice.transcribe(WEBM, "audio/webm", "fala.webm", 6.4)["text"] == "falei isso"
    assert ok.existia == [True], "o provedor precisa receber um arquivo de verdade"
    assert list(d.iterdir()) == []

    _injeta(monkeypatch, StubTranscribe(erro=ProviderError("boom")))
    with pytest.raises(ProviderError):
        voice.transcribe(WEBM, "audio/webm", "fala.webm", 6.4)
    assert list(d.iterdir()) == []


def test_ut09_transcribe_propaga_a_falha_do_provedor_real(monkeypatch):
    from studio.chat import voice
    from studio.edit.captions.transcribe import ProviderError
    _injeta(monkeypatch, StubTranscribe(erro=ProviderError("transcrição falhou: 429")))
    with pytest.raises(ProviderError, match="429"):
        voice.transcribe(WEBM, "audio/webm", "fala.webm", 6.4)


# ---------- integração: POST /api/chats/{id}/transcribe ----------
def _aba(client) -> str:
    return client.post("/api/chats", json={"title": "voz"}).json()["id"]


def _post(client, cid, data=WEBM, tipo="audio/webm", nome="fala.webm", duracao=6.4):
    return client.post(f"/api/chats/{cid}/transcribe",
                       files={"file": (nome, data, tipo)}, data={"duration_s": str(duracao)})


def test_it01_transcricao_concluida(client, monkeypatch):
    stub = _injeta(monkeypatch, StubTranscribe("gera as ideias"))
    r = _post(client, _aba(client))
    assert r.status_code == 200
    assert r.json() == {"text": "gera as ideias", "provider": "stub-1", "duration_s": 6.4}
    assert len(stub.chamadas) == 1


def test_it02_sem_provedor_real_responde_409(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = _post(client, _aba(client))
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert isinstance(detail, str)
    assert "OPENAI_API_KEY" in detail and ".env.local" in detail
    assert "palavra1" not in detail


def test_it03_corpo_acima_do_teto_responde_413(client, monkeypatch):
    from studio.chat import voice
    stub = _injeta(monkeypatch, StubTranscribe())
    grande = WEBM + b"\x00" * (voice.MAX_AUDIO_BYTES + 1 - len(WEBM))
    r = _post(client, _aba(client), data=grande)
    assert r.status_code == 413
    assert "fala.webm" in r.json()["detail"] and "10 MB" in r.json()["detail"]
    assert stub.chamadas == []


@pytest.mark.parametrize(("data", "tipo", "duracao", "campo"), [
    (b"", "audio/webm", 6.4, "file:"),
    (WEBM, "application/pdf", 6.4, "file:"),
    (b"nao sou webm", "audio/webm", 6.4, "file:"),
    (WEBM, "audio/webm", 200, "duration_s:"),
])
def test_it04_entrada_invalida_responde_422(client, monkeypatch, data, tipo, duracao, campo):
    stub = _injeta(monkeypatch, StubTranscribe())
    r = _post(client, _aba(client), data=data, tipo=tipo, duracao=duracao)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str) and detail.startswith(campo)
    assert stub.chamadas == []


def test_it05_aba_inexistente_responde_404_antes_de_ler_o_arquivo(client, monkeypatch):
    stub = _injeta(monkeypatch, StubTranscribe())
    r = _post(client, "nao-existe")
    assert r.status_code == 404
    assert r.json()["detail"] == "conversa não encontrada: nao-existe"
    assert stub.chamadas == []


def test_it06_provedor_real_falhou_responde_502(client, monkeypatch):
    from studio.edit.captions.transcribe import ProviderError
    _injeta(monkeypatch, StubTranscribe(erro=ProviderError("transcrição falhou: boom")))
    r = _post(client, _aba(client))
    assert r.status_code == 502
    assert "boom" in r.json()["detail"]


def test_it07_nenhum_byte_sobrevive_a_requisicao(client, monkeypatch, tmp_path):
    """IT-01, IT-02, IT-04 e IT-06 em sequência com `tempfile.tempdir` num diretório vazio."""
    from studio.edit.captions.transcribe import ProviderError
    d = _tmp_vazio(monkeypatch, tmp_path)
    cid = _aba(client)

    _injeta(monkeypatch, StubTranscribe("gera as ideias"))
    assert _post(client, cid).status_code == 200
    assert list(d.iterdir()) == []

    # devolve a resolução ao módulo da ADR-024, que sem a chave cai no `FakeTranscribe`
    from studio.chat import voice
    from studio.edit.captions.transcribe import get_transcribe
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(voice, "get_transcribe", get_transcribe)
    assert _post(client, cid).status_code == 409
    assert list(d.iterdir()) == []

    _injeta(monkeypatch, StubTranscribe())
    assert _post(client, cid, data=b"nao sou webm").status_code == 422
    assert list(d.iterdir()) == []

    _injeta(monkeypatch, StubTranscribe(erro=ProviderError("boom")))
    assert _post(client, cid).status_code == 502
    assert list(d.iterdir()) == []


def test_it09_procedencia_no_transcript(client, monkeypatch):
    """`via:"voice"` chega ao `events.jsonl` e ao WS; sem `via`, o evento é o de hoje."""
    from studio.chat import runtime

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "result", "is_error": False, "text": "ok", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    cid = _aba(client)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "oi", "via": "voice"})
        eco = ws.receive_json()
        assert eco["kind"] == "user" and eco["text"] == "oi" and eco["via"] == "voice"

    eventos = [e for e in client.get(f"/api/chats/{cid}/events").json()["events"]
               if e["kind"] == "user"]
    assert len(eventos) == 1
    ev = eventos[0]
    assert ev["text"] == "oi" and ev["via"] == "voice"
    assert not (set(ev) & {"audio", "file", "bytes", "data", "blob", "media"}), \
        "o transcript guarda só texto e o rótulo de procedência (ADR-040)"

    # sem `via` (e com qualquer outro valor) o evento continua sem a chave
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "digitei"})
        assert "via" not in ws.receive_json()
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "inventado", "via": "telepatia"})
        assert "via" not in ws.receive_json()
    digitados = [e for e in client.get(f"/api/chats/{cid}/events").json()["events"]
                 if e["kind"] == "user" and e["text"] in ("digitei", "inventado")]
    assert len(digitados) == 2 and all("via" not in e for e in digitados)


def test_it11_titularidade_declarada():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_adr010_fronteira_nucleo import TITULARES_DO_NUCLEO, violacao
    branch = "feature/adh-os-20260906-11-chat-audio"
    motivo, prefixos = TITULARES_DO_NUCLEO[branch]
    assert prefixos == ("frontend/", "studio/web/")
    assert "ADR-043" in motivo and "#89" in motivo
    assert violacao({"frontend/src/areas/chat/useRecorder.ts", "studio/web/dist/assets/x.js",
                     "studio/chat/voice.py"}, branch) is None


def test_it08_a_suite_nao_importa_o_sdk():
    """Último teste do arquivo: nada aqui pode ter puxado `openai` (ADR-008)."""
    assert "openai" not in sys.modules
