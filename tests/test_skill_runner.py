"""Runner de skill do Claude CLI: comando montado, `cwd`, contrato do `_run.json` e matriz de erros.

Sem rede e sem `claude` real (ADR-008): o CLI é trocado por um fake via duplo monkeypatch de
`skill_runner.BIN` e `skill_runner.subprocess.run`, como em `tests/test_prompter.py`.
"""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from studio.common import skill_runner
from studio.config import ROOT


def _fake_claude(chamadas: list, *, manifesto=..., returncode: int = 0, stdout: str = "ok\n", stderr: str = "",
                 prancha: bool = False, saida: Path | None = None):
    """Fake do CLI: registra a chamada, escreve o `_run.json` em `saida` e devolve o processo."""
    def run(args, **kwargs):
        chamadas.append({"args": args, "kwargs": kwargs})
        if saida is not None and manifesto is not ...:
            saida.mkdir(parents=True, exist_ok=True)
            texto = manifesto if isinstance(manifesto, str) else json.dumps(manifesto)
            (saida / skill_runner.RUN_MANIFEST).write_text(texto, encoding="utf-8")
            if prancha:
                (saida / "_moodboard.jpg").write_bytes(b"jpg")
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)
    return run


def _com_cli(monkeypatch):
    monkeypatch.setattr(skill_runner, "BIN", "/usr/bin/claude")


def _recarrega():
    """Recarrega o módulo **no lugar**, para que a env nova seja relida.

    A fixture `studio_env` do `conftest` apaga todo `studio.*` de `sys.modules`; sem repor o
    objeto antes, o `reload` estoura e as demais funções deste arquivo ficariam com uma
    referência morta. Repor mantém a identidade do módulo que o `monkeypatch` usa.
    """
    sys.modules.setdefault(skill_runner.__name__, skill_runner)
    return importlib.reload(skill_runner)


# ---------- UT-01 / UT-02 / UT-03: disponibilidade e comando ----------
def test_available_falso_sem_cli(monkeypatch):
    """UT-01."""
    monkeypatch.setattr(skill_runner, "BIN", None)
    assert skill_runner.available() is False
    monkeypatch.setattr(skill_runner, "BIN", "/usr/bin/claude")
    assert skill_runner.available() is True


def test_build_command_libera_as_tools_e_nao_limita_turnos(monkeypatch):
    """UT-02: 7 tools num único argumento, sem `--max-turns` (4 skills não cabem em 6 turnos)."""
    _com_cli(monkeypatch)
    args = skill_runner.build_command("/x")
    assert args[0] == "/usr/bin/claude" and args[1] == "-p" and args[2] == "/x"
    assert args[args.index("--output-format") + 1] == "text"
    assert args[args.index("--allowedTools") + 1] == "Read,Bash,Write,WebSearch,WebFetch,Skill,Agent"
    assert "--max-turns" not in args


def test_build_command_respeita_o_modelo_do_modulo(monkeypatch):
    """UT-03: `MODEL` vazio omite `--model`; `MODEL` preenchido entra como par."""
    _com_cli(monkeypatch)
    monkeypatch.setattr(skill_runner, "MODEL", "")
    assert "--model" not in skill_runner.build_command("/x")
    monkeypatch.setattr(skill_runner, "MODEL", "m")
    args = skill_runner.build_command("/x")
    assert args[args.index("--model") + 1] == "m"


# ---------- UT-04 / UT-05: prompt ----------
def test_build_prompt_cita_caminho_e_omite_none():
    """UT-04."""
    p = skill_runner.build_prompt("mood_orquestrador", {
        "foto": "/a/b.jpg", "objetivo": "ambiente", "gate": "auto", "board": 8, "n": 3, "fundo": None})
    assert p == '/mood_orquestrador --foto "/a/b.jpg" --objetivo ambiente --gate auto --board 8 --n 3'


def test_build_prompt_recusa_aspas_duplas():
    """UT-05 (E12): o prompt é uma string única; a aspa quebraria a citação."""
    with pytest.raises(ValueError, match="aspas duplas"):
        skill_runner.build_prompt("mood_orquestrador", {"foto": '/a/b".jpg'})


# ---------- UT-06 / UT-07: execução ----------
def test_run_skill_roda_na_raiz_do_repo_com_o_teto_pedido(monkeypatch, tmp_path):
    """UT-06: sem `cwd=ROOT` o `.claude/skills` não resolve e a skill não é encontrada."""
    _com_cli(monkeypatch)
    chamadas = []
    monkeypatch.setattr(skill_runner.subprocess, "run",
                        _fake_claude(chamadas, manifesto={"boards": []}, saida=tmp_path))
    skill_runner.run_skill("/mood_orquestrador", saida=tmp_path, timeout_s=42)
    assert chamadas[0]["kwargs"]["cwd"] == ROOT
    assert chamadas[0]["kwargs"]["timeout"] == 42


def test_run_skill_sem_cli(monkeypatch, tmp_path):
    """UT-07 (E1)."""
    monkeypatch.setattr(skill_runner, "BIN", None)
    with pytest.raises(skill_runner.SkillUnavailable, match="não encontrado"):
        skill_runner.run_skill("/x", saida=tmp_path)


# ---------- UT-08 … UT-13: matriz de erros ----------
def test_run_skill_timeout(monkeypatch, tmp_path):
    """UT-08 (E2): a mensagem cita o limite, para o job dizer de quanto foi o teto."""
    _com_cli(monkeypatch)

    def estoura(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=7)
    monkeypatch.setattr(skill_runner.subprocess, "run", estoura)
    with pytest.raises(skill_runner.SkillTimeout, match="passou de 7s"):
        skill_runner.run_skill("/x", saida=tmp_path, timeout_s=7)


def test_run_skill_returncode_diferente_de_zero(monkeypatch, tmp_path):
    """UT-09 (E3)."""
    _com_cli(monkeypatch)
    monkeypatch.setattr(skill_runner.subprocess, "run",
                        _fake_claude([], returncode=1, stdout="", stderr="boom"))
    with pytest.raises(skill_runner.SkillFailed, match="boom"):
        skill_runner.run_skill("/x", saida=tmp_path)


def test_run_skill_sem_manifesto(monkeypatch, tmp_path):
    """UT-10 (E4): `returncode` 0 e nada gravado é contrato quebrado, não processo quebrado."""
    _com_cli(monkeypatch)
    monkeypatch.setattr(skill_runner.subprocess, "run", _fake_claude([]))
    with pytest.raises(skill_runner.SkillManifestMissing) as e:
        skill_runner.run_skill("/x", saida=tmp_path)
    assert str(tmp_path) in str(e.value) and "_run.json" in str(e.value)


@pytest.mark.parametrize("conteudo, caso", [
    ("nao sou json {", "UT-11"),
    ('["um", "array"]', "UT-12"),
    ('{"boards": "x"}', "UT-13"),
])
def test_run_skill_manifesto_invalido(monkeypatch, tmp_path, conteudo, caso):
    """UT-11/UT-12/UT-13 (E5): nunca `except: return {}` — falha explícita com o motivo."""
    _com_cli(monkeypatch)
    monkeypatch.setattr(skill_runner.subprocess, "run",
                        _fake_claude([], manifesto=conteudo, saida=tmp_path))
    with pytest.raises(skill_runner.SkillManifestInvalid, match="_run.json inválido"):
        skill_runner.run_skill("/x", saida=tmp_path)


# ---------- UT-14: caminho feliz ----------
def test_run_skill_devolve_o_manifesto_a_duracao_e_a_cauda(monkeypatch, tmp_path):
    """UT-14."""
    _com_cli(monkeypatch)
    manifesto = {"boards": [{"objetivo": "ambiente", "pasta": "board-neon-ambiente"}], "vibe": "neon"}
    monkeypatch.setattr(skill_runner.subprocess, "run", _fake_claude(
        [], manifesto=manifesto, saida=tmp_path, prancha=True, stdout="montando\nprancha pronta\n"))
    r = skill_runner.run_skill("/x", saida=tmp_path)
    assert r.manifesto == manifesto
    assert isinstance(r.seconds, float) and r.seconds >= 0
    assert r.log == ["montando", "prancha pronta"]
    assert (tmp_path / "_moodboard.jpg").is_file()


def test_cauda_do_log_e_limitada(monkeypatch, tmp_path):
    """A saída inteira de uma corrida de 15 min não cabe num job dict."""
    _com_cli(monkeypatch)
    monkeypatch.setattr(skill_runner.subprocess, "run", _fake_claude(
        [], manifesto={}, saida=tmp_path, stdout="\n".join(f"linha {i}" for i in range(200))))
    r = skill_runner.run_skill("/x", saida=tmp_path)
    assert len(r.log) == skill_runner.MAX_LOG_LINES
    assert r.log[-1] == "linha 199"
    assert sum(len(linha) + 1 for linha in r.log) <= skill_runner.MAX_LOG_CHARS


# ---------- UT-15 / UT-16: envs próprias ----------
def test_env_do_modelo_e_propria(monkeypatch):
    """UT-15 (A9): trocar o modelo do bot de prompts não pode trocar o da corrida."""
    monkeypatch.setenv("STUDIO_SKILL_MODEL", "skill-m")
    monkeypatch.setenv("STUDIO_PROMPTER_MODEL", "prompt-m")
    try:
        recarregado = _recarrega()
        assert recarregado.MODEL == "skill-m"
    finally:
        monkeypatch.undo()
        _recarrega()


@pytest.mark.parametrize("env, esperado", [(None, 1800), ("60", 60)])
def test_env_do_timeout(monkeypatch, env, esperado):
    """UT-16."""
    monkeypatch.delenv("STUDIO_SKILL_TIMEOUT_S", raising=False)
    if env is not None:
        monkeypatch.setenv("STUDIO_SKILL_TIMEOUT_S", env)
    try:
        assert _recarrega().TIMEOUT_S == esperado
    finally:
        monkeypatch.undo()
        _recarrega()


# ---------- guardas da feature ----------
def test_o_runner_nao_toca_higgsfield_nem_credito():
    """A cadeia `mood_` é gratuita (ADR-016) e não passa pela Higgsfield (ADR-002)."""
    fonte = (ROOT / "studio" / "common" / "skill_runner.py").read_text(encoding="utf-8")
    for proibido in ("import studio.higgsfield", "from studio import higgsfield", "require_cli",
                     "spend_action", "record_generation", "except Exception"):
        assert proibido not in fonte, f"o runner não pode usar {proibido!r}"
