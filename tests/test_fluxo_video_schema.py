"""[extensão] Testes do schema + validador de congruência do fluxo_video. Sem rede, sem GPU."""

import copy
import json

import pytest

from fluxo_video.schema import RoteiroInvalido, carregar_roteiro, validar_estrutura
from fluxo_video.validador import validar_congruencia


def _plano(n, scene_key, duration_s, palavras, narration, beats, estilo):
    return {
        "n": n, "scene_key": scene_key, "duration_s": duration_s, "palavras": palavras,
        "narration": narration, "headline": "GANCHO", "body": "", "visual": "resumo pt-BR",
        "image_prompt": f"{estilo}, wide shot of a city at dusk", "image_negative": "text, logo",
        "video_prompt": {
            "subject": "personagem", "subject_movement": "anda", "scene_description": "cidade",
            "camera": "slow push in", "lighting": "golden hour", "atmosphere": "nostálgica",
            "beats": beats, "negative_extra": "blur",
        },
        "transicao": "cut", "sfx": "whoosh",
    }


def roteiro_valido() -> dict:
    """Roteiro mínimo, estruturalmente válido E congruente (3 cenas, 3 planos, 15s)."""
    estilo = "anime 2D cinematic"
    planos = [
        _plano(1, "gancho", 5.0, 12, "primeira fala do gancho aqui neste plano de abertura agora",
               [{"seconds": 2.0, "prompt": "a"}, {"seconds": 3.0, "prompt": "b"}], estilo),
        _plano(2, "virada", 6.0, 12, "a virada acontece e muda tudo para o espectador de vez",
               [{"seconds": 6.0, "prompt": "c"}], estilo),
        _plano(3, "cta", 4.0, 12, "chamada final para acao siga o perfil e ative o sininho ja",
               [{"seconds": 4.0, "prompt": "d"}], estilo),
    ]
    return {
        "version": "1.0",
        "meta": {
            "titulo": "Teste", "essencia": "uma frase", "content_type": "reel",
            "aspect_ratio": "9:16", "target_duration_s": 15, "duracao_total_s": 15.0,
            "palavras_total": 36, "persona": "criador", "tom": "direto", "idioma": "pt-BR",
        },
        "identidade_visual": {
            "estilo": estilo, "paleta": "quente",
            "personagem": {"nome": "Aria", "descriptor": "cabelo azul", "negative": "sem óculos"},
            "negative_base": "text, watermark", "ancora": "primeiro plano",
        },
        "cenas": [
            {"key": "gancho", "label": "Gancho", "objetivo": "prender", "planos": [planos[0]]},
            {"key": "virada", "label": "Virada", "objetivo": "revelar", "planos": [planos[1]]},
            {"key": "cta", "label": "CTA", "objetivo": "agir", "planos": [planos[2]]},
        ],
        "narracao_completa": {
            "texto": " ".join(p["narration"] for p in planos),
            "segments": [
                {"plano_n": p["n"], "scene_key": p["scene_key"], "text": p["narration"]}
                for p in planos
            ],
        },
        "publicacao": {"legenda_post": "post", "hashtags": ["#a", "#b"], "cta_unico": "siga"},
        "audio": {"voz_sugerida": "grave", "musica": "lofi", "sfx_gerais": "—"},
        "fontes": [],
        "validacao": {
            "por_plano": [{"n": p["n"], "ok": True, "notas": ""} for p in planos],
            "conjunto": {
                "progressao_sem_repeticao": True, "prova_responde_gancho": True, "cta_unico": True,
                "duracao_ok": True, "palavras_ok": True, "virada_maior_bloco": True,
                "identidade_consistente": True, "essencia_preservada": True, "notas": "",
            },
            "aprovado_para_producao": True,
        },
    }


# ---------- schema ----------

def test_schema_aceita_roteiro_valido():
    r = validar_estrutura(roteiro_valido())
    assert r.version == "1.0"
    assert [p.n for p in r.planos] == [1, 2, 3]


def test_carregar_roteiro_de_arquivo(tmp_path):
    caminho = tmp_path / "roteiro.json"
    caminho.write_text(json.dumps(roteiro_valido()), encoding="utf-8")
    r = carregar_roteiro(caminho)
    assert r.meta.titulo == "Teste"


def test_arquivo_inexistente():
    with pytest.raises(RoteiroInvalido, match="não encontrado"):
        carregar_roteiro("/nao/existe.json")


def test_campo_desconhecido_e_rejeitado():
    dados = roteiro_valido()
    dados["campo_extra"] = 1
    with pytest.raises(RoteiroInvalido, match="fora do schema"):
        validar_estrutura(dados)


def test_menos_de_tres_cenas_rejeitado():
    dados = roteiro_valido()
    dados["cenas"] = dados["cenas"][:2]
    with pytest.raises(RoteiroInvalido):
        validar_estrutura(dados)


# ---------- congruência ----------

def test_congruencia_ok():
    rel = validar_congruencia(validar_estrutura(roteiro_valido()))
    assert rel.ok, rel.resumo()
    assert not rel.avisos, rel.resumo()


def test_n_nao_contiguo_e_erro():
    dados = roteiro_valido()
    dados["cenas"][2]["planos"][0]["n"] = 9
    dados["narracao_completa"]["segments"][2]["plano_n"] = 9
    rel = validar_congruencia(validar_estrutura(dados))
    assert not rel.ok
    assert any("contíguo" in e for e in rel.erros)


def test_scene_key_divergente_e_erro():
    dados = roteiro_valido()
    dados["cenas"][1]["planos"][0]["scene_key"] = "prova"  # cena é 'virada'
    rel = validar_congruencia(validar_estrutura(dados))
    assert any("scene_key" in e for e in rel.erros)


def test_beats_nao_cobrem_duracao_e_erro():
    dados = roteiro_valido()
    dados["cenas"][0]["planos"][0]["video_prompt"]["beats"] = [{"seconds": 1.0, "prompt": "x"}]
    rel = validar_congruencia(validar_estrutura(dados))
    assert any("beats somam" in e for e in rel.erros)


def test_duracao_fora_do_alvo_e_erro():
    dados = roteiro_valido()
    dados["cenas"][1]["planos"][0]["duration_s"] = 14.0  # total vira 23s vs alvo 15
    dados["cenas"][1]["planos"][0]["video_prompt"]["beats"] = [{"seconds": 14.0, "prompt": "c"}]
    rel = validar_congruencia(validar_estrutura(dados))
    assert any("duração total" in e for e in rel.erros)


def test_segments_faltando_e_erro():
    dados = roteiro_valido()
    dados["narracao_completa"]["segments"].pop()
    rel = validar_congruencia(validar_estrutura(dados))
    assert any("segments" in e for e in rel.erros)


def test_virada_nao_maior_e_apenas_aviso():
    dados = roteiro_valido()
    # encolhe a virada e cresce o cta, mantendo o total 15s e os beats coerentes
    dados["cenas"][1]["planos"][0]["duration_s"] = 3.0
    dados["cenas"][1]["planos"][0]["video_prompt"]["beats"] = [{"seconds": 3.0, "prompt": "c"}]
    dados["cenas"][2]["planos"][0]["duration_s"] = 7.0
    dados["cenas"][2]["planos"][0]["video_prompt"]["beats"] = [{"seconds": 7.0, "prompt": "d"}]
    rel = validar_congruencia(validar_estrutura(dados))
    assert rel.ok  # continua válido…
    assert any("virada" in a for a in rel.avisos)  # …mas avisa


def test_base_fixture_nao_vaza_entre_casos():
    a = roteiro_valido()
    b = copy.deepcopy(a)
    a["meta"]["titulo"] = "outro"
    assert b["meta"]["titulo"] == "Teste"
