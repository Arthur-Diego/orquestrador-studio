"""[extensão] Testes do motor local (engine_local, render, pipeline, cli). Sem GPU, sem ffmpeg, sem rede."""

import json
from dataclasses import dataclass

import pytest

from fluxo_video import engine_local, pipeline, render
from fluxo_video.cli import build_parser, cmd_imagens, cmd_validar
from fluxo_video.projeto import Projeto, projeto_para, slugify
from fluxo_video.schema import validar_estrutura
from tests.test_fluxo_video_schema import roteiro_valido


@dataclass
class FakeProc:
    returncode: int
    stdout: str = ""
    stderr: str = ""


# ---------- engine_local ----------

def test_build_args_image_mood_e_anime():
    a = engine_local.build_args_image("um gato", preset="story", model="flux-schnell", seed=7)
    assert a[:2] == ["image", "um gato"] and "--preset" in a and "story" in a and "--seed" in a
    m = engine_local.build_args_mood("cena", "ref.png", preset="story", model="flux-dev")
    assert m[0] == "mood" and "--ref" in m and "--mode" in m and "mood" in m
    an = engine_local.build_args_anime("1girl", preset="retrato", ref="r.png")
    assert an[:2] == ["gerar", "1girl"] and "--preset" in an and "retrato" in an
    assert "--ref" in an and "--face" in an  # ref ativa o IPAdapter de rosto


def test_gerar_imagem_copia_saida_do_engine(tmp_path):
    produzida = tmp_path / "engine_out.png"
    produzida.write_bytes(b"img")
    calls = []

    def fake_runner(cmd, **kw):
        calls.append(cmd)
        return FakeProc(0, stdout=f"gerando...\n{produzida}\n")

    out = tmp_path / "fontes" / "plano01.png"
    ret = engine_local.gerar_imagem("prompt", out, motor="engine", bin="engine", runner=fake_runner)
    assert ret == out and out.exists() and out.read_bytes() == b"img"
    assert calls[0][0] == "engine" and calls[0][1] == "image"


def test_gerar_imagem_motor_anime(tmp_path):
    produzida = tmp_path / "a.png"
    produzida.write_bytes(b"i")
    calls = []

    def fake_runner(cmd, **kw):
        calls.append(cmd)
        return FakeProc(0, stdout=str(produzida))

    engine_local.gerar_imagem("1girl", tmp_path / "o.png", motor="anime", bin="anime", runner=fake_runner)
    assert calls[0][0] == "anime" and calls[0][1] == "gerar" and "--preset" in calls[0]


def test_gerar_imagem_falha_com_returncode(tmp_path):
    def fake_runner(cmd, **kw):
        return FakeProc(1, stderr="boom")
    with pytest.raises(engine_local.EngineError, match="retornou 1"):
        engine_local.gerar_imagem("p", tmp_path / "o.png", bin="engine", runner=fake_runner)


def test_resolve_bin_por_env(monkeypatch, tmp_path):
    (tmp_path / "anime").write_text("#!/bin/sh\n")
    monkeypatch.setenv("FLUXO_ENGINE_DIR", str(tmp_path))
    assert engine_local.resolve_bin("anime") == str(tmp_path / "anime")


# ---------- render (ffmpeg puro) ----------

def test_vf_kenburns_frames():
    assert "d=90:" in render._vf_kenburns(3.0, fps=30)  # 3s * 30fps = 90 frames
    assert "zoompan" in render._vf_kenburns(3.0)


def test_args_kenburns_e_concat():
    a = render.args_kenburns("img.png", "out.mp4", dur_s=4.0)
    assert "-loop" in a and "libx264" in a and "img.png" in a and "out.mp4" in a
    c = render.args_concat("lista.txt", "final.mp4")
    assert c[:4] == ["-y", "-f", "concat", "-safe"] and "copy" in c


def test_concat_vazio_erra(tmp_path):
    with pytest.raises(render.RenderError, match="vazia"):
        render.concat([], tmp_path / "f.mp4")


def test_concat_escreve_lista_e_chama_ffmpeg(tmp_path):
    clips = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    for c in clips:
        c.write_bytes(b"x")
    chamado = {}

    def fake_runner(cmd, **kw):
        chamado["cmd"] = cmd
        return FakeProc(0)
    out = render.concat(clips, tmp_path / "final.mp4", runner=fake_runner)
    assert out == tmp_path / "final.mp4"
    assert (tmp_path / "concat.txt").exists()
    assert chamado["cmd"][0] == "ffmpeg"


# ---------- pipeline (orquestração) ----------

def test_gerar_imagens_encadeia_ancora_de_identidade(tmp_path):
    roteiro = validar_estrutura(roteiro_valido())
    proj = Projeto(tmp_path / "proj")
    calls = []

    def fake_gerar(prompt, out, *, motor="anime", model=None, ref=None, **kw):
        calls.append((out.name, ref))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"i")
        return out

    caminhos = pipeline.gerar_imagens(roteiro, proj, gerar=fake_gerar)
    assert len(caminhos) == 3
    assert calls[0] == ("personagem.png", None)          # 1ª chamada = retrato-âncora (character sheet)
    assert calls[1] == ("plano01.png", proj.personagem)  # cada plano usa o character sheet como ref
    assert calls[2][1] == proj.personagem and calls[3][1] == proj.personagem


def test_plano_sem_personagem_nao_usa_ancora(tmp_path):
    dados = roteiro_valido()
    dados["cenas"][1]["planos"][0]["personagem"] = False  # plano do meio = cenário puro
    roteiro = validar_estrutura(dados)
    proj = Projeto(tmp_path / "proj")
    refs = {}

    def fake_gerar(prompt, out, *, motor="anime", model=None, ref=None, **kw):
        refs[out.name] = ref
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"i")
        return out

    pipeline.gerar_imagens(roteiro, proj, gerar=fake_gerar)
    assert refs["plano02.png"] is None               # cenário puro → sem âncora
    assert refs["plano01.png"] == proj.personagem     # personagem → com âncora


def test_gerar_imagens_sem_identidade(tmp_path):
    roteiro = validar_estrutura(roteiro_valido())
    proj = Projeto(tmp_path / "proj")

    def fake_gerar(prompt, out, *, motor="anime", model=None, ref=None, **kw):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"i")
        assert ref is None
        return out

    pipeline.gerar_imagens(roteiro, proj, seguir_identidade=False, gerar=fake_gerar)


def test_montar_video_exige_imagens(tmp_path):
    roteiro = validar_estrutura(roteiro_valido())
    proj = Projeto(tmp_path / "proj")
    proj.preparar()
    with pytest.raises(FileNotFoundError, match="plano 1"):
        pipeline.montar_video(roteiro, proj)


def test_montar_video_gera_clipes_e_concatena(tmp_path):
    roteiro = validar_estrutura(roteiro_valido())
    proj = Projeto(tmp_path / "proj")
    proj.preparar()
    for p in roteiro.planos:
        proj.imagem(p.n).write_bytes(b"i")
    clipes = []

    def fake_render(img, saida, *, dur_s, **kw):
        clipes.append((saida.name, dur_s))
        return saida

    def fake_concat(clips, saida, **kw):
        assert len(clips) == 3
        return saida

    final = pipeline.montar_video(roteiro, proj, render_clip=fake_render, concat=fake_concat)
    assert final == proj.final
    assert clipes[0] == ("plano01.mp4", 5.0)


# ---------- projeto + cli ----------

def test_slugify_e_projeto_para():
    assert slugify("Meu Vídeo Incrível!") == "meu-v-deo-incr-vel"
    assert projeto_para("Teste").raiz.name == "teste"


def test_cli_parser_liga_subcomandos():
    args = build_parser().parse_args(["imagens", "r.json", "--model", "flux-dev"])
    assert args.func is cmd_imagens and args.model == "flux-dev"
    assert build_parser().parse_args(["validar", "r.json"]).func is cmd_validar


def test_cli_validar_ok(tmp_path):
    from fluxo_video.cli import main
    caminho = tmp_path / "r.json"
    caminho.write_text(json.dumps(roteiro_valido()), encoding="utf-8")
    assert main(["validar", str(caminho)]) == 0
