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
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, BrowserContext, Page

from ..config import PINTEREST_PROFILE

PIN_IMG_RE = re.compile(r"https://i\.pinimg\.com/(\d+x|originals)/")
SIZES_FALLBACK = ["originals", "736x", "564x", "474x"]


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
    report = lambda **kw: progress and progress(kw)

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
            found: dict[str, dict] = {}
            idle_rounds = 0
            while len(found) < max_per_term and idle_rounds < 4:
                before = len(found)
                for item in _collect_from_page(page):
                    src = item.get("src") or ""
                    if not PIN_IMG_RE.match(src):
                        continue
                    best = _best_url(src)
                    if best in seen_urls or best in found:
                        continue
                    found[best] = item
                    if len(found) >= max_per_term:
                        break
                idle_rounds = idle_rounds + 1 if len(found) == before else 0
                page.mouse.wheel(0, random.randint(900, 1600))
                _human_pause()
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
              thumbs_dir: Path, seen_hashes: set[str]) -> Optional[Candidate]:
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
        id=cid, source="pinterest", term=term, url=used or best,
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
