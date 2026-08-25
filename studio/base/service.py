"""Etapa 3 — Imagem base (aula 009), em "modo UI".

A aula manda, para cada referência escolhida na etapa 1: pedir "o produto na exata mesma
situação da imagem de referência, com o mood da campanha" (aba nova, sem viés), escolher a
melhor, trocar o rótulo pela marca própria com o Nano Banana (uma instrução por vez) e fazer
upscale 2x High Fidelity. Aqui isso vira:

1. `prompts()` monta os prompts da aula (em inglês) a partir de `refs/`, `mood/` e `project.json`;
2. o usuário gera na UI da Higgsfield (ilimitado) — ou via CLI, pagando créditos — e importa
   (upload, pasta Downloads, histórico do CLI) dizendo o `kind` (situation|label|upscale);
3. `select()` marca a candidata escolhida, copia para `base/base_final.png` e regrava `base.md`.

O campo `brand` (nome/descrição do rótulo) é `[extensão]` aprovada na wave 1: sem ele não há
como escrever o prompt de troca de rótulo que a aula dita.
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image

from .. import higgsfield as hf
from ..common import ingest
from ..common.jobs import JobRegistry
from ..refs.service import project_dir

log = logging.getLogger("studio.base")

STEP = "base"
KINDS = ("situation", "label", "upscale")
RANK = {"situation": 0, "label": 1, "upscale": 2}
FINAL_REL = "base/base_final.png"

# IDs sugeridos pelo plano-higgsfield; o catálogo vivo ainda não pôde ser conferido (CLI sem
# login), por isso todo request aceita `model` e sobrescreve estes defaults.
DEFAULT_MODEL = "nano_banana_2"
DEFAULT_MODEL_LABEL = "nano_banana_2"
DEFAULT_MODEL_UPSCALE = "bytedance_image_upscale"
DEFAULT_MODELS = {"situation": DEFAULT_MODEL, "label": DEFAULT_MODEL_LABEL, "upscale": DEFAULT_MODEL_UPSCALE}

MOOD_REFS_MAX = 3          # a aula anexa a referência + algumas imagens do mood, não o mood inteiro
NO_PEOPLE = "No people unless they appear in the reference image."

_registry = JobRegistry()


# ---------- insumos das etapas 1 e 2 ----------
def _meta(root: Path) -> dict:
    f = root / "project.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _product(root: Path) -> str:
    meta = _meta(root)
    return (meta.get("product") or meta.get("name") or "the product").strip()


def selected_refs(root: Path) -> list[dict]:
    """Referências escolhidas na etapa 1 que têm arquivo em `refs/brainstorming/`."""
    f = root / "refs" / "candidates" / "candidates.json"
    if not f.exists():
        return []
    out = []
    for c in json.loads(f.read_text()):
        if not c.get("selected"):
            continue
        p = root / "refs" / "brainstorming" / f"{c['id']}.jpg"
        if p.exists():
            out.append({"ref_id": c["id"], "file": f"refs/brainstorming/{c['id']}.jpg", "path": p,
                        "term": c.get("term") or ""})
    return out


def _palette(root: Path) -> dict | None:
    f = root / "mood" / "palette.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError:
        return None
    colors = [c for c in (data.get("colors") or []) if isinstance(c, str)]
    note = (data.get("note") or "").strip()
    if not colors and not note:
        return None      # a etapa 2 ainda não produziu mood de verdade
    return {"colors": colors, "note": note}


def mood_files(root: Path) -> list[str]:
    d = root / "mood" / "selected"
    if not d.exists():
        return []
    return [f"mood/selected/{p.name}" for p in sorted(d.iterdir())
            if p.is_file() and p.suffix.lower() in ingest.MEDIA_EXT["image"]]


# ---------- marca (extensão aprovada) ----------
def brand_get(pid: str) -> dict:
    f = project_dir(pid) / STEP / "brand.json"
    if not f.exists():
        return {"name": "", "description": ""}
    data = json.loads(f.read_text())
    return {"name": data.get("name", ""), "description": data.get("description", "")}


def brand_set(pid: str, name: str, description: str = "") -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Informe o nome da marca para escrever o prompt de troca de rótulo (aula 009).")
    root = project_dir(pid)
    (root / STEP).mkdir(parents=True, exist_ok=True)
    brand = {"name": name, "description": (description or "").strip()}
    (root / STEP / "brand.json").write_text(json.dumps(brand, ensure_ascii=False, indent=1))
    if _chain(load(pid))["final"]:
        _write_md(root)      # o base.md carrega a marca; regrava quando ela muda
    return brand


# ---------- prompts da aula (em inglês, aula 007) ----------
def _mood_clause(pal: dict) -> str:
    parts = []
    if pal["note"]:
        parts.append(pal["note"])
    if pal["colors"]:
        parts.append("palette " + " ".join(pal["colors"][:6]))
    return ", ".join(parts)


def situation_prompt(product: str, pal: dict) -> str:
    return (f"The product ({product}) in the exact same situation as the reference image, "
            f"with the campaign mood: {_mood_clause(pal)}. {NO_PEOPLE} Photorealistic.")


def no_bias_prompt(product: str) -> str:
    """Aula 009: em uma aba nova, sem histórico, pedir o prompt da imagem idêntica — sem viés."""
    return (f"Write the prompt for an image identical to this one, but the {product} is the subject. "
            f"{NO_PEOPLE}")


def label_prompt(brand: dict) -> str | None:
    if not brand.get("name"):
        return None
    desc = brand.get("description") or ""
    return ("Replace the product label with the brand: " + brand["name"]
            + (f", {desc}" if desc else "")
            + ". Keep the product colors and everything else identical, realistic.")


def prompts(pid: str, model: str | None = None) -> dict:
    """Prompts determinísticos da aula 009: um de situação por referência escolhida (+ variante
    sem viés), o de troca de rótulo (quando há marca) e a instrução de upscale."""
    root = project_dir(pid)
    refs = selected_refs(root)
    if not refs:
        raise ValueError("Volte à etapa 1 e escolha ao menos uma referência (ela vira o 'brainstorming').")
    pal = _palette(root)
    if pal is None:
        raise ValueError("Volte à etapa 2 e salve o mood da campanha (mood/palette.json).")
    product = _product(root)
    brand = brand_get(pid)
    lp = label_prompt(brand)
    return {
        "model": model or DEFAULT_MODEL,
        "ui_hint": ("Abra uma aba nova na Higgsfield (sem histórico), anexe a referência e 1 a 3 imagens do "
                    "mood, e cole o prompt. Gere, escolha a melhor e importe aqui como 'situação'."),
        "aspect_ratio": "16:9",
        "product": product,
        "palette": pal,
        "mood_files": mood_files(root),
        "refs": [{"ref_id": r["ref_id"], "file": r["file"],
                  "prompt": situation_prompt(product, pal),
                  "prompt_no_bias": no_bias_prompt(product)} for r in refs],
        "label_prompt": lp,
        "label_prompt_ready": lp is not None,
        "upscale_hint": "Upscale 2x High Fidelity V2 na UI (ou modelo bytedance_image_upscale via CLI).",
    }


# ---------- candidatas ----------
def _normalize(cands: list[dict], kind: str | None = None, ref_id: str | None = None,
               new_ids: set[str] | None = None) -> list[dict]:
    """Completa o que o `ingest` não sabe da etapa: `kind` da aula e `ref_id`, e deixa
    `file`/`thumb` relativos ao projeto (schema fixado na wave 1)."""
    for c in cands:
        if new_ids is not None and c["id"] in new_ids:
            if kind:
                c["kind"] = kind
            c["ref_id"] = ref_id
        if c.get("kind") not in KINDS:
            c["kind"] = kind or "situation"
        c.setdefault("ref_id", None)
        if c.get("file") and not str(c["file"]).startswith(f"{STEP}/"):
            c["file"] = f"{STEP}/candidates/{c['file']}"
        if c.get("thumb") and not str(c["thumb"]).startswith(f"{STEP}/"):
            c["thumb"] = f"{STEP}/candidates/{c['thumb']}"
    return cands


def load(pid: str) -> list[dict]:
    return _normalize(ingest.load_candidates(project_dir(pid), STEP))


def _finish_import(root: Path, before: set[str], kind: str, ref_id: str | None) -> None:
    cands = ingest.load_candidates(root, STEP)
    new_ids = {c["id"] for c in cands} - before
    ingest.save_candidates(root, STEP, _normalize(cands, kind, ref_id, new_ids))


def _check_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"kind inválido: {kind} (use situation, label ou upscale)")
    return kind


def import_upload(pid: str, files: list[tuple[str, bytes]], kind: str = "situation",
                  ref_id: str | None = None, prompt: str = "") -> dict:
    _check_kind(kind)
    root = project_dir(pid)
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    res = ingest.import_upload(root, STEP, files, prompt)
    _finish_import(root, before, kind, ref_id)
    return res


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40,
                     kind: str = "situation", ref_id: str | None = None, prompt: str = "") -> dict:
    _check_kind(kind)
    root = project_dir(pid)
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    res = ingest.import_downloads(root, STEP, folder, since_minutes, limit, prompt=prompt)
    _finish_import(root, before, kind, ref_id)
    return res


def import_history(pid: str, kind: str = "situation", ref_id: str | None = None, size: int = 50,
                   prompt_filter: str | None = None) -> dict:
    _check_kind(kind)
    root = project_dir(pid)
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    res = ingest.import_history(root, STEP, "image", size, prompt_filter)
    _finish_import(root, before, kind, ref_id)
    return res


# ---------- seleção, base_final.png e base.md ----------
def _chain(cands: list[dict]) -> dict:
    chain: dict = {k: None for k in KINDS}
    for c in cands:
        if c.get("selected") and c.get("kind") in KINDS:
            chain[c["kind"]] = c["id"]
    final = next((k for k in reversed(KINDS) if chain[k]), None)
    return {**chain, "final": final}


def _selected(cands: list[dict], kind: str) -> dict | None:
    return next((c for c in cands if c.get("selected") and c.get("kind") == kind), None)


def most_advanced(cands: list[dict]) -> dict | None:
    """A candidata selecionada mais avançada da cadeia: upscale > label > situação."""
    chosen = [c for c in cands if c.get("selected") and c.get("kind") in KINDS]
    return max(chosen, key=lambda c: RANK[c["kind"]]) if chosen else None


def _write_final(root: Path, cand: dict) -> None:
    src = root / cand["file"]
    dst = root / FINAL_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".png":
        shutil.copy2(src, dst)          # cópia byte a byte quando já é PNG
    else:
        with Image.open(src) as im:
            im.convert("RGB").save(dst, "PNG")


def _write_md(root: Path, note: str = "") -> None:
    cands = _normalize(ingest.load_candidates(root, STEP))
    chain = _chain(cands)
    brand = json.loads((root / STEP / "brand.json").read_text()) if (root / STEP / "brand.json").exists() \
        else {"name": "", "description": ""}
    pal = _palette(root) or {"colors": [], "note": ""}
    lines = ["# Imagem base", "", f"Etapa 3 · aula 009 · atualizado em {datetime.now():%Y-%m-%d %H:%M}.", "",
             f"**Produto:** {_product(root)}"]
    if brand.get("name"):
        desc = f" — {brand['description']}" if brand.get("description") else ""
        lines.append(f"**Marca [extensão]:** {brand['name']}{desc}")
    lines += ["", f"**Arquivo final:** `{FINAL_REL}`" if chain["final"] else "**Arquivo final:** ainda não escolhido",
              "", "| Etapa | id | origem | referência | prompt |", "| --- | --- | --- | --- | --- |"]
    rotulo = {"situation": "situação", "label": "rótulo", "upscale": "upscale 2x"}
    for kind in KINDS:
        c = _selected(cands, kind)
        if not c:
            continue
        lines.append(f"| {rotulo[kind]} | `{c['id']}` | {c.get('source', '')} | "
                     f"{c.get('ref_id') or '—'} | {(c.get('prompt') or '').replace('|', '/')[:200]} |")
    if pal["colors"]:
        lines += ["", "**Paleta usada:** " + ", ".join(pal["colors"])]
    if pal["note"]:
        lines += ["", f"**Mood:** {pal['note']}"]
    if note:
        lines += ["", f"**Notas:** {note}"]
    (root / STEP).mkdir(parents=True, exist_ok=True)
    (root / STEP / "base.md").write_text("\n".join(lines) + "\n")


def select(pid: str, cid: str, note: str = "") -> dict:
    """Marca a candidata como escolhida (exclusiva no seu `kind`), regrava `base_final.png` e `base.md`.
    Escolher um passo anterior recomeça a cadeia: as seleções dos passos seguintes caem."""
    root = project_dir(pid)
    cands = load(pid)
    target = next((c for c in cands if c["id"] == cid), None)
    if target is None:
        raise FileNotFoundError(f"candidata não encontrada: {cid}")
    kind = target["kind"] if target.get("kind") in KINDS else "situation"
    for c in cands:
        k = c.get("kind")
        if k == kind:
            c["selected"] = c["id"] == cid
        elif k in KINDS and RANK.get(k, 0) > RANK[kind]:
            c["selected"] = False
    ingest.save_candidates(root, STEP, cands)
    final = most_advanced(cands)
    if final:
        _write_final(root, final)
    _write_md(root, note)
    chain = _chain(cands)
    log.info("base: select pid=%s id=%s kind=%s final=%s", pid, cid, kind, chain["final"])
    return {"final": FINAL_REL if final else None, "kind": final["kind"] if final else None,
            "chain": {k: chain[k] for k in KINDS}}


def final_file(pid: str) -> str | None:
    return FINAL_REL if (project_dir(pid) / FINAL_REL).exists() else None


# ---------- geração via CLI (paga créditos) ----------
def _plan(root: Path, kind: str, ref_ids: list[str] | None, count: int) -> tuple[list[dict], str]:
    """Itens do job (um por chamada ao CLI) + o prompt/instrução que cada um usa."""
    _check_kind(kind)
    cands = _normalize(ingest.load_candidates(root, STEP))
    mood = [str(root / m) for m in mood_files(root)][:MOOD_REFS_MAX]
    if kind == "situation":
        refs = selected_refs(root)
        if ref_ids:
            refs = [r for r in refs if r["ref_id"] in set(ref_ids)]
        if not refs:
            raise ValueError("Nenhuma referência escolhida na etapa 1 com arquivo em refs/brainstorming/.")
        pal = _palette(root)
        if pal is None:
            raise ValueError("Volte à etapa 2 e salve o mood da campanha (mood/palette.json).")
        text = situation_prompt(_product(root), pal)
        return [{"ref_id": r["ref_id"], "prompt": text,
                 "image_references": [str(r["path"]), *mood]} for r in refs], text
    if kind == "label":
        base = _selected(cands, "situation")
        if base is None:
            raise ValueError("Escolha primeiro a melhor imagem de situação (aula 009).")
        text = label_prompt(_brand_from_disk(root))
        if not text:
            raise ValueError("Informe a marca antes de trocar o rótulo (campo 'brand').")
        item = {"ref_id": base.get("ref_id"), "prompt": text,
                "image_references": [str(root / base["file"])]}
        return [dict(item) for _ in range(max(1, count))], text
    src = most_advanced(cands)
    if src is None:
        raise ValueError("Escolha primeiro a imagem que será ampliada (situação ou rótulo).")
    return [{"ref_id": src.get("ref_id"), "prompt": "", "image_references": [str(root / src["file"])]}], ""


def _brand_from_disk(root: Path) -> dict:
    f = root / STEP / "brand.json"
    return json.loads(f.read_text()) if f.exists() else {"name": "", "description": ""}


def estimate_cost(pid: str, kind: str, model: str | None = None, ref_ids: list[str] | None = None,
                  count: int = 1, aspect_ratio: str = "16:9", resolution: str = "2k") -> dict:
    """Estimativa de créditos SEM gerar (a UI mostra e pede `confirm()` antes de gastar)."""
    root = project_dir(pid)
    items, text = _plan(root, kind, ref_ids, count)
    n = len(items) * (count if kind == "situation" else 1)
    model = model or DEFAULT_MODELS[kind]
    params: dict = {}
    if text:
        params["prompt"] = text
    if kind == "situation":     # mesmo corpo que start_generate manda ao CLI
        params.update({"aspect_ratio": aspect_ratio, "resolution": resolution, "count": count})
    raw = hf.cost(model, params)
    per = raw.get("credits")
    total = per * n if isinstance(per, (int, float)) else None
    return {"per_item": per, "count": n, "total": total, "raw": raw}


def start_generate(pid: str, kind: str, model: str | None = None, ref_ids: list[str] | None = None,
                   count: int = 1, aspect_ratio: str = "16:9", resolution: str = "2k") -> dict:
    """Caminho pago: o Studio chama o CLI por item e importa o resultado. Sem retry automático."""
    root = project_dir(pid)
    items, _ = _plan(root, kind, ref_ids, count)
    model = model or DEFAULT_MODELS[kind]

    log.info("base: job início pid=%s kind=%s itens=%s model=%s", pid, kind, len(items), model)

    def run(job: dict) -> None:
        failures = 0
        last = ""
        for i, item in enumerate(items):
            try:
                params: dict = {"image_references": item["image_references"]}
                if item["prompt"]:
                    params["prompt"] = item["prompt"]
                if kind == "situation":
                    params.update({"aspect_ratio": aspect_ratio, "resolution": resolution, "count": count})
                res = hf.generate(model, params)
                added = _ingest_job(root, res, kind, item, model, job)
                job["added"] += added
                job["log"].append(f"[{kind}] ref={item.get('ref_id') or '—'} model={model} "
                                  f"urls={len(res.get('urls') or [])} added={added}")
            except Exception as e:  # noqa: BLE001  — falha de item não derruba o job inteiro
                failures += 1
                last = f"{type(e).__name__}: {e}"[:400]
                job["log"].append(f"erro: {last}")
            job["done"] = i + 1
        log.info("base: job pid=%s kind=%s itens=%s added=%s falhas=%s", pid, kind, len(items), job["added"], failures)
        if failures and failures == len(items):
            raise RuntimeError(last)

    try:
        return _registry.start(pid, len(items), run, kind=kind, model=model)
    except RuntimeError as e:
        raise RuntimeError("Já existe uma geração em andamento para este projeto.") from e


def _ingest_job(root: Path, res: dict, kind: str, item: dict, model: str, job: dict | None = None) -> int:
    """Baixa as URLs do job e registra como candidatas do `kind`. Link expirado é pulado."""
    (root / "jobs").mkdir(parents=True, exist_ok=True)
    jid = res.get("id") or f"{datetime.now():%Y%m%d%H%M%S}"
    (root / "jobs" / f"{STEP}_{jid}.json").write_text(json.dumps(res.get("raw"), ensure_ascii=False, indent=1))
    tmp_dir = root / "jobs" / "_tmp"
    added = 0
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    for url in res.get("urls") or []:
        name = url.split("?")[0].rsplit("/", 1)[-1] or "cli.png"
        tmp = tmp_dir / name
        try:
            hf.download(url, tmp)
            data = tmp.read_bytes()
        except Exception as e:  # noqa: BLE001  — links da Higgsfield expiram
            if job is not None:
                job["log"].append(f"download pulado ({name}): {e}"[:400])
            continue
        finally:
            tmp.unlink(missing_ok=True)
        if ingest.ingest_bytes(root, STEP, data, "cli", name, item["prompt"],
                               {"job_id": res.get("id"), "model": model}):
            added += 1
    _finish_import(root, before, kind, item.get("ref_id"))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return added


def job_status(pid: str) -> dict:
    return _registry.status(pid)
