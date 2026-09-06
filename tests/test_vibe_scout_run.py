"""Coleta do `mood_vibe_scout` pela tela `[extensão]` (ADH-OS-20260905-03).

Sem rede e sem `claude` real (ADR-008): o CLI é trocado por um fake que lê o `--saida` do próprio
prompt e escreve ali o que a skill escreveria — as imagens de vibe e o `_indice.json` (o scout NÃO
grava `_run.json`, ao contrário do orquestrador). Espelha `tests/test_mood_run_api.py`.

A fixture `studio_env` do `conftest` apaga os módulos `studio.*` por teste, então o `JobRegistry`
de módulo do `vibe_scout_run` nasce limpo a cada caso.
"""
from __future__ import annotations

import io
import re
import subprocess
import time
import tokenize
from pathlib import Path

from tests.conftest import make_image

SLUG = "anime-city-night"


# ---------- fake do CLI ----------
def _prompt_de(args: list[str]) -> str:
    return args[args.index("-p") + 1]


def _flag_do_prompt(prompt: str, flag: str) -> str:
    achado = re.search(rf'--{flag} (?:"([^"]*)"|(\S+))', prompt)
    assert achado, f"--{flag} ausente em {prompt!r}"
    return achado.group(1) if achado.group(1) is not None else achado.group(2)


def _instalar_cli(monkeypatch, *, returncode: int = 0, stderr: str = "", delay: float = 0.0,
                  imagens: int = 2) -> list[dict]:
    """Instala o fake do `claude` e devolve a lista onde cada chamada é registrada.

    Por padrão o fake escreve `imagens` `.jpg` de vibe + `_indice.json` no `--saida`.
    """
    from studio.common import skill_runner
    from studio.moodboards import vibe_scout_run

    monkeypatch.setattr(skill_runner, "BIN", "/usr/bin/claude")
    chamadas: list[dict] = []

    def run(args, **kwargs):
        chamadas.append({"args": args, "kwargs": kwargs})
        if delay:
            time.sleep(delay)
        if returncode == 0:
            saida = Path(_flag_do_prompt(_prompt_de(args), "saida"))
            saida.mkdir(parents=True, exist_ok=True)
            for i in range(imagens):
                make_image(saida / f"custom-0{i + 1}-{SLUG}-1.jpg", color=(10 * (i + 1), 20, 30))
            (saida / "_indice.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(args, returncode, "ok\n", stderr)

    monkeypatch.setattr(vibe_scout_run.subprocess, "run", run)
    return chamadas


def _sem_cli(monkeypatch) -> None:
    from studio.common import skill_runner
    monkeypatch.setattr(skill_runner, "BIN", None)


def _esperar_job(client, *, tentativas: int = 60) -> dict:
    for _ in range(tentativas):
        job = client.get("/api/vibes/scout-run/job").json()
        if job.get("state") in ("done", "error"):
            return job
        time.sleep(0.1)
    return job


# ---------- /options ----------
def test_options_espelha_o_manifesto(client, studio_env, monkeypatch):
    _instalar_cli(monkeypatch)
    from studio.moodboards import skills_params, vibes

    body = client.get("/api/vibes/scout-run/options").json()
    por_nome = {p.nome: p for p in skills_params.skill("mood_vibe_scout").params}
    assert body["defaults"] == {"n": por_nome["n"].default}
    assert body["limites"] == {"n_min": por_nome["n"].apresentacao.minimo}
    assert body["saida"] == str(vibes.vibes_dir())
    assert body["available_claude"] is True
    assert body["job"] == {"state": "idle", "done": 0, "total": 0, "added": 0, "error": None, "log": []}


def test_options_sem_claude(client, studio_env, monkeypatch):
    _sem_cli(monkeypatch)
    assert client.get("/api/vibes/scout-run/options").json()["available_claude"] is False


# ---------- POST /scout-run ----------
def test_start_409_sem_claude(client, studio_env, monkeypatch):
    _sem_cli(monkeypatch)
    r = client.post("/api/vibes/scout-run", json={"vibes": ["anime-city-night"]})
    assert r.status_code == 409 and "Claude CLI" in r.json()["detail"]


def test_start_422_sem_vibe(client, studio_env, monkeypatch):
    _instalar_cli(monkeypatch)
    r = client.post("/api/vibes/scout-run", json={"descricao": "algo", "vibes": []})
    assert r.status_code == 422 and "vibe" in r.json()["detail"]


def test_start_422_n_abaixo_do_piso(client, studio_env, monkeypatch):
    _instalar_cli(monkeypatch)
    r = client.post("/api/vibes/scout-run", json={"vibes": ["neon"], "n": 0})
    assert r.status_code == 422 and "1" in r.json()["detail"]


def test_start_caminho_feliz_coleta_e_conclui(client, studio_env, monkeypatch):
    chamadas = _instalar_cli(monkeypatch, imagens=3)
    from studio.moodboards import vibes

    r = client.post("/api/vibes/scout-run",
                    json={"descricao": "campanha neon", "vibes": ["neon-city", "neon-city"], "n": 4})
    assert r.status_code == 200, r.text
    aberto = r.json()
    assert aberto["state"] == "running" and aberto["op"] == "vibe_scout"
    assert aberto["vibes"] == ["neon-city"]        # dedup preservando ordem

    job = _esperar_job(client)
    assert job["state"] == "done", job
    assert job["done"] == 3 and job["added"] == 3

    # as imagens do fake caíram no `_vibes/` global e agora a grade de vibes as lista
    assert vibes.count_chosen() == 0
    listadas = client.get("/api/vibes").json()
    assert listadas["total"] == 3

    # o servidor impôs `--saida` e `--sem-entrevista`; a descrição foi posicional
    prompt = _prompt_de(chamadas[0]["args"])
    assert _flag_do_prompt(prompt, "saida") == str(vibes.vibes_dir())
    assert _flag_do_prompt(prompt, "n") == "4"
    assert _flag_do_prompt(prompt, "vibes") == "neon-city"
    assert prompt.endswith("--sem-entrevista")
    assert '"campanha neon"' in prompt


def test_start_409_com_coleta_em_andamento(client, studio_env, monkeypatch):
    _instalar_cli(monkeypatch, delay=1.0)
    corpo = {"vibes": ["neon"]}
    assert client.post("/api/vibes/scout-run", json=corpo).status_code == 200
    segundo = client.post("/api/vibes/scout-run", json=corpo)
    assert segundo.status_code == 409 and "andamento" in segundo.json()["detail"]
    _esperar_job(client)


# ---------- /job ----------
def test_job_idle_tem_as_chaves_base(client, studio_env):
    body = client.get("/api/vibes/scout-run/job").json()
    assert body == {"state": "idle", "done": 0, "total": 0, "added": 0, "error": None, "log": []}


def test_job_erro_carrega_a_cauda_do_stderr(client, studio_env, monkeypatch):
    _instalar_cli(monkeypatch, returncode=1, stderr="boom: o scout explodiu")
    assert client.post("/api/vibes/scout-run", json={"vibes": ["neon"]}).status_code == 200
    job = _esperar_job(client)
    assert job["state"] == "error", job
    assert "boom: o scout explodiu" in job["error"]


# ---------- guarda: a cadeia `mood_` é gratuita ----------
def _codigo_sem_prosa(path: Path) -> str:
    fonte = path.read_text(encoding="utf-8")
    pedacos = [tok.string for tok in tokenize.generate_tokens(io.StringIO(fonte).readline)
               if tok.type not in (tokenize.COMMENT, tokenize.STRING)]
    return " ".join(pedacos).lower()


def test_nenhum_gasto_nem_higgsfield_nos_modulos_novos():
    raiz = Path(__file__).resolve().parent.parent
    proibidos = ("higgsfield", "require_cli", "spend_action", "record_generation")
    for rel in ("studio/moodboards/vibe_scout_run.py", "studio/moodboards/vibe_scout_router.py"):
        codigo = _codigo_sem_prosa(raiz / rel)
        for termo in proibidos:
            assert termo not in codigo, f"{rel} usa {termo}"
