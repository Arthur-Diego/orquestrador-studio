"""Tools de AÇÃO do MCP (ADR-037), Onda B. Conduzem a criação pelas rotas da API.

Dois padrões estruturantes:
- **Gate de custo embutido (ADR-016/038).** Toda geração paga passa por `_paid`: estima o custo,
  pede a confirmação ao usuário (`ui.confirm_cost`) e só então gera. O agente não tem como pular —
  não há tool paga que gere sem passar por aqui. No terminal (sem UI), exige `confirm=true`.
- **Escolha visual do usuário (ADR-038).** As tools `*_pick` buscam as candidatas, mostram a grade
  (`ui.choose_images`) e aplicam a seleção — em uma tool só, sem despejar dezenas de ids no modelo.
"""
from __future__ import annotations

from typing import Any

from . import ui
from .client import StudioApiError, StudioClient


# ---------- helpers ----------
def _images_for(pid: str, step: str, cands: list[dict], label_key: str = "batch") -> list[dict]:
    out = []
    for c in cands:
        thumb = c.get("thumb")
        if not thumb:
            continue
        out.append({"id": c["id"], "thumb": f"/files/{pid}/{step}/candidates/{thumb}",
                    "label": c.get(label_key) or c.get("name") or ""})
    return out


def _credits(cost: dict) -> Any:
    for k in ("total", "credits", "cost"):
        v = cost.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def _paid(client: StudioClient, *, step: str, cost_path: str, cost_body: dict, gen_path: str,
          gen_body: dict, action: str, model: str, confirm: bool) -> str:
    try:
        cost = client.post(cost_path, cost_body) or {}
    except StudioApiError as e:
        return str(e)
    credits = _credits(cost)
    cred_txt = credits if credits is not None else "não estimável"
    if ui.chat_id():
        ans = ui.confirm_cost(client, action, cred_txt, model)
        if not ans.get("answered") or not ans.get("confirmed"):
            return f"Geração cancelada pelo usuário (custo estimado: {cred_txt} créditos)."
    elif not confirm:
        return (f"Custo estimado: {cred_txt} créditos ({model}). "
                "Para gerar, chame esta tool de novo com confirm=true.")
    try:
        client.post(gen_path, gen_body)
    except StudioApiError as e:
        return str(e)
    return f"Geração iniciada ({model}). Acompanhe com `job_wait` (etapa {step})."


def _pick(client: StudioClient, *, pid: str, step: str, cands_path: str, select_path: str,
          title: str, minimum: int, maximum: int | None, select_body) -> str:
    try:
        cands = client.get(cands_path) or []
    except StudioApiError as e:
        return str(e)
    imgs = _images_for(pid, step, cands)
    if not imgs:
        return f"Nenhuma candidata na etapa {step} ainda — gere ou importe antes de escolher."
    ans = ui.choose_images(client, title, imgs, minimum=minimum, maximum=maximum)
    if ans.get("no_ui"):
        return ("Sem interface para escolher aqui. Candidatas disponíveis: "
                + ", ".join(i["id"] for i in imgs) + ". Diga quais escolher.")
    if not ans.get("answered"):
        return "O usuário não escolheu (sem resposta). Você pode perguntar de novo."
    ids = ans.get("selected") or []
    if not ids:
        return "O usuário não selecionou nenhuma imagem."
    try:
        client.post(select_path, select_body(ids))
    except StudioApiError as e:
        return str(e)
    return f"{len(ids)} imagem(ns) selecionada(s) e salva(s) na etapa {step}."


# ---------- 1 · Referências ----------
def refs_suggest_terms(client: StudioClient, product: str = "", vibe: str = "", brand: str = "",
                       pid: str = "") -> str:
    terms = client.get("/api/suggest-terms", {"product": product, "vibe": vibe, "brand": brand, "pid": pid}) or []
    return "Termos sugeridos: " + ", ".join(terms) if terms else "Nenhum termo sugerido (informe o produto)."


def refs_search(client: StudioClient, pid: str, terms: list[str], max_per_term: int = 30) -> str:
    if not terms:
        return "Passe ao menos um termo de busca."
    client.post(f"/api/projects/{pid}/refs/search", {"terms": terms, "max_per_term": max_per_term, "headless": True})
    return (f"Busca no Pinterest iniciada para {len(terms)} termo(s). Acompanhe com `job_wait` "
            "(etapa refs); depois use `refs_pick` para o usuário escolher.")


def refs_pick(client: StudioClient, pid: str) -> str:
    return _pick(client, pid=pid, step="refs", cands_path=f"/api/projects/{pid}/refs/candidates",
                 select_path=f"/api/projects/{pid}/refs/select",
                 title="Escolha as referências que você gosta", minimum=1, maximum=None,
                 select_body=lambda ids: {"ids": ids, "notes": {}})


# ---------- 2 · Mood board ----------
def mood_prompt(client: StudioClient, pid: str, mode: str = "brief", instruction: str = "",
                purpose: str = "", tone: str = "", reference: str = "", model: str = "nano_banana_2") -> str:
    resp = client.post(f"/api/projects/{pid}/mood/prompts/generate",
                       {"mode": mode, "instruction": instruction, "purpose": purpose, "tone": tone,
                        "reference": reference, "model": model}) or {}
    prompt = resp.get("prompt") if isinstance(resp, dict) else None
    return f"Prompt de vibe gerado:\n{prompt}" if prompt else f"Prompt gerado: {resp}"


def mood_generate(client: StudioClient, pid: str, prompts: list[str], count: int = 2,
                  model: str = "nano_banana_2", aspect_ratio: str = "16:9", resolution: str = "2k",
                  confirm: bool = False) -> str:
    if not prompts:
        return "Passe ao menos um prompt de vibe (use `mood_prompt` para gerá-lo)."
    body = {"model": model, "prompts": prompts, "aspect_ratio": aspect_ratio, "resolution": resolution, "count": count}
    return _paid(client, step="mood", cost_path=f"/api/projects/{pid}/mood/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/mood/generate", gen_body=body,
                 action="Gerar grid de mood", model=model, confirm=confirm)


def mood_pick(client: StudioClient, pid: str, note: str = "") -> str:
    return _pick(client, pid=pid, step="mood", cands_path=f"/api/projects/{pid}/mood/candidates",
                 select_path=f"/api/projects/{pid}/mood/select",
                 title="Escolha as imagens do mood (mesma vibe)", minimum=1, maximum=8,
                 select_body=lambda ids: {"ids": ids, "note": note})


# ---------- 3 · Imagem base ----------
def base_prompt(client: StudioClient, pid: str, ref_id: str | None = None, mode: str = "images",
                instruction: str = "") -> str:
    resp = client.post(f"/api/projects/{pid}/base/prompts/generate",
                       {"ref_id": ref_id, "mode": mode, "instruction": instruction}) or {}
    prompt = resp.get("prompt") if isinstance(resp, dict) else None
    return f"Prompt da base gerado:\n{prompt}" if prompt else f"Prompt gerado: {resp}"


def base_generate(client: StudioClient, pid: str, kind: str = "situation", prompt: str = "",
                  count: int | None = None, model: str | None = None, confirm: bool = False) -> str:
    body: dict = {"kind": kind, "prompt": prompt}
    if count is not None:
        body["count"] = count
    if model:
        body["model"] = model
    return _paid(client, step="base", cost_path=f"/api/projects/{pid}/base/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/base/generate", gen_body=body,
                 action="Gerar imagem base", model=model or "default", confirm=confirm)


def base_pick(client: StudioClient, pid: str, note: str = "") -> str:
    # a base final é UMA imagem; select da base recebe {id, note}
    try:
        cands = client.get(f"/api/projects/{pid}/base/candidates") or []
    except StudioApiError as e:
        return str(e)
    imgs = _images_for(pid, "base", cands)
    if not imgs:
        return "Nenhuma candidata de base ainda — gere com `base_generate` antes."
    ans = ui.choose_images(client, "Escolha a imagem base final", imgs, minimum=1, maximum=1)
    if ans.get("no_ui"):
        return "Sem interface aqui. Candidatas: " + ", ".join(i["id"] for i in imgs) + ". Diga qual escolher."
    if not ans.get("answered") or not ans.get("selected"):
        return "O usuário não escolheu a base."
    client.post(f"/api/projects/{pid}/base/select", {"id": ans["selected"][0], "note": note})
    return "Imagem base escolhida e salva."


# ---------- 4 · Storyboard (motor local grátis + escolha) ----------
def storyboard_local_generate(client: StudioClient, pid: str, prompt: str, count: int = 4,
                              model: str = "flux-schnell") -> str:
    if not prompt.strip():
        return "Escreva o prompt do keyframe (em inglês, aula 007)."
    try:
        client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    {"prompt": prompt, "count": count, "model": model})
    except StudioApiError as e:
        return str(e)  # 409 se o motor local (engine/ComfyUI) estiver offline
    return f"Keyframes locais (grátis) sendo gerados com {model}. Acompanhe com `job_wait` (etapa storyboard)."


def storyboard_pick(client: StudioClient, pid: str) -> str:
    return _pick(client, pid=pid, step="storyboard", cands_path=f"/api/projects/{pid}/storyboard/candidates",
                 select_path=f"/api/projects/{pid}/storyboard/candidates/select",
                 title="Escolha os keyframes do storyboard", minimum=1, maximum=None,
                 select_body=lambda ids: {"ids": ids})


def storyboard_scenes(client: StudioClient, pid: str) -> str:
    resp = client.get(f"/api/projects/{pid}/storyboard/scenes") or {}
    scenes = resp.get("scenes") if isinstance(resp, dict) else resp
    if not scenes:
        return "Nenhuma cena definida ainda no storyboard."
    linhas = [f"{i + 1}. {s.get('text', s) if isinstance(s, dict) else s}" for i, s in enumerate(scenes)]
    return "Cenas do storyboard:\n" + "\n".join(linhas)


# ---------- 5 · Animação ----------
def animate_shots(client: StudioClient, pid: str) -> str:
    resp = client.get(f"/api/projects/{pid}/animate/shots") or {}
    shots = resp.get("shots") if isinstance(resp, dict) else resp
    n = len(shots) if isinstance(shots, list) else "?"
    return f"Shots para animar: {n}. Use `animate_generate` para gerar um take (pago) e `job_wait`."


def animate_generate(client: StudioClient, pid: str, scene: str, shot: str, model: str = "kling3_0",
                     count: int = 2, prompt: str = "", confirm: bool = False) -> str:
    cost_body = {"scene": scene, "shot": shot, "model": model, "count": count}
    gen_body = {**cost_body, "prompt": prompt or None}
    return _paid(client, step="animate", cost_path=f"/api/projects/{pid}/animate/cost", cost_body=cost_body,
                 gen_path=f"/api/projects/{pid}/animate/generate", gen_body=gen_body,
                 action=f"Animar take (cena {scene}, shot {shot})", model=model, confirm=confirm)


# ---------- 6 · Trilha ----------
def music_generate(client: StudioClient, pid: str, prompt: str = "", duration: int = 30,
                   confirm: bool = False) -> str:
    body = {"prompt": prompt, "duration": duration}
    return _paid(client, step="music", cost_path=f"/api/projects/{pid}/music/generate/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/music/generate", gen_body=body,
                 action="Gerar trilha", model="sonilo_music", confirm=confirm)


# ---------- 7 · Montagem (ffmpeg, grátis) ----------
def edit_render(client: StudioClient, pid: str) -> str:
    try:
        client.post(f"/api/projects/{pid}/edit/render", {})
    except StudioApiError as e:
        return str(e)
    return "Montagem (render por ffmpeg, grátis) iniciada. Acompanhe com `job_wait` (etapa edit)."


# ---------- 8 · Export ----------
def export_render(client: StudioClient, pid: str, formats: list[str] | None = None) -> str:
    body = {"formats": formats or ["16x9", "9x16", "1x1"]}
    try:
        client.post(f"/api/projects/{pid}/export/render", body)
    except StudioApiError as e:
        return str(e)
    return "Export (formatos + thumb, grátis) iniciado. Acompanhe com `job_wait` (etapa export)."


def export_qa(client: StudioClient, pid: str) -> str:
    resp = client.post(f"/api/projects/{pid}/export/qa", {}) or {}
    return f"QA técnico do export: {resp}"


# ---------- 9 · Publicar ----------
def portfolio(client: StudioClient) -> str:
    resp = client.get("/api/portfolio") or {}
    return f"Portfólio: {resp}"
