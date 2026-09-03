"""Corrida das skills `mood_` pela tela `[extensão]` (ADH-OS-20260902-01) — IT-01…IT-26.

Sem rede e sem `claude` real (ADR-008): o CLI é trocado por um fake que lê o `--saida` do próprio
prompt e escreve ali o que a skill escreveria (`_run.json`, pranchas, `leitura.md`, `curadoria.md`).
Contrato e matriz de erros: `docs/domains/mood/features/mood-run-fdd.md` (seções 5 e 6).

A fixture `studio_env` do `conftest` apaga todos os módulos `studio.*` por teste, então o
`JobRegistry` de módulo do `mood_run` nasce limpo a cada caso — não é preciso resetá-lo à mão.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from tests.conftest import make_image

#: `board-<slug-da-vibe>-<objetivo>` — o nome da pasta é escolhido pela SKILL, não por nós.
SLUG = "anime-city-night"


# ---------- fake do CLI ----------
def _prompt_de(args: list[str]) -> str:
    return args[args.index("-p") + 1]


def _flag_do_prompt(prompt: str, flag: str) -> str:
    """Valor de `--<flag>` no prompt montado, com ou sem aspas."""
    achado = re.search(rf'--{flag} (?:"([^"]*)"|(\S+))', prompt)
    assert achado, f"--{flag} ausente em {prompt!r}"
    return achado.group(1) if achado.group(1) is not None else achado.group(2)


def _instalar_cli(monkeypatch, *, returncode: int = 0, stderr: str = "", delay: float = 0.0,
                  manifesto=..., prancha: bool = True, docs: bool = True) -> list[dict]:
    """Instala o fake do `claude` e devolve a lista onde cada chamada é registrada.

    Por padrão o fake escreve uma pasta por objetivo pedido, com `dna.json`, `leitura.md`,
    `curadoria.md` e `_moodboard.jpg`, mais o `_run.json` na raiz do `--saida`.
    """
    from studio.common import skill_runner

    monkeypatch.setattr(skill_runner, "BIN", "/usr/bin/claude")
    chamadas: list[dict] = []

    def run(args, **kwargs):
        chamadas.append({"args": args, "kwargs": kwargs})
        if delay:
            time.sleep(delay)
        if returncode == 0:
            prompt = _prompt_de(args)
            saida = Path(_flag_do_prompt(prompt, "saida"))
            objetivos = [o for o in _flag_do_prompt(prompt, "objetivo").split(",") if o]
            saida.mkdir(parents=True, exist_ok=True)
            boards = []
            for objetivo in objetivos:
                pasta = saida / f"board-{SLUG}-{objetivo}"
                pasta.mkdir(parents=True, exist_ok=True)
                (pasta / "dna.json").write_text(json.dumps({"vibe": SLUG}), encoding="utf-8")
                if docs:
                    (pasta / "leitura.md").write_text("# leitura", encoding="utf-8")
                    (pasta / "curadoria.md").write_text("# curadoria", encoding="utf-8")
                if prancha:
                    make_image(pasta / "_moodboard.jpg")
                boards.append({"objetivo": objetivo, "pasta": str(pasta), "imagens": 8,
                               "refeitas": [], "trocas": []})
            texto = (json.dumps({"semente": _flag_do_prompt(prompt, "foto"), "gate": "auto",
                                 "downloads": 21, "boards": boards})
                     if manifesto is ... else manifesto)
            (saida / skill_runner.RUN_MANIFEST).write_text(texto, encoding="utf-8")
        return subprocess.CompletedProcess(args, returncode, "ok\n", stderr)

    monkeypatch.setattr(skill_runner.subprocess, "run", run)
    return chamadas


def _sem_cli(monkeypatch) -> None:
    from studio.common import skill_runner
    monkeypatch.setattr(skill_runner, "BIN", None)


# ---------- fixtures de cenário ----------
def _board(client) -> str:
    return client.post("/api/moodboards", json={"name": "Neon Snow"}).json()["id"]


def _escolher(client, studio_env, quantas: int = 1) -> list[str]:
    """Popula `_vibes/`, escolhe `quantas` fotos pela rota real e devolve os caminhos absolutos."""
    from studio.moodboards import vibes

    ids = []
    for i in range(quantas):
        nome = f"custom-0{i + 1}-{SLUG}-1.jpg"
        make_image(vibes.vibes_dir() / nome, color=(10 * (i + 1), 20, 30))
        ids.append(nome)
    assert client.post("/api/vibes/select", json={"ids": ids}).status_code == 200
    return [i["caminho"] for i in client.get("/api/escolhidas").json()["items"]]


def _esperar_job(client, mbid: str, *, tentativas: int = 60) -> dict:
    for _ in range(tentativas):
        job = client.get(f"/api/moodboards/{mbid}/mood-run/job").json()
        if job.get("state") in ("done", "error"):
            return job
        time.sleep(0.1)
    return job


def _corrida_completa(client, studio_env, monkeypatch, **kw) -> tuple[str, dict]:
    """Board + peneira + corrida feliz até `done`. Devolve `(mbid, job final)`."""
    chamadas = _instalar_cli(monkeypatch, **kw)
    mbid = _board(client)
    foto = _escolher(client, studio_env)[0]
    r = client.post(f"/api/moodboards/{mbid}/mood-run",
                    json={"foto": foto, "objetivos": ["ambiente"], "board": 8, "n": 3})
    assert r.status_code == 200, r.text
    job = _esperar_job(client, mbid)
    return mbid, {"job": job, "chamadas": chamadas, "foto": foto}


# ---------- IT-01 … IT-04: /options ----------
def test_options_espelha_o_manifesto(client, studio_env, monkeypatch):
    """IT-01: nenhum literal — objetivos, agregador, fundos e defaults saem do manifesto."""
    _instalar_cli(monkeypatch)
    from studio.moodboards import skills_params

    mbid = _board(client)
    body = client.get(f"/api/moodboards/{mbid}/mood-run/options").json()
    por_nome = {p.nome: p for p in skills_params.skill("mood_orquestrador").params}

    assert body["objetivos"] == list(por_nome["objetivo"].opcoes)
    assert body["agregador"] == por_nome["objetivo"].agregador
    assert body["fundos"] == list(por_nome["fundo"].opcoes)
    assert body["defaults"] == {"board": por_nome["board"].default, "n": por_nome["n"].default,
                                "fundo": por_nome["fundo"].default}
    assert body["limites"] == {"board_min": por_nome["board"].apresentacao.minimo,
                               "n_min": por_nome["n"].apresentacao.minimo}
    # o que o servidor impõe e a tela nunca decide
    assert body["gate"] == "auto"
    assert body["saida"].endswith(f"/{mbid}/mood_run")
    assert body["job"] == {"state": "idle", "done": 0, "total": 0, "added": 0, "error": None, "log": []}


def test_options_404_para_mbid_invalido(client, studio_env):
    """IT-02 (E7)."""
    assert client.get("/api/moodboards/nope/mood-run/options").status_code == 404
    assert client.get("/api/moodboards/../x/mood-run/options").status_code == 404


def test_options_sem_claude(client, studio_env, monkeypatch):
    """IT-03 (A1/E1): sem CLI a tela desabilita o botão; nada quebra."""
    _sem_cli(monkeypatch)
    mbid = _board(client)
    body = client.get(f"/api/moodboards/{mbid}/mood-run/options").json()
    assert body["available_claude"] is False


def test_options_conta_a_peneira(client, studio_env, monkeypatch):
    """IT-04: o contador e a pasta vêm de `vibes`, não de um literal."""
    _instalar_cli(monkeypatch)
    from studio.moodboards import vibes

    mbid = _board(client)
    _escolher(client, studio_env, quantas=2)
    body = client.get(f"/api/moodboards/{mbid}/mood-run/options").json()
    assert body["escolhidas"] == {"total": 2, "pasta": str(vibes.chosen_dir())}


# ---------- IT-05 … IT-09: /estimate ----------
def test_estimate_todos_da_84(client, studio_env):
    """IT-05 (A2): `todos --board 8 --n 3` = 4 × 7 × 3 = 84, o número da corrida de referência."""
    mbid = _board(client)
    body = client.post(f"/api/moodboards/{mbid}/mood-run/estimate",
                       json={"objetivos": ["todos"], "board": 8, "n": 3}).json()
    assert body["downloads"] == 84
    assert body["consultas"] == 7 and body["objetivos"] == 4
    assert body["formula"] == "downloads = objetivos × (board − 1) × n"


def test_estimate_dois_objetivos(client, studio_env):
    """IT-06: 2 × 7 × 3 = 42."""
    mbid = _board(client)
    body = client.post(f"/api/moodboards/{mbid}/mood-run/estimate",
                       json={"objetivos": ["ambiente", "produto"], "board": 8, "n": 3}).json()
    assert body["downloads"] == 42


def test_estimate_objetivo_invalido_lista_os_aceitos(client, studio_env):
    """IT-07 (E9): a mensagem lista os aceitos — a regra do `SKILL.md` é listar, nunca adivinhar."""
    mbid = _board(client)
    r = client.post(f"/api/moodboards/{mbid}/mood-run/estimate",
                    json={"objetivos": ["paisagem"], "board": 8, "n": 3})
    assert r.status_code == 422
    detalhe = r.json()["detail"]
    for aceito in ("ambiente", "campanha", "produto", "personagem"):
        assert aceito in detalhe


def test_estimate_lista_vazia(client, studio_env):
    """IT-08 (E9)."""
    mbid = _board(client)
    r = client.post(f"/api/moodboards/{mbid}/mood-run/estimate", json={"objetivos": [], "board": 8, "n": 3})
    assert r.status_code == 422


def test_estimate_pisos_do_manifesto(client, studio_env):
    """IT-09 (E11): o piso citado na mensagem é o da camada de apresentação do manifesto."""
    mbid = _board(client)
    r = client.post(f"/api/moodboards/{mbid}/mood-run/estimate",
                    json={"objetivos": ["ambiente"], "board": 3, "n": 3})
    assert r.status_code == 422 and "4" in r.json()["detail"]
    r = client.post(f"/api/moodboards/{mbid}/mood-run/estimate",
                    json={"objetivos": ["ambiente"], "board": 8, "n": 0})
    assert r.status_code == 422 and "1" in r.json()["detail"]


def test_estimate_404_para_mbid_invalido(client, studio_env):
    """IT-02 (E7) na rota de estimativa: 404 precede qualquer 422 de parâmetro."""
    r = client.post("/api/moodboards/nope/mood-run/estimate", json={"objetivos": ["paisagem"]})
    assert r.status_code == 404


# ---------- IT-10 … IT-17: POST /mood-run ----------
def test_start_409_sem_claude(client, studio_env, monkeypatch):
    """IT-10 (A1/E1): o 409 é a rede de segurança, não o caminho normal."""
    _sem_cli(monkeypatch)
    mbid = _board(client)
    r = client.post(f"/api/moodboards/{mbid}/mood-run", json={"foto": "/x.jpg", "objetivos": ["ambiente"]})
    assert r.status_code == 409 and "Claude CLI" in r.json()["detail"]


def test_start_422_com_peneira_vazia(client, studio_env, monkeypatch):
    """IT-11 (E8): a mensagem ensina o caminho de saída."""
    _instalar_cli(monkeypatch)
    mbid = _board(client)
    r = client.post(f"/api/moodboards/{mbid}/mood-run", json={"foto": "/x.jpg", "objetivos": ["ambiente"]})
    assert r.status_code == 422 and "/mood_vibe_scout" in r.json()["detail"]


def test_start_422_com_foto_fora_da_peneira(client, studio_env, monkeypatch):
    """IT-12 (E10): contenção sobre o caminho RESOLVIDO, não prefixo textual."""
    _instalar_cli(monkeypatch)
    mbid = _board(client)
    _escolher(client, studio_env)
    r = client.post(f"/api/moodboards/{mbid}/mood-run",
                    json={"foto": "/etc/hosts", "objetivos": ["ambiente"]})
    assert r.status_code == 422 and "escolhidas" in r.json()["detail"]


def test_start_422_com_foto_inexistente_na_peneira(client, studio_env, monkeypatch):
    """IT-13 (E10): dentro de `_escolhidas/`, mas o arquivo não existe."""
    _instalar_cli(monkeypatch)
    from studio.moodboards import vibes

    mbid = _board(client)
    _escolher(client, studio_env)
    fantasma = str(vibes.chosen_dir() / "aaaaaaaaaaaa.jpg")
    r = client.post(f"/api/moodboards/{mbid}/mood-run",
                    json={"foto": fantasma, "objetivos": ["ambiente"]})
    assert r.status_code == 422


def test_start_404_precede_409(client, studio_env, monkeypatch):
    """IT-14 (E7): `mbid` inexistente com CLI ausente é 404, nunca 409."""
    _sem_cli(monkeypatch)
    r = client.post("/api/moodboards/nope/mood-run", json={"foto": "/x.jpg", "objetivos": ["ambiente"]})
    assert r.status_code == 404


def test_start_caminho_feliz_grava_params_e_conclui(client, studio_env, monkeypatch):
    """IT-15 (A3): 200 com job `running`, polling até `done`, e o `params.json` do pedido em disco."""
    _instalar_cli(monkeypatch)
    mbid = _board(client)
    foto = _escolher(client, studio_env)[0]
    r = client.post(f"/api/moodboards/{mbid}/mood-run",
                    json={"foto": foto, "objetivos": ["ambiente"], "board": 8, "n": 3, "fundo": "claro"})
    assert r.status_code == 200
    aberto = r.json()
    assert aberto["state"] == "running" and aberto["op"] == "mood_run"
    assert aberto["total"] == 1 and aberto["downloads_estimados"] == 21

    job = _esperar_job(client, mbid)
    assert job["state"] == "done", job
    assert job["done"] == 1
    assert job["log"][:2] == ["Validando parâmetros", f"Preparando {job['saida']}"]
    assert any(linha.startswith("Chamando claude -p /mood_orquestrador (limite ") for linha in job["log"])
    assert "Lendo _run.json" in job["log"]

    from studio.config import MOODBOARDS_DIR
    params = json.loads((MOODBOARDS_DIR / mbid / "mood_run" / "params.json").read_text(encoding="utf-8"))
    assert params == {"foto": foto, "objetivos": ["ambiente"], "gate": "auto", "board": 8, "n": 3,
                      "fundo": "claro", "saida": str(MOODBOARDS_DIR / mbid / "mood_run"),
                      "downloads_estimados": 21}


def test_start_409_com_corrida_em_andamento(client, studio_env, monkeypatch):
    """IT-16 (E6/A6): um job por board; a chave é `mood_run:<mbid>`."""
    _instalar_cli(monkeypatch, delay=1.0)
    mbid = _board(client)
    foto = _escolher(client, studio_env)[0]
    corpo = {"foto": foto, "objetivos": ["ambiente"], "board": 8, "n": 3}
    assert client.post(f"/api/moodboards/{mbid}/mood-run", json=corpo).status_code == 200
    segundo = client.post(f"/api/moodboards/{mbid}/mood-run", json=corpo)
    assert segundo.status_code == 409 and "andamento" in segundo.json()["detail"]
    _esperar_job(client, mbid)


def test_start_ignora_gate_e_saida_do_body(client, studio_env, monkeypatch):
    """IT-17 (D1/D3): `gate` e `saida` são do servidor; mandá-los no body não muda o comando."""
    chamadas = _instalar_cli(monkeypatch)
    mbid = _board(client)
    foto = _escolher(client, studio_env)[0]
    r = client.post(f"/api/moodboards/{mbid}/mood-run",
                    json={"foto": foto, "objetivos": ["ambiente"], "board": 8, "n": 3,
                          "gate": "interativo", "saida": "/tmp/roubado"})
    assert r.status_code == 200
    _esperar_job(client, mbid)

    from studio.config import MOODBOARDS_DIR
    prompt = _prompt_de(chamadas[0]["args"])
    assert _flag_do_prompt(prompt, "gate") == "auto"
    assert _flag_do_prompt(prompt, "saida") == str(MOODBOARDS_DIR / mbid / "mood_run")
    assert "/tmp/roubado" not in prompt


# ---------- IT-18 / IT-19: /job ----------
def test_job_idle_tem_as_chaves_base(client, studio_env):
    """IT-18: mesmo sem corrida, o shape é o que o `ui.progressJob` espera."""
    mbid = _board(client)
    body = client.get(f"/api/moodboards/{mbid}/mood-run/job").json()
    assert body == {"state": "idle", "done": 0, "total": 0, "added": 0, "error": None, "log": []}
    assert client.get("/api/moodboards/nope/mood-run/job").status_code == 404


def test_job_erro_carrega_a_cauda_do_stderr(client, studio_env, monkeypatch):
    """IT-19 (E3): falha do subprocess vira `state=error` com o diagnóstico junto."""
    _instalar_cli(monkeypatch, returncode=1, stderr="boom: a skill explodiu")
    mbid = _board(client)
    foto = _escolher(client, studio_env)[0]
    assert client.post(f"/api/moodboards/{mbid}/mood-run",
                       json={"foto": foto, "objetivos": ["ambiente"]}).status_code == 200
    job = _esperar_job(client, mbid)
    assert job["state"] == "error", job
    assert "boom: a skill explodiu" in job["error"]


# ---------- IT-20 … IT-24: /result ----------
def test_result_404_sem_corrida(client, studio_env):
    """IT-20 (E13)."""
    mbid = _board(client)
    r = client.get(f"/api/moodboards/{mbid}/mood-run/result")
    assert r.status_code == 404 and "corrida" in r.json()["detail"]


def test_result_expoe_as_urls_sob_mbfiles(client, studio_env, monkeypatch):
    """IT-21 (A3/A5): prancha, leitura e curadoria servidas pelo mount que já existe."""
    mbid, _ = _corrida_completa(client, studio_env, monkeypatch)
    body = client.get(f"/api/moodboards/{mbid}/mood-run/result").json()
    board = body["boards"][0]
    base = f"/mbfiles/{mbid}/mood_run/board-{SLUG}-ambiente"
    assert board["prancha_url"] == f"{base}/_moodboard.jpg"
    assert board["leitura_url"] == f"{base}/leitura.md"
    assert board["curadoria_url"] == f"{base}/curadoria.md"
    assert body["gate"] == "auto" and body["downloads"] == 21
    assert client.get(board["prancha_url"]).status_code == 200


def test_result_com_todos_lista_os_quatro_boards(client, studio_env, monkeypatch):
    """IT-22 (A4): `todos` produz 4 pastas, cada uma com seu `dna.json`."""
    _instalar_cli(monkeypatch)
    mbid = _board(client)
    foto = _escolher(client, studio_env)[0]
    assert client.post(f"/api/moodboards/{mbid}/mood-run",
                       json={"foto": foto, "objetivos": ["todos"], "board": 8, "n": 3}).status_code == 200
    job = _esperar_job(client, mbid)
    assert job["state"] == "done" and job["total"] == 4 and job["done"] == 4

    body = client.get(f"/api/moodboards/{mbid}/mood-run/result").json()
    assert len(body["boards"]) == 4
    for board in body["boards"]:
        assert (Path(board["pasta"]) / "dna.json").is_file()


def test_result_502_com_manifesto_corrompido(client, studio_env, monkeypatch):
    """IT-23 (E14): o `_run.json` é de produtor externo; falhar explícito bate mentir sobre o shape."""
    mbid, _ = _corrida_completa(client, studio_env, monkeypatch)
    from studio.config import MOODBOARDS_DIR
    (MOODBOARDS_DIR / mbid / "mood_run" / "_run.json").write_text("{isso não é json", encoding="utf-8")
    r = client.get(f"/api/moodboards/{mbid}/mood-run/result")
    assert r.status_code == 502


def test_result_degrada_prancha_ausente(client, studio_env, monkeypatch):
    """IT-24 (E15): board declarado sem prancha em disco aparece sem `prancha_url`, sem exceção."""
    mbid, _ = _corrida_completa(client, studio_env, monkeypatch, prancha=False)
    body = client.get(f"/api/moodboards/{mbid}/mood-run/result").json()
    board = body["boards"][0]
    assert "prancha_url" not in board
    assert board["leitura_url"].endswith("/leitura.md")


# ---------- IT-25 / IT-26: guardas ----------
def test_imagens_da_corrida_nao_entram_no_git():
    """IT-25 (A10): as dezenas de imagens de terceiros baixadas ficam fora do repositório."""
    if shutil.which("git") is None:
        pytest.skip("git indisponível no ambiente")
    raiz = Path(__file__).resolve().parent.parent
    alvo = "moodboards/qualquer-board/mood_run/board-x-ambiente/imagem.jpg"
    r = subprocess.run(["git", "check-ignore", "-q", alvo], cwd=raiz)
    assert r.returncode == 0, f"{alvo} NÃO está gitignored"


def _codigo_sem_prosa(path: Path) -> str:
    """O módulo sem comentários nem literais de string — só o que o interpretador executa.

    A prosa é retirada de propósito: os três módulos EXPLICAM, na docstring, que não tocam a
    Higgsfield e não registram gasto. Comparar o arquivo cru transformaria a guarda numa aposta na
    capitalização da palavra; comparar só o código torna o "não importa, não chama" verificável.
    """
    import io
    import tokenize

    fonte = path.read_text(encoding="utf-8")
    pedacos = [tok.string for tok in tokenize.generate_tokens(io.StringIO(fonte).readline)
               if tok.type not in (tokenize.COMMENT, tokenize.STRING)]
    return " ".join(pedacos).lower()


def test_nenhum_gasto_nem_higgsfield_nos_modulos_novos():
    """IT-26 (A11): a cadeia `mood_` é gratuita (ADR-002, ADR-016)."""
    raiz = Path(__file__).resolve().parent.parent
    proibidos = ("higgsfield", "require_cli", "spend_action", "record_generation")
    for rel in ("studio/moodboards/mood_run.py", "studio/moodboards/mood_run_router.py",
                "studio/common/skill_runner.py"):
        codigo = _codigo_sem_prosa(raiz / rel)
        for termo in proibidos:
            assert termo not in codigo, f"{rel} usa {termo}"
