"""Coleta de referências no Pinterest via Playwright (sessão do próprio usuário).

Aviso: automatizar o Pinterest contraria os termos de uso dele. Este módulo roda em
ritmo humano (pausas aleatórias), com teto de imagens por busca, e usa um perfil de
navegador persistente do usuário. Use de preferência uma conta secundária.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote_plus, unquote, urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright

from ..config import PINTEREST_PROFILE

PIN_IMG_RE = re.compile(r"https://i\.pinimg\.com/(\d+x|originals)/")
SIZES_FALLBACK = ["originals", "736x", "564x", "474x"]

#: `[extensão]` (Wave 9) — `source` das candidatas trazidas por URL. A galeria, os filtros por fonte
#: e o `select` da etapa 1 tratam esta fonte como qualquer outra: o schema `Candidate` não muda.
SOURCE_URL = "url"
#: `term` de um pin avulso (um pin não tem slug de board de onde derivar um termo útil).
URL_TERM = "url"
#: Primeiros segmentos que o Pinterest usa em rotas próprias — nenhum deles é nome de usuário, então
#: uma URL que comece por um deles nunca é board. Lista curta e explícita de propósito (o risco de
#: rejeitar board legítimo é menor que o de tratar uma rota do site como board).
BOARD_RESERVED = {"pin", "search", "login", "ideas", "settings", "today", "videos"}
#: Mensagem única do 422: mostra os DOIS formatos aceitos para o usuário se autocorrigir sozinho.
IMPORT_URL_HELP = (
    "URL não reconhecida. Cole o link de um pin (https://www.pinterest.com/pin/<id>/) ou de um "
    "board (https://www.pinterest.com/<usuario>/<board>/) do Pinterest. Links encurtados (pin.it) "
    "não são aceitos: abra o pin no navegador e copie a URL completa da barra de endereços."
)


@dataclass
class Candidate:
    id: str
    source: str
    term: str
    url: str                 # imagem em maior resolução encontrada
    pin_url: Optional[str]
    alt: str
    file: Optional[str] = None
    thumb: Optional[str] = None
    width: int = 0
    height: int = 0
    selected: bool = False
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ImportTarget:
    """`[extensão]` O que uma URL colada pelo usuário aponta, já classificado e normalizado."""
    kind: str                # "pin" | "board"
    url: str                 # URL canônica usada na navegação
    term: str                # `Candidate.term` derivado (slug do board, ou "url" para pin avulso)


class PinUnavailable(Exception):
    """Pin sem nenhuma imagem acessível: privado, removido ou atrás do login.

    Erro de negócio (mensagem vai crua para o job), ao contrário das falhas inesperadas do
    scraper, que o serviço reporta no formato `TypeName: msg`.

    **Não** herda de `RuntimeError` de propósito: a rota traduz `RuntimeError` em 409 ("já existe
    uma busca em andamento"). Hoje esta exceção só nasce dentro da thread do job, mas se um dia a
    checagem do pin subir para o trecho síncrono, herdar de `RuntimeError` faria "pin inacessível"
    responder 409 — um erro de contrato silencioso.
    """


def _board_term(slug: str) -> str:
    """Slug do board vira termo legível: `campanhas-energetico` → `campanhas energetico`."""
    return " ".join(unquote(slug).replace("-", " ").split()) or URL_TERM


def classify_url(raw: str) -> ImportTarget:
    """`[extensão]` Classifica a URL colada como pin ou board do Pinterest. Função pura.

    Aceita `https://<sub>.pinterest.com/pin/<id>/` (pin) e `https://<sub>.pinterest.com/<usuario>/
    <board>/` (board). Uma URL de **seção** de board (`/<usuario>/<board>/<secao>/`) é tratada como
    board comum: a página rola do mesmo jeito e uma matriz de casos separada não agregaria nada.
    Qualquer outra coisa — inclusive encurtador `pin.it` e host de terceiro — levanta `ValueError`
    com `IMPORT_URL_HELP`, que a rota transforma em 422 sem criar job nenhum.
    """
    parsed = urlparse((raw or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not (host == "pinterest.com" or host.endswith(".pinterest.com")):
        raise ValueError(IMPORT_URL_HELP)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) == 2 and parts[0] == "pin":
        return ImportTarget("pin", f"https://www.pinterest.com/pin/{parts[1]}/", URL_TERM)
    if 2 <= len(parts) <= 3 and not any(p in BOARD_RESERVED for p in parts):
        return ImportTarget("board", "https://www.pinterest.com/" + "/".join(parts) + "/", _board_term(parts[1]))
    raise ValueError(IMPORT_URL_HELP)


def _human_pause(a: float = 1.5, b: float = 3.5) -> None:
    time.sleep(random.uniform(a, b))


def _launch(pw, headless: bool) -> BrowserContext:
    PINTEREST_PROFILE.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(PINTEREST_PROFILE),
        headless=headless,
        viewport={"width": 1400, "height": 1000},
        locale="pt-BR",
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        args=["--disable-blink-features=AutomationControlled"],
    )


def is_logged_in(ctx: BrowserContext) -> bool:
    return any(c["name"] == "_auth" and c["value"] == "1" for c in ctx.cookies("https://www.pinterest.com"))


def login(timeout_s: int = 300) -> bool:
    """Abre o navegador COM JANELA para o usuário logar; espera o cookie de sessão."""
    with sync_playwright() as pw:
        ctx = _launch(pw, headless=False)
        page = ctx.new_page()
        page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded")
        deadline = time.time() + timeout_s
        ok = False
        while time.time() < deadline:
            if is_logged_in(ctx):
                ok = True
                break
            time.sleep(3)
        ctx.close()
        return ok


def _best_url(src: str) -> str:
    return PIN_IMG_RE.sub("https://i.pinimg.com/originals/", src)


def _collect_from_page(page: Page) -> list[dict]:
    return page.evaluate(
        """() => {
          const out = [];
          for (const img of document.querySelectorAll('img[src*="pinimg.com"]')) {
            // o link do pin pode ser ancestral ou irmão dentro do card; tentamos os dois
            let a = img.closest('a[href*="/pin/"]');
            if (!a) { const card = img.closest('[data-test-id="pin"], [data-grid-item]'); a = card && card.querySelector('a[href*="/pin/"]'); }
            let pin = a ? a.getAttribute('href') : null;
            if (pin && pin.startsWith('http')) pin = new URL(pin).pathname;
            out.push({src: img.currentSrc || img.src, alt: img.alt || '', pin});
          }
          return out;
        }"""
    )


def _collect_grid(page: Page, seen_urls: set[str], limit: int) -> dict[str, dict]:
    """Rola uma grade de pins (busca ou board) em ritmo humano até `limit` ou 4 rodadas ociosas.

    Devolve `{url_em_maior_resolucao: item_do_DOM}`. O critério de parada por ociosidade é o que
    impede o crawler de descer um board infinito (ADR-005).
    """
    found: dict[str, dict] = {}
    idle_rounds = 0
    while len(found) < limit and idle_rounds < 4:
        before = len(found)
        for item in _collect_from_page(page):
            src = item.get("src") or ""
            if not PIN_IMG_RE.match(src):
                continue
            best = _best_url(src)
            if best in seen_urls or best in found:
                continue
            found[best] = item
            if len(found) >= limit:
                break
        idle_rounds = idle_rounds + 1 if len(found) == before else 0
        page.mouse.wheel(0, random.randint(900, 1600))
        _human_pause()
    return found


def _pin_main_image(page: Page) -> Optional[dict]:
    """A imagem principal da página de UM pin: a maior `pinimg` renderizada, ou o `og:image`.

    Seletor genérico de propósito (mesma estratégia resiliente do search): o DOM do Pinterest muda
    com frequência, mas a imagem do pin é sempre a maior da página.
    """
    return page.evaluate(
        """() => {
          let best = null, area = 0;
          for (const img of document.querySelectorAll('img[src*="pinimg.com"]')) {
            const a = (img.naturalWidth || img.width || 0) * (img.naturalHeight || img.height || 0);
            if (a > area) { area = a; best = {src: img.currentSrc || img.src, alt: img.alt || ''}; }
          }
          if (best) return best;
          const og = document.querySelector('meta[property="og:image"]');
          const src = og && og.getAttribute('content');
          return src && src.includes('pinimg.com') ? {src, alt: document.title || ''} : null;
        }"""
    )


def import_url(
    url: str,
    out_dir: Path,
    max_pins: int = 30,
    headless: bool = True,
    progress: Optional[Callable[[dict], None]] = None,
) -> list[Candidate]:
    """`[extensão]` Importa para as candidatas o pin OU o board apontado por `url`.

    A aula 009 ensina a buscar por termos; trazer um link que o usuário já tem é extensão do Studio
    (ADR-004) que produz o MESMO artefato da etapa: candidatas em `refs/candidates/`.

    Aviso: automatizar o Pinterest contraria os termos de uso dele. Como o `search`, esta função
    roda com a sessão do próprio usuário, em ritmo humano e com teto de imagens (ADR-005) — prefira
    uma conta secundária. Board respeita `max_pins`; pin baixa exatamente uma imagem.

    Dedupe em três camadas: URL já conhecida (não rebaixa), SHA-1 dentro da rodada (`_download`) e
    SHA-1 contra as candidatas já gravadas (`known_ids`) — reimportar o mesmo conteúdo adiciona 0.
    """
    target = classify_url(url)
    out_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir = out_dir / "thumbs"
    thumbs_dir.mkdir(exist_ok=True)

    def report(**kw):
        if progress:
            progress(kw)

    existing = load_candidates(out_dir)
    seen_urls = {c.url for c in existing}
    seen_hashes: set[str] = set()
    known_ids = {c.id for c in existing}
    results: list[Candidate] = list(existing)

    with sync_playwright() as pw:
        ctx = _launch(pw, headless=headless)
        try:
            report(stage="start", logged_in=is_logged_in(ctx))
            page = ctx.new_page()
            page.goto(target.url, wait_until="domcontentloaded")
            _human_pause(2.5, 4.5)
            if target.kind == "pin":
                item = _pin_main_image(page)
                src = (item or {}).get("src") or ""
                if not PIN_IMG_RE.match(src):
                    # 0 imagens na página de um pin não é "board vazio": o pin não abriu.
                    raise PinUnavailable("pin inacessível (privado, removido ou exige login)")
                found = {_best_url(src): {"src": src, "alt": item.get("alt") or "",
                                          "pin": urlparse(target.url).path}}
            else:
                found = _collect_grid(page, seen_urls, max(1, max_pins))
            report(stage="download", term=target.term, count=len(found))
            for best, item in found.items():
                cand = _download(ctx, best, item, target.term, out_dir, thumbs_dir, seen_hashes,
                                 source=SOURCE_URL)
                if cand and cand.id not in known_ids:
                    cand.extra["import_url"] = url        # URL original, para auditoria
                    known_ids.add(cand.id)
                    seen_urls.add(best)
                    results.append(cand)
                    save_candidates(out_dir, results)
                    report(stage="saved", term=target.term, id=cand.id, total=len(results))
                _human_pause(0.3, 0.9)
        finally:
            ctx.close()
    save_candidates(out_dir, results)
    report(stage="done", total=len(results))
    return results


def search(
    terms: list[str],
    out_dir: Path,
    max_per_term: int = 30,
    headless: bool = True,
    progress: Optional[Callable[[dict], None]] = None,
) -> list[Candidate]:
    """Busca cada termo, rola a página em ritmo humano, baixa as imagens em maior resolução.

    Retorna a lista de candidatas (também gravada em out_dir/candidates.json).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir = out_dir / "thumbs"
    thumbs_dir.mkdir(exist_ok=True)
    def report(**kw):
        if progress:
            progress(kw)

    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    existing = load_candidates(out_dir)
    for c in existing:
        seen_urls.add(c.url)
    results: list[Candidate] = list(existing)

    with sync_playwright() as pw:
        ctx = _launch(pw, headless=headless)
        logged = is_logged_in(ctx)
        report(stage="start", logged_in=logged)
        page = ctx.new_page()
        for ti, term in enumerate(terms):
            report(stage="term", term=term, index=ti, n_terms=len(terms))
            page.goto(f"https://www.pinterest.com/search/pins/?q={quote_plus(term)}", wait_until="domcontentloaded")
            _human_pause(2.5, 4.5)
            found = _collect_grid(page, seen_urls, max_per_term)
            report(stage="download", term=term, count=len(found))
            for best, item in found.items():
                cand = _download(ctx, best, item, term, out_dir, thumbs_dir, seen_hashes)
                if cand:
                    seen_urls.add(best)
                    results.append(cand)
                    save_candidates(out_dir, results)
                    report(stage="saved", term=term, id=cand.id, total=len(results))
                _human_pause(0.3, 0.9)
        ctx.close()
    save_candidates(out_dir, results)
    report(stage="done", total=len(results))
    return results


def _download(ctx: BrowserContext, best: str, item: dict, term: str, out_dir: Path,
              thumbs_dir: Path, seen_hashes: set[str], source: str = "pinterest") -> Optional[Candidate]:
    from PIL import Image
    data = None
    used = None
    for size in SIZES_FALLBACK:
        url = re.sub(r"/(originals|\d+x)/", f"/{size}/", best, count=1)
        try:
            r = ctx.request.get(url, timeout=20000)
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                data, used = r.body(), url
                break
        except Exception:
            continue
    if not data:
        return None
    h = hashlib.sha1(data).hexdigest()
    if h in seen_hashes:
        return None
    seen_hashes.add(h)
    cid = h[:12]
    ext = ".jpg"
    fpath = out_dir / f"{cid}{ext}"
    fpath.write_bytes(data)
    w = hgt = 0
    try:
        with Image.open(fpath) as im:
            w, hgt = im.size
            im = im.convert("RGB")
            im.thumbnail((480, 480))
            im.save(thumbs_dir / f"{cid}.jpg", "JPEG", quality=82)
    except Exception:
        pass
    pin = item.get("pin")
    return Candidate(
        id=cid, source=source, term=term, url=used or best,
        pin_url=f"https://www.pinterest.com{pin}" if pin else None,
        alt=(item.get("alt") or "")[:300], file=fpath.name, thumb=f"thumbs/{cid}.jpg",
        width=w, height=hgt,
    )


def load_candidates(out_dir: Path) -> list[Candidate]:
    f = out_dir / "candidates.json"
    if not f.exists():
        return []
    return [Candidate(**c) for c in json.loads(f.read_text())]


def save_candidates(out_dir: Path, cands: list[Candidate]) -> None:
    (out_dir / "candidates.json").write_text(json.dumps([asdict(c) for c in cands], ensure_ascii=False, indent=1))
