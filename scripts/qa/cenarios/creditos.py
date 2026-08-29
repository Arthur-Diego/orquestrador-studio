"""Casos da área global "Créditos & Custos" `[extensão]` (`studio/web/creditos.js` + `studio/creditos/`).

Quatro blocos na mesma rota reservada `#/creditos`: saldo do CLI, painel ADMIN dos modelos default
por ação (escopo Global × Esta campanha), tabela de custo por modelo/variação e histórico de gasto.

Os casos são registrados com `pid=None` (a rota é campanha-independente e `H.abrir_tela` levantaria
RuntimeError com um pid). A campanha usada no escopo "Esta campanha" é fixada por `_abrir()`, que
chama `Studio.creditos.open(pid)` — a tela guarda esse pid para os PUT/DELETE por projeto.

Higiene: todo caso que grava default (global em `STUDIO_STATE/config.json`, do projeto em
`projects/<pid>/config.json`) restaura o arquivo no fim — senão as telas de etapa e os casos
seguintes passam a ver um default diferente.
"""
from __future__ import annotations

import json

from scripts.qa import harness as H

TELA = "creditos"
CASOS: list[H.Caso] = []
_reg = H.registrador(TELA, CASOS)
JSON = {"content-type": "application/json"}


def caso(id: str, titulo: str):
    """Registra um caso da área global (sempre `pid=None` — a rota não tem campanha)."""
    return _reg(id, titulo, pid=None)


# ---------- helpers locais ----------
def _abrir(page, ctx, pid: str | None = "cheio", escopo: str = "global") -> None:
    """Abre a tela com a campanha desejada (`None` = sem campanha, como o deep link).

    O escopo do painel admin é estado de MÓDULO em `creditos.js`: ele sobrevive a `open()` e
    vazaria de um caso para o outro — por isso cada caso declara o escopo que quer.
    """
    alvo = None if pid is None else (ctx.pid_cheio if pid == "cheio" else pid)
    if not page.url.endswith("#/creditos"):
        H.ir(page, ctx, "#/creditos", espera_ms=200)
    page.evaluate("p => window.Studio.creditos.open(p)", alvo)
    page.wait_for_selector("#main .cr-table.admin tbody tr", timeout=H.TIMEOUT_MS)
    page.wait_for_timeout(200)
    if escopo and alvo:
        _escopo(page, escopo)


def _linha(page, acao: str):
    return page.locator(f"#main tr[data-action='{acao}']")


def _escopo(page, nome: str) -> None:
    """Garante o escopo pedido no painel admin (não clica se ele já está ativo)."""
    btn = page.locator(f"#main .cr-scope [data-scope='{nome}']")
    if not btn.count() or " on" in (btn.get_attribute("class") or ""):
        return
    btn.click()
    page.wait_for_selector("#main .cr-table.admin tbody tr", timeout=H.TIMEOUT_MS)
    page.wait_for_timeout(200)


def _config_global(ctx) -> dict:
    f = ctx.state_dir / "config.json"
    return json.loads(f.read_text()).get("defaults", {}) if f.exists() else {}


def _config_projeto(ctx, pid: str) -> dict:
    f = ctx.projeto(pid) / "config.json"
    return json.loads(f.read_text()).get("defaults", {}) if f.exists() else {}


def _limpar_global(ctx, *acoes: str) -> None:
    """Remove overrides globais do `config.json` da rodada (não existe DELETE global na API)."""
    f = ctx.state_dir / "config.json"
    if not f.exists():
        return
    cfg = json.loads(f.read_text())
    for a in acoes:
        cfg.get("defaults", {}).pop(a, None)
    f.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))


def _limpar_projeto(page, ctx, pid: str, *acoes: str) -> None:
    for a in acoes:
        H.api(page, ctx, "delete", f"/api/projects/{pid}/creditos/config/{a}")


def _cr(n) -> str:
    """Formata um número como o JS imprime (7.0 → "7", 7.5 → "7.5")."""
    f = float(n)
    return str(int(f)) if f == int(f) else str(f)


def _gastar(page, ctx, **kw) -> dict:
    """Registra um gasto no livro-caixa (o mesmo endpoint que as telas usam depois de gerar)."""
    corpo = {"action": "mood.multishot", "model": "nano_banana_2", "variant": "2k", "credits": 7,
             "step": "mood", **kw}
    return H.api(page, ctx, "post", "/api/creditos/spend", data=json.dumps(corpo), headers=JSON).json()


# ---------- saldo ----------
@caso("C-CREDITOS-01", "card de saldo mostra os créditos e o plano de /api/creditos/balance")
def saldo(page, ctx):
    _abrir(page, ctx)
    bal = H.api(page, ctx, "get", "/api/creditos/balance").json()
    valor = (page.locator("#main .cr-saldo b").text_content() or "").strip()
    chip = (page.locator("#main .cr-balance .chip").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "cr-saldo")
    esperado = str(bal.get("credits")) if bal.get("logged_in") else "—"
    return H.verifica(valor == esperado and (chip == (bal.get("plan") or "logado") if bal.get("logged_in") else True),
                      f"saldo={valor} chip='{chip}'",
                      f"saldo UI='{valor}' esperado='{esperado}' chip='{chip}' balance={bal}", ev)


@caso("C-CREDITOS-02", "'Atualizar saldo' consulta o CLI com refresh=1 e repinta o card")
def refresh_saldo(page, ctx):
    _abrir(page, ctx)
    with page.expect_response(lambda r: "/api/creditos/balance" in r.url and "refresh=1" in r.url,
                              timeout=H.TIMEOUT_MS) as resp:
        page.locator("#crRefresh").click()
    r = resp.value
    page.wait_for_selector("#crRefresh:not(.loading)", timeout=H.TIMEOUT_MS)
    page.wait_for_timeout(300)
    valor = (page.locator("#main .cr-saldo b").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "cr-refresh", full_page=False)
    return H.verifica(r.ok and valor == str(r.json().get("credits")),
                      f"HTTP {r.status}, saldo repintado em {valor}",
                      f"HTTP {r.status} saldo UI='{valor}' resposta={r.json()}", ev)


@caso("C-CREDITOS-03", "chip global de créditos (topbar/sidebar) reflete o mesmo saldo")
def chip_global(page, ctx):
    _abrir(page, ctx)
    bal = H.api(page, ctx, "get", "/api/creditos/balance").json()
    chips = page.locator("[data-credits-chip]").all_text_contents()
    esperado = f"{bal.get('credits')} créditos" if bal.get("logged_in") else "CLI"
    return H.verifica(bool(chips) and all(esperado in c for c in chips),
                      f"chips={chips}", f"chips={chips} esperado conter '{esperado}' (balance={bal})")


# ---------- painel admin ----------
@caso("C-CREDITOS-04", "tabela admin tem uma linha por ação, com custo e origem de /api/creditos")
def admin_linhas(page, ctx):
    _abrir(page, ctx)
    data = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/creditos").json()
    linhas = page.locator("#main .cr-table.admin tbody tr")
    chaves = linhas.evaluate_all("els => els.map(e => e.dataset.action)")
    modelos = page.locator("#main .cr-table.admin .cr-model").evaluate_all("els => els.map(e => e.value)")
    custos = page.locator("#main .cr-table.admin .cr-cost").all_text_contents()
    ev = H.evidencia(page, ctx, "cr-admin")
    esp_chaves = [a["key"] for a in data["actions"]]
    esp_modelos = [a["model"] for a in data["actions"]]
    esp_custos = [f"{a['credits']} cr" if a["credits"] is not None else "—" for a in data["actions"]]
    return H.verifica(chaves == esp_chaves and modelos == esp_modelos and [c.strip() for c in custos] == esp_custos,
                      f"{len(chaves)} ações com modelo e custo iguais à API",
                      f"chaves={chaves} vs {esp_chaves}; modelos={modelos} vs {esp_modelos}; "
                      f"custos={[c.strip() for c in custos]} vs {esp_custos}", ev)


@caso("C-CREDITOS-05", "o select de modelo de uma ação só oferece modelos do mesmo tipo")
def admin_opcoes(page, ctx):
    _abrir(page, ctx)
    data = H.api(page, ctx, "get", "/api/creditos").json()
    por_kind = {}
    for m in data["models"]:
        por_kind.setdefault(m["kind"], []).append(m["id"])
    erros = []
    for acao in data["actions"]:
        opts = _linha(page, acao["key"]).locator(".cr-model option").evaluate_all("els => els.map(e => e.value)")
        if opts != por_kind.get(acao["kind"], []):
            erros.append(f"{acao['key']} ({acao['kind']}): {opts} != {por_kind.get(acao['kind'])}")
    return H.verifica(not erros, f"{len(data['actions'])} ações com opções do próprio tipo", f"divergências: {erros}")


@caso("C-CREDITOS-06", "trocar o modelo no escopo Global grava em STUDIO_STATE/config.json")
def admin_global(page, ctx):
    acao = "mood.grid"
    try:
        _abrir(page, ctx)
        _linha(page, acao).locator(".cr-model").select_option("gpt_image_2")
        t = H.esperar_toast(page, "salvo")
        page.wait_for_timeout(600)
        cfg = _config_global(ctx)
        linha = _linha(page, acao)
        origem = (linha.locator(".cr-src .chip").text_content() or "").strip()
        custo = (linha.locator(".cr-cost").text_content() or "").strip()
        variacao = linha.locator(".cr-variant").count()
        # GET /api/creditos/config devolve os defaults JÁ RESOLVIDOS (lista), não o arquivo cru
        api = {a["action"]: a for a in H.api(page, ctx, "get", "/api/creditos/config").json()["defaults"]}
        ev = H.evidencia(page, ctx, "cr-admin-global")
        return H.verifica(cfg.get(acao, {}).get("model") == "gpt_image_2" and origem == "global"
                          and custo == "8.5 cr" and variacao == 0 and api.get(acao, {}).get("model") == "gpt_image_2",
                          f"toast='{t}', config.json={cfg.get(acao)}, origem='{origem}', custo={custo}",
                          f"toast='{t}' config.json={cfg.get(acao)} api={api.get(acao)} origem='{origem}' "
                          f"custo='{custo}' selects de variação={variacao}", ev)
    finally:
        _limpar_global(ctx, acao)


@caso("C-CREDITOS-07", "trocar a variação recalcula o custo da linha e persiste a resolução")
def admin_variacao(page, ctx):
    acao = "base.image"
    try:
        _abrir(page, ctx)
        linha = _linha(page, acao)
        antes = (linha.locator(".cr-cost").text_content() or "").strip()
        linha.locator(".cr-variant").select_option("4k")
        t = H.esperar_toast(page, "salvo")
        page.wait_for_timeout(600)
        linha = _linha(page, acao)
        depois = (linha.locator(".cr-cost").text_content() or "").strip()
        valor = linha.locator(".cr-variant").input_value()
        cfg = _config_global(ctx)
        ev = H.evidencia(page, ctx, "cr-admin-variacao", full_page=False)
        return H.verifica(antes == "2 cr" and depois == "4 cr" and valor == "4k"
                          and cfg.get(acao, {}).get("variant") == "4k",
                          f"toast='{t}', custo {antes} → {depois} e variação {valor} persistida",
                          f"toast='{t}' custo {antes}→{depois} select='{valor}' config.json={cfg.get(acao)}", ev)
    finally:
        _limpar_global(ctx, acao)


@caso("C-CREDITOS-08", "com campanha aberta, o seletor de escopo Global/Esta campanha aparece")
def escopo_visivel(page, ctx):
    _abrir(page, ctx)
    botoes = page.locator("#main .cr-scope .seg-btn").all_text_contents()
    ativo_global = page.locator("#main .seg-btn[data-scope='global']").get_attribute("class") or ""
    _escopo(page, "project")
    ativo_proj = page.locator("#main .seg-btn[data-scope='project']").get_attribute("class") or ""
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/creditos").json()["actions"]
    # "usar global" só fica clicável nas ações que TÊM override do projeto
    estado = page.locator("#main .cr-clear").evaluate_all("els => els.map(e => [e.dataset.action, !e.disabled])")
    esperado = [[a["key"], a["source"] == "project"] for a in api]
    ev = H.evidencia(page, ctx, "cr-escopo", full_page=False)
    return H.verifica([b.strip() for b in botoes] == ["Global", "Esta campanha"] and " on" in ativo_global
                      and " on" in ativo_proj and estado == esperado,
                      f"escopos={botoes}, {len(estado)} links 'usar global' coerentes com a origem",
                      f"botões={botoes} classe global='{ativo_global}' projeto='{ativo_proj}' "
                      f"links={estado} esperado={esperado}", ev)


@caso("C-CREDITOS-09", "override por campanha grava em projects/<pid>/config.json e marca a origem 'projeto'")
def admin_projeto(page, ctx):
    acao = "animate.video"
    try:
        _abrir(page, ctx)
        _escopo(page, "project")
        _linha(page, acao).locator(".cr-model").select_option("kling3_0_turbo")
        t = H.esperar_toast(page, "campanha")
        page.wait_for_timeout(600)
        cfg_proj = _config_projeto(ctx, ctx.pid_cheio)
        cfg_glob = _config_global(ctx)
        linha = _linha(page, acao)
        origem = (linha.locator(".cr-src .chip").text_content() or "").strip()
        clear_on = linha.locator(".cr-clear").is_enabled()
        custo = (linha.locator(".cr-cost").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "cr-admin-projeto")
        return H.verifica(cfg_proj.get(acao, {}).get("model") == "kling3_0_turbo" and origem == "projeto"
                          and clear_on and custo == "7.5 cr" and acao not in cfg_glob,
                          f"toast='{t}', override do projeto={cfg_proj.get(acao)}, origem='{origem}', custo={custo}",
                          f"toast='{t}' projeto={cfg_proj.get(acao)} global={cfg_glob.get(acao)} "
                          f"origem='{origem}' 'usar global' habilitado={clear_on} custo='{custo}'", ev)
    finally:
        _limpar_projeto(page, ctx, ctx.pid_cheio, acao)


@caso("C-CREDITOS-10", "'usar global' remove o override do projeto (DELETE) e a origem volta a código")
def usar_global(page, ctx):
    acao = "animate.video"
    try:
        H.api(page, ctx, "put", f"/api/projects/{ctx.pid_cheio}/creditos/config",
              data=json.dumps({"action": acao, "model": "kling3_0", "variant": "10s"}), headers=JSON)
        _abrir(page, ctx)
        _escopo(page, "project")
        linha = _linha(page, acao)
        antes = (linha.locator(".cr-src .chip").text_content() or "").strip()
        linha.locator(".cr-clear").click()
        t = H.esperar_toast(page, "removido")
        page.wait_for_timeout(600)
        linha = _linha(page, acao)
        origem = (linha.locator(".cr-src .chip").text_content() or "").strip()
        modelo = linha.locator(".cr-model").input_value()
        cfg = _config_projeto(ctx, ctx.pid_cheio)
        ev = H.evidencia(page, ctx, "cr-usar-global", full_page=False)
        return H.verifica(antes == "projeto" and origem == "código" and modelo == "kling2_6" and acao not in cfg,
                          f"toast='{t}', origem '{antes}' → '{origem}' e modelo de volta a {modelo}",
                          f"toast='{t}' origem {antes}→{origem} modelo={modelo} config do projeto={cfg}", ev)
    finally:
        _limpar_projeto(page, ctx, ctx.pid_cheio, acao)


@caso("C-CREDITOS-11", "default global sobrevive ao reload e continua marcado como 'global'")
def persistencia_global(page, ctx):
    acao = "storyboard.multishot"
    try:
        _abrir(page, ctx)
        _linha(page, acao).locator(".cr-model").select_option("gpt_image_2")
        H.esperar_toast(page, "salvo")
        page.wait_for_timeout(500)
        page.reload()
        H.esperar_tela(page)
        _abrir(page, ctx)
        linha = _linha(page, acao)
        origem = (linha.locator(".cr-src .chip").text_content() or "").strip()
        modelo = linha.locator(".cr-model").input_value()
        cfg = _config_global(ctx)
        ev = H.evidencia(page, ctx, "cr-persistencia", full_page=False)
        return H.verifica(origem == "global" and modelo == "gpt_image_2" and cfg.get(acao, {}).get("model") == "gpt_image_2",
                          f"após reload: modelo={modelo}, origem='{origem}'",
                          f"origem='{origem}' modelo={modelo} config.json={cfg.get(acao)}", ev)
    finally:
        _limpar_global(ctx, acao)


# ---------- tabela de custo ----------
@caso("C-CREDITOS-12", "tabela de custo agrupa por tipo na ordem de kind_order")
def custo_grupos(page, ctx):
    _abrir(page, ctx)
    data = H.api(page, ctx, "get", "/api/creditos").json()
    titulos = [t.strip() for t in page.locator("#main .cr-kind").all_text_contents()]
    esperado = [data["kind_label"][k] for k in data["kind_order"]
                if any(m["kind"] == k for m in data["models"])]
    return H.verifica(titulos == esperado, f"grupos={titulos}", f"grupos={titulos} esperado={esperado}")


@caso("C-CREDITOS-13", "tabela de custo lista uma linha por variação de cada modelo")
def custo_linhas(page, ctx):
    _abrir(page, ctx)
    data = H.api(page, ctx, "get", "/api/creditos").json()
    esperado = sum(len(m["rows"]) for m in data["models"])
    tabelas = page.locator("#main .cr-card:has(.cr-kind) .cr-table")   # o card de custo, não o histórico
    linhas = tabelas.locator("tbody tr").count()
    nano = [m for m in data["models"] if m["id"] == "nano_banana_2"][0]
    texto = tabelas.first.inner_text()
    ev = H.evidencia(page, ctx, "cr-custos")
    variacoes_ok = all(r["variant"] in texto and f"{r['credits']} cr" in texto for r in nano["rows"])
    return H.verifica(linhas == esperado and variacoes_ok,
                      f"{linhas} linhas de custo; {nano['label']} com {len(nano['rows'])} variações",
                      f"linhas={linhas} esperado={esperado} variações do nano na tabela={variacoes_ok}", ev)


@caso("C-CREDITOS-14", "custo da tabela admin é o medido; o gate de geração usa o custo ao vivo do CLI")
def custo_medido_vs_cli(page, ctx):
    _abrir(page, ctx)
    cost = H.api(page, ctx, "get", "/api/creditos/cost?action=mood.multishot").json()
    linha = (_linha(page, "mood.multishot").locator(".cr-cost").text_content() or "").strip()
    return H.verifica(linha == f"{cost['measured']} cr" and cost["credits"] is not None,
                      f"tabela={linha}; gate usa {cost['credits']} cr (source={cost['source']})",
                      f"linha='{linha}' measured={cost['measured']} credits={cost['credits']} source={cost['source']}")


# ---------- histórico ----------
@caso("C-CREDITOS-15", "gasto registrado aparece em 'Gerações recentes', por etapa e por projeto")
def historico(page, ctx):
    nome = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}").json()["name"]
    _gastar(page, ctx, pid=ctx.pid_cheio, project_name=nome, step="mood", credits=7)
    _abrir(page, ctx)
    resumo = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/creditos").json()["summary"]
    chips = [c.strip() for c in page.locator("#main .cr-card-head .chip").all_text_contents()]
    recentes = page.locator("#main .cr-hist-scroll tbody tr").count()
    etapas = page.locator("#main .cr-hist-grid table").first.inner_text()
    projetos = page.locator("#main .cr-hist-grid table").last.inner_text()
    ev = H.evidencia(page, ctx, "cr-historico")
    return H.verifica(f"total {_cr(resumo['total_credits'])} cr" in chips and f"{resumo['count']} gerações" in chips
                      and recentes >= 1 and "Mood board" in etapas and nome in projetos,
                      f"chips={chips}, {recentes} linhas recentes, etapa e projeto listados",
                      f"chips={chips} resumo={resumo} recentes={recentes} etapas='{etapas[:120]}' "
                      f"projetos='{projetos[:120]}'", ev)


@caso("C-CREDITOS-16", "com campanha aberta o histórico é o da campanha (nota + só os gastos do pid)")
def historico_por_campanha(page, ctx):
    _gastar(page, ctx, pid=ctx.pid_vazio, project_name="QA Vazia", step="animate", credits=10)
    _abrir(page, ctx)
    nota = page.locator("#main .cr-note").all_text_contents()
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/creditos").json()
    linhas = page.locator("#main .cr-hist-scroll tbody tr").count()
    texto = page.locator("#main .cr-hist-scroll").inner_text()
    ev = H.evidencia(page, ctx, "cr-historico-campanha", full_page=False)
    return H.verifica(any("campanha atual" in n for n in nota) and linhas == min(len(api["history"]), 30)
                      and "QA Vazia" not in texto,
                      f"nota da campanha e {linhas} linhas só do pid atual",
                      f"notas={[n[:60] for n in nota]} linhas={linhas} history_api={len(api['history'])} "
                      f"contém outra campanha={'QA Vazia' in texto}", ev)


@caso("C-CREDITOS-17", "sem campanha (deep link) a tela mostra o total geral e só defaults globais")
def deep_link_sem_campanha(page, ctx):
    try:
        page.goto("about:blank")                       # documento novo: o deep link não herda o pid
        page.goto(f"{ctx.base}/#/creditos")
        H.esperar_tela(page)
        page.wait_for_selector("#main .cr-table.admin tbody tr", timeout=H.TIMEOUT_MS)
        geral = H.api(page, ctx, "get", "/api/creditos").json()
        toggle = page.locator("#main .cr-scope").count()
        notas = [n.strip() for n in page.locator("#main .cr-note").all_text_contents()]
        chips = [c.strip() for c in page.locator("#main .cr-card-head .chip").all_text_contents()]
        topbar_vazio = "vazio" in (page.locator("#topbar").get_attribute("class") or "")
        ev = H.evidencia(page, ctx, "cr-deep-link")
        return H.verifica(toggle == 0 and any("abra uma campanha" in n.lower() for n in notas) and topbar_vazio
                          and f"total {_cr(geral['summary']['total_credits'])} cr" in chips,
                          "sem toggle de escopo, nota de defaults globais e total geral nos chips",
                          f"toggle={toggle} notas={[n[:60] for n in notas]} chips={chips} "
                          f"total_geral={geral['summary']['total_credits']} topbar vazio={topbar_vazio}", ev)
    finally:
        page.goto(f"{ctx.base}/")
        H.esperar_tela(page)


@caso("C-CREDITOS-18", "chip de créditos da topbar abre a área de Créditos & Custos")
def botao_topbar(page, ctx):
    H.ir(page, ctx, f"#/{ctx.pid_cheio}/overview")
    page.locator("#btnCredits").click()
    H.esperar_tela(page)
    page.wait_for_selector("#main .cr-table.admin tbody tr", timeout=H.TIMEOUT_MS)
    ativo = "active" in (page.locator("#btnCreditos").get_attribute("class") or "")
    titulo = (page.locator("#main h2").first.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "cr-abrir-topbar", full_page=False)
    return H.verifica(page.url.endswith("#/creditos") and "Créditos" in titulo and ativo,
                      f"abriu '{titulo}' e marcou o item do menu",
                      f"url={page.url} título='{titulo}' menu ativo={ativo}", ev)


@caso("C-CREDITOS-19", "trocar de escopo não perde o override do projeto nem o mostra no global")
def escopo_isolado(page, ctx):
    acao = "storyboard.scene"
    try:
        H.api(page, ctx, "put", "/api/creditos/config",
              data=json.dumps({"action": acao, "model": "nano_banana_2", "variant": "1k"}), headers=JSON)
        H.api(page, ctx, "put", f"/api/projects/{ctx.pid_cheio}/creditos/config",
              data=json.dumps({"action": acao, "model": "gpt_image_2", "variant": None}), headers=JSON)
        _abrir(page, ctx)
        no_global = (_linha(page, acao).locator(".cr-src .chip").text_content() or "").strip()
        modelo_global = _linha(page, acao).locator(".cr-model").input_value()
        _escopo(page, "project")
        no_projeto = (_linha(page, acao).locator(".cr-src .chip").text_content() or "").strip()
        _escopo(page, "global")
        volta = (_linha(page, acao).locator(".cr-src .chip").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "cr-escopo-isolado", full_page=False)
        # a tabela mostra sempre o default EFETIVO da campanha aberta (projeto › global › código)
        return H.verifica(no_global == no_projeto == volta == "projeto" and modelo_global == "gpt_image_2",
                          f"origem estável ('{volta}') ao alternar escopos, sem perder o override",
                          f"global='{no_global}' projeto='{no_projeto}' volta='{volta}' modelo={modelo_global}", ev)
    finally:
        _limpar_projeto(page, ctx, ctx.pid_cheio, acao)
        _limpar_global(ctx, acao)


@caso("C-CREDITOS-20", "cada select do painel admin tem nome acessível (rótulo/aria-label)")
def admin_acessibilidade(page, ctx):
    _abrir(page, ctx)
    sem_nome = page.locator("#main .cr-table.admin select").evaluate_all("""els => els.filter(e =>
        !(e.getAttribute('aria-label') || e.getAttribute('title') || e.closest('label') ||
          (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`))))
        .map(e => (e.closest('tr') ? e.closest('tr').dataset.action : '?') + ' · ' + e.className)""")
    total = page.locator("#main .cr-table.admin select").count()
    ev = H.evidencia(page, ctx, "cr-a11y-selects", full_page=False)
    return H.verifica(not sem_nome, f"{total} selects com nome acessível",
                      f"{len(sem_nome)} de {total} selects sem rótulo/aria-label: {sem_nome[:6]}", ev)
