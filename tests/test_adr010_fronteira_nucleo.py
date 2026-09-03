"""Guarda única da fronteira do núcleo (ADR-010, item b) — invariante do REPOSITÓRIO.

## O que esta guarda afirma

*Frente de etapa não toca o núcleo.* Uma frente que só implementa uma etapa cria **só a pasta
dela** (`studio/etapas/<id>/` + `studio/<id>/service.py`) e nunca edita os arquivos únicos que
todas as etapas compartilham. Isso é o que torna possível rodar N worktrees em paralelo sem que
elas disputem o mesmo arquivo — a razão de existir da regra no ADR-010.

## Por que ela mora aqui e não dentro de um teste de feature

Até a Wave 10 este invariante era materializado por duas guardas escondidas em arquivos de teste
de feature específica:

- `tests/test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo`
- `tests/test_storyboard_view.py::test_t3_13_nucleo_do_shell_intocado[…]`

Ambas afirmavam um invariante do repositório inteiro a partir do arquivo de uma feature, e ambas
hardcodavam "ninguém toca o núcleo" — sem prever que uma frente pudesse ser **de núcleo**. A
Wave 10 (migração integral do frontend para React) é exatamente esse caso: E2 porta
`ui.js`/`style.css`, E3 reescreve `app.js`/`index.html`, E4 remove `etapas/mood/view.*`, E6 remove
`moodboards.js`/`creditos.js`/`multishot.js` e E10 remove o resíduo e edita `studio/app.py`. As
cinco reprovavam em `make verify` sem ter feito nada errado.

A correção **não** é desligar a proteção (um `skip` deixaria toda frente de etapa livre para
editar o núcleo). É tornar a **titularidade explícita**: quem é dono de um pedaço do núcleo
declara-se aqui, com motivo; todo o resto continua barrado exatamente como antes.

## Como uma frente de núcleo se declara

Acrescente uma entrada em `TITULARES_DO_NUCLEO` com o nome da sua branch, o motivo (card/ADR) e
**apenas** os prefixos que a frente realmente possui. Declarar titularidade é um ato de registro,
não uma isenção: uma frente que declara `studio/web/` e mexe em `studio/steps.py` continua
reprovando.

## Escopo desta guarda

Ela compara a branch com `merge-base develop HEAD` e inclui o *working tree*
(`git status --porcelain`), para pegar a violação antes do commit. Fora de um clone com `develop`
disponível — o caso do CI, que faz checkout raso — ela pula: é uma guarda de disciplina local,
como as duas que ela substitui.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Os arquivos únicos compartilhados por todas as etapas. Editá-los é privilégio de frente de
#: núcleo (preparo/shell de uma wave), nunca de frente de etapa — ADR-010, item (b).
#:
#: `frontend/` entra aqui pela Wave 10 (ADR-031/ADR-032): o núcleo do frontend muda de endereço de
#: `studio/web/*` para `frontend/src/**`, e o item (b) do ADR-010 passa a valer nos dois lugares
#: enquanto o vanilla e o React convivem atrás da ponte strangler.
NUCLEO_PREFIXOS = (
    "studio/web/",
    "studio/app.py",
    "studio/steps.py",
    "studio/config.py",
    "studio/higgsfield.py",
    "studio/etapas/__init__.py",
    "studio/index.html",
    "frontend/",
)

#: branch → (motivo verificável, prefixos do núcleo que a frente possui).
#:
#: Uma frente de etapa NÃO aparece aqui e continua barrada. Uma frente de núcleo aparece com o
#: recorte mínimo do que precisa tocar — o registro é auditável no PR.
TITULARES_DO_NUCLEO: dict[str, tuple[str, tuple[str, ...]]] = {
    "refactor/adh-os-20260902-08-react-fundacao": (
        "Wave 10 · E0 fundação — card [REACT-01]; cria o scaffold `frontend/` (ADR-031)",
        ("frontend/",),
    ),
    "refactor/adh-os-20260903-02-react-contrato-api": (
        "Wave 10 · E1 contrato tipado da API — card [REACT-02]; acrescenta `frontend/src/api/` "
        "(tipos gerados do /openapi.json, client HTTP e hooks TanStack Query) — ADR-031/ADR-032",
        ("frontend/",),
    ),
    "refactor/adh-os-20260903-03-react-design-system": (
        "Wave 10 · E2 design system e biblioteca de UI — card [REACT-03]; acrescenta "
        "`frontend/src/ui/` (componentes/hooks equivalentes ao `Studio.ui`) e `frontend/src/styles/` "
        "(cópia byte-a-byte de style.css/ui.css). O vanilla segue intocado até a E10 — ADR-031/ADR-032",
        ("frontend/",),
    ),
    "refactor/adh-os-20260903-04-react-shell-ponte": (
        "Wave 10 · E3 shell React + ponte strangler — card [REACT-04]; acrescenta o shell React em "
        "`frontend/src/shell/` (sidebar, rail, topbar, visão geral, wizard, roteamento por hash, "
        "contrato de host do plugin React e a ponte `window.Studio` para as 10 etapas vanilla) e "
        "serve o índice React sob a flag `STUDIO_UI=react` em `studio/app.py` — o serving estático do "
        "shell é a exceção sancionada (recon §1.1/§6.3), a lógica de backend (service/router/guide) "
        "segue intocada. O vanilla continua no default até a E10 — ADR-031/ADR-032",
        ("frontend/", "studio/app.py"),
    ),
    "refactor/adh-os-20260903-07-react-lote-c": (
        "Wave 10 · E6 lote C — áreas globais — card [REACT-07]; migra a biblioteca de mood boards "
        "(ADR-013), créditos & custos (ADR-016) e o componente compartilhado multishot (ADR-017) "
        "para React em `frontend/src/areas/*`, hospedadas pelo content-root do shell, e REMOVE os "
        "vanilla `studio/web/{moodboards,creditos,multishot}.js` + os `<script>` correspondentes em "
        "`studio/web/index.html`. O vanilla residual restante é cortado pela E10 — ADR-031/ADR-032",
        ("frontend/", "studio/web/"),
    ),
}


def _caminhos_da_branch() -> set[str] | None:
    """Caminhos tocados pela branch: commitados (vs. `merge-base develop`) + working tree.

    Devolve `None` quando não dá para comparar (sem git, sem `develop`) — o chamador pula.
    """
    git = shutil.which("git")
    if not git or not (ROOT / ".git").exists():
        return None

    def run(*args):
        return subprocess.run([git, "-C", str(ROOT), *args], capture_output=True, text=True)

    base = run("merge-base", "develop", "HEAD")
    if base.returncode != 0:
        return None
    commitado = run("diff", "--name-only", f"{base.stdout.strip()}..HEAD")
    assert commitado.returncode == 0, commitado.stderr
    trabalho = run("status", "--porcelain")
    assert trabalho.returncode == 0, trabalho.stderr

    caminhos = set(commitado.stdout.split())
    caminhos |= {ln[3:].strip().split(" -> ")[-1] for ln in trabalho.stdout.splitlines() if ln[3:].strip()}
    return caminhos


def _branch_atual() -> str:
    git = shutil.which("git")
    r = subprocess.run([git, "-C", str(ROOT), "branch", "--show-current"], capture_output=True, text=True)
    return r.stdout.strip()


def violacao(caminhos: set[str], branch: str,
             titulares: dict[str, tuple[str, tuple[str, ...]]] | None = None) -> str | None:
    """Decisão pura da guarda: devolve a mensagem de reprovação, ou `None` se a fronteira foi respeitada.

    Separada da coleta por git para que os três desfechos sejam testáveis sem fabricar branches:
    frente de etapa barrada, frente de núcleo dentro do recorte, frente de núcleo fora do recorte.
    """
    titulares = TITULARES_DO_NUCLEO if titulares is None else titulares
    sujos = sorted(p for p in caminhos if p.startswith(NUCLEO_PREFIXOS))
    if not sujos:
        return None
    if branch not in titulares:
        return (f"ADR-010: a branch `{branch}` toca o núcleo sem declarar titularidade: {sujos}\n"
                "Frente de etapa cria só `studio/etapas/<id>/` (+ `studio/<id>/service.py`). Se esta é "
                "mesmo uma frente de núcleo, registre-a em `TITULARES_DO_NUCLEO` "
                f"({Path(__file__).name}) com o card e o recorte mínimo de prefixos.")
    motivo, permitidos = titulares[branch]
    fora = sorted(p for p in sujos if not p.startswith(permitidos))
    if fora:
        return (f"a branch `{branch}` declarou titularidade sobre {list(permitidos)} ({motivo}), mas "
                f"tocou o núcleo fora desse recorte: {fora}\n"
                "Titularidade é registro, não isenção: amplie a declaração no PR ou tire estes "
                "arquivos do diff.")
    return None


def test_frente_de_etapa_nao_toca_o_nucleo():
    """ADR-010 (b): só frente de núcleo declarada em `TITULARES_DO_NUCLEO` edita os arquivos únicos."""
    caminhos = _caminhos_da_branch()
    if caminhos is None:
        pytest.skip("sem git ou sem `develop` para comparar (checkout raso do CI)")
    erro = violacao(caminhos, _branch_atual())
    assert erro is None, erro


# ---------- a guarda morde: os três desfechos, sem depender do estado da branch real ----------
FRENTE_DE_ETAPA = "feature/adh-os-99999999-01-etapa-nova"


def test_frente_de_etapa_e_barrada_no_nucleo():
    erro = violacao({"studio/etapas/mood/view.js", "studio/web/ui.js"}, FRENTE_DE_ETAPA, {})
    assert erro and "sem declarar titularidade" in erro and "studio/web/ui.js" in erro


def test_frente_de_etapa_passa_quando_fica_na_pasta_dela():
    assert violacao({"studio/etapas/mood/view.js", "studio/mood/service.py"}, FRENTE_DE_ETAPA, {}) is None


def test_frente_de_nucleo_passa_dentro_do_recorte_declarado():
    titulares = {"refactor/e2": ("Wave 10 · E2 — card [REACT-03]", ("studio/web/",))}
    assert violacao({"studio/web/ui.js", "studio/web/style.css"}, "refactor/e2", titulares) is None


def test_frente_de_nucleo_e_barrada_fora_do_recorte_declarado():
    titulares = {"refactor/e2": ("Wave 10 · E2 — card [REACT-03]", ("studio/web/",))}
    erro = violacao({"studio/web/ui.js", "studio/steps.py"}, "refactor/e2", titulares)
    assert erro and "fora desse recorte" in erro and "studio/steps.py" in erro


def test_frente_de_nucleo_da_wave_nao_e_barrada_por_remover_view_de_etapa():
    """Regressão da guarda antiga: ela barrava `studio/etapas/mood/view.` e quebrava a E4 por
    construção, que remove esses arquivos ao portar a tela para React."""
    assert violacao({"studio/etapas/mood/view.html", "studio/etapas/mood/view.js"}, FRENTE_DE_ETAPA, {}) is None


def test_o_registro_de_titularidade_tem_recorte_minimo():
    """Nenhum titular pode declarar o núcleo inteiro nem um prefixo que não seja do núcleo.

    Sem isto, a válvula de escape viraria a porta dos fundos: bastaria alguém registrar `("",)` ou
    `("studio/",)` para desligar a guarda para todo mundo que usasse aquela branch.
    """
    for branch, (motivo, permitidos) in TITULARES_DO_NUCLEO.items():
        assert motivo.strip(), f"{branch}: titularidade sem motivo verificável (card/ADR)"
        assert permitidos, f"{branch}: titularidade sem nenhum prefixo declarado"
        for p in permitidos:
            assert p in NUCLEO_PREFIXOS, (
                f"{branch}: `{p}` não é um prefixo do núcleo — declare um de {list(NUCLEO_PREFIXOS)}")
        assert set(permitidos) != set(NUCLEO_PREFIXOS), (
            f"{branch}: declarar o núcleo inteiro equivale a desligar a guarda; declare o recorte real")
