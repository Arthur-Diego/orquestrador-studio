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
          "posted_at": "2026-08-20T10:00:00", "note": ""} for i, v in enumerate(videos)]), encoding="utf-8")


def open_gate(root):
    publish_log(root, [f"export/v{i}.mp4" for i in range(4)])


def a_lead(svc, root, handle="@padariadoze"):
    return svc.create_lead(root, "Padaria do Zé", handle, "o pão de fermentação natural das 6h",
                           "fotos com luz de manhã", "consumidor")


# ---------- gate: 4 vídeos publicados (aula 015 → 001) ----------
def test_gate_conta_videos_distintos_nao_posts(svc, root):
    """Decisão 1 da wave: '4 vídeos', não '4 posts' — o mesmo vídeo em 4 redes não abre o gate."""
    publish_log(root, ["export/a.mp4"] * 4 + ["export/b.mp4"])
    g = svc.gate(root)
    assert g["published"] == 2 and g["posts"] == 5 and g["ok"] is False
    assert g["message"] == "A aula manda publicar 4 vídeos criativos antes de prospectar. Você tem 2/4."


def test_gate_abre_com_quatro_videos_distintos(svc, root):
    open_gate(root)
    assert svc.gate(root)["ok"] is True and svc.gate(root)["published"] == 4


def test_gate_sem_log_ou_com_json_invalido_conta_zero(svc, root):
    assert svc.gate(root) == {"published": 0, "posts": 0, "required": 4, "ok": False,
                              "message": "A aula manda publicar 4 vídeos criativos antes de prospectar. Você tem 0/4."}
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text("{isso não é json", encoding="utf-8")
    assert svc.gate(root)["published"] == 0, "log inválido conta como zero e nunca levanta"


def test_gate_fechado_bloqueia_qualquer_escrita(svc, root):
    with pytest.raises(svc.GateClosed) as e:
        a_lead(svc, root)
    assert "4 vídeos criativos" in str(e.value)
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
        svc.create_lead(root, "", "@outro")
    with pytest.raises(ValueError):
        svc.create_lead(root, "Outro", "  ")
    with pytest.raises(ValueError, match="role"):
        svc.create_lead(root, "Outro", "@outro", role="parceiro")
    with pytest.raises(ValueError, match="já cadastrado"):
        svc.create_lead(root, "Padaria de novo", "@PadariaDoZé")
    with pytest.raises(ValueError, match="2000"):
        svc.create_lead(root, "Outro", "@outro2", post_ref="x" * 2001)


# ---------- contador N/10 hoje (meta, nunca trava) ----------
def test_today_sent_conta_so_hoje_e_nao_bloqueia(svc, root):
    open_gate(root)
    ontem = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    for i in range(3):
        svc.mark_sent(root, svc.create_lead(root, f"Hoje {i}", f"@hoje{i}")["id"])
    for i in range(2):
        svc.mark_sent(root, svc.create_lead(root, f"Ontem {i}", f"@ontem{i}")["id"], ontem)
    leads = svc.load_leads(root)
    assert svc.today_sent(leads) == 3
    assert svc.today_sent(leads, date.today() - timedelta(days=1)) == 2
    for i in range(3, 12):   # passa de 10: a aula dá o número como meta de disciplina, não como trava
        svc.mark_sent(root, svc.create_lead(root, f"Hoje {i}", f"@hoje{i}")["id"])
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
    assert svc.mark_replied(root, lid)["status"] == "replied"
    desfeito = svc.mark_replied(root, lid, False)
    assert desfeito["replied"] is False and desfeito["status"] == "dm_sent"


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


def test_teaser_valida_antes_de_iniciar_o_job(svc, root, monkeypatch):
    open_gate(root)
    lid = a_lead(svc, root)["id"]
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
    lid = a_lead(svc, root)["id"]
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
    lid = a_lead(svc, root)["id"]
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
    lid = a_lead(svc, root)["id"]
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
    assert lead["teaser"] is None and lead["status"] == "new"
    assert not (root / "prospect" / "teasers" / f"{lid}.mp4").exists(), "arquivo parcial removido"


# ---------- pitch da call ----------
def test_pitch_tem_a_tabela_de_etapas_sem_preco_e_os_lembretes(svc, root):
    md = svc.pitch_markdown({"name": "Gelo Zero"})
    assert md.startswith("# Pitch: Gelo Zero")
    for etapa in ("Conceito", "Mood board", "Roteirização", "Direção criativa", "Produção", "Montagem", "Entrega"):
        assert f"| {etapa} |" in md
    tabela = md.split("## Lembretes")[0]
    assert "R$" not in tabela, "a aula manda a tabela para ancorar; os valores ficam nos lembretes"
    for lembrete in ("50% de desconto no primeiro", "50% na entrada e 50% na entrega",
                     "R$ 100 a R$ 500", "não a IA", "15 minutos"):
        assert lembrete in md


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
