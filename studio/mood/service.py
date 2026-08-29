"""Etapa 2 — Mood board (aula 009).

**A CRIAÇÃO de mood boards migrou para a biblioteca global** (`studio/moodboards/`, ADR-014 que
estende a ADR-013/ADR-007). Decisão do dono do produto (27/08/2026): a etapa 2 da campanha deixou
de criar/curar e passou a **só ESCOLHER** um board da biblioteca e **aplicá-lo à campanha** via
`pull_board()` (copia as imagens do board para `mood/selected/` + `mood.md`/`palette.json`/
`project.vibe`). A tela usa apenas `current()` (mood atual) e `pull_board()`.

Os endpoints/funções de CRIAÇÃO abaixo (`suggest_prompts`, `generate_prompt`, `vibe_*`,
`import_*`, `start_generate`, `select`, …) **continuam existindo** — a biblioteca global usa a
MESMA família de ingest/prompter/paleta e os contratos não podem quebrar — mas **não são mais
chamados pela tela da etapa 2**. Eles são o fluxo da criação, que agora vive na biblioteca.

Fidelidade (auditoria da wave 2, §2): o mood board da aula **tem o produto** — nada de "no product,
no text, no logos" injetado no prompt. "Sem pessoas" é sugestão marcada por padrão, nunca silenciosa.
O texto de aula (achar a vibe pelo sentimento, grid de 4, teto de 8) continua no guia como contexto.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from .. import higgsfield as hf
from ..common import atomic, ingest, prompter, settings
from ..common.jobs import JobRegistry
from ..common.palette import palette as _palette
from ..refs.service import project_dir

DOWNLOADS_DEFAULT = ingest.DOWNLOADS_DEFAULT
IMG_EXT = ingest.MEDIA_EXT["image"]
_registry = JobRegistry()


# ---------- prompts ----------
def _refs_summary(root: Path) -> list[str]:
    """Termos e descrições das referências escolhidas na etapa 1.

    **Não entra no prompt de vibe** (auditoria M4: a aula diz que a vibe "não precisa ter a ver com
    esse tipo de campanha"). Fica disponível para a etapa 3, que trabalha a partir das referências.
    """
    cands = root / "refs" / "candidates" / "candidates.json"
    if not cands.exists():
        return []
    chosen = [c for c in json.loads(cands.read_text()) if c.get("selected")]
    terms = sorted({c["term"] for c in chosen})
    junk = ("salvar pin", "save pin", "pinterest")
    alts = [c["alt"].strip() for c in chosen
            if c.get("alt") and len(c["alt"]) > 25 and not any(j in c["alt"].lower() for j in junk)][:5]
    return terms + alts


#: Fonte única das variações de estilização (M8): `common/prompter.STYLE_VARIANTS`.
_STYLE_VARIANTS = prompter.STYLE_VARIANTS


def refs_terms(pid: str) -> list[str]:
    """Termos/descrições das referências da etapa 1 — usados pela etapa 3 e pelas validações."""
    return _refs_summary(project_dir(pid))


def suggest_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0,
                    no_people: bool = True, explore_prompt: str = "") -> dict:
    """Aula 009: o mood board é UMA vibe — um único prompt de ambiente/luz/cor, gerado em grid de 4.

    `variation` troca só a estilização (o que o instrutor faz ao ajustar o Stylization e regerar
    quando o grid "não pegou a vibe"). `explore_prompt` é o prompt que o usuário copiou do Explore
    ("copiar o prompt dessa pessoa"): quando vem preenchido, ele é a base e só a estilização é
    acrescentada. `no_people` é a única restrição que a aula enuncia — e é opcional.
    Produto na cena, escala e rótulo pertencem à etapa 3 (imagem base).
    """
    root = project_dir(pid)
    meta = json.loads((root / "project.json").read_text())
    brief = {"product": meta.get("product") or "the product", "vibe": meta.get("vibe") or "cinematic",
             "explore_prompt": explore_prompt}
    text = prompter.fallback_template("mood", brief, variation, no_people)["prompt"]
    return {"model": model, "ui_hint": _ui_hint(model), "aspect_ratio": "16:9", "variation": variation,
            "no_people": no_people, "explore_prompt": explore_prompt,
            "prompts": [{"label": "Vibe da campanha", "text": text}]}


# ---------- imagens de vibe + bot de prompts (aula 009: achar a vibe → bot → prompt) ----------
VIBE_STEP = "mood/vibe"
MAX_VIBE_IMAGES = 4


def vibe_images(pid: str) -> list[dict]:
    return ingest.load_candidates(project_dir(pid), VIBE_STEP)


def vibe_import_upload(pid: str, files: list[tuple[str, bytes]]) -> dict:
    return ingest.import_upload(project_dir(pid), VIBE_STEP, files, "vibe")


def vibe_import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120) -> dict:
    return ingest.import_downloads(project_dir(pid), VIBE_STEP, folder, since_minutes, kind="image")


def _brief(root: Path, extra: dict | None = None) -> dict:
    """Brief do bot. Sem os termos do Pinterest (M4): a vibe é escolhida pelo sentimento."""
    meta = json.loads((root / "project.json").read_text())
    b = {"product": meta.get("product") or "", "vibe": meta.get("vibe") or ""}
    for k in ("purpose", "tone", "reference", "instruction", "explore_prompt"):
        if extra and extra.get(k):
            b[k] = extra[k]
    if extra and extra.get("no_people"):
        b["no_people"] = "no people in the frame (the product is the focus)"
    return b


#: Linha de qualidade da aula 007 pedida pela auditoria (G8).
STYLIZATION_HINT = "Estilização no meio-termo: extremos alucinam."


def _ui_hint(model: str) -> str:
    """Dica de UI. 2K e 16:9 são **sugestão do Studio** (a aula não fixa nem um nem outro, M10);
    o plano com geração ilimitada na UI chama-se **Ultimate** (aula 006, G10)."""
    base = ("Na UI da Higgsfield: Nano Banana Pro · sugestão 2K · 16:9 · gere um grid de 4 "
            "(o ilimitado do plano Ultimate vale só na UI); no modo com imagens, anexe as imagens de "
            "vibe como referência de estilo. Não pegou a vibe? Pegue a melhor do grid como referência "
            "e gere outro grid com o mesmo prompt."
            if model == "nano_banana_2" else "Na UI: GPT Image 2 · sugestão 2K · 16:9 · gere 4 imagens.")
    return f"{base} {STYLIZATION_HINT}"


def generate_prompt(pid: str, mode: str = "images", instruction: str = "", image_ids: list[str] | None = None,
                    purpose: str = "", tone: str = "", reference: str = "", model: str = "nano_banana_2",
                    variation: int = 0, no_people: bool = True, explore_prompt: str = "") -> dict:
    """mode: 'template' (sem Claude), 'brief' (Claude, só texto) ou 'images' (Claude olha as imagens de vibe).

    `no_people` (padrão marcado) é a única restrição da aula 009 e vai explícita para o bot;
    `explore_prompt` é o prompt copiado do Explore, preservado como base do prompt de vibe.
    """
    root = project_dir(pid)
    brief = _brief(root, {"purpose": purpose, "tone": tone, "reference": reference, "instruction": instruction,
                          "explore_prompt": explore_prompt, "no_people": no_people})
    if mode == "template":
        res = prompter.fallback_template("mood", brief, variation, no_people)
        images = []
    elif mode == "brief":
        if not prompter.available():
            raise RuntimeError("Claude CLI indisponível — use o modo template ou instale o Claude Code")
        res = prompter.from_brief("mood", brief)
        images = []
    elif mode == "images":
        ids = list(image_ids or [])[:MAX_VIBE_IMAGES]
        if not ids:
            raise ValueError("escolha de 1 a 4 imagens de vibe")
        if not prompter.available():
            raise RuntimeError("Claude CLI indisponível — use o modo template ou instale o Claude Code")
        by_id = {c["id"]: c for c in vibe_images(pid)}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise ValueError(f"imagem de vibe inexistente: {', '.join(missing)}")
        paths = [root / VIBE_STEP / "candidates" / by_id[i]["file"] for i in ids]
        res = prompter.from_images("mood", paths, instruction, brief)
        images = ids
    else:
        raise ValueError("mode deve ser template, brief ou images")
    res = prompter.enforce_mood_rules(res, no_people)
    entry = {"mode": mode, "instruction": instruction, "images": images, "model": model, "aspect_ratio": "16:9",
             "no_people": no_people, "explore_prompt": explore_prompt,
             "ui_hint": _ui_hint(model), "created": datetime.now().isoformat(timespec="seconds"), **res}
    hist = prompt_history(pid)
    hist.insert(0, entry)
    (root / "mood" / "prompts.json").write_text(json.dumps(hist[:50], ensure_ascii=False, indent=1))
    return entry


def prompt_history(pid: str) -> list[dict]:
    f = project_dir(pid) / "mood" / "prompts.json"
    return json.loads(f.read_text()) if f.exists() else []


# ---------- importação (delegada a studio/common/ingest.py) ----------
def load(pid: str) -> list[dict]:
    return ingest.load_candidates(project_dir(pid), "mood")


def candidates(pid: str) -> list[dict]:
    """Candidatas do mood com o lote de origem, para a legenda do protótipo ("grid_01 · img 1").

    O lote não é estado novo (wave 4, regra 5 — o backend só expõe o que a tela mostra): é
    derivado do job do CLI (`job_id`) ou do minuto da importação, que é como um grid inteiro
    entra de uma vez (upload de 4 arquivos, pasta Downloads, histórico). `batch_index` é a
    posição da imagem dentro do lote.
    """
    lotes: dict[str, int] = {}
    dentro: dict[str, int] = {}
    out = []
    for c in load(pid):
        chave = str(c.get("job_id") or (c.get("imported") or "")[:16] or c.get("source") or "?")
        lotes.setdefault(chave, len(lotes) + 1)
        dentro[chave] = dentro.get(chave, 0) + 1
        out.append({**c, "batch": f"grid_{lotes[chave]:02d}", "batch_index": dentro[chave]})
    return out


def _save(root: Path, cands: list[dict]) -> None:
    ingest.save_candidates(root, "mood", cands)


def _ingest_bytes(root: Path, data: bytes, source: str, name: str, prompt: str = "", meta: dict | None = None) -> dict | None:
    return ingest.ingest_bytes(root, "mood", data, source, name, prompt, meta, kind="image")


def import_upload(pid: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    return ingest.import_upload(project_dir(pid), "mood", files, prompt)


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40) -> dict:
    return ingest.import_downloads(project_dir(pid), "mood", folder, since_minutes, limit)


def import_history(pid: str, size: int = 50) -> dict:
    return ingest.import_history(project_dir(pid), "mood", "image", size)


# ---------- referência de estilo para o CLI (aula 009, M2) ----------
MAX_STYLE_REFS = 4


def style_reference_files(pid: str, vibe_ids: list[str] | None = None, best_id: str | None = None) -> list[str]:
    """Arquivos que vão ao CLI como `image_references`.

    Aula 009: a 1ª rodada usa a **imagem de vibe** encontrada no Explore; a 2ª usa a **melhor
    imagem do grid** como *referência de estilo* ("o que eu quero é referência de estilo"). As
    referências do Pinterest (etapa 1) **não** entram aqui — elas alimentam a etapa 3.
    """
    root = project_dir(pid)
    out: list[str] = []
    vibes = vibe_images(pid)
    wanted = list(vibe_ids or [])
    chosen = [c for c in vibes if c["id"] in wanted] if wanted else vibes[:MAX_STYLE_REFS]
    for c in chosen[:MAX_STYLE_REFS]:
        f = root / VIBE_STEP / "candidates" / (c.get("file") or "")
        if f.is_file():
            out.append(str(f))
    if best_id:
        best = next((c for c in load(pid) if c["id"] == best_id), None)
        if best is None:
            raise ValueError(f"candidata inexistente: {best_id}")
        f = root / "mood" / "candidates" / (best.get("file") or "")
        if f.is_file():
            out.append(str(f))
    return out


# ---------- geração via CLI (paga créditos) ----------
def start_generate(pid: str, model: str, prompts: list[str], aspect_ratio: str = "16:9", resolution: str = "2k",
                   count: int = 2, refs: list[str] | None = None) -> dict:
    root = project_dir(pid)

    def run(job: dict):
        for i, prompt in enumerate(prompts):
            params = {"prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": resolution, "count": count}
            if refs:
                params["image_references"] = refs
            res = hf.generate(model, params)
            # `[extensão]` livro-caixa de créditos (ADR-016).
            settings.record_generation(action="mood.grid", model=model, params=params, count=count,
                                       pid=pid, step="mood", job_id=res.get("id"))
            for url in res["urls"]:
                try:
                    data = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
                    if _ingest_bytes(root, data, "cli", url.split("?")[0].rsplit("/", 1)[-1], prompt, {"job_id": res.get("id"), "model": model}):
                        job["added"] += 1
                except Exception as e:  # noqa: BLE001
                    job["log"].append(f"download falhou: {e}")
            (root / "jobs").mkdir(exist_ok=True)
            (root / "jobs" / f"mood_{res.get('id') or i}.json").write_text(json.dumps(res["raw"], ensure_ascii=False, indent=1))
            job["done"] = i + 1

    try:
        return _registry.start(pid, len(prompts), run)
    except RuntimeError as e:
        raise RuntimeError("Já existe uma geração em andamento para este projeto.") from e


def job_status(pid: str) -> dict:
    return _registry.status(pid)


# ---------- seleção e paleta ----------
# A derivação da paleta vive em `studio/common/palette.py` (fonte única, ADR-013): a etapa 2 e a
# biblioteca global de mood boards usam o MESMO algoritmo. `_palette` aqui é o alias importado.
def _write_project_vibe(root: Path, note: str) -> str:
    """Grava a vibe encontrada nesta etapa em `project.json` (G2), com escrita atômica.

    Aula 009: "Você não precisa ter ideia nenhuma ainda" — a vibe nasce aqui, não na criação do
    projeto. Falha de leitura/escrita nunca derruba a seleção do mood (o mood já foi salvo).
    """
    if not note.strip():
        return ""
    path = root / "project.json"
    try:
        with atomic.project_lock(root):
            meta = json.loads(path.read_text())
            meta["vibe"] = note.strip()
            # Temporário único (`common.atomic`): o `project.json.tmp` de nome fixo era o MESMO
            # que o núcleo usa em `_write_project` — as duas escritas colidiam.
            atomic.write_json_atomic(path, meta, ensure_ascii=False, indent=1)
        return meta["vibe"]
    except (OSError, json.JSONDecodeError):
        return ""


def select(pid: str, ids: list[str], note: str = "") -> dict:
    root = project_dir(pid)
    cands = load(pid)
    chosen = set(ids)
    if len(chosen) > 8:
        raise ValueError("Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009).")
    sdir = root / "mood" / "selected"
    sdir.mkdir(parents=True, exist_ok=True)
    for old in sdir.iterdir():
        old.unlink()
    paths = []
    lines = ["# Mood board", "", f"Escolhido em {datetime.now():%Y-%m-%d %H:%M}.", "",
             "Aula 009: um mood só para a campanha inteira — todas as imagens no mesmo mood. "
             "O mood pode conter o produto (o da aula contém).", ""]
    if note:
        lines += [f"**Vibe em palavras:** {note}", ""]
    for c in cands:
        c["selected"] = c["id"] in chosen
        if c["selected"]:
            src = root / "mood" / "candidates" / c["file"]
            dst = sdir / c["file"]
            shutil.copy2(src, dst)
            paths.append(dst)
            lines.append(f"- `{c['file']}` — origem: {c['source']}" + (f" — prompt: {c['prompt'][:160]}" if c.get("prompt") else ""))
    _save(root, cands)
    palette = _palette(paths)
    # `by_file` guarda os 3 tons dominantes de CADA imagem: é o que permite ao guia avisar
    # "parecem moods diferentes" sem abrir imagem nenhuma (o hook do guia é leitura pura e barata).
    by_file = {f.name: _palette([f], 3) for f in paths}
    (root / "mood" / "palette.json").write_text(
        json.dumps({"colors": palette, "note": note, "by_file": by_file}, indent=1))
    lines += ["", "Paleta dominante `[extensão]` (derivado técnico do Studio — a aula usa as próprias "
              "imagens do mood como filtro, nunca extrai cores): " + ", ".join(palette)]
    (root / "mood" / "mood.md").write_text("\n".join(lines) + "\n")
    vibe = _write_project_vibe(root, note)
    return {"selected": len(paths), "palette": palette, "vibe": vibe}


# ---------- mood atual da campanha (painel "Mood atual" da etapa 2) ----------
def current(pid: str) -> dict:
    """Mood aplicado à campanha: imagens de `mood/selected/`, paleta e vibe.

    Leitura pura (nunca escreve) para o painel "Mood atual" da etapa 2. Seguro chamar antes de
    qualquer mood existir — devolve listas vazias. As imagens são servidas em
    `/files/<pid>/mood/selected/<file>`.
    """
    root = project_dir(pid)
    sdir = root / "mood" / "selected"
    files = sorted(p.name for p in sdir.iterdir()
                   if p.is_file() and p.suffix.lower() in IMG_EXT) if sdir.is_dir() else []
    palette: list[str] = []
    note = ""
    pf = root / "mood" / "palette.json"
    if pf.is_file():
        try:
            data = json.loads(pf.read_text())
            palette = [c for c in (data.get("colors") or []) if isinstance(c, str)]
            note = (data.get("note") or "").strip()
        except (OSError, json.JSONDecodeError):
            pass
    vibe = ""
    try:
        vibe = (json.loads((root / "project.json").read_text()).get("vibe") or "").strip()
    except (OSError, json.JSONDecodeError):
        pass
    return {"selected": [{"file": f} for f in files], "count": len(files),
            "palette": palette, "note": note, "vibe": vibe}


# ---------- puxar da biblioteca global de mood boards `[extensão]` (ADR-013/ADR-014) ----------
def pull_board(pid: str, mbid: str) -> dict:
    """Semeia o mood da campanha a partir de um board da biblioteca global.

    Copia as imagens curadas do board para `mood/selected/` e grava `mood.md`/`palette.json`/
    `project.vibe` — como o `select()`, mas a semente vem do board. Mantém o modelo de VIBE ÚNICA
    por campanha (ADR-007): o board é só a origem. Idempotente (reexecutar sobrescreve o mood).
    A biblioteca é global — apagar o board depois não afeta esta campanha (a cópia é independente).
    """
    from ..moodboards import service as mb
    root = project_dir(pid)
    src_paths = mb.board_image_paths(mbid)          # KeyError → 404 no router
    if not src_paths:
        raise ValueError("Este mood board ainda não tem imagens curadas para puxar.")
    meta = mb.get_board(mbid)
    note = (meta.get("vibe") or meta.get("name") or "").strip()
    sdir = root / "mood" / "selected"
    sdir.mkdir(parents=True, exist_ok=True)
    for old in sdir.iterdir():
        if old.is_file():
            old.unlink()
    paths = []
    for src in src_paths:
        dst = sdir / src.name
        shutil.copy2(src, dst)
        paths.append(dst)
    palette = _palette(paths)
    by_file = {f.name: _palette([f], 3) for f in paths}
    (root / "mood" / "palette.json").write_text(
        json.dumps({"colors": palette, "note": note, "by_file": by_file}, indent=1))
    lines = ["# Mood board", "", f"Puxado do mood board **{meta.get('name')}** (biblioteca global "
             "`[extensão]`) em " + f"{datetime.now():%Y-%m-%d %H:%M}.", "",
             "Aula 009: um mood só para a campanha inteira. O board é a semente; a vibe continua "
             "única por campanha (ADR-007). Copiado para a campanha — apagar o board não afeta aqui.", ""]
    if note:
        lines += [f"**Vibe em palavras:** {note}", ""]
    for src in src_paths:
        lines.append(f"- `{src.name}` — origem: mood board {mbid}")
    if meta.get("prompt"):
        lines += ["", f"**Prompt de vibe do board:** {meta['prompt'][:400]}"]
    lines += ["", "Paleta dominante `[extensão]`: " + ", ".join(palette)]
    (root / "mood" / "mood.md").write_text("\n".join(lines) + "\n")
    vibe = _write_project_vibe(root, note)
    return {"selected": len(paths), "palette": palette, "vibe": vibe, "board": mbid}
