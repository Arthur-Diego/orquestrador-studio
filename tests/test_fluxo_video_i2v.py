"""[extensão] Testes do passo i2v (workflow LTX + normalização + pipeline motion). Sem GPU/rede."""

from fluxo_video import pipeline, render, render_i2v
from fluxo_video.projeto import Projeto
from fluxo_video.schema import validar_estrutura
from tests.test_fluxo_video_schema import roteiro_valido


def test_build_ltx_graph_estrutura():
    g = render_i2v.build_ltx_graph("in.png", "um homem caminha ao amanhecer", seed=3)
    tipos = {k: v["class_type"] for k, v in g.items()}
    # nós essenciais do workflow LTXV presentes
    for esperado in ("CheckpointLoaderSimple", "CLIPLoader", "LTXVImgToVideo", "LTXVConditioning",
                     "LTXVScheduler", "SamplerCustom", "VAEDecode", "SaveVideo"):
        assert esperado in tipos.values(), esperado
    assert g["clip"]["inputs"]["type"] == "ltxv"            # encoder t5 no modo ltxv
    assert g["img"]["inputs"]["image"] == "in.png"
    assert g["sampler"]["inputs"]["noise_seed"] == 3
    # ligações-chave: LTXVImgToVideo alimenta conditioning e scheduler
    assert g["cond"]["inputs"]["positive"] == ["ltxv", 0]
    assert g["sched"]["inputs"]["latent"] == ["ltxv", 2]
    assert g["sampler"]["inputs"]["latent_image"] == ["ltxv", 2]


def test_escolher_video_prefere_extensao_de_video():
    arquivos = [{"filename": "algo.png"}, {"filename": "clipe.mp4"}]
    assert render_i2v._escolher_video(arquivos)["filename"] == "clipe.mp4"
    assert render_i2v._escolher_video([]) is None


def test_args_normalizar():
    a = render.args_normalizar("cru.mp4", "out.mp4")
    assert "scale=1080:1920" in " ".join(a) and "libx264" in a and "cru.mp4" in a


def test_montar_video_i2v_usa_animar_e_normalizar(tmp_path):
    roteiro = validar_estrutura(roteiro_valido())
    proj = Projeto(tmp_path / "proj")
    proj.preparar()
    for p in roteiro.planos:
        proj.imagem(p.n).write_bytes(b"i")
    animados, normalizados, prompts = [], [], []

    def fake_animar(img, prompt, raw, *, seed=0, **kw):
        animados.append((raw.name, seed))
        prompts.append(prompt)
        return raw

    def fake_normalizar(raw, saida, **kw):
        normalizados.append(saida.name)
        return saida

    def fake_concat(clips, saida, **kw):
        assert len(clips) == 3
        return saida

    final = pipeline.montar_video(roteiro, proj, motion="i2v", animar=fake_animar,
                                  normalizar=fake_normalizar, concat=fake_concat)
    assert final == proj.final
    assert animados[0] == ("plano01_raw.mp4", 1)          # seed = número do plano
    assert normalizados == ["plano01.mp4", "plano02.mp4", "plano03.mp4"]
    # o prompt de movimento inclui o image_prompt (longo) e o movimento
    assert "masterpiece" in prompts[0] or "anime" in prompts[0].lower() or len(prompts[0]) > 40


def test_prompt_movimento_e_descritivo():
    roteiro = validar_estrutura(roteiro_valido())
    p = roteiro.planos[0]
    prompt = pipeline._prompt_movimento(p)
    assert p.video_prompt.subject_movement in prompt and "Camera:" in prompt
