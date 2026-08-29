"""Etapa 8 — bloco `editor` (editor de vídeo completo, [extensão]).

Cobre: normalização/round-trip do modelo rico, clamps de faixa, bloqueio de path traversal e,
o mais importante, RETROCOMPATIBILIDADE — timeline sem `editor` continua sendo a montagem da
aula 014, sem nenhum campo novo no round-trip.
"""
from __future__ import annotations

import pytest

from studio.edit import editor as ed
from studio.edit import render
from tests.test_edit_service import seed


def _mini_timeline() -> dict:
    return {"clips": [{"id": "c1", "scene": "c", "shot": "s", "take": "t", "file": "videos/x.mp4",
                       "in": 0.0, "out": 2.0, "speed": 1.0, "blend": True, "zoom": 1.0}],
            "blacks": [], "music": {"file": None, "offset": 0.0}, "sfx": [], "fade_out": 0.0,
            "loudnorm": True}


def _crf(args: list[str]) -> str:
    return args[args.index("-crf") + 1]


def test_export_default_is_1080_30(tmp_path):
    args, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master")
    joined = " ".join(args)
    assert "scale=1280:720" not in joined            # sem rescale de saída
    assert args[args.index("-r") + 1] == "30"


def test_export_resolution_and_fps(tmp_path):
    args, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master",
                                       width=1280, height=720, fps=24)
    joined = " ".join(args)
    assert "scale=1280:720:force_original_aspect_ratio=decrease" in joined
    assert args[args.index("-r") + 1] == "24"


def test_export_quality_maps_crf(tmp_path):
    high, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master", quality="high")
    low, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master", quality="low")
    assert int(_crf(high)) < int(_crf(low))


# ---------- fase 2: burn-in das camadas do editor no render ----------
def test_clip_fx_chain_maps_adjustments(tmp_path):
    tl = _mini_timeline()
    tl["editor"] = {"clip_fx": {"c1": {"filters": {"contrast": 50, "saturation": 20, "hue": 10},
                                       "effects": [{"type": "blur", "intensity": 0.5, "enabled": True}]}}}
    args, _ = render.build_filtergraph(tmp_path, tl, "master")
    joined = " ".join(args)
    assert "eq=" in joined and "contrast=1.5" in joined
    assert "hue=h=18" in joined
    assert "gblur=sigma=5" in joined
    # sem clip_fx, nenhum eq (backbone intacto)
    plain, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master")
    assert "eq=" not in " ".join(plain)


def test_overlays_composited_with_time_gate(tmp_path):
    png = tmp_path / "layer.png"
    png.write_bytes(b"x")
    args, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master",
                                       overlays=[{"path": str(png), "start": 0.5, "end": 1.5}])
    joined = " ".join(args)
    assert "overlay=0:0:enable='between(t,0.5,1.5)'" in joined
    assert str(png) in joined                       # o PNG entra como input
    # sem overlays, nenhum filtro overlay (retrocompat)
    plain, _ = render.build_filtergraph(tmp_path, _mini_timeline(), "master")
    assert "overlay=0:0" not in " ".join(plain)


def test_positional_gap_becomes_black(tmp_path):
    """[extensão] clipes com `start` livre: o espaço entre eles vira preto no render."""
    def mk(cid, f, start):
        return {"id": cid, "scene": "c", "shot": "s", "take": "t", "file": f,
                "in": 0.0, "out": 2.0, "speed": 1.0, "blend": True, "zoom": 1.0, "start": start}
    tl = {"clips": [mk("c1", "videos/a.mp4", 0.0), mk("c2", "videos/b.mp4", 5.0)],
          "blacks": [], "music": {"file": None, "offset": 0.0}, "sfx": [], "fade_out": 0.0, "loudnorm": True}
    args, dur = render.build_filtergraph(tmp_path, tl, "master")
    joined = " ".join(args)
    assert "color=black" in joined                 # o gap (2s→5s) vira preto
    assert "concat=n=3" in joined                  # clip + preto + clip
    assert abs(dur - 7.0) < 0.05                    # 2 + 3(gap) + 2
    # sem `start` = sequencial (colado, sem gap): concat=n=2
    seq = {**tl, "clips": [{k: v for k, v in c.items() if k != "start"} for c in tl["clips"]]}
    a2, _ = render.build_filtergraph(tmp_path, seq, "master")
    assert "concat=n=2" in " ".join(a2) and "color=black" not in " ".join(a2)


def test_put_preserves_clip_start(client, project, root):
    """A posição livre do clipe (`start`) faz round-trip no PUT/GET."""
    seed(root)
    tl = client.get(_url(project, "/timeline")).json()["timeline"]
    body = _legacy_body(tl)
    body["clips"][0]["start"] = 3.5
    saved = client.put(_url(project, "/timeline"), json=body).json()["timeline"]
    assert saved["clips"][0]["start"] == 3.5
    assert "start" not in saved["clips"][1]        # clipe sem start continua sequencial


def test_burnin_renders_text_layer_png(tmp_path):
    from studio.edit import burnin
    editor = {"tracks": [{"type": "text", "visible": True, "items": [
        {"id": "tx1", "start": 0.0, "end": 2.0, "text": "GELO ZERO",
         "style": {"size": 64, "weight": 800, "color": "#FFFFFF"},
         "transform": {"x": .5, "y": .5, "scaleX": 1, "opacity": 1}}]}]}
    specs = burnin.render_layer_pngs(tmp_path, editor, 1920, 1080, tmp_path / "ov")
    assert len(specs) == 1
    assert specs[0]["start"] == 0.0 and specs[0]["end"] == 2.0
    from pathlib import Path as P
    assert P(specs[0]["path"]).exists()


# ---------- normalização pura (sem ffmpeg, sem app) ----------
def sample_editor() -> dict:
    return {
        "version": 1,
        "project": {"width": 1080, "height": 1920, "fps": 30, "aspect": "9:16"},
        "tracks": [
            {"id": "t1", "type": "text", "name": "Texto", "items": [
                {"id": "tx1", "start": 0.0, "end": 2.5, "text": "Olá mundo",
                 "style": {"size": 72, "color": "#FFEE00", "align": "left"},
                 "transform": {"x": 0.5, "y": 0.2, "rotation": 10}}]},
            {"id": "s1", "type": "sfx", "items": [
                {"id": "sf1", "file": "edit/candidates/x.wav", "start": 0.5, "gain": -6}]},
        ],
        "transitions": [{"id": "tr1", "from": "c_a", "to": "c_b", "type": "dissolve", "duration": 0.5}],
        "markers": [{"id": "mk1", "at": 1.2, "name": "Hook"}],
        "ui": {"zoom": 1.5, "snap": True},
    }


def test_none_and_malformed(tmp_path):
    assert ed.normalize_editor(tmp_path, None) is None
    with pytest.raises(ed.EditorError):
        ed.normalize_editor(tmp_path, "não é dict")


def test_roundtrip_idempotent(tmp_path):
    once = ed.normalize_editor(tmp_path, sample_editor())
    twice = ed.normalize_editor(tmp_path, once)
    assert once == twice
    assert once["project"] == {"width": 1080, "height": 1920, "fps": 30, "aspect": "9:16"}
    assert once["tracks"][0]["items"][0]["text"] == "Olá mundo"
    assert once["tracks"][0]["items"][0]["style"]["color"] == "#FFEE00"
    assert once["tracks"][1]["items"][0]["gain"] == -6.0


def test_clamps_never_reject(tmp_path):
    raw = {
        "project": {"width": 99999, "height": 5, "fps": 59, "aspect": "banana"},
        "tracks": [
            {"type": "text", "items": [
                {"text": "x", "style": {"opacity": 5, "size": 9000},
                 "transform": {"rotation": 999, "opacity": -3}}]},
            {"type": "sfx", "items": [{"file": "edit/x.wav", "gain": -99}]},
        ],
        "transitions": [{"type": "dissolve", "duration": 9}],
    }
    e = ed.normalize_editor(tmp_path, raw)
    assert e["project"]["width"] == 8192
    assert e["project"]["height"] == 16
    assert e["project"]["fps"] == 60          # 59 -> 60 (mais próximo)
    assert e["project"]["aspect"] == "16:9"   # inválido -> default
    txt = e["tracks"][0]["items"][0]
    assert txt["style"]["opacity"] == 1.0
    assert txt["style"]["size"] == ed.FONT_SIZE_RANGE[1]
    assert txt["transform"]["rotation"] == 360.0
    assert txt["transform"]["opacity"] == 0.0
    assert e["tracks"][1]["items"][0]["gain"] == -40.0
    assert e["transitions"][0]["duration"] == 3.0


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(ed.EditorError):
        ed.normalize_editor(tmp_path, {"tracks": [
            {"type": "overlay", "items": [{"src": "../../etc/passwd"}]}]})
    with pytest.raises(ed.EditorError):
        ed.normalize_editor(tmp_path, {"tracks": [
            {"type": "sfx", "items": [{"file": "../secret.wav"}]}]})


def test_unknown_track_and_item_dropped(tmp_path):
    e = ed.normalize_editor(tmp_path, {"tracks": [
        {"type": "inexistente", "items": [{"text": "x"}]},
        {"type": "text", "items": ["não é dict", {"text": "ok"}]}]})
    assert len(e["tracks"]) == 1                 # a track de tipo inválido some
    assert len(e["tracks"][0]["items"]) == 1     # o item inválido some, o válido fica


def test_ids_generated_when_missing(tmp_path):
    e = ed.normalize_editor(tmp_path, {"tracks": [{"type": "text", "items": [{"text": "a"}]}]})
    assert e["tracks"][0]["id"]
    assert e["tracks"][0]["items"][0]["id"]


def test_transition_type_is_case_insensitive(tmp_path):
    """AP-09: o painel manda o rótulo ("Glitch"); sem normalizar a caixa tudo virava dissolve."""
    e = ed.normalize_editor(tmp_path, {"transitions": [
        {"id": "tr1", "from": "c1", "to": "c2", "type": "Glitch"},
        {"id": "tr2", "from": "c2", "to": "c3", "type": " Wipe ",
         "config": {"direction": "Right", "easing": "Ease-In"}},
        {"id": "tr3", "from": "c3", "to": "c4", "type": "inexistente"}]})
    assert [t["type"] for t in e["transitions"]] == ["glitch", "wipe", "dissolve"]
    assert e["transitions"][1]["config"]["direction"] == "right"
    assert e["transitions"][1]["config"]["easing"] == "ease-in"


def test_overlay_keeps_shape_and_text(tmp_path):
    """AP-07: elemento do painel Elementos guarda `shape` + `text` — sem isso vira quadrado vazio."""
    e = ed.normalize_editor(tmp_path, {"tracks": [
        {"id": "v2", "type": "overlay", "items": [
            {"id": "ov1", "start": 0, "end": 3, "text": "★", "shape": "★"},
            {"id": "ov2", "start": 0, "end": 1, "shape": "x" * 40, "text": "y" * (ed.MAX_TEXT + 10)},
            {"id": "ov3", "start": 0, "end": 1}]}]})
    itens = e["tracks"][0]["items"]
    assert itens[0]["shape"] == "★" and itens[0]["text"] == "★"
    assert len(itens[1]["shape"]) == ed.MAX_SHAPE and len(itens[1]["text"]) == ed.MAX_TEXT
    assert "shape" not in itens[2] and "text" not in itens[2]   # overlay de mídia não ganha campo


def test_ui_zoom_is_a_factor(tmp_path):
    """AP-06: o frontend grava `ui.zoom` como FATOR (0.25–4, default 1) — o backend preserva."""
    e = ed.normalize_editor(tmp_path, {"ui": {"zoom": 2.5, "snap": False}})
    assert e["ui"] == {"zoom": 2.5, "snap": False}
    assert ed.normalize_editor(tmp_path, {"ui": {"zoom": 0.25}})["ui"]["zoom"] == 0.25
    assert ed.normalize_editor(tmp_path, {})["ui"]["zoom"] == 1.0          # default = 1x
    assert ed.normalize_editor(tmp_path, {"ui": {"zoom": 0.01}})["ui"]["zoom"] == 0.25
    # px/s de timelines antigas (2–400) não vira 400% de zoom: volta ao default
    assert ed.normalize_editor(tmp_path, {"ui": {"zoom": 40}})["ui"]["zoom"] == 1.0
    assert ed.editor_from_legacy({})["ui"]["zoom"] == 1.0


def test_clip_fx_map(tmp_path):
    e = ed.normalize_editor(tmp_path, {"clip_fx": {
        "c_001": {"transform": {"x": 0.3}, "filters": {"brightness": 20, "desconhecido": 5}}}})
    fx = e["clip_fx"]["c_001"]
    assert fx["transform"]["x"] == 0.3
    assert fx["filters"] == {"brightness": 20.0}   # chave desconhecida descartada
    assert "audio" not in fx                       # sem a aba Áudio tocada, nada é inventado


def test_clip_fx_keeps_audio_and_preset(tmp_path):
    """AP-08: aba Áudio do clipe (FDD §7.4) e preset do painel Filtros sobrevivem ao round-trip."""
    e = ed.normalize_editor(tmp_path, {"clip_fx": {"c_001": {
        "filters": {"contrast": 10, "preset": "cinema"}, "presetCss": "saturate(1.2) contrast(1.1)",
        "audio": {"volume": 1.5, "muted": True, "fadeIn": 0.5, "fadeOut": 2,
                  "normalize": True, "enhance": True, "denoise": False}}}})
    fx = e["clip_fx"]["c_001"]
    assert fx["audio"] == {"volume": 1.5, "muted": True, "fadeIn": 0.5, "fadeOut": 2.0,
                           "normalize": True, "enhance": True, "denoise": False}
    assert fx["filters"] == {"contrast": 10.0, "preset": "cinema"}
    assert fx["presetCss"] == "saturate(1.2) contrast(1.1)"
    assert ed.normalize_editor(tmp_path, e) == e   # idempotente
    # volume do clipe vai a 150% sem ser cortado em 1.0, mas nada passa de 2
    alto = ed.normalize_editor(tmp_path, {"clip_fx": {"c1": {"audio": {"volume": 9}}}})
    assert alto["clip_fx"]["c1"]["audio"]["volume"] == 2.0


def test_clip_fx_keeps_vfx_and_radius(tmp_path):
    """AP-08: os toggles da aba Vídeo (`vfx`) e o border radius sobrevivem ao round-trip."""
    e = ed.normalize_editor(tmp_path, {"clip_fx": {"c_001": {
        "vfx": {"crop": True, "chroma": False, "inventado": True}, "radius": 24}}})
    fx = e["clip_fx"]["c_001"]
    assert fx["vfx"] == {"crop": True, "chroma": False}   # chave fora do painel é descartada
    assert fx["radius"] == 24
    assert ed.normalize_editor(tmp_path, e) == e          # idempotente
    # sem tocar a aba Vídeo, nada é inventado; o raio é clampado em 0–200
    limpo = ed.normalize_editor(tmp_path, {"clip_fx": {"c1": {"filters": {}}}})["clip_fx"]["c1"]
    assert "vfx" not in limpo and "radius" not in limpo
    alto = ed.normalize_editor(tmp_path, {"clip_fx": {"c1": {"radius": 900}}})
    assert alto["clip_fx"]["c1"]["radius"] == 200


def test_overlay_keeps_preset_css(tmp_path):
    """AP-08: o preset de filtro também é gravado no próprio item quando o alvo é um overlay."""
    e = ed.normalize_editor(tmp_path, {"tracks": [{"type": "overlay", "items": [
        {"id": "ov1", "filters": {"preset": "vhs"}, "presetCss": "sepia(.3)"}]}]})
    item = e["tracks"][0]["items"][0]
    assert item["filters"] == {"preset": "vhs"} and item["presetCss"] == "sepia(.3)"


# ---------- API: retrocompatibilidade e round-trip ----------
@pytest.fixture()
def project(studio_env):
    return studio_env["refs"].create_project("Gelo Zero", "energy drink", "snow neon")["id"]


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


def _url(pid: str, path: str = "") -> str:
    return f"/api/projects/{pid}/edit{path}"


def _legacy_body(tl: dict) -> dict:
    return {k: tl[k] for k in ("clips", "blacks", "music", "sfx", "fade_out")}


def test_put_without_editor_is_legacy(client, project, root):
    """Sem bloco `editor`, o round-trip é exatamente o schema da aula 014 — nada novo aparece."""
    seed(root)
    tl = client.get(_url(project, "/timeline")).json()["timeline"]
    r = client.put(_url(project, "/timeline"), json=_legacy_body(tl))
    assert r.status_code == 200
    assert "editor" not in r.json()["timeline"]


def test_clips_have_stable_ids(client, project, root):
    seed(root)
    tl = client.get(_url(project, "/timeline")).json()["timeline"]
    assert tl["clips"] and all(c.get("id") for c in tl["clips"])
    # o id é preservado no round-trip
    saved = client.put(_url(project, "/timeline"), json=_legacy_body(tl)).json()["timeline"]
    assert [c["id"] for c in saved["clips"]] == [c["id"] for c in tl["clips"]]


def test_put_with_editor_roundtrips(client, project, root):
    seed(root)
    tl = client.get(_url(project, "/timeline")).json()["timeline"]
    payload = {**_legacy_body(tl), "editor": sample_editor()}
    r = client.put(_url(project, "/timeline"), json=payload)
    assert r.status_code == 200
    editor = r.json()["timeline"]["editor"]
    assert editor["project"]["aspect"] == "9:16"
    assert editor["tracks"][0]["items"][0]["text"] == "Olá mundo"
    # persistiu: um novo GET traz o mesmo editor
    again = client.get(_url(project, "/timeline")).json()["timeline"]["editor"]
    assert again == editor


def test_put_editor_traversal_is_422(client, project, root):
    seed(root)
    tl = client.get(_url(project, "/timeline")).json()["timeline"]
    bad = {**_legacy_body(tl), "editor": {"tracks": [
        {"type": "overlay", "items": [{"src": "../../../etc/passwd"}]}]}}
    assert client.put(_url(project, "/timeline"), json=bad).status_code == 422
