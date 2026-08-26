"""Etapa 11 — Prospecção: a aula 001 no serviço (gate, script literal, contador, teaser, pitch)."""
import json
import time
from datetime import date, datetime, timedelta

import pytest

from studio.common import ffmpeg as ff
from tests.conftest import make_audio, make_video

# Script literal do instrutor (aula 001) com as quatro substituições — sem nenhum link.
DM_LITERAL = (
    "Oi Padaria do Zé. Eu sou consumidor da sua marca. O seu post a respeito de o pão de fermentação natural "
    "das 6h realmente ressoou comigo. Quero ser bem direto: eu produzo anúncios criativos para marcas. Você pode "
    "acompanhar meu portfólio no meu perfil. Tive uma inspiração e criei algo para o seu negócio. "
    "Quer ver como ficou?"
)
FOLLOWUP_LITERAL = (
    "Aqui está o início. Se quiser, podemos agendar uma call de 15 minutinhos e te explico a minha ideia para "
    "esse anúncio completo."
)


@pytest.fixture()
def svc(studio_env):
    return studio_env["svc"]("prospect")


@pytest.fixture()
def root(studio_env):
    refs = studio_env["refs"]
    return refs.project_dir(refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"])


def publish_log(root, videos):
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text(json.dumps(
        [{"id": f"p{i}", "video": v, "network": "instagram", "url": f"https://exemplo/{i}",
          "posted_at": "2026-08-20", "note": ""} for i, v in enumerate(videos)]), encoding="utf-8")


def outro_projeto(root, slug, videos=("export/9x16.mp4",)):
    """Cria um projeto irmão com posts registrados — uma OBRA a mais no portfólio global."""
    other = root.parent / slug
    other.mkdir(parents=True, exist_ok=True)
    (other / "project.json").write_text(json.dumps({"id": slug, "name": slug}), encoding="utf-8")
    publish_log(other, list(videos))
    return other


def open_gate(root, n=4):
    """Portfólio GLOBAL (ADR-012): `n` PROJETOS distintos com pelo menos um post registrado."""
    publish_log(root, ["export/9x16.mp4"])
    for i in range(1, n):
        outro_projeto(root, f"2026-08-obra-{i}")


def a_lead(svc, root, handle="@padariadoze"):
    return svc.create_lead(root, "Padaria do Zé", handle, "o pão de fermentação natural das 6h",
                           "fotos com luz de manhã", "consumidor")


def lead_respondido(svc, root, handle="@padariadoze"):
    """A aula manda criar o teaser só depois da resposta: `new → dm_sent → replied`."""
    lid = a_lead(svc, root, handle)["id"]
    svc.mark_sent(root, lid)
    svc.mark_replied(root, lid)
    return lid


# ---------- gate: 4 vídeos publicados (aula 015 → 001) ----------
def test_gate_conta_projetos_distintos_nao_arquivos(svc, root):
    """Auditoria 10.1/11.2: '4 vídeos' são 4 OBRAS — os formatos do mesmo projeto contam 1."""
    publish_log(root, ["export/16x9.mp4", "export/9x16.mp4", "export/1x1.mp4", "export/extra.mp4"])
    g = svc.gate(root)
    assert g["published"] == 1 and g["posts"] == 4 and g["ok"] is False
    assert g["message"] == "A aula pede quatro obras diferentes antes de prospectar — faltam 3 campanhas."
    assert g["this_project_published"] is True


def test_gate_abre_com_quatro_projetos_distintos(svc, root):
    open_gate(root)
    g = svc.gate(root)
    assert g["ok"] is True and g["published"] == 4
    assert [p["project_id"] for p in g["projects"]][0].startswith("2026-08"), "lista as obras do portfólio"


def test_gate_conta_projeto_do_lead_e_os_outros(svc, root):
    """O projeto do lead pode nem estar publicado: o portfólio vem dos projetos anteriores."""
    for i in range(1, 5):
        outro_projeto(root, f"2026-08-obra-{i}")
    g = svc.gate(root)
    assert g["ok"] is True and g["published"] == 4
    assert g["this_project_published"] is False, "este projeto ainda não tem post e o gate abre assim mesmo"


def test_gate_sem_log_ou_com_json_invalido_conta_zero(svc, root):
    g = svc.gate(root)
    assert g["published"] == 0 and g["posts"] == 0 and g["required"] == 4 and g["ok"] is False
    assert g["message"] == "A aula pede quatro obras diferentes antes de prospectar — faltam 4 campanhas."
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text("{isso não é json", encoding="utf-8")
    assert svc.gate(root)["published"] == 0, "log inválido conta como zero e nunca levanta"


def test_gate_fechado_bloqueia_qualquer_escrita(svc, root):
    with pytest.raises(svc.GateClosed) as e:
        a_lead(svc, root)
    assert "quatro obras diferentes" in str(e.value)
    assert not svc.leads_file(root).exists(), "nada é escrito em prospect/ com o gate fechado"


# ---------- DM: o script literal, sem links ----------
def test_dm_e_o_script_literal_da_aula_sem_link(svc, root):
    open_gate(root)
    lead = a_lead(svc, root)
    assert lead["dm_text"] == DM_LITERAL
    baixo = lead["dm_text"].lower()
    assert "http" not in baixo and "www." not in baixo and ".com" not in baixo, "aula 001: DM com link cai em spam"


def test_followup_e_literal(svc):
    assert svc.followup_text() == FOLLOWUP_LITERAL


def test_lead_normaliza_handle_e_valida_campos(svc, root):
    open_gate(root)
    lead = a_lead(svc, root, "@PadariaDoZé")
    assert lead["handle"] == "padariadozé" and lead["id"] == "padariadoz" and lead["status"] == "new"
    with pytest.raises(ValueError):
        svc.create_lead(root, "", "@outro", "um post")
    with pytest.raises(ValueError):
        svc.create_lead(root, "Outro", "  ", "um post")
    with pytest.raises(ValueError, match="role"):
        svc.create_lead(root, "Outro", "@outro", "um post", role="parceiro")
    with pytest.raises(ValueError, match="já cadastrado"):
        svc.create_lead(root, "Padaria de novo", "@PadariaDoZé", "um post")
    with pytest.raises(ValueError, match="2000"):
        svc.create_lead(root, "Outro", "@outro2", post_ref="x" * 2001)


def test_post_ref_e_obrigatorio_na_criacao_e_na_edicao(svc, root):
    """11.3: 'não é spam porque você personaliza… menciona um post específico'."""
    open_gate(root)
    with pytest.raises(ValueError, match="post específico"):
        svc.create_lead(root, "Padaria do Zé", "@padariadoze")
    with pytest.raises(ValueError, match="post específico"):
        svc.create_lead(root, "Padaria do Zé", "@padariadoze", post_ref="   ")
    lid = a_lead(svc, root)["id"]
    with pytest.raises(ValueError, match="post específico"):
        svc.update_lead(root, lid, post_ref="  ")
    assert svc.get_lead(root, lid)["post_ref"] == "o pão de fermentação natural das 6h", "nada mudou"


# ---------- contador N/10 hoje (meta, nunca trava) ----------
def test_today_sent_conta_so_hoje_e_nao_bloqueia(svc, root):
    open_gate(root)
    ontem = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    for i in range(3):
        svc.mark_sent(root, svc.create_lead(root, f"Hoje {i}", f"@hoje{i}", "o post de hoje")["id"])
    for i in range(2):
        svc.mark_sent(root, svc.create_lead(root, f"Ontem {i}", f"@ontem{i}", "o post de ontem")["id"], ontem)
    leads = svc.load_leads(root)
    assert svc.today_sent(leads) == 3
    assert svc.today_sent(leads, date.today() - timedelta(days=1)) == 2
    for i in range(3, 12):   # passa de 10: a aula dá o número como meta de disciplina, não como trava
        svc.mark_sent(root, svc.create_lead(root, f"Hoje {i}", f"@hoje{i}", "o post de hoje")["id"])
    assert svc.today_sent(svc.load_leads(root)) == 12 > svc.DAILY_LIMIT


def test_mark_sent_grava_status_e_data_invalida_e_422(svc, root):
    open_gate(root)
    lead = svc.mark_sent(root, a_lead(svc, root)["id"], "2026-08-25T10:20:00")
    assert lead["status"] == "dm_sent" and lead["sent_at"] == "2026-08-25T10:20:00"
    with pytest.raises(ValueError, match="ISO"):
        svc.mark_sent(root, lead["id"], "25/08/2026")


def test_dm_enviada_nunca_muda_mas_lead_novo_regenera(svc, root):
    open_gate(root)
    lid = a_lead(svc, root)["id"]
    novo = svc.update_lead(root, lid, post_ref="a vitrine de Natal")
    assert "a vitrine de Natal" in novo["dm_text"], "enquanto não foi enviada, a DM acompanha o lead"
    svc.mark_sent(root, lid)
    congelado = svc.update_lead(root, lid, business="Padaria Nova", role="fã")
    assert congelado["dm_text"] == novo["dm_text"], "DM já enviada não muda"


def test_replied_exige_dm_enviada_e_pode_ser_desfeito(svc, root):
    open_gate(root)
    lid = a_lead(svc, root)["id"]
    with pytest.raises(ValueError):
        svc.mark_replied(root, lid)
    svc.mark_sent(root, lid)
    respondeu = svc.mark_replied(root, lid)
    assert respondeu["status"] == "replied" and respondeu["replied_at"], "data da resposta gravada"
    desfeito = svc.mark_replied(root, lid, False)
    assert desfeito["replied"] is False and desfeito["status"] == "dm_sent"
    assert desfeito["replied_at"] is None, "desfazer a resposta limpa a data do follow-up"


def test_gate_sobrevive_a_log_de_outro_projeto_estragado(svc, root):
    """O gate varre todos os projetos: um log estragado em qualquer um não pode levantar."""
    open_gate(root)
    ruim = root.parent / "2026-08-ruim"
    (ruim / "publish").mkdir(parents=True, exist_ok=True)
    (ruim / "project.json").write_text(json.dumps({"id": "2026-08-ruim", "name": "Ruim"}), encoding="utf-8")
    (ruim / "publish" / "log.json").write_text('["nao sou um post"]', encoding="utf-8")
    g = svc.gate(root)
    assert g["ok"] is True and g["published"] == 4, "o projeto estragado é ignorado, não conta nem explode"


def test_call_registra_data_nota_e_status(svc, root):
    open_gate(root)
    lid = a_lead(svc, root)["id"]
    agendada = svc.register_call(root, lid, "2026-08-27T15:00:00", note="quer ver a vitrine de Natal")
    assert agendada["status"] == "call_scheduled" and agendada["call_note"] == "quer ver a vitrine de Natal"
    assert svc.register_call(root, lid, "2026-08-27T15:00:00", done=True)["status"] == "call_done"
    with pytest.raises(ValueError, match="ISO"):
        svc.register_call(root, lid, "amanhã")


def test_lead_inexistente_e_404(svc, root):
    open_gate(root)
    for fn in (svc.get_lead, svc.mark_sent, svc.delete_lead):
        with pytest.raises(FileNotFoundError):
            fn(root, "ninguem")


# ---------- teaser: um take da etapa 6 + a trilha da etapa 7 ----------
def takes_json(root, duration=6):
    (root / "animate").mkdir(parents=True, exist_ok=True)
    (root / "animate" / "takes.json").write_text(json.dumps({"shots": [{"scene": "cena01", "shot": "shot01", "takes": [
        {"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": False, "duration": duration},
        {"id": "take2", "file": "videos/cena01/shot01_take2.mp4", "liked": True, "duration": duration},
    ]}]}), encoding="utf-8")


def test_pick_take_prefere_o_liked_e_valida(svc, root):
    with pytest.raises(FileNotFoundError, match="Etapa 6"):
        svc.pick_take(root)
    takes_json(root)
    for name in ("shot01_take1.mp4", "shot01_take2.mp4"):
        (root / "videos" / "cena01" / name).parent.mkdir(parents=True, exist_ok=True)
        (root / "videos" / "cena01" / name).write_bytes(b"x")
    assert svc.pick_take(root)["take"] == "take2", "sem take informado, vale o que recebeu like (aula 012)"
    assert svc.pick_take(root, {"take": "take1"})["take"] == "take1"
    with pytest.raises(ValueError, match="não encontrado"):
        svc.pick_take(root, {"take": "take9"})


def test_find_music_aponta_a_etapa_7(svc, root):
    with pytest.raises(FileNotFoundError, match="Etapa 7"):
        svc.find_music(root)
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "audio" / "music.wav").write_bytes(b"x")
    assert svc.find_music(root).name == "music.wav"


def test_teaser_exige_que_a_empresa_tenha_respondido(svc, root):
    """11.1: 'você só cria de verdade se a empresa responder' — antes disso, 422."""
    open_gate(root)
    lid = a_lead(svc, root)["id"]
    with pytest.raises(ValueError, match="depois que a empresa responder"):
        svc.start_teaser(root, "p", lid)
    svc.mark_sent(root, lid)
    with pytest.raises(ValueError, match="depois que a empresa responder"):
        svc.start_teaser(root, "p", lid), "DM enviada ainda não é resposta"
    svc.mark_replied(root, lid)
    with pytest.raises(FileNotFoundError, match="Etapa 6"):
        svc.start_teaser(root, "p", lid)   # passou do gate da resposta e chegou nos artefatos


def test_teaser_valida_antes_de_iniciar_o_job(svc, root, monkeypatch):
    open_gate(root)
    lid = lead_respondido(svc, root)
    monkeypatch.setattr(svc.ff, "available", lambda: False)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        svc.start_teaser(root, "p", lid)
    monkeypatch.setattr(svc.ff, "available", lambda: True)
    with pytest.raises(ValueError, match="entre 5 e 10"):
        svc.start_teaser(root, "p", lid, duration=12)
    with pytest.raises(FileNotFoundError, match="Etapa 6"):
        svc.start_teaser(root, "p", lid)
    takes_json(root, duration=3)
    for name in ("shot01_take1.mp4", "shot01_take2.mp4"):
        (root / "videos" / "cena01" / name).parent.mkdir(parents=True, exist_ok=True)
        (root / "videos" / "cena01" / name).write_bytes(b"x")
    with pytest.raises(FileNotFoundError, match="Etapa 7"):
        svc.start_teaser(root, "p", lid)
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "audio" / "music.wav").write_bytes(b"x")
    with pytest.raises(ValueError, match="menos de 5"):
        svc.start_teaser(root, "p", lid)


def test_teaser_recusa_segundo_job_no_mesmo_projeto(svc, root):
    open_gate(root)
    lid = lead_respondido(svc, root)
    svc._registry._jobs["pid-x"] = {"state": "running", "done": 0, "total": 3}
    with pytest.raises(RuntimeError, match="andamento"):
        svc.start_teaser(root, "pid-x", lid)


def wait_job(svc, pid, timeout=90):
    limite = time.time() + timeout
    while time.time() < limite:
        job = svc.job_status(pid)
        if job.get("state") not in ("running",):
            return job
        time.sleep(0.2)
    raise AssertionError("job de teaser não terminou a tempo")


@pytest.mark.skipif(not ff.available(), reason="ffmpeg não disponível")
def test_teaser_sai_com_musica_entre_5_e_10s(svc, root):
    open_gate(root)
    lid = lead_respondido(svc, root)
    takes_json(root, duration=6)
    make_video(root / "videos" / "cena01" / "shot01_take1.mp4", seconds=6, size="320x240")
    make_video(root / "videos" / "cena01" / "shot01_take2.mp4", seconds=6, size="320x240")
    make_audio(root / "audio" / "music.wav", seconds=4)
    job = svc.start_teaser(root, "pid-t", lid)
    assert job["state"] == "running" and job["total"] == 3 and job["lead"] == lid
    job = wait_job(svc, "pid-t")
    assert job["state"] == "done", job.get("error")
    teaser = root / "prospect" / "teasers" / f"{lid}.mp4"
    info = svc.ff.probe(teaser)
    assert 5.0 <= info["duration"] <= 10.0, info
    assert info["has_audio"] is True, "aula 001: o teaser vai COM música"
    assert (info["width"], info["height"]) == (320, 240)
    lead = svc.get_lead(root, lid)
    assert lead["teaser"] == f"prospect/teasers/{lid}.mp4" and lead["status"] == "teaser_ready"
    svc.delete_lead(root, lid)
    assert not teaser.exists(), "apagar o lead apaga o teaser dele"


@pytest.mark.skipif(not ff.available(), reason="ffmpeg não disponível")
def test_teaser_com_ffmpeg_falhando_nao_toca_leads_json(svc, root):
    open_gate(root)
    lid = lead_respondido(svc, root)
    takes_json(root, duration=6)
    for name in ("shot01_take1.mp4", "shot01_take2.mp4"):
        (root / "videos" / "cena01" / name).parent.mkdir(parents=True, exist_ok=True)
        (root / "videos" / "cena01" / name).write_bytes(b"nao sou um mp4")
    make_audio(root / "audio" / "music.wav", seconds=4)
    svc.start_teaser(root, "pid-f", lid)
    job = wait_job(svc, "pid-f")
    assert job["state"] == "error" and job["error"]
    assert len(job["error"]) <= 480, "stderr truncado"
    lead = svc.get_lead(root, lid)
    assert lead["teaser"] is None and lead["status"] == "replied", "a falha não desfaz a resposta"
    assert not (root / "prospect" / "teasers" / f"{lid}.mp4").exists(), "arquivo parcial removido"


# ---------- pitch da call ----------
def test_pitch_tem_a_tabela_de_etapas_com_valores_e_os_lembretes_literais(svc, root):
    md = svc.pitch_markdown({"name": "Gelo Zero"})
    assert md.startswith("# Pitch: Gelo Zero")
    for etapa in ("Conceito", "Mood board", "Roteirização", "Direção criativa", "Produção", "Montagem", "Entrega"):
        assert f"| {etapa} |" in md
    assert "| Etapa | O que envolve | Entrega | Valor (R$) |" in md, "11.4: coluna de valor por etapa"
    assert "**Total**" in md and "Total com 50 % off no 1º trabalho" in md
    for lembrete in ("Condição especial na hora, ou válida por 24h",
                     "50 % off no primeiro trabalho, deixando claro o valor cheio para os próximos",
                     "50 % na entrada e 50 % na entrega", "R$ 100 a R$ 500", "não a IA", "15 minutos"):
        assert lembrete in md, lembrete


def test_pitch_values_soma_etapas_e_calcula_o_desconto(svc, root):
    open_gate(root)
    pitch = svc.save_pitch_values(root, {"Conceito": 50, "Produção": 150, "Montagem": 100})
    assert pitch["sum"] == 300.0 and pitch["total"] == 300.0 and pitch["matches"] is True
    assert pitch["discount"] == 150.0 and pitch["in_range"] is True and pitch["priced"] is True
    md = svc.pitch_markdown({"name": "Gelo Zero"}, pitch)
    assert "| Conceito | ideia central e mensagem | uma frase de conceito | R$ 50,00 |" in md
    assert "R$ 300,00" in md and "R$ 150,00" in md
    assert "| Mood board | referências de estilo, cor e clima | painel de referências | — |" in md


def test_pitch_avisa_quando_o_total_nao_bate_com_a_soma(svc, root):
    open_gate(root)
    pitch = svc.save_pitch_values(root, {"Conceito": 100}, total=400)
    assert pitch["sum"] == 100.0 and pitch["total"] == 400.0 and pitch["matches"] is False
    assert "diferente do total" in svc.pitch_markdown({"name": "X"}, pitch)


def test_pitch_values_rejeita_etapa_desconhecida_e_valor_negativo(svc, root):
    open_gate(root)
    with pytest.raises(ValueError, match="etapa desconhecida"):
        svc.save_pitch_values(root, {"Cafezinho": 10})
    with pytest.raises(ValueError, match="negativo"):
        svc.save_pitch_values(root, {"Conceito": -1})


def test_pitch_fora_da_faixa_da_aula_e_apenas_aviso(svc, root):
    open_gate(root)
    assert svc.save_pitch_values(root, {"Conceito": 5000})["in_range"] is False, "aviso, não trava"
    assert svc.load_pitch_values(root)["total"] == 5000.0


def test_pitch_gerado_na_primeira_leitura_e_edicao_preservada(svc, root):
    project = {"name": "Gelo Zero"}
    assert "Pitch: Gelo Zero" in svc.read_pitch(root, project), "com o gate fechado o texto é só leitura"
    assert not svc.pitch_file(root).exists(), "nada é escrito em prospect/ com o gate fechado"
    open_gate(root)
    assert "Pitch: Gelo Zero" in svc.read_pitch(root, project)
    assert svc.pitch_file(root).exists()
    f = svc.pitch_file(root)
    f.write_text("# meu pitch à mão", encoding="utf-8")
    assert svc.read_pitch(root, project) == "# meu pitch à mão", "GET não sobrescreve edição manual"
    svc.write_pitch(root, project)
    assert "Pitch: Gelo Zero" in f.read_text(encoding="utf-8"), "só a regeneração explícita sobrescreve"


# ---------- 11.8: sugestão de offset da trilha ----------
def test_sugestao_de_music_offset_e_meio_segundo_antes_do_primeiro_impacto(svc, root):
    assert svc.suggest_music_offset(root)["music_offset"] is None, "sem beats.json não há sugestão"
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "audio" / "beats.json").write_text(json.dumps({"bpm": 120, "beats": [0.5, 1.0],
                                                           "impacts": [2.4, 5.1]}), encoding="utf-8")
    s = svc.suggest_music_offset(root)
    assert s["music_offset"] == 1.9 and s["impact"] == 2.4


def test_sugestao_nunca_fica_negativa_nem_explode_com_json_ruim(svc, root):
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "audio" / "beats.json").write_text(json.dumps({"impacts": [0.2]}), encoding="utf-8")
    assert svc.suggest_music_offset(root)["music_offset"] == 0.0
    (root / "audio" / "beats.json").write_text("{quebrado", encoding="utf-8")
    assert svc.suggest_music_offset(root)["music_offset"] is None
