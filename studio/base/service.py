"""Etapa 3 — Imagem base (aula 009), em "modo UI".

A aula manda, para cada referência escolhida na etapa 1: mostrar ao BOT o mood da campanha e a
referência e pedir "o prompt do meu produto na exata mesma situação desta imagem, com a vibe da
minha campanha"; gerar com o mood anexado; escolher a melhor; trocar o rótulo pela marca própria
com o Nano Banana (uma instrução por vez, reescrevendo se ficar simples demais) e fazer upscale
2x High Fidelity V2. Aqui isso vira:

1. `generate_prompt()` chama o bot (`common/prompter.py`, Claude CLI) com a referência + as
   imagens de `mood/selected/`; sem Claude, cai no template determinístico (`situation_prompt`);
2. `prompts()` monta a tela: a **instrução para o bot** (sessão nova, sem viés — a "aba nova" da
   aula é do bot, não da Higgsfield) e o **prompt para gerar** (a resposta do bot, editável);
3. o usuário gera na UI da Higgsfield (ilimitado) — ou via CLI, pagando créditos — e importa
   (upload, pasta Downloads, histórico do CLI) dizendo o `kind` (situation|label|upscale);
4. `select()` marca a candidata escolhida, copia para `base/base_final.png` e regrava `base.md`.

O campo `brand` (nome/descrição do rótulo) é `[extensão]` aprovada na wave 1: sem ele não há
como escrever o prompt de troca de rótulo que a aula dita.
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from .. import higgsfield as hf
from ..common import ingest, prompter, settings
from ..common.jobs import JobRegistry
from ..refs.service import project_dir

log = logging.getLogger("studio.base")

STEP = "base"
#: `clean` é `[extensão]` da wave 9: entra ENTRE `situation` e `label` (FDD base-clean-marca §4).
#: A limpeza acontece depois de escolhida a situação (é ela que herda a marca alheia da
#: referência) e antes do rótulo (limpa-se a embalagem para então aplicar a marca do usuário).
KINDS = ("situation", "clean", "label", "upscale")
RANK = {"situation": 0, "clean": 1, "label": 2, "upscale": 3}
KIND_LABEL = {"situation": "situação", "clean": "limpeza de marca", "label": "rótulo",
              "upscale": "upscale 2x"}
#: Os três passos que a aula 009 ensina. `clean` fica de fora de propósito: é `[extensão]` e
#: opcional, então não conta no progresso da etapa (senão o chip do guia viraria "cadeia 4/3").
#: Use `KINDS` para validação/iteração e `COURSE_KINDS` só onde se mede o roteiro do curso.
COURSE_KINDS = ("situation", "label", "upscale")
FINAL_REL = "base/base_final.png"

# IDs sugeridos pelo plano-higgsfield; o catálogo vivo ainda não pôde ser conferido (CLI sem
# login), por isso todo request aceita `model` e sobrescreve estes defaults.
DEFAULT_MODEL = "nano_banana_2"
DEFAULT_MODEL_LABEL = "nano_banana_2"
DEFAULT_MODEL_UPSCALE = "bytedance_image_upscale"
DEFAULT_MODELS = {"situation": DEFAULT_MODEL, "clean": DEFAULT_MODEL, "label": DEFAULT_MODEL_LABEL,
                  "upscale": DEFAULT_MODEL_UPSCALE}
#: Ação de custo de cada `kind` (ADR-016): fonte ÚNICA da regra, lida tanto por `_default_model`
#: (modelo default resolvido da config) quanto pelo `record_generation` do job (livro-caixa).
#: Kind ausente aqui cai em `base.image`, a ação genérica de edição/geração de imagem da etapa.
KIND_ACTION = {"upscale": "base.upscale", "clean": "base.clean"}
ACTION_DEFAULT = "base.image"

MOOD_REFS_MAX = 3          # a aula anexa a referência + algumas imagens do mood, não o mood inteiro
#: B11 (wave 2): a aula 009 põe "no people" no MOOD, não na base (ela até imagina "um mini ser
#: humano em perspectiva"). Aqui a frase é opcional — checkbox na tela, `no_people` nos contratos.
NO_PEOPLE = "No people unless they appear in the reference image."

#: Modos do bot de prompts, os mesmos da etapa 2 (aula 007: modo simplificado × guiado).
PROMPT_MODES = ("images", "brief", "template")
PROMPT_IMAGES_MAX = 4      # o prompter corta em 4: a referência + até 3 imagens do mood
#: B4 (wave 2): a aula reescreve a instrução do rótulo e gera 3 variações. A limpeza de marca
#: (`[extensão]`, wave 9) segue o mesmo padrão de edição do Nano Banana: gera 3, escolhe a melhor.
DEFAULT_COUNT = {"situation": 1, "clean": 3, "label": 3, "upscale": 1}
#: G3 (wave 2): o formato vem do projeto (aula 007 manda escolher pelo destino).
ASPECT_RATIOS = ("16:9", "9:16", "1:1")
ASPECT_DEFAULT = "16:9"
#: B6 (wave 2): a aula manda upscale 2x (preset High Fidelity V2); ±10 % de folga.
UPSCALE_MIN, UPSCALE_MAX = 1.8, 2.2
#: §3.5 da auditoria: prompt vindo do bot é longo ("até o tipo de câmera").
PROMPT_MIN_WORDS = 40

_registry = JobRegistry()


# ---------- insumos das etapas 1 e 2 ----------
def _meta(root: Path) -> dict:
    f = root / "project.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _product(root: Path) -> str:
    meta = _meta(root)
    return (meta.get("product") or meta.get("name") or "the product").strip()


def project_aspect(root: Path) -> str:
    """`project.aspect_ratio` (G3) — formato escolhido pelo destino na aula 007. Default 16:9.
    Valor inválido (project.json editado à mão) cai no default: o núcleo já valida no PATCH."""
    v = (_meta(root).get("aspect_ratio") or "").strip()
    return v if v in ASPECT_RATIOS else ASPECT_DEFAULT


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


def mood_paths(root: Path) -> list[Path]:
    """As imagens do mood como caminhos absolutos — é o "print do mood" que a aula mostra ao bot."""
    return [root / m for m in mood_files(root)]


def _mood_ref_files(root: Path, board: str | None = None) -> list[dict]:
    """base-prompt-provenance (FDD §2): as imagens de mood/board que entraram como referência de
    estilo no bot, em caminhos RELATIVOS para thumbs na UI. `board=None` é o mood da campanha
    (`mood/selected/`, servido por `/files/<pid>/...`); com `board`, são as imagens curadas do board
    da biblioteca (servidas por `/mbfiles/<board>/<rel>`). Mesmo corte que vai ao bot (MOOD_REFS_MAX)."""
    if board:
        from ..moodboards import service as mb
        return [{"file": rel, "board": board} for rel in mb.board_image_files(board)[:MOOD_REFS_MAX]]
    return [{"file": f, "board": None} for f in mood_files(root)[:MOOD_REFS_MAX]]


def _ref_mood_paths(root: Path, board: str | None = None) -> list[Path]:
    """`[extensão]` (ADR-013): as imagens de referência que vão ao bot como "mood".

    Sem `board`, é o mood da campanha (`mood/selected/`, o comportamento de sempre). Com `board`,
    são as imagens curadas de um board da biblioteca global — por caminho absoluto, como o
    `mood_paths` faz. Assim a etapa 3 pode referenciar visualmente um board sem tocar na campanha.
    """
    if board:
        from ..moodboards import service as mb
        return mb.board_image_paths(board)   # KeyError → 404 no router
    return mood_paths(root)


def mood_sources(pid: str) -> dict:
    """`[extensão]` (ADR-013): as fontes de mood que a etapa 3 pode usar como referência —
    o mood da campanha (atual) e os boards da biblioteca global com imagens curadas."""
    from ..moodboards import service as mb
    root = project_dir(pid)
    camp = mood_files(root)
    boards = [{"id": b["id"], "name": b["name"], "count": b["count"], "cover": b["cover"]}
              for b in mb.list_boards() if b["count"]]
    return {"campaign": {"files": camp, "count": len(camp)}, "boards": boards}


def _require_inputs(root: Path) -> tuple[list[dict], list[str]]:
    """Insumos das etapas 1 e 2 sem os quais a aula 009 não começa (B3: o mood entra como IMAGEM;
    os hex de `mood/palette.json` são opcionais)."""
    refs = selected_refs(root)
    if not refs:
        raise ValueError("Volte à etapa 1 e escolha ao menos uma referência (ela vira o 'brainstorming').")
    mood = mood_files(root)
    if not mood:
        raise ValueError("Volte à etapa 2 e salve o mood da campanha: o bot precisa ver as imagens de "
                         "mood/selected/ antes de escrever o prompt (aula 009).")
    return refs, mood


# ---------- marca do rótulo como IMAGEM (extensão, supersede da marca-texto) ----------
#: A marca do rótulo deixou de ser texto (nome + descrição) e passou a ser uma IMAGEM anexada
#: pelo dono (criada por ele, ex.: no Higgsfield). Ela entra como `image_reference` na geração do
#: rótulo (ADR-002: sem máscara real, aplica-se por prompt + imagem de referência). Ver ADR de
#: supersede da marca-por-texto da wave 1.
BRAND_IMAGE_FILE = "brand_image.png"
#: Prompt fixo do rótulo por imagem (não passa pelo Claude, como o antigo `label_prompt`): manda o
#: CLI aplicar a marca anexada sobre a embalagem, preservando o resto.
LABEL_IMAGE_PROMPT = ("Apply the attached brand/logo image onto the product label. "
                      "Keep the product colors, shape and everything else identical, realistic.")


def _brand_image_path(root: Path) -> Path | None:
    f = root / STEP / BRAND_IMAGE_FILE
    return f if f.exists() else None


def brand_image_get(pid: str) -> dict:
    """Marca-imagem atual do projeto (ou vazio quando ainda não foi anexada)."""
    return {"file": BRAND_IMAGE_FILE} if _brand_image_path(project_dir(pid)) else {}


def brand_image_set(pid: str, data: bytes) -> dict:
    """Salva a imagem da marca anexada pelo dono, normalizada em PNG. Valida que é imagem."""
    root = project_dir(pid)
    (root / STEP).mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(BytesIO(data)) as im:
            im.convert("RGB").save(root / STEP / BRAND_IMAGE_FILE, "PNG")
    except Exception as e:  # noqa: BLE001
        raise ValueError("Arquivo de marca inválido: envie uma imagem (PNG/JPG).") from e
    if chain(load(pid))["final"]:
        _write_md(root)      # o base.md aponta se há marca anexada; regrava quando muda
    return {"file": BRAND_IMAGE_FILE}


def brand_image_clear(pid: str) -> dict:
    (project_dir(pid) / STEP / BRAND_IMAGE_FILE).unlink(missing_ok=True)
    root = project_dir(pid)
    if chain(load(pid))["final"]:
        _write_md(root)
    return {}


# ---------- prompts da aula (em inglês, aula 007) ----------
def _mood_clause(pal: dict) -> str:
    parts = []
    if pal["note"]:
        parts.append(pal["note"])
    if pal["colors"]:
        parts.append("palette " + " ".join(pal["colors"][:6]))
    return ", ".join(parts)


def situation_prompt(product: str, pal: dict | None, no_people: bool = False) -> str:
    """Fallback determinístico (sem Claude). Na aula quem escreve este prompt é o BOT olhando a
    referência e o mood (B1) — este texto é a rede de segurança quando o Claude CLI não existe."""
    mood = _mood_clause(pal) if pal else ""
    txt = (f"The product ({product}) in the exact same situation as the reference image"
           + (f", with the campaign mood: {mood}" if mood else "") + ". ")
    if no_people:
        txt += NO_PEOPLE + " "
    return txt + "Photorealistic."


def bot_instruction(product: str, instruction: str = "") -> str:
    """B2: a INSTRUÇÃO que se dá ao bot em uma sessão nova, sem contexto da campanha (aula 009:
    "vou criar uma outra aba do meu GPT […] sem que ele saiba nada sobre a minha campanha").

    Não é o prompt de imagem: o prompt é a resposta que o bot devolve, e é ela que vai para a
    Higgsfield com a referência e o mood anexados.
    """
    extra = (instruction or "").strip()
    return ("I will show you a reference image. Write the prompt for an image identical to this one, "
            f"but the subject is: {product}."
            + (f" Change only this: {extra}." if extra else "")
            + " Be very detailed: composition, light, materials, camera body, lens and aperture. "
              "Answer in English, with the prompt only.")


#: Texto do painel: a "aba nova" da aula é do bot, não da Higgsfield (B2).
BOT_HINT = ("A \"aba nova\" da aula é do BOT, não da Higgsfield: abra uma sessão nova do bot (sem "
            "nada sobre a sua campanha), mande a instrução abaixo junto com a imagem de referência e "
            "traga de volta o prompt que ele escrever. O botão \"sem viés\" faz isso aqui pelo Claude.")


def _ui_hint(ar: str) -> str:
    return (f"Na UI da Higgsfield: anexe a referência e 1 a 3 imagens do mood, cole o prompt e gere um "
            f"grid de 4 em {ar} (sem o mood anexado \"sai coisa muito estranha\"). Escolha a melhor e "
            "importe aqui como \"situação\". Ignore a marca e os textos que saírem na embalagem — o "
            "rótulo vem no passo seguinte.")


def _brief(root: Path, instruction: str = "") -> dict:
    """Brief da campanha para o bot (aula 007: propósito, tom, referência em uma frase)."""
    pal = _palette(root) or {"colors": [], "note": ""}
    meta = _meta(root)
    b = {"product": _product(root), "vibe": (meta.get("vibe") or pal["note"] or "").strip(),
         "hints": _mood_clause(pal), "instruction": (instruction or "").strip()}
    return {k: v for k, v in b.items() if v}


def _template_result(product: str, pal: dict | None, no_people: bool) -> dict:
    return {"prompt": situation_prompt(product, pal, no_people), "negative": "text, logos, watermark",
            "camera": "", "notes_pt": "Template fixo (sem Claude): na aula quem escreve o prompt é o bot "
                                      "olhando a referência e o mood.",
            "source": "template", "seconds": 0.0, "images": []}


# ---------- o bot da aula escrevendo o prompt (B1) ----------
def prompt_history(pid: str) -> list[dict]:
    return _prompt_hist(project_dir(pid))


def _prompt_hist(root: Path) -> list[dict]:
    f = root / STEP / "prompts.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _last_prompt(hist: list[dict], ref_id: str | None) -> dict | None:
    """Último prompt gerado para a referência (o histórico já vem do mais novo para o mais velho)."""
    return next((e for e in hist if e.get("ref_id") == ref_id and e.get("prompt")), None)


def generate_prompt(pid: str, ref_id: str | None = None, mode: str = "images", instruction: str = "",
                    no_bias: bool = False, no_people: bool = False, model: str | None = None,
                    board: str | None = None, preset: settings.PresetArg = settings.PRESET_UNSET) -> dict:
    """B1/B2 (aula 009): o prompt de situação nasce do BOT olhando a referência e o mood.

    `mode`: `images` (o bot lê a referência + até 3 imagens do mood), `brief` (só texto) ou
    `template` (fallback determinístico, sem Claude). `no_bias=True` reproduz a aba nova da aula:
    só a referência, **sem** o brief da campanha e **sem** o mood, para o bot não ter viés.
    `board` `[extensão]` (ADR-013): usa as imagens de um board da biblioteca no lugar do mood da
    campanha como referência de estilo.

    `preset` `[extensão]` (opt-in): preset de realismo. Ausente resolve o default da ação `base`,
    `None` de fábrica — sem preset, o texto que vai ao CLI e o registro gravado são os de antes
    desta extensão.
    """
    if mode not in PROMPT_MODES:
        raise ValueError(f"mode deve ser {', '.join(PROMPT_MODES)}")
    root = project_dir(pid)
    preset, explicit = settings.resolve_preset("base", pid, preset)
    # Sem preset a chamada ao prompter fica exatamente como era (invariante opt-in do gate W3).
    kw = {"preset": preset} if preset else {}
    refs, _ = _require_inputs(root)
    ref = next((r for r in refs if r["ref_id"] == ref_id), None) if ref_id else refs[0]
    if ref is None:
        raise ValueError(f"referência inexistente ou não escolhida na etapa 1: {ref_id}")
    product = _product(root)
    pal = _palette(root)
    brief = None if no_bias else _brief(root, instruction)
    if mode == "template":
        # FDD §4: só o preset ESCOLHIDO mexe no fallback determinístico — e quem sabe preencher
        # `Camera:`/`Lighting:`/`Color grading:` com o rig do catálogo é o template do prompter.
        # Sem preset explícito o template da etapa fica byte-idêntico ao do curso.
        res = ({**prompter.fallback_template("base", brief or {"product": product}, no_people=no_people,
                                             preset=explicit), "images": []}
               if explicit else _template_result(product, pal, no_people))
    elif not prompter.available():
        raise RuntimeError("Claude CLI indisponível — use o modo template ou instale o Claude Code")
    elif mode == "brief":
        res = {**prompter.from_brief("base", brief or {"product": product}, **kw), "images": []}
    elif no_bias:
        res = prompter.from_images("base", [ref["path"]], bot_instruction(product, instruction), **kw)
    else:
        images = [ref["path"], *_ref_mood_paths(root, board)][:PROMPT_IMAGES_MAX]
        res = prompter.from_images("base", images, instruction, brief, **kw)
    text = (res.get("prompt") or "").strip()
    if no_people and "no people" not in text.lower():
        text = text.rstrip(". ") + ". " + NO_PEOPLE
    entry = {"ref_id": ref["ref_id"], "ref_file": ref["file"], "mode": mode,
             "instruction": (instruction or "").strip(), "no_bias": bool(no_bias),
             "no_people": bool(no_people), "model": model or DEFAULT_MODEL, "board": board or None,
             "aspect_ratio": project_aspect(root),
             "created": datetime.now().isoformat(timespec="seconds"), **res, "prompt": text,
             # base-prompt-provenance (FDD §1/§2): a junção mood × referência fica explícita no
             # retorno e no histórico — proveniência determinística + os insumos visuais usados.
             "provenance": prompter.provenance(text),
             "mood_refs": _mood_ref_files(root, board),
             "palette": pal or {"colors": [], "note": ""},
             # `[extensão]`: preset resolvido da requisição, também no histórico (FDD §7).
             "preset": preset}
    hist = _prompt_hist(root)
    hist.insert(0, entry)
    (root / STEP).mkdir(parents=True, exist_ok=True)
    (root / STEP / "prompts.json").write_text(json.dumps(hist[:50], ensure_ascii=False, indent=1))
    log.info("base: prompt pid=%s ref=%s mode=%s no_bias=%s fonte=%s", pid, ref["ref_id"], mode,
             no_bias, res.get("source"))
    return entry


def clean_prompt(target: str = "") -> str:
    """Instrução de limpeza de marca `[extensão]` (wave 9), em inglês e determinística.

    É instrução fixa, como `label_prompt`: não passa pelo Claude e não lê nada do disco. `target`
    nomeia a marca a remover (a tela pré-preenche com a marca validada da etapa 1); vazio, o texto
    fica genérico e ainda vale. A limpeza é **best-effort por prompt**: o CLI da Higgsfield não
    tem máscara nem inpaint (ADR-002), por isso o texto fixa "keep everything else identical".
    """
    alvo = target.strip()
    return ("Remove all brand names, logos, labels and printed text from the product"
            + (f' (the "{alvo}" branding in particular)' if alvo else "")
            + ". Leave the label area blank and clean."
            + " Keep the product shape, colors, materials, lighting and background identical, realistic.")


def prompts(pid: str, model: str | None = None) -> dict:
    """O que a tela da etapa 3 precisa mostrar: por referência escolhida, a **instrução para o bot**
    (sessão nova, sem viés) e o **prompt para gerar** — o último que o bot escreveu para aquela
    referência, ou o template de fallback enquanto ninguém gerou (B1/B2)."""
    root = project_dir(pid)
    refs, mood = _require_inputs(root)
    pal = _palette(root)
    product = _product(root)
    brand_ready = _brand_image_path(root) is not None
    hist = _prompt_hist(root)
    ar = project_aspect(root)
    out = []
    for r in refs:
        last = _last_prompt(hist, r["ref_id"])
        prompt = last["prompt"] if last else situation_prompt(product, pal)
        out.append({"ref_id": r["ref_id"], "file": r["file"],
                    "prompt": prompt,
                    "prompt_source": (last.get("source") or "claude") if last else "template",
                    "prompt_mode": last.get("mode") if last else None,
                    # base-prompt-provenance (FDD §1/§3): a UI mostra a junção mood × referência
                    # anotando as 5 linhas do prompt exibido; recomputamos aqui para o texto atual.
                    "provenance": prompter.provenance(prompt),
                    "bot_instruction": bot_instruction(product)})
    return {
        "model": model or DEFAULT_MODEL,
        "aspect_ratio": ar,
        "bot_hint": BOT_HINT,
        "ui_hint": _ui_hint(ar),
        "product": product,
        "palette": pal or {"colors": [], "note": ""},
        "mood_files": mood,
        "claude": prompter.available(),
        "modes": list(PROMPT_MODES),
        "refs": out,
        # Marca-imagem (supersede da marca-texto): o rótulo fica pronto quando a imagem da marca
        # foi anexada. A UI usa `brand_image` (arquivo servível) para o preview.
        "brand_image": BRAND_IMAGE_FILE if brand_ready else None,
        "label_ready": brand_ready,
        "label_count": DEFAULT_COUNT["label"],
        # `[extensão]` wave 9: o texto default do passo de limpeza também vem do backend (mesmo
        # molde do rótulo). Sai genérico — o `target` é campo da tela e entra no prompt na hora de
        # gerar, via `clean_prompt(target)` (a tela não monta texto de prompt por conta própria).
        "clean_prompt": clean_prompt(),
        "clean_count": DEFAULT_COUNT["clean"],
        "upscale_hint": "Upscale 2x, preset High Fidelity V2 na UI (a mesma imagem, com mais qualidade) "
                        "— ou o modelo bytedance_image_upscale via CLI.",
    }


# ---------- candidatas ----------
def _normalize(cands: list[dict], kind: str | None = None, ref_id: str | None = None,
               new_ids: set[str] | None = None, source_id: str | None = None) -> list[dict]:
    """Completa o que o `ingest` não sabe da etapa: `kind` da aula e `ref_id`, e deixa
    `file`/`thumb` relativos ao projeto (schema fixado na wave 1).

    `source_id` é `[extensão]` (F11): de que candidata a nova veio. Só é gravado nas candidatas de
    `new_ids`; nas antigas entra por `setdefault`, para que um `candidates.json` anterior à feature
    carregue com `source_id: null` sem migração e sem reescrita de nenhum outro campo.
    """
    for c in cands:
        if new_ids is not None and c["id"] in new_ids:
            if kind:
                c["kind"] = kind
            c["ref_id"] = ref_id
            # A origem de uma `situation` é a referência da etapa 1, já em `ref_id`; o `!= c["id"]`
            # sustenta o invariante "nunca o próprio id" (FDD §6).
            sid = None if kind == "situation" else source_id
            c["source_id"] = sid if sid != c["id"] else None
        if c.get("kind") not in KINDS:
            c["kind"] = kind or "situation"
        c.setdefault("ref_id", None)
        c.setdefault("source_id", None)
        if c.get("file") and not str(c["file"]).startswith(f"{STEP}/"):
            c["file"] = f"{STEP}/candidates/{c['file']}"
        if c.get("thumb") and not str(c["thumb"]).startswith(f"{STEP}/"):
            c["thumb"] = f"{STEP}/candidates/{c['thumb']}"
    return cands


def load(pid: str) -> list[dict]:
    return _normalize(ingest.load_candidates(project_dir(pid), STEP))


def _finish_import(root: Path, before: set[str], kind: str, ref_id: str | None,
                   source_id: str | None = None) -> tuple[list[str], list[str]]:
    """`source_id` `[extensão]` (F11): no caminho pago vem pronto do item do `_plan`, que já
    resolveu a origem antes de chamar o CLI. No import pela tela chega `None` e é inferido por
    `source_candidate` sobre as candidatas que já existiam ANTES do import (`before`), para que uma
    candidata nova jamais seja origem de si mesma.

    Devolve `(warnings, new_ids)` `[extensão]` (F11): os ids novos, na ordem de ingestão, já eram
    calculados aqui e eram descartados. São a FONTE ÚNICA de `new_candidates` no status do job
    (FDD §10 risco 1) — nunca uma segunda varredura do diretório."""
    cands = ingest.load_candidates(root, STEP)
    new_ids = [c["id"] for c in cands if c["id"] not in before]   # ordem do JSON = ordem de ingestão
    novos = set(new_ids)
    if source_id is None and kind != "situation":
        src = source_candidate([c for c in cands if c["id"] in before], kind)
        source_id = src["id"] if src else None
    cands = _normalize(cands, kind, ref_id, novos, source_id)
    ingest.save_candidates(root, STEP, cands)
    warnings = upscale_warnings(root, cands, novos) if kind == "upscale" else []
    return warnings, new_ids


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001  — arquivo sumiu ou não é imagem: sem dimensão, sem aviso
        return None


def cand_size(root: Path, c: dict | None) -> tuple[int, int]:
    """Dimensões da candidata: `width`/`height` do `ingest` e, só se faltarem, o arquivo."""
    if not c:
        return 0, 0
    w, h = int(c.get("width") or 0), int(c.get("height") or 0)
    if w and h:
        return w, h
    size = _image_size(root / c["file"]) if c.get("file") else None
    return size if size else (0, 0)


def upscale_warnings(root: Path, cands: list[dict], new_ids: set[str]) -> list[str]:
    """B6: a aula manda "2x, preset High Fidelity V2". Compara a largura da candidata importada
    como `upscale` com a da candidata de origem selecionada. Aviso — nunca recusa o import."""
    src = source_candidate(cands, "upscale")
    base_w = cand_size(root, src)[0]
    if not base_w:
        return []
    out = []
    for c in cands:
        if c["id"] not in new_ids or c.get("kind") != "upscale":
            continue
        w = cand_size(root, c)[0]
        if not w:
            continue
        ratio = w / base_w
        if not (UPSCALE_MIN <= ratio <= UPSCALE_MAX):
            out.append(f"{c['id']}: a aula pede upscale 2x — esta ficou {ratio:.1f}x "
                       f"({base_w}px → {w}px). Refaça com 2x, preset High Fidelity V2.")
    return out


def upscale_ratio(root: Path, cands: list[dict]) -> tuple[float | None, int, int]:
    """Razão entre a largura do upscale escolhido e a da candidata de origem da cadeia."""
    up = _selected(cands, "upscale")
    src = _selected(cands, "label") or _selected(cands, "clean") or _selected(cands, "situation")
    w0, w1 = cand_size(root, src)[0], cand_size(root, up)[0]
    return (round(w1 / w0, 2) if w0 and w1 else None), w0, w1


def _default_model(pid: str, kind: str) -> str:
    """Modelo default da etapa 3, LIDO DA CONFIG (ADR-016): override do projeto › global › código.

    A etapa 3 não tem seletor de modelo na tela (o `?model=` saiu na wave 3): o default vem daqui,
    não de um id fixo, para o painel admin de "Créditos & Custos" mandar de fato.
    """
    kind = _check_kind(kind)
    chosen = settings.default_for(KIND_ACTION.get(kind, ACTION_DEFAULT), pid).get("model")
    return chosen or DEFAULT_MODELS[kind]


def _check_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"kind inválido: {kind} (use situation, clean, label ou upscale)")
    return kind


def import_upload(pid: str, files: list[tuple[str, bytes]], kind: str = "situation",
                  ref_id: str | None = None, prompt: str = "") -> dict:
    _check_kind(kind)
    root = project_dir(pid)
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    res = ingest.import_upload(root, STEP, files, prompt)
    return {**res, "warnings": _finish_import(root, before, kind, ref_id)[0]}


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40,
                     kind: str = "situation", ref_id: str | None = None, prompt: str = "") -> dict:
    _check_kind(kind)
    root = project_dir(pid)
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    res = ingest.import_downloads(root, STEP, folder, since_minutes, limit, prompt=prompt)
    return {**res, "warnings": _finish_import(root, before, kind, ref_id)[0]}


def import_history(pid: str, kind: str = "situation", ref_id: str | None = None, size: int = 50,
                   prompt_filter: str | None = None) -> dict:
    _check_kind(kind)
    root = project_dir(pid)
    before = {c["id"] for c in ingest.load_candidates(root, STEP)}
    res = ingest.import_history(root, STEP, "image", size, prompt_filter)
    return {**res, "warnings": _finish_import(root, before, kind, ref_id)[0]}


# ---------- seleção, base_final.png e base.md ----------
def chain(cands: list[dict]) -> dict:
    """Ids escolhidos em cada passo da cadeia da aula + o passo mais avançado (`final`)."""
    out: dict = {k: None for k in KINDS}
    for c in cands:
        if c.get("selected") and c.get("kind") in KINDS:
            out[c["kind"]] = c["id"]
    final = next((k for k in reversed(KINDS) if out[k]), None)
    return {**out, "final": final}


def _selected(cands: list[dict], kind: str) -> dict | None:
    return next((c for c in cands if c.get("selected") and c.get("kind") == kind), None)


def most_advanced(cands: list[dict]) -> dict | None:
    """A candidata selecionada mais avançada da cadeia: upscale > label > situação."""
    chosen = [c for c in cands if c.get("selected") and c.get("kind") in KINDS]
    return max(chosen, key=lambda c: RANK[c["kind"]]) if chosen else None


def source_candidate(cands: list[dict], kind: str) -> dict | None:
    """`[extensão]` (F11): de qual candidata selecionada um passo `kind` parte.

    Reproduz a precedência que `_plan` já usa no caminho pago, para que o import pela tela grave a
    mesma origem — com uma diferença deliberada: um `upscale` importado NUNCA aponta para outro
    `upscale` (`most_advanced` consideraria), o que evitaria origem circular na cadeia. Sem origem
    selecionada devolve `None`: grava-se `null`, nunca um chute.
    """
    if kind == "clean":
        return _selected(cands, "situation")
    if kind == "label":
        return _selected(cands, "clean") or _selected(cands, "situation")
    if kind == "upscale":
        return most_advanced([c for c in cands if c.get("kind") in ("situation", "clean", "label")])
    return None     # `situation` (origem é a referência da etapa 1, em `ref_id`) e kind inválido


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
    ch = chain(cands)
    pal = _palette(root) or {"colors": [], "note": ""}
    lines = ["# Imagem base", "", f"Etapa 3 · aula 009 · atualizado em {datetime.now():%Y-%m-%d %H:%M}.", "",
             f"**Produto:** {_product(root)}"]
    if _brand_image_path(root):
        lines.append(f"**Marca [extensão]:** imagem anexada (`{BRAND_IMAGE_FILE}`)")
    lines += ["", f"**Arquivo final:** `{FINAL_REL}`" if ch["final"] else "**Arquivo final:** ainda não escolhido",
              "", "| Etapa | id | origem | referência | prompt |", "| --- | --- | --- | --- | --- |"]
    for kind in KINDS:
        c = _selected(cands, kind)
        if not c:
            continue
        lines.append(f"| {KIND_LABEL[kind]} | `{c['id']}` | {c.get('source', '')} | "
                     f"{c.get('ref_id') or '—'} | {(c.get('prompt') or '').replace('|', '/')[:200]} |")
    if pal["colors"]:
        lines += ["", "**Paleta usada:** " + ", ".join(pal["colors"])]
    if pal["note"]:
        lines += ["", f"**Mood:** {pal['note']}"]
    if note:
        lines += ["", f"**Notas:** {note}"]
    lines += _md_prompts(root, cands)
    lines += ["", "## Dever de casa (aula 009)", "",
              "Poste a imagem base e o prompt acima na aba de compartilhamento de prompts da "
              "comunidade — é o dever de casa que o instrutor pede no fim da aula."]
    (root / STEP).mkdir(parents=True, exist_ok=True)
    (root / STEP / "base.md").write_text("\n".join(lines) + "\n")


def _md_prompts(root: Path, cands: list[dict]) -> list[str]:
    """B4/B10: a instrução de cada passo fica gravada por inteiro — o dever de casa da aula pede o
    prompt junto da imagem, e o texto truncado da tabela não serve para copiar."""
    hist = _prompt_hist(root)
    lines = ["", "## Prompts e instruções usados", ""]
    for kind in KINDS:
        c = _selected(cands, kind)
        if not c:
            continue
        lines += [f"### {KIND_LABEL[kind].capitalize()}", ""]
        if kind == "situation":
            entry = _last_prompt(hist, c.get("ref_id"))
            lines.append("- **Instrução ao bot (sessão nova, sem viés):** " + bot_instruction(_product(root)))
            if entry:
                lines.append(f"- **Modo do bot:** {entry.get('mode')} · fonte: {entry.get('source')}"
                             + (" · sem viés" if entry.get("no_bias") else ""))
                if entry.get("instruction"):
                    lines.append(f"- **Instrução do usuário:** {entry['instruction']}")
        if kind == "upscale":
            ratio, w0, w1 = upscale_ratio(root, cands)
            lines.append(f"- **Upscale:** {ratio}x ({w0}px → {w1}px)" if ratio
                         else "- **Upscale:** dimensões indisponíveis")
        lines += [f"- **Prompt/instrução:** {(c.get('prompt') or '—').strip()}", ""]
    return lines


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
    ch = chain(cands)
    log.info("base: select pid=%s id=%s kind=%s final=%s", pid, cid, kind, ch["final"])
    return {"final": FINAL_REL if final else None, "kind": final["kind"] if final else None,
            "chain": {k: ch[k] for k in KINDS}}


def final_file(pid: str) -> str | None:
    return FINAL_REL if (project_dir(pid) / FINAL_REL).exists() else None


# ---------- geração via CLI (paga créditos) ----------
def _plan(root: Path, kind: str, ref_ids: list[str] | None, count: int,
          prompt: str = "", board: str | None = None, target: str = "") -> tuple[list[dict], str]:
    """Itens do job (um por chamada ao CLI) + o prompt/instrução que cada um usa.
    `prompt` não vazio é o texto EDITADO na tela (B4) e vence o histórico/template.
    `board` `[extensão]` (ADR-013): referência de estilo vinda de um board da biblioteca.
    `target` `[extensão]` (wave 9): marca a remover, só usada pelo `kind="clean"`."""
    _check_kind(kind)
    cands = _normalize(ingest.load_candidates(root, STEP))
    mood = [str(m) for m in _ref_mood_paths(root, board)][:MOOD_REFS_MAX]
    if kind == "situation":
        refs, _ = _require_inputs(root)
        if ref_ids:
            refs = [r for r in refs if r["ref_id"] in set(ref_ids)]
        if not refs:
            raise ValueError("Nenhuma referência escolhida na etapa 1 com arquivo em refs/brainstorming/.")
        pal, product, hist = _palette(root), _product(root), _prompt_hist(root)
        items = []
        for r in refs:
            # B1: o prompt que vai ao CLI é o que o bot escreveu para AQUELA referência; sem
            # histórico, o template de fallback.
            last = _last_prompt(hist, r["ref_id"])
            text = prompt.strip() or (last["prompt"] if last else situation_prompt(product, pal))
            items.append({"ref_id": r["ref_id"], "prompt": text,
                          "image_references": [str(r["path"]), *mood]})
        return items, items[0]["prompt"]
    if kind == "clean":
        # `[extensão]` wave 9: limpeza sempre parte da SITUAÇÃO escolhida — é ela que herda a marca
        # alheia da referência. Mesma pré-condição (e mesma mensagem) do rótulo, FDD §6.
        base = _selected(cands, "situation")
        if base is None:
            raise ValueError("Escolha primeiro a melhor imagem de situação (aula 009).")
        # `clean_prompt` sempre devolve texto (sem `target`, fica genérico): não há segundo `raise`.
        text = prompt.strip() or clean_prompt(target)
        item = {"ref_id": base.get("ref_id"), "prompt": text, "source_id": base["id"],
                "image_references": [str(root / base["file"])]}
        return [dict(item) for _ in range(max(1, count))], text
    if kind == "label":
        # Com a limpeza `[extensão]` escolhida, o rótulo é aplicado sobre a embalagem já limpa;
        # sem ela, parte da situação exatamente como antes da wave 9 (fallback aditivo, FDD §4).
        base = _selected(cands, "clean") or _selected(cands, "situation")
        if base is None:
            raise ValueError("Escolha primeiro a melhor imagem de situação (aula 009).")
        # Marca-imagem (supersede): a marca vai como 2ª `image_reference` e o CLI a aplica no rótulo
        # (ADR-002: sem máscara, por prompt + imagem). Sem imagem anexada, não há rótulo.
        brand_img = _brand_image_path(root)
        if brand_img is None:
            raise ValueError("Anexe a imagem da marca antes de trocar o rótulo.")
        text = prompt.strip() or LABEL_IMAGE_PROMPT
        item = {"ref_id": base.get("ref_id"), "prompt": text, "source_id": base["id"],
                "image_references": [str(root / base["file"]), str(brand_img)]}
        return [dict(item) for _ in range(max(1, count))], text
    src = most_advanced(cands)
    if src is None:
        raise ValueError("Escolha primeiro a imagem que será ampliada (situação ou rótulo).")
    # `source_id` `[extensão]` (F11): aqui a origem é a imagem que de fato foi ao CLI — inclusive
    # outro `upscale`, se foi ela a entrada. A regra de "nunca outro upscale" é da inferência do
    # import pela tela (`source_candidate`), onde a entrada real não é conhecida.
    return [{"ref_id": src.get("ref_id"), "prompt": "", "source_id": src["id"],
             "image_references": [str(root / src["file"])]}], ""


def cost_model(pid: str, kind: str, model: str | None = None) -> str:
    """Modelo que a estimativa/geração vai de fato usar: o explícito do cliente ou o default da
    config (ADR-016). `[extensão]` wave 11: a rota de custo precisa NOMEAR o modelo no
    `CostPreview`, e `estimate_cost` o resolve por dentro — a regra continua num lugar só.
    """
    return model or _default_model(pid, kind)


def estimate_cost(pid: str, kind: str, model: str | None = None, ref_ids: list[str] | None = None,
                  count: int | None = None, aspect_ratio: str | None = None, resolution: str = "2k",
                  prompt: str = "", board: str | None = None, target: str = "") -> dict:
    """Estimativa de créditos SEM gerar (a UI mostra e pede `confirm()` antes de gastar).
    `count` ausente usa o default do passo (B4: 3 no rótulo); `aspect_ratio` ausente, o do projeto (G3).
    `target` `[extensão]` (wave 9): marca a remover, só usada pelo `kind="clean"`."""
    root = project_dir(pid)
    count = count or DEFAULT_COUNT[_check_kind(kind)]
    aspect_ratio = aspect_ratio or project_aspect(root)
    items, text = _plan(root, kind, ref_ids, count, prompt, board, target)
    n = len(items) * (count if kind == "situation" else 1)
    model = model or _default_model(pid, kind)
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
                   count: int | None = None, aspect_ratio: str | None = None, resolution: str = "2k",
                   prompt: str = "", board: str | None = None, target: str = "") -> dict:
    """Caminho pago: o Studio chama o CLI por item e importa o resultado. Sem retry automático.
    `target` `[extensão]` (wave 9): marca a remover, só usada pelo `kind="clean"`."""
    root = project_dir(pid)
    count = count or DEFAULT_COUNT[_check_kind(kind)]
    aspect_ratio = aspect_ratio or project_aspect(root)
    items, _ = _plan(root, kind, ref_ids, count, prompt, board, target)
    model = model or _default_model(pid, kind)

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
                # `[extensão]` livro-caixa de créditos (ADR-016): registra o gasto real por chamada.
                settings.record_generation(action=KIND_ACTION.get(kind, ACTION_DEFAULT),
                                           model=model, params=params, count=count if kind == "situation" else 1,
                                           pid=pid, step=STEP, job_id=res.get("id"))
                job["log"].append(f"[{kind}] ref={item.get('ref_id') or '—'} model={model} "
                                  f"urls={len(res.get('urls') or [])} added={added}")
            except Exception as e:  # noqa: BLE001  — falha de item não derruba o job inteiro
                failures += 1
                last = f"{type(e).__name__}: {e}"[:400]
                job["log"].append(f"erro: {last}")
            job["done"] = i + 1
        log.info("base: job pid=%s kind=%s itens=%s added=%s falhas=%s", pid, kind, len(items), job["added"], failures)
        # `[extensão]` (F11, FDD §7): o que o job PRODUZIU, para cruzar com `added` na observação.
        novas = new_candidates(pid, job.get("new_ids") or [])
        log.info("base: job pid=%s kind=%s novas=%s origens=%s", pid, kind,
                 len(novas), sum(1 for c in novas if c["source_id"]))
        if failures and failures == len(items):
            raise RuntimeError(last)

    try:
        job = _registry.start(pid, len(items), run, kind=kind, model=model)
    except RuntimeError as e:
        raise RuntimeError("Já existe uma geração em andamento para este projeto.") from e
    # `new_ids` é escrituração interna do job (`[extensão]` F11): a thread pode já tê-la criado
    # quando este retorno é serializado, e o payload de `/base/generate` não muda por causa dela.
    return {k: v for k, v in job.items() if k != "new_ids"}


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
    warnings, new_ids = _finish_import(root, before, kind, item.get("ref_id"), item.get("source_id"))
    if job is not None:
        for w in warnings:
            job["log"].append(w)
        # `[extensão]` (F11): os ids saem do MESMO lugar que conta `added` — o `_finish_import` deste
        # item. Sem segunda varredura do diretório, o que sustenta `len(new_candidates) == added`.
        job.setdefault("new_ids", []).extend(new_ids)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return added


def new_candidates(pid: str, ids: list[str]) -> list[dict]:
    """`[extensão]` (F11) — as candidatas de `ids` no formato que o chat consegue mostrar (FDD §5
    contrato 1): na ordem pedida, com as URLs já absolutas e servíveis por `/files` (`app.py`).

    A prefixação com `/files/{pid}/` acontece SÓ aqui, na borda: `file`/`thumb` seguem relativos à
    raiz do projeto no `candidates.json` (invariante do HLD base). Leitura defensiva: id sem
    candidata correspondente é omitido — nunca levanta, para não derrubar a rota do job."""
    if not ids:
        return []
    by_id = {c["id"]: c for c in load(pid)}     # uma leitura de candidates.json por chamada
    out = []
    for cid in ids:
        c = by_id.get(cid)
        if c is None:
            continue
        out.append({"id": c["id"], "kind": c.get("kind"),
                    "thumb_url": f"/files/{pid}/{c['thumb']}" if c.get("thumb") else None,
                    "file_url": f"/files/{pid}/{c['file']}" if c.get("file") else None,
                    "source_id": c.get("source_id")})
    return out


def job_status(pid: str) -> dict:
    """O status do job diz TAMBÉM o que ele produziu (`new_candidates`, `[extensão]` F11, FDD §5).

    A cópia é obrigatória: `JobRegistry.status` devolve a referência VIVA do job, e escrever nela
    vazaria a chave para `job_wait`/`job_status` de outras etapas e a recalcularia a cada polling.
    `new_ids` é escrituração interna e não entra no payload."""
    job = dict(_registry.status(pid))
    ids = job.pop("new_ids", None) or []
    job["new_candidates"] = new_candidates(pid, ids)
    return job
