"""Tools de AÇÃO do MCP (ADR-037), Onda B. Conduzem a criação pelas rotas da API.

Dois padrões estruturantes:
- **Gate de custo embutido (ADR-016/038).** Toda geração paga passa por `_paid`: estima o custo,
  pede a confirmação ao usuário (`ui.confirm_cost`) e só então gera. O agente não tem como pular —
  não há tool paga que gere sem passar por aqui. No terminal (sem UI), exige `confirm=true`.
- **Escolha visual do usuário (ADR-038).** As tools `*_pick` buscam as candidatas, mostram a grade
  (`ui.choose_images`) e aplicam a seleção — em uma tool só, sem despejar dezenas de ids no modelo.
"""
from __future__ import annotations

import json
import time
from typing import Any

from . import ui
from .client import StudioApiError, StudioClient

#: Chaves de lista aceitas quando a rota de candidatas devolve um **dict** em vez de uma lista.
#: Os shapes são diferentes por domínio, por design (base publica `{candidates, final}`, storyboard
#: publica `{ideas}`, refs/mood/personagem publicam lista pura) — o consumidor é que é tolerante,
#: as rotas não mudam (ADR-037: o MCP é cliente da API, a correção mora no cliente).
CAND_KEYS = ("candidates", "ideas", "items")

#: Cadeia de fallback do rótulo da grade, aplicada depois da chave preferida da etapa. Sem ela,
#: base, refs e storyboard exibiriam legenda vazia (só mood tem `batch`).
LABEL_KEYS = ("batch", "kind", "term", "label", "name")
LABEL_MAX = 60


# ---------- helpers ----------
def _candidate_rows(payload: Any) -> list[dict]:
    """Normaliza o shape da resposta de candidatas para uma lista de linhas `dict`.

    Lista devolve as linhas que são `dict`; dict devolve a primeira lista entre `CAND_KEYS`;
    qualquer outra coisa devolve `[]`. NUNCA levanta: shape inesperado vira "sem candidatas",
    que a tool traduz em texto acionável.
    """
    rows: Any = payload
    if isinstance(payload, dict):
        rows = next((v for k in CAND_KEYS if isinstance(v := payload.get(k), list)), None)
    if not isinstance(rows, list):
        return []
    return [c for c in rows if isinstance(c, dict)]


def _media_url(prefix: str, step: str, thumb: str) -> str:
    """URL servível da thumb. `thumb` já absoluto passa direto; já prefixado com `<step>/` (base e
    storyboard, relativos à raiz do projeto) só recebe o prefixo; relativo recebe o caminho inteiro.
    """
    if thumb.startswith("/") or thumb.startswith("http"):
        return thumb
    if thumb.startswith(f"{step}/"):
        return f"{prefix}/{thumb}"
    return f"{prefix}/{step}/candidates/{thumb}"


def _label(c: dict, label_key: str) -> str:
    """Legenda da grade: a chave preferida da etapa, a cadeia de fallback e, por último, o prompt.
    Truncada, porque a legenda fica sob a miniatura e o prompt de storyboard é uma frase inteira."""
    for k in (label_key, *LABEL_KEYS, "prompt"):
        v = c.get(k)
        if isinstance(v, str) and v.strip():
            texto = v.strip()
            return texto if len(texto) <= LABEL_MAX else texto[:LABEL_MAX - 1] + "…"
    return ""


def _images_for(pid: str, step: str, cands: Any, label_key: str = "batch") -> list[dict]:
    """Payload de `ui.choose_images` a partir de qualquer shape publicado pelas rotas de candidatas."""
    out = []
    for c in _candidate_rows(cands):
        thumb = c.get("thumb")
        cid = c.get("id")
        if not thumb or not isinstance(thumb, str) or not cid:
            continue
        out.append({"id": cid, "thumb": _media_url(f"/files/{pid}", step, thumb),
                    "label": _label(c, label_key)})
    return out


def _next_step(client: StudioClient, pid: str) -> str | None:
    """Próxima etapa **segundo o backend** (`current` do guia). Nunca calculada aqui (ADR-010 a);
    qualquer falha de leitura degrada para `None` — o dado é enriquecimento, não fluxo."""
    try:
        guide = client.get(f"/api/projects/{pid}/guide")
    except StudioApiError:
        return None
    current = guide.get("current") if isinstance(guide, dict) else None
    return current if isinstance(current, str) else None


def _result_json(selected: list[str], next_step: str | None) -> str:
    """Sufixo maquinalmente legível do retorno das `*_pick` (contrato consumido pelo chat).

    Sempre a ÚLTIMA linha, sempre começando por `{"selected":`, emitido só quando a seleção foi
    de fato gravada — a ausência do sufixo significa "nada foi selecionado".
    """
    return json.dumps({"selected": list(selected), "next_step": next_step},
                      ensure_ascii=False, separators=(", ", ": "))


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
          title: str, minimum: int, maximum: int | None, select_body,
          cands_params: dict | None = None, label_key: str = "batch",
          empty_text: str | None = None, ok_text=None,
          no_ui_text: str | None = None, no_answer_text: str | None = None) -> str:
    """Fluxo único das `*_pick` de etapa: busca candidatas, mostra a grade, aplica a seleção.

    Os textos são parametrizáveis para que cada etapa preserve a frase que já usa hoje; o sufixo
    JSON só sai no caminho em que o `select` gravou.
    """
    try:
        payload = client.get(cands_path, cands_params)
    except StudioApiError as e:
        return str(e)
    imgs = _images_for(pid, step, payload, label_key)
    if not imgs:
        return empty_text or f"Nenhuma candidata na etapa {step} ainda — gere ou importe antes de escolher."
    ans = ui.choose_images(client, title, imgs, minimum=minimum, maximum=maximum)
    if ans.get("no_ui"):
        return no_ui_text.format(ids=", ".join(i["id"] for i in imgs)) if no_ui_text else (
            "Sem interface para escolher aqui. Candidatas disponíveis: "
            + ", ".join(i["id"] for i in imgs) + ". Diga quais escolher.")
    if not ans.get("answered"):
        return no_answer_text or "O usuário não escolheu (sem resposta). Você pode perguntar de novo."
    ids = ans.get("selected") or []
    if not ids:
        return no_answer_text or "O usuário não selecionou nenhuma imagem."
    try:
        client.post(select_path, select_body(ids))
    except StudioApiError as e:
        return str(e)
    texto = ok_text(ids) if ok_text else f"{len(ids)} imagem(ns) selecionada(s) e salva(s) na etapa {step}."
    return f"{texto}\n{_result_json(ids, _next_step(client, pid))}"


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
                 select_body=lambda ids: {"ids": ids, "notes": {}}, label_key="term")


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
    prefix = _character_prefix(client, pid)
    if prefix:
        instruction = (f"Keep this exact character identity: {prefix}. " + instruction).strip()
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
    # a base final é UMA imagem; select da base recebe {id, note}. `GET /base/candidates` devolve
    # um DICT (`{candidates, final}`) e a `thumb` já vem prefixada com `base/` — os dois casos são
    # tratados pelos helpers compartilhados, e é por isso que esta tool não tem laço próprio.
    return _pick(client, pid=pid, step="base", cands_path=f"/api/projects/{pid}/base/candidates",
                 select_path=f"/api/projects/{pid}/base/select",
                 title="Escolha a imagem base final", minimum=1, maximum=1,
                 select_body=lambda ids: {"id": ids[0], "note": note}, label_key="kind",
                 empty_text="Nenhuma candidata de base ainda — gere com `base_generate` antes.",
                 ok_text=lambda ids: "Imagem base escolhida e salva.",
                 no_ui_text="Sem interface aqui. Candidatas: {ids}. Diga qual escolher.",
                 no_answer_text="O usuário não escolheu a base.")


# ---------- 4 · Storyboard (motor local grátis + escolha) ----------
def storyboard_local_generate(client: StudioClient, pid: str, prompt: str, count: int = 4,
                              model: str = "flux-schnell") -> str:
    if not prompt.strip():
        return "Escreva o prompt do keyframe (em inglês, aula 007)."
    prefix = _character_prefix(client, pid)
    if prefix:
        prompt = f"{prompt}. Character identity (keep identical): {prefix}"
    try:
        client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    {"prompt": prompt, "count": count, "model": model})
    except StudioApiError as e:
        return str(e)  # 409 se o motor local (engine/ComfyUI) estiver offline
    return f"Keyframes locais (grátis) sendo gerados com {model}. Acompanhe com `job_wait` (etapa storyboard)."


def storyboard_pick(client: StudioClient, pid: str) -> str:
    # `GET /storyboard/candidates` devolve `{"ideas": [...]}` (chave `ideas`, não `candidates`) e a
    # `thumb` já vem prefixada com `storyboard/` — ambos tratados por `_candidate_rows`/`_media_url`.
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


# ---------- Personagem e identidade (ADR-039) ----------
def _char_images(cid: str, step: str, cands: Any) -> list[dict]:
    """Mesmo helper de URL das etapas, com base `/cfiles/{cid}` (mount da biblioteca, ADR-039).
    A legenda continua sendo `view`/`name`: personagem não tem lote nem termo de busca."""
    out = []
    for c in _candidate_rows(cands):
        thumb = c.get("thumb")
        if thumb and isinstance(thumb, str) and c.get("id"):
            out.append({"id": c["id"], "thumb": _media_url(f"/cfiles/{cid}", step, thumb),
                        "label": c.get("view") or c.get("name") or ""})
    return out


def _character_prefix(client: StudioClient, pid: str) -> str:
    """Descritor do personagem aplicado à campanha, para reancorar os prompts (ADR-039)."""
    try:
        data = client.get(f"/api/projects/{pid}/character") or {}
    except StudioApiError:
        return ""
    ch = data.get("character") if isinstance(data, dict) else None
    return (ch or {}).get("descriptor", "") if ch else ""


def character_list(client: StudioClient) -> str:
    data = client.get("/api/characters") or []
    if not data:
        return "Nenhum personagem ainda. Crie um com `character_create`."
    return "Personagens:\n" + "\n".join(
        f"- {c['name']} (id `{c['id']}`, {c.get('style', 'foto')})"
        + (" — fixado" if c.get("locked_ref") else " — a fixar") for c in data)


def character_create(client: StudioClient, name: str, style: str = "foto") -> str:
    c = client.post("/api/characters", {"name": name, "style": style})
    return f"Personagem '{c['name']}' criado (id `{c['id']}`). Explore variações com `character_explore`."


def character_explore(client: StudioClient, cid: str, brief: str, count: int = 6) -> str:
    if not brief.strip():
        return "Escreva um brief do personagem (em inglês)."
    try:
        client.post(f"/api/characters/{cid}/explore", {"brief": brief, "count": count})
    except StudioApiError as e:
        return str(e)
    return (f"Explorando {count} variações no motor local (grátis). É GPU, leva alguns minutos — "
            "espere com `character_wait` e então use `character_pick`.")


def character_wait(client: StudioClient, cid: str, timeout: int = 900, _sleep=time.sleep) -> str:
    """Espera o job do personagem (explore/sheet) terminar. O job de personagem tem URL própria
    (`/api/characters/{cid}/job`), diferente da URL de job das etapas — por isso NÃO use `job_wait`."""
    deadline = time.monotonic() + max(1, timeout)
    viu_running = False
    while time.monotonic() < deadline:
        try:
            g = client.get(f"/api/characters/{cid}/job")
        except StudioApiError as e:
            return str(e)
        state = g.get("state", "idle")
        if state == "running":
            viu_running = True
            _sleep(2.0)
            continue
        if state == "idle" and not viu_running:
            return f"Personagem {cid}: nenhum trabalho em andamento."
        if g.get("error"):
            return f"Personagem {cid}: o job falhou — {g['error']}"
        return f"Personagem {cid}: {g.get('mode', 'job')} concluído ({g.get('added', 0)}/{g.get('total', 0)})."
    return f"Personagem {cid}: ainda gerando após {timeout}s (rode `character_wait` de novo)."


def character_pick(client: StudioClient, cid: str) -> str:
    """Mostra as variações para o USUÁRIO escolher o personagem e o fixa (gera o descritor)."""
    try:
        cands = client.get(f"/api/characters/{cid}/candidates", {"step": "explore"}) or []
    except StudioApiError as e:
        return str(e)
    imgs = _char_images(cid, "explore", cands)
    if not imgs:
        try:
            job = client.get(f"/api/characters/{cid}/job")
        except StudioApiError:
            job = {}
        if job.get("state") == "running":
            return (f"Ainda gerando as variações ({job.get('added', 0)}/{job.get('total', 0)}). "
                    "Espere com `character_wait` e chame de novo.")
        if job.get("error"):
            return f"A exploração falhou: {job['error']} (o motor local/ComfyUI está no ar?)."
        return "Nenhuma variação ainda — rode `character_explore` antes."
    ans = ui.choose_images(client, "Escolha o personagem (o que você acertou)", imgs, minimum=1, maximum=1)
    if ans.get("no_ui"):
        return "Sem interface aqui. Variações: " + ", ".join(i["id"] for i in imgs) + ". Diga qual fixar."
    if not ans.get("answered") or not ans.get("selected"):
        return "O usuário não escolheu o personagem."
    escolhido = ans["selected"][0]
    meta = client.post(f"/api/characters/{cid}/lock", {"candidate_id": escolhido, "step": "explore"}) or {}
    # `next_step` é `null`: personagem é biblioteca global (ADR-039), fora da cadeia das 10 etapas —
    # a chave fica no sufixo para o shape ser único nas 5 `*_pick`.
    return (f"Personagem fixado. Descritor de identidade:\n{meta.get('descriptor', '(gerado)')}"
            f"\n{_result_json([escolhido], None)}")


def character_sheet(client: StudioClient, cid: str) -> str:
    try:
        client.post(f"/api/characters/{cid}/sheet", {})
    except StudioApiError as e:
        return str(e)
    return "Gerando o character sheet (frente, 3/4, perfil, corpo inteiro) no motor local. Espere com `character_wait`."


def character_apply(client: StudioClient, pid: str, cid: str) -> str:
    try:
        client.post(f"/api/projects/{pid}/character", {"cid": cid})
    except StudioApiError as e:
        return str(e)
    return ("Personagem aplicado à campanha. A partir de agora eu injeto o descritor de identidade "
            "nos prompts das etapas 3–5, para manter a mesma pessoa entre as cenas.")


def character_bind_soul(client: StudioClient, cid: str, variant: str = "soul-2") -> str:
    """Treina um Soul ID (Higgsfield, PAGO — plano Basic+) para identidade em foto/vídeo."""
    if ui.chat_id():
        ans = ui.confirm(client, "Treinar Soul ID (Higgsfield, plano pago)",
                         "Treina um modelo de identidade da pessoa. Requer plano Basic+ na Higgsfield.")
        if not ans.get("answered") or not ans.get("confirmed"):
            return "Treino de Soul cancelado pelo usuário."
    try:
        client.post(f"/api/characters/{cid}/soul", {"variant": variant})
    except StudioApiError as e:
        return str(e)
    return f"Soul treinado ({variant}). A identidade paga fica disponível para gerar com `--soul-id`."


def character_score(client: StudioClient, cid: str, candidate_id: str, step: str = "explore") -> str:
    try:
        res = client.post(f"/api/characters/{cid}/score", {"candidate_id": candidate_id, "step": step})
    except StudioApiError as e:
        return str(e)
    if not res.get("available"):
        return f"Nota de identidade indisponível: {res.get('reason')}"
    return f"Nota de identidade (similaridade facial): {res.get('score')}"
