"""Harness Playwright do QA E2E do Orquestrador Studio (skill qa-studio).

Fora do CI (ADR-008): precisa do servidor da rodada no ar (`scripts/qa/stack-up.sh`) e do Chromium
do Playwright. Os cenários em `scripts/qa/cenarios/<tela>.py` usam este módulo; o runner é
`scripts/qa/run.py`.

Conceitos:
- `Ctx`: ambiente da rodada (base URL, pids do seed, diretórios, tema/viewport atuais).
- `Resultado`: saída de um caso — PASSA / FALHA / BLOQUEADO + detalhe + evidências.
- `@caso(id, titulo)`: registra a função como caso da tela (cada módulo de cenário tem `TELA` e
  acumula em `CASOS`).
- `Sonda`: ouvintes de `console`, `pageerror`, respostas HTTP ≥ 400 e requests falhas por página.
- `auditar_visual(page)`: checagens automáticas de layout (overflow horizontal, imagens quebradas,
  botões sem nome acessível, elementos fora do viewport).
"""
from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

PASSA, FALHA, BLOQUEADO = "PASSA", "FALHA", "BLOQUEADO"
#: Telas globais (sem etapa) e aliases numéricos das etapas (a ordem vem de /api/steps).
TELAS_GLOBAIS = ("shell", "overview", "moodboards", "creditos")
TIMEOUT_MS = 15_000


# ---------- ambiente ----------
def carregar_env(run_dir: Path) -> dict[str, str]:
    """Lê os `export` de `.qa/runs/<run>/env.sh` sem precisar de shell."""
    env: dict[str, str] = {}
    for line in (run_dir / "env.sh").read_text().splitlines():
        m = re.match(r'export (\w+)="(.*)"$', line.strip())
        if m:
            env[m.group(1)] = m.group(2)
    return env


@dataclass
class Ctx:
    base: str
    run_dir: Path
    pid_cheio: str
    pid_vazio: str
    mbid: str
    tema: str = "light"
    viewport: tuple[int, int] = (1440, 900)
    projects_dir: Path | None = None
    moodboards_dir: Path | None = None
    state_dir: Path | None = None
    fake_dir: Path | None = None
    modo: str = "offline"
    steps: list[dict] = field(default_factory=list)

    @classmethod
    def da_rodada(cls, run_dir: Path) -> Ctx:
        env = carregar_env(run_dir)
        seed = json.loads((run_dir / "seed.json").read_text())
        ctx = cls(base=env["QA_BASE_URL"], run_dir=run_dir, pid_cheio=seed["pid_cheio"],
                  pid_vazio=seed["pid_vazio"], mbid=seed["mbid"],
                  projects_dir=Path(env["STUDIO_PROJECTS"]), moodboards_dir=Path(env["STUDIO_MOODBOARDS"]),
                  state_dir=Path(env["STUDIO_STATE"]), fake_dir=Path(env.get("QA_FAKE_DIR", run_dir / "fakes")),
                  modo=env.get("QA_MODE", "offline"))
        os.environ.setdefault("QA_BASE_URL", ctx.base)
        return ctx

    @property
    def evid_dir(self) -> Path:
        d = self.run_dir / "evidencias"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def projeto(self, pid: str) -> Path:
        assert self.projects_dir is not None
        return self.projects_dir / pid

    def moodboard(self, mbid: str) -> Path:
        assert self.moodboards_dir is not None
        return self.moodboards_dir / mbid

    @property
    def downloads_dir(self) -> Path:
        d = Path(carregar_env(self.run_dir).get("STUDIO_DOWNLOADS", self.run_dir / "downloads"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def rota(self, tela: str, pid: str | None = None, sub: str | None = None) -> str:
        """`sub` = id de sub-tela de área global (ex.: mbid do editor de mood board)."""
        pid = pid or self.pid_cheio
        if tela in ("shell", "overview"):
            return f"#/{pid}/overview"
        if tela == "moodboards":
            return f"#/moodboards/{sub}" if sub else "#/moodboards"
        if tela == "creditos":
            return "#/creditos"
        return f"#/{pid}/{tela}"

    def fakes_log(self) -> str:
        p = (self.fake_dir or self.run_dir / "fakes") / "fakes.log"
        return p.read_text() if p.exists() else ""


# ---------- resultado e registro de casos ----------
@dataclass
class Resultado:
    status: str
    detalhe: str = ""
    evidencias: list[str] = field(default_factory=list)
    #: status HTTP ≥ 400 que o caso PROVOCA de propósito (caminho triste): o runner não os conta
    #: como erro da sonda. Ex.: `res.http_esperados = (422,)`.
    http_esperados: tuple[int, ...] = ()

    def esperando(self, *status: int) -> Resultado:
        self.http_esperados = tuple(status)
        return self

    @staticmethod
    def passa(detalhe: str = "", *evid: str) -> Resultado:
        return Resultado(PASSA, detalhe, list(evid))

    @staticmethod
    def falha(detalhe: str, *evid: str) -> Resultado:
        return Resultado(FALHA, detalhe, list(evid))

    @staticmethod
    def bloqueado(motivo: str, *evid: str) -> Resultado:
        return Resultado(BLOQUEADO, motivo, list(evid))


@dataclass
class Caso:
    id: str
    titulo: str
    tela: str
    fn: Callable[[Page, Ctx], Resultado]
    pid: str = "cheio"           # "cheio" | "vazio" | None (tela global)


def registrador(tela: str, casos: list[Caso]):
    """Fábrica do decorador `@caso` de um módulo de cenário."""
    def caso(id: str, titulo: str, pid: str = "cheio"):
        def deco(fn):
            casos.append(Caso(id=id, titulo=titulo, tela=tela, fn=fn, pid=pid))
            return fn
        return deco
    return caso


def verifica(cond: bool, ok: str, erro: str, *evid: str) -> Resultado:
    return Resultado.passa(ok, *evid) if cond else Resultado.falha(erro, *evid)


# ---------- navegador e sonda ----------
class Sonda:
    """Coleta o que o navegador reclama enquanto um caso roda."""

    def __init__(self, page: Page, base: str) -> None:
        self.base = base
        self.console: list[str] = []
        self.pageerrors: list[str] = []
        self.http: list[dict] = []
        self.falhas_rede: list[str] = []
        self.requests: list[str] = []
        page.on("console", lambda m: self.console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: self.pageerrors.append(str(e)))
        page.on("response", lambda r: self.http.append({"status": r.status, "method": r.request.method,
                                                         "url": r.url.replace(base, "")}) if r.status >= 400 else None)
        page.on("requestfailed", lambda r: self.falhas_rede.append(f"{r.method} {r.url.replace(base, '')}: {r.failure}"))
        page.on("request", lambda r: self.requests.append(r.url.replace(base, "")))

    def zerar(self) -> None:
        for lst in (self.console, self.pageerrors, self.http, self.falhas_rede, self.requests):
            lst.clear()

    def snapshot(self) -> dict:
        return {"console": list(self.console), "pageerrors": list(self.pageerrors),
                "http_erros": list(self.http), "falhas_rede": list(self.falhas_rede)}

    def limpo(self, ignorar_http: tuple[int, ...] = ()) -> bool:
        return not self.pageerrors and not self.console and not [h for h in self.http if h["status"] not in ignorar_http]


class Navegador:
    def __init__(self, ctx: Ctx, headless: bool = True) -> None:
        self.ctx = ctx
        self._pw = sync_playwright().start()
        self.browser: Browser = self._pw.chromium.launch(headless=headless)
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.sonda: Sonda | None = None

    def nova_pagina(self, tema: str | None = None, viewport: tuple[int, int] | None = None) -> tuple[Page, Sonda]:
        if self.context:
            self.context.close()
        tema = tema or self.ctx.tema
        w, h = viewport or self.ctx.viewport
        self.context = self.browser.new_context(viewport={"width": w, "height": h}, color_scheme=tema,
                                                accept_downloads=True)
        self.context.set_default_timeout(TIMEOUT_MS)
        # botões "Copiar" usam navigator.clipboard: sem a permissão eles rejeitam em silêncio
        self.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.ctx.base)
        self.page = self.context.new_page()
        self.sonda = Sonda(self.page, self.ctx.base)
        # tema explícito da UI (auto → light/dark) via localStorage antes do primeiro load
        self.page.add_init_script(f"try{{localStorage.setItem('studio.theme', '{tema}')}}catch(e){{}}")
        return self.page, self.sonda

    def fechar(self) -> None:
        try:
            if self.context:
                self.context.close()
            self.browser.close()
        finally:
            self._pw.stop()


# ---------- navegação e espera ----------
def ir(page: Page, ctx: Ctx, rota: str, espera_ms: int = 800, forcar: bool = False) -> None:
    """Abre `rota` (`#/...`). Se já estiver no app, troca só o hash (dispara `hashchange`).

    Hash igual ao atual NÃO remonta a tela; `forcar=True` recarrega a página (DOM limpo)."""
    if page.url.startswith(ctx.base) and not forcar:
        page.evaluate("h => { location.hash = h; }", rota)
    else:
        page.goto(f"{ctx.base}/{rota}")
        if forcar:
            page.reload()
    esperar_tela(page, espera_ms)


def esperar_tela(page: Page, espera_ms: int = 800) -> None:
    """Espera o `#main` sair de 'Carregando…' e a rede acalmar."""
    try:
        page.wait_for_function("() => { const m = document.querySelector('#main'); "
                               "return m && !/Carregando…/.test(m.textContent || '') }", timeout=TIMEOUT_MS)
    except PWTimeout:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeout:
        pass
    page.wait_for_timeout(espera_ms)


def abrir_tela(page: Page, ctx: Ctx, tela: str, pid: str | None = None, forcar: bool = False) -> None:
    """Abre a tela e GARANTE que a SPA ficou no pid pedido.

    A SPA só conhece a lista de campanhas carregada no boot: um pid criado depois (via API) cai
    silenciosamente na 1ª campanha — e qualquer ação destrutiva iria para o projeto errado. Por
    isso, se o hash final não tiver o pid, recarrega a página uma vez e, persistindo, levanta.
    """
    rota = ctx.rota(tela, pid)
    ir(page, ctx, rota, forcar=forcar)
    alvo = None if tela in ("moodboards", "creditos") else (pid or ctx.pid_cheio)
    if alvo and f"#/{alvo}/" not in page.url:
        page.goto(f"{ctx.base}/{rota}")
        esperar_tela(page)
        if f"#/{alvo}/" not in page.url:
            raise RuntimeError(f"SPA não ficou no pid {alvo}: url={page.url} (rota {rota})")


def modal(page: Page):
    """Locator do modal aberto (o `ui.modal`/`ui.progress` usam `.modal[role=dialog]`)."""
    return page.locator(".modal[role=dialog]").last


def fechar_modal(page: Page) -> None:
    m = modal(page)
    if m.count() and m.is_visible():
        btn = m.locator(".modal-close")
        try:
            if btn.count() and btn.is_enabled():
                btn.click(timeout=2000)      # clique interceptado por overlay → cai no Escape
            else:
                page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        if m.count() and m.is_visible():   # último recurso: remove o backdrop pelo DOM
            page.evaluate("() => document.querySelectorAll('.modal-backdrop').forEach(b => b.remove())")


def esperar_modal_sumir(page: Page, timeout_ms: int = 60_000) -> bool:
    try:
        page.wait_for_function("() => !document.querySelector('.modal[role=dialog]')", timeout=timeout_ms)
        return True
    except PWTimeout:
        return False


def toast(page: Page) -> str:
    t = page.locator("#toast")
    return (t.text_content() or "").strip() if t.count() and t.is_visible() else ""


def esperar_toast(page: Page, contendo: str = "", timeout_ms: int = 8000) -> str:
    """Devolve o toast que contém `contendo` (ou o primeiro toast). Sem toast → `""`.

    Se apareceu um toast com OUTRO texto, ele fica em `esperar_toast.ultimo` para o diagnóstico."""
    esperar_toast.ultimo = ""
    fim = time.time() + timeout_ms / 1000
    while time.time() < fim:
        t = toast(page)
        if t:
            esperar_toast.ultimo = t
            if not contendo or contendo.lower() in t.lower():
                return t
        page.wait_for_timeout(150)
    return ""


esperar_toast.ultimo = ""


def remontar(page: Page) -> None:
    """Recarrega a página e espera a tela — para não herdar o DOM do caso anterior quando o hash
    não muda (`ir` só troca o hash, e hash igual não dispara `hashchange`)."""
    page.reload()
    esperar_tela(page)


def esperar_progresso(page: Page, timeout_ms: int = 120_000) -> dict:
    """Espera o modal de progresso (`ui.progress`/`progressJob`) aparecer e terminar.

    Devolve {abriu, fechavel_no_inicio, passos, nota, sumiu}. `fechavel_no_inicio` deve ser False
    (o `.modal-close` nasce `disabled` até o job acabar)."""
    info = {"abriu": False, "fechavel_no_inicio": None, "passos": [], "nota": "", "sumiu": False}
    try:
        page.wait_for_selector(".modal[role=dialog] .prog-steps", timeout=10_000)
    except PWTimeout:
        return info
    info["abriu"] = True
    btn = page.locator(".modal[role=dialog] .modal-close").last
    info["fechavel_no_inicio"] = btn.is_enabled() if btn.count() else None
    try:
        page.wait_for_function("() => { const b = document.querySelector('.modal[role=dialog] .modal-close');"
                               " return !b || !b.disabled }", timeout=timeout_ms)
    except PWTimeout:
        info["nota"] = "timeout: o modal de progresso não terminou"
        return info
    m = page.locator(".modal[role=dialog]").last
    if m.count():
        info["passos"] = m.locator(".prog-steps li").all_text_contents()
        nota = m.locator(".prog-note")
        info["nota"] = (nota.text_content() or "").strip() if nota.count() else ""
        fechar_modal(page)
    info["sumiu"] = esperar_modal_sumir(page, 5000)
    return info


class dialogos:
    """Context manager para `confirm()`/`alert()` nativos — o Playwright recusa todos por padrão.

        with H.dialogos(page, aceitar=True) as d: page.click("text=Remover")
        d.mensagens  # textos dos diálogos que apareceram
    """

    def __init__(self, page: Page, aceitar: bool = True) -> None:
        self.page, self.aceitar, self.mensagens = page, aceitar, []

    def _on(self, d) -> None:
        self.mensagens.append(d.message)
        d.accept() if self.aceitar else d.dismiss()

    def __enter__(self):
        self.page.on("dialog", self._on)
        return self

    def __exit__(self, *_):
        self.page.remove_listener("dialog", self._on)


def liberar_clipboard(page: Page, ctx: Ctx) -> None:
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=ctx.base)


def clipboard(page: Page) -> str:
    return page.evaluate("() => navigator.clipboard.readText()")


def api_json(page: Page, ctx: Ctx, method: str, path: str, body: dict | list | None = None):
    """`api()` com corpo JSON e content-type já preenchidos."""
    return api(page, ctx, method, path, data=json.dumps(body if body is not None else {}),
               headers={"content-type": "application/json"})


class projeto_descartavel:
    """Cria uma campanha via API, recarrega a SPA (que só conhece campanhas do boot) e apaga no fim.

        with H.projeto_descartavel(page, ctx, "QA Remover") as pid: ...
    """

    def __init__(self, page: Page, ctx: Ctx, nome: str, product: str = "produto qa") -> None:
        self.page, self.ctx, self.nome, self.product, self.pid = page, ctx, nome, product, None

    def __enter__(self) -> str:
        import shutil
        r = api_json(self.page, self.ctx, "post", "/api/projects", {"name": self.nome, "product": self.product})
        if r.status == 409:
            self.pid = next(p["id"] for p in api(self.page, self.ctx, "get", "/api/projects").json()
                            if p["name"] == self.nome)
            shutil.rmtree(self.ctx.projeto(self.pid), ignore_errors=True)
            r = api_json(self.page, self.ctx, "post", "/api/projects", {"name": self.nome, "product": self.product})
        self.pid = r.json()["id"]
        remontar(self.page)
        return self.pid

    def __exit__(self, *_):
        import shutil
        if self.pid:
            shutil.rmtree(self.ctx.projeto(self.pid), ignore_errors=True)


def probe(path: Path) -> dict:
    """Duração, streams e dimensões de um arquivo de mídia gerado (ffprobe)."""
    import subprocess
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        return {"erro": p.stderr.strip()[:200]}
    data = json.loads(p.stdout or "{}")
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {"duracao": float(data.get("format", {}).get("duration", 0) or 0),
            "video": bool(v), "audio": any(s.get("codec_type") == "audio" for s in streams),
            "largura": v.get("width"), "altura": v.get("height"), "streams": len(streams)}


def esperar_job(ctx: Ctx, page: Page, url: str, timeout_s: int = 120) -> dict:
    """Faz polling de um endpoint `/job` até sair de `running`."""
    fim = time.time() + timeout_s
    while time.time() < fim:
        r = page.request.get(f"{ctx.base}{url}")
        data = r.json() if r.ok else {"state": f"http {r.status}"}
        if data.get("state") not in ("running",):
            return data
        page.wait_for_timeout(1000)
    return {"state": "timeout"}


def api(page: Page, ctx: Ctx, method: str, path: str, **kw):
    return getattr(page.request, method.lower())(f"{ctx.base}{path}", **kw)


# ---------- evidência ----------
def evidencia(page: Page, ctx: Ctx, nome: str, full_page: bool = True) -> str:
    nome = re.sub(r"[^a-zA-Z0-9_.-]+", "-", nome)
    path = ctx.evid_dir / f"{ctx.tema}-{ctx.viewport[0]}x{ctx.viewport[1]}-{nome}.png"
    page.screenshot(path=str(path), full_page=full_page)
    return str(path.relative_to(ctx.run_dir))


# ---------- auditoria automática ----------
AUDIT_JS = """
() => {
  const out = {overflow_horizontal: false, imagens_quebradas: [], botoes_sem_nome: [], fora_do_viewport: [],
               texto_cortado: [], inputs_sem_label: [], controles_cobertos: []};
  const de = document.scrollingElement || document.documentElement;
  out.overflow_horizontal = de.scrollWidth > de.clientWidth + 2;
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const desc = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : ''));
  for (const img of document.images) {
    if (img.src && img.complete && img.naturalWidth === 0 && vis(img)) out.imagens_quebradas.push(img.getAttribute('src').slice(0, 120));
  }
  for (const b of document.querySelectorAll('button, a[href], [role=button]')) {
    if (!vis(b)) continue;
    const nome = (b.getAttribute('aria-label') || b.getAttribute('title') || b.textContent || '').trim();
    if (!nome) out.botoes_sem_nome.push(desc(b));
  }
  for (const i of document.querySelectorAll('input:not([type=hidden]):not([type=file]), select, textarea')) {
    if (!vis(i)) continue;
    const ok = i.id && document.querySelector(`label[for="${CSS.escape(i.id)}"]`) || i.closest('label') ||
      i.getAttribute('aria-label') || i.getAttribute('aria-labelledby') || i.getAttribute('placeholder') || i.getAttribute('title');
    if (!ok) out.inputs_sem_label.push(desc(i));
  }
  // controle visível cujo centro está coberto por outro elemento (overlay/z-index errado)
  for (const b of document.querySelectorAll('#main button, #main a[href], #main input, #main select, .modal button')) {
    if (!vis(b) || out.controles_cobertos.length >= 10) continue;
    const r = b.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) continue;
    // recortado por ancestral rolável (overflow auto/scroll) = alcançável rolando, não é overlay
    let clipped = false;
    for (let a = b.parentElement; a && a !== document.body; a = a.parentElement) {
      const so = getComputedStyle(a);
      if (/(auto|scroll)/.test(so.overflowY + so.overflowX)) {
        const ar = a.getBoundingClientRect();
        if (cy < ar.top || cy > ar.bottom || cx < ar.left || cx > ar.right) { clipped = true; break; }
      }
    }
    if (clipped) continue;
    const top = document.elementFromPoint(cx, cy);
    if (top && top !== b && !b.contains(top) && !top.contains(b) && !(b.closest('label') && b.closest('label').contains(top)))
      out.controles_cobertos.push(desc(b) + ' coberto por ' + desc(top));
  }
  const W = innerWidth;
  for (const el of document.querySelectorAll('#main *, .topbar *, .sidebar *')) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > W + 2 && r.left < W && out.fora_do_viewport.length < 15) out.fora_do_viewport.push(desc(el) + ` (right=${Math.round(r.right)} > ${W})`);
    const s = getComputedStyle(el);
    if ((s.overflow === 'hidden' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 2 &&
        el.children.length === 0 && (el.textContent || '').trim().length > 0 && out.texto_cortado.length < 15)
      out.texto_cortado.push(desc(el) + ': ' + (el.textContent || '').trim().slice(0, 40));
  }
  return out;
}
"""


def auditar_visual(page: Page) -> dict:
    return page.evaluate(AUDIT_JS)


def problemas_visuais(audit: dict) -> list[str]:
    """Lista legível dos achados que valem apontamento (texto cortado com ellipsis é só aviso)."""
    out: list[str] = []
    if audit.get("overflow_horizontal"):
        out.append("página com rolagem horizontal (overflow)")
    if audit.get("imagens_quebradas"):
        out.append(f"{len(audit['imagens_quebradas'])} imagem(ns) quebrada(s): {audit['imagens_quebradas'][:3]}")
    if audit.get("botoes_sem_nome"):
        out.append(f"{len(audit['botoes_sem_nome'])} botão(ões) sem nome acessível: {audit['botoes_sem_nome'][:5]}")
    if audit.get("fora_do_viewport"):
        out.append(f"elementos além da borda direita: {audit['fora_do_viewport'][:3]}")
    if audit.get("inputs_sem_label"):
        out.append(f"{len(audit['inputs_sem_label'])} campo(s) sem rótulo: {audit['inputs_sem_label'][:5]}")
    if audit.get("controles_cobertos"):
        out.append(f"{len(audit['controles_cobertos'])} controle(s) coberto(s) por overlay: {audit['controles_cobertos'][:3]}")
    return out


def timer_orfao(page: Page, ctx: Ctx, tela_de: str, tela_para: str, janela_ms: int = 6000) -> list[str]:
    """Sai de `tela_de` para `tela_para` e conta requests da tela anterior na janela (smoke_ui)."""
    assert page is not None
    abrir_tela(page, ctx, tela_de)
    page.wait_for_timeout(2000)
    abrir_tela(page, ctx, tela_para)
    page.wait_for_timeout(1200)
    vistos: list[str] = []
    page.on("request", lambda r: vistos.append(r.url.replace(ctx.base, "")))
    page.wait_for_timeout(janela_ms)
    return sorted({u for u in vistos if f"/{tela_de}/" in u and f"/{tela_para}/" not in u})


# ---------- utilidades de disco ----------
def arquivos(root: Path, glob: str = "**/*") -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.glob(glob) if p.is_file())


def upload(page: Page, seletor: str, *paths: Path) -> None:
    page.set_input_files(seletor, [str(p) for p in paths])


def png_temp(ctx: Ctx, nome: str, color=(30, 120, 200), size=(640, 400), unico: bool = True) -> Path:
    """PNG de fixture. `unico=True` (padrão) grava um texto com timestamp na imagem: o `ingest`
    deduplica por hash do conteúdo, então dois uploads "iguais" viriam como `added=0`."""
    from PIL import Image, ImageDraw
    d = ctx.run_dir / "fixtures"
    d.mkdir(exist_ok=True)
    p = d / f"{nome}.png"
    if unico or not p.exists():
        img = Image.new("RGB", size, color)
        if unico:
            ImageDraw.Draw(img).text((10, 10), f"{nome} {time.time_ns()}", fill=(255, 255, 255))
        img.save(p, "PNG")
    return p


def plantar_download(ctx: Ctx, nome: str = "qa-download", **kw) -> Path:
    """Copia um PNG único para a pasta Downloads da rodada (`STUDIO_DOWNLOADS`)."""
    import shutil
    src = png_temp(ctx, nome, **kw)
    dest = ctx.downloads_dir / f"{nome}-{time.time_ns()}.png"
    shutil.copy(src, dest)
    return dest


def mp4_temp(ctx: Ctx, nome: str, seconds: float = 2, unico: bool = False) -> Path:
    """MP4 sintético. `unico=True` gera um arquivo novo (nome com timestamp) — o `ingest` deduplica
    por hash, então reimportar o mesmo arquivo devolve `added=0`."""
    import subprocess
    d = ctx.run_dir / "fixtures"
    d.mkdir(exist_ok=True)
    p = d / (f"{nome}-{time.time_ns()}.mp4" if unico else f"{nome}.mp4")
    if not p.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(p)], check=True)
    return p


def mp3_temp(ctx: Ctx, nome: str, seconds: float = 3, unico: bool = False) -> Path:
    """MP3 sintético; `unico=True` como em `mp4_temp` (a frequência varia para o hash mudar)."""
    import subprocess
    d = ctx.run_dir / "fixtures"
    d.mkdir(exist_ok=True)
    p = d / (f"{nome}-{time.time_ns()}.mp3" if unico else f"{nome}.mp3")
    if unico:
        seconds = seconds + (time.time_ns() % 7) / 10
    if not p.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
                        str(p)], check=True)
    return p


def modal_com(page: Page, seletor: str, timeout_ms: int = TIMEOUT_MS):
    """Modal (possivelmente empilhado) que contém `seletor` — ex.: `.cost-sheet` do modal de custo."""
    page.wait_for_selector(f".modal[role=dialog] {seletor}", timeout=timeout_ms)
    return page.locator(f".modal[role=dialog]:has({seletor})").last


def confirmar_custo(page: Page, aceitar: bool = True, timeout_ms: int = TIMEOUT_MS) -> str:
    """Modal de custo (`ui.confirmCost`): devolve o texto e clica em confirmar (primary) ou cancelar."""
    m = modal_com(page, ".cost-sheet, .modal-actions", timeout_ms)
    texto = (m.text_content() or "").strip()
    botoes = m.locator(".modal-actions button")
    alvo = botoes.filter(has_not_text="Cancelar").last if aceitar else botoes.filter(has_text="Cancelar").first
    if not alvo.count():
        alvo = botoes.last if aceitar else botoes.first
    alvo.click()
    page.wait_for_timeout(300)
    return texto


def limpar_toast(page: Page) -> None:
    """Esconde o toast atual para o próximo `esperar_toast` não ler o anterior (toast dura ~3 s)."""
    page.evaluate("() => { const t = document.querySelector('#toast'); if (t) { t.textContent = ''; t.classList.add('hidden'); } }")


class capturar_popup:
    """Captura a aba aberta por `window.open` e a fecha ao sair.

        with H.capturar_popup(page) as pop: page.click("#sbRender")
        pop.url  # URL da aba aberta
    """

    def __init__(self, page: Page, timeout_ms: int = TIMEOUT_MS) -> None:
        self.page, self.timeout_ms, self.url, self._ctx, self._nova = page, timeout_ms, "", None, None

    def __enter__(self):
        self._ctx = self.page.context.expect_page(timeout=self.timeout_ms)
        self._ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._ctx.__exit__(exc_type, exc, tb)
            self._nova = self._ctx.value
            self.url = self._nova.url
            self._nova.close()
        except Exception:  # noqa: BLE001 — sem popup: url fica vazia
            self.url = ""
        return False


def observar_progresso(page: Page) -> None:
    """Instala um observador que registra se um modal de progresso apareceu (mesmo que se feche
    sozinho em < 1 s). Ler com `progresso_visto(page)`."""
    page.evaluate("""() => { window.__qaProg = window.__qaProg || {visto: false, passos: []};
      const obs = new MutationObserver(() => { const s = document.querySelector('.modal[role=dialog] .prog-steps');
        if (s) { window.__qaProg.visto = true; window.__qaProg.passos = [...s.querySelectorAll('li')].map(l => l.textContent); } });
      obs.observe(document.body, {childList: true, subtree: true}); }""")


def progresso_visto(page: Page) -> dict:
    return page.evaluate("() => window.__qaProg || {visto: false, passos: []}")


def soltar_arquivos(page: Page, seletor: str, *paths: Path) -> None:
    """Simula drag&drop de arquivos numa zona de drop (DataTransfer com File real)."""
    import base64
    import mimetypes
    files = [{"name": p.name, "type": mimetypes.guess_type(p.name)[0] or "application/octet-stream",
              "b64": base64.b64encode(Path(p).read_bytes()).decode()} for p in paths]
    page.evaluate("""([sel, files]) => {
      const el = document.querySelector(sel);
      const dt = new DataTransfer();
      for (const f of files) {
        const bin = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
        dt.items.add(new File([bin], f.name, {type: f.type}));
      }
      for (const type of ['dragenter', 'dragover', 'drop']) {
        el.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt}));
      }
    }""", [seletor, files])
    page.wait_for_timeout(500)


def arquivo_invalido(ctx: Ctx, nome: str = "invalido", ext: str = "png") -> Path:
    """Arquivo com extensão de mídia mas conteúdo lixo (testa rejeição amigável de upload)."""
    d = ctx.run_dir / "fixtures"
    d.mkdir(exist_ok=True)
    p = d / f"{nome}.{ext}"
    p.write_bytes(b"isto nao e uma midia " + str(time.time_ns()).encode())
    return p


def retrato(root: Path, *globs: str) -> dict[str, bytes]:
    """Guarda o conteúdo dos arquivos que casam com `globs` (relativos a `root`) para restaurar
    depois de um caso que mexe no seed: `r = H.retrato(ctx.projeto(pid), "animate/**/*")`."""
    out: dict[str, bytes] = {}
    for g in globs or ("**/*",):
        for p in root.glob(g):
            if p.is_file():
                out[str(p.relative_to(root))] = p.read_bytes()
    return out


def restaurar(root: Path, foto: dict[str, bytes], *globs: str) -> None:
    """Volta os arquivos ao retrato: regrava os guardados e apaga os que nasceram depois (nos globs)."""
    for g in globs or ("**/*",):
        for p in root.glob(g):
            if p.is_file() and str(p.relative_to(root)) not in foto:
                p.unlink()
    for rel, data in foto.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def elemento_no_ponto(page: Page, seletor: str) -> str:
    """Descrição do elemento que receberia o clique no centro de `seletor` (diagnóstico de overlay)."""
    return page.evaluate(r"""sel => { const b = document.querySelector(sel); if (!b) return 'ausente';
      const r = b.getBoundingClientRect(); const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (!t) return 'nada'; if (t === b || b.contains(t)) return 'ok';
      return t.tagName.toLowerCase() + (t.id ? '#' + t.id : '') + (t.className ? '.' + String(t.className).trim().split(/\s+/).slice(0, 2).join('.') : ''); }""", seletor)


def arrastar(page: Page, origem: str | tuple[float, float], destino: str | tuple[float, float], passos: int = 12) -> None:
    """Drag com o ponteiro (timeline, resizers, bounding box). Origem/destino: seletor ou (x, y)."""
    def ponto(alvo):
        if isinstance(alvo, str):
            r = page.locator(alvo).first.bounding_box()
            return (r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
        return alvo
    x0, y0 = ponto(origem)
    x1, y1 = ponto(destino)
    page.mouse.move(x0, y0)
    page.mouse.down()
    for i in range(1, passos + 1):
        page.mouse.move(x0 + (x1 - x0) * i / passos, y0 + (y1 - y0) * i / passos)
        page.wait_for_timeout(20)
    page.mouse.up()
    page.wait_for_timeout(200)


def esperar_disco(cond: Callable[[], bool], timeout_s: float = 10, page: Page | None = None) -> bool:
    """Espera um efeito assíncrono em disco (autosave com debounce, job que escreve arquivo)."""
    fim = time.time() + timeout_s
    while time.time() < fim:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001 — arquivo ainda pela metade
            pass
        if page is not None:
            page.wait_for_timeout(200)
        else:
            time.sleep(0.2)
    return False
