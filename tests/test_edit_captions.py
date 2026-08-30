"""Legendas no servidor: constantes do contrato e transcrição pura. `[extensão]`

Camada sem ffmpeg, sem HTTP e sem rede — o SDK da OpenAI NUNCA é importado de verdade
(ADR-008): quando um teste precisa do provedor real, injeta um módulo `openai` falso em
`sys.modules` via `monkeypatch.setitem`, que o desfaz sozinho no fim.
"""
from __future__ import annotations

import importlib
import re
import sys
import types
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from studio.edit import burnin
from studio.edit.captions import (
    CAPTION_MODES,
    CHUNK_OPTS,
    DEFAULT_HI,
    HI_COLORS,
    WPS,
    effective_mode,
    word_in_window,
)
from studio.edit.captions.audio import duration_of, extract_wav, extracted
from studio.edit.captions.layout import (
    GAP_S,
    KARAOKE_MIN_WORDS,
    MIN_FONT_PX,
    LayoutOpts,
    build_items,
    karaoke_font_size,
    layout_windows,
)
from studio.edit.captions.transcribe import (
    FakeTranscribe,
    OpenAITranscribe,
    ProviderError,
    WordTiming,
    align,
    fake_transcript,
    get_transcribe,
    proportional,
)
from tests.conftest import make_audio, make_image

# --------------------------------------------------------------- SDK falso (sem rede)


class _FakeWord:
    """Palavra do `verbose_json` do whisper: `.word`, `.start`, `.end`."""

    def __init__(self, word: str, start: float, end: float):
        self.word, self.start, self.end = word, start, end


class _FakeResult:
    def __init__(self, text: str, words: list[_FakeWord]):
        self.text, self.words = text, words


def _fake_sdk(monkeypatch, *, result=None, boom: Exception | None = None) -> dict:
    """Instala um módulo `openai` falso e devolve o que foi capturado nas chamadas."""
    captured: dict[str, list] = {"client": [], "create": []}

    class _Transcriptions:
        def create(self, **kwargs):
            captured["create"].append(kwargs)
            if boom is not None:
                raise boom
            return result

    class _Audio:
        def __init__(self):
            self.transcriptions = _Transcriptions()

    class _OpenAI:
        def __init__(self, **kwargs):
            captured["client"].append(kwargs)
            self.audio = _Audio()

    mod = types.ModuleType("openai")
    mod.OpenAI = _OpenAI
    monkeypatch.setitem(sys.modules, "openai", mod)
    return captured


@pytest.fixture()
def audio(tmp_path):
    p = tmp_path / "voz.wav"
    p.write_bytes(b"nao-e-um-wav-de-verdade")
    return p


# ------------------------------------------------- constantes do contrato congelado


def test_captions_constantes_batem_com_o_contrato_congelado():
    """A frente C espelha estes valores no `view.js`: divergir quebra o preview."""
    assert WPS == 2.4
    assert CAPTION_MODES == ("karaoke", "linha", "bloco")
    assert HI_COLORS == ["#C8F751", "#57E2F0", "#F2B544", "#A78BFA"]
    assert CHUNK_OPTS == [0, 6, 4, 2]
    assert DEFAULT_HI == "#C8F751"


# ------------------------------------------------------------------- `proportional`


def test_captions_proportional_pesa_len_mais_um_e_e_deterministico():
    saida = proportional("de desenvolvimento", 3.0)

    assert saida == proportional("de desenvolvimento", 3.0)     # determinístico
    assert [w.text for w in saida] == ["de", "desenvolvimento"]
    curta, longa = saida
    assert (longa.end - longa.start) > (curta.end - curta.start)
    assert curta.start == 0.0
    assert longa.end == 3.0
    assert pytest.approx(sum(w.end - w.start for w in saida)) == 3.0


def test_captions_proportional_sem_texto_ou_sem_duracao_devolve_vazio():
    assert proportional("", 5) == []
    assert proportional("oi", 0) == []


# -------------------------------------------------------------------------- `align`


def test_captions_align_usa_nosso_texto_com_os_tempos_ouvidos():
    """Contagem igual: um-para-um. O texto exibido é SEMPRE o nosso."""
    ouvidas = [WordTiming("nossa", 0.1, 0.5), WordTiming("txt", 0.5, 0.9),
               WordTiming("aki", 0.9, 1.4)]

    saida = align("nosso texto aqui", ouvidas, 2.0)

    assert [w.text for w in saida] == ["nosso", "texto", "aqui"]
    assert [(w.start, w.end) for w in saida] == [(0.1, 0.5), (0.5, 0.9), (0.9, 1.4)]


def test_captions_align_com_contagem_diferente_usa_o_intervalo_real_da_fala():
    ouvidas = [WordTiming("bla", 2.0, 3.0), WordTiming("ble", 3.0, 4.0)]

    saida = align("uma frase nossa com cinco", ouvidas, 30.0)

    assert [w.text for w in saida] == ["uma", "frase", "nossa", "com", "cinco"]
    assert saida[0].start >= 2.0
    assert saida[-1].end <= 4.0


def test_captions_align_sem_palavras_ouvidas_cai_no_proporcional():
    saida = align("um dois", [], 4.0)

    assert saida == proportional("um dois", 4.0)
    assert saida[-1].end == 4.0


def test_captions_align_sem_texto_devolve_vazio():
    ouvidas = [WordTiming("bla", 0.0, 1.0)]
    assert align("", ouvidas, 3.0) == []


# ----------------------------------------------------------------- `fake_transcript`


def test_captions_fake_transcript_segue_o_wps_e_ignora_o_nome():
    texto = fake_transcript("qualquer.wav", 5.0)

    assert len(texto.split()) == round(5.0 * 2.4) == 12
    assert texto.split()[0] == "palavra1"
    assert texto == fake_transcript("outro-nome.mp4", 5.0)


# --------------------------------------------------- `word_in_window` / `effective_mode`


def test_captions_word_in_window_usa_o_centro_com_a_incluso_e_b_excluso():
    # centro exatamente em `a` (1.0) → pertence; centro exatamente em `b` (2.0) → não
    no_limite_a = {"w": "x", "start_s": 0.8, "end_s": 1.2}
    no_limite_b = {"w": "y", "start_s": 1.8, "end_s": 2.2}

    assert word_in_window(no_limite_a, 1.0, 2.0) is True
    assert word_in_window(no_limite_b, 1.0, 2.0) is False


def test_captions_word_in_window_aceita_dict_e_wordtiming():
    como_dict = {"w": "x", "start_s": 1.0, "end_s": 1.4}
    como_timing = WordTiming("x", 1.0, 1.4)

    for a, b in [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]:
        assert word_in_window(como_dict, a, b) == word_in_window(como_timing, a, b)
    assert word_in_window(como_timing, 1.0, 2.0) is True


def test_captions_effective_mode_cai_no_default_fora_do_dominio():
    assert effective_mode("karaoke") == "karaoke"
    assert effective_mode("x") == "bloco"
    assert effective_mode(None) == "bloco"
    assert effective_mode(7) == "bloco"
    assert effective_mode("x", "linha") == "linha"


# ---------------------------------------------------------------- escolha do provedor


def test_captions_get_transcribe_le_a_chave_em_tempo_de_chamada(monkeypatch):
    """Sem reimportar o módulo entre as duas asserções: a chave é lida a cada chamada."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(get_transcribe(), FakeTranscribe)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    assert isinstance(get_transcribe(), OpenAITranscribe)


def test_captions_importar_o_pacote_nao_carrega_o_sdk(monkeypatch):
    """ADR-008: a suíte nunca importa `openai` de verdade — o import é lazy nos métodos."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delitem(sys.modules, "openai", raising=False)
    for name in [m for m in list(sys.modules) if m.startswith("studio.edit.captions")]:
        monkeypatch.delitem(sys.modules, name, raising=False)

    importlib.import_module("studio.edit.captions")
    importlib.import_module("studio.edit.captions.transcribe")

    assert "openai" not in sys.modules


# ------------------------------------------------------------------ `OpenAITranscribe`


def test_captions_transcribe_text_mapeia_o_resultado_do_whisper(monkeypatch, audio):
    result = _FakeResult("Ninguém te conta isso.",
                         [_FakeWord("Ninguém", 0.32, 0.71), _FakeWord("te", 0.71, 0.9)])
    captured = _fake_sdk(monkeypatch, result=result)

    texto, ouvidas = OpenAITranscribe("sk-teste").transcribe_text(audio, 120.0)

    assert texto == "Ninguém te conta isso."
    assert ouvidas == [WordTiming("Ninguém", 0.32, 0.71), WordTiming("te", 0.71, 0.9)]
    assert captured["client"][0] == {"api_key": "sk-teste", "timeout": 120, "max_retries": 1}
    assert captured["create"][0]["model"] == "whisper-1"
    assert captured["create"][0]["response_format"] == "verbose_json"
    assert captured["create"][0]["timestamp_granularities"] == ["word"]
    assert captured["create"][0]["language"] == "pt"


def test_captions_transcribe_text_sem_texto_nosso_levanta_provider_error(monkeypatch, audio):
    """Política assimétrica: sem texto nosso não há o que estimar — a falha sobe (502)."""
    _fake_sdk(monkeypatch, boom=RuntimeError("connection reset sk-teste"))

    with pytest.raises(ProviderError) as exc:
        OpenAITranscribe("sk-teste").transcribe_text(audio, 120.0)

    assert "transcrição falhou" in str(exc.value)
    assert "connection reset" in str(exc.value)
    assert "sk-teste" not in str(exc.value)     # a chave nunca vaza na exceção


def test_captions_words_cai_no_proporcional_quando_o_provedor_falha(monkeypatch, audio):
    """Política assimétrica: temos o texto, então legenda é enfeite e não levanta."""
    _fake_sdk(monkeypatch, boom=RuntimeError("connection reset"))

    saida = OpenAITranscribe("sk-teste").words(audio, "uma fala qualquer", 3.0)

    assert saida == proportional("uma fala qualquer", 3.0)
    assert [w.text for w in saida] == "uma fala qualquer".split()


def test_captions_words_devolve_nosso_texto_com_os_tempos_ouvidos(monkeypatch, audio):
    result = _FakeResult("gaélico ilegível",
                         [_FakeWord("gaélico", 0.2, 0.6), _FakeWord("ilegível", 0.6, 1.1)])
    _fake_sdk(monkeypatch, result=result)

    saida = OpenAITranscribe("sk-teste").words(audio, "nosso texto", 3.0)

    assert saida == [WordTiming("nosso", 0.2, 0.6), WordTiming("texto", 0.6, 1.1)]


def test_captions_repr_do_provedor_real_nao_expoe_a_chave():
    assert "sk-teste" not in repr(OpenAITranscribe("sk-teste"))


# ------------------------------------------------------------------- `FakeTranscribe`


def test_captions_fake_transcribe_devolve_texto_falso_e_tempos_proporcionais(audio):
    texto, palavras = FakeTranscribe().transcribe_text(audio, 5.0)

    assert texto == fake_transcript(audio.name, 5.0)
    assert palavras == proportional(texto, 5.0)
    assert len(palavras) == len(texto.split()) == 12


# ====================================================================== layout
# Fatiamento da fala em janelas de uma linha e itens prontos para a faixa `t_cap`.

DEZ = "uma duas tres quatro cinco seis sete oito nove dez"

#: Longo o bastante para estourar `0.84 * 1920 px` com a fonte real do burn-in (Liberation a
#: 34 px) e também com a fonte bitmap de fallback do Pillow, bem mais estreita — a quebra por
#: largura não pode depender de qual fonte a máquina tem instalada.
LONGO = (
    "Ninguém te conta isso mas a diferença entre um vídeo que prende e um vídeo que passa "
    "batido está inteira no ritmo do corte e na respiração da narração que você grava muito "
    "antes de abrir o editor e começar a montar a sequência inteira no ritmo da trilha que "
    "escolheu para o projeto"
)


def test_captions_build_items_respeita_o_chunk_e_nao_perde_palavra():
    items = build_items(proportional(DEZ, 10 / WPS), LayoutOpts(chunk=6))

    assert all(len(i["words"]) <= 6 for i in items)
    # a união das janelas é exatamente a fala original: mesma ordem, sem duplicata nem perda
    assert [w["w"] for i in items for w in i["words"]] == DEZ.split()


def test_captions_chunk_dois_nunca_passa_de_duas_palavras_por_item():
    items = build_items(proportional(DEZ, 10 / WPS), LayoutOpts(chunk=2))

    assert all(len(i["words"]) <= 2 for i in items)
    assert [w["w"] for i in items for w in i["words"]] == DEZ.split()


def test_captions_chunk_zero_fecha_a_janela_pela_largura_real_da_linha():
    """Sem teto de contagem, quem quebra a linha é a largura medida com a fonte do burn-in."""
    janelas = layout_windows(proportional(LONGO, 30.0),
                             LayoutOpts(chunk=0, style={"size": 34, "weight": 700}))

    assert len(janelas) > 1
    # janela de uma palavra só pisca na tela: só a última pode ficar abaixo do mínimo
    assert all(len(j) >= KARAOKE_MIN_WORDS for j in janelas[:-1])


def test_captions_itens_cobrem_o_trecho_inteiro_sem_buraco_nem_sobreposicao():
    start, duracao = 3.0, 10 / WPS

    items = build_items(proportional(DEZ, duracao), LayoutOpts(chunk=4, start=start))

    assert items[0]["start"] == start
    assert all(items[i]["end"] == items[i + 1]["start"] for i in range(len(items) - 1))
    assert items[-1]["end"] == round(start + round(duracao, 3), 3)


def test_captions_pausa_maior_que_gap_separa_as_janelas():
    """Duas frases com um respiro no meio nunca viram a mesma linha, mesmo cabendo no `chunk`."""
    palavras = [WordTiming("antes", 0.0, 0.5), WordTiming("da", 0.5, 0.8),
                WordTiming("pausa", 0.8, 1.2),
                WordTiming("depois", 1.2 + GAP_S + 0.5, 3.2), WordTiming("dela", 3.2, 3.6)]

    items = build_items(palavras, LayoutOpts(chunk=20))

    assert len(items) == 2
    assert [w["w"] for w in items[0]["words"]] == ["antes", "da", "pausa"]
    assert [w["w"] for w in items[1]["words"]] == ["depois", "dela"]


def test_captions_dois_generate_com_starts_distintos_nunca_compartilham_item():
    texto = "primeira fala do video"

    antes = build_items(proportional(texto, 4.0), LayoutOpts(chunk=6, start=0.0))
    depois = build_items(proportional(texto, 4.0), LayoutOpts(chunk=6, start=10.0))

    assert antes[-1]["end"] <= depois[0]["start"]          # cada chamada cobre só o seu intervalo
    assert {i["id"] for i in antes}.isdisjoint({i["id"] for i in depois})


def test_captions_item_tem_exatamente_as_chaves_do_contrato():
    items = build_items(proportional(DEZ, 4.0), LayoutOpts(chunk=6, hi="#57E2F0", mode="karaoke"))

    assert set(items[0]) == {"id", "start", "end", "text", "mode", "hi", "chunk",
                             "words", "style", "transform", "anim"}
    assert re.fullmatch(r"cap_[0-9a-f]{6}", items[0]["id"])
    assert items[0]["mode"] == "karaoke" and items[0]["hi"] == "#57E2F0" and items[0]["chunk"] == 6
    assert items[0]["anim"] == {"in": "fade", "out": "fade"}
    assert items[0]["transform"] == {"x": 0.5, "y": 0.82, "scaleX": 1, "scaleY": 1,
                                     "rotation": 0, "opacity": 1}


@pytest.mark.parametrize(("position", "y"), [("top", 0.12), ("middle", 0.5), ("bottom", 0.82)])
def test_captions_transform_y_segue_a_posicao_pedida(position, y):
    items = build_items(proportional(DEZ, 4.0), LayoutOpts(chunk=6, position=position))

    assert items[0]["transform"]["y"] == y


def test_captions_texto_do_item_e_a_juncao_das_palavras_por_espaco_simples():
    items = build_items(proportional(DEZ, 4.0), LayoutOpts(chunk=3))

    assert items[0]["text"] == "uma duas tres"
    assert all(i["text"] == " ".join(w["w"] for w in i["words"]) for i in items)


# ======================================================================= áudio
# Extração do wav 16 kHz mono que o whisper aceita (precisa do ffmpeg de verdade).


def test_captions_extract_wav_produz_audio_e_respeita_o_recorte(ffmpeg_or_skip, tmp_path):
    src = make_audio(tmp_path / "voz.wav", seconds=3)

    inteiro = extract_wav(src, tmp_path / "inteiro.wav")
    curto = extract_wav(src, tmp_path / "curto.wav", duration=1.0)

    assert ffmpeg_or_skip.probe(inteiro)["has_audio"] is True
    assert ffmpeg_or_skip.probe(curto)["duration"] == pytest.approx(1.0, abs=0.2)


def test_captions_duration_of_le_a_duracao_do_arquivo(ffmpeg_or_skip, tmp_path):
    assert duration_of(make_audio(tmp_path / "voz.wav", seconds=3)) == pytest.approx(3.0, abs=0.3)


def test_captions_duration_of_sem_trilha_de_audio_levanta_value_error(ffmpeg_or_skip, tmp_path):
    """Take mudo ou imagem não chegam ao whisper: a chamada seria paga para devolver nada."""
    mudo = make_image(tmp_path / "frame.jpg")

    with pytest.raises(ValueError) as exc:
        duration_of(mudo)

    assert str(exc.value).startswith("file: ")


def test_captions_extracted_apaga_o_temporario_inclusive_em_erro(ffmpeg_or_skip, tmp_path):
    src = make_audio(tmp_path / "voz.wav", seconds=1)

    with extracted(src) as wav:
        assert wav.exists()
        ok = wav
    assert not ok.exists() and not ok.parent.exists()

    with pytest.raises(RuntimeError):
        with extracted(src) as wav:
            explodiu = wav
            raise RuntimeError("boom")
    assert not explodiu.exists() and not explodiu.parent.exists()


# ------------------------------------------------- burn-in karaokê (Pillow, sem ffmpeg)

HI = "#C8F751"
HI_RGB = (200, 247, 81)
BRANCO = (255, 255, 255)


def _cap_item(palavras, *, start=0.0, end=2.0, mode="karaoke", size=64, **extra) -> dict:
    """Item de `caption` no shape que `build_items` produz (o que o `PUT /timeline` guarda)."""
    words = [{"w": w, "start_s": s, "end_s": e} for w, s, e in palavras]
    item = {"id": "cap_1", "start": start, "end": end,
            "text": " ".join(w["w"] for w in words), "mode": mode, "hi": HI, "chunk": 6,
            "words": words,
            "style": {"size": size, "weight": 800, "color": "#FFFFFF", "bg": "transparent",
                      "align": "center", "lineHeight": 1.2, "shadow": True},
            "transform": {"x": .5, "y": .82, "scaleX": 1, "scaleY": 1, "rotation": 0, "opacity": 1},
            "anim": {"in": "fade", "out": "fade"}}
    item.update(extra)
    return item


def _editor(items, ttype="caption") -> dict:
    return {"tracks": [{"id": "t_cap", "type": ttype, "visible": True, "items": items}]}


QUATRO = [("GELO", 0.0, 0.4), ("ZERO", 0.5, 0.9), ("GELA", 1.0, 1.4), ("TUDO", 1.5, 2.0)]


def _caixa_da_cor(path, cor) -> tuple | None:
    """Retângulo dos pixels EXATAMENTE nesta cor, ou `None` se a cor não aparece.

    A diferença por canal (`lighter` dos três) é zero só onde a cor bate exata, então o
    antialiasing das bordas do glifo não entra: o que sobra é o miolo chapado do texto.
    """
    img = Image.open(path).convert("RGB")
    diff = ImageChops.difference(img, Image.new("RGB", img.size, cor)).split()
    maior = ImageChops.lighter(ImageChops.lighter(diff[0], diff[1]), diff[2])
    return maior.point(lambda v: 255 if v == 0 else 0).getbbox()


def test_captions_burnin_karaoke_gera_um_png_por_palavra(tmp_path):
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(QUATRO)]), 1920, 1080,
                                     tmp_path / "ov")

    assert len(specs) == 4
    for spec in specs:
        assert Path(spec["path"]).exists()
        assert Image.open(spec["path"]).size == (1920, 1080)
        assert "kind" not in spec                   # abaixo do limiar é overlay puro


def test_captions_burnin_estados_sao_contiguos_e_cobrem_o_item(tmp_path):
    item = _cap_item(QUATRO, start=1.0, end=3.0)
    specs = burnin.render_layer_pngs(tmp_path, _editor([item]), 1920, 1080, tmp_path / "ov")

    assert specs[0]["start"] == item["start"]
    assert specs[-1]["end"] == item["end"]
    for a, b in zip(specs, specs[1:], strict=False):
        assert a["end"] == b["start"]               # sem buraco: a linha não pisca na pausa
    assert all(s["end"] - s["start"] >= 1 / 30 for s in specs)


def test_captions_burnin_destaca_a_palavra_corrente_na_cor_hi(tmp_path):
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(QUATRO)]), 1920, 1080,
                                     tmp_path / "ov")

    destaques = []
    for spec in specs:
        hi = _caixa_da_cor(spec["path"], HI_RGB)
        assert hi is not None, f"{spec['path']} sem a cor de destaque"
        assert _caixa_da_cor(spec["path"], BRANCO) is not None, \
            f"{spec['path']} sem as demais palavras em branco"
        destaques.append(hi[0])
    # o destaque anda para a direita palavra a palavra: cada PNG é um estado diferente
    assert destaques == sorted(destaques) and len(set(destaques)) == 4


@pytest.mark.parametrize("mode", ["linha", "bloco"])
def test_captions_burnin_linha_e_bloco_geram_um_png_por_item(tmp_path, mode):
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(QUATRO, mode=mode)]),
                                     1920, 1080, tmp_path / "ov")

    assert len(specs) == 1
    assert (specs[0]["start"], specs[0]["end"]) == (0.0, 2.0)


def test_captions_burnin_legenda_sem_palavras_segue_o_caminho_de_hoje(tmp_path):
    item = _cap_item(QUATRO)
    item["words"] = []
    specs = burnin.render_layer_pngs(tmp_path, _editor([item]), 1920, 1080, tmp_path / "ov")

    assert len(specs) == 1 and Path(specs[0]["path"]).name == "layer_000.png"


def test_captions_burnin_track_de_texto_com_words_nao_vira_karaoke(tmp_path):
    """`words` num item de `text` é ruído: só a faixa de legenda tem karaokê."""
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(QUATRO)], ttype="text"),
                                     1920, 1080, tmp_path / "ov")

    assert len(specs) == 1


def test_captions_burnin_ignora_palavra_com_centro_fora_da_janela(tmp_path):
    fora = [*QUATRO[:3], ("SOBRA", 4.0, 4.5)]       # centro em 4.25, fora de [0, 2)
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(fora)]), 1920, 1080,
                                     tmp_path / "ov")

    assert len(specs) == 3
    assert specs[-1]["end"] == 2.0


def test_captions_burnin_escada_de_corpos_reduz_o_texto_ate_caber(tmp_path):
    style = {"size": 64, "weight": 800}

    assert karaoke_font_size("GELO ZERO", style, 1920, 1080) == 64
    apertado = karaoke_font_size("GELO ZERO GELA TUDO " * 3, style, 1920, 1080)
    assert MIN_FONT_PX <= apertado < 64
    assert karaoke_font_size("PALAVRA " * 60, style, 1920, 1080) == MIN_FONT_PX

    longo = [(f"PALAVRA{i}", i * 0.1, i * 0.1 + 0.09) for i in range(18)]
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(longo, end=1.8)]),
                                     1920, 1080, tmp_path / "ov")
    assert len(specs) == 18                          # não levanta nem perde palavra


def test_captions_burnin_timeline_sem_legenda_nao_muda(tmp_path):
    """Retrocompat: sem faixa de legenda, os specs são os mesmos de antes desta entrega."""
    editor = {"tracks": [{"type": "text", "visible": True, "items": [
        {"id": "tx1", "start": 0.0, "end": 2.0, "text": "GELO ZERO",
         "style": {"size": 64, "weight": 800, "color": "#FFFFFF"},
         "transform": {"x": .5, "y": .5, "scaleX": 1, "opacity": 1}},
        {"id": "tx2", "start": 2.0, "end": 4.0, "text": "SEM AÇÚCAR",
         "style": {"size": 40, "weight": 400, "color": "#FFEE00"},
         "transform": {"x": .5, "y": .2, "scaleX": 1, "opacity": 1}}]}]}
    specs = burnin.render_layer_pngs(tmp_path, editor, 1920, 1080, tmp_path / "ov")

    assert [(s["start"], s["end"]) for s in specs] == [(0.0, 2.0), (2.0, 4.0)]
    assert [Path(s["path"]).name for s in specs] == ["layer_000.png", "layer_001.png"]


def test_captions_burnin_acima_do_limiar_degrada_para_faixa_ffconcat(tmp_path, monkeypatch):
    monkeypatch.setattr(burnin, "MAX_OVERLAY_INPUTS", 5)
    seis = [(f"P{i}", i * 0.3, i * 0.3 + 0.25) for i in range(6)]
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(seis, end=1.8)]),
                                     1920, 1080, tmp_path / "ov")

    assert len(specs) == 1
    spec = specs[0]
    assert spec["kind"] == "concat" and spec["start"] == 0 and spec["end"] == 1.8
    assert 0 < spec["y"] < 1080
    linhas = Path(spec["path"]).read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "ffconcat version 1.0"
    files = [ln for ln in linhas if ln.startswith("file ")]
    assert len(files) == 7                           # 6 estados + a última entrada repetida
    assert files[-1] == files[-2]                    # o concat ignora a duração do último
    for i in range(6):                               # cada estado traz a sua duração
        assert linhas[1 + 2 * i].startswith("file ")
        assert linhas[2 + 2 * i].startswith("duration ")
        assert Path(linhas[1 + 2 * i][6:-1]).exists()
    faixa = Image.open(linhas[1][6:-1])
    assert faixa.width == 1920 and faixa.height < 1080   # faixa da altura da linha, não o quadro


def test_captions_burnin_faixa_comeca_com_quadro_vazio_quando_a_fala_atrasa(tmp_path, monkeypatch):
    monkeypatch.setattr(burnin, "MAX_OVERLAY_INPUTS", 5)
    seis = [(f"P{i}", 1.0 + i * 0.3, 1.0 + i * 0.3 + 0.25) for i in range(6)]
    specs = burnin.render_layer_pngs(tmp_path, _editor([_cap_item(seis, start=1.0, end=2.8)]),
                                     1920, 1080, tmp_path / "ov")

    linhas = Path(specs[0]["path"]).read_text(encoding="utf-8").splitlines()
    assert linhas[1].endswith("_vazio.png'") and linhas[2] == "duration 1.000"
    assert len([ln for ln in linhas if ln.startswith("file ")]) == 8   # vazio + 6 + repetição
