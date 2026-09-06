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
    "feature/adh-os-20260906-10-chat-navigate": (
        "`[extensão]` Wave 11 · frente F08 — o assistente leva a tela junto, card #88 "
        "(ADH-OS-20260906-10), FDD `docs/domains/chat/features/chat-navigate-fdd.md`. A tool "
        "`ui_navigate` e o registro das tools vivem em `studio/mcp/` (fora de NUCLEO_PREFIXOS). "
        "No núcleo, só `frontend/src/areas/chat/**`, `frontend/src/shell/"
        "{router.ts,events.ts}` e o bundle `studio/web/dist/`. Nenhuma rota nova, nenhum modelo "
        "Pydantic novo (logo `schema.ts` fica intocado), nenhuma etapa tocada. "
        "ADR-038/010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-04-chat-feedback": (
        "`[extensão]` Feedback ao vivo do assistente de chat (Wave 11 · F02), card #86 "
        "ADH-OS-20260906-04: ciclo de vida do turno, streaming de texto e progresso de job em "
        "`studio/chat/` (fora de NUCLEO_PREFIXOS). O núcleo tocado é só `frontend/` (dock, hook, "
        "rótulos de tool e CSS) e o bundle `studio/web/dist/`. Nenhuma rota REST nova e nenhum "
        "modelo Pydantic novo; os GERADOS `src/api/schema.ts` e `frontend/openapi.json` entram "
        "apenas regenerados por `make frontend-schema` (guarda de drift do CI). Nenhuma etapa nem "
        "o shell tocados. ADR-036/041, ADR-008/010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-14-chat-moodboards": (
        "`[extensão]` Biblioteca de Mood boards no chat, card #90 / ADH-OS-20260906-14 (wave 11 · "
        "F12): 16 tools MCP, resource e HLD do domínio. O trabalho é todo FORA do núcleo "
        "(`studio/mcp/**`, `studio/chat/{prompts,mudancas.py}`, `tests/`, `docs/`). O único "
        "toque em `frontend/` é UMA linha em `src/areas/chat/toolCredits.ts`: `moodboard_multishot` "
        "passa por `actions._paid`, e o próprio módulo da F10 manda espelhar ali toda tool paga "
        "nova, senão o dock não recarrega o saldo depois do gasto. Em `studio/web/` muda APENAS o "
        "bundle GERADO `studio/web/dist/` (`make frontend-build`, guarda de drift do CI). "
        "Nenhum componente, estilo ou rota do shell é alterado por esta frente — os demais "
        "arquivos de `frontend/` que aparecem no diff vêm do MERGE de `develop` (F10 creditos-chat, "
        "já revisada e mergeada), não de edição daqui. ADR-016/037/038, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-12-creditos-chat": (
        "`[extensão]` Créditos no chat, card #91 / ADH-OS-20260906-12 (wave 11 · F10): o gate de "
        "custo do dock mostrava duas linhas enquanto as telas mostravam a planilha inteira "
        "(ADR-016), e a ADR-038 §3 exigia um `confirm_token` que não existia no código. O grosso "
        "do trabalho é FORA do núcleo (`studio/common/pricing.py`, `studio/common/settings.py`, "
        "`studio/creditos/service.py`, `studio/mcp/**`, `studio/chat/prompts/`, os `router.py` das "
        "etapas e `studio/moodboards/router.py`). Em `frontend/` o recorte é "
        "`src/ui/{costRows.ts,CostSheet.tsx,index.ts}` (extração da fonte única das linhas de "
        "custo, DOM do `CostSheet` inalterado), `src/areas/chat/*` (widget rico, `CreditsChip` no "
        "cabeçalho, `toolCredits.ts`) e `src/areas/creditos/{CreditosArea.tsx,creditos.css}` "
        "(gasto hoje/campanha/total e a reconciliação explicada), mais os GERADOS "
        "`src/api/schema.ts` e `frontend/openapi.json`. Em `studio/web/` muda APENAS o bundle "
        "GERADO `studio/web/dist/` (`make frontend-build`, guarda de drift do CI). "
        "`src/styles/` (cópia byte-a-byte do vanilla) e `scripts/qa/cenarios/` NÃO são tocados. "
        "ADR-004/016/037/038, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-05-chat-sync": (
        "`[extensão]` Wave 11 · frente F03 — sincronização chat → telas, card #87 "
        "(ADH-OS-20260906-05): o evento `state_changed` nasce em `studio/chat/` e o mapa de tools "
        "em `studio/chat/mudancas.py` (fora de NUCLEO_PREFIXOS). O núcleo tocado é `frontend/` "
        "(barramento `src/shell/events.ts`, ponte no ChatDock, export de `invalidarGuia`) e o "
        "bundle `studio/web/dist/`. Nenhuma rota nova, nenhum modelo Pydantic novo, nenhuma etapa "
        "tocada. ADR-036/040, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-09-storyboard-geracao-por-cena": (
        "`[extensão]` Geração por cena na etapa 4 (ângulos da aula 011 + cena do produto da aula "
        "013), card ADH-OS-20260906-09 (wave 11): liga os endpoints por cena que já existiam e "
        "eram testados, mas não tinham chamador na tela. Todo o código próprio vive FORA do "
        "núcleo (`studio/storyboard/{local,angles}.py`, `studio/etapas/storyboard/**`, "
        "`studio/mcp/**`). Em `frontend/` muda APENAS o arquivo GERADO "
        "`frontend/src/api/schema.ts` (campo `scene` no modelo `LocalGenerateReq`) e o "
        "`frontend/openapi.json`; em `studio/web/` muda APENAS o bundle GERADO `studio/web/dist/` "
        "(`make frontend-schema` + `make frontend-build`, guarda de drift do CI). Nenhuma fonte do "
        "shell ou do design system é tocada. ADR-002/004/016/033/037, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-07-creditos-actions-catalog": (
        "Correção do catálogo de ações de crédito (ADR-016), card #92 / ADH-OS-20260906-07: quatro "
        "gerações reais gravavam no livro-caixa com chaves fora de `settings.ACTIONS`. O trabalho é "
        "quase todo fora do núcleo (`studio/common/{settings,pricing}.py`, `studio/storyboard/"
        "service.py`, testes). Núcleo tocado: `frontend/` SÓ no recorte `frontend/src/areas/"
        "creditos/` (rótulo 'Biblioteca' para gasto sem campanha e guarda de custo nulo na tabela) "
        "e o bundle `studio/web/dist/`, obrigatório pela guarda de drift. Nenhuma rota nem modelo "
        "Pydantic muda, logo `frontend/src/api/schema.ts` fica intocado; nenhuma etapa é tocada. "
        "ADR-016, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260906-03-chat-markdown": (
        "`[extensão]` Wave 11 · F01 — markdown na bolha do assistente do dock de chat, card #85 "
        "(https://trello.com/c/lqrj73sV), FDD `docs/domains/chat/features/chat-markdown-fdd.md`. "
        "Recorte mínimo: `frontend/` (componente novo `src/areas/chat/MessageMarkdown.tsx`, duas "
        "chamadas no `switch` do `Message` em `ChatDock.tsx`, regras `.chat-md*` em `chat.css` e "
        "as deps pinadas `react-markdown`/`remark-gfm` em `package.json` — ADR-031) e "
        "`studio/web/` só pelo bundle regenerado por `make frontend-build` (ADR-032). Nenhuma "
        "rota nem modelo Pydantic muda, logo `schema.ts` não é regenerado.",
        ("frontend/", "studio/web/"),
    ),
    "fix/adh-os-20260905-09-schema-drift-trace": (
        "Hotfix: regenera `frontend/src/api/schema.ts` para a rota `GET /api/chats/{id}/trace` "
        "adicionada na Onda E (o schema não foi regenerado, quebrando a guarda de drift do CI em "
        "develop). Só o arquivo GERADO muda. ADR-031/032.",
        ("frontend/",),
    ),
    "feature/adh-os-20260905-08-chat-onda-e": (
        "`[extensão]` Onda E — conhecimento, MCP no terminal, observabilidade e docs, card "
        "ADH-OS-20260905-08: `.mcp.json` (raiz), resources e trace em `studio/mcp`/`studio/chat` "
        "(fora de NUCLEO_PREFIXOS), skills e docs. O único núcleo tocado é `frontend/`, e só um "
        "arquivo de TESTE (`useChatSocket.test.ts`) — nenhuma fonte do bundle muda. ADR-037.",
        ("frontend/",),
    ),
    "feature/adh-os-20260905-07-chat-onda-d": (
        "`[extensão]` Onda D — biblioteca de Personagens e identidade (ADR-039), card "
        "ADH-OS-20260905-07: novo domínio `studio/characters/` e `studio/mcp/` (fora de "
        "NUCLEO_PREFIXOS). Núcleo tocado: `studio/app.py` (include do router + mount /cfiles), "
        "`studio/higgsfield.py` (soul_id_create/list — Soul ID via CLI oficial, ADR-002), "
        "`frontend/` (área Personagens + link/rota no shell) e o bundle `studio/web/dist/`. "
        "Nenhuma etapa é tocada. ADR-039, ADR-002/033/010/031/032.",
        ("studio/app.py", "studio/higgsfield.py", "frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260905-06-chat-onda-c": (
        "`[extensão]` Onda C do assistente de chat (abas paralelas, ui.open, limite de ativos), "
        "card ADH-OS-20260905-06: mudanças em `studio/chat/` e `studio/mcp/` (fora de "
        "NUCLEO_PREFIXOS). O núcleo tocado é só `frontend/` (ChatDock com abas, tabs, widget open) "
        "e o bundle `studio/web/dist/`. Nenhuma rota nova, nenhuma etapa nem o shell tocados. "
        "ADR-036/038, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260905-05-chat-onda-b": (
        "`[extensão]` Onda B do assistente de chat (implementa ADR-037/038), card "
        "ADH-OS-20260905-05: tools de ação e `ui.*` em `studio/mcp/` e o endpoint `/emit` em "
        "`studio/chat/` (fora de NUCLEO_PREFIXOS). O núcleo tocado é só `frontend/` (cartões ricos "
        "no ChatDock, `schema.ts` regenerado pela rota `/emit`) e o bundle `studio/web/dist/`. "
        "Nenhuma etapa nem o shell são tocados. ADR-037/038, ADR-010/031/032.",
        ("frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260905-04-chat-onda-a": (
        "`[extensão]` Onda A do assistente de chat (ADR-036/037/040), card ADH-OS-20260905-04: "
        "novos módulos `studio/chat/` e `studio/mcp/` (fora de NUCLEO_PREFIXOS) e a nova área "
        "global de chat no frontend (`frontend/src/areas/chat/` + montagem do dock no shell). O "
        "núcleo tocado é `studio/app.py` (include do router do chat + WebSocket) e `frontend/` (o "
        "dock no `Shell.tsx`, o registro no roteamento e o bundle versionado `studio/web/dist/`). "
        "Nenhuma etapa é tocada. ADR-036/037/040, ADR-010/031/032.",
        ("studio/app.py", "frontend/", "studio/web/"),
    ),
    "feature/adh-os-20260905-02-remove-combo-formulas": (
        "Remoção do combo de fórmulas da aula (`#sbPreset`) do Storyboard, ADR-035 (reconcilia o "
        "PR #103 pré-Wave-10 na versão React): a UI da etapa muda, exigindo RECONSTRUIR o bundle "
        "versionado `studio/web/dist/`. O backend e a UI da etapa (`studio/etapas/storyboard/**`) "
        "não são núcleo; `schema.ts` não muda (a chave `presets` não era tipada). ADR-035, ADR-032.",
        ("studio/web/",),
    ),
    "feature/adh-os-20260905-01-storyboard-motor-local": (
        "`[extensão]` motor de imagem LOCAL na etapa 4 (ADR-033), card ADH-OS-20260905-01: rotas "
        "novas `/storyboard/local/*` mudam o `/openapi.json`, exigindo REGERAR `frontend/src/api/"
        "schema.ts` (guarda de drift do CI), e a UI nova (`studio/etapas/storyboard/ui/MaskEditor.tsx` "
        "+ painel local no `Ideation.tsx`, ambos co-localizados na etapa) exige RECONSTRUIR o bundle "
        "versionado `studio/web/dist/`. A lógica das outras etapas e do shell (`frontend/src/**`) fica "
        "intocada — só os dois artefatos gerados. ADR-033, ADR-031/ADR-032.",
        ("frontend/", "studio/web/"),
    ),
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
    "refactor/adh-os-20260903-05-react-lote-a": (
        "Wave 10 · E4 lote A (mood/publish/export/music) + correções de integração do shell E2/E3 que "
        "destravam as frentes de tela (resolução de `studio/etapas/*/ui` no tsconfig/vite/eslint, "
        "`Guide.tsx`/`PluginHost` para o diff de textContent do ADR-004, `useUpload` `.over` síncrono) "
        "— card [REACT-05]. A pasta das etapas (`studio/etapas/`) não é prefixo do núcleo e não entra "
        "no recorte; só `frontend/` precisa de titularidade.",
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
    "refactor/adh-os-20260903-10-react-lote-f": (
        "Wave 10 · E9 lote F — etapa edit — card [REACT-10]; migra a etapa 7 (Studio de vídeo) para "
        "`studio/etapas/edit/ui/`. Toca `frontend/` só na INTEGRAÇÃO da wave: torna a guarda de "
        "`frontend/src/shell/host.test.tsx` robusta a novas migrações (id inexistente no lugar de "
        "`edit`, que deixou de ser vanilla). Recorte `frontend/` — ADR-031/ADR-032",
        ("frontend/",),
    ),
    "refactor/adh-os-20260903-11-react-corte-final": (
        "Wave 10 · E10 corte e fechamento — card [REACT-11]; React vira o DEFAULT. REMOVE a flag "
        "`STUDIO_UI` e a rota `/steps/<id>/view.{html,js}` de `studio/app.py` (única mudança de "
        "backend da wave), o resíduo vanilla `studio/web/{index.html,app.js,ui.js,ui.css,style.css}` "
        "e a ponte strangler `window.Studio` do shell React (`frontend/src/shell/bridge.ts`), e "
        "COMMITA o bundle `studio/web/dist/`. Recorte: `frontend/`, `studio/web/`, `studio/app.py`. "
        "ADR-031/ADR-032, ADR-001/ADR-004/ADR-006/ADR-008/ADR-010/ADR-017.",
        ("frontend/", "studio/web/", "studio/app.py"),
    ),
    "refactor/adh-os-20260903-09-react-lote-e": (
        "Wave 10 · E8 lote E storyboard + canvas de marcação — card [REACT-09]; porta a etapa 4 para "
        "React em `studio/etapas/storyboard/ui/` (com o canvas `Annotate` CO-LOCALIZADO na própria "
        "etapa, não no shell) e REMOVE `studio/web/annotate.js`. O ÚNICO arquivo de núcleo tocado é "
        "`studio/web/annotate.js` (deleção); como o guard granulariza por prefixo de `NUCLEO_PREFIXOS`, "
        "o recorte mínimo declarável é `studio/web/`. Não toca o shell (`frontend/src/**`), que é da E4. "
        "ADR-031/ADR-032, ADR-004/ADR-017/ADR-021.",
        ("studio/web/",),
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
